"""
build_network.py

Pipe diameter rules based on number of upstream nodes n:
- n < 8: 0.30 m
- n < 20: 0.45 m
- otherwise: 0.60 m
"""
import os
import sys
import json
import math
import argparse
from app.sim.area import Area
from app.sim.osm_fetch import fetch_roads

def prepare_graph(G_multi):
    import networkx as nx
    orig_nodes = len(G_multi.nodes)
    orig_edges = len(G_multi.edges)
    
    G_un = G_multi.to_undirected()
    self_loops = list(nx.selfloop_edges(G_un))
    G_un.remove_edges_from(self_loops)
    
    G = nx.Graph()
    G.add_nodes_from(G_un.nodes(data=True))
    for u, v, k, data in G_un.edges(keys=True, data=True):
        if G.has_edge(u, v):
            if data.get('length', float('inf')) < G[u][v].get('length', float('inf')):
                G[u][v].update(data)
        else:
            G.add_edge(u, v, **data)
            
    if len(G) > 0:
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        
    print(f"Graph simplified: removed {orig_nodes - len(G.nodes)} nodes, {orig_edges - len(G.edges)} edges")
    return G

def smooth_grounds(G):
    for _ in range(3):
        new_clean = {}
        for n in G.nodes:
            # Undirected neighbors
            neighbors = list(G.neighbors(n))
            vals = [G.nodes[x]['ground_clean_m'] for x in neighbors + [n]]
            new_clean[n] = sum(vals) / len(vals)
        for n in G.nodes:
            G.nodes[n]['ground_clean_m'] = new_clean[n]
            
    for n in G.nodes:
        G.nodes[n]['ground_elevation_m'] = G.nodes[n]['ground_clean_m']

def select_outfall_pure(nodes_data):
    best_n = None
    best_z = float('inf')
    for n, data in nodes_data.items():
        if data.get('is_boundary'):
            if data['ground'] < best_z:
                best_z = data['ground']
                best_n = n
    return best_n

def build_tree(G, outfall):
    import networkx as nx
    paths = nx.single_source_dijkstra_path(G, outfall, weight='length')
    tree = nx.DiGraph()
    for n in G.nodes:
        tree.add_node(n, **G.nodes[n])
        
    for n, path in paths.items():
        if len(path) > 1:
            parent = path[-2]
            edge_data = G.get_edge_data(n, parent).copy()
            tree.add_edge(n, parent, **edge_data)
            
    tree = tree.subgraph(paths.keys()).copy()
    return tree

def insert_manholes(tree, max_spacing):
    import networkx as nx
    from shapely.geometry import LineString
    
    new_tree = nx.DiGraph()
    for n in tree.nodes:
        new_tree.add_node(n, **tree.nodes[n])
        
    for u, v, data in tree.edges(data=True):
        length = data.get('length', 0.0)
        if length <= max_spacing:
            new_tree.add_edge(u, v, **data)
            continue
            
        splits = math.ceil(length / max_spacing)
        segment_len = length / splits
        
        if 'geometry' in data:
            line = data['geometry']
        else:
            line = LineString([(tree.nodes[u]['x'], tree.nodes[u]['y']), 
                               (tree.nodes[v]['x'], tree.nodes[v]['y'])])
                               
        curr = u
        for i in range(1, splits):
            dist = i * segment_len / length * line.length
            pt = line.interpolate(dist)
            mid_id = f"mid_{u}_{v}_{i}"
            new_tree.add_node(mid_id, x=pt.x, y=pt.y)
            # Inherit ground if possible, though tests provide grounds via get_ground
            # For pure core, we just don't set ground_elevation_m yet
            new_tree.add_edge(curr, mid_id, length=segment_len)
            curr = mid_id
        new_tree.add_edge(curr, v, length=segment_len)
        
    return new_tree

def compute_inverts(tree, outfall, cover, min_slope):
    import networkx as nx
    
    rev_tree = tree.reverse()
    order = list(nx.topological_sort(rev_tree))
    
    tree.nodes[outfall]['invert_elevation_m'] = tree.nodes[outfall]['ground_elevation_m'] - cover
    
    adj_count = 0
    max_adj = 0.0
    
    for n in order:
        if n == outfall:
            continue
            
        parents = list(tree.successors(n))
        if not parents:
            continue
        parent = parents[0]
        length = tree[n][parent]['length']
        parent_invert = tree.nodes[parent]['invert_elevation_m']
        
        req_invert = parent_invert + min_slope * length
        ground = tree.nodes[n]['ground_elevation_m']
        
        invert = max(ground - cover, req_invert)
        tree.nodes[n]['invert_elevation_m'] = invert
        
        if invert > ground - 0.6:
            new_ground = invert + 0.6
            adj = new_ground - ground
            tree.nodes[n]['ground_elevation_m'] = new_ground
            tree.nodes[n]['ground_adjusted_m'] = new_ground
            adj_count += 1
            max_adj = max(max_adj, adj)
            
    return adj_count, max_adj

def compute_pipes(tree):
    import networkx as nx
    rev_tree = tree.reverse()
    for n in rev_tree.nodes:
        tree.nodes[n]['upstream_nodes'] = len(nx.descendants(rev_tree, n))
        
    for u, v, data in tree.edges(data=True):
        length = data['length']
        inv_u = tree.nodes[u]['invert_elevation_m']
        inv_v = tree.nodes[v]['invert_elevation_m']
        
        slope = (inv_u - inv_v) / length if length > 0 else 0.0
        data['slope'] = max(slope, 0.001)
        data['manning_n'] = 0.013
        
        n_up = tree.nodes[u]['upstream_nodes']
        if n_up < 8:
            data['diameter_m'] = 0.30
        elif n_up < 20:
            data['diameter_m'] = 0.45
        else:
            data['diameter_m'] = 0.60

def assign_ids(tree, outfall):
    import networkx as nx
    rev_tree = tree.reverse()
    dfs_nodes = list(nx.dfs_preorder_nodes(rev_tree, source=outfall))
    
    node_mapping = {}
    for i, n in enumerate(dfs_nodes):
        node_mapping[n] = f"MH-{i+1:03d}"
        
    tree = nx.relabel_nodes(tree, node_mapping)
    
    for u, v, data in tree.edges(data=True):
        num_u = u.split('-')[1]
        num_v = v.split('-')[1]
        data['id'] = f"P-{num_u}-{num_v}"
        
    return tree, node_mapping[outfall]

def build_network_core(G_multi, outfall_node, max_spacing, cover, min_slope, get_ground, seed, is_boundary=None):
    import networkx as nx
    import random
    random.seed(seed)
    
    G = prepare_graph(G_multi)
    
    # 1. Fetch grounds
    for n, data in G.nodes(data=True):
        raw, clean = get_ground(data['x'], data['y'], n)
        data['ground_raw_m'] = raw
        data['ground_clean_m'] = clean
        
    # 2. Smooth grounds on undirected graph
    smooth_grounds(G)
    
    # 3. Select outfall if not provided
    if outfall_node is None:
        nodes_data = {}
        for n in G.nodes:
            nodes_data[n] = {
                'is_boundary': is_boundary(n, G.nodes[n]['x'], G.nodes[n]['y']) if is_boundary else True,
                'ground': G.nodes[n]['ground_elevation_m']
            }
        best_n = select_outfall_pure(nodes_data)
        if best_n is None:
            best_n = list(G.nodes)[0]
        outfall_node = best_n
        
    # 4. Build tree
    tree = build_tree(G, outfall_node)
    
    # 5. Insert manholes
    tree = insert_manholes(tree, max_spacing)
    
    # 6. Fetch grounds for new manholes
    for n, data in tree.nodes(data=True):
        if 'ground_elevation_m' not in data:
            raw, clean = get_ground(data['x'], data['y'], n)
            data['ground_raw_m'] = raw
            data['ground_elevation_m'] = clean
            
    # 7. Compute inverts, pipes, IDs
    adj_count, max_adj = compute_inverts(tree, outfall_node, cover, min_slope)
    compute_pipes(tree)
    tree, outfall_id = assign_ids(tree, outfall_node)
    
    return tree, outfall_id, adj_count, max_adj

def generate_outputs(tree, outfall_id, area, args, source, data_dir):
    nodes_out = []
    for n, data in tree.nodes(data=True):
        d = {
            "id": n,
            "lon": data['x'],
            "lat": data['y'],
            "ground_elevation_m": round(data['ground_elevation_m'], 3),
            "invert_elevation_m": round(data.get('invert_elevation_m', 0.0), 3),
            "depth_m": round(data['ground_elevation_m'] - data.get('invert_elevation_m', 0.0), 3),
            "has_sensor": True,
            "is_outfall": n == outfall_id
        }
        if 'ground_adjusted_m' in data:
            d['ground_adjusted_m'] = round(data['ground_adjusted_m'], 3)
        if data.get('ground_raw_m') is not None:
            d['ground_raw_m'] = round(data['ground_raw_m'], 3)
        nodes_out.append(d)
        
    pipes_out = []
    total_length = 0.0
    for u, v, data in tree.edges(data=True):
        total_length += data['length']
        if 'geometry' in data:
            coords = list(data['geometry'].coords)
            start_coord = coords[0]
            end_coord = coords[-1]
            u_x, u_y = tree.nodes[u]['x'], tree.nodes[u]['y']
            d_start = (start_coord[0] - u_x)**2 + (start_coord[1] - u_y)**2
            d_end = (end_coord[0] - u_x)**2 + (end_coord[1] - u_y)**2
            if d_end < d_start:
                coords.reverse()
        else:
            coords = [[tree.nodes[u]['x'], tree.nodes[u]['y']], [tree.nodes[v]['x'], tree.nodes[v]['y']]]
            
        pipes_out.append({
            "id": data['id'],
            "from_node": u,
            "to_node": v,
            "length_m": round(data['length'], 3),
            "diameter_m": round(data['diameter_m'], 3),
            "slope": round(data['slope'], 5),
            "manning_n": data['manning_n'],
            "coords": coords
        })
        
    out = {
        "area": {
            "name": area.name,
            "bbox": area.bbox(),
            "center": [area.center_lon, area.center_lat]
        },
        "params": vars(args),
        "elevation_source": source,
        "synthetic": True,
        "note": "drain network is synthetic along OSM roads and is not the real Kolkata drainage",
        "nodes": nodes_out,
        "pipes": pipes_out,
        "summary": {
            "nodes": len(nodes_out),
            "pipes": len(pipes_out),
            "total_length_m": total_length
        }
    }
    
    os.makedirs(os.path.join(data_dir, "swmm"), exist_ok=True)
    json_path = os.path.join(data_dir, "swmm", f"{area.name}_network.json")
    with open(json_path, 'w') as f:
        json.dump(out, f, indent=2)
        
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    for p in pipes_out:
        geojson['features'].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": p['coords']},
            "properties": {"id": p['id'], "diameter_m": p['diameter_m']}
        })
    with open(os.path.join(data_dir, "swmm", f"{area.name}_network.geojson"), 'w') as f:
        json.dump(geojson, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfall-lat", type=float)
    parser.add_argument("--outfall-lon", type=float)
    parser.add_argument("--max-spacing", type=float, default=100.0)
    parser.add_argument("--cover", type=float, default=1.5)
    parser.add_argument("--min-slope", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    area = Area.from_env()
    G_multi, *_ = fetch_roads(area)
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    from app.sim.dem import find_dem, sample_dem, robust_ground
    dem_path = find_dem(data_dir)
    
    import networkx as nx
    import numpy as np
    import osmnx as ox
    
    outfall_node = None
    if args.outfall_lat is not None and args.outfall_lon is not None:
        import networkx as nx
        # Temporarily simplify just to find nearest node, pure core will do it again but it's fast
        G_temp = prepare_graph(G_multi)
        outfall_node = ox.distance.nearest_nodes(G_temp, args.outfall_lon, args.outfall_lat)
        print(f"Outfall nearest to coords: {outfall_node}")
        
    south, west, north, east = area.bbox()
    def is_boundary(n, x, y):
        d_south = abs(y - south) * 111320
        d_north = abs(north - y) * 111320
        d_west = abs(x - west) * 111320 * math.cos(math.radians(y))
        d_east = abs(east - x) * 111320 * math.cos(math.radians(y))
        return min(d_south, d_north, d_west, d_east) <= 30.0

    if dem_path:
        source = "copernicus_glo30_dsm_p10_smoothed"
        def get_ground(x, y, n):
            r = sample_dem(dem_path, [(x, y)])[0]
            c = robust_ground(dem_path, [(x, y)], radius_px=1, percentile=10)[0]
            c = c if not np.isnan(c) else (r if not np.isnan(r) else 0.0)
            return r, c
    else:
        source = "synthetic"
        # Since we need lengths from outfall before it's chosen... wait.
        # If synthetic and no outfall given, we should pick closest to SW corner.
        if outfall_node is None:
            G_temp = prepare_graph(G_multi)
            best_n, best_d = None, float('inf')
            for n in G_temp.nodes:
                if is_boundary(n, G_temp.nodes[n]['x'], G_temp.nodes[n]['y']):
                    d = math.hypot(G_temp.nodes[n]['y'] - south, (G_temp.nodes[n]['x'] - west) * math.cos(math.radians(G_temp.nodes[n]['y'])))
                    if d < best_d:
                        best_d, best_n = d, n
            outfall_node = best_n
            print(f"Outfall closest to SW boundary: {outfall_node}")
            
        tree_temp = build_tree(prepare_graph(G_multi), outfall_node)
        lengths = nx.shortest_path_length(tree_temp, target=outfall_node, weight='length')
        def get_ground(x, y, n):
            dist = lengths.get(n, 100.0)
            return None, 5.0 + 0.002 * dist

    tree, outfall_id, adj_count, max_adj = build_network_core(
        G_multi, outfall_node, args.max_spacing, args.cover, args.min_slope, get_ground, args.seed, is_boundary
    )
    
    generate_outputs(tree, outfall_id, area, args, source, data_dir)
    
    print(f"Nodes: {len(tree.nodes)}, Pipes: {len(tree.edges)}")
    total_len = sum(d['length'] for u, v, d in tree.edges(data=True))
    print(f"Total pipe length: {total_len:.2f} m")
    print(f"Elevation source: {source}")
    
    raw = [d.get('ground_raw_m') for n, d in tree.nodes(data=True) if d.get('ground_raw_m') is not None]
    clean = [d.get('ground_elevation_m') for n, d in tree.nodes(data=True)]
    if raw:
        print(f"Raw relief: {min(raw):.2f} to {max(raw):.2f} m")
    print(f"Cleaned relief: {min(clean):.2f} to {max(clean):.2f} m")
    
    print(f"Adjustments: {adj_count}, max {max_adj:.2f} m")
    print(f"Outfall: {outfall_id} at {tree.nodes[outfall_id]['y']:.5f}, {tree.nodes[outfall_id]['x']:.5f} (ground: {tree.nodes[outfall_id]['ground_elevation_m']:.3f} m)")
    
    rev = tree.reverse()
    lens = nx.single_source_dijkstra_path_length(rev, outfall_id, weight='length')
    print(f"Longest upstream path: {max(lens.values()):.2f} m")
    
    dia = [d['diameter_m'] for u, v, d in tree.edges(data=True)]
    print(f"Diameter histogram: 0.30: {dia.count(0.30)}, 0.45: {dia.count(0.45)}, 0.60: {dia.count(0.60)}")
