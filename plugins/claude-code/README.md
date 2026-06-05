# Claude Code adapter

Claude Code discovers skills under `~/.claude/skills/<name>/SKILL.md`.
This plugin treats the whole repository as a self-contained skill —
SKILL.md is at its root, with `scripts/` and `web/` shipping alongside.

## Install

Pick one:

### A. Symlink (recommended, gets updates via `git pull`)

```bash
ln -s "$(pwd)" ~/.claude/skills/the-snap
```

### B. Copy

```bash
mkdir -p ~/.claude/skills/the-snap
cp -R ./* ~/.claude/skills/the-snap/
```

## Verify

In a Claude Code session, type:

```
/skills
```

You should see `the-snap` in the list with the description from
`SKILL.md`'s frontmatter.

## Invoke

Either:

- **Implicit**: ask in natural language — e.g. *"我要重置这台 Windows，先帮我核对一下文件有没有都迁过来"* or *"audit this machine before I wipe it"*. Claude decides from the `description` / `when_to_use` in SKILL.md, which list trigger phrases in Chinese + English (`migrate`, `wipe`, `audit files`, `响指`, `迁移`, …).
- **Explicit**: `/the-snap` (if your Claude Code version supports
  slash-named skills) or just paste `Skill({skill: "the-snap"})`.

## What the skill does

Walks through the SKILL.md playbook step-by-step, calibrating the
exclusion list with you before any scan. See `../../SKILL.md` for the
full workflow.
