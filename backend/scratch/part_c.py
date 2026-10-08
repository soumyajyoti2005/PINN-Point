import os
import numpy as np
import pandas as pd
from collections import defaultdict
from app.ml.features import build_dataset, get_network_lists
from app.ml.baseline_model import train_model
from app.ml.evaluate import evaluate
import networkx as nx
import joblib

def get_network_graph(data_dir):
    import json
    with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
        network = json.load(f)
        
    G = nx.DiGraph()
    for n in network.get("nodes", []):
        G.add_node(n["id"])
    for p in network.get("pipes", []):
        G.add_edge(p["from_node"], p["to_node"], id=p["id"])
    return G

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    # B4. Miss rate & false-alarm rate (raw and residual)
    print("\n=== PART B4, B5, B6 ===")
    X_raw, y_raw, meta_raw, classes, nodes = build_dataset(dataset_dir, data_dir, use_residuals=False)
    X_res, y_res, meta_res, _, _ = build_dataset(dataset_dir, data_dir, use_residuals=True)
    
    model_raw = train_model(X_raw['train'], y_raw['train'], X_raw['val'], y_raw['val'], len(classes))
    model_res = train_model(X_res['train'], y_res['train'], X_res['val'], y_res['val'], len(classes))
    
    none_idx = classes.index('none')
    none_model_idx = list(model_raw.classes_).index(none_idx)
    
    test_blockage_mask = (meta_raw['test']['severity'] > 0).values
    test_baseline_mask = (meta_raw['test']['severity'] == 0.0).values
    
    def format_pct(count, total):
        p = count / total if total > 0 else 0
        ci = 1.96 * np.sqrt((p * (1 - p)) / total) if total > 0 else 0
        return f"{p*100:.2f}% ± {ci*100:.2f}% ({count}/{total})"
        
    for name, model, X, y in [("Raw", model_raw, X_raw, y_raw), ("Residual", model_res, X_res, y_res)]:
        print(f"\n--- {name} Model ---")
        preds = model.predict(X['test'])
        mapped_preds = [classes[p] for p in preds]
        
        # Miss rate: blockage predicted 'none'
        X_blk = X['test'][test_blockage_mask]
        preds_blk = model.predict(X_blk)
        mapped_blk = [classes[p] for p in preds_blk]
        miss_count = sum(1 for p in mapped_blk if p == "none")
        print(f"Miss rate (blockage predicted 'none'): {format_pct(miss_count, len(X_blk))}")
        
        # False alarm rate: baseline predicted as pipe
        X_base = X['test'][test_baseline_mask]
        preds_base = model.predict(X_base)
        mapped_base = [classes[p] for p in preds_base]
        fa_count = sum(1 for p in mapped_base if p != "none")
        print(f"False-alarm rate (baseline predicted as pipe): {format_pct(fa_count, len(X_base))}")
        
    # B5. Threshold table
    print("\nB5. Threshold Table (Residual Model)")
    probas = model_res.predict_proba(X_res['test'])
    
    # We want max probability excluding 'none', but wait: "confidence thresholds ... on the top-1 pipe probability"
    # So we sort, find top-1 pipe.
    pipe_indices = [i for i, c in enumerate(model_res.classes_) if classes[c] != "none"]
    
    def eval_threshold(thresh):
        # alarm on baseline
        base_alarms = 0
        for i, idx in enumerate(np.where(test_baseline_mask)[0]):
            pipe_probs = probas[idx][pipe_indices]
            max_pipe_prob = np.max(pipe_probs)
            if max_pipe_prob >= thresh:
                base_alarms += 1
                
        # blockage flagged correctly (top-1 is true label AND prob >= thresh)
        # blockage flagged at all (any pipe prob >= thresh)
        blk_correct = 0
        blk_flagged = 0
        blk_det_correct = 0
        blk_det_flagged = 0
        det_count = 0
        
        for i, idx in enumerate(np.where(test_blockage_mask)[0]):
            row_meta = meta_res['test'].iloc[idx]
            true_label = y_res['test'][idx] # This is the index in classes
            true_model_idx = list(model_res.classes_).index(true_label)
            
            pipe_probs = probas[idx][pipe_indices]
            max_pipe_prob = np.max(pipe_probs)
            best_pipe_idx = pipe_indices[np.argmax(pipe_probs)]
            
            is_det = row_meta['detectable']
            # active upstream sensor
            G = get_network_graph(data_dir)
            active_sens = False
            for u, v, d in G.edges(data=True):
                if d['id'] == row_meta['blocked_pipe_id']:
                    if u in row_meta['sensor_node_ids']:
                        active_sens = True
                        
            is_det_active = is_det and active_sens
            if is_det_active:
                det_count += 1
                
            flagged = max_pipe_prob >= thresh
            correct = flagged and (best_pipe_idx == true_model_idx)
            
            if flagged: blk_flagged += 1
            if correct: blk_correct += 1
            
            if is_det_active:
                if flagged: blk_det_flagged += 1
                if correct: blk_det_correct += 1
                
        return base_alarms, sum(test_baseline_mask), blk_correct, blk_flagged, sum(test_blockage_mask), blk_det_correct, blk_det_flagged, det_count

    print("Threshold | Base FA | Blk Correct | Blk Flagged | Det-Act Correct | Det-Act Flagged")
    for t in [0.2, 0.3, 0.4, 0.5, 0.6]:
        ba, base_n, bc, bf, blk_n, dc, df, det_n = eval_threshold(t)
        print(f"{t:.1f}      | {format_pct(ba, base_n)} | {format_pct(bc, blk_n)} | {format_pct(bf, blk_n)} | {format_pct(dc, det_n)} | {format_pct(df, det_n)}")

    # B6. Severity 0.3 mean residual
    print("\nB6. Severity 0.3 Mean |Residual| by hop distance")
    # Actually just run the B2 script for this or print it here. I'll defer this to another script if needed.

if __name__ == "__main__":
    main()
