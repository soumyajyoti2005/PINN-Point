import numpy as np
import os
import datetime
import json

def extract_features_from_raw(observed_levels, rain, t_min, mask, npz_node_ids, ordered_node_ids, use_residuals=True, expected_levels=None):
    from app.ml.features import compute_features
    
    # Apply mask explicitly: set unmasked columns to NaN
    obs = observed_levels.copy()
    for i, is_active in enumerate(mask):
        if not is_active:
            obs[:, i] = np.nan
            
    return compute_features(obs, rain, t_min, npz_node_ids, ordered_node_ids, use_residuals, expected_levels)

def predict(observed_levels, rain, t_min, mask, npz_node_ids, model, classes, nodes, use_residuals=True, expected_levels=None):
    features = extract_features_from_raw(observed_levels, rain, t_min, mask, npz_node_ids, nodes, use_residuals, expected_levels)
    X = np.array([features])
    probas = model.predict_proba(X)[0]
    
    top_5_idx = np.argsort(probas)[::-1][:5]
    
    candidates = []
    for idx in top_5_idx:
        mapped_idx = model.classes_[idx]
        c_name = classes[mapped_idx]
        candidates.append({"pipe_id": c_name, "score": float(probas[idx])})
        
    top_class = candidates[0]["pipe_id"]
    confidence = candidates[0]["score"]
    
    # Convention: If "none" is the top class, it means the network is behaving normally
    # according to baseline simulations. We return "none" as the top_pipe_id to signify no blockage.
    # The schema specifies top_pipe_id must match "^[A-Za-z0-9_-]{1,50}$", so "none" is perfectly valid.
    
    payload = {
        "v": 1,
        "type": "detection",
        "detection": {
            "detection_id": int(datetime.datetime.now().timestamp()),
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "top_pipe_id": top_class,
            "confidence": confidence,
            "candidates": candidates,
            "status": "new"
        }
    }
    return payload

if __name__ == "__main__":
    from app.ml.baseline_model import load_model
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python -m app.ml.infer <path_to_npz>")
        sys.exit(1)
        
    npz_path = sys.argv[1]
    data_dir = os.environ.get("DATA_DIR", "/data")
    model_path = os.path.join(data_dir, "models", "baseline.joblib")
    
    model, classes, nodes = load_model(model_path)
    
    data = np.load(npz_path)
    obs = data['observed']
    rain = data['rain']
    t_min = data['t_min']
    npz_node_ids = data['node_ids']
    # If mask is not in npz, assume all non-all-NaNs are working
    mask = np.ones(obs.shape[1], dtype=bool)
    
    res = predict(obs, rain, t_min, mask, npz_node_ids, model, classes, nodes)
    
    # Validate against schema (R3)
    from jsonschema import validate, FormatChecker
    contracts_dir = os.environ.get("CONTRACTS_DIR", "/contracts")
    schema_path = os.path.join(contracts_dir, "events", "detection.schema.json")
    with open(schema_path) as f:
        schema = json.load(f)
    
    validate(instance=res, schema=schema, format_checker=FormatChecker())
    print(json.dumps(res, indent=2))
    
    if res["detection"]["top_pipe_id"] == "none":
        print("\nConvention Note: The top class is 'none'. This indicates no blockage was detected.")
