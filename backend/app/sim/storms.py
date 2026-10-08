import numpy as np

def generate_storm(rng: np.random.Generator, max_peak_cap: float = 80.0):
    """
    Generate a synthetic storm series (1-minute intervals).
    Peak: 30 to max_peak_cap mm/hr.
    Duration: 20 to 90 min.
    Peak position: 0.2 to 0.8 of duration.
    """
    peak = rng.uniform(30.0, max_peak_cap)
    duration = int(rng.integers(20, 91))
    peak_position = rng.uniform(0.2, 0.8)
    
    t_peak = int(duration * peak_position)
    series = np.zeros(duration + 1)
    
    for t in range(duration + 1):
        if t <= t_peak:
            series[t] = peak * (t / max(1, t_peak))
        else:
            series[t] = peak * (1.0 - (t - t_peak) / max(1, duration - t_peak))
            
    # Format for SWMM (list of tuples (time_min, intensity_mm_hr))
    # Note: swmm needs it as continuous points
    # Actually, the user's `make_swmm_inp.py` assumes list of `(t_min, intensity)`.
    # Let's return the series as a numpy array and format it outside or return tuples.
    # The requirement says "Return the series plus params".
    return series, {
        "peak_mm_hr": float(peak),
        "duration_min": duration,
        "peak_position": float(peak_position),
    }

def apply_sensor_effects(clean: np.ndarray, sigma_m: float, dropout_frac: float, sensor_mask: np.ndarray, rng: np.random.Generator, node_depths_m: np.ndarray) -> np.ndarray:
    """
    Apply sensor noise and mask.
    clean: shape [time, nodes]
    sigma_m: float (Gaussian noise standard deviation in meters)
    dropout_frac: float (fraction of dropouts set to NaN)
    sensor_mask: boolean array shape [nodes], True if node has a sensor
    rng: np.random.Generator
    node_depths_m: array of max depths per node, shape [nodes]
    """
    # 1. Clip true clean levels at the rim before adding noise
    observed = np.clip(clean, 0.0, node_depths_m)
    
    # Apply Gaussian noise
    noise = rng.normal(0.0, sigma_m, size=observed.shape)
    observed += noise
    
    # 2. Clip again to [0, rim]
    observed = np.clip(observed, 0.0, node_depths_m)
    
    # Dropouts
    if dropout_frac > 0.0:
        drop_mask = rng.random(size=observed.shape) < dropout_frac
        observed[drop_mask] = np.nan
        
    # Mask nodes without sensors
    observed[:, ~sensor_mask] = np.nan
    
    return observed

def blockage_injection(base_network: dict, severity: float, pipe_id: str) -> dict:
    """
    Returns a dictionary of pipe_id -> new_diameter_m
    """
    overrides = {}
    for p in base_network.get("pipes", []):
        if p["id"] == pipe_id:
            overrides[pipe_id] = p["diameter_m"] * (1.0 - severity)
            break
    return overrides
