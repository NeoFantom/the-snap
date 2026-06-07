# the-snap

**After the snap, only some of your files remain — you decide which ones.**

**the-snap finds the files that exist *only* on a machine you're about to wipe.**
It indexes that machine and a reference (your new PC / backup / NAS), matches
files by **name + content hash** so a file that merely *moved* isn't flagged or
copied twice, shows you the source-only files in a browser tree where you click
to keep or drop, then copies the survivors and verifies each one. Works when
either side is Windows, macOS, Linux, or WSL.

> A reproducible workflow for migrating, auditing, and pruning files across
> machines — built for the "PC about to be wiped, what did I forget?" moment,
> usable for any file-organizing chore.

📖 **中文说明 → [README.zh-CN.md](./README.zh-CN.md)**（项目中文名:**响指**）

**Status**: extracted from a real one-shot migration; APIs may shift before 1.0.

## Install

One command. It auto-detects your coding agent (Claude Code, Codex, OpenCode,
Cursor, … 70+) and drops the whole skill — scripts *and* the web UI — into its
skills folder:

```bash
npx skills add NeoFantom/the-snap
```

| | |
|---|---|
| All projects (user-level) | `npx skills add NeoFantom/the-snap -g` |
| A specific agent | `npx skills add NeoFantom/the-snap -a claude-code` |
| Preview, don't install | `npx skills add NeoFantom/the-snap --list` |
| Update later | `npx skills update the-snap` |

Powered by the [`skills`](https://github.com/vercel-labs/skills) CLI — no global
install, `npx` fetches it on demand.

<details><summary>Manual install (no npx)</summary>

The repo *is* the skill (SKILL.md at root, `scripts/` + `web/` alongside), so
just point your agent's skills folder at a clone:

```bash
git clone https://github.com/NeoFantom/the-snap
ln -s "$(pwd)/the-snap" ~/.claude/skills/the-snap   # Claude Code
# or ~/.codex/skills/the-snap · ~/.config/opencode/skill/the-snap · …
```

</details>

Once installed, just describe the job in natural language — *"audit this machine
before I wipe it"*, *"迁移"*, *"响指"* — and the agent loads the skill and walks
the pipeline. Trigger phrases live in `SKILL.md`'s `description` / `when_to_use`.

## What it does

Given two roots (source and reference) — typically *the old machine* and
*the new machine* — this toolkit:

1. **Indexes** both sides into TSVs (path, size, mtime) without recursing into
   black-listed system / cache / dependency directories. Any OS on either side.
2. **Compares** by **name + content hash**: small files whose name+size match are
   confirmed by sha256 (catching same-name-same-size-but-different-content), while
   large files (> `hash_max_bytes`) are matched by name+size — a big file almost
   never collides on size, and hashing it is the expensive case. Each file is
   classified `present` (already on reference), `changed` (different content), or
   `unique` (source-only). Hashing happens natively on each machine; files never
   travel just to be compared.
3. **Refines** the *to-migrate* list by stripping noise (build artifacts,
   third-party clones, hidden config dirs, user-declared drops).
4. **Serves** an interactive tree at `http://localhost:<hash-port>/` where you
   click to exclude prefixes; selections persist live to JSON.
5. **Copies** the refined set, preserving non-ASCII (CJK/emoji) filenames
   (`tar`-over-ssh for Windows sources, `rsync` for unix).
6. **Verifies** every landed file by size against the manifest.

Designed for: pre-wipe migration; C-drive cleanup; project-file collection;
catching what got missed by file-sync tools that exclude shared-data roots.

## Why it exists

File-sync tools (FreeFileSync, robocopy, rsync) mirror trees but don't tell
you *what's unique vs. already-elsewhere*. Disk visualizers (WinDirStat,
TreeSize) show sizes but lose track during a real audit. AI agents can drive
the workflow but need a structured skill to follow — that's what
`SKILL.md` provides.

Two pitfalls this toolkit specifically catches (see `METHODOLOGY.md`):

- **Blacklist roots are dangerous**. Excluding `ProgramData` or `AppData` by
  name buries user-placed portable programs (e.g. several GB of chat
  histories from older app versions).
- **`tar -T` reads the file-list using the system ANSI codepage on Windows**
  (typically GBK on Chinese locale), not UTF-8. Converting the list with
  `iconv -t GBK` is required for CJK paths to survive.

## Layout

```
.
├── README.md           # this file
├── LICENSE             # MIT
├── SKILL.md            # step-by-step workflow for AI agents
├── METHODOLOGY.md      # principles + tested patterns (anonymized)
├── scripts/            # cross-platform: PowerShell indexer + Python pipeline
│   ├── config.example.json   # copy to config.json, then edit
│   └── check-no-pii.sh       # guard: fail if private data leaks in
├── web/                # interactive tree-exclude UI (no build, just open)
│   └── tree.json.example     # anonymized sample data
└── docs/               # platforms.md — per-OS & WSL/cross-VM recipes
```

## Quick start

```bash
# 0. Configure (host, ssh user, drives, exclusions) — read the inline comments
cp scripts/config.example.json scripts/config.json && $EDITOR scripts/config.json

# 1. Index the machine you're about to wipe (the "source")
#    Windows source (no Python needed there):
B64=$(iconv -t UTF-16LE < scripts/index-remote.ps1 | base64 -w0)
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -NoProfile -EncodedCommand $B64" > index/source.tsv
#    mac / linux / WSL source instead: pipe the Python indexer over ssh
#    ssh "$REMOTE_USER@$REMOTE_HOST" python3 - --roots /home /data < scripts/index-local.py > index/source.tsv
#    (WSL crossing to its Windows host? see docs/platforms.md — index natively, don't walk /mnt/c)

# 2. Index the local reference (roots come from config.json)
python3 scripts/index-local.py > index/reference.tsv

# 3. Compare, refine, then confirm small-file candidates by content hash
python3 scripts/compare.py index/source.tsv index/reference.tsv > index/report-missing.md
python3 scripts/diff-analyze.py index/source.tsv index/reference.tsv
python3 scripts/hash-confirm.py        # add --src-local if the source is this machine

# 4. Build the tree and audit interactively (browser persists clicks to JSON)
python3 scripts/build-tree.py index/to-migrate.tsv web/tree.json
python3 scripts/serve.py
# open http://localhost:<port>/

# 5. Copy the refined set (Windows: tar-over-ssh; unix: rsync — see SKILL.md step 7)
python3 scripts/copy-scattered.py

# 6. Verify every landed file by size
python3 scripts/verify-landed.py
```

Full step-by-step (incl. the exact tar/rsync commands, CJK/encoding gotchas,
and per-platform recipes): see `SKILL.md` and `docs/platforms.md`.

## Status & roadmap

Pre-1.0. Current limitations:

- Content hashing is **name+size-gated**: it confirms small (≤ `hash_max_bytes`)
  name+size matches by sha256, and trusts name+size for larger files. This is a
  deliberate trade-off (whole-disk hashing is too slow) — a large file with a
  colliding size but different content would be treated as already-present.
- Source indexing: Windows uses `index-remote.ps1` (no Python required there);
  macOS / Linux / WSL pipe `index-local.py` over ssh.
- `tar`-over-ssh assumes the remote has `bsdtar` (Windows 10+ ships it); unix
  sources use `rsync` instead.

## License

MIT — see `LICENSE`.
