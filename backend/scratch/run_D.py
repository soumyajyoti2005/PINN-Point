import os, tempfile, json
import numpy as np
import pyswmm
from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import run_simulation

def do_D(ha):
    print(f"\n=== D.1 & D.2: {ha} ha ===")
    net_path = '/data/swmm/kolkata-amherst_network.json'
    with open(net_path, 'r') as f: network = json.load(f)
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': ha, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)

    fd, inp_path = tempfile.mkstemp(suffix='.inp')
    os.close(fd)
    with open(inp_path, 'w', encoding='utf-8') as f: f.write(inp_text)

    # D.3
    if ha == 0.02:
        print("\n=== D.3 ===")
        with pyswmm.Simulation(inp_path) as sim:
            n = next(n for n in pyswmm.Nodes(sim) if n.nodeid == "MH-024")
            for _ in sim: pass
            print(f"End of loop sim.current_time = {sim.current_time}")
            try:
                print(f"Read one node depth after loop: {n.depth}")
            except Exception as e:
                print(f"Failed: {e}")

    # Fine routing-step series
    true_times = []
    depths = []
    with pyswmm.Simulation(inp_path) as sim:
        nodes = list(pyswmm.Nodes(sim))
        node_ids = [n.nodeid for n in nodes]
        for _ in sim:
            true_times.append((sim.current_time - sim.start_time).total_seconds())
            depths.append([n.depth for n in nodes])
            
    true_times = np.array(true_times)
    depths = np.array(depths)
    
    if ha == 0.02:
        diff_last = np.abs(depths[-1, :] - depths[-2, :])
        max_idx = np.argmax(diff_last)
        print(f"0.02 ha max |depth(last) - depth(second-last)| = {diff_last[max_idx]:.8f} at node {node_ids[max_idx]}")
        print(f"True times: {true_times[-2]}s and {true_times[-1]}s")

    # Time probe logic (true sample times of run_simulation)
    print("\nTime probe logic ...")
    api_true_times = []
    with pyswmm.Simulation(inp_path) as sim:
        for _ in range(120): # maximum 120 advances
            sim.step_advance(60)
            try:
                next(sim)
                api_true_times.append((sim.current_time - sim.start_time).total_seconds())
            except StopIteration:
                break
    
    api_true_times = np.array(api_true_times)
    
    # Run simulation
    res = run_simulation(inp_text)
    api_depths = res["depths"]
    
    interp_depths = np.zeros((len(api_true_times), len(node_ids)))
    for i in range(len(node_ids)):
        interp_depths[:, i] = np.interp(api_true_times, true_times, depths[:, i])
        
    # Compare
    max_diff = -1.0
    max_diff_loc = None
    for i, t in enumerate(api_true_times):
        for j, nid in enumerate(node_ids):
            api_idx = res["node_ids"].index(nid)
            # api_depths shape: (119, 2236)
            d_api = api_depths[i, api_idx]
            d_interp = interp_depths[i, j]
            diff = abs(d_api - d_interp)
            if diff > max_diff:
                max_diff = diff
                max_diff_loc = (nid, t)
                
    print(f"Max |diff| between interp(true_times) and run_simulation: {max_diff:.8f} at {max_diff_loc}")
    os.remove(inp_path)

if __name__ == "__main__":
    do_D(0.02)
    do_D(0.05)
