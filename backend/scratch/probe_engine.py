import json
import os
import tempfile
import sys
import numpy as np

def probe():
    import os, tempfile
    try:
        import pyswmm
    except ImportError:
        print("pyswmm not found")
        return
        
    # We must load the network from the real path
    net_path = "/data/swmm/kolkata-amherst_network.json"
    if not os.path.exists(net_path):
        net_path = "backend/scratch/kolkata-amherst_network.json" # fallback
        if not os.path.exists(net_path):
            print("network not found")
            return
            
    with open(net_path, "r") as f:
        network = json.load(f)
        
    print(f"PROBE NETWORK PATH: {net_path}")
    print(f"PROBE NETWORK NODES: {len(network.get('nodes', []))}")
    print(f"PROBE NETWORK PIPES: {len(network.get('pipes', []))}")
        
    storm = [(t, 60.0) for t in range(31)] + [(31, 0.0), (120, 0.0)]
    
    # We must import from app
    sys.path.insert(0, "/app/backend")
    sys.path.insert(0, "/app")
    
    try:
        from app.sim.make_swmm_inp import build_inp_text
        from app.sim.generate_dataset import run_simulation
    except ImportError as e:
        print(f"Import error: {e}")
        return
        
    pipe_diam = {p['id']: p['diameter_m'] for p in network['pipes']}
    sorted_pipes = sorted(network['pipes'], key=lambda p: p['diameter_m'], reverse=True)
    largest_3_conduits = [p['id'] for p in sorted_pipes[:3]]
    largest_conduit = largest_3_conduits[0]
    
    catchments = [0.02, 0.05, 0.1]
    
    first_run = True
    
    for c_ha in catchments:
        print(f"\n{'='*40}")
        print(f"CATCHMENT: {c_ha} ha")
        print(f"{'='*40}")
        
        settings = {'SWMM_CATCHMENT_HA_PER_NODE': c_ha, 'SWMM_IMPERVIOUS_PCT': 100.0, 'SWMM_PONDED_AREA_M2': 100.0}
        inp_text = build_inp_text(network, storm, settings, duration_minutes=120)
        
        import tempfile, os
        fd, inp_path = tempfile.mkstemp(suffix=".inp")
        os.close(fd)
        fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
        os.close(fd)
        with open(inp_path, "w") as f:
            f.write(inp_text)
        if first_run:
            first_run = False
            with open(inp_path, 'r') as f:
                disk_inp = f.read()
            import hashlib
            sha = hashlib.sha256(disk_inp.encode('utf-8')).hexdigest()
            routing_step = next((l for l in disk_inp.splitlines() if l.startswith("ROUTING_STEP")), "NOT FOUND")
            allow_ponding = next((l for l in disk_inp.splitlines() if l.startswith("ALLOW_PONDING")), "NOT FOUND")
            first_conduit = "NOT FOUND"
            in_cond = False
            for l in disk_inp.splitlines():
                if l.startswith("[CONDUITS]"): in_cond = True; continue
                if in_cond and not l.startswith(";") and l.strip() and not l.startswith("["):
                    first_conduit = l; break
                if l.startswith("["): in_cond = False
            print(f"PROBE INP SHA256: {sha}")
            print(f"PROBE INP ROUTING_STEP: {routing_step}")
            print(f"PROBE INP ALLOW_PONDING: {allow_ponding}")
            print(f"PROBE INP FIRST CONDUIT: {first_conduit}")
            
            print("--- INP EXCERPTS ---")
            lines = inp_text.splitlines()
            def print_section(name, count):
                in_sec = False
                c = 0
                for l in lines:
                    if l.startswith(name):
                        in_sec = True
                        print(l)
                        continue
                    if in_sec:
                        if l.startswith("["): break
                        if not l.startswith(";;") and l.strip() != "":
                            print(l)
                            c += 1
                            if c >= count: break
            
            print_section("[OPTIONS]", 20)
            print_section("[CONDUITS]", 3)
            print_section("[XSECTIONS]", 200) # Wait, only 3
            # I will just print the exact sections correctly below manually
            in_xsec, in_jun, in_time = False, False, False
            c_xsec, c_jun, c_time = 0, 0, 0
            for l in lines:
                if l.startswith("[XSECTIONS]"): in_xsec=True; print(l); continue
                if l.startswith("[JUNCTIONS]"): in_jun=True; print(l); continue
                if l.startswith("[TIMESERIES]"): in_time=True; print(l); continue
                
                if l.startswith("["): in_xsec=in_jun=in_time=False
                if in_xsec and c_xsec < 3 and not l.startswith(";;") and l.strip(): print(l); c_xsec+=1
                if in_jun and c_jun < 3 and not l.startswith(";;") and l.strip(): print(l); c_jun+=1
                if in_time and c_time < 6 and not l.startswith(";;") and l.strip(): print(l); c_time+=1
                
        fd, inp_path = tempfile.mkstemp(suffix=".inp")
        os.close(fd)
        fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
        os.close(fd)
        

        with open(inp_path, "w") as f:
            f.write(inp_text)
            
        if first_run:
            first_run = False
            with open(inp_path, "r") as f:
                disk_inp = f.read()
            import hashlib
            sha = hashlib.sha256(disk_inp.encode('utf-8')).hexdigest()
            routing_step = next((l for l in disk_inp.splitlines() if l.startswith("ROUTING_STEP")), "NOT FOUND")
            allow_ponding = next((l for l in disk_inp.splitlines() if l.startswith("ALLOW_PONDING")), "NOT FOUND")
            first_conduit = "NOT FOUND"
            in_cond = False
            for l in disk_inp.splitlines():
                if l.startswith("[CONDUITS]"): in_cond = True; continue
                if in_cond and not l.startswith(";") and l.strip() and not l.startswith("["):
                    first_conduit = l; break
                if l.startswith("["): in_cond = False
            print(f"PROBE INP SHA256: {sha}")
            print(f"PROBE INP ROUTING_STEP: {routing_step}")
            print(f"PROBE INP ALLOW_PONDING: {allow_ponding}")
            print(f"PROBE INP FIRST CONDUIT: {first_conduit}")
            
            print("--- INP EXCERPTS (FROM DISK) ---")
            lines = disk_inp.splitlines()
            print(f"Total lines: {len(lines)}")
            def print_section(name, count):
                print(f"[{name}]")
                in_sec = False
                c = 0
                for l in lines:
                    if l.startswith(f"[{name}]"): in_sec = True; continue
                    if in_sec and l.startswith("["): break
                    if in_sec and l.strip() and not l.startswith(";"):
                        print(l)
                        c += 1
                        if c >= count and count > 0: break
            print_section("OPTIONS", 0)
            print_section("CONDUITS", 5)

        # a. Run plain pyswmm
        plain_node_max = {}
        target_mins = {10, 20, 30, 60, 120}
        visited_mins = set()
        
        try:
            with pyswmm.Simulation(inp_path, reportfile=rpt_path) as sim:
                link_objs = [l for l in pyswmm.Links(sim) if l.is_conduit()]
                node_objs = list(pyswmm.Nodes(sim))
                
                # print dir once
                if c_ha == catchments[0]:
                    print("--- DIR(LINKS) ---")
                    try: print(dir(list(links)[0]))
                    except: pass
                    print("--- DIR(NODES) ---")
                    try: print(dir(list(nodes)[0]))
                    except: pass
                    
                for step in sim:
                    for n in node_objs:
                        plain_node_max[n.nodeid] = max(plain_node_max.get(n.nodeid, 0.0), n.depth)
                        
                    current_min = int((sim.current_time - sim.start_time).total_seconds() / 60)
                    if current_min in target_mins and current_min not in visited_mins:
                        visited_mins.add(current_min)
                        print(f"--- MINUTE {current_min} ---")
                        for lid in largest_3_conduits:
                            l = next((x for x in link_objs if x.linkid == lid), None)
                            if l:
                                d = l.depth
                                f = l.flow if hasattr(l, "flow") else "N/A"
                                print(f"{lid}: diam={pipe_diam[lid]}, depth={d}, flow={f}")
        finally:
            pass
            
        print("TOP 5 LINK MAX/FULL DEPTH (.RPT):")
        # I'll parse it below.
            
        with open(rpt_path, "r") as f:
            rpt_lines = f.readlines()
            
        print(f"RPT LINES READ: {len(rpt_lines)}")
        
        # Parse rpt exact block helper
        def parse_exact(title, lines):
            in_section = False
            results = []
            for line in lines:
                if title in line: in_section = True; continue
                if in_section and line.startswith("  ---"): continue
                if in_section and (line.strip() == "" or line.startswith("  ***") or line.startswith("  ===")): break
                if in_section: results.append(line.strip())
            return results

        def parse_flooding(lines):
            in_section = False
            results = []
            for line in lines:
                if "Node Flooding Summary" in line: in_section = True; continue
                if in_section and line.strip() == "": continue
                if in_section and line.startswith("  ---"): continue
                if in_section and line.startswith("  ***"): break
                if in_section and "No nodes were flooded" in line: return []
                if in_section and line.startswith("  Outfall"): break
                if in_section and line.startswith("  Node"): continue
                if in_section and line.startswith("  Name"): continue
                if in_section: results.append(line.strip())
            return results

            
        continuity_err_runoff = []
        continuity_err_routing = []
        node_depths = {}
        node_reported_max = {}
        node_time_max = {}
        link_flows = {}
        flooding = []
        
        # Routing cont: Flow Routing Continuity
        in_cont_runoff = False
        in_cont_routing = False
        for line in rpt_lines:
            if "Runoff Quantity Continuity" in line: in_cont_runoff = True; in_cont_routing = False
            elif "Flow Routing Continuity" in line: in_cont_routing = True; in_cont_runoff = False
            elif (in_cont_runoff or in_cont_routing) and (line.strip() == "" or line.startswith("***")):
                in_cont_runoff = in_cont_routing = False
            elif in_cont_runoff and "Error" in line: continuity_err_runoff.append(line.strip())
            elif in_cont_routing and "Error" in line: continuity_err_routing.append(line.strip())
            
        # Node Depth Summary (dash count = 2)
        nd_lines = parse_exact("Node Depth Summary", rpt_lines)
        for line in nd_lines:
            parts = line.split()
            if len(parts) >= 4:
                try: 
                    node_depths[parts[0]] = float(parts[3])
                    node_reported_max[parts[0]] = float(parts[-1])
                    if len(parts) >= 6: node_time_max[parts[0]] = parts[4] + " " + parts[5]
                except (ValueError, IndexError): pass
                
        # Link Flow Summary (dash count = 2)
        lf_lines = parse_exact("Link Flow Summary", rpt_lines)
        for line in lf_lines:
            parts = line.split()
            if len(parts) >= 8:
                try: link_flows[parts[0]] = {"max_flow": float(parts[2]), "max_full_flow": float(parts[6]), "max_full_depth": float(parts[7])}
                except (ValueError, IndexError): pass
                
        flooding = parse_flooding(rpt_lines)
                    
        print(f"RUNOFF CONTINUITY:")
        for c in continuity_err_runoff: print(c)
        print(f"ROUTING CONTINUITY:")
        for c in continuity_err_routing: print(c)
        
        print("NODE FLOODING SUMMARY:")
        if not flooding: print("none")
        else:
            for f in flooding[:5]: print(f)
            
        print("--- HIGHEST FLOW INSTABILITY INDEXES ---")
        for line in parse_exact("Highest Flow Instability Indexes", rpt_lines): print(line)
        print("--- ROUTING TIME STEP SUMMARY ---")
        for line in parse_exact("Routing Time Step Summary", rpt_lines): print(line)
        
        print("TOP 5 LINK MAX/FULL DEPTH (.RPT):")
        sorted_links = sorted(link_flows.items(), key=lambda x: x[1][2], reverse=True)[:5]
        for l, d in sorted_links: print(f"{l}: max_flow={d[0]}, max/full_flow={d[1]}, max/full_depth={d[2]}")
        print("LARGEST CONDUIT (.RPT):")
        if largest_3_conduits:
            l = largest_3_conduits[0]
            if l in link_flows:
                d = link_flows[l]
                print(f"{l}: max_flow={d[0]}, max/full_flow={d[1]}, max/full_depth={d[2]}")
        
        sorted_links = sorted(link_flows.items(), key=lambda x: x[1]['max_full_depth'], reverse=True)[:5]
        print("TOP 5 LINK MAX/FULL DEPTH (.RPT):")
        for l, d in sorted_links: print(f"{l}: max_flow={d['max_flow']}, max/full_flow={d['max_full_flow']}, max/full_depth={d['max_full_depth']}")
        print("LARGEST CONDUIT (.RPT):")
        ld = link_flows.get(largest_conduit)
        if ld: print(f"{largest_conduit}: max_flow={ld['max_flow']}, max/full_flow={ld['max_full_flow']}, max/full_depth={ld['max_full_depth']}")
        
        # run_simulation max depth
        res = run_simulation(inp_text)
        run_depths = res["depths"]
        run_node_ids = res["node_ids"]
        
        sorted_nodes = sorted(node_reported_max.items(), key=lambda x: x[1], reverse=True)[:5]
        print("TOP 5 NODE DEPTHS (MaxDepth | ReportedMax | Time | PlainLoop | API):")
        
        run_node_ids_list = list(run_node_ids)
        for n, rep in sorted_nodes: 
            d = node_depths.get(n, 0.0)
            tm = node_time_max.get(n, "N/A")
            pl_d = plain_node_max.get(n, 0.0)
            
            if n in run_node_ids_list:
                idx = run_node_ids_list.index(n)
                run_d = np.max(run_depths[:, idx])
            else:
                run_d = 0.0
            print(f"{n}: {d} | {rep} | {tm} | {pl_d} | {run_d}")
                
        max_diff_max = 0.0
        max_diff_rep = 0.0
        for i, n in enumerate(run_node_ids_list):
            if n in node_depths:
                diff_m = abs(np.max(run_depths[:, i]) - node_depths[n])
                max_diff_max = max(max_diff_max, diff_m)
            if n in node_reported_max:
                diff_r = abs(np.max(run_depths[:, i]) - node_reported_max[n])
                max_diff_rep = max(max_diff_rep, diff_r)
        print(f"LARGEST ABS DIFFERENCE vs Maximum Depth: {max_diff_max}")
        print(f"LARGEST ABS DIFFERENCE vs Reported Max: {max_diff_rep}")
        
        # D. Extra pass
        if c_ha == catchments[1]: # 0.05 ha only or for all? User says: "Why is MH-024 1.20 m in the .rpt but 0.43 m in run_simulation at 0.05 ha? For the 5 nodes, using the same INP, run one extra pass with no step_advance...". I will just run it for all to be safe, or just run it always.
            print("--- NO STEP ADVANCE EXTRA PASS ---")
            no_step_max = {}
            no_step_60_max = {}
            mh024_all = []
            
            with pyswmm.Simulation(inp_path) as sim2:
                n_objs = list(pyswmm.Nodes(sim2))
                top_node_ids = [k[0] for k in sorted_nodes]
                
                tm_str = node_time_max.get("MH-024", "")
                target_dt = None
                if tm_str:
                    import datetime
                    try:
                        target_dt = datetime.datetime.strptime("2026-01-01 " + tm_str, "%Y-%m-%d %H:%M")
                    except:
                        pass
                
                for step in sim2:
                    t = sim2.current_time
                    for n in n_objs:
                        if n.nodeid in top_node_ids:
                            no_step_max[n.nodeid] = max(no_step_max.get(n.nodeid, 0.0), n.depth)
                            delta_s = (t - sim2.start_time).total_seconds()
                            if delta_s % 60 == 0:
                                no_step_60_max[n.nodeid] = max(no_step_60_max.get(n.nodeid, 0.0), n.depth)
                            
                            if n.nodeid == "MH-024" and target_dt:
                                if abs((t - target_dt).total_seconds()) <= 180:
                                    mh024_all.append((t, n.depth))
                                    
            for n, rep in sorted_nodes:
                run_d = 0.0
                if n in run_node_ids_list:
                    run_d = np.max(run_depths[:, run_node_ids_list.index(n)])
                d = node_depths.get(n, 0.0)
                ns = no_step_max.get(n, 0.0)
                ns60 = no_step_60_max.get(n, 0.0)
                print(f"EXTRA: {n} | RPT Max: {d} | RPT Rep: {rep} | API: {run_d} | NoStep All: {ns} | NoStep 60s: {ns60}")
                
            if mh024_all:
                print("MH-024 ROUTING STEP SERIES (+/- 3 min from .RPT max):")
                for t, d in mh024_all: print(f"  {t}: {d}")
                print("MH-024 API SAMPLES (+/- 3 min):")
                if "MH-024" in run_node_ids_list:
                    idx = run_node_ids_list.index("MH-024")
                    for i, ts in enumerate(res["times_s"]):
                        import datetime
                        st = datetime.datetime(2026,1,1,0,0,0) + datetime.timedelta(seconds=ts)
                        if target_dt and abs((st - target_dt).total_seconds()) <= 180:
                            print(f"  {st}: {run_depths[i, idx]}")
                            
        os.remove(inp_path)
        if os.path.exists(rpt_path): os.remove(rpt_path)

if __name__ == "__main__":
    probe()
