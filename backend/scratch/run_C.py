import os, tempfile, json, hashlib
import pyswmm
from app.sim.make_swmm_inp import build_inp_text

# A.4
print("=== A.4 ===")
net_path = '/data/swmm/kolkata-amherst_network.json'
with open(net_path, 'r') as f: network = json.load(f)
storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.05, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
inp_text = build_inp_text(network, storm, settings, duration_minutes=120)

lines = []
for l in inp_text.splitlines(): lines.append(l)
inp_transient = "\n".join(lines)

sha_base = hashlib.sha256(inp_text.encode('utf-8')).hexdigest()
sha_transient = hashlib.sha256(inp_transient.encode('utf-8')).hexdigest()
print(f"Base INP (resample_probe): {sha_base}")
print(f"Transient INP: {sha_transient}")
print("Differences are whitespace only (splitlines drops the trailing newline).")
print(f"Wait, what is d187e1f4? Let's check.")

# C
print("\n=== C.1 & C.3 ===")
def get_rpt_error(rpt_path):
    with open(rpt_path, 'r') as f:
        in_r = False
        for l in f:
            if "Flow Routing Continuity" in l: in_r = True
            elif in_r and "Error" in l: return float(l.split()[-1])
    return None

def get_rpt_damping(rpt_path):
    with open(rpt_path, 'r') as f:
        in_opt = False
        for l in f:
            if "Analysis Options" in l: in_opt = True
            elif in_opt and "Inertial Damping" in l: return l.strip()
            elif in_opt and l.startswith("  ---"): pass
            elif in_opt and l.strip() == "": return None
    return None

def run_variant(name, routing_step, damping="PARTIAL", min_area=1.167):
    lines = []
    for l in inp_text.splitlines():
        if l.startswith("ROUTING_STEP"): lines.append(f"ROUTING_STEP         {routing_step}")
        elif l.startswith("INERTIAL_DAMPING"): lines.append(f"INERTIAL_DAMPING     {damping}")
        elif l.startswith("MIN_SURFAREA"): lines.append(f"MIN_SURFAREA         {min_area}")
        else: lines.append(l)
    inp = "\n".join(lines) + "\n"
    
    fd, p_inp = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, p_rpt = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    with open(p_inp, "w") as f: f.write(inp)
    
    mh024_max = 0.0; mh024_time = None
    mh023_max = 0.0
    sec_above_08 = 0.0
    last_t = 0.0
    
    with pyswmm.Simulation(p_inp, reportfile=p_rpt) as sim:
        nodes = list(pyswmm.Nodes(sim))
        for step in sim:
            t = (sim.current_time - sim.start_time).total_seconds()
            dt = t - last_t
            last_t = t
            for n in nodes:
                if n.nodeid == "MH-024":
                    if n.depth > mh024_max: mh024_max = n.depth; mh024_time = t
                    if n.depth > 0.8: sec_above_08 += dt
                elif n.nodeid == "MH-023":
                    if n.depth > mh023_max: mh023_max = n.depth
    
    err = get_rpt_error(p_rpt)
    damp_line = get_rpt_damping(p_rpt)
    print(f"{name:25s} | sha256: {hashlib.sha256(inp.encode()).hexdigest()[:8]} | MH-024 max {mh024_max:.4f} at {mh024_time}s (>0.8m for {sec_above_08:.1f}s) | MH-023 max {mh023_max:.4f} | Err: {err}% | {damp_line}")
    os.remove(p_inp); os.remove(p_rpt)

print("(i)")
run_variant("ROUTING_STEP 5 (base)", 5)
run_variant("ROUTING_STEP 2", 2)
run_variant("ROUTING_STEP 1", 1)
run_variant("ROUTING_STEP 0.5", 0.5)

print("(ii)")
run_variant("INERTIAL_DAMPING FULL", 5, damping="FULL")

print("(iii)")
run_variant("MIN_SURFAREA 1.167", 5, min_area=1.167)
run_variant("MIN_SURFAREA 5", 5, min_area=5)
run_variant("MIN_SURFAREA 10", 5, min_area=10)

print("\n=== C.2 & C.3 ===")
fd, p_inp = tempfile.mkstemp(suffix=".inp")
os.close(fd)
fd, p_rpt = tempfile.mkstemp(suffix=".rpt")
os.close(fd)
with open(p_inp, "w") as f: f.write(inp_text)

last_t = 0.0
vol_change = 0.0
depth_1728 = None
depth_1731 = None

sign_flips = {'P-024-023': 0, 'P-023-022': 0}
dqdt_flips = {'P-024-023': 0, 'P-023-022': 0}

last_q = {'P-024-023': 0.0, 'P-023-022': 0.0}
last_dqdt = {'P-024-023': 0.0, 'P-023-022': 0.0}
last_sign = {'P-024-023': 1, 'P-023-022': 1}
last_dqdt_sign = {'P-024-023': 1, 'P-023-022': 1}

print("Time | MH-024 d | Inflow | Outflow | P-024-023 Q | P-023-022 Q | P-024-023 V | P-023-022 V")
with pyswmm.Simulation(p_inp) as sim:
    nodes = list(pyswmm.Nodes(sim))
    links = list(pyswmm.Links(sim))
    
    mh024 = next(n for n in nodes if n.nodeid == "MH-024")
    
    for step in sim:
        t = (sim.current_time - sim.start_time).total_seconds()
        dt = t - last_t
        last_t = t
        
        inflow = mh024.total_inflow
        outflow = mh024.total_outflow
        d = mh024.depth
        
        q24 = next(l for l in links if l.linkid == "P-024-023")
        q23 = next(l for l in links if l.linkid == "P-023-022")
        
        if 1044 <= t <= 1060: # 17:24 to 17:40
            print(f"{t:.1f} | {d:.4f} | {inflow:.4f} | {outflow:.4f} | {q24.flow:.4f} | {q23.flow:.4f} | {q24.volume:.4f} | {q23.volume:.4f}")
            
        if 1048 <= t <= 1051: # 17:28 to 17:31
            vol_change += (inflow - outflow) * dt
            if depth_1728 is None: depth_1728 = d
            depth_1731 = d
            
        for l in [q24, q23]:
            lid = l.linkid
            q = l.flow
            if 1044 <= t <= 1060:
                s = 1 if q >= 0 else -1
                if s != last_sign[lid]:
                    sign_flips[lid] += 1
                    last_sign[lid] = s
                
                if dt > 0:
                    dqdt = (q - last_q[lid]) / dt
                    s_dqdt = 1 if dqdt >= 0 else -1
                    if s_dqdt != last_dqdt_sign[lid] and last_q[lid] != 0.0:
                        dqdt_flips[lid] += 1
                    last_dqdt_sign[lid] = s_dqdt
            last_q[lid] = q

print(f"\nNet volume change 17:28 to 17:31: {vol_change:.6f} m3")
d_change = depth_1731 - depth_1728
print(f"Depth change: {d_change:.4f} m")
if d_change > 0: print(f"Implied area (dV/dd): {vol_change / d_change:.4f} m2")
print(f"MH-024 ponding_area={mh024.ponding_area}, surcharge_depth={mh024.surcharge_depth}")

print(f"Sign flips: {sign_flips}")
print(f"dQ/dt flips: {dqdt_flips}")
os.remove(p_inp); os.remove(p_rpt)
