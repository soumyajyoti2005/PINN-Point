import os
import json
import numpy as np
import pandas as pd
from app.ml.features import build_dataset
from app.ml.baseline_model import train_model
from app.ml.evaluate import evaluate
from collections import Counter

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    print("=== PART A: Diagnostics ===")
    X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir, use_residuals=False)
    
    # A1. none-class bug
    print("Label counts per class in train:")
    counts = Counter(y_dict['train'])
    print({classes[k]: v for k, v in counts.items()})
    
    none_idx = classes.index('none')
    print(f"Index of 'none' at training (in classes list): {none_idx}")
    
    model_raw = train_model(X_dict['train'], y_dict['train'], X_dict['val'], y_dict['val'], len(classes))
    print(f"Index of 'none' in model.classes_: {list(model_raw.classes_).index(none_idx)}")
    
    test_baseline_mask = (meta_dict['test']['severity'] == 0.0).values
    X_base = X_dict['test'][test_baseline_mask]
    y_base = np.array(y_dict['test'])[test_baseline_mask]
    
    preds = model_raw.predict(X_base)
    probas = model_raw.predict_proba(X_base)
    
    # Map predictions back to original classes space
    mapped_preds = [classes[p] for p in preds]
    
    print("\nPredicted-class histogram on the 100 test baseline runs:")
    pred_counts = Counter(mapped_preds)
    print(dict(pred_counts))
    
    # Mean predicted probability of 'none'
    none_model_idx = list(model_raw.classes_).index(none_idx)
    mean_none_prob = np.mean(probas[:, none_model_idx])
    print(f"Mean predicted probability of 'none' on baseline runs: {mean_none_prob:.4f}")
    
    # A2. test_unseen_pipe labels
    print("\nProve no test_unseen_pipe pipe_id appears in train/val:")
    unseen_labels = set(y_dict['test_unseen_pipe'])
    train_labels = set(y_dict['train'])
    val_labels = set(y_dict['val'])
    
    print(f"Overlap train & unseen: {train_labels.intersection(unseen_labels)}")
    print(f"Overlap val & unseen: {val_labels.intersection(unseen_labels)}")
    
    # PART B: Leakage and honesty checks on residual model
    print("\n=== PART B: Leakage and Honesty Checks ===")
    X_dict_res, y_dict_res, meta_dict_res, classes_res, nodes_res = build_dataset(dataset_dir, data_dir, use_residuals=True)
    model_res = train_model(X_dict_res['train'], y_dict_res['train'], X_dict_res['val'], y_dict_res['val'], len(classes_res))
    
    # B1. Shuffled-label control
    print("\nB1. Shuffled-label control:")
    y_train_shuffled = np.random.permutation(y_dict_res['train'])
    model_shuf = train_model(X_dict_res['train'], y_train_shuffled, X_dict_res['val'], y_dict_res['val'], len(classes_res))
    print("Evaluating Shuffled Model on Test:")
    evaluate(model_shuf, X_dict_res['test'], y_dict_res['test'], meta_dict_res['test'], classes_res, 'test')
    
    # B2. Mismatched-expected control
    # We modify X_dict_res['test'] by recalculating residuals with mismatched baselines.
    # We can't easily do it without re-extracting, but let's shift the expected levels in extraction!
    # Wait, X_dict_res contains the pre-computed features. To mis-match, we should re-extract features for 'test'
    # using a shifted mapping.
    
    # B3. Top 15 features by gain
    print("\nB3. Top 15 features by gain (Residual Model):")
    # For LightGBM, we can get feature importances. Since we used a pipeline with LGBMClassifier,
    importances = model_res.booster_.feature_importance(importance_type='gain')
    
    # We need feature names. In `features.py`, we have 5 node features * num_nodes + 2 rain metrics.
    feature_names = []
    for n in nodes_res:
        for f in ['peak', 'time_of_peak', 'max_rise_rate', 'area_under_curve', 'final_level']:
            feature_names.append(f"{n}_{f}")
    feature_names.extend(["peak_rain_intensity", "total_rain"])
    
    feat_imps = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    for name, imp in feat_imps[:15]:
        print(f"{name}: {imp:.4f}")
        
if __name__ == "__main__":
    main()
