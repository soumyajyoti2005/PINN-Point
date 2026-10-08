import os, json, sys, pyswmm
from app.sim.make_swmm_inp import build_inp_text

area = 'kolkata-amherst'
data_dir = '/data'
swmm_dir = os.path.join(data_dir, 'swmm')
net_path = os.path.join(swmm_dir, f'{area}_network.json')
with open(net_path) as f:
    network = json.load(f)

storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}

def run_calib(ha):
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': ha, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    inp_text = build_inp_text(network, storm, settings)
    inp_path = '/tmp/test.inp'
    with open(inp_path, 'w') as f:
        f.write(inp_text)
        
    max_d_D = 0.0
    max_flood = 0.0
    
    with pyswmm.Simulation(inp_path) as sim:
        nodes = pyswmm.Nodes(sim)
        links = pyswmm.Links(sim)
        for step in sim:
            for n in nodes:
                if n.flooding > 0:
                    max_flood += n.flooding * sim.step_advance
            for l in links:
                if l.is_conduit():
                    diam = pipe_diam.get(l.linkid)
                    if diam:
                        d_D = l.depth / float(diam)
                        if d_D > max_d_D:
                            max_d_D = d_D
                            
        print(f"HA: {ha}, Max d/D: {max_d_D}, Flood: {max_flood}, Outfall: {nodes['MH-001'].cumulative_inflow}")

run_calib(0.01)
run_calib(0.05)
run_calib(0.1)
