import os
import json
import pytest
from pathlib import Path
from pydantic import ValidationError
from app.schemas.mqtt import LevelPayload, RainPayload
from app.schemas.events import LevelUpdateEvent, RainUpdateEvent, DetectionEvent

CONTRACTS_DIR = os.environ.get("CONTRACTS_DIR")

if not CONTRACTS_DIR or not (Path(CONTRACTS_DIR) / "examples").exists():
    pytest.skip(f"Contracts examples directory not found at {CONTRACTS_DIR}", allow_module_level=True)

contracts_path = Path(CONTRACTS_DIR)
examples_path = contracts_path / "examples"

FILE_MODEL_MAP = {
    "mqtt_level_valid.json": LevelPayload,
    "mqtt_level_invalid.json": LevelPayload,
    "mqtt_rain_valid.json": RainPayload,
    "mqtt_rain_invalid.json": RainPayload,
    "event_level_update_valid.json": LevelUpdateEvent,
    "event_level_update_invalid.json": LevelUpdateEvent,
    "event_rain_update_valid.json": RainUpdateEvent,
    "event_rain_update_invalid.json": RainUpdateEvent,
    "event_detection_valid.json": DetectionEvent,
    "event_detection_invalid.json": DetectionEvent,
}

def test_all_examples_mapped():
    for file_path in examples_path.glob("*.json"):
        assert file_path.name in FILE_MODEL_MAP, f"File {file_path.name} is not mapped to a model in FILE_MODEL_MAP"

@pytest.mark.parametrize("filename,model_class", FILE_MODEL_MAP.items())
def test_contract_examples(filename, model_class):
    file_path = examples_path / filename
    if not file_path.exists():
        pytest.fail(f"Example file missing: {filename}")
        
    with open(file_path, "r") as f:
        raw_text = f.read()
        
    if "invalid" in filename:
        with pytest.raises(ValidationError):
            model_class.model_validate_json(raw_text)
    else:
        model_class.model_validate_json(raw_text)

def test_strict_level_m_string():
    raw_json = '{"v": 1, "ts": "2023-10-27T10:00:00Z", "level_m": "0.42"}'
    with pytest.raises(ValidationError):
        LevelPayload.model_validate_json(raw_json)

def test_strict_datetime_date_only():
    raw_json = '{"v": 1, "ts": "2023-10-27", "level_m": 0.42}'
    with pytest.raises(ValidationError):
        LevelPayload.model_validate_json(raw_json)
