# Codex adapter

Codex (OpenAI Codex CLI) reads agent context from `AGENTS.md` and
project-rooted instructions. To make `file-organizer` available as a
skill there:

## Install

### A. As a plugin (skills directory)

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)" ~/.codex/skills/file-organizer
```

### B. As a project-rooted reference

Add to the project's `AGENTS.md`:

```markdown
## file-organizer skill

For pre-wipe file audit / migration, follow the workflow in
@~/projects/file-organizer/SKILL.md.
```

## Invoke

Mention the trigger keywords (see `../../SKILL.md` frontmatter) — Codex
will pick up the SKILL.md and follow its step-by-step pipeline.
