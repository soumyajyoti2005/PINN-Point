import pytest
import tempfile
import os
import json
from app.sim.make_swmm_inp import build_inp_text

@pytest.fixture
def dummy_network():
    return {
        "nodes": [
            {"id": "MH-001", "is_outfall": True, "lon": 0.0, "lat": 0.0, "invert_elevation_m": 1.0, "depth_m": 2.0},
            {"id": "MH-002", "is_outfall": False, "lon": 1.0, "lat": 1.0, "invert_elevation_m": 2.0, "depth_m": 2.0},
            {"id": "MH-003", "is_outfall": False, "lon": 2.0, "lat": 2.0, "invert_elevation_m": 3.0, "depth_m": 2.0},
        ],
        "pipes": [
            {"id": "P-002-001", "from_node": "MH-002", "to_node": "MH-001", "length_m": 100.0, "diameter_m": 0.3, "manning_n": 0.013},
            {"id": "P-003-002", "from_node": "MH-003", "to_node": "MH-002", "length_m": 100.0, "diameter_m": 0.3, "manning_n": 0.013},
        ]
    }

def test_build_inp_text_pure(dummy_network):
    settings = {
        "SWMM_CATCHMENT_HA_PER_NODE": 0.01,
        "SWMM_IMPERVIOUS_PCT": 100,
        "SWMM_PONDED_AREA_M2": 100,
    }
    storm = [(0, 60), (30, 60), (31, 0), (60, 0)]
    inp = build_inp_text(dummy_network, storm, settings)
    
    sections = [
        "[TITLE]", "[OPTIONS]", "[RAINGAGES]", "[SUBCATCHMENTS]", "[SUBAREAS]", 
        "[INFILTRATION]", "[JUNCTIONS]", "[OUTFALLS]", "[CONDUITS]", "[XSECTIONS]", 
        "[TIMESERIES]", "[REPORT]", "[COORDINATES]", "[VERTICES]", "[POLYGONS]"
    ]
    for sec in sections:
        assert sec in inp
        
    lines = inp.split("\n")
    junction_lines = [l for l in lines if l.startswith("MH-") and " 0          0 " in l]
    assert len(junction_lines) == 2 # MH-002, MH-003
    
    outfall_lines = [l for l in lines if l.startswith("MH-001 ") and " FREE " in l]
    assert len(outfall_lines) == 1
    
    conduit_lines = [l for l in lines if l.startswith("P-")]
    assert len(conduit_lines) == 4 # 2 in CONDUITS, 2 in XSECTIONS
    
    subcatch_lines = [l for l in lines if l.startswith("S_MH-")]
    assert len(subcatch_lines) == 8 # 2 in SUBCATCHMENTS, 2 in SUBAREAS, 2 in INFILTRATION, 2 in POLYGONS

def test_smoke_swmm_engine(dummy_network):
    pyswmm = pytest.importorskip("pyswmm")
    from pyswmm import Simulation
    
    settings = {
        "SWMM_CATCHMENT_HA_PER_NODE": 0.01,
        "SWMM_IMPERVIOUS_PCT": 100,
        "SWMM_PONDED_AREA_M2": 100,
    }
    storm = [(0, 60), (30, 60), (31, 0), (60, 0)]
    inp = build_inp_text(dummy_network, storm, settings)
    
    with tempfile.NamedTemporaryFile(suffix=".inp", delete=False) as f:
        f.write(inp.encode('utf-8'))
        f.close()
        try:
            with Simulation(f.name) as sim:
                for step in sim:
                    pass
                
                # Check continuity errors
                err_runoff = sim.runoff_error
                err_routing = sim.flow_routing_error
                
                assert abs(err_runoff) < 0.05
                assert abs(err_routing) < 0.05
                
                # Check outfall flow > 0
                nodes = pyswmm.Nodes(sim)
                outfall = nodes["MH-001"]
                assert outfall.cumulative_inflow > 0
        finally:
            os.remove(f.name)
def test_determinism_swmm_engine(dummy_network):
    settings = {
        "SWMM_CATCHMENT_HA_PER_NODE": 0.02,
        "SWMM_IMPERVIOUS_PCT": 100,
        "SWMM_PONDED_AREA_M2": 100,
    }
    storm = [(0, 60), (30, 60), (31, 0), (60, 0)]
    inp1 = build_inp_text(dummy_network, storm, settings)
    
    # Shuffle the input to verify sorting works
    import copy, random
    shuffled_net = copy.deepcopy(dummy_network)
    random.shuffle(shuffled_net['nodes'])
    random.shuffle(shuffled_net['pipes'])
    
    inp2 = build_inp_text(shuffled_net, storm, settings)
    assert inp1 == inp2, "Generated INP is not deterministic"
def test_parse_continuity_errors():
    from app.sim.make_swmm_inp import parse_continuity_errors
    rpt_text = """
  Evaporation Loss .........         0.000         0.000
  Infiltration Loss ........         0.000         0.000
  Surface Runoff ...........         0.030        31.014
  Final Storage ............         0.000         0.050
  Continuity Error (%) .....        -0.206
  
  Evaporation Loss .........         0.000         0.000
  Exfiltration Loss ........         0.000         0.000
  Initial Stored Volume ....         0.000         0.000
  Final Stored Volume ......         0.000         0.001
  Continuity Error (%) .....         1.112
    """
    runoff, routing = parse_continuity_errors(rpt_text)
    assert runoff == -0.206
    assert routing == 1.112
