code = open(r'c:\projects\PINN-Point\backend\scratch\probe_engine.py').read()
code = code.replace("        if first_run:\n            first_run = False\n            with open(inp_path, 'r') as f:", """        import tempfile, os
        fd, inp_path = tempfile.mkstemp(suffix=".inp")
        os.close(fd)
        fd, rpt_path = tempfile.mkstemp(suffix=".rpt")
        os.close(fd)
        with open(inp_path, "w") as f:
            f.write(inp_text)
        if first_run:
            first_run = False
            with open(inp_path, 'r') as f:""")
open(r'c:\projects\PINN-Point\backend\scratch\probe_engine.py', 'w').write(code)
