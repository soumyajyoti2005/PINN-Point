import os, json, hashlib, difflib, tempfile
import pyswmm
from app.sim.make_swmm_inp import build_inp_text

net_path = '/data/swmm/kolkata-amherst_network.json'
with open(net_path, 'r') as f: network = json.load(f)
pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}
storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}

def get_rpt_row(rpt_path, linkid):
    with open(rpt_path, 'r') as f:
        lines = f.readlines()
    in_sec = False
    for l in lines:
        if 'Link Flow Summary' in l: in_sec = True
        elif in_sec and linkid in l:
            return l.rstrip()
    return None

# A.1
print("=== A.1 ===")
inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
sha_unmod = hashlib.sha256(inp_text.encode('utf-8')).hexdigest()

fd, inp_path = tempfile.mkstemp(suffix='.inp')
os.close(fd)
with open(inp_path, 'w', encoding='utf-8') as f:
    f.write(inp_text)

for run_idx in range(2):
    max_d_D = 0.0
    argmax = None
    argmax_time = None
    steps = 0
    with pyswmm.Simulation(inp_path) as sim:
        link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
        for _ in sim:
            steps += 1
            for l in link_objs:
                if l.linkid == 'P-034-033':
                    d_D = l.depth / float(pipe_diam[l.linkid])
                    if d_D > max_d_D:
                        max_d_D = d_D
                        argmax = l.linkid
                        argmax_time = sim.current_time
    print(f"Run {run_idx}: sha256={sha_unmod}, steps={steps}, max d/D={max_d_D:.10f}, link={argmax}, time={argmax_time}")

# A.2
print("\n=== A.2 ===")
fd, rpt_path = tempfile.mkstemp(suffix='.rpt')
os.close(fd)
max_d_D_2 = 0.0
with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
    link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
    for _ in sim:
        for l in link_objs:
            if l.linkid == 'P-034-033':
                d_D = l.depth / float(pipe_diam[l.linkid])
                if d_D > max_d_D_2: max_d_D_2 = d_D
print(f"Sensitivity (unmod): sha256={sha_unmod}, max d/D={max_d_D_2:.10f}")

# A.3
print("\n=== A.3 ===")
lines = []
for l in inp_text.splitlines():
    if l.startswith("ROUTING_STEP"): lines.append(f"ROUTING_STEP         5")
    else: lines.append(l)
inp_sens = "\n".join(lines)
sha_sens = hashlib.sha256(inp_sens.encode('utf-8')).hexdigest()

diff = list(difflib.unified_diff(inp_text.splitlines(keepends=True), inp_sens.splitlines(keepends=True), n=0))
print("Unified diff (repr):")
for d in diff: print(repr(d))
print(f"Unmod \\r count: {inp_text.count(chr(13))}")
print(f"Sens \\r count: {inp_sens.count(chr(13))}")
print("Unmod last 3 lines:", repr(inp_text.splitlines(keepends=True)[-3:]))
print("Sens last 3 lines:", repr(inp_sens.splitlines(keepends=True)[-3:]))

# A.5
print("\n=== A.5 ===")
raw_row = get_rpt_row(rpt_path, 'P-034-033')
print(f"Raw row: {repr(raw_row)}")
print("Tokens: 0:Link, 1:Type, 2:MaxFlow, 3:MaxDate, 4:MaxTime, 5:MaxVelocity, 6:Max/FullFlow, 7:Max/FullDepth")

# A.6
print("\n=== A.6 ===")
for step in [5, 2, 1]:
    # modifying only the digit, exactly matched
    inp_mod = inp_text.replace("ROUTING_STEP         5", f"ROUTING_STEP         {step}")
    with open(inp_path, 'w', encoding='utf-8') as f: f.write(inp_mod)
    with pyswmm.Simulation(inp_path) as sim:
        link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
        max_d_D = 0.0
        for _ in sim:
            for l in link_objs:
                if l.linkid == 'P-034-033':
                    d_D = l.depth / float(pipe_diam[l.linkid])
                    if d_D > max_d_D: max_d_D = d_D
    print(f"Digit {step}: max d/D={max_d_D:.10f}")

os.remove(inp_path)
os.remove(rpt_path)
