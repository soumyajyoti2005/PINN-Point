from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from .base import Base

class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    ground_elevation_m: Mapped[float] = mapped_column(Float, nullable=False)
    invert_elevation_m: Mapped[float] = mapped_column(Float, nullable=False)
    depth_m: Mapped[float] = mapped_column(Float, nullable=False)
    has_sensor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
