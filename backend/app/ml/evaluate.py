import numpy as np
import pandas as pd
import os
import json

def print_metrics(y, preds_proba, classes, model, name, meta=None):
    if len(y) == 0:
        return
        
    print(f"--- {name} (N={len(y)}) ---")
    
    # Calculate top-1, top-3, top-5 accuracy
    top1 = 0
    top3 = 0
    top5 = 0
    false_alarms = 0
    baseline_runs = 0
    
    for i in range(len(y)):
        true_cls = y.iloc[i] if isinstance(y, pd.Series) else y[i]
        probas = preds_proba[i]
        top_k_idx = np.argsort(probas)[::-1]
        
        # map predicted indices back to the original classes indices
        top_k_classes = [model.classes_[idx] for idx in top_k_idx]
        
        if true_cls == top_k_classes[0]: top1 += 1
        if true_cls in top_k_classes[:3]: top3 += 1
        if true_cls in top_k_classes[:5]: top5 += 1
        
        true_label = classes[true_cls]
        if true_label == "none":
            baseline_runs += 1
            if classes[top_k_classes[0]] != "none":
                false_alarms += 1
                
    def format_pct(count, total):
        if total == 0: return "0.00% ± 0.00%"
        p = count / total
        ci = 1.96 * np.sqrt((p * (1 - p)) / total)
        return f"{p*100:.2f}% ± {ci*100:.2f}% ({count}/{total})"

    print(f"Top-1 Accuracy: {format_pct(top1, len(y))}")
    print(f"Top-3 Accuracy: {format_pct(top3, len(y))}")
    print(f"Top-5 Accuracy: {format_pct(top5, len(y))}")
    
    if baseline_runs > 0:
        print(f"False Alarm Rate: {format_pct(false_alarms, baseline_runs)}")
    print()

def evaluate(model, X, y, meta, classes, split_name):
    if len(X) == 0:
        print(f"--- {split_name} ---")
        print("No data.\n")
        return
        
    preds_proba = model.predict_proba(X)
    
    if split_name == 'test':
        # 1. all blockage runs
        blockage_mask = meta['blocked_pipe_id'].notna() & (meta['blocked_pipe_id'] != "")
        print_metrics(y[blockage_mask], preds_proba[blockage_mask], classes, model, "Test: All Blockage Runs", meta[blockage_mask])
        
        # 2. detectable subset
        detectable_mask = blockage_mask & meta['detectable']
        print_metrics(y[detectable_mask], preds_proba[detectable_mask], classes, model, "Test: Detectable Subset", meta[detectable_mask])
        
        # 3. detectable split by upstream node sensor
        data_dir = os.environ.get("DATA_DIR", "/data")
        with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
            network = json.load(f)
            
        pipe_dict = {p['id']: p for p in network.get("pipes", [])}
        node_dict = {n['id']: n for n in network.get("nodes", [])}
        
        def has_active_upstream_sensor(row):
            pipe_id = row['blocked_pipe_id']
            if pd.isna(pipe_id) or pipe_id == "": return False
            p = pipe_dict.get(pipe_id)
            if not p: return False
            up_node = p.get('from_node')
            
            # Check if up_node is in the active sensors for this run
            active_sensors = row.get('sensor_node_ids', [])
            if isinstance(active_sensors, np.ndarray):
                active_sensors = active_sensors.tolist()
            return up_node in active_sensors
            
        upstream_sensor = meta.apply(has_active_upstream_sensor, axis=1)
        
        mask_up_sensor = detectable_mask & upstream_sensor
        mask_no_up_sensor = detectable_mask & (~upstream_sensor)
        
        print_metrics(y[mask_up_sensor], preds_proba[mask_up_sensor], classes, model, "Test: Detectable (Upstream Sensor = True)")
        print_metrics(y[mask_no_up_sensor], preds_proba[mask_no_up_sensor], classes, model, "Test: Detectable (Upstream Sensor = False)")
        
        # Baseline runs
        print_metrics(y[~blockage_mask], preds_proba[~blockage_mask], classes, model, "Test: Baseline Runs")
        
        # Breakdown by severity and sensor_fraction
        for sev in sorted(meta['severity'].unique()):
            if sev == 0.0: continue
            sev_mask = blockage_mask & (meta['severity'] == sev)
            print_metrics(y[sev_mask], preds_proba[sev_mask], classes, model, f"Test: Severity {sev}")
            
        for sf in sorted(meta['sensor_fraction'].unique()):
            sf_mask = blockage_mask & (meta['sensor_fraction'] == sf)
            print_metrics(y[sf_mask], preds_proba[sf_mask], classes, model, f"Test: Sensor Fraction {sf}")

    elif split_name == 'test_unseen_pipe':
        print_metrics(y, preds_proba, classes, model, "Test: Unseen Pipe (Reference PINN must beat)", meta)

if __name__ == "__main__":
    from app.ml.features import build_dataset
    from app.ml.baseline_model import load_model
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", os.environ.get("DATASET_NAME", "sample"))
    model_path = os.path.join(data_dir, "models", "baseline.joblib")
    
    X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir)
    model, loaded_classes, loaded_nodes = load_model(model_path)
    
    assert classes == loaded_classes, "Classes mismatch between dataset and model"
    
    for split in ['test', 'test_unseen_pipe']:
        evaluate(model, X_dict[split], y_dict[split], meta_dict[split], classes, split)
