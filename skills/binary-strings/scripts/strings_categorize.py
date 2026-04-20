#!/usr/bin/env python3
"""
strings_categorize.py — Bucket filtered strings into security-relevant categories.

Part of the Claude Binary Strings Skill.

Usage:
    strings -a -n 6 <binary> | python3 strings_english.py | python3 strings_categorize.py
    python3 strings_categorize.py --json < filtered_strings.txt
    python3 strings_categorize.py --markdown < filtered_strings.txt
"""

import re
import sys
import json
import argparse
from collections import defaultdict


# ── Category patterns (ordered: first match wins within each string) ──────────

CATEGORIES = [
    ("CREDENTIALS", re.compile(
        r'(?i)\b(?:password|passwd|secret|token|api[_-]?key|bearer|'
        r'auth(?:orization)?|credential|passphrase|private[_-]?key|'
        r'access[_-]?key|client[_-]?secret|master[_-]?key|encryption[_-]?key)\b'
    )),
    ("CRYPTO", re.compile(
        r'-----BEGIN|-----END|PRIVATE KEY|PUBLIC KEY|CERTIFICATE|'
        r'RSA|EC (?:PRIVATE|PUBLIC|PARAMETERS)|'
        r'\b(?:AES|DES|3DES|RC4|RC2|ChaCha20|Salsa20|Blowfish|'
        r'SHA-?(?:1|256|384|512)|MD5|HMAC|PBKDF2|bcrypt|scrypt|'
        r'argon2|secp256[kr]1|curve25519|ed25519)\b',
        re.IGNORECASE
    )),
    ("REGISTRY", re.compile(
        r'HKEY_(?:LOCAL_MACHINE|CURRENT_USER|CLASSES_ROOT|USERS|CURRENT_CONFIG)'
        r'|SOFTWARE\\|SYSTEM\\CurrentControlSet|Run(?:Once)?\\',
        re.IGNORECASE
    )),
    ("COMMANDS", re.compile(
        r'(?i)\b(?:cmd\.exe|powershell(?:\.exe)?|bash|sh|/bin/sh|/bin/bash|'
        r'wget|curl|nc |netcat|ncat|exec\(|system\(|popen\(|'
        r'os\.system|subprocess|ShellExecute|WinExec|CreateProcess)\b'
    )),
    ("PATHS_UNIX", re.compile(
        r'^/(?:etc|var|tmp|usr|home|root|proc|sys|dev|opt|bin|sbin|lib)[/A-Za-z0-9_./-]*'
    )),
    ("PATHS_WINDOWS", re.compile(
        r'(?i)[A-Z]:\\(?:Windows|Users|Program Files|ProgramData|Temp|System32|'
        r'AppData|Documents)[\\A-Za-z0-9_./ -]*'
    )),
    ("URLS", re.compile(
        r'https?://[^\s"\'<>]{6,}|ftp://[^\s"\'<>]{4,}'
    )),
    ("IPS", re.compile(
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
        r'|(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}'   # IPv6
    )),
    ("DOMAINS", re.compile(
        r'\b(?:[a-zA-Z0-9-]{2,63}\.)+(?:com|net|org|io|gov|edu|mil|'
        r'ru|cn|de|uk|fr|jp|xyz|onion|local)\b'
    )),
    ("FORMAT_STRINGS", re.compile(
        r'%(?:[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcspn%])'
    )),
    ("DEBUG", re.compile(
        r'(?i)\b(?:assert|debug|warning|error|fatal|critical|verbose|'
        r'trace|TODO|FIXME|HACK|XXX|version|build|compiled|'
        r'__FILE__|__LINE__|__FUNCTION__)\b'
        r'|\.c:|\.cpp:|\.h:|\.py:'           # source file paths in assert messages
    )),
    ("NETWORK_PROTO", re.compile(
        r'(?i)\b(?:HTTP/[12]|HTTPS|FTP|SSH|SMTP|IMAP|POP3|DNS|DHCP|SNMP|'
        r'LDAP|SMB|RDP|VNC|MQTT|WebSocket|gRPC|REST|SOAP|'
        r'TLS|SSL|DTLS|mTLS)\b'
    )),
    ("MUTEX_HANDLES", re.compile(
        r'(?i)(?:mutex|semaphore|event|pipe|mailslot|Global\\\\|Local\\\\)'
        r'[A-Za-z0-9_-]{3,}'
    )),
    ("GUIDS", re.compile(
        r'\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
        r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?'
    )),
    ("EMAIL", re.compile(
        r'\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    )),
    ("BASE64_CANDIDATES", re.compile(
        r'^[A-Za-z0-9+/]{32,}={0,2}$'
    )),
]

MISC_CATEGORY = "MISC"


def categorize(line: str) -> str:
    for cat_name, pattern in CATEGORIES:
        if pattern.search(line):
            return cat_name
    return MISC_CATEGORY


def parse_args():
    parser = argparse.ArgumentParser(
        description="Categorize filtered strings into security-relevant buckets."
    )
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON.")
    parser.add_argument("--markdown", action="store_true",
                        help="Output as Markdown sections.")
    parser.add_argument("--no-misc", action="store_true",
                        help="Suppress MISC category in output.")
    parser.add_argument("--only", type=str, default=None,
                        help="Only show a specific category (e.g. --only CREDENTIALS).")
    return parser.parse_args()


def print_text(buckets, args):
    category_order = [cat for cat, _ in CATEGORIES] + [MISC_CATEGORY]
    for cat in category_order:
        items = buckets.get(cat, [])
        if not items:
            continue
        if args.no_misc and cat == MISC_CATEGORY:
            continue
        if args.only and cat != args.only.upper():
            continue
        print(f"\n{'='*60}")
        print(f"  [{cat}]  ({len(items)} items)")
        print(f"{'='*60}")
        for item in sorted(set(items)):
            print(f"  {item}")


def print_markdown(buckets, args):
    category_order = [cat for cat, _ in CATEGORIES] + [MISC_CATEGORY]
    for cat in category_order:
        items = buckets.get(cat, [])
        if not items:
            continue
        if args.no_misc and cat == MISC_CATEGORY:
            continue
        if args.only and cat != args.only.upper():
            continue
        print(f"\n## {cat} ({len(items)})\n")
        for item in sorted(set(items)):
            print(f"- `{item}`")


def main():
    args = parse_args()
    buckets = defaultdict(list)

    for line in sys.stdin:
        s = line.rstrip("\n")
        if not s:
            continue
        cat = categorize(s)
        buckets[cat].append(s)

    if args.json:
        out = {k: sorted(set(v)) for k, v in buckets.items()}
        print(json.dumps(out, indent=2))
    elif args.markdown:
        print_markdown(buckets, args)
    else:
        print_text(buckets, args)

    # Summary
    if not args.json:
        total = sum(len(v) for v in buckets.values())
        print(f"\n{'─'*60}")
        print(f"  SUMMARY: {total} strings categorized")
        for cat, _ in CATEGORIES:
            if buckets.get(cat):
                print(f"    {cat:<25} {len(buckets[cat]):>4}")
        if buckets.get(MISC_CATEGORY) and not args.no_misc:
            print(f"    {MISC_CATEGORY:<25} {len(buckets[MISC_CATEGORY]):>4}")


if __name__ == "__main__":
    main()
