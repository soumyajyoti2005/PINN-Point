from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal, Optional

class LevelPayload(BaseModel):
    v: Literal[1]
    ts: datetime
    level_m: float = Field(ge=0)
    battery: Optional[float] = Field(default=None, ge=0)
    model_config = ConfigDict(extra="forbid", strict=True)

class RainPayload(BaseModel):
    v: Literal[1]
    ts: datetime
    intensity_mm_hr: float = Field(ge=0)
    model_config = ConfigDict(extra="forbid", strict=True)
