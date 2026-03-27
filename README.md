# claude-skills

A collection of Claude Code skills and agents, installable as a plugin marketplace.

## Install

Add the marketplace to Claude Code:
```bash
claude plugin marketplace add ryarmst/claude-skills
```

Install all skills and agents in one shot:
```bash
curl -s https://raw.githubusercontent.com/ryarmst/claude-skills/main/.claude-plugin/marketplace.json | python3 -c "import json,sys; [print(p['name']) for p in json.load(sys.stdin)['plugins']]" | xargs -I{} claude plugin install {}@ryarmst
```

Or install individually:
```bash
claude plugin install <skill-name>@ryarmst
```

## Usage

Once installed, skills are auto-invoked by Claude when relevant, or triggered manually with `/skill-name`.

## Structure
```
claude-skills/
├── skills/
│   └── <skill-name>/
│       ├── .claude-plugin/plugin.json
│       └── SKILL.md
├── agents/
│   └── <agent-name>.md
├── generate_marketplace.py   # regenerates marketplace.json + scaffolds plugin.json
└── .claude-plugin/
    └── marketplace.json      # auto-updated on every push
```

## Contributing

1. Add a new folder under `skills/` or `agents/` with a `SKILL.md` containing `name` and `description` frontmatter
2. Push to `main` — `marketplace.json` and `plugin.json` files update automatically via GitHub Actions
