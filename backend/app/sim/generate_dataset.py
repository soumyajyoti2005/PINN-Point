import os
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import uuid
import pyswmm

from app.sim.make_swmm_inp import build_inp_text, parse_continuity_errors
from app.sim.storms import generate_storm, blockage_injection, apply_sensor_effects

def resample_time_series(raw_times, raw_depths, target_duration_s=None, step_s=60.0):
    raw_times_arr = np.array(raw_times)
    raw_depths_arr = np.array(raw_depths)
    if target_duration_s is None:
        target_duration_s = raw_times_arr[-1]
    n_samples = int(target_duration_s // step_s) + 1
    t_grid = np.arange(n_samples) * step_s
    
    depths_interp = np.zeros((len(t_grid), raw_depths_arr.shape[1]))
    for i in range(raw_depths_arr.shape[1]):
        depths_interp[:, i] = np.interp(t_grid, raw_times_arr, raw_depths_arr[:, i])
    return t_grid, depths_interp

def split_dataset(num_storms: int, pipes: list, rng: np.random.Generator, held_out_fraction: float = 0.15):
    splits = {}
    storm_ids = [f"storm_{i:04d}" for i in range(num_storms)]
    
    shuffled_storms = storm_ids.copy()
    rng.shuffle(shuffled_storms)
    
    n_val = round(0.1 * num_storms)
    n_test = round(0.1 * num_storms)
    
    if num_storms >= 10:
        n_val = max(1, n_val)
        n_test = max(1, n_test)
        
    val_storms = set(shuffled_storms[:n_val])
    test_storms = set(shuffled_storms[n_val:n_val+n_test])
    
    for s in storm_ids:
        if s in val_storms:
            splits[s] = "val"
        elif s in test_storms:
            splits[s] = "test"
        else:
            splits[s] = "train"
            
    num_held_out = 0
    if len(pipes) >= 7:
        num_held_out = max(1, round(len(pipes) * held_out_fraction))
        
    held_out_pipes = []
    if num_held_out > 0:
        held_out_pipes = [p["id"] for p in rng.choice(pipes, num_held_out, replace=False)]
        
    return splits, held_out_pipes

def run_simulation(inp_text: str, network: dict = None) -> dict:
    run_id = str(uuid.uuid4())
    inp_path = f"/tmp/{run_id}.inp"
    rpt_path = f"/tmp/{run_id}.rpt"
    out_path = f"/tmp/{run_id}.out"
    
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    depths = []
    times_s = []
    node_ids = []
    status = "failed"
    
    try:
        with pyswmm.Simulation(inp_path) as sim:
            sim.step_advance(10)
            node_objs = [node for node in pyswmm.Nodes(sim)]
            node_ids = [node.nodeid for node in node_objs]
            
            start_time = sim.start_time
            
            raw_depths = [[node.depth for node in node_objs]]
            raw_times = [0.0]
            
            for step in sim:
                elapsed = (sim.current_time - start_time).total_seconds()
                raw_depths.append([node.depth for node in node_objs])
                raw_times.append(elapsed)
                
            end_time = sim.current_time
            status = "success"
    except Exception as e:
        print(f"Simulation failed: {e}")
        
    depths_arr = np.array([])
    times_arr = np.array([])
    
    if status == "success":
        target_duration = (end_time - start_time).total_seconds()
        t_grid, d_interp = resample_time_series(raw_times, raw_depths, target_duration)
        depths_arr = d_interp
        times_arr = t_grid
        
        if network is not None:
            target_order = [n["id"] for n in network.get("nodes", [])]
            idx_map = [node_ids.index(nid) for nid in target_order if nid in node_ids]
            depths_arr = depths_arr[:, idx_map]
            node_ids = [node_ids[i] for i in idx_map]
    
    runoff_err = 0.0
    routing_err = 0.0
    
    if os.path.exists(rpt_path):
        runoff_err, routing_err = parse_continuity_errors(rpt_path)
        
    for p in [inp_path, rpt_path, out_path]:
        if os.path.exists(p):
            os.remove(p)
            
    return {
        "status": status,
        "depths": depths_arr,
        "times_s": times_arr,
        "node_ids": node_ids,
        "runoff_err_pct": runoff_err,
        "routing_err_pct": routing_err,
        "flood_volume_m3": 0.0
    }

def generate_dataset():
    print("Starting dataset generation...")
    data_dir = os.getenv("DATA_DIR", "/data")
    area = os.getenv("AREA_NAME", "kolkata-amherst")
    dataset_name = os.getenv("DATASET_NAME", "sample")
    dataset_runs = int(os.getenv("DATASET_RUNS", "6"))
    base_seed = int(os.getenv("DATASET_SEED", "42"))
    max_peak = float(os.getenv("DATASET_MAX_PEAK_MM_HR", "80.0"))
    detectable_m = float(os.getenv("DATASET_DETECTABLE_M", "0.05"))
    
    out_dir = os.path.join(data_dir, "datasets", dataset_name)
    os.makedirs(out_dir, exist_ok=True)
    
    with open(f"{data_dir}/swmm/{area}_network.json") as f:
        network = json.load(f)
        
    settings = {
        'SWMM_CATCHMENT_HA_PER_NODE': float(os.getenv("SWMM_CATCHMENT_HA_PER_NODE", "0.02")),
        'SWMM_IMPERVIOUS_PCT': float(os.getenv("SWMM_IMPERVIOUS_PCT", "100.0")),
        'SWMM_PONDED_AREA_M2': float(os.getenv("SWMM_PONDED_AREA_M2", "100.0")),
    }
    
    sq = np.random.SeedSequence(base_seed)
    rng = np.random.default_rng(sq)
    
    splits, held_out_pipes = split_dataset(dataset_runs, network.get("pipes", []), rng)
    
    print(f"Splits sizes: Train {list(splits.values()).count('train')}, Val {list(splits.values()).count('val')}, Test {list(splits.values()).count('test')}")
    print(f"Held out pipes count: {len(held_out_pipes)}")
    
    manifest_rows = []
    
    all_pipes = list(network.get("pipes", []))
    pool_rng = np.random.default_rng(base_seed)
    pipe_pool = []
    
    def get_next_pipe():
        nonlocal pipe_pool
        if not pipe_pool:
            pipe_pool = all_pipes.copy()
            pool_rng.shuffle(pipe_pool)
        return pipe_pool.pop()
        
    node_depth_dict = {n["id"]: n.get("depth_m", np.inf) for n in network.get("nodes", [])}
    
    for i in range(dataset_runs):
        storm_id = f"storm_{i:04d}"
        run_rng = np.random.default_rng(sq.spawn(1)[0])
        
        series, params = generate_storm(run_rng, max_peak_cap=max_peak)
        dur = params["duration_min"]
        
        storm_inp = []
        for t, val in enumerate(series):
            storm_inp.append((t, val))
            
        storm_inp.append((dur+1, 0.0))
        storm_inp.append((dur+60, 0.0))
        
        sim_dur = 120
        
        base_inp = build_inp_text(network, storm_inp, settings, pipe_diam_overrides=None, duration_minutes=sim_dur)
        
        t0 = time.time()
        base_res = run_simulation(base_inp, network)
        dt = time.time() - t0
        
        if i == 0:
            print(f"One run takes ~{dt:.2f}s. Estimated for 1000 runs: {dt*1000/60:.1f} mins.")
            
        run_id = f"{storm_id}_base"
        
        base_row = {
            "run_id": run_id,
            "storm_id": storm_id,
            "split": splits[storm_id],
            "blocked_pipe_id": None,
            "blocked_pipe_id_2": None,
            "severity": 0.0,
            "sigma_m": 0.0,
            "dropout_frac": 0.0,
            "sensor_fraction": 1.0,
            "sensor_count": len(base_res.get("node_ids", [])),
            "sensor_node_ids": base_res.get("node_ids", []),
            "seed": base_seed + i,
            "peak_mm_hr": params["peak_mm_hr"],
            "duration_min": dur,
            "peak_position": params["peak_position"],
            "runoff_err_pct": base_res.get("runoff_err_pct", 0.0),
            "routing_err_pct": base_res.get("routing_err_pct", 0.0),
            "flood_volume_m3": base_res.get("flood_volume_m3", 0.0),
            "flagged": False,
            "status": base_res["status"],
            "rim_exceeded": False,
            "peak_signal_m": None,
            "max_signal_m": None,
            "detectable": None
        }
        
        if base_res["status"] == "success":
            flag = abs(base_res["runoff_err_pct"]) > 5.0 or abs(base_res["routing_err_pct"]) > 5.0
            base_row["flagged"] = flag
            
            node_ids_base = np.array(base_res["node_ids"])
            depths_m_base = np.array([node_depth_dict[nid] for nid in node_ids_base])
            
            rim_exceeded = np.any(base_res["depths"] > depths_m_base)
            base_row["rim_exceeded"] = rim_exceeded
            
            base_sigma = run_rng.uniform(0.01, 0.03)
            base_drop = run_rng.uniform(0.0, 0.05)
            base_sens_frac = run_rng.choice([1.0, 0.5, 0.3])
            
            base_mask = np.zeros(len(node_ids_base), dtype=bool)
            base_idx = run_rng.choice(len(node_ids_base), int(len(node_ids_base) * base_sens_frac), replace=False)
            base_mask[base_idx] = True
            
            base_obs = apply_sensor_effects(base_res["depths"], base_sigma, base_drop, base_mask, run_rng, depths_m_base)
            
            base_row["sigma_m"] = float(base_sigma)
            base_row["dropout_frac"] = float(base_drop)
            base_row["sensor_fraction"] = float(base_sens_frac)
            base_row["sensor_count"] = int(base_mask.sum())
            base_row["sensor_node_ids"] = node_ids_base[base_mask].tolist()
            
            rain_padded = np.zeros(len(base_res["times_s"]))
            min_len = min(len(series), len(rain_padded))
            rain_padded[:min_len] = series[:min_len]
            
            np.savez_compressed(
                os.path.join(out_dir, f"{run_id}.npz"),
                clean=base_res["depths"],
                observed=base_obs,
                node_ids=node_ids_base,
                rain=rain_padded,
                times_s=base_res["times_s"],
                t_min=base_res["times_s"] / 60.0,
                sensor_mask=base_mask
            )
            
        manifest_rows.append(base_row)
        
        sevs = [0.3, 0.6, 0.9]
        run_rng.shuffle(sevs)
        
        for k, sev in enumerate(sevs):
            pipe = get_next_pipe()
            pid = pipe["id"]
            
            overrides = blockage_injection(network, sev, pid)
            if pid in overrides:
                overrides[pid] = round(overrides[pid], 4)
            
            block_inp = build_inp_text(network, storm_inp, settings, pipe_diam_overrides=overrides, duration_minutes=sim_dur)
            block_res = run_simulation(block_inp, network)
            
            run_id_block = f"{storm_id}_block_{k}"
            split_label = splits[storm_id]
            if pid in held_out_pipes:
                split_label = "test_unseen_pipe"
                
            sigma = run_rng.uniform(0.01, 0.03)
            drop = run_rng.uniform(0.0, 0.05)
            sens_frac = run_rng.choice([1.0, 0.5, 0.3])
            
            if block_res["status"] == "success":
                node_ids = np.array(block_res["node_ids"])
                depths_m = np.array([node_depth_dict[nid] for nid in node_ids])
                
                mask = np.zeros(len(node_ids), dtype=bool)
                idx = run_rng.choice(len(node_ids), int(len(node_ids) * sens_frac), replace=False)
                mask[idx] = True
                
                sensor_node_ids = node_ids[mask].tolist()
                
                obs = apply_sensor_effects(block_res["depths"], sigma, drop, mask, run_rng, depths_m)
                
                # Signal
                base_clean_clipped = np.clip(base_res["depths"], 0.0, depths_m)
                block_clean_clipped = np.clip(block_res["depths"], 0.0, depths_m)
                
                min_len = min(len(block_clean_clipped), len(base_clean_clipped))
                diffs = block_clean_clipped[:min_len] - base_clean_clipped[:min_len]
                
                # from node max
                up_node = pipe["from_node"]
                if up_node in node_ids:
                    up_idx = list(node_ids).index(up_node)
                    peak_signal_m = float(np.max(diffs[:, up_idx]))
                else:
                    peak_signal_m = 0.0
                    
                max_signal_m = float(np.max(diffs))
                
                detectable = peak_signal_m >= detectable_m
                
                rim_exceeded = np.any(block_res["depths"] > depths_m)
                
                rain_padded = np.zeros(len(block_res["times_s"]))
                min_len = min(len(series), len(rain_padded))
                rain_padded[:min_len] = series[:min_len]

                np.savez_compressed(
                    os.path.join(out_dir, f"{run_id_block}.npz"),
                    clean=block_res["depths"],
                    observed=obs,
                    node_ids=node_ids,
                    rain=rain_padded,
                    times_s=block_res["times_s"],
                    t_min=block_res["times_s"] / 60.0,
                    sensor_mask=mask
                )
            else:
                sensor_node_ids = []
                mask = np.array([])
                peak_signal_m = None
                max_signal_m = None
                detectable = None
                rim_exceeded = False
            
            row = {
                "run_id": run_id_block,
                "storm_id": storm_id,
                "split": split_label,
                "blocked_pipe_id": pid,
                "blocked_pipe_id_2": None,
                "severity": sev,
                "sigma_m": sigma,
                "dropout_frac": drop,
                "sensor_fraction": sens_frac,
                "sensor_count": len(sensor_node_ids),
                "sensor_node_ids": sensor_node_ids,
                "seed": base_seed + i * 1000 + k,
                "peak_mm_hr": params["peak_mm_hr"],
                "duration_min": dur,
                "peak_position": params["peak_position"],
                "runoff_err_pct": block_res.get("runoff_err_pct", 0.0),
                "routing_err_pct": block_res.get("routing_err_pct", 0.0),
                "flood_volume_m3": block_res.get("flood_volume_m3", 0.0),
                "flagged": False,
                "status": block_res["status"],
                "rim_exceeded": rim_exceeded,
                "peak_signal_m": peak_signal_m,
                "max_signal_m": max_signal_m,
                "detectable": detectable
            }
            
            if block_res["status"] == "success":
                flag = abs(block_res["runoff_err_pct"]) > 5.0 or abs(block_res["routing_err_pct"]) > 5.0
                row["flagged"] = flag
                
            manifest_rows.append(row)
            
    df = pd.DataFrame(manifest_rows)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, os.path.join(out_dir, "manifest.parquet"))
    
    print(f"\nManifest summary:")
    print("Splits:\n", df["split"].value_counts())
    print("Severities:\n", df["severity"].value_counts())
    print("Sensor Fractions:\n", df["sensor_fraction"].value_counts())
    print("Flagged:", df["flagged"].sum())
    print("Failed:", (df["status"] == "failed").sum())
    print("Rim Exceeded:", df["rim_exceeded"].sum())
    
    detectables = df[df["detectable"] == True]
    print(f"Detectable overall: {len(detectables)} / {len(df[df['severity'] > 0.0])}")
    for sev in [0.3, 0.6, 0.9]:
        sev_df = df[df["severity"] == sev]
        det = (sev_df["detectable"] == True).sum()
        print(f"  Sev {sev}: {det} / {len(sev_df)}")
        
    counts = df[df["severity"] > 0]["blocked_pipe_id"].value_counts()
    print(f"Per-pipe blockage counts: min={counts.min()}, max={counts.max()}")
    
    # Calculate disk size
    total_size = 0
    for dirpath, _, filenames in os.walk(out_dir):
        for f in filenames:
            total_size += os.path.getsize(os.path.join(dirpath, f))
    print(f"Total size on disk: {total_size / 1e6:.2f} MB")

def main():
    generate_dataset()

if __name__ == "__main__":
    main()
