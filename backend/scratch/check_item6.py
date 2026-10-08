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
        
    nodes = {n["id"]: n for n in network.get("nodes", [])}
    
    df = pq.read_table(os.path.join(ds_dir, "manifest.parquet")).to_pandas()
    blocks = df[df['severity'] > 0.0]
    
    runs_with_excess = 0
    max_excess_overall = 0.0
    excess_by_sev = {0.3: 0, 0.6: 0, 0.9: 0}
    
    for _, row in blocks.iterrows():
        b_id = row["run_id"]
        sev = row["severity"]
        
        block_npz = np.load(os.path.join(ds_dir, f"{b_id}.npz"))
        block_clean = block_npz["clean"]
        node_ids = list(block_npz["node_ids"])
        
        has_excess = False
        run_max_excess = 0.0
        
        for i, nid in enumerate(node_ids):
            max_depth = nodes[nid]["depth_m"]
            peak = np.max(block_clean[:, i])
            excess = peak - max_depth
            if excess > 0:
                has_excess = True
                run_max_excess = max(run_max_excess, excess)
                
        if has_excess:
            runs_with_excess += 1
            excess_by_sev[sev] += 1
            max_excess_overall = max(max_excess_overall, run_max_excess)
            
    print("Item 6. Rim saturation:")
    print(f"Runs with depth > node depth_m: {runs_with_excess} / {len(blocks)}")
    print(f"Maximum excess across all runs: {max_excess_overall:.4f} m")
    print("Share of those runs by severity:")
    for sev in [0.3, 0.6, 0.9]:
        total_sev = len(blocks[blocks['severity'] == sev])
        share = (excess_by_sev[sev] / runs_with_excess) * 100 if runs_with_excess > 0 else 0
        print(f"  Severity {sev}: {excess_by_sev[sev]} runs ({share:.1f}% of the {runs_with_excess} saturated runs)")

if __name__ == "__main__":
    main()
