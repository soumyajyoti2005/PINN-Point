import os
import json
import datetime
import numpy as np
import pandas as pd
from app.ml.baseline_model import load_model

def make_replay():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_name = os.environ.get("DATASET_NAME", "large1000")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    
    replay_dir = os.path.join(data_dir, "replay")
    os.makedirs(replay_dir, exist_ok=True)
    
    with open(os.path.join(data_dir, "swmm", f"{area}_network.json")) as f:
        network = json.load(f)
    
    manifest_path = os.path.join(data_dir, "datasets", dataset_name, "manifest.parquet")
    df = pd.read_parquet(manifest_path)
    
    df_test = df[df['split'] == 'test']
    
    detectable_blocked = df_test[(df_test['detectable'] == True) & (df_test['blocked_pipe_id'] != 'none')]
    second_blocked = df_test[(df_test['blocked_pipe_id'] != 'none') & (~df_test.index.isin(detectable_blocked.index))]
    
    # Baseline could be in any split
    baseline = df[(df['blocked_pipe_id'] == 'none') | (df['blocked_pipe_id'].isna()) | (df['blocked_pipe_id'] == '')]
    
    np.random.seed(42)
    s1 = detectable_blocked.sample(1).iloc[0]
    if len(second_blocked) == 0:
        second_blocked = df_test[df_test['blocked_pipe_id'] != 'none']
    s2 = second_blocked.sample(1).iloc[0]
    s3 = baseline.sample(1).iloc[0]
    
    scenarios = [s1, s2, s3]
    
    model_path = os.path.join(data_dir, "models", "baseline.joblib")
    model, classes, nodes = load_model(model_path)
    
    index_data = []
    
    for idx, s in enumerate(scenarios):
        run_id = s['run_id']
        print(f"Processing scenario {idx+1}: {run_id}")
        
        npz_path = os.path.join(data_dir, "datasets", dataset_name, f"{run_id}.npz")
        data = np.load(npz_path)
        
        rain = data['rain'].tolist()
        obs = data['observed']
        mask = data['sensor_mask']
        npz_node_ids = data['node_ids']
        
        levels = {}
        for i, node_id in enumerate(npz_node_ids):
            if mask[i]:
                node_levels = np.clip(obs[:, i], 0, None)
                levels[node_id] = [float(l) if not np.isnan(l) else None for l in node_levels]
            else:
                levels[node_id] = [None] * len(obs)
                
        scenario_id = f"scenario_{idx+1}_{run_id}"
        true_pipe = s['blocked_pipe_id']
        if true_pipe == 'none' or pd.isna(true_pipe):
            true_pipe = None
        severity = float(s['severity']) if true_pipe is not None else 0.0
        
        detections = []
        base_runs = df[(df['storm_id'] == s['storm_id']) & ((df['blocked_pipe_id'] == 'none') | (df['blocked_pipe_id'].isna()) | (df['blocked_pipe_id'] == ''))]
        base_run_id = base_runs.iloc[0]['run_id'] if len(base_runs) > 0 else None
        base_npz_path = os.path.join(data_dir, "datasets", dataset_name, f"{base_run_id}.npz") if base_run_id else None
        
        from app.ml.features import extract_features_from_npz
        
        for minute in [15, 30, 45, 60, 90, 120]:
            if minute >= len(obs): continue
            
            features = extract_features_from_npz(npz_path, nodes, use_residuals=False, base_npz_path=base_npz_path, cutoff_min=minute)
            
            X = np.array([features])
            probas = model.predict_proba(X)[0]
            
            top_5_idx = np.argsort(probas)[::-1][:5]
            candidates = []
            for c_idx in top_5_idx:
                mapped_idx = model.classes_[c_idx]
                c_name = classes[mapped_idx]
                candidates.append({"pipe_id": c_name, "score": float(probas[c_idx])})
                
            top_class = candidates[0]["pipe_id"]
            confidence = candidates[0]["score"]
            
            det_payload = {
                "detection_id": int(datetime.datetime.now().timestamp() * 1000) + minute,
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
                "top_pipe_id": top_class,
                "confidence": confidence,
                "candidates": candidates,
                "status": "new"
            }
            detections.append({"minute": minute, "detection": det_payload})
            
        replay_payload = {
            "v": 1,
            "scenario_id": scenario_id,
            "true_pipe_id": true_pipe,
            "severity": severity,
            "step_s": 60,
            "rain": rain,
            "levels": levels,
            "detections": detections
        }
        
        out_path = os.path.join(replay_dir, f"{scenario_id}.json")
        with open(out_path, "w") as f:
            json.dump(replay_payload, f)
            
        index_data.append({
            "scenario_id": scenario_id,
            "description": f"Scenario {idx+1}: {true_pipe if true_pipe else 'baseline'}"
        })
        
    with open(os.path.join(replay_dir, "index.json"), "w") as f:
        json.dump(index_data, f)
        
    print("Replays written to", replay_dir)

if __name__ == "__main__":
    make_replay()
