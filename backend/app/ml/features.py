import numpy as np
import pandas as pd
import os
import pyarrow.parquet as pq
import json

def get_network_lists(data_dir):
    with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
        network = json.load(f)
    nodes = [n["id"] for n in network.get("nodes", [])]
    pipes = [p["id"] for p in network.get("pipes", [])]
    return nodes, pipes

def extract_features_from_npz(npz_path, ordered_node_ids, use_residuals=True, base_npz_path=None, cutoff_min=None):
    data = np.load(npz_path)
    obs = data['observed']  # shape (time, nodes)
    rain = data['rain']
    t_min = data['t_min']
    npz_node_ids = data['node_ids']
    
    expected_levels = None
    if use_residuals:
        if base_npz_path is not None and os.path.exists(base_npz_path):
            base_data = np.load(base_npz_path)
            expected_levels = base_data['clean']
        else:
            expected_levels = data['clean']
            
    return compute_features(obs, rain, t_min, npz_node_ids, ordered_node_ids, use_residuals, expected_levels, cutoff_min)

def compute_features(obs, rain, t_min, npz_node_ids, ordered_node_ids, use_residuals, expected_levels=None, cutoff_min=None):
    if cutoff_min is not None:
        mask = t_min <= cutoff_min
        obs = obs[mask]
        rain = rain[mask]
        t_min = t_min[mask]
        if expected_levels is not None:
            expected_levels = expected_levels[mask]

    node_idx_map = {nid: idx for idx, nid in enumerate(npz_node_ids)}
    
    total_rain = np.sum(rain) if len(rain) > 0 else 0.0
    peak_rain = np.max(rain) if len(rain) > 0 else 0.0
    
    features = []
    
    with np.errstate(all='ignore'):
        for nid in ordered_node_ids:
            if nid not in node_idx_map:
                if use_residuals:
                    features.extend([np.nan, np.nan, np.nan, np.nan])
                else:
                    features.extend([np.nan, np.nan, np.nan, np.nan, np.nan])
                continue
                
            idx = node_idx_map[nid]
            series = obs[:, idx]
            
            if np.all(np.isnan(series)):
                if use_residuals:
                    features.extend([np.nan, np.nan, np.nan, np.nan])
                else:
                    features.extend([np.nan, np.nan, np.nan, np.nan, np.nan])
            else:
                if use_residuals and expected_levels is not None:
                    exp_series = expected_levels[:, idx]
                    min_len = min(len(series), len(exp_series))
                    s = series[:min_len]
                    e = exp_series[:min_len]
                    
                    # 1. peak residual (difference in peaks)
                    peak_res = np.nanmax(s) - np.nanmax(e)
                    
                    # 2. residual at the expected peak time
                    exp_peak_idx = np.nanargmax(e)
                    res_at_exp_peak = s[exp_peak_idx] - e[exp_peak_idx]
                    
                    # 3. area residual
                    diff = s - e
                    try:
                        area_res = np.trapezoid(np.nan_to_num(diff), t_min[:min_len])
                    except AttributeError:
                        area_res = np.trapz(np.nan_to_num(diff), t_min[:min_len])
                        
                    # 4. max residual
                    max_res = np.nanmax(diff)
                    
                    features.extend([peak_res, res_at_exp_peak, area_res, max_res])
                else:
                    peak = np.nanmax(series)
                    peak_idx = np.nanargmax(series)
                    time_of_peak = t_min[peak_idx]
                    
                    if len(series) > 1:
                        diffs = np.diff(series) / np.diff(t_min)
                        max_rise_rate = np.nanmax(diffs)
                    else:
                        max_rise_rate = 0.0
                        
                    try:
                        auc = np.trapezoid(np.nan_to_num(series), t_min)
                    except AttributeError:
                        auc = np.trapz(np.nan_to_num(series), t_min)
                        
                    final_level = series[-1]
                    
                    features.extend([peak, time_of_peak, max_rise_rate, auc, final_level])
                    
    out = [total_rain, peak_rain] + features
    return np.array(out, dtype=np.float32)

def build_dataset(dataset_dir, data_dir, use_residuals=True, cutoff_min=None):
    manifest_path = os.path.join(dataset_dir, 'manifest.parquet')
    manifest = pq.read_table(manifest_path).to_pandas()
    
    nodes, pipes = get_network_lists(data_dir)
    classes = pipes + ["none"]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    
    # Pre-compute storm baseline runs
    # For a given storm, find the run_id where blocked_pipe_id is "none" or NaN
    base_runs = manifest[(manifest['blocked_pipe_id'] == "none") | (manifest['blocked_pipe_id'].isna()) | (manifest['blocked_pipe_id'] == "")]
    storm_to_base = {}
    for _, row in base_runs.iterrows():
        storm_to_base[row['storm_id']] = row['run_id']
    
    X_dict = {'train': [], 'val': [], 'test': [], 'test_unseen_pipe': []}
    y_dict = {'train': [], 'val': [], 'test': [], 'test_unseen_pipe': []}
    meta_dict = {'train': [], 'val': [], 'test': [], 'test_unseen_pipe': []}
    
    for idx, row in manifest.iterrows():
        run_id = row['run_id']
        split = row['split']
        storm_id = row['storm_id']
        
        npz_path = os.path.join(dataset_dir, f"{run_id}.npz")
        if not os.path.exists(npz_path):
            continue
            
        base_run_id = storm_to_base.get(storm_id)
        base_npz_path = None
        if base_run_id:
            base_npz_path = os.path.join(dataset_dir, f"{base_run_id}.npz")
            
        features = extract_features_from_npz(npz_path, nodes, use_residuals=use_residuals, base_npz_path=base_npz_path, cutoff_min=cutoff_min)
        
        # Label: blocked pipe_id or "none"
        blocked_pipe = row['blocked_pipe_id']
        label = blocked_pipe if pd.notna(blocked_pipe) and blocked_pipe != "" else "none"
        cls_idx = class_to_idx[label]
        
        X_dict[split].append(features)
        y_dict[split].append(cls_idx)
        meta_dict[split].append(row)
        
    for k in X_dict:
        X_dict[k] = np.array(X_dict[k])
        y_dict[k] = np.array(y_dict[k])
        meta_dict[k] = pd.DataFrame(meta_dict[k])
        
    return X_dict, y_dict, meta_dict, classes, nodes

if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", os.environ.get("DATASET_NAME", "sample"))
    print(f"Building features from {dataset_dir}")
    X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir)
    for k in X_dict:
        print(f"{k}: X shape {X_dict[k].shape}, y shape {y_dict[k].shape}, meta {len(meta_dict[k])}")
