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

def get_network_and_settings(data_dir, area, manning_mult=1.0):
    with open(os.path.join(data_dir, "swmm", f"{area}_network.json")) as f:
        network = json.load(f)
    if manning_mult != 1.0:
        for p in network.get("pipes", []):
            p["manning_n"] = p.get("manning_n", 0.01) * manning_mult
    settings = {
        'SWMM_CATCHMENT_HA_PER_NODE': float(os.getenv("SWMM_CATCHMENT_HA_PER_NODE", "0.02")),
        'SWMM_IMPERVIOUS_PCT': float(os.getenv("SWMM_IMPERVIOUS_PCT", "100.0")),
        'SWMM_PONDED_AREA_M2': float(os.getenv("SWMM_PONDED_AREA_M2", "100.0")),
    }
    return network, settings

def build_nx_graph(network):
    G = nx.Graph()
    for p in network.get("pipes", []):
        G.add_edge(p["from_node"], p["to_node"], id=p["id"])
    return G

def get_pipe_distance(G, p1_id, p2_id, network):
    if p1_id == p2_id: return 0
    p1 = next((p for p in network.get("pipes", []) if p["id"] == p1_id), None)
    p2 = next((p for p in network.get("pipes", []) if p["id"] == p2_id), None)
    if not p1 or not p2: return np.inf
    try:
        d1 = nx.shortest_path_length(G, p1["from_node"], p2["from_node"])
        d2 = nx.shortest_path_length(G, p1["from_node"], p2["to_node"])
        d3 = nx.shortest_path_length(G, p1["to_node"], p2["from_node"])
        d4 = nx.shortest_path_length(G, p1["to_node"], p2["to_node"])
        return min(d1, d2, d3, d4) + 1
    except nx.NetworkXNoPath:
        return np.inf

def generate_hypotheses(storm_id, rain_series, pipe_ids, sevs, network, settings, sim_dur=120):
    hypotheses = {}
    storm_inp = [(t, val) for t, val in enumerate(rain_series)]
    
    base_inp = build_inp_text(network, storm_inp, settings, duration_minutes=sim_dur)
    base_res = run_simulation(base_inp, network)
    hypotheses['none'] = base_res['depths'] if base_res['status'] == 'success' else None

    for pid in pipe_ids:
        for sev in sevs:
            overrides = blockage_injection(network, sev, pid)
            if pid in overrides: overrides[pid] = round(overrides[pid], 4)
            inp = build_inp_text(network, storm_inp, settings, pipe_diam_overrides=overrides, duration_minutes=sim_dur)
            res = run_simulation(inp, network)
            hypotheses[f"{pid}_{sev}"] = res['depths'] if res['status'] == 'success' else None

    return storm_id, hypotheses

def worker_fn(args):
    storm_id, rain_series, pipe_ids, sevs, data_dir, area, rain_scales = args
    network, settings = get_network_and_settings(data_dir, area)
    
    all_hypotheses = {}
    for r_scale in rain_scales:
        rain_mod = rain_series * r_scale
        _, h = generate_hypotheses(storm_id, rain_mod, pipe_ids, sevs, network, settings)
        for k, v in h.items():
            all_hypotheses[f"{k}__scale{r_scale}"] = v
            
    return storm_id, all_hypotheses

def calculate_log_likelihood(obs, pred, mask, sigma, max_idx):
    if pred is None: return -np.inf
    max_idx = min(max_idx, obs.shape[0], pred.shape[0])
    obs_trunc = obs[:max_idx, mask]
    pred_trunc = pred[:max_idx, mask]
    valid_mask = ~np.isnan(obs_trunc)
    if not np.any(valid_mask): return -np.inf
    sse = np.sum((obs_trunc[valid_mask] - pred_trunc[valid_mask])**2)
    return -sse / (2 * max(sigma, 0.001)**2)

def evaluate_split(df, cache, G, network, threshold=1.0, cutoffs_min=[15, 30, 45, 60, 90, 120]):
    pipe_ids = [p["id"] for p in network.get("pipes", [])]
    results = {c: {'top1': 0, 'top3': 0, 'top5': 0, 'total': 0, 'hops': []} for c in cutoffs_min}
    fa = {'false_alarms': 0, 'baseline_runs': 0}
    
    for idx, row in df.iterrows():
        storm_id = row['storm_id']
        if storm_id not in cache: continue
            
        hypotheses = cache[storm_id]
        obs = row['obs_data']
        times_s = row['times_s']
        mask = row['mask_data']
        sigma = row['sigma_m']
        true_pipe = row['blocked_pipe_id']
        if pd.isna(true_pipe) or true_pipe == "": true_pipe = "none"
            
        for c_min in cutoffs_min:
            max_idx = np.searchsorted(times_s, c_min * 60, side='right')
            if max_idx == 0: continue
                
            ll_dict = {}
            for h_key, pred in hypotheses.items():
                ll_dict[h_key] = calculate_log_likelihood(obs, pred, mask, sigma, max_idx)
                
            pipe_scores = {}
            for h_key, ll in ll_dict.items():
                base_k = h_key.split('__scale')[0]
                p_id = 'none' if base_k == 'none' else base_k.rsplit('_', 1)[0]
                if p_id not in pipe_scores: pipe_scores[p_id] = []
                pipe_scores[p_id].append(ll)
                
            final_scores = {}
            for p_id, lls in pipe_scores.items():
                max_ll = max(lls)
                if max_ll == -np.inf:
                    final_scores[p_id] = -np.inf
                else:
                    final_scores[p_id] = max_ll + np.log(sum(np.exp(ll - max_ll) for ll in lls))
            
            ll_none = final_scores.get('none', -np.inf)
            if len(final_scores) <= 1: continue
            
            best_blocked = max((score, p_id) for p_id, score in final_scores.items() if p_id != 'none')
            best_blocked_score, best_blocked_id = best_blocked
            
            if (best_blocked_score - ll_none) < threshold:
                pred_pipe = 'none'
                sorted_pipes = ['none'] + [p for p, s in sorted(final_scores.items(), key=lambda x: x[1], reverse=True) if p != 'none']
            else:
                sorted_pipes = [p for p, s in sorted(final_scores.items(), key=lambda x: x[1], reverse=True) if p != 'none']
                pred_pipe = sorted_pipes[0]
            
            if true_pipe == "none":
                if c_min == 120:
                    fa['baseline_runs'] += 1
                    if pred_pipe != "none": fa['false_alarms'] += 1
            else:
                results[c_min]['total'] += 1
                if true_pipe == sorted_pipes[0]: results[c_min]['top1'] += 1
                if true_pipe in sorted_pipes[:3]: results[c_min]['top3'] += 1
                if true_pipe in sorted_pipes[:5]: results[c_min]['top5'] += 1
                
                if c_min == 120 and pred_pipe != "none" and true_pipe != pred_pipe:
                    h = get_pipe_distance(G, true_pipe, pred_pipe, network)
                    if h != np.inf: results[c_min]['hops'].append(h)
    
    print("\nMetrics:")
    def format_ci(count, total):
        if total == 0: return "0.0% [0.0%, 0.0%] (N=0)"
        p = count / total
        alpha = 0.05
        lower = stats.beta.ppf(alpha / 2, count, total - count + 1) if count > 0 else 0.0
        upper = stats.beta.ppf(1 - alpha / 2, count + 1, total - count) if count < total else 1.0
        return f"{p*100:.1f}% [{lower*100:.1f}%, {upper*100:.1f}%] (N={total})"
        
    for c_min in cutoffs_min:
        tot = results[c_min]['total']
        if tot > 0:
            top1 = format_ci(results[c_min]['top1'], tot)
            top3 = format_ci(results[c_min]['top3'], tot)
            top5 = format_ci(results[c_min]['top5'], tot)
            print(f"Delay {c_min:3d} min -> Top-1: {top1}, Top-3: {top3}, Top-5: {top5}")
    
    if len(results[120]['hops']) > 0:
        print(f"Avg Hop Distance (120 min, wrong preds only): {np.mean(results[120]['hops']):.2f} (N={len(results[120]['hops'])})")
        
    if fa['baseline_runs'] > 0:
        print(f"False Alarm Rate (120 min): {format_ci(fa['false_alarms'], fa['baseline_runs'])}")


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
    
    unseen_storms = df[df['split'] == 'test_unseen_pipe']['storm_id'].unique()
    unseen_storms = np.random.choice(unseen_storms, min(80, len(unseen_storms)), replace=False)
    
    all_storms = list(test_storms) + list(unseen_storms)
    df_eval = df[df['storm_id'].isin(all_storms)].copy()
    
    print(f"Evaluating {len(df_eval)} events across {len(all_storms)} storms...")
    
    obs_list = []
    times_list = []
    mask_list = []
    for idx, row in df_eval.iterrows():
        npz_path = os.path.join(data_dir, "datasets", dataset_name, f"{row['run_id']}.npz")
        data = np.load(npz_path)
        obs_list.append(data['observed'])
        times_list.append(data['times_s'])
        mask_list.append(data['sensor_mask'])
    df_eval['obs_data'] = obs_list
    df_eval['times_s'] = times_list
    df_eval['mask_data'] = mask_list
    
    tasks = []
    for s_id in all_storms:
        s_runs = df[df['storm_id'] == s_id]
        if len(s_runs) == 0: continue
        run_id = s_runs.iloc[0]['run_id']
        npz_path = os.path.join(data_dir, "datasets", dataset_name, f"{run_id}.npz")
        data = np.load(npz_path)
        tasks.append((s_id, data['rain'], pipe_ids, sevs, data_dir, area, [0.9, 1.0, 1.1]))
        
    cache = {}
    t0 = time.time()
    
    print("Generating hypotheses via SWMM with nuisance parameters...")
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(worker_fn, task): task[0] for task in tasks}
        for future in as_completed(futures):
            s_id, hypotheses = future.result()
            cache[s_id] = hypotheses
            
    dt = time.time() - t0
    events = len(df_eval)
    if events > 0:
        print(f"Generation took {dt:.1f}s ({dt/events:.2f}s per event on average).")
    
    if 'detectable' in df_eval.columns:
        df_detectable = df_eval[df_eval['detectable'] == True]
    else:
        df_detectable = df_eval
        
    print("\n================== ALL EVENTS ==================")
    print("\n--- TEST SPLIT ---")
    evaluate_split(df_eval[df_eval['split'] == 'test'], cache, G, network, threshold)
    print("\n--- TEST UNSEEN PIPE SPLIT ---")
    evaluate_split(df_eval[df_eval['split'] == 'test_unseen_pipe'], cache, G, network, threshold)
    
    print("\n================== DETECTABLE SUBSET ==================")
    print("\n--- TEST SPLIT ---")
    evaluate_split(df_detectable[df_detectable['split'] == 'test'], cache, G, network, threshold)
    print("\n--- TEST UNSEEN PIPE SPLIT ---")
    evaluate_split(df_detectable[df_detectable['split'] == 'test_unseen_pipe'], cache, G, network, threshold)
    
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
    print("\n--- ROBUSTNESS: +10% / -10% Rain, 0.45 / 0.75 Severity ---")
    evaluate_split(df_rob, cache, G, network, threshold)
    
if __name__ == "__main__":
    main()
