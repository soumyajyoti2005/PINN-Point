import os, tempfile, json, hashlib
import pyswmm
import numpy as np
from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import run_simulation

def do_probe(ha):
    net_path = "/data/swmm/kolkata-amherst_network.json"
    with open(net_path, 'r') as f:
        network = json.load(f)
        
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': ha, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    sha256 = hashlib.sha256(inp_text.encode('utf-8')).hexdigest()
    print(f"\n--- HA {ha} ---")
    print(f"INP sha256: {sha256}")
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    # 1. No step advance pass
    true_times = []
    all_depths = []
    
    with pyswmm.Simulation(inp_path) as sim:
        nodes = list(pyswmm.Nodes(sim))
        node_ids = [n.nodeid for n in nodes]
        
        # Initial state (t=0)
        true_times.append(0.0)
        all_depths.append([n.depth for n in nodes])
        
        for step in sim:
            t = (sim.current_time - sim.start_time).total_seconds()
            true_times.append(t)
            all_depths.append([n.depth for n in nodes])
            
    os.remove(inp_path)
    
    true_times = np.array(true_times)
    all_depths = np.array(all_depths) # shape: (steps, nodes)
    
    # 2. Resample
    grid_times = np.arange(0, 7201, 60)
    resampled = np.zeros((len(grid_times), len(node_ids)))
    
    for i in range(len(node_ids)):
        resampled[:, i] = np.interp(grid_times, true_times, all_depths[:, i])
        
    print(f"Number of routing steps: {len(true_times)}")
    print(f"First true time: {true_times[0]}, Last true time: {true_times[-1]}")
    print(f"Grid length: {len(grid_times)}")
    print(f"Last recorded true time >= 7200: {true_times[-1] >= 7200}")
    
    # 3. Compare with run_simulation
    res = run_simulation(inp_text)
    api_times = res["times_s"]
    api_depths = res["depths"]
    
    # Find matching nodes
    max_diff = -1.0
    max_diff_node = None
    max_diff_time = None
    
    for i, t in enumerate(api_times):
        if t > 7080: continue # Only up to returned labels
        grid_idx = np.where(grid_times == t)[0][0]
        
        for j, nid in enumerate(node_ids):
            api_idx = res["node_ids"].index(nid)
            d_api = api_depths[i, api_idx]
            d_grid = resampled[grid_idx, j]
            
            diff = abs(d_grid - d_api)
            if diff > max_diff:
                max_diff = diff
                max_diff_node = nid
                max_diff_time = t
                
    print(f"Max |grid_depth - run_simulation_depth|: {max_diff:.8f}")
    print(f"Node/Time of max diff: {max_diff_node} at t={max_diff_time}s")
    
if __name__ == "__main__":
    do_probe(0.02)
    do_probe(0.05)
