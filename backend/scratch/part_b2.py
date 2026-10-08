import os
import numpy as np
import pandas as pd
from app.ml.features import build_dataset, get_network_lists, extract_features_from_npz
from app.ml.baseline_model import train_model
from app.ml.evaluate import evaluate
import pyarrow.parquet as pq
import random

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    print("\n=== B2. Mismatched-expected control ===")
    
    X_dict_res, y_dict_res, meta_dict_res, classes, nodes = build_dataset(dataset_dir, data_dir, use_residuals=True)
    model_res = train_model(X_dict_res['train'], y_dict_res['train'], X_dict_res['val'], y_dict_res['val'], len(classes))
    
    # We will build X_test_mismatched
    manifest_path = os.path.join(dataset_dir, 'manifest.parquet')
    manifest = pq.read_table(manifest_path).to_pandas()
    
    base_runs = manifest[(manifest['blocked_pipe_id'] == "none") | (manifest['blocked_pipe_id'].isna()) | (manifest['blocked_pipe_id'] == "")]
    all_base_run_ids = base_runs['run_id'].tolist()
    
    class_to_idx = {c: i for i, c in enumerate(classes)}
    X_test_mismatched = []
    y_test = []
    meta_test = []
    
    for idx, row in manifest[manifest['split'] == 'test'].iterrows():
        run_id = row['run_id']
        storm_id = row['storm_id']
        
        npz_path = os.path.join(dataset_dir, f"{run_id}.npz")
        if not os.path.exists(npz_path):
            continue
            
        # Pick a MISMATCHED base run
        other_base_runs = [r for r in all_base_run_ids if not r.startswith(storm_id)]
        mismatched_base_run_id = random.choice(other_base_runs)
        base_npz_path = os.path.join(dataset_dir, f"{mismatched_base_run_id}.npz")
            
        features = extract_features_from_npz(npz_path, nodes, use_residuals=True, base_npz_path=base_npz_path)
        
        blocked_pipe = row['blocked_pipe_id']
        label = blocked_pipe if pd.notna(blocked_pipe) and blocked_pipe != "" else "none"
        
        X_test_mismatched.append(features)
        y_test.append(class_to_idx[label])
        meta_test.append(row)
        
    X_test_mismatched = np.array(X_test_mismatched)
    y_test = np.array(y_test)
    meta_test = pd.DataFrame(meta_test)
    
    print("Evaluating Model on Test with MISMATCHED Baselines:")
    evaluate(model_res, X_test_mismatched, y_test, meta_test, classes, 'test')
    
if __name__ == "__main__":
    main()
