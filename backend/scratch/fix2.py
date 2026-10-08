code = open(r'c:\projects\PINN-Point\backend\scratch\probe_mh024.py').read()
code = code.replace('rpt_rep_time[nid] = parts[4] + " " + parts[5]', 'rpt_rep_time[nid] = parts[-3] + " " + parts[-2]')
code = code.replace('mh024_dt = datetime.datetime.strptime("2026-01-01 " + rpt_rep_time["MH-024"], "%Y-%m-%d %H:%M")',
                    'try:\n        mh024_dt = datetime.datetime.strptime("2026-01-01 " + rpt_rep_time["MH-024"].split()[1], "%Y-%m-%d %H:%M")\n    except: pass')
open(r'c:\projects\PINN-Point\backend\scratch\probe_mh024.py', 'w').write(code)
