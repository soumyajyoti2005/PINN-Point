import os, tempfile, json, pyswmm
from app.sim.make_swmm_inp import build_inp_text

def time_probe():
    net_path = "/data/swmm/kolkata-amherst_network.json"
    with open(net_path, 'r') as f:
        network = json.load(f)
    
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    records = []
    
    with pyswmm.Simulation(inp_path) as sim:
        sim.step_advance(60)
        node_objs = [node for node in pyswmm.Nodes(sim)]
        
        start_time = sim.start_time
        records.append((0, 0.0))
        t = 60
        
        loop_iterations = 0
        for step in sim:
            loop_iterations += 1
            true_sec = (sim.current_time - start_time).total_seconds()
            records.append((t, true_sec))
            t += 60
            
        print(f"sim.start_time: {sim.start_time}")
        print(f"sim.end_time: {sim.end_time}")
        print(f"Loop iterations: {loop_iterations}")
        
    os.remove(inp_path)
    
    print(f"Number of samples: {len(records)}")
    
    print("FIRST 5:")
    for lab, tru in records[:5]:
        print(f"{lab}, {tru}, {lab - tru}")
        
    print("LAST 5:")
    for lab, tru in records[-5:]:
        print(f"{lab}, {tru}, {lab - tru}")
        
    max_diff = max(abs(lab - tru) for lab, tru in records)
    print(f"Max |label - true|: {max_diff}")

if __name__ == "__main__":
    time_probe()
