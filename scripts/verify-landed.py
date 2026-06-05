#!/usr/bin/env python3
"""verify-landed.py — for every entry in to-migrate.tsv (minus user-excluded
prefixes), stat the landed file and compare size against the manifest.

Mapping:  ``X:\\rel\\path``  →  ``<config.landed_root.path>/<rel/path>``
(forward slashes, drive letter dropped; matches the layout produced by
running ``tar -C X:/ -T scattered-X.list`` into that root.)

Outputs:
  index/verify-missing.tsv   missing or size-mismatched
  stdout                     summary counts
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load

cfg = load()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index")
LANDED = cfg["landed_root"]["path"]


def norm(p):
    return p.replace("/", "\\").rstrip("\\").lower()


excluded = []
excl_path = os.path.join(IDX, "exclude-state.json")
if os.path.exists(excl_path):
    excluded = [norm(x) for x in json.load(open(excl_path, encoding="utf-8")).get("excluded", [])]


def is_excluded(p):
    n = norm(p)
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
        rel = path[3:].replace("\\", "/")
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
