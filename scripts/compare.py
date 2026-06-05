#!/usr/bin/env python3
"""compare.py — layer-1 one-way completeness check.

Inputs:
  source.tsv     (from index-remote.ps1)
  reference.tsv  (from index-local.py)

Matches by (basename lowercase, size bytes). Files on the source whose
(name, size) pair is not present on the reference become the "missing"
candidate set. Method is intentionally over-reports rather than under
(safer for a wipe-prep audit).

Outputs:
  index/missing.tsv          — path \t size, one per missing candidate
  stdout                     — markdown report

Usage:
  python3 scripts/compare.py source.tsv reference.tsv > index/report-missing.md
"""
import sys
import os
import ntpath
from collections import defaultdict


def load(tsv, basename_fn):
    rows = []
    with open(tsv, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            path, size = parts[0], parts[1]
            rows.append((path, size, basename_fn(path).lower()))
    return rows


def main():
    src_tsv, ref_tsv = sys.argv[1], sys.argv[2]
    ref = load(ref_tsv, os.path.basename)
    ref_keys = set((name, size) for _, size, name in ref)

    src = load(src_tsv, ntpath.basename)
    present = 0
    missing = []
    for path, size, name in src:
        if (name, size) in ref_keys:
            present += 1
        else:
            missing.append((path, int(size)))

    os.makedirs("index", exist_ok=True)
    with open("index/missing.tsv", "w", encoding="utf-8") as mf:
        for path, size in missing:
            mf.write(f"{path}\t{size}\n")

    total = present + len(missing)
    by_root = defaultdict(lambda: [0, 0])
    for path, size in missing:
        drive = path.split("\\")[0]
        segs = path.split("\\")
        root = "\\".join(segs[:3]) if len(segs) >= 3 else drive
        by_root[root][0] += 1
        by_root[root][1] += size

    print("# Source-side missing-copy report (layer-1, name+size)\n")
    print(f"- Source total files: **{total}**")
    print(f"- Reference has (name+size match): **{present}**")
    print(f"- Missing-copy candidates: **{len(missing)}**")
    miss_gb = sum(s for _, s in missing) / 1024**3
    print(f"- Total candidate bytes: **{miss_gb:.2f} GB**\n")

    print("## By source root\n")
    print("| Root | Files | GB |")
    print("|---|---|---|")
    for root, (c, b) in sorted(by_root.items(), key=lambda x: -x[1][1]):
        print(f"| {root} | {c} | {b/1024**3:.2f} |")

    print("\n## Top 300 missing files (by size desc)\n")
    missing.sort(key=lambda x: -x[1])
    print("| Size MB | Path |")
    print("|---|---|")
    for path, size in missing[:300]:
        print(f"| {size/1024**2:.1f} | {path} |")


if __name__ == "__main__":
    main()
