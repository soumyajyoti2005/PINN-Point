from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.get("/nodes/{id}/readings")
async def get_readings(id: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.post("/readings")
async def post_readings():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")
