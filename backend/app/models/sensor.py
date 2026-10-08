from sqlalchemy import Integer, String, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .base import Base

class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, ForeignKey("nodes.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)

    __table_args__ = (
        CheckConstraint(type.in_(["ultrasonic", "pressure"]), name="ck_sensor_type"),
    )
