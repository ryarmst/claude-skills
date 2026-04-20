#!/usr/bin/env python3
"""
extract_strings.py — Pure-Python binary string extractor.

Use when the `strings` system utility is unavailable.
Supports ASCII, UTF-16 LE, and UTF-16 BE.

Part of the Claude Binary Strings Skill.

Usage:
    python3 extract_strings.py <binary> [--min-len 6] [--encoding ascii,utf16le,utf16be]
    python3 extract_strings.py <binary> | python3 strings_english.py
"""

import re
import sys
import argparse

PRINTABLE_ASCII = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}


def extract_ascii(data: bytes, min_len: int):
    """Extract null-terminated and newline-terminated ASCII strings."""
    current = []
    for byte in data:
        if byte in PRINTABLE_ASCII:
            current.append(chr(byte))
        else:
            if len(current) >= min_len:
                yield ''.join(current)
            current = []
    if len(current) >= min_len:
        yield ''.join(current)


def extract_utf16le(data: bytes, min_len: int):
    """Extract UTF-16 LE strings (common in Windows PE binaries)."""
    current = []
    i = 0
    while i + 1 < len(data):
        lo = data[i]
        hi = data[i + 1]
        if hi == 0 and lo in PRINTABLE_ASCII:
            current.append(chr(lo))
            i += 2
        else:
            if len(current) >= min_len:
                yield ''.join(current)
            current = []
            i += 1  # walk one byte to avoid missing embedded strings
    if len(current) >= min_len:
        yield ''.join(current)


def extract_utf16be(data: bytes, min_len: int):
    """Extract UTF-16 BE strings."""
    current = []
    i = 0
    while i + 1 < len(data):
        hi = data[i]
        lo = data[i + 1]
        if hi == 0 and lo in PRINTABLE_ASCII:
            current.append(chr(lo))
            i += 2
        else:
            if len(current) >= min_len:
                yield ''.join(current)
            current = []
            i += 1
    if len(current) >= min_len:
        yield ''.join(current)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract printable strings from a binary file."
    )
    parser.add_argument("binary", help="Path to binary file (use - for stdin).")
    parser.add_argument("--min-len", "-n", type=int, default=6,
                        help="Minimum string length (default: 6).")
    parser.add_argument("--encoding", "-e", type=str, default="ascii",
                        help="Comma-separated encodings: ascii,utf16le,utf16be (default: ascii).")
    parser.add_argument("--offset", action="store_true",
                        help="Prefix each string with its hex offset in the file.")
    return parser.parse_args()


def main():
    args = parse_args()
    encodings = [e.strip().lower() for e in args.encoding.split(",")]

    if args.binary == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(args.binary, "rb") as f:
            data = f.read()

    seen = set()
    results = []

    for enc in encodings:
        if enc == "ascii":
            gen = extract_ascii(data, args.min_len)
        elif enc == "utf16le":
            gen = extract_utf16le(data, args.min_len)
        elif enc == "utf16be":
            gen = extract_utf16be(data, args.min_len)
        else:
            print(f"[!] Unknown encoding: {enc}", file=sys.stderr)
            continue

        for s in gen:
            if s not in seen:
                seen.add(s)
                print(s)


if __name__ == "__main__":
    main()
