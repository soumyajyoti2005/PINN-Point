from fastapi import APIRouter

router = APIRouter()

@router.get("/network")
async def get_network():
    return {"type": "FeatureCollection", "features": []}
