# claude-skills

A collection of Claude Code skills and agents, installable as a plugin marketplace.

## Install

> **Note:** The recommended install method is the direct install below. The plugin-based install (`claude plugin install`) is affected by a [known Claude Code bug](https://github.com/anthropics/claude-code/issues/15178) where plugin skills are not injected into Claude's context, preventing auto-invocation.

Run this to install all skills and agents directly into `~/.claude/skills/` and `~/.claude/agents/`:
```bash
curl -fsSL https://raw.githubusercontent.com/ryarmst/claude-skills/main/install.sh | bash
```

Then restart Claude Code.

## Usage

Once installed, skills are auto-invoked by Claude when relevant, or triggered manually with `/skill-name`. Agents are available via `@agent-name`.

## Structure
```
claude-skills/
├── skills/
│   └── <skill-name>/
│       ├── .claude-plugin/plugin.json
│       └── SKILL.md
├── agents/
│   └── <agent-name>.md
├── install.sh                # direct install script
├── generate_marketplace.py   # regenerates marketplace.json + scaffolds plugin.json
└── .claude-plugin/
    └── marketplace.json      # auto-updated on every push
```

## Contributing

1. Add a new folder under `skills/` with a `SKILL.md` containing `name` and `description` frontmatter, or add a `.md` file under `agents/`
2. Push to `main` — `marketplace.json` and `plugin.json` files update automatically via GitHub Actions
