#!/usr/bin/env python3
"""
Fetch the current text of an ASVS requirement from the master branch.

Usage:
  python3 fetch_requirement_text.py <requirement_id>

Example:
  python3 fetch_requirement_text.py 1.2.4

Output: JSON with current requirement text, level, chapter, section.
"""

import sys
import json
import re
import urllib.request

REPO_RAW = "https://raw.githubusercontent.com/OWASP/ASVS/master/5.0/en"

# Chapter file naming follows 0xNN-V<n>-<topic>.md - we list candidates and try them.
# As of v5.0.0, the chapters are:
CHAPTER_FILES = [
    "0x10-V1-Encoding-and-Sanitization.md",
    "0x11-V2-Validation-and-Business-Logic.md",
    "0x12-V3-Web-Frontend-Security.md",
    "0x13-V4-API-and-Web-Service.md",
    "0x14-V5-File-Handling.md",
    "0x15-V6-Authentication.md",
    "0x16-V7-Session-Management.md",
    "0x17-V8-Authorization.md",
    "0x18-V9-Self-contained-Tokens.md",
    "0x19-V10-OAuth-and-OIDC.md",
    "0x20-V11-Cryptography.md",
    "0x21-V12-Secure-Communication.md",
    "0x22-V13-Configuration.md",
    "0x23-V14-Data-Protection.md",
    "0x24-V15-Secure-Coding-and-Architecture.md",
    "0x25-V16-Security-Logging-and-Error-Handling.md",
    "0x26-V17-WebRTC.md",
]

HEADERS = {"User-Agent": "ASVS-Research-Script/1.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [ERROR] {url}: {e}", file=sys.stderr)
        return None


def find_requirement(req_id):
    """req_id like '1.2.4' - chapter is the leading number."""
    chapter_num = req_id.split(".")[0]
    candidates = [f for f in CHAPTER_FILES if f"-V{chapter_num}-" in f]
    if not candidates:
        # Fallback: try all chapters
        candidates = CHAPTER_FILES

    for fname in candidates:
        url = f"{REPO_RAW}/{fname}"
        print(f"  [FETCH] {fname}", file=sys.stderr)
        content = fetch(url)
        if not content:
            continue

        # Look for the requirement row: | **X.Y.Z** | text | level |
        pattern = re.compile(
            r"\|\s*\*\*" + re.escape(req_id) + r"\*\*\s*\|\s*(.+?)\s*\|\s*([0-9])\s*\|"
        )
        m = pattern.search(content)
        if not m:
            continue

        text = m.group(1).strip()
        level = m.group(2).strip()

        # Find the chapter title (first H1)
        chapter_match = re.search(r"^#\s+(V\d+\s+.+?)$", content, re.MULTILINE)
        chapter_title = chapter_match.group(1).strip() if chapter_match else ""

        # Find the section title that the requirement lives under.
        # Walk backward from the requirement match to find the nearest "## VX.Y" heading.
        before = content[: m.start()]
        section_matches = re.findall(
            r"^##\s+(V\d+\.\d+\s+.+?)$", before, re.MULTILINE
        )
        section_title = section_matches[-1].strip() if section_matches else ""

        return {
            "requirement_id": req_id,
            "text": text,
            "level": level,
            "chapter": chapter_title,
            "section": section_title,
            "source_file": fname,
            "source_url": url,
        }

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_requirement_text.py <requirement_id>", file=sys.stderr)
        sys.exit(1)

    req_id = sys.argv[1]
    print(f"Looking up requirement {req_id}...", file=sys.stderr)
    result = find_requirement(req_id)

    if not result:
        print(f"\nERROR: Requirement {req_id} not found in any chapter file.", file=sys.stderr)
        print("It may have been renumbered, removed, or the chapter file list is stale.", file=sys.stderr)
        sys.exit(2)

    print(f"\nFound in {result['source_file']}:", file=sys.stderr)
    print(f"  Chapter: {result['chapter']}", file=sys.stderr)
    print(f"  Section: {result['section']}", file=sys.stderr)
    print(f"  Level:   L{result['level']}", file=sys.stderr)
    print(f"  Text:    {result['text'][:100]}...", file=sys.stderr)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
