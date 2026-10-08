import os
import numpy as np
import pandas as pd
from app.ml.features import build_dataset, get_network_lists
from app.ml.baseline_model import train_model
from app.ml.evaluate import evaluate
import joblib

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    print("\n=== PART C: Early Detection ===")
    
    # C1. Rain peak and rain ends
    import pyarrow.parquet as pq
    manifest_path = os.path.join(dataset_dir, 'manifest.parquet')
    manifest = pq.read_table(manifest_path).to_pandas()
    
    rain_peaks = []
    rain_ends = []
    # We only need to check one run per storm to get the rain shape.
    for storm_id in manifest['storm_id'].unique():
        # find a run
        run_id = manifest[manifest['storm_id'] == storm_id]['run_id'].iloc[0]
        npz_path = os.path.join(dataset_dir, f"{run_id}.npz")
        data = np.load(npz_path)
        rain = data['rain']
        t_min = data['t_min']
        
        peak_idx = np.argmax(rain)
        rain_peaks.append(t_min[peak_idx])
        
        # rain ends when it goes to 0 and stays 0
        non_zero = np.where(rain > 0)[0]
        if len(non_zero) > 0:
            rain_ends.append(t_min[non_zero[-1]])
            
    print(f"Rain Peak (min/median/max): {np.min(rain_peaks):.1f} / {np.median(rain_peaks):.1f} / {np.max(rain_peaks):.1f}")
    print(f"Rain Ends (min/median/max): {np.min(rain_ends):.1f} / {np.median(rain_ends):.1f} / {np.max(rain_ends):.1f}")
    
    # C3. Train ONE residual model on rows from all cutoffs
    cutoffs = [15, 30, 45, 60, 90, 120]
    
    X_train_all, y_train_all = [], []
    X_val_all, y_val_all = [], []
    
    X_test_dict = {c: [] for c in cutoffs}
    y_test_dict = {c: [] for c in cutoffs}
    meta_test_dict = {c: [] for c in cutoffs}
    
    for c in cutoffs:
        print(f"Building dataset for cutoff {c}...")
        X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir, use_residuals=True, cutoff_min=c)
        
        # Add cutoff as extra feature
        for split in ['train', 'val']:
            for i in range(len(X_dict[split])):
                f = np.append(X_dict[split][i], c)
                if split == 'train':
                    X_train_all.append(f)
                    y_train_all.append(y_dict[split][i])
                else:
                    X_val_all.append(f)
                    y_val_all.append(y_dict[split][i])
                    
        for i in range(len(X_dict['test'])):
            f = np.append(X_dict['test'][i], c)
            X_test_dict[c].append(f)
            y_test_dict[c].append(y_dict['test'][i])
            
        meta_test_dict[c] = meta_dict['test']
        
    X_train_all = np.array(X_train_all)
    y_train_all = np.array(y_train_all)
    X_val_all = np.array(X_val_all)
    y_val_all = np.array(y_val_all)
    
    print("Training unified early-detection model...")
    model_early = train_model(X_train_all, y_train_all, X_val_all, y_val_all, len(classes))
    
    model_path = os.path.join(data_dir, "models", "early_model.joblib")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model_early, model_path)
    
    # Evaluate per cutoff
    pipe_indices = [i for i, c in enumerate(model_early.classes_) if classes[c] != "none"]
    import networkx as nx
    import json
    with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
        network = json.load(f)
    G = nx.DiGraph()
    for p in network.get("pipes", []):
        G.add_edge(p["from_node"], p["to_node"], id=p["id"])
        
    for c in cutoffs:
        print(f"\n--- Cutoff {c} mins ---")
        X_test = np.array(X_test_dict[c])
        y_test = np.array(y_test_dict[c])
        meta_test = meta_test_dict[c]
        
        probas = model_early.predict_proba(X_test)
        
        # all blockage runs
        test_blockage_mask = (meta_test['severity'] > 0).values
        test_baseline_mask = (meta_test['severity'] == 0.0).values
        
        # metrics
        def eval_subset(mask, name):
            idx_list = np.where(mask)[0]
            if len(idx_list) == 0:
                print(f"[{name}] N=0")
                return
            top1, top3, top5 = 0, 0, 0
            for idx in idx_list:
                p_probs = probas[idx]
                true_label = y_test[idx]
                true_model_idx = list(model_early.classes_).index(true_label)
                
                sorted_idx = np.argsort(p_probs)[::-1]
                if true_model_idx == sorted_idx[0]: top1 += 1
                if true_model_idx in sorted_idx[:3]: top3 += 1
                if true_model_idx in sorted_idx[:5]: top5 += 1
                
            n = len(idx_list)
            print(f"[{name}] N={n} | Top-1: {top1/n*100:.1f}% | Top-3: {top3/n*100:.1f}% | Top-5: {top5/n*100:.1f}%")
            
        eval_subset(test_blockage_mask, "All Blockages")
        
        det_act_mask = []
        for i in range(len(meta_test)):
            row = meta_test.iloc[i]
            if row['severity'] > 0 and row['detectable']:
                active_sens = False
                for u, v, d in G.edges(data=True):
                    if d['id'] == row['blocked_pipe_id']:
                        if u in row['sensor_node_ids']:
                            active_sens = True
                det_act_mask.append(active_sens)
            else:
                det_act_mask.append(False)
                
        eval_subset(det_act_mask, "Detectable + Active Upstream")
        
        # baseline FA
        base_alarms_3 = 0
        base_alarms_5 = 0
        for idx in np.where(test_baseline_mask)[0]:
            p_probs = probas[idx][pipe_indices]
            if np.max(p_probs) >= 0.3: base_alarms_3 += 1
            if np.max(p_probs) >= 0.5: base_alarms_5 += 1
            
        n_base = sum(test_baseline_mask)
        print(f"[Baseline FA] N={n_base} | >=0.3: {base_alarms_3/n_base*100:.1f}% | >=0.5: {base_alarms_5/n_base*100:.1f}%")

if __name__ == "__main__":
    main()
