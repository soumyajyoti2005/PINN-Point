from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.post("/detect")
async def post_detect():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.get("/detections")
async def get_detections():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.get("/detections/{id}")
async def get_detection(id: int):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")

@router.patch("/detections/{id}")
async def patch_detection(id: int):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")
