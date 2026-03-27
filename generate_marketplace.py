#!/usr/bin/env python3
# generate_marketplace.py
#
# Supports two repo layouts:
#
#   Layout A — each plugin is a root-level folder:
#     my-skill/
#       SKILL.md
#       .claude-plugin/plugin.json  (auto-created if missing)
#
#   Layout B — flat skills/ and agents/ folders (this repo's layout):
#     skills/
#       my-skill/
#         SKILL.md
#         .claude-plugin/plugin.json  (auto-created if missing)
#     agents/
#       my-agent.md                   (single-file agent)
#
# Also scaffolds missing .claude-plugin/plugin.json files so that
# `claude plugin install <n>@<marketplace>` works correctly.

import json
import re
from pathlib import Path

CONFIG = {
    # marketplace.json "name" must match what users type after @
    # e.g. `claude plugin install apk-decompile@ryarmst`
    "repo_owner": "ryarmst",
    "repo_name": "claude-skills",
    "owner_email": "your@email.com",
    "default_version": "1.0.0",
}

SKIP_DIRS = {'.claude-plugin', '.git', 'scripts', 'node_modules', '__pycache__'}


def find_skill_file(d: Path) -> Path | None:
    """Find SKILL.md in a directory."""
    f = d / "SKILL.md"
    return f if f.exists() else None


def extract_description_from_skill(skill_file: Path) -> str | None:
    """Pull description from SKILL frontmatter, handles multi-line block scalar."""
    content = skill_file.read_text()
    match = re.search(
        r'^description:\s*(?:>\s*\n((?:[ \t]+.+\n?)+)|(.+))$',
        content, re.MULTILINE
    )
    if match:
        if match.group(1):
            return " ".join(line.strip() for line in match.group(1).splitlines()).strip()
        return match.group(2).strip()
    return None


def load_plugin_json(plugin_dir: Path) -> dict:
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        return json.loads(plugin_json.read_text())
    return {}


def extract_description(plugin_dir: Path, skill_file: Path | None = None) -> str:
    data = load_plugin_json(plugin_dir)
    if desc := data.get("description"):
        return desc
    if skill_file and (desc := extract_description_from_skill(skill_file)):
        return desc
    readme = plugin_dir / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]
    return f"{plugin_dir.name} plugin"


def extract_version(plugin_dir: Path) -> str:
    data = load_plugin_json(plugin_dir)
    return data.get("version", CONFIG["default_version"])


def ensure_plugin_json(plugin_dir: Path, name: str, description: str, tags: list | None = None):
    """Create .claude-plugin/plugin.json if it doesn't already exist."""
    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json_path.exists():
        return
    plugin_json_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": name,
        "version": CONFIG["default_version"],
        "description": description,
        "author": {"name": CONFIG["repo_owner"]}
    }
    if tags:
        data["tags"] = tags
    plugin_json_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"    → scaffolded {plugin_json_path}")


def collect_plugins(root: Path, repo_url: str) -> list:
    plugins = []

    # --- Layout B: skills/<skill-name>/SKILL.md ---
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.iterdir()):
            if not d.is_dir() or d.name.startswith('.'):
                continue
            skill_file = find_skill_file(d)
            if not skill_file:
                continue
            description = extract_description(d, skill_file)
            ensure_plugin_json(d, d.name, description)
            plugins.append({
                "name": d.name,
                "version": extract_version(d),
                "source": {"source": "git-subdir", "url": repo_url, "path": f"skills/{d.name}"},
                "description": description,
            })
            print(f"  ✓ skill: {d.name}")

    # --- Layout B: agents/ ---
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                # Single-file agent — no dedicated folder, so no plugin.json scaffold
                name = f.stem
                desc = extract_description_from_skill(f) or f"{name} agent"
                plugins.append({
                    "name": name,
                    "version": CONFIG["default_version"],
                    "source": {"source": "git-subdir", "url": repo_url, "path": "agents"},
                    "description": desc,
                    "tags": ["agent"]
                })
                print(f"  ✓ agent: {name}")
            elif f.is_dir() and not f.name.startswith('.'):
                skill_file = find_skill_file(f)
                if not skill_file:
                    continue
                description = extract_description(f, skill_file)
                ensure_plugin_json(f, f.name, description, tags=["agent"])
                plugins.append({
                    "name": f.name,
                    "version": extract_version(f),
                    "source": {"source": "git-subdir", "url": repo_url, "path": f"agents/{f.name}"},
                    "description": description,
                    "tags": ["agent"]
                })
                print(f"  ✓ agent: {f.name}")

    # --- Layout A: root-level plugin folders (fallback) ---
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name in SKIP_DIRS or d.name.startswith('.'):
            continue
        if d.name in {"skills", "agents"}:
            continue
        skill_file = find_skill_file(d)
        has_plugin_json = (d / ".claude-plugin" / "plugin.json").exists()
        has_skills_subdir = (d / "skills").is_dir()
        if not (skill_file or has_plugin_json or has_skills_subdir):
            continue
        description = extract_description(d, skill_file)
        ensure_plugin_json(d, d.name, description)
        plugins.append({
            "name": d.name,
            "version": extract_version(d),
            "source": {"source": "git-subdir", "url": repo_url, "path": d.name},
            "description": description,
        })
        print(f"  ✓ plugin: {d.name}")

    return plugins


def main():
    root = Path(".")
    repo_url = f"https://github.com/{CONFIG['repo_owner']}/{CONFIG['repo_name']}.git"

    print("Scanning repo...")
    plugins = collect_plugins(root, repo_url)

    # name = repo_owner so users install with @ryarmst
    marketplace = {
        "name": CONFIG["repo_owner"],
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
    (out / "marketplace.json").write_text(json.dumps(marketplace, indent=2) + "\n")
    print(f"\nGenerated .claude-plugin/marketplace.json ({len(plugins)} plugins)")
    print(f"Install with: claude plugin install <name>@{CONFIG['repo_owner']}")
    print("Validate with: claude plugin validate .")


if __name__ == "__main__":
    main()
