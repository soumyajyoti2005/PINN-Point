import os
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

def main():
    data_dir = "/data"
    ds_dir = os.path.join(data_dir, "datasets", "sample")
    net_path = os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")
    
    with open(net_path, "r") as f:
        network = json.load(f)
        
    pipes = {p["id"]: p for p in network.get("pipes", [])}
    
    # build adjacency for 1-hop
    neighbors = {n["id"]: set() for n in network.get("nodes", [])}
    for p in pipes.values():
        u, v = p["from_node"], p["to_node"]
        neighbors[u].add(v)
        neighbors[v].add(u)
    
    df = pq.read_table(os.path.join(ds_dir, "manifest.parquet")).to_pandas()
    baselines = df[df['severity'] == 0.0]
    blocks = df[df['severity'] > 0.0]
    
    equal_count = 0
    one_hop_count = 0
    neither = []
    
    for _, row in blocks.iterrows():
        b_id = row["run_id"]
        s_id = row["storm_id"]
        pid = row["blocked_pipe_id"]
        
        base_row = baselines[baselines["storm_id"] == s_id].iloc[0]
        base_id = base_row["run_id"]
        
        base_npz = np.load(os.path.join(ds_dir, f"{base_id}.npz"))
        block_npz = np.load(os.path.join(ds_dir, f"{b_id}.npz"))
        
        base_clean = base_npz["clean"]
        block_clean = block_npz["clean"]
        node_ids = list(block_npz["node_ids"])
        
        min_len = min(len(block_clean), len(base_clean))
        
        # max diff per node over time
        diffs = block_clean[:min_len] - base_clean[:min_len]
        max_diff_per_node = np.max(diffs, axis=0)
        
        argmax_idx = np.argmax(max_diff_per_node)
        max_node_id = node_ids[argmax_idx]
        
        up_node = pipes[pid]["from_node"]
        down_node = pipes[pid]["to_node"]
        
        if max_node_id == up_node:
            equal_count += 1
        elif max_node_id == down_node or max_node_id in neighbors[up_node] or max_node_id in neighbors[down_node]:
            one_hop_count += 1
        else:
            neither.append(f"Run: {b_id}, Pipe: {pid} ({up_node}->{down_node}), Sev: {row['severity']}, MaxNode: {max_node_id} (Diff: {max_diff_per_node[argmax_idx]:.4f})")
            
    total = len(blocks)
    print(f"Total runs: {total}")
    print(f"Fraction == from_node: {equal_count / total * 100:.2f}%")
    print(f"Fraction within 1 hop (not from_node): {one_hop_count / total * 100:.2f}%")
    print(f"Total within 1 hop or exact: {(equal_count + one_hop_count) / total * 100:.2f}%")
    
    print("\nNeither:")
    for n in neither:
        print(n)

if __name__ == "__main__":
    main()
