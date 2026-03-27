#!/usr/bin/env python3
# generate_marketplace.py

import json
import os
import re
from pathlib import Path

CONFIG = {
    "repo_owner": "ryarmst",
    "repo_name": "claude-skills",
    "owner_email": "your@email.com",
}

SKIP_DIRS = {'.claude-plugin', '.git', 'scripts', 'node_modules', '__pycache__'}

def extract_description(plugin_dir: Path) -> str:
    # 1. Try plugin.json
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        data = json.loads(plugin_json.read_text())
        if desc := data.get("description"):
            return desc

    # 2. Try SKILL.md frontmatter description
    skill_md = plugin_dir / "SKILL.md"
    if not skill_md.exists():
        # Check in skills/ subdirectory
        for skill_file in plugin_dir.glob("skills/*/SKILL.md"):
            skill_md = skill_file
            break

    if skill_md.exists():
        content = skill_md.read_text()
        match = re.search(r'^description:\s*(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

    # 3. First non-heading line of README
    readme = plugin_dir / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]

    return f"{plugin_dir.name} plugin"

def is_plugin(d: Path) -> bool:
    return (
        (d / ".claude-plugin" / "plugin.json").exists() or
        (d / "skills").is_dir() or
        (d / "SKILL.md").exists() or
        (d / "agents").is_dir()
    )

def extract_version(plugin_dir: Path) -> str | None:
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        data = json.loads(plugin_json.read_text())
        return data.get("version")
    return None

def main():
    root = Path(".")
    repo_url = f"https://github.com/{CONFIG['repo_owner']}/{CONFIG['repo_name']}.git"

    plugins = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name in SKIP_DIRS or d.name.startswith('.'):
            continue
        if not is_plugin(d):
            continue

        entry = {
            "name": d.name,
            "source": {
                "source": "git-subdir",
                "url": repo_url,
                "path": d.name
            },
            "description": extract_description(d),
        }

        if version := extract_version(d):
            entry["version"] = version

        plugins.append(entry)
        print(f"  ✓ {d.name}")

    marketplace = {
        "name": CONFIG["repo_name"],
        "owner": {
            "name": CONFIG["repo_owner"],
            "email": CONFIG["owner_email"]
        },
        "metadata": {
            "description": f"Claude Code skills and agents by {CONFIG['repo_owner']}",
            "homepage": f"https://github.com/{CONFIG['repo_owner']}/{CONFIG['repo_name']}"
        },
        "plugins": plugins
    }

    out = Path(".claude-plugin")
    out.mkdir(exist_ok=True)
    (out / "marketplace.json").write_text(json.dumps(marketplace, indent=2))
    print(f"\nGenerated .claude-plugin/marketplace.json ({len(plugins)} plugins)")
    print("Validate with: claude plugin validate .")

if __name__ == "__main__":
    main()
