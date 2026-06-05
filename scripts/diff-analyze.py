#!/usr/bin/env python3
"""diff-analyze.py — bidirectional refinement of the to-migrate list.

Reads source.tsv and reference.tsv (and config.json), matches each source file
by basename in the reference, and classifies (METHODOLOGY 2.3, two layers):

  unique     : reference has no same-name file                 → migrate
  changed    : same name, different size                       → migrate (mtime tags newer side)
  present    : same name + same size AND size > hash_max_bytes  → assume copied (big file, size is enough)
  candidate  : same name + same size AND size <= hash_max_bytes → needs layer-2 hash to decide

Layer 2 is done next by hash-confirm.py: it hashes candidates on each machine
natively and turns them into present (drop) or changed-hash (migrate). Size is
only a pre-filter — a same-name file with a DIFFERENT size is content-different
for sure, so it is migrated without hashing.

Then strips (before classifying):
  - third-party clones (names in cfg.third_party_names in any path segment)
  - noise (cfg.ext_noise; hidden-dir segments; system files; checkpoints; ...)
  - cfg.skip_prefix (handled out-of-band) and cfg.user_drop (user said no)

Outputs:
  index/to-migrate.tsv   path \t size \t {unique, changed-S, changed-R}
  index/needs-hash.tsv   src_path \t size \t ref_path[ \t ref_path ...]
  index/report-migrate.md

Usage: python3 scripts/diff-analyze.py source.tsv reference.tsv
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import load
import _paths

cfg = load()
THIRD_PARTY = {s.lower() for s in cfg.get("third_party_names", [])}
SKIP_PREFIX = list(cfg.get("skip_prefix", []))
USER_DROP   = list(cfg.get("user_drop", []))
EXT_NOISE   = {e.lower() for e in cfg.get("ext_noise", [])}
HASH_MAX    = int(cfg.get("hash_max_bytes", 64 << 20))


def is_noise(name, path):
    n = name.lower()
    pl = path.lower()
    if os.path.splitext(n)[1] in EXT_NOISE:
        return True
    # any hidden-dir segment except the leaf → config/cache, drop
    if any(s.startswith(".") for s in _paths.segments(path)[:-1]):
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
    return any(seg.lower() in THIRD_PARTY for seg in _paths.segments(path))


def main():
    src_tsv, ref_tsv = sys.argv[1], sys.argv[2]

    ref = collections.defaultdict(list)          # basename → [(size, mtime), ...]
    ref_paths = collections.defaultdict(list)    # (basename, size) → [path, ...]
    for line in open(ref_tsv, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 2:
            continue
        name = _paths.basename(p[0]).lower()
        size = int(p[1])
        mtime = int(p[2]) if len(p) > 2 and p[2].lstrip("-").isdigit() else 0
        ref[name].append((size, mtime))
        ref_paths[(name, size)].append(p[0])
    ref_sizes = {k: set(s for s, _ in v) for k, v in ref.items()}

    present = 0
    unique = []
    changed = []
    candidates = []   # (src_path, size, [ref_path, ...])
    skip_third = skip_noise = skip_other = skip_drop = 0

    for line in open(src_tsv, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 3:
            continue
        path, size, mtime = p[0], int(p[1]), int(p[2])
        if any(path.startswith(pre) for pre in USER_DROP):
            skip_drop += 1; continue
        if any(path.startswith(pre) for pre in SKIP_PREFIX):
            skip_other += 1; continue
        if is_thirdparty(path):
            skip_third += 1; continue
        name = _paths.basename(path)
        if is_noise(name, path):
            skip_noise += 1; continue
        nl = name.lower()
        if nl in ref_sizes:
            if size in ref_sizes[nl]:
                # name + size match: big file → trust size; small → hash-confirm
                if size > HASH_MAX:
                    present += 1
                else:
                    candidates.append((path, size, ref_paths[(nl, size)]))
            else:
                r_newest = max(m for _, m in ref[nl])
                who = "S" if mtime > r_newest + 2 else "R"
                changed.append((path, size, who))
        else:
            unique.append((path, size))

    os.makedirs("index", exist_ok=True)
    with open("index/to-migrate.tsv", "w", encoding="utf-8") as f:
        for path, size in unique:
            f.write(f"{path}\t{size}\tunique\n")
        for path, size, who in changed:
            f.write(f"{path}\t{size}\tchanged-{who}\n")

    with open("index/needs-hash.tsv", "w", encoding="utf-8") as f:
        for path, size, rpaths in candidates:
            f.write(path + f"\t{size}\t" + "\t".join(rpaths) + "\n")

    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    for path, size in unique:
        a = agg[_paths.top_dir(path)]; a[0] += 1; a[1] += size
    for path, size, _ in changed:
        a = agg[_paths.top_dir(path)]; a[2] += 1; a[3] += size

    uniq_b = sum(s for _, s in unique)
    chg_b  = sum(s for _, s, _ in changed)
    chg_s  = sum(1 for *_, w in changed if w == "S")
    cand_b = sum(s for _, s, _ in candidates)

    lines = []
    lines.append("# Refined to-migrate report (bidirectional diff)\n")
    lines.append(f"- present (same name + same size, big file > hash_max_bytes): **{present}**")
    lines.append(f"- **candidates pending layer-2 hash (same name + same size, small): "
                 f"{len(candidates)} / {cand_b/1024**3:.2f} GB** → run hash-confirm.py")
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
