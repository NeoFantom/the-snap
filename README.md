# 文件收纳师 / file-organizer

> A reproducible workflow for migrating, auditing, and pruning files across
> machines — built for the "PC about to be wiped, what did I forget?" moment,
> usable for any file-organizing chore.

**Status**: extracted from a real one-shot migration; APIs may shift before 1.0.

## What it does

Given two roots (source and reference) — typically *the old machine* and
*the new machine* — this toolkit:

1. **Indexes** both sides into TSVs (path, size, mtime) without recursing into
   black-listed system / cache / dependency directories.
2. **Compares** by name+size: classifies each file as `present` (already on
   reference), `changed` (same name, different size), or `unique` (source-only).
3. **Refines** the *to-migrate* list by stripping noise (build artifacts,
   third-party clones, hidden config dirs, user-declared drops).
4. **Serves** an interactive tree at `http://localhost:<hash-port>/` where you
   click to exclude prefixes; selections persist live to JSON.
5. **Copies** the refined set, preserving non-ASCII (CJK/emoji) filenames via
   `tar`-over-ssh with explicit encoding handling.
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
└── plugins/            # adapter manifests for claude-code / codex / opencode
```

## Quick start

```bash
# 0. Configure (host, ssh user, drives, exclusions) — read the inline comments
cp scripts/config.example.json scripts/config.json && $EDITOR scripts/config.json

# 1. Index the remote (Windows) machine you're about to wipe
B64=$(iconv -t UTF-16LE < scripts/index-remote.ps1 | base64 -w0)
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -NoProfile -EncodedCommand $B64" \
    > index/source.tsv

# 2. Index the local reference (roots come from config.json)
python3 scripts/index-local.py > index/reference.tsv

# 3. Compare, then diff & refine to the to-migrate list
python3 scripts/compare.py index/source.tsv index/reference.tsv > index/report-missing.md
python3 scripts/diff-analyze.py index/source.tsv index/reference.tsv

# 4. Build the tree and audit interactively (browser persists clicks to JSON)
python3 scripts/build-tree.py index/to-migrate.tsv web/tree.json
python3 scripts/serve.py
# open http://localhost:<port>/

# 5. Copy the refined set (tar-over-ssh; see SKILL.md step 7 for CJK handling)
python3 scripts/copy-scattered.py

# 6. Verify every landed file by size
python3 scripts/verify-landed.py
```

Full step-by-step (incl. the exact tar-over-ssh commands and CJK/encoding
gotchas): see `SKILL.md`.

## Installing as an agent skill

Each `plugins/<agent>/` directory is a self-contained manifest pointing at
`SKILL.md`. Symlink or copy into the agent's skill folder:

- **Claude Code**: `~/.claude/skills/file-organizer/` → `plugins/claude-code/`
- **Codex**: see `plugins/codex/README.md`
- **OpenCode**: see `plugins/opencode/README.md`

The agent will autoload the skill when the user mentions "migrate", "audit
files", "what's unique on this machine", etc.

## Status & roadmap

Pre-1.0. Current limitations:

- The `index-remote.ps1` script is Windows-only. macOS / Linux source indexing
  uses `index-local.py` for now.
- Diff is name+size; no content hashing (deliberate — full-disk hashing is
  too slow for the audit workflow). Pluggable hash check is on the roadmap.
- `tar`-over-ssh assumes the remote has `bsdtar` (Windows 10+ ships it). For
  Unix sources, GNU tar works fine.

## License

MIT — see `LICENSE`.
