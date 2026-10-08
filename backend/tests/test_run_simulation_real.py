import pytest
import os
import json
import numpy as np
import tempfile

def test_run_simulation_real():
    pyswmm = pytest.importorskip("pyswmm")
    
    data_dir = os.environ.get("DATA_DIR", "/data")
    area = os.environ.get("AREA_NAME", "kolkata-amherst")
    net_path = os.path.join(data_dir, "swmm", f"{area}_network.json")
    
    if not os.path.exists(net_path):
        pytest.skip(f"Real network not found at {net_path}")
        
    with open(net_path, "r") as f:
        network = json.load(f)
        
    print(f"TEST NETWORK PATH: {net_path}")
    print(f"TEST NETWORK NODES: {len(network.get('nodes', []))}")
    print(f"TEST NETWORK PIPES: {len(network.get('pipes', []))}")
        
    # EXACTLY the calibration storm & settings
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    settings = {'SWMM_CATCHMENT_HA_PER_NODE': 0.02, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
    
    from app.sim.make_swmm_inp import build_inp_text
    from app.sim.generate_dataset import run_simulation
    
    inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
    
    # Print INP info
    import hashlib
    sha = hashlib.sha256(inp_text.encode('utf-8')).hexdigest()
    routing_step = next((l for l in inp_text.splitlines() if l.startswith("ROUTING_STEP")), "NOT FOUND")
    allow_ponding = next((l for l in inp_text.splitlines() if l.startswith("ALLOW_PONDING")), "NOT FOUND")
    first_conduit = "NOT FOUND"
    in_cond = False
    for l in inp_text.splitlines():
        if l.startswith("[CONDUITS]"): in_cond = True; continue
        if in_cond and not l.startswith(";") and l.strip() and not l.startswith("["):
            first_conduit = l; break
        if l.startswith("["): in_cond = False
            
    print(f"TEST INP SHA256: {sha}")
    print(f"TEST INP ROUTING_STEP: {routing_step}")
    print(f"TEST INP ALLOW_PONDING: {allow_ponding}")
    print(f"TEST INP FIRST CONDUIT: {first_conduit}")
    
    fd, inp_path = tempfile.mkstemp(suffix=".inp")
    os.close(fd)
    fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
    os.close(fd)
    
    with open(inp_path, "w") as f:
        f.write(inp_text)
        
    pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}
    
    # b. Calibration regression (plain pyswmm loop)
    max_d_D = 0.0
    max_d_D_linkid = None
    max_d_D_time = None
    max_d_D_diam = None
    
    steps = 0
    start_time = None
    end_time = None
    node_depths_plain = {}
    
    conduits_iterated = 0
    conduits_matched = 0
    unmapped_links = set()
    
    p002_001_depth = None
    p002_001_min_diff = float("inf")
    
    try:
        with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
            link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
            node_objs = list(pyswmm.Nodes(sim))
            
            raw_depths = []
            raw_times = []
            
            for step in sim:
                if start_time is None:
                    start_time = sim.start_time
                steps += 1
                
                elapsed = (sim.current_time - start_time).total_seconds()
                raw_depths.append([n.depth for n in node_objs])
                raw_times.append(elapsed)
                
                # Check nearest minute 30 for P-002-001
                elapsed_min = (sim.current_time - start_time).total_seconds() / 60.0
                diff_30 = abs(elapsed_min - 30.0)
                if diff_30 < p002_001_min_diff:
                    p002_001_min_diff = diff_30
                    try: p002_001_depth = next((l.depth for l in link_objs if l.linkid == "P-002-001"), None)
                    except: pass
                    
                for l in link_objs:
                    conduits_iterated += 1
                    diam = pipe_diam.get(l.linkid)
                    if diam:
                        conduits_matched += 1
                        d_D = l.depth / float(diam)
                        if d_D > max_d_D:
                            max_d_D = d_D
                            max_d_D_linkid = l.linkid
                            max_d_D_time = sim.current_time
                            max_d_D_diam = diam
                    else:
                        unmapped_links.add(l.linkid)
                            
                for n in node_objs:
                    node_depths_plain[n.nodeid] = max(node_depths_plain.get(n.nodeid, 0.0), n.depth)
                    
            end_time = sim.current_time
    finally:
        if os.path.exists(inp_path): os.remove(inp_path)
        
    raw_depths = np.array(raw_depths)
    from app.sim.generate_dataset import resample_time_series
    target_duration = (end_time - start_time).total_seconds()
    plain_t_grid, plain_depths_60s = resample_time_series(raw_times, raw_depths, target_duration)
    
    # Reorder plain_depths_60s to match network node order
    node_ids_plain = [n.nodeid for n in node_objs]
    target_order = [n["id"] for n in network.get("nodes", [])]
    idx_map = [node_ids_plain.index(nid) for nid in target_order if nid in node_ids_plain]
    plain_depths_60s = plain_depths_60s[:, idx_map]
    
    print(f"Steps: {steps}")
    print(f"Start time: {start_time}, End time: {end_time}")
    print(f"Conduits iterated (total steps * conduits): {conduits_iterated}")
    print(f"Conduits matched in pipe_diam: {conduits_matched}")
    print(f"Unmapped linkids (up to 5): {list(unmapped_links)[:5]}")
    print(f"pipe_diam keys (up to 5): {list(pipe_diam.keys())[:5]}")
    print(f"Argmax link id: {max_d_D_linkid}")
    print(f"Argmax time: {max_d_D_time}")
    print(f"max d/D: {max_d_D}, diameter: {max_d_D_diam}")
    print(f"P-002-001 depth at nearest min 30: {p002_001_depth}")
    
    assert steps > 1000, f"Expected > 1000 steps, got {steps}"
    
    time_diff_seconds = (end_time - start_time).total_seconds()
    assert abs(time_diff_seconds - 120 * 60) <= 120, f"Expected ~7200s simulation time, got {time_diff_seconds}s"
    
    if max_d_D < 0.68 or max_d_D > 0.78:
        pytest.fail(f"Calibration regression failed: max d/D was {max_d_D:.4f}")
    
    # c. Differential check
    with open(rpt_path, "r") as f:
        rpt_lines = f.readlines()
        
    if os.path.exists(rpt_path): os.remove(rpt_path)
    
    assert len(rpt_lines) > 100, f".rpt file read failed, length {len(rpt_lines)}"
    
    node_depths_rpt = {}
    mode = None
    for line in rpt_lines:
        if "Node Depth Summary" in line: mode = "NODE_DEPTH"
        elif "Link Flow Summary" in line: mode = "LINK_FLOW"
        elif "Analysis begun" in line: mode = None
        
        if mode == "NODE_DEPTH" and len(line.split()) >= 4 and not line.startswith("  ---"):
            parts = line.split()
            if parts[0] != "Node" and parts[0] != "Name":
                try:
                    nid = parts[0]
                    max_depth = float(parts[2])
                    node_depths_rpt[nid] = max_depth
                except ValueError: pass
                
    # Run simulation function
    res1 = run_simulation(inp_text, network)
    res2 = run_simulation(inp_text, network)
    
    # d. Keep baseline checks
    assert res1["status"] == "success"
    assert res1["flood_volume_m3"] == 0.0
    assert res1["routing_err_pct"] < 5.0
    
    depths = res1["depths"]
    node_ids = res1["node_ids"]
    times_s = res1["times_s"]
    
    # Fixed 60s grid check
    expected_length = 121
    
    print("depths.shape:", np.array(depths).shape)
    print("times_s[:3]:", times_s[:3])
    print("times_s[-3:]:", times_s[-3:])
    print("sorted(set(np.diff(times_s))):", sorted(set(np.diff(times_s))))
    
    assert len(times_s) == expected_length, f"Expected length {expected_length}, got {len(times_s)}"
    for i in range(1, len(times_s)):
        assert times_s[i] - times_s[i-1] == 60, "Times not strictly increasing by 60s"
    
    np.testing.assert_array_equal(res1["depths"], res2["depths"])
    np.testing.assert_array_equal(res1["times_s"], res2["times_s"])
    assert len(res1["node_ids"]) == len(network.get("nodes", []))
    assert res1["node_ids"] == [n["id"] for n in network.get("nodes", [])]
    
    # Differential check
    max_diff = 0.0
    worst_node = ""
    for idx, nid in enumerate(node_ids):
        run_max = np.max(depths[:, idx])
        rpt_max = node_depths_rpt.get(nid, 0.0)
        diff = abs(run_max - rpt_max)
        if diff > max_diff:
            max_diff = diff
            worst_node = nid
            
    assert max_diff < 0.3, f"Differential check failed: max difference {max_diff:.4f} m at node {worst_node}"
    
    # Check run_simulation interpolated against plain loop interpolated
    max_plain_diff = 0.0
    worst_plain_node = ""
    
    min_len = min(len(res1["depths"]), len(plain_depths_60s))
    
    for idx, nid in enumerate(node_ids):
        run_arr = res1["depths"][:min_len, idx]
        plain_arr = plain_depths_60s[:min_len, idx]
        diff = float(np.max(np.abs(run_arr - plain_arr)))
        if diff > max_plain_diff:
            max_plain_diff = diff
            worst_plain_node = nid
            
    print(f"run_simulation resampled vs plain loop resampled diff: {max_plain_diff:.4f} at {worst_plain_node}")
    assert max_plain_diff <= 0.02, f"run_simulation resampled depth differs from plain loop by {max_plain_diff:.4f} at {worst_plain_node}"
