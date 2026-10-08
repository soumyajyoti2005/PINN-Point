import os
with open(r'c:\projects\PINN-Point\backend\scratch\probe_engine.py', 'r') as f:
    code = f.read()

import re

# Fix INP Excerpts
new_inp = '''
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
'''
code = re.sub(r'        with open\(inp_path, "w"\) as f:\n            f.write\(inp_text\).*?        # a. Run plain pyswmm', new_inp + '\n        # a. Run plain pyswmm', code, flags=re.DOTALL)

# Fix parse_section and add parse_exact/parse_flooding
new_parse = '''        def parse_exact(title, lines):
            in_section = False
            results = []
            for line in lines:
                if title in line: in_section = True; continue
                if in_section and line.strip() == "": continue
                if in_section and line.startswith("  ---"): continue
                if in_section and line.startswith("  ***"): break
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
'''
code = re.sub(r'        def parse_section.*?return results', new_parse, code, flags=re.DOTALL)

# Fix Node Depth and Node Flooding loops
code = code.replace('nd_lines = parse_section("Node Depth Summary", rpt_lines)', 'nd_lines = parse_exact("Node Depth Summary", rpt_lines)')
code = code.replace('lf_lines = parse_section("Link Flow Summary", rpt_lines)', 'lf_lines = parse_exact("Link Flow Summary", rpt_lines)')
code = re.sub(r'        # Node Flooding Summary.*?flooding\.append\(line\)', '        flooding = parse_flooding(rpt_lines)', code, flags=re.DOTALL)

# Add Node time max map
code = code.replace('node_reported_max = {}', 'node_reported_max = {}\n        node_time_max = {}')
code = code.replace('node_reported_max[parts[0]] = float(parts[-1])', 'node_reported_max[parts[0]] = float(parts[-1])\n                    if len(parts) >= 6: node_time_max[parts[0]] = parts[4] + " " + parts[5]')

# Fix NEW BLOCKS section
new_blocks = '''
        print("--- HIGHEST FLOW INSTABILITY INDEXES ---")
        for line in parse_exact("Highest Flow Instability Indexes", rpt_lines): print(line)
        print("--- ROUTING TIME STEP SUMMARY ---")
        for line in parse_exact("Routing Time Step Summary", rpt_lines): print(line)
'''
code = re.sub(r'        # New blocks.*?print\(line\)', new_blocks.strip(), code, flags=re.DOTALL)

# Replace the run_simulation max depth output block
new_end = '''        # run_simulation max depth
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
                            
        os.remove(inp_path)'''
code = re.sub(r'        # run_simulation max depth.*os\.remove\(inp_path\)', new_end, code, flags=re.DOTALL)

with open(r'c:\projects\PINN-Point\backend\scratch\probe_engine.py', 'w') as f:
    f.write(code)
