#!/usr/bin/env python3
"""copy-scattered.py — turn the refined to-migrate.tsv (minus user-excluded
prefixes from exclude-state.json) into per-root `tar -T` / rsync file lists.

Each list holds paths relative to their root, forward slashes, UTF-8 no BOM:
  - Windows drive ``C:\\Users\\me\\x``  → bucket ``C``,    rel ``Users/me/x``
  - POSIX ``/home/me/x``               → bucket ``posix``, rel ``home/me/x``

How to consume the lists (see SKILL.md step 7):
  - Windows source (bsdtar): tar -T, iconv the list to GBK first.
  - unix source: rsync -a --files-from=list user@host:/ <landed>/

Output: index/scattered-<BUCKET>.list, plus a per-bucket count.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index")
TOMIG = os.path.join(IDX, "to-migrate.tsv")
EXCL = os.path.join(IDX, "exclude-state.json")


excluded = []
if os.path.exists(EXCL):
    excluded = [_paths.norm_key(x) for x in
                json.load(open(EXCL, encoding="utf-8")).get("excluded", [])]


def is_excluded(path):
    n = _paths.norm_key(path)
    for pre in excluded:
        if n == pre or n.startswith(pre + "\\"):
            return True
    return False


buckets = {}
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
        root, rel = _paths.split_root(path)
        bucket = _paths.segs_drive(path)[:-1] if _paths.segs_drive(path) else "posix"
        buckets.setdefault(bucket, []).append(rel)

for bucket, rels in buckets.items():
    out = os.path.join(IDX, f"scattered-{bucket}.list")
    with open(out, "w", encoding="utf-8", newline="\n") as w:
        for r in rels:
            w.write(r + "\n")
    print(f"{bucket}: {len(rels)} entries -> {out}")

print(f"total {total}  kept {kept}  dropped {dropped}")
