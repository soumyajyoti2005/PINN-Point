from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.post("/simulation/run")
async def run_simulation():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.post("/simulation/replay")
async def replay_simulation():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.post("/simulation/replay/stop")
async def stop_replay_simulation():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")
