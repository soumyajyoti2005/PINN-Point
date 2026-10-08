import os
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from app.sim.make_swmm_inp import build_inp_text

def get_conduit_xsection(inp_text, pid):
    lines = inp_text.splitlines()
    conduit_line = None
    xsection_line = None
    in_conduits = False
    in_xsections = False
    for line in lines:
        if line.startswith("[CONDUITS]"):
            in_conduits = True
            in_xsections = False
            continue
        if line.startswith("[XSECTIONS]"):
            in_xsections = True
            in_conduits = False
            continue
        if line.startswith("["):
            in_conduits = False
            in_xsections = False
            
        if in_conduits and line.startswith(f"{pid:<16}"):
            conduit_line = line
        if in_xsections and line.startswith(f"{pid:<16}"):
            xsection_line = line
            
    return conduit_line, xsection_line

def main():
    data_dir = os.getenv("DATA_DIR", "/data")
    ds_dir = os.path.join(data_dir, "datasets", "sample")
    net_path = os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")
    
    with open(net_path, "r") as f:
        network = json.load(f)
        
    pipes = {p["id"]: p for p in network.get("pipes", [])}
    nodes = {n["id"]: n for n in network.get("nodes", [])}
    
    from_nodes = {p["from_node"] for p in pipes.values()}
    to_nodes = {p["to_node"] for p in pipes.values()}
    
    print("1a. Diagnostic definition of leaf pipe and upstream node:")
    print("  is_leaf = up_node not in to_nodes")
    print("  up_node = pipe['from_node']")
    
    df = pq.read_table(os.path.join(ds_dir, "manifest.parquet")).to_pandas()
    blocks = df[(~df['is_baseline']) if 'is_baseline' in df.columns else (df['severity'] > 0)]
    
    leaf_sev9 = []
    for idx, row in blocks.iterrows():
        if row["severity"] != 0.9: continue
        pid = row["blocked_pipe_id"]
        up_node = pipes[pid]["from_node"]
        if up_node not in to_nodes:
            leaf_sev9.append(row)
            if len(leaf_sev9) == 3: break
            
    node_ids_sorted = sorted(list(nodes.keys()))
    
    print("\n1b & 1c. Picked 3 leaf-pipe runs at severity 0.9:")
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100, 'SWMM_PONDED_AREA_M2': 100}
    
    for row in leaf_sev9:
        b_id = row["run_id"]
        s_id = row["storm_id"]
        pid = row["blocked_pipe_id"]
        pipe = pipes[pid]
        up_node = pipe["from_node"]
        
        print(f"\nRun: {b_id} | Pipe: {pid} | {up_node} -> {pipe['to_node']}")
        
        # Build INPs
        base_inp = build_inp_text(network, [(0,0)], settings, pipe_diam_overrides=None, duration_minutes=120)
        overrides = {pid: pipe["diameter_m"] * (1.0 - 0.9)}
        block_inp = build_inp_text(network, [(0,0)], settings, pipe_diam_overrides=overrides, duration_minutes=120)
        
        bc, bx = get_conduit_xsection(base_inp, pid)
        kc, kx = get_conduit_xsection(block_inp, pid)
        print(f"  Base INP: {bc}")
        print(f"            {bx}")
        print(f"  Blck INP: {kc}")
        print(f"            {kx}")
        
        base_npz = np.load(os.path.join(ds_dir, f"{s_id}_base.npz"))
        block_npz = np.load(os.path.join(ds_dir, f"{b_id}.npz"))
        
        up_idx = list(base_npz['node_ids']).index(up_node)
        base_depth = np.max(base_npz["clean"][:, up_idx])
        block_depth = np.max(block_npz["clean"][:, up_idx])
        print(f"  Peak depth at {up_node}: Base = {base_depth:.4f} m | Blocked = {block_depth:.4f} m")
        
        n_data = nodes[up_node]
        print(f"  Junction: max depth = {n_data['depth_m']} m, SWMM_PONDED_AREA_M2 = 100, Area = 0 (except ponded)")
        
        # Calculate water balance
        peak_intensity = row["peak_mm_hr"]
        catch_area_ha = settings['SWMM_CATCHMENT_HA_PER_NODE']
        imperv = settings['SWMM_IMPERVIOUS_PCT']
        
        # Runoff (Q = C*I*A / 360). Assuming 100% impervious -> C=1. 
        # m3/s = (mm/hr) * (ha) * 10,000 / 3,600,000 = (mm/hr) * ha / 360
        runoff_m3s = (peak_intensity * catch_area_ha) / 360
        
        # Manning's capacity for blocked pipe (full pipe)
        diam = overrides[pid]
        n = pipe["manning_n"]
        s = 0.01 # Assume 1% slope if unknown, or calculate from network
        # For simplicity, calculate approx capacity: Q = (1/n) * A * R^(2/3) * S^(1/2)
        # We don't have slope easily, but let's just print runoff in L/s
        
        runoff_Lps = runoff_m3s * 1000
        print(f"  Catchment Peak Inflow (approx): {runoff_Lps:.2f} L/s (at {peak_intensity:.1f} mm/hr)")
        # Blocked capacity estimate:
        A = np.pi * (diam/2)**2
        print(f"  Blocked Pipe full Area: {A:.4f} m2. (If v ~ 1 m/s, capacity ~ {A*1000:.1f} L/s)")

    print("\n2. Severity Assignment:")
    print("  Rule in generate_dataset.py: For each block run k=0,1,2, it selects: sev = run_rng.choice([0.3, 0.6, 0.9])")
    print("  It also selects pid = run_rng.choice(network['pipes']) independently.")
    pipe_counts = blocks["blocked_pipe_id"].value_counts()
    print(f"  Pipes with 0 blockage runs: {len(pipes) - len(pipe_counts)}")
    # Just print some stats on pipe_counts
    print("  Per-pipe blockage count summary:")
    print(pipe_counts.describe())
    
    print("\n3. Continuity and Flooding:")
    print("Routing Error %:")
    print(blocks["routing_err_pct"].describe(percentiles=[0.5, 0.95]))
    print("Runoff Error %:")
    print(blocks["runoff_err_pct"].describe(percentiles=[0.5, 0.95]))
    flood_runs = (blocks["flood_volume_m3"] > 0).sum()
    max_flood = blocks["flood_volume_m3"].max()
    print(f"Runs with flooding > 0: {flood_runs}")
    print(f"Max flooding volume: {max_flood:.2f} m3")
    print("Flagged threshold in code: flagged = (runoff_err_pct > 5.0) or (routing_err_pct > 5.0)")
    
    print("\n5. Observed-level check (using sensor_nodes from manifest):")
    for sev in [0.6, 0.9]:
        print(f" Severity {sev}:")
        sev_df = blocks[blocks["severity"] == sev]
        for sf in [1.0, 0.5, 0.3]:
            sf_df = sev_df[sev_df["sensor_fraction"] == sf]
            if len(sf_df) == 0: continue
            
            # The mask is randomly selected per run. We can estimate it or deduce it.
            # actually, using sensor_nodes in the manifest gives the NUMBER of sensors, but not WHICH ones.
            # But earlier we used the npz file at t=0. We'll use the same here.
            up_has_count = 0
            neither_has_count = 0
            
            for _, r in sf_df.iterrows():
                b_id = r["run_id"]
                obs = np.load(os.path.join(ds_dir, f"{b_id}.npz"))["observed"]
                mask = ~np.all(np.isnan(obs), axis=0)
                
                pid = r["blocked_pipe_id"]
                pipe = pipes[pid]
                up_node = pipe["from_node"]
                down_node = pipe["to_node"]
                
                up_idx = list(base_npz['node_ids']).index(up_node)
                down_idx = node_ids_sorted.index(down_node)
                
                up_has = mask[up_idx]
                down_has = mask[down_idx]
                
                if up_has: up_has_count += 1
                if not up_has and not down_has: neither_has_count += 1
                
            print(f"  Sensor fraction {sf}:")
            print(f"    Upstream node has sensor: {up_has_count / len(sf_df) * 100:.1f}%")
            print(f"    Neither end has sensor: {neither_has_count / len(sf_df) * 100:.1f}%")

if __name__ == "__main__":
    main()
