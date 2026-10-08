import os
import numpy as np
import pandas as pd
from app.ml.features import build_dataset
from app.ml.baseline_model import train_model
from app.ml.evaluate import evaluate

def main():
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    print("=== RAW FEATURES ===")
    X_dict_raw, y_dict_raw, meta_dict_raw, classes_raw, nodes_raw = build_dataset(dataset_dir, data_dir, use_residuals=False)
    
    print("Training model on raw features...")
    model_raw = train_model(X_dict_raw['train'], y_dict_raw['train'], X_dict_raw['val'], y_dict_raw['val'], len(classes_raw))
    
    print("\nEvaluating Raw Features on Test Split:")
    evaluate(model_raw, X_dict_raw['test'], y_dict_raw['test'], meta_dict_raw['test'], classes_raw, 'test')
    print("\nEvaluating Raw Features on Unseen Pipe Split:")
    evaluate(model_raw, X_dict_raw['test_unseen_pipe'], y_dict_raw['test_unseen_pipe'], meta_dict_raw['test_unseen_pipe'], classes_raw, 'test_unseen_pipe')
    
    print("\n\n=== RESIDUAL FEATURES ===")
    X_dict_res, y_dict_res, meta_dict_res, classes_res, nodes_res = build_dataset(dataset_dir, data_dir, use_residuals=True)
    
    print("Training model on residual features...")
    model_res = train_model(X_dict_res['train'], y_dict_res['train'], X_dict_res['val'], y_dict_res['val'], len(classes_res))
    
    print("\nEvaluating Residual Features on Test Split:")
    evaluate(model_res, X_dict_res['test'], y_dict_res['test'], meta_dict_res['test'], classes_res, 'test')
    print("\nEvaluating Residual Features on Unseen Pipe Split:")
    evaluate(model_res, X_dict_res['test_unseen_pipe'], y_dict_res['test_unseen_pipe'], meta_dict_res['test_unseen_pipe'], classes_res, 'test_unseen_pipe')

if __name__ == "__main__":
    main()
