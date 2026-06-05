#!/usr/bin/env python3
"""build-tree.py — turn a TSV (path\tsize[\tmtime]) into a nested-tree JSON
for the web UI. Aggregates directory size and file count; sorts each level
by size desc.

Usage: python3 scripts/build-tree.py index/missing.tsv web/tree.json
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "index/missing.tsv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "web/tree.json"

    root = {}
    nfiles = 0
    total = 0
    for line in open(src, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2:
            continue
        path, size = parts[0], int(parts[1])
        nfiles += 1
        total += size
        segs = _paths.segments(path)
        cur = root
        for i, seg in enumerate(segs):
            is_leaf = i == len(segs) - 1
            node = cur.get(seg)
            if node is None:
                node = {"children": {}, "size": 0, "count": 0, "isfile": is_leaf}
                cur[seg] = node
            if is_leaf:
                node["size"] = size
                node["count"] = 1
                node["isfile"] = True
            cur = node["children"]

    def agg(node):
        ts = tc = 0
        for e in node.values():
            if e["isfile"]:
                cs, cc = e["size"], 1
            else:
                cs, cc = agg(e["children"])
                e["size"], e["count"] = cs, cc
            ts += cs
            tc += cc
        return ts, tc

    agg(root)

    def to_list(node):
        out = []
        for name, e in node.items():
            item = {"name": name, "size": e["size"], "count": e["count"], "isfile": e["isfile"]}
            if not e["isfile"]:
                item["children"] = to_list(e["children"])
            out.append(item)
        out.sort(key=lambda x: (-x["size"], x["name"]))
        return out

    data = {"total_files": nfiles, "total_size": total, "tree": to_list(root)}
    json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"files={nfiles} size={total/1024**3:.2f}GB -> {dst}")


if __name__ == "__main__":
    main()
