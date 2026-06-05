#!/usr/bin/env python3
"""copy-scattered.py — turn the refined to-migrate.tsv (minus user-excluded
prefixes from exclude-state.json) into per-drive `tar -T` file lists.

Lists have:
  - paths relative to the drive root (e.g. ``Users/me/Desktop/foo.txt``)
  - forward slashes
  - UTF-8, no BOM

If the receiving end is Windows bsdtar, also iconv to GBK; see
METHODOLOGY.md section 5 ("tar -T on Windows").

Output: index/scattered-<DRIVE>.list, plus prints a per-drive count.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index")
TOMIG = os.path.join(IDX, "to-migrate.tsv")
EXCL = os.path.join(IDX, "exclude-state.json")


def norm(p):
    return p.replace("/", "\\").rstrip("\\").lower()


excluded = []
if os.path.exists(EXCL):
    excluded = [norm(x) for x in json.load(open(EXCL, encoding="utf-8")).get("excluded", [])]


def is_excluded(path):
    n = norm(path)
    for pre in excluded:
        if n == pre or n.startswith(pre + "\\"):
            return True
    return False


drives = {}
total = kept = dropped = 0
with open(TOMIG, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        path = line.split("\t")[0]
        total += 1
        if is_excluded(path):
            dropped += 1
            continue
        kept += 1
        drv = path[0].upper()
        rel = path[3:].replace("\\", "/")
        drives.setdefault(drv, []).append(rel)

for drv, rels in drives.items():
    out = os.path.join(IDX, f"scattered-{drv}.list")
    with open(out, "w", encoding="utf-8", newline="\n") as w:
        for r in rels:
            w.write(r + "\n")
    print(f"{drv}: {len(rels)} entries -> {out}")

print(f"total {total}  kept {kept}  dropped {dropped}")
