import os
import numpy as np
import pyarrow.parquet as pq
import networkx as nx
import json

def get_network_graph(data_dir):
    with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
        network = json.load(f)
    G = nx.Graph() # undirected for hop distance
    for n in network.get("nodes", []):
        G.add_node(n["id"])
    for p in network.get("pipes", []):
        G.add_edge(p["from_node"], p["to_node"], id=p["id"])
    return G

def main():
    print("=== PART B6: Residual Decay ===")
    data_dir = os.environ.get("DATA_DIR", "/data")
    dataset_dir = os.path.join(data_dir, "datasets", "large1000")
    
    manifest_path = os.path.join(dataset_dir, 'manifest.parquet')
    manifest = pq.read_table(manifest_path).to_pandas()
    
    # Get 90 severity=0.3 test runs
    runs = manifest[(manifest['split'] == 'test') & (np.abs(manifest['severity'] - 0.3) < 0.01)]
    print(f"Found {len(runs)} severity=0.3 test runs.")
    
    G = get_network_graph(data_dir)
    
    hops_data = {0: [], 1: [], 2: [], 3: []} # 3 means 3+
    
    for _, row in runs.iterrows():
        run_id = row['run_id']
        npz_path = os.path.join(dataset_dir, f"{run_id}.npz")
        data = np.load(npz_path)
        
        obs = data['observed']
        clean = data['clean']
        res = obs - clean
        node_ids = data['node_ids']
        
        blocked_pipe = row['blocked_pipe_id']
        # Find the upstream node of the blocked pipe
        # The prompt says: "sensors 0 hops away (upstream of the blockage)"
        # So hop 0 is specifically the upstream node.
        # But wait, networkx Graph is undirected. Let's find the edge.
        with open(os.path.join(data_dir, "swmm", "kolkata-amherst_network.json")) as f:
            network = json.load(f)
            
        up_node = None
        for p in network.get("pipes", []):
            if p["id"] == blocked_pipe:
                up_node = p["from_node"]
                break
                
        if up_node is None:
            continue
            
        # compute shortest path length from up_node to all other nodes
        lengths = nx.single_source_shortest_path_length(G, up_node)
        
        max_abs_res = np.max(np.abs(res), axis=0) # shape: (nodes,)
        
        for idx, nid in enumerate(node_ids):
            if np.isnan(max_abs_res[idx]):
                continue
                
            hop = lengths.get(nid, 999)
            if hop >= 3: hop = 3
            if hop in hops_data:
                hops_data[hop].append(max_abs_res[idx])
                
    for hop in [0, 1, 2, 3]:
        vals = hops_data[hop]
        if len(vals) > 0:
            mean_val = np.mean(vals)
            label = "3+" if hop == 3 else str(hop)
            print(f"Hop {label}: {mean_val:.4f} m (N={len(vals)})")

if __name__ == "__main__":
    main()
