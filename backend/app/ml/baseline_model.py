import lightgbm as lgb
import os
import joblib

def train_model(X_train, y_train, X_val, y_val, num_classes):
    model = lgb.LGBMClassifier(
        n_estimators=1000,
        learning_rate=0.05,
        random_state=42,
        objective='multiclass',
        num_class=num_classes
    )
    # LightGBM handles NaNs naturally
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric='multi_logloss',
        callbacks=[lgb.early_stopping(stopping_rounds=50)]
    )
    return model

def save_model(model, classes, nodes, path_prefix):
    os.makedirs(os.path.dirname(path_prefix), exist_ok=True)
    joblib.dump({
        'model': model,
        'classes': classes,
        'nodes': nodes
    }, path_prefix + "baseline.joblib")
    
def load_model(path):
    data = joblib.load(path)
    return data['model'], data['classes'], data['nodes']

if __name__ == "__main__":
    from app.ml.features import build_dataset
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", os.environ.get("DATASET_NAME", "sample"))
    
    print("Loading data...")
    X_dict, y_dict, meta_dict, classes, nodes = build_dataset(dataset_dir, data_dir)
    
    print(f"Training on {len(X_dict['train'])} runs, validating on {len(X_dict['val'])} runs...")
    print(f"Classes: {len(classes)}")
    
    model = train_model(X_dict["train"], y_dict["train"], X_dict["val"], y_dict["val"], len(classes))
    
    model_prefix = os.path.join(data_dir, "models/")
    save_model(model, classes, nodes, model_prefix)
    print(f"Model and metadata saved to {model_prefix}baseline.joblib")
