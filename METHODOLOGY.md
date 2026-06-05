# Methodology — the-snap

> Reusable principles + tested patterns for "audit & migrate before wipe"
> work. Separate from any project-specific execution log, which records
> *this run's* data and decisions.

## 1. The problem

A machine (the **source**) is about to be **wiped / decommissioned /
replaced**. Before pulling the trigger you must prove:

> Everything important on it already has a copy somewhere else
> (the **reference** — another machine, a backup drive, cloud).

Wipe is irreversible, so this is **not a sync task — it's a completeness
audit**. A file is not droppable until you've confirmed a copy exists.

Difficulties:

- Data is scattered (system drive, data drive, USB, multiple user-data roots).
- The source may be slow to access (remote SSH, USB).
- True *user-originated data* is buried under system files, caches,
  dependencies, third-party clones, and app-generated outputs.
- The same project folder may have **diverged** on both machines — "skip if
  reference already has it" misses source-side additions.

## 2. Core principles

### 2.1 One-way completeness check, not two-way sync

You care about **source-has, reference-lacks**. The final artifact is a
**gap list**. What the reference has that the source doesn't is irrelevant.
This framing drives every pruning decision downstream.

### 2.2 Index first, compare second

Direct `find` + per-file comparison on slow media (USB / remote SSH) is
infeasible. Scan each side once into a **lightweight index** (`path \t size
\t mtime`, no hashes yet) and do all comparisons on the indexes. One disk
read per side.

### 2.3 Layered comparison — control hash cost

Whole-disk hashing is too slow. Two layers:

1. Match by **name + size** (cheap, pure string/int compare). Different sizes
   → different content for sure; no hash needed. This kills ~99% of the budget.
2. On a name+size hit, **confirm by content sha256** — but only for files at or
   below a size threshold (`hash_max_bytes`, default 64 MiB). This catches the
   dangerous case (same name, same size, *different* content) that would
   otherwise be mistaken for an existing copy and lost. Larger files are trusted
   on name+size alone: a big file colliding on exact byte-size is vanishingly
   unlikely, and it is precisely the expensive thing to hash.

Hashing runs **natively on each machine** (remote `Get-FileHash`/`sha256sum`,
local `hashlib`); only `path → hash` crosses the wire, never the file. Results
are cached by `(path, size, mtime)` so re-runs are cheap.

> Lineage note: this two-layer scheme was the original design, but early
> versions stopped at layer 1 and never hashed. `hash-confirm.py` implements
> layer 2.

### 2.4 Noise exclusion — the make-or-break step

Most files on a machine are not user-originated. They're recoverable from
elsewhere and must be excluded, or the gap list is unreadable:

- **System / cache**: `Windows`, `Program Files`, `AppData` cache, `Temp`,
  `$Recycle.Bin`, …
- **Dependencies / build artifacts**: `node_modules`, `.git` internals,
  `__pycache__`, `target` / `dist` / `build`, `.venv`, …
- **Third-party clones**: public repos cloned via `git clone` (SDKs,
  tutorials) — re-clonable.
- **App-generated outputs**: simulation results, intermediate caches,
  `*-checkpoint.ipynb`, `.tmp`, … — recomputable.
- **Installers**: `.exe` / `.msi` / setup packages — re-downloadable.

Keep exclusion rules **concentrated at the top of the script**, declarative.
Every new noise class learned in the wild gets one line added — this is the
key to a self-evolving workflow.

### 2.5 Bidirectional diff handles divergence

The same project on both machines may have new work on either side. Naive
"reference has the folder → skip" misses source-side additions. Correct
approach for hand-edited directories: bidirectional comparison, three
classes:

- `present` — same name + same size → already migrated.
- `changed` — same name, different size → diverged; use `mtime` to pick the
  newer side.
- `unique` — reference has no same-name file → source-only; will be lost
  on wipe.

To-migrate = `unique` + `changed (source-newer)`.

### 2.6 Human review — machines can't judge "value"

The script excludes noise. It cannot decide whether "this experimental
dataset / that installer / those photos" are still wanted. The final step
is **visual human review**: render the to-migrate list as a collapsible
tree (filenames left-aligned, sizes right-aligned), let the human click to
keep / drop, export the final manifest.

### 2.7 Copy then verify

- Many small files: stream **one `tar` over ssh**, not per-file `scp` —
  avoids per-file handshake.
- After copy, verify file count and size against the manifest (optional
  hash for high-stakes subsets).

## 3. Standard procedure

```
1. Establish access      → can log into source, can read reference roots
2. Calibrate structure   → map drive letters, user-data regions, removable
                           media locations, existing sync relationships
3. Scope by size         → file counts / sizes per candidate dir; data-driven
                           narrowing of scan scope
4. Define exclusions     → centralize the noise / skip rules
5. Build indexes (both)  → row counts sane, CJK paths not garbled (any OS)
6. Layer-1 compare       → produce missing.tsv (name+size candidates)
7. Bidirectional diff    → strip third-party + noise → to-migrate.tsv + needs-hash.tsv
8. Hash-confirm (layer2) → sha256 small candidates natively → resolve present/changed
9. Human review (web)    → checkbox tree, export final selection
10. Copy + verify        → sample-compare source vs landed
11. Wire into ongoing    → fold the landed area into routine backup
                           (e.g. FreeFileSync)
```

## 4. Script inventory (`scripts/`)

| Script | Purpose |
|---|---|
| `index-remote.ps1` | Windows source: walk roots minus blacklist → `path\tsize\tmtime` TSV (mtime unix sec). |
| `index-local.py` | Cross-platform indexer (any OS): config mode locally, `--roots` arg mode over ssh. |
| `compare.py` | Layer-1 compare (name+size candidates) → `missing.tsv` + report. |
| `diff-analyze.py` | Bidirectional refine: strip third-party + noise → `to-migrate.tsv` + `needs-hash.tsv`. |
| `hash-confirm.py` | Layer-2: sha256 small name+size candidates natively → present / changed-hash. |
| `hash-remote.ps1` | Windows source-side hasher (`Get-FileHash`), reads paths on stdin. |
| `build-tree.py` | Build a nested-tree JSON from a TSV for the web UI. |
| `serve.py` | Static GET + `POST /api/state` to persist exclusion selections live to `exclude-state.json`. |
| `copy-scattered.py` | From `to-migrate.tsv`, drop excluded prefixes → per-root `tar`/`rsync` lists. |
| `verify-landed.py` | For every kept entry: stat the landed file, compare size against the manifest. |
| `_paths.py` / `_hash.py` | Helpers: separator-agnostic paths; cached sha256. |
| `web/index.html` | Collapsible tree browser: check to keep/drop (live persistence), right-click to copy path. |

## 5. Pitfalls & lessons

- **Cross-shell PowerShell delivery**: local bash → ssh → Windows shell
  multi-layer quoting will explode. Use `powershell -EncodedCommand
  <base64(UTF-16LE)>` to bypass quote and `$` escaping entirely.
- **CJK filenames**:
  - Set `[Console]::OutputEncoding = UTF8` before any PowerShell output.
  - Cross-machine copy via `tar` — Windows ships `bsdtar` which stores names
    as UTF-8; GNU `tar` on the receiving end decodes correctly. `dir` /
    `scp` may show mojibake in a GBK console but `tar` is unaffected.
- **Windows admin SSH passwordless setup**: the admin account is forced
  through `C:\ProgramData\ssh\administrators_authorized_keys`, ignoring
  the per-user `~/.ssh/authorized_keys`. Often refuses to accept keys for
  opaque reasons. **Workaround: use a non-admin account**; per-user
  authorized_keys works there.
- **Index slow media exactly once**: USB / exFAT / remote disks get one
  full scan; everything downstream operates on the index. Never re-walk to
  re-check a question.
- **Third-party libraries and app-generated outputs are the biggest noise
  source**: their file counts dwarf real user data. Skipping them keeps
  the to-migrate list within an order of magnitude of reality.
- **mtime units**: Windows .NET ticks (100ns since 0001-01-01) → unix
  epoch: `ticks/1e7 - 62135596800`.
- **Skip Windows junctions / reparse points**: during a full-disk walk,
  legacy paths like `All Users` → `ProgramData`, the user-profile's
  `Application Data` → `AppData`, `Default User` → `Default` are all
  junctions. PowerShell `Get-ChildItem` **follows them by default**,
  re-entering blacklisted system regions (a real run produced 4M rows and
  timed out). In the walker, check `$_.Attributes -band
  [IO.FileAttributes]::ReparsePoint` and skip. (Python `os.walk` defaults
  to `followlinks=False` and is unaffected.)
- **Whitelist vs blacklist**: prefer a blacklist on the reference (scan
  everything, exclude system / noise) — a whitelist may miss unexpected
  landing zones. On the source, *especially* blacklist — a missed file is
  a permanently lost file. Cost: handle junctions and noise.
- **Don't blanket-exclude "app shared-data roots"**: directories like
  `ProgramData` and `Public` on Windows are *mostly* application output
  (caches, models, binaries), but they also accumulate user-placed
  portable programs and data. A real run that excluded `ProgramData` by
  name buried: portable apps with self-converted data, a downloader's
  ProgramData payload, custom UI skins, and a multi-GB chat history from
  an older messaging-app version that still lived under its old
  `ProgramData\<App>` path. **Correct approach**: list the top level of
  these roots and review each child directory (manually or via a
  subagent), categorizing "app output → SKIP" vs "user content → KEEP".
  Same logic for vendor-driver caches (`swsetup`-style) — verify nothing
  hard-to-find lives there before excluding by name.
- **Incremental reuse**: re-walks are slow (USB / remote). Maintain a
  `SKIP_DONE` set of fully-indexed directories, scan only new regions,
  then concatenate old + delta indexes.
- **`tar -T` (file-list copy) on Windows**:
  1. In `cmd`, `-C "C:\"` becomes `\"` (escaped quote) — the path argument
     gets eaten. Use `-C C:/` (forward slash, no trailing backslash).
  2. Windows `bsdtar -T <list>` decodes the list using the **process
     locale** (system ANSI, often GBK on Chinese installs). Feeding UTF-8
     yields `Can't convert a path to a wchar_t string`. Convert the list
     with `iconv -f UTF-8 -t GBK` first. `chcp 65001` does **not** fix
     this — it only changes the console codepage, not `-T` decoding.
  3. Use paths relative to drive root with forward slashes.
  4. Post-copy verify: line count == landed file count, and spot-check
     sizes byte-exact.

## 6. Reusing on a new machine

1. Swap the access method (SSH / local mount / etc.).
2. Re-run **calibrate structure + scope by size** — every machine has a
   different layout; don't copy a whitelist verbatim.
3. Tune `index-remote.ps1`'s whitelist and `diff-analyze.py`'s
   `THIRD_PARTY` / `is_noise` to fit the actual layout discovered.
4. Run: index → compare → refine → web review → copy → verify.

> Steps are reusable; whitelists and exclusion rules are not. Each machine
> needs its own.

## 7. Evolvable design

- **Methodology (this file) is separate from execution log**: principles
  are stable, the data each run is unique. Keep them in different files
  so neither pollutes the other.
- **Exclusion rules: centralized and declarative**: all in top-of-script
  constants. New noise → one line, not a logic change.
- **Documents cross-reference and update on discovery**: any new pitfall
  (e.g. the bidirectional-diff oversight) updates the doc *before*
  changing the practice.
- **Indexes are intermediate artifacts, recomputable**: deleting
  `index/*.tsv` is fine — they regenerate. All downstream stages (compare,
  refine, web) are pure functions of the indexes, so rule changes only
  require re-running the back half of the pipeline.
