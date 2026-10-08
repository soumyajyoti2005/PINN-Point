from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal, List

ID_PATTERN = "^[A-Za-z0-9_-]{1,50}$"

class LevelUpdateEvent(BaseModel):
    v: Literal[1]
    type: Literal["level_update"]
    node_id: str = Field(pattern=ID_PATTERN)
    ts: datetime
    level_m: float = Field(ge=0)
    model_config = ConfigDict(extra="forbid", strict=True)

class RainUpdateEvent(BaseModel):
    v: Literal[1]
    type: Literal["rain_update"]
    zone_id: str = Field(pattern=ID_PATTERN)
    ts: datetime
    intensity_mm_hr: float = Field(ge=0)
    model_config = ConfigDict(extra="forbid", strict=True)

class DetectionCandidate(BaseModel):
    pipe_id: str = Field(pattern=ID_PATTERN)
    score: float = Field(ge=0, le=1)
    model_config = ConfigDict(extra="forbid", strict=True)

class DetectionBody(BaseModel):
    detection_id: int
    ts: datetime
    top_pipe_id: str = Field(pattern=ID_PATTERN)
    confidence: float = Field(ge=0, le=1)
    candidates: List[DetectionCandidate] = Field(min_length=1)
    status: Literal["new", "confirmed", "false_alarm", "resolved"] = "new"
    model_config = ConfigDict(extra="forbid", strict=True)

class DetectionEvent(BaseModel):
    v: Literal[1]
    type: Literal["detection"]
    detection: DetectionBody
    model_config = ConfigDict(extra="forbid", strict=True)
