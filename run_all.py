"""Run the whole analysis, from the raw data to every table and figure of the thesis.

    python run_all.py                  steps 01-08; the three GAMMs are read from outputs/models/
    python run_all.py --refit          also fit the three GAMMs again (step 06)
    python run_all.py --from 07        start at step 07
    python run_all.py --only 03 04     run only these steps

Step 00 (boundaries from the IBGE download, climate from Google Earth Engine) is not part of the
run: its outputs are in data/raw/. Rscript is found on the PATH, in the RSCRIPT environment
variable, or in the default Windows install folder.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("01", "scripts/01_compute_spei.py"),
    ("02", "scripts/02_build_panel.py"),
    ("03", "scripts/03_describe_data.py"),
    ("04", "scripts/04_data_figures.py"),
    ("05", "scripts/05_window_lag_test.py"),
    ("06", "scripts/06_fit_models.R"),
    ("07", "scripts/07_model_results.R"),
    ("08", "scripts/08_robustness.R"),
]


def find_rscript() -> str:
    for candidate in (os.environ.get("RSCRIPT"), shutil.which("Rscript")):
        if candidate:
            return candidate
    found = sorted(glob.glob("C:/Program Files/R/R-*/bin/Rscript.exe"))
    if found:
        return found[-1]
    sys.exit("Rscript not found: put it on the PATH or set RSCRIPT to its full path.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="start", default="01", help="first step to run (e.g. 05)")
    p.add_argument("--only", nargs="+", help="run only these steps")
    p.add_argument("--refit", action="store_true", help="fit the three GAMMs again in step 06")
    args = p.parse_args()

    steps = [s for s in STEPS if (s[0] in args.only if args.only else s[0] >= args.start)]
    rscript = find_rscript() if any(path.endswith(".R") for _, path in steps) else None
    for number, path in steps:
        cmd = [rscript, path] if path.endswith(".R") else [sys.executable, path]
        if number == "06" and args.refit:
            cmd.append("--refit")
        print(f"\n=== Step {number}: {path} ===", flush=True)
        t0 = time.time()
        subprocess.run(cmd, cwd=ROOT, check=True)
        print(f"--- step {number} done in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
