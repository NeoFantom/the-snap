#!/usr/bin/env python3
"""index-local.py — cross-platform filesystem indexer. Emits TSV to stdout.

Format: <path>\t<size bytes>\t<mtime unix seconds>   (same on every OS)

Two ways to run:

  Local reference walk (reads ./config.json, $FO_CONFIG, default side):
      python3 index-local.py > reference.tsv
      python3 index-local.py --side reference > reference.tsv

  Remote source over ssh (no config on the remote — pass roots/excludes):
      ssh host python3 - --roots /home /data --exclude-name node_modules .git \
          < scripts/index-local.py > source.tsv

This is the indexer for any mac / linux / WSL tree, local or remote. Windows
sources without Python use index-remote.ps1 instead.

WSL / cross-VM note: walking a Windows drive from inside WSL (a /mnt/c drvfs
mount) or another distro (9p) is slow and loses mtime precision. Index each
tree on its OWN OS and compare the TSVs — see docs/platforms.md. This script
warns on stderr when a root sits on such a filesystem.
"""
import argparse
import os
import sys

# Sensible cross-platform defaults for arg-mode (remote, no config.json).
DEFAULT_EXCLUDES = [
    "node_modules", ".git", "__pycache__", ".cache",
    "target", "dist", "build", ".gradle", ".conda", ".venv", "venv",
    ".idea", ".vscode", ".ipynb_checkpoints",
    "$Recycle.Bin", "System Volume Information", "Windows",
]


def crossing_vm_warning(roots):
    """Warn if any root lives on a drvfs/9p/cifs mount (WSL→Windows or
    cross-distro / network) where native indexing would be far better."""
    try:
        mounts = []  # (mountpoint, fstype)
        with open("/proc/mounts", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    mounts.append((parts[1], parts[2]))
    except OSError:
        return
    SLOW = {"drvfs", "9p", "cifs", "v9fs"}
    for root in roots:
        ar = os.path.abspath(root)
        best = max((m for m in mounts if ar == m[0] or ar.startswith(m[0].rstrip("/") + "/")),
                   key=lambda m: len(m[0]), default=None)
        if best and best[1] in SLOW:
            print(f"warning: {root} is on a '{best[1]}' mount (crossing the "
                  f"WSL/VM boundary). Indexing it here is slow and mtime may "
                  f"drift; prefer indexing it natively — see docs/platforms.md.",
                  file=sys.stderr)


def walk(roots, exclude_names, skip_paths, out):
    exclude = set(exclude_names)
    skip = set(skip_paths)
    for root in roots:
        if not os.path.isdir(root):
            print(f"skip (not a dir): {root}", file=sys.stderr)
            continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs
                       if d not in exclude
                       and os.path.join(dirpath, d) not in skip]
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if not os.path.isfile(p):
                    continue
                out.write(f"{p}\t{st.st_size}\t{int(st.st_mtime)}\n")


def main():
    ap = argparse.ArgumentParser(description="Cross-platform TSV indexer.")
    ap.add_argument("--side", choices=["reference", "source"], default="reference",
                    help="which config section to read when --roots is absent")
    ap.add_argument("--roots", nargs="+",
                    help="override roots to walk (enables config-less arg mode)")
    ap.add_argument("--exclude-name", nargs="*", dest="exclude_name",
                    help="directory names to prune anywhere in the tree")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="absolute paths to skip entirely")
    args = ap.parse_args()

    if args.roots:  # arg mode — no config needed (remote-friendly)
        roots = args.roots
        excludes = args.exclude_name if args.exclude_name is not None else DEFAULT_EXCLUDES
        skip = args.skip
    else:           # config mode
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _config import load
        cfg = load()
        section = cfg[args.side]
        roots = section["roots"]
        skip = list(section.get("skip_done", section.get("skip_full", [])))
        excludes = cfg["exclude_dirs"]

    crossing_vm_warning(roots)
    walk(roots, excludes, skip, sys.stdout)


if __name__ == "__main__":
    main()
