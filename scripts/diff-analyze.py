#!/usr/bin/env python3
"""diff-analyze.py — bidirectional refinement of the to-migrate list.

Reads source.tsv and reference.tsv (and config.json), then for each source
file matches by basename in the reference and classifies:

  present : same name + same size on reference → already migrated
  changed : same name, different size → diverged; mtime picks newer side
  unique  : reference has no same-name file → source-only

Then strips:
  - third-party clones (names in cfg.third_party_names appearing in any path segment)
  - noise (extensions in cfg.ext_noise; hidden-dir segments; system files;
    notebook checkpoints; etc.)
  - paths under cfg.skip_prefix (handled out-of-band)
  - paths under cfg.user_drop (user said don't migrate)

Outputs:
  index/to-migrate.tsv   path \t size \t {unique, changed-S, changed-R}
  index/report-migrate.md  per-top-dir aggregation + exclusion counts

Usage: python3 scripts/diff-analyze.py source.tsv reference.tsv
"""
import os
import sys
import ntpath
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load

cfg = load()
THIRD_PARTY = {s.lower() for s in cfg.get("third_party_names", [])}
SKIP_PREFIX = list(cfg.get("skip_prefix", []))
USER_DROP   = list(cfg.get("user_drop", []))
EXT_NOISE   = {e.lower() for e in cfg.get("ext_noise", [])}


def is_noise(name, path):
    n = name.lower(); pl = path.lower()
    if os.path.splitext(n)[1] in EXT_NOISE:
        return True
    # any hidden-dir segment except the leaf → config/cache, drop
    if any(s.startswith(".") for s in path.split("\\")[:-1]):
        return True
    if n in ("pagefile.sys", "hiberfil.sys", "swapfile.sys",
             "dumpstack.log.tmp", "dumpstack.log"):
        return True
    if n.startswith("ntuser.dat") or n.endswith((".dmp", ".blf", ".regtrans-ms")):
        return True
    if ".ipynb_checkpoints" in pl or "-checkpoint." in n:
        return True
    if n in ("desktop.ini", "thumbs.db", ".ds_store"):
        return True
    if n.startswith("~$") or n.endswith(".tmp"):
        return True
    return False


def is_thirdparty(path):
    return any(seg in THIRD_PARTY for seg in path.lower().split("\\"))


def ticks_to_epoch(t):
    # Windows .NET ticks (100ns since 0001-01-01) → unix epoch
    return t / 1e7 - 62135596800


def main():
    src_tsv, ref_tsv = sys.argv[1], sys.argv[2]

    ref = collections.defaultdict(list)  # basename → [(size, mtime), ...]
    for line in open(ref_tsv, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 2:
            continue
        name = os.path.basename(p[0]).lower()
        mtime = int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
        ref[name].append((int(p[1]), mtime))
    ref_sizes = {k: set(s for s, _ in v) for k, v in ref.items()}

    present = 0
    unique = []
    changed = []
    skip_third = skip_noise = skip_other = skip_drop = 0

    for line in open(src_tsv, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 3:
            continue
        path, size, ticks = p[0], int(p[1]), int(p[2])
        if any(path.startswith(pre) for pre in USER_DROP):
            skip_drop += 1; continue
        if any(path.startswith(pre) for pre in SKIP_PREFIX):
            skip_other += 1; continue
        name = ntpath.basename(path)
        if is_thirdparty(path):
            skip_third += 1; continue
        if is_noise(name, path):
            skip_noise += 1; continue
        nl = name.lower()
        if nl in ref_sizes:
            if size in ref_sizes[nl]:
                present += 1
            else:
                s_ep = ticks_to_epoch(ticks)
                r_newest = max(m for _, m in ref[nl])
                who = "S" if s_ep > r_newest + 2 else "R"
                changed.append((path, size, who))
        else:
            unique.append((path, size))

    os.makedirs("index", exist_ok=True)
    with open("index/to-migrate.tsv", "w", encoding="utf-8") as f:
        for path, size in unique:
            f.write(f"{path}\t{size}\tunique\n")
        for path, size, who in changed:
            f.write(f"{path}\t{size}\tchanged-{who}\n")

    def top_dir(path):
        segs = path.split("\\")
        # group by drive + first 2 segments
        return "\\".join(segs[:3])

    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    for path, size in unique:
        a = agg[top_dir(path)]; a[0] += 1; a[1] += size
    for path, size, _ in changed:
        a = agg[top_dir(path)]; a[2] += 1; a[3] += size

    uniq_b = sum(s for _, s in unique)
    chg_b  = sum(s for _, s, _ in changed)
    chg_s  = sum(1 for *_, w in changed if w == "S")

    lines = []
    lines.append("# Refined to-migrate report (bidirectional diff)\n")
    lines.append(f"- present (same name + same size on reference): **{present}**")
    lines.append(f"- **unique (source-only): {len(unique)} / {uniq_b/1024**3:.2f} GB**")
    lines.append(f"- **changed (same name, different size): {len(changed)} / "
                 f"{chg_b/1024**3:.2f} GB**  (source-newer {chg_s}, reference-newer {len(changed)-chg_s})")
    lines.append(f"- excluded — third-party {skip_third}, noise {skip_noise}, "
                 f"skip-prefix {skip_other}, user-drop {skip_drop}\n")
    lines.append("## Aggregation by source top-dir (to-migrate)\n")
    lines.append("| Dir | unique # | unique GB | changed # | changed GB |")
    lines.append("|---|---|---|---|---|")
    for d, (un, ub, cn, cb) in sorted(agg.items(), key=lambda x: -(x[1][1] + x[1][3])):
        lines.append(f"| {d} | {un} | {ub/1024**3:.2f} | {cn} | {cb/1024**3:.2f} |")

    open("index/report-migrate.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
