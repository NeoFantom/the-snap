#!/usr/bin/env python3
"""index-local.py — walk the REFERENCE machine's roots, emit TSV to stdout.

Format: <path>\t<size bytes>\t<mtime seconds>

Config: scripts/_config.py reads ./config.json (or $FO_CONFIG).
Uses ``reference.roots``, ``reference.skip_done``, and ``exclude_dirs``.

Usage: python3 scripts/index-local.py > reference.tsv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load

cfg = load()
ROOTS = cfg["reference"]["roots"]
SKIP_DONE = set(cfg["reference"].get("skip_done", []))
EXCLUDE_DIRS = set(cfg["exclude_dirs"])

out = sys.stdout
for root in ROOTS:
    if not os.path.isdir(root):
        print(f"skip (not a dir): {root}", file=sys.stderr)
        continue
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d not in EXCLUDE_DIRS
                   and os.path.join(dirpath, d) not in SKIP_DONE]
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not os.path.isfile(p):
                continue
            out.write(f"{p}\t{st.st_size}\t{int(st.st_mtime)}\n")
