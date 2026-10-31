#!/usr/bin/env python3
"""The DATRAS download and derivation for this claim are shared with claim ch03-18:
../thompson1917-ch03-18/fetch.py downloads NS-IBTS CA/HH records (2015-2024, Q1 and Q3),
applies the pre-registered cleaning and writes ns_ibts_lw_bins.csv and fetch_summary.json,
which are copied here.  Running this script runs that one and copies the outputs."""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "thompson1917-ch03-18")
subprocess.check_call([sys.executable, os.path.join(SRC, "fetch.py"), *sys.argv[1:]])
os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
for name in ("ns_ibts_lw_bins.csv", "fetch_summary.json"):
    shutil.copy(os.path.join(SRC, "derived", name), os.path.join(HERE, "derived", name))
