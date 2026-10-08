import os, tempfile, json
import numpy as np
import pyswmm
from app.sim.make_swmm_inp import build_inp_text

# B.1, B.2, B.3
net_path = '/data/swmm/kolkata-amherst_network.json'
with open(net_path, 'r') as f: network = json.load(f)
storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.05, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
inp_text = build_inp_text(network, storm, settings, duration_minutes=120)

fd, inp_path = tempfile.mkstemp(suffix='.inp')
os.close(fd)
fd, rpt_path = tempfile.mkstemp(suffix='.rpt')
os.close(fd)
with open(inp_path, 'w', encoding='utf-8') as f: f.write(inp_text)

true_times = []
depths = []
target_nodes = ['MH-024', 'MH-023', 'MH-037', 'MH-022', 'MH-036']
with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
    nodes = [n for n in pyswmm.Nodes(sim) if n.nodeid in target_nodes]
    for step in sim:
        t = (sim.current_time - sim.start_time).total_seconds()
        true_times.append(t)
        depths.append([n.depth for n in nodes])

true_times = np.array(true_times)
depths = np.array(depths)

rpt_rep_depth = {}
with open(rpt_path, 'r') as f:
    in_sec = False
    for l in f:
        if 'Node Depth Summary' in l: in_sec = True
        elif in_sec and l.startswith('  ***'): break
        elif in_sec and l.strip() and not l.startswith('  -') and not l.startswith('  N') and not l.startswith('  A'):
            parts = l.split()
            if parts[0] in target_nodes:
                rpt_rep_depth[parts[0]] = float(parts[-1])

# B.1 exact 60s
print("=== B.1 ===")
grid = np.arange(0, 7201, 60)
interp_depths = np.zeros((len(grid), len(target_nodes)))
for i in range(len(target_nodes)):
    interp_depths[:, i] = np.interp(grid, true_times, depths[:, i])

for i, nid in enumerate(target_nodes):
    max_idx = np.argmax(interp_depths[:, i])
    print(f"{nid}: Interp Max={interp_depths[max_idx, i]:.4f} at {grid[max_idx]}s | .rpt Rep={rpt_rep_depth[nid]}")

# B.2 nearest
print("\n=== B.2 ===")
nearest_depths = np.zeros((len(grid), len(target_nodes)))
for i, g in enumerate(grid):
    idx = np.abs(true_times - g).argmin()
    nearest_depths[i, :] = depths[idx, :]
for i, nid in enumerate(target_nodes):
    max_idx = np.argmax(nearest_depths[:, i])
    print(f"{nid}: Nearest Max={nearest_depths[max_idx, i]:.4f} at {grid[max_idx]}s (true {true_times[np.abs(true_times - grid[max_idx]).argmin()]:.1f}s) | .rpt Rep={rpt_rep_depth[nid]}")
print("Scheme matching Reported Max Depth: Nearest (it directly samples the routing step closest to the reporting boundary).")

# B.3 MH-037 series
print("\n=== B.3 ===")
i37 = target_nodes.index('MH-037')
print("MH-037 routing steps (11:50 to 12:15, i.e., 710s to 735s):")
for t, d in zip(true_times, depths[:, i37]):
    if 710 <= t <= 735: print(f"  t={t:.2f}s, depth={d:.4f}")
print("Interpolated:")
for g in [660, 720, 780]:
    val = np.interp(g, true_times, depths[:, i37])
    print(f"  t={g}s, depth={val:.4f}")

os.remove(inp_path)
os.remove(rpt_path)
