from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from .base import Base

class Pipe(Base):
    __tablename__ = "pipes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    from_node: Mapped[str] = mapped_column(String, ForeignKey("nodes.id"), nullable=False)
    to_node: Mapped[str] = mapped_column(String, ForeignKey("nodes.id"), nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False)
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    diameter_m: Mapped[float] = mapped_column(Float, nullable=False)
    slope: Mapped[float] = mapped_column(Float, nullable=False)
    manning_n: Mapped[float] = mapped_column(Float, nullable=False)
