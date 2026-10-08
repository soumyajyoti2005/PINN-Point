import os, tempfile
from app.sim.make_swmm_inp import build_inp_text
import pyswmm
import json

def get_routing_error(rpt_path):
    with open(rpt_path, 'r') as f:
        in_routing = False
        for line in f:
            if "Flow Routing Continuity" in line:
                in_routing = True
            elif in_routing and "Error" in line:
                return float(line.split()[-1])
            elif in_routing and (line.strip() == "" or line.startswith("***")):
                in_routing = False
    return None

def test_routing_step(net_path, routing_step):
    with open(net_path, 'r') as f:
        network = json.load(f)
    
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    lines = []
    for l in inp_text.splitlines():
        if l.startswith("ROUTING_STEP"):
            lines.append(f"ROUTING_STEP         {routing_step}")
        else:
            lines.append(l)
    inp_text = "\n".join(lines)
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}
    max_d_D = 0.0
    
    try:
        with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
            link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
            for step in sim:
                for l in link_objs:
                    if l.linkid == "P-034-033":
                        diam = pipe_diam.get(l.linkid)
                        if diam:
                            d_D = l.depth / float(diam)
                            max_d_D = max(max_d_D, d_D)
    finally:
        pass
        
    err = get_routing_error(rpt_path)
    os.remove(inp_path)
    os.remove(rpt_path)
    return max_d_D, err

if __name__ == "__main__":
    net = "/data/swmm/kolkata-amherst_network.json"
    print("SENSITIVITY TEST P-034-033:")
    for step in [5, 2, 1]:
        d, e = test_routing_step(net, step)
        print(f"ROUTING_STEP {step}: max d/D = {d}, Routing Error = {e}%")
