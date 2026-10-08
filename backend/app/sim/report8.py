import os
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

def main():
    data_dir = os.getenv("DATA_DIR", "/data")
    ds_dir = os.path.join(data_dir, "datasets", "sample")
    net_path = os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")
    
    with open(net_path, "r") as f:
        network = json.load(f)
        
    pipes = {p["id"]: p for p in network.get("pipes", [])}
    nodes = {n["id"]: n for n in network.get("nodes", [])}
    
    # Identify leaf pipes (no other pipe has to_node == this pipe's from_node)
    from_nodes = {p["from_node"] for p in pipes.values()}
    to_nodes = {p["to_node"] for p in pipes.values()}
    
    manifest_path = os.path.join(ds_dir, "manifest.parquet")
    df = pq.read_table(manifest_path).to_pandas()
    
    print("=== 2. DATASET RUNS AND TOTALS ===")
    print("DATASET_RUNS controls the number of baseline storms generated per batch (which runs in parallel).")
    print("Each baseline storm produces 1 baseline run + 3 blockage runs (for 0.3, 0.6, 0.9 severities) = 4 runs per storm.")
    print(f"Total storms in sample: {df['storm_id'].nunique()}")
    print(f"Total runs in sample: {len(df)}")
    # size on disk
    total_size = sum(os.path.getsize(os.path.join(dirpath, f)) for dirpath, _, fnames in os.walk(ds_dir) for f in fnames)
    print(f"Total size on disk: {total_size / 1e6:.2f} MB")
    
    print("\n=== 3. MANIFEST SUMMARY ===")
    print("Splits (counts):")
    print(df["split"].value_counts())
    print("\nSeverities (counts):")
    print(df["severity"].value_counts())
    print("\nSensor Fractions (counts):")
    print(df["sensor_fraction"].value_counts(dropna=False))
    print(f"\nBaseline runs: {len(df[df['severity'] == 0.0])}")
    print(f"Blockage runs: {len(df[df['severity'] > 0.0])}")
    print(f"Flagged runs: {df['flagged'].sum()}")
    print(f"Failed runs: {(df['status'] == 'failed').sum()}")
    print(f"Held out pipes: {df[df['split'] == 'test_unseen_pipe']['blocked_pipe_id'].nunique()}")
    print("Held out pipes list:", df[df['split'] == 'test_unseen_pipe']['blocked_pipe_id'].dropna().unique().tolist())
    
    print("\n=== 4. DETECTABILITY BY LOCATION ===")
    # load numpy arrays for all base/block pairs
    # we need the peak d/D of the blocked pipe in the BASELINE run.
    # to do that, we need the max depth of its upstream node in the BASELINE run, divided by diameter.
    
    node_ids_sorted = sorted(list(nodes.keys()))
    
    results = []
    
    baselines = df[df['severity'] == 0.0]
    blocks = df[df['severity'] > 0.0]
    
    for idx, row in blocks.iterrows():
        b_id = row["run_id"]
        s_id = row["storm_id"]
        sev = row["severity"]
        p_id = row["blocked_pipe_id"]
        
        base_row = baselines[baselines["storm_id"] == s_id].iloc[0]
        base_id = base_row["run_id"]
        
        base_npz = np.load(os.path.join(ds_dir, f"{base_id}.npz"))
        block_npz = np.load(os.path.join(ds_dir, f"{b_id}.npz"))
        
        base_clean = base_npz["clean"]
        block_clean = block_npz["clean"]
        
        min_len = min(len(block_clean), len(base_clean))
        
        pipe = pipes[p_id]
        up_node = pipe["from_node"]
        diam = pipe["diameter_m"]
        
        up_idx = node_ids_sorted.index(up_node)
        
        base_up_depths = base_clean[:min_len, up_idx]
        block_up_depths = block_clean[:min_len, up_idx]
        
        # upstream max diff
        up_diff = np.max(block_up_depths - base_up_depths)
        
        # baseline peak d/D
        peak_depth = np.max(base_up_depths)
        peak_dd = peak_depth / diam
        
        is_leaf = up_node not in to_nodes
        
        results.append({
            "run_id": b_id,
            "severity": sev,
            "peak_dd": peak_dd,
            "is_leaf": is_leaf,
            "up_diff": up_diff,
            "sensor_fraction": row["sensor_fraction"],
            "flagged": row["flagged"]
        })
        
    res_df = pd.DataFrame(results)
    
    # bins: <0.2, 0.2-0.4, 0.4-0.6, >0.6
    bins = [0, 0.2, 0.4, 0.6, float('inf')]
    labels = ["<0.2", "0.2-0.4", "0.4-0.6", ">0.6"]
    res_df["dd_bin"] = pd.cut(res_df["peak_dd"], bins=bins, labels=labels)
    
    print(f"Detectability includes flagged runs? {'Yes' if res_df['flagged'].any() else 'No flagged runs exist in this sample.'}")
    
    for sev in [0.3, 0.6, 0.9]:
        print(f"\nSeverity {sev}:")
        sev_df = res_df[res_df["severity"] == sev]
        
        for leaf_status in [True, False]:
            leaf_str = "Leaf pipe" if leaf_status else "Non-leaf pipe"
            for b in labels:
                group = sev_df[(sev_df["is_leaf"] == leaf_status) & (sev_df["dd_bin"] == b)]
                if len(group) == 0: continue
                
                gt_3 = (group["up_diff"] > 0.03).mean() * 100
                gt_5 = (group["up_diff"] > 0.05).mean() * 100
                
                print(f"  {leaf_str:<15} | Base d/D {b:<8} | Runs: {len(group):<3} | >3cm: {gt_3:>5.1f}% | >5cm: {gt_5:>5.1f}%")

    print("\n=== 5. OBSERVED-LEVEL CHECK ===")
    for sev in [0.6, 0.9]:
        sev_df = res_df[res_df["severity"] == sev]
        print(f"\nSeverity {sev}:")
        
        for sf in [1.0, 0.5, 0.3]:
            sf_df = sev_df[sev_df["sensor_fraction"] == sf]
            if len(sf_df) == 0: continue
            
            # check if upstream node has sensor
            # wait, the sensor placement is random per network but deterministic for the sensor fraction.
            # to check if the upstream node has a sensor, we need to load the mask!
            
            up_has_sensor_count = 0
            neither_has_sensor_count = 0
            
            for _, r in sf_df.iterrows():
                b_id = r["run_id"]
                block_npz = np.load(os.path.join(ds_dir, f"{b_id}.npz"))
                obs = block_npz["observed"]
                mask = ~np.all(np.isnan(obs), axis=0)
                
                # find pipe
                p_id = blocks[blocks["run_id"] == b_id].iloc[0]["blocked_pipe_id"]
                pipe = pipes[p_id]
                up_node = pipe["from_node"]
                down_node = pipe["to_node"]
                
                up_idx = node_ids_sorted.index(up_node)
                down_idx = node_ids_sorted.index(down_node)
                
                up_has = mask[up_idx]
                down_has = mask[down_idx]
                
                if up_has: up_has_sensor_count += 1
                if not up_has and not down_has: neither_has_sensor_count += 1
                
            print(f"  Sensor fraction {sf}:")
            print(f"    Upstream node has sensor: {up_has_sensor_count / len(sf_df) * 100:.1f}%")
            print(f"    Neither end has sensor: {neither_has_sensor_count / len(sf_df) * 100:.1f}%")

if __name__ == "__main__":
    main()
