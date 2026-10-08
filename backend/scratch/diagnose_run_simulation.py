import os
import json
import numpy as np
import pyswmm
import tempfile
import sys

from app.sim.make_swmm_inp import build_inp_text
from app.sim.generate_dataset import run_simulation

def main():
    print("=== A. 7C CALIBRATION METRIC DEFINITION ===")
    print("Storm used in calib.py:")
    print("  storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]")
    print("Settings used in calib.py:")
    print("  settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}")
    print("Metric definition in calib.py (produced ~0.73):")
    print("  for l in links:")
    print("      if l.is_conduit():")
    print("          diam = pipe_diam.get(l.linkid)")
    print("          if diam:")
    print("              d_D = l.depth / float(diam)")
    print("              if d_D > max_d_D:")
    print("                  max_d_D = d_D")
    
    print("\n=== B. RUN SWMM & PARSE REPORT ===")
    area = 'kolkata-amherst'
    net_path = f'/data/swmm/{area}_network.json'
    if not os.path.exists(net_path):
        print(f"File not found: {net_path}")
        return
        
    with open(net_path) as f:
        network = json.load(f)
        
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    
    inp_text = build_inp_text(network, storm, settings)
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    try:
        with pyswmm.Simulation(inp_path) as sim:
            sim.report_filename = rpt_path
            for step in sim:
                pass
                
        with open(rpt_path, "r") as f:
            rpt_lines = f.readlines()
            
        print(f"Parsed .rpt file ({len(rpt_lines)} lines).")
        
        node_depths_rpt = {}
        link_flows_rpt = {}
        max_trunk_dd = 0.0
        trunk_id = ""
        
        mode = None
        for line in rpt_lines:
            if "Node Depth Summary" in line: mode = "NODE_DEPTH"
            elif "Link Flow Summary" in line: mode = "LINK_FLOW"
            elif "Node Flooding Summary" in line: mode = "NODE_FLOOD"
            elif "Continuity Error" in line: mode = "CONTINUITY"
            elif "Analysis begun" in line: mode = None
            
            if mode == "NODE_DEPTH" and len(line.split()) >= 4 and not line.startswith("  ---"):
                parts = line.split()
                if parts[0] != "Node" and parts[0] != "Name":
                    try:
                        nid = parts[0]
                        max_depth = float(parts[2])
                        node_depths_rpt[nid] = max_depth
                    except ValueError: pass
                    
            if mode == "LINK_FLOW" and len(line.split()) >= 6 and not line.startswith("  ---"):
                parts = line.split()
                if parts[0] != "Link" and parts[0] != "Name":
                    try:
                        lid = parts[0]
                        max_full_depth = float(parts[5])
                        link_flows_rpt[lid] = max_full_depth
                        if max_full_depth > max_trunk_dd:
                            max_trunk_dd = max_full_depth
                            trunk_id = lid
                    except ValueError: pass
                    
        print(f"Trunk Conduit (max d/D): {trunk_id} with Max/Full Depth = {max_trunk_dd}")
        
        print("\n=== C. RUN_SIMULATION COMPARISON ===")
        res = run_simulation(inp_text)
        depths = res["depths"]
        node_ids = res["node_ids"]
        
        print(f"depths.shape = {depths.shape}")
        print(f"Number of timesteps = {depths.shape[0]}")
        print(f"First row (t=0) non-zero count = {np.sum(depths[0] > 0)}")
        print(f"Last row non-zero count = {np.sum(depths[-1] > 0)}")
        
        max_diff = 0.0
        worst_node = ""
        
        print(f"\nNode | run_simulation Max Depth | RPT Max Depth | Diff")
        for idx, nid in enumerate(node_ids):
            run_max = np.max(depths[:, idx])
            rpt_max = node_depths_rpt.get(nid, 0.0)
            diff = abs(run_max - rpt_max)
            print(f"{nid:<15} {run_max:.<20.4f} {rpt_max:.<15.4f} {diff:.4f}")
            if diff > max_diff:
                max_diff = diff
                worst_node = nid
        
        print(f"\nLargest absolute difference: {max_diff:.6f} at node {worst_node}")
            
    finally:
        if os.path.exists(inp_path): os.remove(inp_path)
        if os.path.exists(rpt_path): os.remove(rpt_path)

if __name__ == "__main__":
    main()
