import os
import time
import json
import numpy as np
from app.sim.generate_dataset import run_simulation


def main():
    print("=== PART D: Timing ===")
    
    cpu_count = os.cpu_count()
    print(f"os.cpu_count(): {cpu_count}")
    
    # Run simulation locally to time it
    data_dir = os.environ.get("DATA_DIR", "/data")
    with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
        network = json.load(f)
        
    times = []
    
    storm = [(t, 60.0) if 30 <= t < 60 else (t, 0.0) for t in range(120)]
    
    from app.sim.make_swmm_inp import build_inp_text
    
    for i in range(10):
        t0 = time.time()
        inp_text = build_inp_text(network, storm, {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}, duration_minutes=120)
        run_simulation(inp_text, network)
        t1 = time.time()
        times.append(t1 - t0)
        
    print(f"10 runs in a SINGLE process: {np.mean(times):.4f}s ± {np.std(times):.4f}s per run")
    
if __name__ == "__main__":
    main()
