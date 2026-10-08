import os, tempfile, json, datetime
import pyswmm
import numpy as np
from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import run_simulation

def probe():
    net_path = "/data/swmm/kolkata-amherst_network.json"
    with open(net_path, 'r') as f:
        network = json.load(f)
        
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.05, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    # parse RPT for these nodes
    target_nodes = ["MH-024", "MH-023", "MH-037", "MH-022", "MH-036"]
    
    # 1. Get RPT depths using plain API so it generates the RPT
    node_depths_plain = {}
    with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
        n_objs = list(pyswmm.Nodes(sim))
        for step in sim:
            for n in n_objs:
                node_depths_plain[n.nodeid] = max(node_depths_plain.get(n.nodeid, 0.0), n.depth)
                
    with open(rpt_path, 'r') as f:
        rpt_lines = f.readlines()
        
    rpt_max_depth = {}
    rpt_rep_depth = {}
    rpt_rep_time = {}
    in_nd = False
    dash_count = 0
    for l in rpt_lines:
        if "Node Depth Summary" in l: in_nd = True; dash_count = 0; continue
        if in_nd and l.startswith("  ---"): dash_count += 1; continue
        if in_nd and dash_count >= 2:
            if l.strip() == "" or l.startswith("  ***") or l.startswith("  ==="): in_nd = False; continue
            parts = l.split()
            if len(parts) >= 6:
                nid = parts[0]
                if nid in target_nodes:
                    rpt_max_depth[nid] = float(parts[3])
                    rpt_rep_depth[nid] = float(parts[-1])
                    rpt_rep_time[nid] = parts[-3] + " " + parts[-2]
                    
    # API Max
    res = run_simulation(inp_text)
    api_max_depth = {}
    api_mh024_samples = []
    
    mh024_dt = None
    if "MH-024" in rpt_rep_time:
        try:
            mh024_dt = datetime.datetime.strptime("2026-01-01 " + rpt_rep_time["MH-024"].split()[1], "%Y-%m-%d %H:%M")
        except:
            pass
        
    for nid in target_nodes:
        if nid in res["node_ids"]:
            idx = res["node_ids"].index(nid)
            api_max_depth[nid] = np.max(res["depths"][:, idx])
            
            if nid == "MH-024" and mh024_dt:
                for i, ts in enumerate(res["times_s"]):
                    sample_dt = datetime.datetime(2026, 1, 1, 0, 0, 0) + datetime.timedelta(seconds=float(ts))
                    if abs((sample_dt - mh024_dt).total_seconds()) <= 180:
                        api_mh024_samples.append((sample_dt.strftime("%H:%M:%S"), res["depths"][i, idx]))
                        
    # NO STEP ADVANCE EXTRA PASS
    no_step_max = {}
    no_step_time = {}
    no_step_60_max = {}
    mh024_series = []
    
    with pyswmm.Simulation(inp_path) as sim2:
        n_objs = list(pyswmm.Nodes(sim2))
        for step in sim2:
            t = sim2.current_time
            delta_s = (t - sim2.start_time).total_seconds()
            
            for n in n_objs:
                if n.nodeid in target_nodes:
                    d = n.depth
                    if d > no_step_max.get(n.nodeid, -1.0):
                        no_step_max[n.nodeid] = d
                        no_step_time[n.nodeid] = t
                        
                    if delta_s % 60 == 0:
                        if d > no_step_60_max.get(n.nodeid, -1.0):
                            no_step_60_max[n.nodeid] = d
                            
                    if n.nodeid == "MH-024" and mh024_dt:
                        if abs((t - mh024_dt).total_seconds()) <= 180:
                            mh024_series.append((t.strftime("%H:%M:%S"), d))
                            
    os.remove(inp_path)
    if os.path.exists(rpt_path): os.remove(rpt_path)
    
    print(f"{'Node':<8} | {'RPT Max':<8} | {'RPT Rep':<8} | {'API Max':<8} | {'NoStep All':<10} | {'NoStep 60s':<10}")
    print("-" * 75)
    for nid in target_nodes:
        print(f"{nid:<8} | {rpt_max_depth.get(nid, 0):<8} | {rpt_rep_depth.get(nid, 0):<8} | {api_max_depth.get(nid, 0):<8.4f} | {no_step_max.get(nid, 0):<10.4f} | {no_step_60_max.get(nid, 0):<10.4f}")
        print(f"  Time of NoStep Max: {no_step_time.get(nid)}")
        print(f"  Time of Maximum Depth (.rpt): {rpt_rep_time.get(nid)}")
        
    print("\nMH-024 ROUTING STEP SERIES (+/- 3 min from .RPT max):")
    for t, d in mh024_series:
        print(f"  {t}: {d:.4f}")
        
    print("\nMH-024 API SAMPLES (+/- 3 min):")
    for t, d in api_mh024_samples:
        print(f"  {t}: {d:.4f}")

if __name__ == "__main__":
    probe()
