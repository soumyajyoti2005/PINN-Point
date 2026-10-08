import os
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

def run_diagnostic():
    data_dir = os.getenv("DATA_DIR", "/data")
    dataset_name = os.getenv("DATASET_NAME", "sample")
    out_dir = os.path.join(data_dir, "datasets", dataset_name)
    
    man = pq.read_table(os.path.join(out_dir, "manifest.parquet")).to_pandas()
    
    with open(f"{data_dir}/swmm/kolkata-amherst_network.json") as f:
        network = json.load(f)
        
    pipe_dict = {p["id"]: p for p in network["pipes"]}
    
    # Preload baselines
    baselines = {}
    
    base_df = man[man["severity"] == 0.0] if "severity" in man.columns else man[man["is_baseline"]]
    for _, row in base_df.iterrows():
        b_id = row["run_id"]
        s_id = row["storm_id"]
        
        npz = np.load(os.path.join(out_dir, f"{b_id}.npz"))
        baselines[s_id] = {
            "clean": npz["clean"],
            "node_ids": list(npz["node_ids"])
        }
        
    print(f"DETECTABILITY DIAGNOSTIC ({dataset_name})")
    print("Note: Previous tables were invalid due to an array indexing bug (node IDs were mapped alphabetically instead of using NPZ node_ids).")
    
    # Identify leaf pipes (no other pipe has to_node == this pipe's from_node)
    to_nodes = {p["to_node"] for p in pipe_dict.values()}
    
    blocks = man[man["severity"] > 0.0] if "severity" in man.columns else man[~man["is_baseline"]]
    
    results = []
    
    for _, row in blocks.iterrows():
        b_id = row["run_id"]
        s_id = row["storm_id"]
        sev = row["severity"]
        pid = row["blocked_pipe_id"]
        
        base_data = baselines[s_id]
        base_clean = base_data["clean"]
        base_node_ids = base_data["node_ids"]
        
        try:
            block_npz = np.load(os.path.join(out_dir, f"{b_id}.npz"))
        except:
            continue
            
        block_clean = block_npz["clean"]
        
        pipe = pipe_dict[pid]
        up_node = pipe["from_node"]
        down_node = pipe["to_node"]
        diam = pipe["diameter_m"]
        
        # Use node_ids from NPZ to find the correct index!
        up_idx = base_node_ids.index(up_node)
        down_idx = base_node_ids.index(down_node)
        
        min_len = min(len(block_clean), len(base_clean))
        
        b_up = base_clean[:min_len, up_idx]
        blk_up = block_clean[:min_len, up_idx]
        
        b_down = base_clean[:min_len, down_idx]
        blk_down = block_clean[:min_len, down_idx]
        
        up_diff = np.max(blk_up - b_up)
        down_diff = np.min(blk_down - b_down)
        
        peak_depth = np.max(b_up)
        peak_dd = peak_depth / diam
        is_leaf = up_node not in to_nodes
        
        results.append({
            "run_id": b_id,
            "severity": sev,
            "peak_dd": peak_dd,
            "is_leaf": is_leaf,
            "up_diff": up_diff,
            "down_diff": down_diff
        })

    res_df = pd.DataFrame(results)
    if len(res_df) == 0:
        print("No valid blockage runs found.")
        return
        
    bins = [-float('inf'), 0.2, 0.4, 0.6, float('inf')]
    labels = ["<0.2", "0.2-0.4", "0.4-0.6", ">0.6"]
    res_df["dd_bin"] = pd.cut(res_df["peak_dd"], bins=bins, labels=labels)
    
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
                
                print(f"  {leaf_str:<15} | Base d/D {b:<8} | Runs: {len(group):<3} | >3cm: {gt_3:>5.1f}% | >5cm: {gt_5:>5.1f}% | Mean Up: {group['up_diff'].mean():.4f} m | Mean Down: {group['down_diff'].mean():.4f} m")

if __name__ == "__main__":
    run_diagnostic()
