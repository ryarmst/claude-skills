# claude-skills

A collection of Claude Code skills and agents, installable as a plugin marketplace.

## Install

Add the marketplace to Claude Code:
```bash
claude plugin marketplace add ryarmst/claude-skills
```

Then install individual plugins:
```bash
claude plugin install <skill-name>@ryarmst
```

## Usage

Once installed, skills are auto-invoked by Claude when relevant, or triggered manually with `/skill-name`.

## Structure
```
claude-skills/
├── <skill-name>/
│   ├── .claude-plugin/plugin.json
│   └── skills/<skill-name>/SKILL.md
├── generate_marketplace.py   # regenerates marketplace.json
└── .claude-plugin/
    └── marketplace.json      # auto-updated on every push
```
