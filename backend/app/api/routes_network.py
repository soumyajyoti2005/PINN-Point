import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/network")
async def get_network():
    data_dir = os.environ.get("DATA_DIR", "/data")
    # Try kolkata-amherst_network.json first, as that's what dataset uses
    network_path = os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")
    if not os.path.exists(network_path):
        network_path = os.path.join(data_dir, "swmm", "network.json")
    
    if not os.path.exists(network_path):
        # Return empty if not found, or maybe raise 404
        raise HTTPException(status_code=404, detail="Network file not found")
        
    with open(network_path, "r") as f:
        return json.load(f)

