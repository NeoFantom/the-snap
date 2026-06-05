# OpenCode adapter

OpenCode reads workflow definitions from its skills/plugins directory
(varies by version). This plugin ships the same SKILL.md the other
adapters use.

## Install

```bash
mkdir -p ~/.opencode/skills
ln -s "$(pwd)" ~/.opencode/skills/file-organizer
```

If your OpenCode version uses a different convention (e.g.
`~/.config/opencode/plugins/`), adjust the path accordingly.

## Invoke

Mention any trigger keyword from `../../SKILL.md`'s frontmatter
(`migrate`, `wipe`, `audit files`, `文件收纳师`, ...) and OpenCode will
load the skill and walk through the pipeline.
