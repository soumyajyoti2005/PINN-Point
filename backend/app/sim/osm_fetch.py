import os
import argparse
from app.sim.area import Area

def fetch_roads(area: Area, refresh: bool = False):
    import osmnx as ox
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    osm_dir = os.path.join(data_dir, "osm")
    os.makedirs(osm_dir, exist_ok=True)
    
    graphml_path = os.path.join(osm_dir, f"{area.name}_roads.graphml")
    geojson_path = os.path.join(osm_dir, f"{area.name}_roads_edges.geojson")
    
    if os.path.exists(graphml_path) and not refresh:
        G = ox.load_graphml(graphml_path)
    else:
        south, west, north, east = area.bbox()
        # OSMNx 2.x bbox is (left, bottom, right, top) = (west, south, east, north)
        G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive")
        ox.save_graphml(G, graphml_path)
        
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
        gdf_edges = gdf_edges.apply(lambda col: col.astype(str) if col.name != 'geometry' else col)
        
        if os.path.exists(geojson_path):
            os.remove(geojson_path)
        gdf_edges.to_file(geojson_path, driver="GeoJSON")

    node_count = len(G.nodes)
    edge_count = len(G.edges)
    
    # Calculate total length in meters. OSMNx sets 'length' property for unprojected graphs.
    total_length = sum(data.get('length', 0.0) for u, v, key, data in G.edges(keys=True, data=True))
    
    return G, node_count, edge_count, total_length, graphml_path, geojson_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Force refresh of OSM data")
    args = parser.parse_args()
    
    area = Area.from_env()
    G, nodes, edges, length, p1, p2 = fetch_roads(area, refresh=args.refresh)
    
    print(f"Area: {area.name}")
    print(f"Bbox: {area.bbox()}")
    print(f"Nodes: {nodes}")
    print(f"Edges: {edges}")
    print(f"Total edge length: {length:.2f} m")
    print(f"Saved to:\n  {p1}\n  {p2}")
