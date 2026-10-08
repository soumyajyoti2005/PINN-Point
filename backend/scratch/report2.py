import os, json, pyswmm, tempfile, re
from app.sim.make_swmm_inp import build_inp_text

area = 'kolkata-amherst'
with open(f'/data/swmm/{area}_network.json') as f: network = json.load(f)
nodes = network.get("nodes", [])
pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}

def run_storm(intensity, duration, ha):
    settings = {
        'SWMM_CATCHMENT_HA_PER_NODE': ha,
        'SWMM_IMPERVIOUS_PCT': 100.0,
        'SWMM_PONDED_AREA_M2': 100.0
    }
    storm = [(t, intensity) for t in range(duration + 1)]
    storm.append((duration + 1, 0.0))
    storm.append((duration + 60, 0.0))
    
    inp_text = build_inp_text(network, storm, settings)
    
    fd, inp_path = tempfile.mkstemp(suffix='.inp')
    with os.fdopen(fd, 'w') as f:
        f.write(inp_text)
        
    rpt_path = inp_path.replace('.inp', '.rpt')
    out_path = inp_path.replace('.inp', '.out')
    
    outfall_peak_lps = 0.0
    outfall_vol_m3 = 0.0
    runoff_err = 0.0
    routing_err = 0.0
    max_depths = {}
    
    with pyswmm.Simulation(inp_path) as sim:
        pnodes = list(pyswmm.Nodes(sim))
        outfall = pyswmm.Nodes(sim)['MH-001']
        for step in sim:
            for n in pnodes:
                d = n.depth
                if d > max_depths.get(n.nodeid, 0): max_depths[n.nodeid] = d
            inflow = outfall.total_inflow
            if inflow > outfall_peak_lps: outfall_peak_lps = inflow
            
        outfall_vol_m3 = outfall.cumulative_inflow
        runoff_err = sim.runoff_error
        routing_err = sim.flow_routing_error
        
    outfall_peak_lps *= 1000 # CMS to LPS
    
    print(f"--- HA {ha:.4f}, Storm {intensity} mm/hr, {duration} min ---")
    print(f"Code reports: Runoff Err = {runoff_err:.4f}, Routing Err = {routing_err:.4f}")
    print(f"Outfall Peak Rate: {outfall_peak_lps:.2f} LPS, Outfall Total Volume: {outfall_vol_m3:.2f} m3")
    
    if intensity in [60, 100] and ha == 0.02:
        with open(rpt_path) as f: rpt = f.read()
        print("\n--- .rpt Continuity Sections ---")
        lines = rpt.split('\n')
        for i, line in enumerate(lines):
            if "Continuity Error (%)" in line:
                print("\n".join(lines[i-4:i+2]))
                
        if intensity == 60:
            print("\n--- Leaf-node check (lowest peak depths) ---")
            sorted_nodes = sorted(max_depths.items(), key=lambda x: x[1])
            for nid, d in sorted_nodes[:10]:
                print(f"{nid}: {d:.3f} m")
                
    os.remove(inp_path)
    if os.path.exists(rpt_path): os.remove(rpt_path)
    if os.path.exists(out_path): os.remove(out_path)
    print("")

print("1. Calibration Sweep (60 mm/hr, 30 min):")
for ha in [0.01, 0.015, 0.02]: run_storm(60, 30, ha)

print("2. Heavy Storm (100 mm/hr, 90 min) at HA 0.02:")
run_storm(100, 90, 0.02)
