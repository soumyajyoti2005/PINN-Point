import os
import json
import numpy as np
import pandas as pd
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import scipy.stats as stats
import networkx as nx

from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import run_simulation
from app.sim.storms import blockage_injection
from app.ml.scan_infer import get_network_and_settings, build_nx_graph, get_pipe_distance, generate_hypotheses, worker_fn, calculate_log_likelihood, evaluate_split

def sim_rob(args):
    s_id, rain, nw, pid, sev, r_scale, mask, sigma = args
    storm_inp = [(t, val * r_scale) for t, val in enumerate(rain)]
    settings = {
        'SWMM_CATCHMENT_HA_PER_NODE': float(os.getenv("SWMM_CATCHMENT_HA_PER_NODE", "0.02")),
        'SWMM_IMPERVIOUS_PCT': float(os.getenv("SWMM_IMPERVIOUS_PCT", "100.0")),
        'SWMM_PONDED_AREA_M2': float(os.getenv("SWMM_PONDED_AREA_M2", "100.0")),
    }
    if pid != "none":
        overrides = blockage_injection(nw, sev, pid)
        inp = build_inp_text(nw, storm_inp, settings, pipe_diam_overrides=overrides)
    else:
        inp = build_inp_text(nw, storm_inp, settings)
        
    res = run_simulation(inp, nw)
    obs = res['depths'] + np.random.normal(0, sigma, res['depths'].shape)
    obs[:, ~mask] = np.nan
    
    return {
        'storm_id': s_id, 'blocked_pipe_id': pid, 'severity': sev, 'sigma_m': sigma,
        'obs_data': obs, 'times_s': np.arange(len(obs)) * 60, 'mask_data': mask
    }

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    dataset_name = os.environ.get("DATASET_NAME", "large1000")
    
    network, _ = get_network_and_settings(data_dir, area)
    pipe_ids = [p["id"] for p in network.get("pipes", [])]
    sevs = [0.3, 0.6, 0.9]
    G = build_nx_graph(network)
    
    manifest_path = os.path.join(data_dir, "datasets", dataset_name, "manifest.parquet")
    df = pd.read_parquet(manifest_path)
    threshold = 5.0
    
    np.random.seed(42)
    test_storms = df[df['split'] == 'test']['storm_id'].unique()
    test_storms = np.random.choice(test_storms, min(80, len(test_storms)), replace=False)
    
    print("\n================== ROBUSTNESS ==================")
    print("Simulating off-grid & noise events...")
    rob_tasks = []
    rob_eval_rows = []
    for s_id in test_storms[:10]:
        base_run_id = df[(df['storm_id'] == s_id)].iloc[0]['run_id']
        data = np.load(os.path.join(data_dir, "datasets", dataset_name, f"{base_run_id}.npz"))
        rain = data['rain']
        mask = data['sensor_mask']
        sigma = df[(df['storm_id'] == s_id)].iloc[0]['sigma_m']
        
        rob_tasks.append((s_id, rain, network, pipe_ids[0], 0.45, 1.1, mask, sigma))
        rob_tasks.append((s_id, rain, network, pipe_ids[5], 0.75, 0.9, mask, sigma))
        rob_tasks.append((s_id, rain, network, "none", 0.0, 1.1, mask, sigma))
        
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        for r_res in executor.map(sim_rob, rob_tasks):
            rob_eval_rows.append(r_res)
            
    df_rob = pd.DataFrame(rob_eval_rows)
    
    # Generate hypothesis cache for these 10 storms
    tasks = []
    for s_id in test_storms[:10]:
        base_run_id = df[(df['storm_id'] == s_id)].iloc[0]['run_id']
        data = np.load(os.path.join(data_dir, "datasets", dataset_name, f"{base_run_id}.npz"))
        tasks.append((s_id, data['rain'], pipe_ids, sevs, data_dir, area, [0.9, 1.0, 1.1]))
        
    cache = {}
    print("Generating hypotheses for robust storms...")
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(worker_fn, task): task[0] for task in tasks}
        for future in as_completed(futures):
            s_id, hypotheses = future.result()
            cache[s_id] = hypotheses
            
    print("\n--- ROBUSTNESS: +10% / -10% Rain, 0.45 / 0.75 Severity ---")
    evaluate_split(df_rob, cache, G, network, threshold)
    
if __name__ == "__main__":
    main()

