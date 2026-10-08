from sqlalchemy import Integer, String, Float, ForeignKey, DateTime, CheckConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .base import Base

class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    storm_id: Mapped[str | None] = mapped_column(String, nullable=True)
    top_pipe_id: Mapped[str] = mapped_column(String, ForeignKey("pipes.id"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    candidates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, default="new", nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_detection_confidence"),
        CheckConstraint(status.in_(["new", "confirmed", "false_alarm", "resolved"]), name="ck_detection_status"),
    )
