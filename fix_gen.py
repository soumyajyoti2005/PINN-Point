import os

with open('backend/app/sim/generate_dataset.py', 'r') as f:
    content = f.read()

new_content = """import os
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
import pyswmm

from app.sim.make_swmm_inp import build_inp_text, parse_continuity_errors
from app.sim.storms import generate_storm, blockage_injection, apply_sensor_effects

def split_dataset(num_storms: int, pipes: list, rng: np.random.Generator, held_out_fraction: float = 0.15):
    splits = {}
    for i in range(num_storms):
        r = rng.random()
        if r < 0.8: splits[f"storm_{i:04d}"] = "train"
        elif r < 0.9: splits[f"storm_{i:04d}"] = "val"
        else: splits[f"storm_{i:04d}"] = "test"
        
    num_held_out = int(len(pipes) * held_out_fraction)
    held_out_pipes = [p["id"] for p in rng.choice(pipes, num_held_out, replace=False)]
    return splits, held_out_pipes

from app.sim.run_swmm import run_simulation

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
        
        sim_dur = max(120, dur + 45)
        
        base_inp = build_inp_text(network, storm_inp, settings, pipe_diam_overrides=None, duration_minutes=sim_dur)
        
        t0 = time.time()
        base_res = run_simulation(base_inp)
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
            
            base_mask = np.ones(len(node_ids_base), dtype=bool)
            
            np.savez_compressed(
                os.path.join(out_dir, f"{run_id}.npz"),
                clean=base_res["depths"],
                observed=base_res["depths"],
                node_ids=node_ids_base,
                rain=series,
                t_min=np.arange(len(base_res["depths"])),
                sensor_mask=base_mask
            )
            
        manifest_rows.append(base_row)
        
        sevs = [0.3, 0.6, 0.9]
        run_rng.shuffle(sevs)
        
        for k, sev in enumerate(sevs):
            pipe = get_next_pipe()
            pid = pipe["id"]
            
            overrides = blockage_injection(network, sev, pid)
            
            block_inp = build_inp_text(network, storm_inp, settings, pipe_diam_overrides=overrides, duration_minutes=sim_dur)
            block_res = run_simulation(block_inp)
            
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
                
                np.savez_compressed(
                    os.path.join(out_dir, f"{run_id_block}.npz"),
                    clean=block_res["depths"],
                    observed=obs,
                    node_ids=node_ids,
                    rain=series,
                    t_min=np.arange(len(block_res["depths"])),
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
    
    print(f"\\nManifest summary:")
    print("Splits:\\n", df["split"].value_counts())
    print("Severities:\\n", df["severity"].value_counts())
    print("Sensor Fractions:\\n", df["sensor_fraction"].value_counts())
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

if __name__ == "__main__":
    generate_dataset()
"""

with open('backend/app/sim/generate_dataset.py', 'w') as f:
    f.write(new_content)
