import math
import os
from dataclasses import dataclass

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@dataclass
class Area:
    name: str
    center_lat: float
    center_lon: float
    half_size_m: float

    @classmethod
    def from_env(cls):
        name = os.environ.get("AREA_NAME")
        if not name:
            raise ValueError("Missing AREA_NAME environment variable")
            
        lat_str = os.environ.get("AREA_CENTER_LAT")
        if not lat_str:
            raise ValueError("Missing AREA_CENTER_LAT environment variable")
            
        lon_str = os.environ.get("AREA_CENTER_LON")
        if not lon_str:
            raise ValueError("Missing AREA_CENTER_LON environment variable")
            
        size_str = os.environ.get("AREA_HALF_SIZE_M")
        if not size_str:
            raise ValueError("Missing AREA_HALF_SIZE_M environment variable")
            
        return cls(
            name=name,
            center_lat=float(lat_str),
            center_lon=float(lon_str),
            half_size_m=float(size_str)
        )

    def bbox(self):
        # 1 degree of latitude is roughly 110.574 km
        dlat = self.half_size_m / 110574.0
        # 1 degree of longitude depends on latitude (111.320 km at equator)
        dlon = self.half_size_m / (111320.0 * math.cos(math.radians(self.center_lat)))
        
        south = self.center_lat - dlat
        north = self.center_lat + dlat
        west = self.center_lon - dlon
        east = self.center_lon + dlon
        
        return (south, west, north, east)
