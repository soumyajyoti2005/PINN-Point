import os
import json
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.config import settings

router = APIRouter()

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

@router.get("/scenarios")
async def get_scenarios():
    data_dir = os.environ.get("DATA_DIR", "/data")
    index_path = os.path.join(data_dir, "replay", "index.json")
    if not os.path.exists(index_path):
        return []
    with open(index_path, "r") as f:
        return json.load(f)

@router.get("/replay/{scenario_id}")
async def get_replay(scenario_id: str):
    if not ID_PATTERN.match(scenario_id):
        raise HTTPException(status_code=400, detail="Invalid scenario_id format")
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    replay_path = os.path.join(data_dir, "replay", f"{scenario_id}.json")
    if not os.path.exists(replay_path):
        raise HTTPException(status_code=404, detail="Scenario not found")
        
    with open(replay_path, "r") as f:
        return json.load(f)

