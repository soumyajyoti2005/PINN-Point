import os
import json
import pyswmm
import tempfile
from app.sim.make_swmm_inp import build_inp_text

area = 'kolkata-amherst'
with open(f'/data/swmm/{area}_network.json') as f:
    network = json.load(f)

nodes = network.get("nodes", [])
pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}
pipe_lengths = {p['id']: p['length_m'] for p in network['pipes']}

settings = {
    'SWMM_CATCHMENT_HA_PER_NODE': 0.02,
    'SWMM_IMPERVIOUS_PCT': 100.0,
    'SWMM_PONDED_AREA_M2': 100.0
}

def run_storm(intensity, duration, report_baseline=False):
    storm = [(t, intensity) for t in range(duration + 1)]
    storm.append((duration + 1, 0.0))
    storm.append((duration + 60, 0.0)) # 1 hr cooldown
    
    inp_text = build_inp_text(network, storm, settings)
    with tempfile.NamedTemporaryFile(suffix='.inp', mode='w', delete=False) as f:
        f.write(inp_text)
        f_name = f.name
        
    try:
        max_depths = {}
        max_d_Ds = {}
        total_flood_vol = 0.0
        outfall_peak = 0.0
        surcharged_nodes = set()
        
        # Max node depths from the network definition for surcharge detection
        node_max_depth = {n['id']: n['depth_m'] for n in nodes}
        
        with pyswmm.Simulation(f_name) as sim:
            pnodes = list(pyswmm.Nodes(sim))
            plinks = list(pyswmm.Links(sim))
            
            for step in sim:
                for n in pnodes:
                    if n.depth > max_depths.get(n.nodeid, 0):
                        max_depths[n.nodeid] = n.depth
                        if n.depth >= node_max_depth.get(n.nodeid, 999) - 0.001:
                            surcharged_nodes.add(n.nodeid)
                    if n.flooding > 0:
                        total_flood_vol += n.flooding * sim.step_advance
                    if n.nodeid == 'MH-001':
                        if n.total_inflow > outfall_peak:
                            outfall_peak = n.total_inflow
                            
                for l in plinks:
                    if l.is_conduit():
                        diam = pipe_diam.get(l.linkid)
                        if diam:
                            d_D = l.depth / float(diam)
                            if d_D > max_d_Ds.get(l.linkid, 0):
                                max_d_Ds[l.linkid] = d_D
            
            runoff_err = sim.runoff_error
            routing_err = sim.flow_routing_error
            
            if report_baseline:
                print("--- BASELINE REPORT (60 mm/hr, 30 min) ---")
                print("Continuity Errors:")
                print(f"  Runoff Error: {runoff_err:.4f}")
                print(f"  Routing Error: {routing_err:.4f}")
                
                print("\nTop 10 Peak Depths per Node:")
                sorted_nodes = sorted(max_depths.items(), key=lambda x: x[1], reverse=True)
                for nid, d in sorted_nodes[:10]:
                    print(f"  {nid}: {d:.3f} m (max {node_max_depth.get(nid, 0):.3f} m)")
                print(f"Min Peak Depth: {sorted_nodes[-1][0]}: {sorted_nodes[-1][1]:.3f} m")
                
                print("\nTop 10 Peak d/D for Trunk Pipes:")
                sorted_links = sorted(max_d_Ds.items(), key=lambda x: x[1], reverse=True)
                for lid, d_D in sorted_links[:10]:
                    print(f"  {lid}: {d_D:.3f} (Diam: {pipe_diam.get(lid):.3f} m)")
                
                # outfall peak flow
                print(f"\nTotal Flooding Volume: {total_flood_vol:.2f} m3")
                print(f"Outfall Peak Flow: {outfall_peak*1000:.2f} LPS ({outfall_peak:.3f} CMS)\n")
            else:
                max_d = max(max_d_Ds.values()) if max_d_Ds else 0
                print(f"Storm {intensity} mm/hr, {duration} min -> "
                      f"Flood Vol: {total_flood_vol:.2f} m3, "
                      f"Max d/D: {max_d:.2f}, "
                      f"Surcharged Nodes: {len(surcharged_nodes)}")
    finally:
        os.remove(f_name)

print("\nRunning heavy-storm check...")
run_storm(30, 30)
run_storm(60, 30, report_baseline=True)
run_storm(100, 30)
run_storm(100, 90)
