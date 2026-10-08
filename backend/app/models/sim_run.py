from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class SimRun(Base):
    __tablename__ = "sim_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    blocked_pipe_id: Mapped[str | None] = mapped_column(String, ForeignKey("pipes.id"), nullable=True)
    severity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_profile: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dataset_path: Mapped[str] = mapped_column(String, nullable=False)
