#!/usr/bin/env python3
"""hash-confirm.py — layer 2: resolve the (name+size) candidates from
diff-analyze.py by content hash.

For each candidate (same name + same size on both sides, small enough per
hash_max_bytes), compute sha256 on each machine NATIVELY and compare:

  any reference twin's hash == source hash  → present  (drop, already have it)
  no match                                  → changed-hash (migrate)

Hashing never moves files across the wire — only path<TAB>hash does:
  - reference side: always this machine (hashlib, cached by path,size,mtime).
  - source side: local if the source is this machine / already mounted
    (--src-local), else over ssh using the source's own tool
    (Windows: Get-FileHash via hash-remote.ps1; unix: sha256sum).

Reads:  index/needs-hash.tsv   (src_path \t size \t ref_path[ \t ref_path...])
Writes: index/to-migrate.tsv   (appends 'changed-hash' rows; idempotent)
        index/hash-cache-ref.json
Usage:  python3 scripts/hash-confirm.py [--src-local]
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load
from _hash import HashCache, file_sha256

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "index")
NEEDS = os.path.join(IDX, "needs-hash.tsv")
TOMIG = os.path.join(IDX, "to-migrate.tsv")
HERE = os.path.dirname(os.path.abspath(__file__))


def read_candidates():
    rows = []
    if not os.path.exists(NEEDS):
        return rows
    for line in open(NEEDS, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        rows.append((parts[0], int(parts[1]), parts[2:]))  # src, size, [ref...]
    return rows


def hash_sources_local(paths):
    out = {}
    for p in paths:
        try:
            out[p] = file_sha256(p)
        except OSError:
            out[p] = None
    return out


def hash_sources_remote(paths, cfg):
    """Hash source paths on the remote machine using its native tool."""
    src = cfg["source"]
    target = f'{src.get("user", "")}@{src["host"]}' if src.get("user") else src["host"]
    osname = src.get("os", "windows").lower()
    out = {}
    if osname.startswith("win"):
        with open(os.path.join(HERE, "hash-remote.ps1"), "rb") as f:
            ps = f.read()
        b64 = subprocess.run(["iconv", "-t", "UTF-16LE"], input=ps,
                             capture_output=True, check=True).stdout
        import base64
        b64 = base64.b64encode(b64).decode()
        cmd = ["ssh", target, f"powershell -NoProfile -EncodedCommand {b64}"]
        stdin = ("\n".join(paths) + "\n").encode("utf-8")
    else:  # unix source: sha256sum, NUL-delimited paths
        cmd = ["ssh", target, "xargs -0 sha256sum"]
        stdin = b"\0".join(p.encode("utf-8") for p in paths)
    res = subprocess.run(cmd, input=stdin, capture_output=True)
    for line in res.stdout.decode("utf-8", "replace").splitlines():
        if osname.startswith("win"):
            if "\t" in line:
                p, h = line.rsplit("\t", 1)
                out[p] = h.strip().lower()
        else:
            # "sha256  path"
            parts = line.split(None, 1)
            if len(parts) == 2:
                out[parts[1]] = parts[0].strip().lower()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-local", action="store_true",
                    help="source files are reachable on this machine at their listed paths")
    args = ap.parse_args()

    cand = read_candidates()
    if not cand:
        print("no candidates (run diff-analyze.py first, or nothing to confirm)")
        return

    cfg = load()
    src_host = cfg.get("source", {}).get("host", "")
    local = args.src_local or src_host in ("", "localhost", "127.0.0.1", "::1")

    src_paths = [c[0] for c in cand]
    src_hashes = hash_sources_local(src_paths) if local else hash_sources_remote(src_paths, cfg)

    ref_cache = HashCache(os.path.join(IDX, "hash-cache-ref.json"))
    present = 0
    migrate = []  # (src_path, size)
    for src, size, refs in cand:
        sh = src_hashes.get(src)
        if sh is None:
            migrate.append((src, size)); continue  # can't hash → safer to migrate
        matched = any(ref_cache.get(r) == sh for r in refs)
        if matched:
            present += 1
        else:
            migrate.append((src, size))
    ref_cache.save()

    # Rewrite to-migrate.tsv: keep non-(changed-hash) rows, re-add fresh ones.
    kept = []
    if os.path.exists(TOMIG):
        for line in open(TOMIG, encoding="utf-8"):
            if not line.rstrip("\n").endswith("\tchanged-hash"):
                kept.append(line.rstrip("\n"))
    with open(TOMIG, "w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")
        for src, size in migrate:
            f.write(f"{src}\t{size}\tchanged-hash\n")

    print(f"candidates {len(cand)}  present(hash-equal) {present}  "
          f"migrate(changed-hash) {len(migrate)}")
    print("-> index/to-migrate.tsv updated")


if __name__ == "__main__":
    main()
