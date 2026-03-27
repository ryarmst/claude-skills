#!/usr/bin/env python3
# generate_marketplace.py
#
# Supports two repo layouts:
#
#   Layout A — each plugin is a root-level folder (original assumption):
#     my-skill/
#       SKILL.md or SKILL.me
#       .claude-plugin/plugin.json  (optional)
#
#   Layout B — flat skills/ and agents/ folders (this repo's actual layout):
#     skills/
#       my-skill/
#         SKILL.md or SKILL.me
#     agents/
#       my-agent.md

import json
import re
from pathlib import Path

CONFIG = {
    "repo_owner": "ryarmst",
    "repo_name": "claude-skills",
    "owner_email": "your@email.com",
}

SKIP_DIRS = {'.claude-plugin', '.git', 'scripts', 'node_modules', '__pycache__'}

# Accept both .md and .me (typo variant in this repo)
SKILL_SUFFIXES = {".md", ".me"}


def find_skill_file(d: Path) -> Path | None:
    """Find SKILL.md or SKILL.me in a directory."""
    for suffix in SKILL_SUFFIXES:
        f = d / f"SKILL{suffix}"
        if f.exists():
            return f
    return None


def extract_description_from_skill(skill_file: Path) -> str | None:
    """Pull description from SKILL frontmatter, handles multi-line block scalar."""
    content = skill_file.read_text()
    # Match 'description: single line' or 'description: >\n  ...'
    match = re.search(
        r'^description:\s*(?:>\s*\n((?:[ \t]+.+\n?)+)|(.+))$',
        content, re.MULTILINE
    )
    if match:
        if match.group(1):
            # Block scalar — join indented lines
            return " ".join(line.strip() for line in match.group(1).splitlines()).strip()
        return match.group(2).strip()
    return None


def extract_description(plugin_dir: Path, skill_file: Path | None = None) -> str:
    # 1. plugin.json
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        data = json.loads(plugin_json.read_text())
        if desc := data.get("description"):
            return desc

    # 2. SKILL file frontmatter
    if skill_file and (desc := extract_description_from_skill(skill_file)):
        return desc

    # 3. README first non-heading line
    readme = plugin_dir / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]

    return f"{plugin_dir.name} plugin"


def extract_version(plugin_dir: Path) -> str | None:
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        data = json.loads(plugin_json.read_text())
        return data.get("version")
    return None


def collect_plugins(root: Path, repo_url: str) -> list[dict]:
    plugins = []

    # --- Layout B: skills/<skill-name>/SKILL.md|me ---
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.iterdir()):
            if not d.is_dir() or d.name.startswith('.'):
                continue
            skill_file = find_skill_file(d)
            if not skill_file:
                continue
            entry = {
                "name": d.name,
                "source": {
                    "source": "git-subdir",
                    "url": repo_url,
                    "path": f"skills/{d.name}"
                },
                "description": extract_description(d, skill_file),
            }
            if version := extract_version(d):
                entry["version"] = version
            plugins.append(entry)
            print(f"  ✓ skill: {d.name}")

    # --- Layout B: agents/<agent-name>.md (single-file agents) ---
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.iterdir()):
            if f.is_file() and f.suffix in SKILL_SUFFIXES:
                name = f.stem
                desc = extract_description_from_skill(f) or f"{name} agent"
                entry = {
                    "name": name,
                    "source": {
                        "source": "git-subdir",
                        "url": repo_url,
                        "path": f"agents"
                    },
                    "description": desc,
                    "tags": ["agent"]
                }
                plugins.append(entry)
                print(f"  ✓ agent: {name}")
            elif f.is_dir():
                # agents/<name>/ folder layout
                skill_file = find_skill_file(f)
                if not skill_file:
                    continue
                entry = {
                    "name": f.name,
                    "source": {
                        "source": "git-subdir",
                        "url": repo_url,
                        "path": f"agents/{f.name}"
                    },
                    "description": extract_description(f, skill_file),
                    "tags": ["agent"]
                }
                plugins.append(entry)
                print(f"  ✓ agent: {f.name}")

    # --- Layout A: root-level plugin folders (fallback) ---
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name in SKIP_DIRS or d.name.startswith('.'):
            continue
        if d.name in {"skills", "agents"}:
            continue  # already handled above
        skill_file = find_skill_file(d)
        has_plugin_json = (d / ".claude-plugin" / "plugin.json").exists()
        has_skills_subdir = (d / "skills").is_dir()
        if not (skill_file or has_plugin_json or has_skills_subdir):
            continue
        entry = {
            "name": d.name,
            "source": {
                "source": "git-subdir",
                "url": repo_url,
                "path": d.name
            },
            "description": extract_description(d, skill_file),
        }
        if version := extract_version(d):
            entry["version"] = version
        plugins.append(entry)
        print(f"  ✓ plugin: {d.name}")

    return plugins


def main():
    root = Path(".")
    repo_url = f"https://github.com/{CONFIG['repo_owner']}/{CONFIG['repo_name']}.git"

    print("Scanning repo...")
    plugins = collect_plugins(root, repo_url)

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
