import os
import sys
import shutil
import hashlib
import numpy as np
import pandas as pd

from app.sim.generate_dataset import generate_dataset

os.environ["DATASET_RUNS"] = "8"
os.environ["DATASET_SEED"] = "42"
os.environ["DATA_DIR"] = "/data"

# Run 1
os.environ["DATASET_NAME"] = "b2_run1"
out1 = "/data/datasets/b2_run1"
if os.path.exists(out1): shutil.rmtree(out1)
generate_dataset()

# Run 2
os.environ["DATASET_NAME"] = "b2_run2"
out2 = "/data/datasets/b2_run2"
if os.path.exists(out2): shutil.rmtree(out2)
generate_dataset()

# Compare
m1 = pd.read_parquet(os.path.join(out1, "manifest.parquet"))
m2 = pd.read_parquet(os.path.join(out2, "manifest.parquet"))

print("\n--- DETERMINISM PROOF ---")
h1 = hashlib.md5(open(os.path.join(out1, "manifest.parquet"), "rb").read()).hexdigest()
h2 = hashlib.md5(open(os.path.join(out2, "manifest.parquet"), "rb").read()).hexdigest()
print(f"Manifest Hash 1: {h1}")
print(f"Manifest Hash 2: {h2}")

ho1 = m1[m1["split"] == "test_unseen_pipe"]["blocked_pipe_id"].unique()
ho2 = m2[m2["split"] == "test_unseen_pipe"]["blocked_pipe_id"].unique()
print(f"Held-out 1: {sorted(ho1)}")
print(f"Held-out 2: {sorted(ho2)}")

# Compare 3 npz
npz_files = [f for f in os.listdir(out1) if f.endswith(".npz")][:3]
for f in npz_files:
    p1 = os.path.join(out1, f)
    p2 = os.path.join(out2, f)
    n1 = np.load(p1)
    n2 = np.load(p2)
    same = True
    for k in n1.keys():
        if not np.array_equal(n1[k], n2[k]):
            same = False
            print(f"  {f} key {k} differs!")
    print(f"NPZ {f} bit-identical: {same}")
