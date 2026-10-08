from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.post("/rainfall")
async def post_rainfall():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.get("/rainfall")
async def get_rainfall():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")
