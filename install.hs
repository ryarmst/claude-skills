#!/bin/bash
# install.sh — installs all skills and agents from ryarmst/claude-skills directly
# into ~/.claude/skills/ and ~/.claude/agents/ so Claude Code picks them up automatically.

set -e

REPO="https://github.com/ryarmst/claude-skills.git"
TMP=$(mktemp -d)
SKILLS_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.claude/agents"

echo "Cloning ryarmst/claude-skills..."
git clone --depth=1 "$REPO" "$TMP" --quiet

mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

# Install skills (each is a folder containing SKILL.md)
echo ""
echo "Installing skills → $SKILLS_DIR"
for skill in "$TMP"/skills/*/; do
  name=$(basename "$skill")
  rm -rf "$SKILLS_DIR/$name"
  cp -r "$skill" "$SKILLS_DIR/$name"
  echo "  ✓ $name"
done

# Install agents (each is a single .md file)
echo ""
echo "Installing agents → $AGENTS_DIR"
for agent in "$TMP"/agents/*.md; do
  name=$(basename "$agent")
  cp "$agent" "$AGENTS_DIR/$name"
  echo "  ✓ $name"
done

rm -rf "$TMP"

echo ""
echo "Done. Restart Claude Code to pick up the new skills and agents."
