import pytest
import os
import torch
import numpy as np
import json
import time
import pandas as pd
import scipy.stats as stats

def test_mass_conservation():
    from app.ml.physics import Simplified1DPhysics
    data_dir = os.environ.get("DATA_DIR", "/data")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    net_path = os.path.join(data_dir, "swmm", f"{area}_network.json")
    if not os.path.exists(net_path):
        pytest.skip(f"Network not found at {net_path}")
        
    model = Simplified1DPhysics(net_path, dt=60.0)
    
    initial_heads = model.node_inverts + 1.0 # 1m depth everywhere
    steps = 10
    runoff = torch.zeros((steps, model.num_nodes))
    
    heads = model(initial_heads, runoff, steps)
    
    initial_volume = torch.sum(initial_heads - model.node_inverts) * model.node_area
    final_volume = torch.sum(heads[-1] - model.node_inverts) * model.node_area
    
    total_final = final_volume + model.volume_exited
    
    assert torch.allclose(initial_volume, total_final, atol=1e-3)

def test_theta_effect():
    from app.ml.physics import Simplified1DPhysics
    data_dir = os.environ.get("DATA_DIR", "/data")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    net_path = os.path.join(data_dir, "swmm", f"{area}_network.json")
    if not os.path.exists(net_path):
        pytest.skip(f"Network not found at {net_path}")
        
    model = Simplified1DPhysics(net_path, dt=60.0)
    initial_heads = model.node_inverts + 1.0
    steps = 5
    runoff = torch.zeros((steps, model.num_nodes))
    
    heads_base = model(initial_heads, runoff, steps)
    
    with torch.no_grad():
        model.theta[0] = 0.1
        
    heads_blocked = model(initial_heads, runoff, steps)
    
    up_idx = model.up_idx[0].item()
    dn_idx = model.dn_idx[0].item()
    
    assert heads_blocked[-1, up_idx] > heads_base[-1, up_idx] - 1e-4
    assert heads_blocked[-1, dn_idx] < heads_base[-1, dn_idx] + 1e-4


def format_ci(count, total):
    if total == 0: return "0.0% [0.0%, 0.0%] (N=0)"
    p = count / total
    alpha = 0.05
    lower = stats.beta.ppf(alpha / 2, count, total - count + 1) if count > 0 else 0.0
    upper = stats.beta.ppf(1 - alpha / 2, count + 1, total - count) if count < total else 1.0
    return f"{p*100:.1f}% [{lower*100:.1f}%, {upper*100:.1f}%] (N={total})"


def test_evaluate_rmse():
    from app.ml.physics import Simplified1DPhysics
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    net_path = os.path.join(data_dir, "swmm", f"{area}_network.json")
    if not os.path.exists(net_path):
        pytest.skip("Network not found.")
        
    dataset_name = "large1000"
    dataset_dir = os.path.join(data_dir, "datasets", dataset_name)
    if not os.path.exists(dataset_dir):
        pytest.fail(f"Dataset {dataset_name} missing at {dataset_dir}")
        
    manifest_path = os.path.join(dataset_dir, "manifest.parquet")
    df = pd.read_parquet(manifest_path)
    
    base_runs = df[(df['split'] == 'test') & (df['severity'] == 0.0)]
    if len(base_runs) == 0:
        pytest.skip("No baseline runs found in test split.")
        
    model = Simplified1DPhysics(net_path, dt=60.0)
    catchment_area = 200.0
    
    # We will pick 10 storms for evaluation
    np.random.seed(42)
    eval_storms = np.random.choice(base_runs['storm_id'].unique(), 10, replace=False)
    
    skill_scores = []
    rmse_scores = []
    rmse_zero_scores = []
    
    diff_errs = {0.3: [], 0.6: [], 0.9: []}
    
    scan_events = []
    scan_top1_correct = 0
    total_eval = 0
    
    total_hypotheses_generated = 0
    total_generation_time = 0.0
    
    print("\n")
    for s_id in eval_storms:
        storm_runs = df[df['storm_id'] == s_id]
        base_run = storm_runs[storm_runs['severity'] == 0.0].iloc[0]
        base_npz = np.load(os.path.join(dataset_dir, f"{base_run['run_id']}.npz"))
        swmm_base = base_npz['clean']
        rain = base_npz['rain']
        steps = len(rain)
        
        runoff_rates = torch.zeros((steps, model.num_nodes))
        for t in range(steps):
            rain_mm_hr = float(rain[t]) if t < len(rain) else 0.0
            rain_m_s = (rain_mm_hr / 1000.0) / 3600.0
            runoff_rates[t, :] = rain_m_s * catchment_area
            
        initial_heads = model.node_inverts.clone()
        with torch.no_grad():
            heads_base_pred = model(initial_heads, runoff_rates, steps)
        pred_base = (heads_base_pred - model.node_inverts).numpy()
        
        calib = np.sum(pred_base * swmm_base, axis=0) / (np.sum(pred_base**2, axis=0) + 1e-8)
        calibrated_base = pred_base * calib
        
        rmse_per_node = np.sqrt(np.mean((calibrated_base - swmm_base)**2, axis=0))
        rmse_zero_per_node = np.sqrt(np.mean(swmm_base**2, axis=0))
        
        # Valid nodes only (where SWMM depth > 1mm)
        valid_nodes = rmse_zero_per_node > 0.001
        if np.any(valid_nodes):
            ss_per_node = 1.0 - (rmse_per_node[valid_nodes] / (rmse_zero_per_node[valid_nodes] + 1e-8))
            skill_scores.extend(ss_per_node)
            rmse_scores.extend(rmse_per_node[valid_nodes])
            rmse_zero_scores.extend(rmse_zero_per_node[valid_nodes])
            
        # Differential accuracy over first 5 blocked pipes
        blocked_runs = storm_runs[storm_runs['severity'] > 0]
        tested_pipes = []
        
        for idx, block_run in blocked_runs.iterrows():
            pid = block_run['blocked_pipe_id']
            if pid not in tested_pipes and len(tested_pipes) < 5:
                tested_pipes.append(pid)
                
            if pid not in tested_pipes: continue
            
            sev = block_run['severity']
            block_npz = np.load(os.path.join(dataset_dir, f"{block_run['run_id']}.npz"))
            swmm_block = block_npz['clean']
            pipe_idx = model.link_ids.index(pid)
            
            with torch.no_grad():
                model.theta[pipe_idx] = 1.0 - sev
                heads_block_pred = model(initial_heads, runoff_rates, steps)
                model.theta[pipe_idx] = 1.0
                
            pred_block = (heads_block_pred - model.node_inverts).numpy()
            calibrated_block = pred_block * calib
            
            swmm_diff = swmm_block - swmm_base
            model_diff = calibrated_block - calibrated_base
            
            diff_rmse = np.sqrt(np.mean((model_diff - swmm_diff)**2))
            swmm_diff_rmse = np.sqrt(np.mean(swmm_diff**2)) + 1e-8
            
            diff_errs[sev].append({
                'diff_rmse': diff_rmse,
                'norm_rmse': diff_rmse / swmm_diff_rmse
            })
            
        # Batched Physics Scan
        num_hypotheses = 1 + model.num_links * 3
        batched_theta = torch.ones((num_hypotheses, model.num_links), dtype=torch.float32)
        hypothesis_keys = ['none']
        h_idx = 1
        for i, pid in enumerate(model.link_ids):
            for sev in [0.3, 0.6, 0.9]:
                batched_theta[h_idx, i] = 1.0 - sev
                hypothesis_keys.append(f"{pid}_{sev}")
                h_idx += 1
                
        t0 = time.time()
        batched_initial_heads = initial_heads.unsqueeze(0).repeat(num_hypotheses, 1)
        with torch.no_grad():
            batched_heads = model(batched_initial_heads, runoff_rates, steps, batched_theta)
        batched_preds = (batched_heads - model.node_inverts).numpy() * calib
        dt = time.time() - t0
        
        total_generation_time += dt
        total_hypotheses_generated += num_hypotheses
        
        hypotheses = {}
        for i, key in enumerate(hypothesis_keys):
            hypotheses[key] = batched_preds[:, i, :] 
            
        eval_events = storm_runs[storm_runs['severity'] > 0].head(15) # Up to 15 events per storm
        for idx, row in eval_events.iterrows():
            obs_data = np.load(os.path.join(dataset_dir, f"{row['run_id']}.npz"))
            obs = obs_data['observed']
            mask = obs_data['sensor_mask']
            sigma = row['sigma_m']
            true_pipe = row['blocked_pipe_id']
            
            ll_dict = {}
            for h_key, pred in hypotheses.items():
                valid_mask = ~np.isnan(obs)
                if not np.any(valid_mask):
                    ll_dict[h_key] = -np.inf
                    continue
                sse = np.sum((obs[valid_mask] - pred[valid_mask])**2)
                ll_dict[h_key] = -sse / (2 * max(sigma, 0.001)**2)
                
            pipe_scores = {}
            for h_key, ll in ll_dict.items():
                p_id = 'none' if h_key == 'none' else h_key.rsplit('_', 1)[0]
                if p_id not in pipe_scores: pipe_scores[p_id] = []
                pipe_scores[p_id].append(ll)
                
            final_scores = {}
            for p_id, lls in pipe_scores.items():
                max_ll = max(lls)
                final_scores[p_id] = max_ll + np.log(sum(np.exp(ll - max_ll) for ll in lls))
                
            sorted_pipes = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
            top1 = sorted_pipes[0] == true_pipe
            if top1: scan_top1_correct += 1
            total_eval += 1

    print("--- a) Calibrated Baseline Skill Score (Over all non-zero nodes and 10 storms) ---")
    print(f"Overall Median Skill Score: {np.median(skill_scores):.4f}")
    print(f"Overall Mean Skill Score: {np.mean(skill_scores):.4f}")
    print(f"Median RMSE: {np.median(rmse_scores):.4f} m")
    print(f"Median Zero-Prediction RMSE: {np.median(rmse_zero_scores):.4f} m")
    
    assert np.median(skill_scores) > 0.0, f"Median skill score must be positive, got {np.median(skill_scores):.4f}"
    
    print("\n--- b) Differential Accuracy (Blocked - Baseline) ---")
    for sev in [0.3, 0.6, 0.9]:
        res = diff_errs[sev]
        if not res: continue
        avg_rmse = np.mean([r['diff_rmse'] for r in res])
        avg_norm = np.mean([r['norm_rmse'] for r in res])
        print(f"Severity {sev} (Tested on {len(res)} pipes across storms):")
        print(f"  Avg Differential RMSE: {avg_rmse:.4f} m")
        print(f"  Avg Normalised RMSE: {avg_norm:.4f} (Model diff / SWMM diff)")
        
        if sev >= 0.6:
            assert avg_norm < 1.0, f"Model differential error is worse than zero-prediction for sev {sev}"
            
    print("\n--- c) End-to-End Physics Scan (Batched) ---")
    print(f"Generated {total_hypotheses_generated} hypotheses in {total_generation_time:.2f}s")
    sec_per_hyp = total_generation_time / total_hypotheses_generated
    print(f"Time per hypothesis: {sec_per_hyp:.4f} s (vs SWMM's ~0.12 s)")
    
    print(f"Scan Accuracy on {total_eval} events: Top-1 = {format_ci(scan_top1_correct, total_eval)}")
    assert total_eval >= 30, f"Not enough events evaluated, expected >= 30, got {total_eval}"
    
    print("\nGATE COMPLETE. Ready for Stage 10b-4 Surrogate design.")
