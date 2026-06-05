#!/usr/bin/env python3
"""verify-landed.py — for every entry in to-migrate.tsv (minus user-excluded
prefixes), stat the landed file and compare size against the manifest.

This is a TRANSFER-integrity check (did each file copy land at the right size),
which is a different concern from the name+hash content comparison done by
diff-analyze.py / hash-confirm.py during the audit.

Mapping (works for Windows and POSIX sources alike, via _paths.split_root):
  ``X:\\rel\\path``  →  ``<landed_root>/rel/path``   (drive dropped)
  ``/a/b/c``         →  ``<landed_root>/a/b/c``

Outputs:
  index/verify-missing.tsv   missing or size-mismatched
  stdout                     summary counts
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load
import _paths

cfg = load()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index")
LANDED = cfg["landed_root"]["path"]


excluded = []
excl_path = os.path.join(IDX, "exclude-state.json")
if os.path.exists(excl_path):
    excluded = [_paths.norm_key(x) for x in
                json.load(open(excl_path, encoding="utf-8")).get("excluded", [])]


def is_excluded(p):
    n = _paths.norm_key(p)
    for pre in excluded:
        if n == pre or n.startswith(pre + "\\"):
            return True
    return False


ok = 0
missing = []
size_mismatch = []
with open(os.path.join(IDX, "to-migrate.tsv"), encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        path, size_str = parts[0], parts[1]
        if is_excluded(path):
            continue
        expected = int(size_str)
        rel = _paths.split_root(path)[1]
        landed = os.path.join(LANDED, rel)
        try:
            actual = os.stat(landed).st_size
            if actual == expected:
                ok += 1
            else:
                size_mismatch.append((path, expected, actual))
        except FileNotFoundError:
            missing.append((path, expected))

with open(os.path.join(IDX, "verify-missing.tsv"), "w", encoding="utf-8") as w:
    w.write("# path\texpected_size\tactual_or_MISSING\n")
    for p, e in missing:
        w.write(f"{p}\t{e}\tMISSING\n")
    for p, e, a in size_mismatch:
        w.write(f"{p}\t{e}\t{a}\n")

print(f"OK: {ok}")
print(f"MISSING: {len(missing)}")
print(f"SIZE MISMATCH: {len(size_mismatch)}")
print(f"-> index/verify-missing.tsv")
