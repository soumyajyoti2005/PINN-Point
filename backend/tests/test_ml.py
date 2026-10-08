import pytest
import numpy as np
import pandas as pd
from app.ml.features import extract_features_from_npz, build_dataset
from app.ml.infer import extract_features_from_raw, predict
from jsonschema import validate

def test_feature_order_and_masking():
    # Fake NPZ structure
    ordered_nodes = ["N1", "N2", "N3"]
    npz_node_ids = np.array(["N3", "N1", "N2"]) # Shuffled!
    
    # 3 time steps
    t_min = np.array([0.0, 1.0, 2.0])
    rain = np.array([1.0, 2.0, 0.0])
    
    # Obs shape (time, nodes)
    # N3 is idx 0, N1 is idx 1, N2 is idx 2
    # Make N2 all NaNs (masked)
    obs = np.array([
        [1.0, 1.0, np.nan],
        [2.0, 3.0, np.nan],
        [1.5, 2.0, np.nan]
    ])
    
    mask = np.array([True, True, False]) # N2 is false (masked)
    
    features = extract_features_from_raw(obs, rain, t_min, mask, npz_node_ids, ordered_nodes, use_residuals=False)
    
    # Features: [total_rain, peak_rain] + [peak, t_peak, rise, auc, final]*3
    assert len(features) == 2 + 5 * 3
    assert features[0] == 3.0 # total rain
    assert features[1] == 2.0 # peak rain
    
    # N1 is index 1 in obs
    # N1 series: 1.0, 3.0, 2.0
    assert features[2] == 3.0 # N1 peak
    assert features[3] == 1.0 # N1 t_peak
    assert features[4] == 2.0 # N1 max rise (3-1)/1
    assert features[5] == 4.5 # N1 auc
    assert features[6] == 2.0 # N1 final
    
    # N2 is index 2 in obs (masked/NaNs)
    assert np.isnan(features[7]) # N2 peak
    
    # N3 is index 0 in obs
    # N3 series: 1.0, 2.0, 1.5
    assert features[12] == 2.0 # N3 peak

def test_predict_schema(monkeypatch):
    class MockModel:
        def __init__(self):
            self.classes_ = [0, 1]
        def predict_proba(self, X):
            # return fake probas for 2 classes
            return np.array([[0.8, 0.2]])
            
    ordered_nodes = ["N1"]
    npz_node_ids = np.array(["N1"])
    t_min = np.array([0.0])
    rain = np.array([0.0])
    obs = np.array([[1.0]])
    mask = np.array([True])
    classes = ["P1", "none"]
    
    res = predict(obs, rain, t_min, mask, npz_node_ids, MockModel(), classes, ordered_nodes)
    
    # Validate
    import json
    from jsonschema import FormatChecker
    import os
    
    contracts_dir = os.environ.get("CONTRACTS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "contracts"))
    schema_path = os.path.join(contracts_dir, "events", "detection.schema.json")
    with open(schema_path) as f:
        schema = json.load(f)
        
    validate(instance=res, schema=schema, format_checker=FormatChecker())
    assert res["detection"]["top_pipe_id"] == "P1"
    assert res["detection"]["candidates"][0]["pipe_id"] == "P1"
    assert res["detection"]["candidates"][0]["score"] == 0.8

def test_evaluate_fake():
    # Evaluate runs on a tiny fake dataset
    from app.ml.evaluate import evaluate
    class MockModel:
        def __init__(self):
            self.classes_ = [0, 1]
        def predict_proba(self, X):
            return np.array([[0.1, 0.9], [0.8, 0.2]])
            
    X = np.array([[1], [2]])
    y = np.array([1, 0])
    meta = pd.DataFrame({
        'blocked_pipe_id': ['P1', 'none'],
        'detectable': [True, False],
        'severity': [0.5, 0.0],
        'sensor_fraction': [0.5, 1.0]
    })
    classes = ["none", "P1"]
    
    # Should not crash
    evaluate(MockModel(), X, y, meta, classes, 'test')
