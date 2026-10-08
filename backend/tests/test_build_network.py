import pytest
import math

def test_select_outfall_pure():
    from app.sim.build_network import select_outfall_pure
    nodes_data = {
        1: {'is_boundary': False, 'ground': 2.0},
        2: {'is_boundary': True, 'ground': 5.0},
        3: {'is_boundary': True, 'ground': 3.5},
        4: {'is_boundary': True, 'ground': 4.0},
    }
    assert select_outfall_pure(nodes_data) == 3
    
def test_pure_core_flat_gentle():
    nx = pytest.importorskip("networkx")
    from app.sim.build_network import build_network_core
    
    G = nx.MultiDiGraph()
    for i in range(12):
        x = 88.370 + (i % 3) * 0.001
        y = 22.579 + (i // 3) * 0.001
        G.add_node(i, x=x, y=y)
        
    edges = [
        (0,1), (1,2),
        (3,4), (4,5),
        (6,7), (7,8),
        (9,10), (10,11),
        (0,3), (3,6), (6,9),
        (1,4), (4,7), (7,10),
        (2,5), (5,8), (8,11),
        (4,1)
    ]
    
    for u, v in edges:
        dx = G.nodes[u]['x'] - G.nodes[v]['x']
        dy = G.nodes[u]['y'] - G.nodes[v]['y']
        l = math.hypot(dx * 111320 * math.cos(math.radians(22.5)), dy * 111320)
        G.add_edge(u, v, length=l)
        
    G.add_node(12, x=88.370+0.003, y=22.579)
    G.add_edge(2, 12, length=200.0)
    
    def get_ground(x, y, n):
        return 5.0, 5.0
        
    def is_boundary(n, x, y):
        return n == 0
        
    tree, outfall_id, adj_count, max_adj = build_network_core(
        G, outfall_node=0, max_spacing=100.0, cover=1.5, min_slope=0.001, get_ground=get_ground, seed=42, is_boundary=is_boundary
    )
    
    # max path length is ~ 300m, so rise is ~ 0.3m
    # Invert start = 3.5, required invert = 3.8. Ground = 5.0. 5.0 - 0.6 = 4.4.
    # 3.8 is less than 4.4, so invert is fine without adjusting ground.
    assert adj_count == 0
    assert max_adj == 0.0
    
    for u, v, d in tree.edges(data=True):
        assert d['slope'] >= 0.001 - 1e-5
        
    for n, d in tree.nodes(data=True):
        assert d['invert_elevation_m'] <= d['ground_elevation_m'] - 0.6 + 1e-5

def test_pure_core_flat_steep():
    nx = pytest.importorskip("networkx")
    from app.sim.build_network import build_network_core
    
    G = nx.MultiDiGraph()
    for i in range(12):
        x = 88.370 + (i % 3) * 0.001
        y = 22.579 + (i // 3) * 0.001
        G.add_node(i, x=x, y=y)
        
    edges = [
        (0,1), (1,2),
        (3,4), (4,5),
        (6,7), (7,8),
        (9,10), (10,11),
        (0,3), (3,6), (6,9),
        (1,4), (4,7), (7,10),
        (2,5), (5,8), (8,11),
        (4,1)
    ]
    
    for u, v in edges:
        dx = G.nodes[u]['x'] - G.nodes[v]['x']
        dy = G.nodes[u]['y'] - G.nodes[v]['y']
        l = math.hypot(dx * 111320 * math.cos(math.radians(22.5)), dy * 111320)
        G.add_edge(u, v, length=l)
        
    def get_ground(x, y, n):
        return 5.0, 5.0
        
    # min_slope 0.01 (1%), rise over 300m is 3m. Invert at far end = 3.5 + 3 = 6.5m.
    # Ground = 5.0m. Invert > ground - 0.6 (6.5 > 4.4), so new ground = 6.5 + 0.6 = 7.1m.
    tree, outfall_id, adj_count, max_adj = build_network_core(
        G, outfall_node=0, max_spacing=100.0, cover=1.5, min_slope=0.01, get_ground=get_ground, seed=42
    )
    
    assert adj_count > 0
    assert max_adj > 0.0
    
    for n, d in tree.nodes(data=True):
        if 'ground_adjusted_m' in d:
            assert abs(d['ground_adjusted_m'] - d['ground_elevation_m']) < 1e-5
            assert d['ground_adjusted_m'] > 5.0
            
        assert d['invert_elevation_m'] <= d['ground_elevation_m'] - 0.6 + 1e-5

def test_pipe_geometry_orientation():
    nx = pytest.importorskip("networkx")
    from shapely.geometry import LineString
    from app.sim.build_network import insert_manholes, generate_outputs
    import os, json, tempfile
    
    tree = nx.DiGraph()
    tree.add_node('MH-001', x=0.0, y=0.0, ground_elevation_m=5.0, invert_elevation_m=4.0)
    tree.add_node('MH-002', x=1.0, y=1.0, ground_elevation_m=5.0, invert_elevation_m=4.1)
    
    # Create an edge with a LineString that goes from MH-002 (1.0, 1.0) down to MH-001 (0.0, 0.0)
    # The edge in the tree goes from MH-002 -> MH-001, but suppose the OSM geometry is reversed
    tree.add_edge('MH-002', 'MH-001', id='P-002-001', length=1.414, diameter_m=0.3, slope=0.001, manning_n=0.013, 
                  geometry=LineString([(0.0, 0.0), (1.0, 1.0)])) # Reversed
                  
    with tempfile.TemporaryDirectory() as tmpdir:
        class Args:
            pass
        generate_outputs(tree, 'MH-001', type('Area', (), {'name': 'test', 'bbox': lambda: (0,0,1,1), 'center_lon': 0.5, 'center_lat': 0.5}), Args(), 'synthetic', tmpdir)
        
        with open(os.path.join(tmpdir, "swmm", "test_network.json")) as f:
            data = json.load(f)
            
        p = data['pipes'][0]
        assert p['from_node'] == 'MH-002'
        assert p['to_node'] == 'MH-001'
        coords = p['coords']
        assert coords[0] == [1.0, 1.0] # start must match from_node
        assert coords[-1] == [0.0, 0.0] # end must match to_node

