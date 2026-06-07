---
name: the-snap
description: Audit a machine (or directory) before wipe/cleanup — index it and a reference, match files by name+content hash to find what exists ONLY on the doomed machine, review in a web tree, then copy and verify. Works for Windows, macOS, Linux, WSL on either side.
when_to_use: Use when a machine is about to be reset / wiped / decommissioned and the user wants to confirm everything important already has a copy elsewhere; when cleaning a fat C-drive and asking "what's actually unique here?"; or when collecting all files for a project/topic before archiving. Trigger phrases include "migrate", "migration", "wipe", "decommission", "before I reset this PC", "audit files", "what's unique on this machine", "C drive cleanup", "collect project files", as well as Chinese "响指", "文件整理", "迁移", "重置前".
---

# the-snap / 响指 — agent workflow

> One-shot "is everything safe before I wipe this?" audit + migration.
> Works for: PC handoff, C-drive cleanup, scoping a project's true file
> footprint, catching what FreeFileSync / robocopy / rsync hide.

> **Where commands run.** The scripts below live in this skill's own directory,
> and the pipeline writes its artifacts (`scripts/config.json`, `index/*.tsv`,
> `web/tree.json`) alongside them. Run every command from the skill directory —
> or prefix script paths with `${CLAUDE_SKILL_DIR}/` so they resolve no matter
> what the current working directory is. Paths below are written relative to the
> skill directory for readability.

## When to invoke this skill

Pattern-match against the user's intent (not just literal keywords):

- Source machine about to be **reset / wiped / replaced**, user wants to
  confirm everything important already has a copy elsewhere.
- Cleaning up a fat C-drive, user wants to know **what's actually unique**
  vs. what already lives on a backup / NAS / other machine.
- Gathering all files related to a project / topic before archiving.
- "I'm not sure if my backup tool covers X — can you double-check?"

Do **not** invoke for: ongoing sync (use FreeFileSync / Syncthing /
rsync), single-file copies, or git-managed code (just `git push`).

## What you produce

A reproducible pipeline that ends in three artifacts:

1. `index/to-migrate.tsv` — the refined source-only / source-newer file
   list, ready for human review.
2. `index/exclude-state.json` — the user's keep/drop selections from the
   web UI.
3. `<landed_root>/` — actually-copied files, size-verified against the
   manifest.

Plus markdown reports: `index/report-missing.md`, `index/report-migrate.md`.

## The standard pipeline

```
0. Calibrate         ← human + agent collaboration
1. Index source      ← index-remote.ps1 (Windows) | index-local.py over ssh (unix/WSL)
2. Index reference   ← scripts/index-local.py     (walk local roots)
3. Layer-1 compare   ← scripts/compare.py         → missing.tsv
4. Refine            ← scripts/diff-analyze.py    → to-migrate.tsv + needs-hash.tsv
5. Hash-confirm      ← scripts/hash-confirm.py    (layer 2: small-file content check)
6. Tree for web      ← scripts/build-tree.py      → web/tree.json
7. Human review      ← scripts/serve.py           ← exclude-state.json (live)
8. Copy              ← scripts/copy-scattered.py + tar/rsync over ssh
9. Verify            ← scripts/verify-landed.py
10. Apps inventory   ← scripts/apps-remote.ps1 + apps-extras.ps1
```

Run these *in order*. Each step is a pure function of the previous
artifacts, so re-running step N after editing a config only requires
re-running N onward.

## Division of labour: agent vs. human

This workflow is a **collaboration**, and the split is deliberate:

- **The agent does content/project-AGNOSTIC structural work** — index, group
  files by where they live (system / installed-app data / project / user docs),
  strip *generic* noise (build artifacts, caches, third-party clones, temp
  files). The agent must **not guess what is "important"** or decide what to
  discard based on a file's meaning.
- **The human makes the keep/delete calls** in the web tree, clicking which
  prefixes to drop. Content judgement is theirs.

When unsure whether something is *valuable*, surface it for the human; only
auto-drop what is noise by *structure*, never by *meaning*.

## Step-by-step playbook

### 0. Calibrate (human collab — do NOT skip)

Before any scanning, work with the user to fill in `scripts/config.json`
(copy from `scripts/config.example.json`):

- **source**: hostname, ssh user (prefer a non-admin account — see
  METHODOLOGY §5), drive letters to scan.
- **reference**: local mount roots where copies might already exist.
- **landed_root**: where new copies will land.
- **exclude_dirs**: start with the example list. **CRITICAL**: before
  adding `ProgramData`, `AppData`, or `Public`, get the user to confirm
  whether any user-placed portable apps or chat-history dumps live there.
  If unsure, **list the top level first** (one ssh, ten seconds) and
  classify each child as app-output vs. user-content. See METHODOLOGY §5
  pitfalls — this trap has eaten ~12 GB of chat history in a real run.

If the user says "just run it" without calibration, **stop and explain**
that the wrong exclusion list silently drops their data. Show the top
level of `ProgramData` / `AppData` and ask before proceeding.

### 1. Index source

Windows source (no Python needed on it):

```bash
B64=$(iconv -t UTF-16LE < scripts/index-remote.ps1 | base64 -w0)
ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $B64" > index/source.tsv
```

mac / linux / WSL source — pipe the Python indexer over ssh instead:

```bash
ssh "$USER@$HOST" python3 - --roots /home /data --exclude-name node_modules .git \
    < scripts/index-local.py > index/source.tsv
```

WSL crossing to its own Windows host? Don't walk `/mnt/c` — run the native
indexer (`powershell.exe -File scripts/index-remote.ps1`). See `docs/platforms.md`.

Expected: thousands–hundreds-of-thousands of lines. Spot-check that
CJK paths look right (not mojibake).

### 2. Index reference

```bash
python3 scripts/index-local.py > index/reference.tsv
```

If the reference includes a slow USB drive, allow time and don't
re-run lightly.

### 3. Layer-1 compare

```bash
python3 scripts/compare.py index/source.tsv index/reference.tsv > index/report-missing.md
```

Reports source files whose (basename, size) pair is missing from the
reference. Over-reports (safe direction). Outputs `index/missing.tsv`.
A (name, size) *hit* is only a candidate — content is confirmed in step 5.

### 4. Refine

```bash
python3 scripts/diff-analyze.py index/source.tsv index/reference.tsv
```

Strips third-party clones, build noise, hidden config, user-excluded
prefixes; bidirectional diff classifies `unique` / `changed` / `present` /
`candidate`. Outputs `index/to-migrate.tsv`, `index/needs-hash.tsv`, and
`index/report-migrate.md`.

If `report-migrate.md`'s top dirs include surprising entries (a build
tree, a cache, a third-party clone), update `config.json` and re-run
this step only.

### 5. Hash-confirm (layer 2)

```bash
python3 scripts/hash-confirm.py          # add --src-local if the source is this machine
```

Resolves the small-file candidates from `needs-hash.tsv` by content sha256,
hashed natively on each machine (Windows source uses `hash-remote.ps1` /
`Get-FileHash`; unix uses `sha256sum`; reference is hashed locally and cached).
Hash-equal → dropped as `present`; hash-different → appended to
`to-migrate.tsv` as `changed-hash`. Large files (> `hash_max_bytes`) were
already settled by name+size in step 4 and are not hashed.

### 6. Tree for web

```bash
python3 scripts/build-tree.py index/to-migrate.tsv web/tree.json
```

### 7. Human review

```bash
python3 scripts/serve.py
```

Open `http://localhost:26826/`. User clicks dirs/files to drop. Each
click POSTs the full exclusion list → `index/exclude-state.json` is
overwritten live; reload / restart preserves selections.

**Important**: this step is the only step *requiring* the user. Do not
proceed to copy until they confirm they're done reviewing.

### 8. Copy

```bash
python3 scripts/copy-scattered.py
```

Windows source — tar over ssh, per drive (CJK list must be GBK):

```bash
iconv -f UTF-8 -t GBK < index/scattered-C.list > index/scattered-C.gbk.list
scp index/scattered-C.gbk.list "$USER@$HOST:C:/tmp/"
ssh "$USER@$HOST" 'cmd /c "chcp 65001 >nul & cd C:/ & tar -cf - -T C:/tmp/scattered-C.gbk.list"' \
  | tar -xf - -C "$LANDED_ROOT/C"
```

unix source — rsync (UTF-8-clean, no GBK dance):

```bash
rsync -a --files-from=index/scattered-posix.list "$USER@$HOST:/" "$LANDED_ROOT"/
```

CJK / `tar -T` / `cmd` quote gotchas: see METHODOLOGY §5 and `docs/platforms.md`.

### 9. Verify

```bash
python3 scripts/verify-landed.py
```

Stat every landed file, compare against manifest. Expected: 0 missing,
0 size mismatch. Investigate any non-zero before declaring victory.

### 10. Apps inventory (parallel to file pipeline, can run any time)

```bash
ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $(iconv -t UTF-16LE < scripts/apps-remote.ps1   | base64 -w0)" > index/source.apps.tsv
ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $(iconv -t UTF-16LE < scripts/apps-extras.ps1   | base64 -w0)" > index/source.apps-extras.txt
# Optional but recommended for batch reinstall:
ssh "$USER@$HOST" 'powershell -NoProfile -Command "winget export --accept-source-agreements -o $env:TEMP\winget-export.json | Out-Null; Get-Content -Raw -Encoding UTF8 $env:TEMP\winget-export.json"' \
  > index/source.winget.json
```

`winget import index/source.winget.json` on the new machine replays the
subset reinstallable from winget sources. The rest needs manual install
per `apps-extras.txt`.

## Failure modes & recovery

- **`tar` reports `Can't convert a path to a wchar_t string`** on Windows
  → the file list isn't GBK. `iconv -f UTF-8 -t GBK` it first.
  METHODOLOGY §5.
- **`Get-ChildItem` runs forever (millions of rows)** → junctions are
  being followed. Confirm `index-remote.ps1` has the `ReparsePoint`
  skip. METHODOLOGY §5.
- **Verify reports "all files differ"** but file counts match → manifest
  has trailing `\r` from PowerShell output. Pipe through `tr -d '\r'`
  before diffing.
- **"`SimplePrograms` / app data is missing from the index"** → the
  exclude list ate `ProgramData` or `AppData` wholesale. Remove it and
  re-index that root specifically; see METHODOLOGY §5.

## Don't do these

- Don't whole-disk hash. Layer-1 (name+size) then hashing only the small
  name+size candidates (step 5) is enough for a wipe audit.
- Don't whitelist on the source — a missing dir is a permanently lost
  file. Use blacklist + careful top-level audit of shared-data roots.
- Don't claim "migration complete" without running step 9 (verify).
- Don't add `ProgramData` / `AppData` / `Public` to the exclude list
  without auditing their top level first.

## Tone for user updates

Concise. Report at major step boundaries (counts + size). Surface
anomalies immediately (large unexpected dirs, encoding errors,
verification mismatches). Don't narrate per-file progress.
