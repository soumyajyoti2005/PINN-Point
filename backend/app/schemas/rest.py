from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, List, Optional
from .events import ID_PATTERN, DetectionCandidate

class ReadingIn(BaseModel):
    node_id: str = Field(pattern=ID_PATTERN)
    ts: datetime
    level_m: float = Field(ge=0)

class RainfallIn(BaseModel):
    zone_id: str = Field(pattern=ID_PATTERN)
    ts: datetime
    intensity_mm_hr: float = Field(ge=0)

class DetectRequest(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime

class DetectionNodeResidual(BaseModel):
    node_id: str = Field(pattern=ID_PATTERN)
    expected_m: float
    actual_m: float
    residual_m: float

class DetectionResponse(BaseModel):
    detection_id: int
    ts: datetime
    top_pipe_id: str = Field(pattern=ID_PATTERN)
    confidence: float = Field(ge=0, le=1)
    candidates: List[DetectionCandidate]
    status: str
    notes: Optional[str] = None
    residuals: List[DetectionNodeResidual]

class DetectionPatch(BaseModel):
    status: Literal["confirmed", "false_alarm", "resolved"]
    notes: Optional[str] = None
