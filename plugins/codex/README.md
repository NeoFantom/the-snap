# Codex adapter

Codex (OpenAI Codex CLI) reads agent context from `AGENTS.md` and
project-rooted instructions. To make `the-snap` available as a
skill there:

## Install

### A. As a plugin (skills directory)

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)" ~/.codex/skills/the-snap
```

### B. As a project-rooted reference

Add to the project's `AGENTS.md`:

```markdown
## the-snap skill

For pre-wipe file audit / migration, follow the workflow in
@~/projects/the-snap/SKILL.md.
```

## Invoke

Mention the trigger phrases (see the `description` / `when_to_use` in
`../../SKILL.md`) — Codex will pick up the SKILL.md and follow its pipeline.
