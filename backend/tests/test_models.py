from app.models.base import Base
# ensure all models are imported so they register with Base.metadata
from app.models import *

def test_metadata_tables():
    tables = Base.metadata.tables
    
    assert "nodes" in tables
    assert "pipes" in tables
    assert "sensors" in tables
    assert "detections" in tables
    assert "sim_runs" in tables
    
    assert len(tables) == 5

def test_fk_and_constraints():
    tables = Base.metadata.tables
    pipes = tables["pipes"]
    
    from_node_fks = list(pipes.c.from_node.foreign_keys)
    assert len(from_node_fks) == 1
    assert from_node_fks[0].target_fullname == "nodes.id"
    
    to_node_fks = list(pipes.c.to_node.foreign_keys)
    assert len(to_node_fks) == 1
    assert to_node_fks[0].target_fullname == "nodes.id"
    
    detections = tables["detections"]
    top_pipe_fks = list(detections.c.top_pipe_id.foreign_keys)
    assert len(top_pipe_fks) == 1
    assert top_pipe_fks[0].target_fullname == "pipes.id"
    
    sensor_checks = [c for c in tables["sensors"].constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any(c.name == "ck_sensor_type" for c in sensor_checks)
    
    detection_checks = [c for c in tables["detections"].constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any(c.name == "ck_detection_confidence" for c in detection_checks)
    assert any(c.name == "ck_detection_status" for c in detection_checks)
