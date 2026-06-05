# Claude Code adapter

Claude Code discovers skills under `~/.claude/skills/<name>/SKILL.md`.
This plugin treats the whole repository as a self-contained skill —
SKILL.md is at its root, with `scripts/` and `web/` shipping alongside.

## Install

Pick one:

### A. Symlink (recommended, gets updates via `git pull`)

```bash
ln -s "$(pwd)" ~/.claude/skills/file-organizer
```

### B. Copy

```bash
mkdir -p ~/.claude/skills/file-organizer
cp -R ./* ~/.claude/skills/file-organizer/
```

## Verify

In a Claude Code session, type:

```
/skills
```

You should see `file-organizer` in the list with the description from
`SKILL.md`'s frontmatter.

## Invoke

Either:

- **Implicit**: ask in natural language — e.g. *"我要重置这台 Windows，先帮我核对一下文件有没有都迁过来"* or *"audit this machine before I wipe it"*. The `trigger_keywords` in SKILL.md (Chinese + English) include `migrate`, `wipe`, `audit files`, `文件收纳师`, `迁移`, etc.
- **Explicit**: `/file-organizer` (if your Claude Code version supports
  slash-named skills) or just paste `Skill({skill: "file-organizer"})`.

## What the skill does

Walks through the SKILL.md playbook step-by-step, calibrating the
exclusion list with you before any scan. See `../../SKILL.md` for the
full workflow.
