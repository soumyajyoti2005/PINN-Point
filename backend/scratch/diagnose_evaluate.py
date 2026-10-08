import sys
import os
import numpy as np
import pandas as pd
import joblib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ml.features import build_dataset

def run_diagnostics():
    # Load dataset
    dataset_name = "large400"
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    dataset_dir = os.path.join(data_dir, "datasets", dataset_name)
    
    print("Building dataset...")
    X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir)
    
    class_to_idx = {c: i for i, c in enumerate(classes)}
    
    # Check index of 'none' at training
    print(f"Index of 'none' in class_to_idx (training): {class_to_idx.get('none')}")
    print(f"Index of 'none' in classes list (training): {classes.index('none') if 'none' in classes else 'Missing'}")
    
    # Label counts in train
    y_train = y_dict['train']
    counts = pd.Series(y_train).value_counts().sort_index()
    print("\nLabel counts in train:")
    for idx, count in counts.items():
        if count > 0:
            print(f"  {classes[idx]}: {count}")
            
    # Load the model
    model_path = os.path.join(data_dir, "baseline_model.joblib")
    if not os.path.exists(model_path):
        print("Model not found at", model_path)
        sys.exit(1)
        
    model, saved_classes = joblib.load(model_path)
    print(f"\nIndex of 'none' in saved_classes (evaluation): {saved_classes.index('none') if 'none' in saved_classes else 'Missing'}")
    print(f"Model classes attribute: {getattr(model, 'classes_', 'Missing')}")
    
    # Test baseline runs
    meta_test = meta_dict['test']
    X_test = X_dict['test']
    
    test_baseline_mask = meta_test['blocked_pipe_id'] == 'none'
    X_test_base = X_test[test_baseline_mask]
    
    print(f"\nTest baseline runs N = {len(X_test_base)}")
    if len(X_test_base) > 0:
        probas = model.predict_proba(X_test_base)
        preds = model.predict(X_test_base)
        
        # Predicted class histogram
        pred_counts = pd.Series(preds).value_counts().sort_index()
        print("\nPredicted class histogram on test baseline runs:")
        for cls_idx, count in pred_counts.items():
            print(f"  Class {cls_idx} ({saved_classes[cls_idx]}): {count}")
            
        none_idx = saved_classes.index('none') if 'none' in saved_classes else -1
        if none_idx != -1:
            mean_prob = probas[:, none_idx].mean()
            print(f"\nMean predicted probability of 'none' on test baseline runs: {mean_prob:.4f}")

if __name__ == "__main__":
    run_diagnostics()
