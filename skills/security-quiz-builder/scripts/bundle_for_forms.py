#!/usr/bin/env python3
"""
bundle_for_forms.py

Combines per-question markdown files (as written by the security-quiz-builder
skill) into a single markdown document formatted for Microsoft Forms import.

Usage:
    python bundle_for_forms.py <questions_folder> <output_file.md>

The output format is the one Microsoft Forms' "Quiz from a document" Copilot
import understands when fed via a Word doc or PDF: numbered questions, A-D
choices, correct answer marked, plus an answer key at the end.
"""

import sys
import re
from pathlib import Path


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
OPTION_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*([A-D])\.\s*(.+?)\s*$")
QUESTION_RE = re.compile(r"\*\*Question:\*\*\s*(.+?)(?=\n\n|\n-\s*\[)", re.DOTALL)
EXPLANATION_RE = re.compile(r"\*\*Explanation:\*\*\s*(.+?)$", re.DOTALL)


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def parse_question_file(path):
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    qm = QUESTION_RE.search(body)
    if not qm:
        raise ValueError(f"{path}: no **Question:** found")
    question_text = qm.group(1).strip()

    options = []
    correct_letter = None
    for line in body.splitlines():
        m = OPTION_RE.match(line)
        if m:
            marker, letter, text_ = m.groups()
            options.append((letter, text_))
            if marker.lower() == "x":
                if correct_letter is not None:
                    raise ValueError(f"{path}: multiple correct answers marked")
                correct_letter = letter

    if len(options) != 4:
        raise ValueError(f"{path}: expected 4 options, got {len(options)}")
    if correct_letter is None:
        raise ValueError(f"{path}: no correct answer marked")

    return {
        "path": path,
        "topic": meta.get("topic", path.stem),
        "number": int(meta.get("number", 0)),
        "difficulty": meta.get("difficulty", ""),
        "question": question_text,
        "options": options,
        "correct": correct_letter,
    }


def sort_key(q):
    return (q["topic"], q["number"], q["path"].name)


def render(questions):
    lines = ["# Quiz Import for Microsoft Forms", ""]
    lines.append(f"_{len(questions)} questions across "
                 f"{len({q['topic'] for q in questions})} topics_")
    lines.append("")
    lines.append("---")
    lines.append("")

    answer_key = []
    for i, q in enumerate(questions, start=1):
        lines.append(f"**{i}. {q['question']}**")
        lines.append("")
        for letter, text_ in q["options"]:
            marker = "*" if letter == q["correct"] else ""
            lines.append(f"{marker}{letter}. {text_}")
        lines.append("")
        answer_key.append((i, q["topic"], q["correct"], q["difficulty"]))

    lines.append("---")
    lines.append("")
    lines.append("## Answer Key")
    lines.append("")
    lines.append("| # | Topic | Answer | Difficulty |")
    lines.append("|---|-------|--------|------------|")
    for i, topic, ans, diff in answer_key:
        lines.append(f"| {i} | {topic} | {ans} | {diff} |")
    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)

    folder = Path(sys.argv[1])
    out = Path(sys.argv[2])

    if not folder.is_dir():
        print(f"error: {folder} is not a directory", file=sys.stderr)
        sys.exit(1)

    files = sorted(folder.glob("*.md"))
    files = [f for f in files if f.resolve() != out.resolve()]
    if not files:
        print(f"error: no .md files found in {folder}", file=sys.stderr)
        sys.exit(1)

    questions = []
    errors = []
    for f in files:
        try:
            questions.append(parse_question_file(f))
        except Exception as e:
            errors.append(str(e))

    if errors:
        print("Parse errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        if not questions:
            sys.exit(1)

    questions.sort(key=sort_key)
    out.write_text(render(questions), encoding="utf-8")
    print(f"Wrote {len(questions)} questions to {out}")
    if errors:
        print(f"({len(errors)} files skipped due to parse errors)")


if __name__ == "__main__":
    main()
