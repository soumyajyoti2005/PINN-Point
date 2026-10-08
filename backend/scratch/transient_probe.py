import os, tempfile, json, hashlib
import pyswmm
from app.sim.make_swmm_inp import build_inp_text

def get_links():
    net_path = '/data/swmm/kolkata-amherst_network.json'
    with open(net_path, 'r') as f:
        network = json.load(f)
        
    mh024_links = []
    mh023_links = []
    for p in network['pipes']:
        if p['from_node'] == 'MH-024' or p['to_node'] == 'MH-024':
            mh024_links.append((p['id'], p['from_node'], p['to_node']))
        if p['from_node'] == 'MH-023' or p['to_node'] == 'MH-023':
            mh023_links.append((p['id'], p['from_node'], p['to_node']))
            
    print("Links connected to MH-024:")
    for l in mh024_links: print(l)
    print("Links connected to MH-023:")
    for l in mh023_links: print(l)
    return [l[0] for l in mh024_links] + [l[0] for l in mh023_links]

def run_variant(name, routing_step, damping_full=False, dump_series=False):
    net_path = '/data/swmm/kolkata-amherst_network.json'
    with open(net_path, 'r') as f: network = json.load(f)
    
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.05, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    lines = []
    for l in inp_text.splitlines():
        if l.startswith("ROUTING_STEP"):
            lines.append(f"ROUTING_STEP         {routing_step}")
        else:
            lines.append(l)
            if damping_full and l.startswith("FLOW_ROUTING"):
                lines.append("INERTIAL_DAMPING     FULL")
    
    inp_text = "\n".join(lines)
    sha256 = hashlib.sha256(inp_text.encode('utf-8')).hexdigest()
    print(f"\nVariant {name}: INP sha256 = {sha256}")
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    mh024_max = 0.0
    mh024_time = None
    mh023_max = 0.0
    mh023_time = None
    
    connected = get_links()
    
    signs = {lid: 1 for lid in connected}
    flips = {lid: 0 for lid in connected}
    
    try:
        with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
            n_objs = list(pyswmm.Nodes(sim))
            l_objs = list(pyswmm.Links(sim))
            
            for step in sim:
                t = sim.current_time
                true_s = (t - sim.start_time).total_seconds()
                
                # Check nodes
                mh024_d = 0.0
                mh024_in = 0.0
                mh024_out = 0.0
                
                for n in n_objs:
                    if n.nodeid == "MH-024":
                        mh024_d = n.depth
                        mh024_in = n.total_inflow
                        mh024_out = n.total_outflow
                        if n.depth > mh024_max:
                            mh024_max = n.depth
                            mh024_time = true_s
                    elif n.nodeid == "MH-023":
                        if n.depth > mh023_max:
                            mh023_max = n.depth
                            mh023_time = true_s
                            
                flows = {}
                for l in l_objs:
                    if l.linkid in connected:
                        fl = l.flow
                        flows[l.linkid] = fl
                        s = 1 if fl >= 0 else -1
                        if true_s >= 1040 and true_s <= 1065: # 17:20 to 17:45
                            if signs[l.linkid] != s:
                                flips[l.linkid] += 1
                                signs[l.linkid] = s
                                
                if dump_series and true_s >= 1040 and true_s <= 1065:
                    print(f"{t.strftime('%H:%M:%S')} | depth: {mh024_d:.4f} | in: {mh024_in:.4f} | out: {mh024_out:.4f} | flows: " + " ".join([f"{lid}={flows.get(lid,0):.4f}" for lid in connected]))
                    
    finally:
        pass
        
    print(f"MH-024 max depth: {mh024_max:.4f} at {mh024_time}s")
    print(f"MH-023 max depth: {mh023_max:.4f} at {mh023_time}s")
    
    if dump_series:
        print("Sign flips per link:")
        for lid in connected:
            print(f"  {lid}: {flips[lid]}")
            
    err = None
    with open(rpt_path, 'r') as f:
        in_routing = False
        for line in f:
            if "Flow Routing Continuity" in line: in_routing = True
            elif in_routing and "Error" in line:
                err = float(line.split()[-1])
                break
                
    print(f"Flow Routing Continuity Error: {err}%")
    os.remove(inp_path)
    os.remove(rpt_path)

if __name__ == "__main__":
    run_variant("Baseline 0.05", 5, dump_series=True)
    run_variant("ROUTING_STEP 1", 1)
    run_variant("INERTIAL_DAMPING FULL", 5, damping_full=True)
