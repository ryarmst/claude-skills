#!/usr/bin/env python3
"""
strings_english.py — Filter raw strings output to keep human-readable English text.

Based on the approach by Gabriel González García (gabrielcybersecurity.com):
  https://github.com/ggonzalez/CyberSecurity-KnowledgeBase/blob/main/ReverseEngineering/strings_english.py

Extended for the Claude Binary Strings Skill with:
  - More robust bigram coverage
  - Crypto/URL/IP fast-path detection
  - Output scoring mode for ranking
  - Optional word-list path override

Usage:
    strings -a -n 6 <binary> | python3 strings_english.py
    strings -a -n 6 <binary> | python3 strings_english.py --negate
    strings -a -n 6 <binary> | python3 strings_english.py --score    # show score per line
"""

import ipaddress
import argparse
import math
import sys
import re
from collections import Counter

debug_enabled = False

# ── English letter frequencies (from Wikipedia / Norvig) ──────────────────────
EN_FREQ = {
    'a': 0.08167, 'b': 0.01492, 'c': 0.02782, 'd': 0.04253,
    'e': 0.12702, 'f': 0.02228, 'g': 0.02015, 'h': 0.06094,
    'i': 0.06966, 'j': 0.00153, 'k': 0.00772, 'l': 0.04025,
    'm': 0.02406, 'n': 0.06749, 'o': 0.07507, 'p': 0.01929,
    'q': 0.00095, 'r': 0.05987, 's': 0.06327, 't': 0.09056,
    'u': 0.02758, 'v': 0.00978, 'w': 0.02360, 'x': 0.00150,
    'y': 0.01974, 'z': 0.00074,
}

# ── Bigrams — extended set for better recall ───────────────────────────────────
BIGRAM_FREQ = {
    "th": 0.0356, "he": 0.0307, "in": 0.0243, "er": 0.0205,
    "an": 0.0199, "re": 0.0185, "on": 0.0176, "at": 0.0149,
    "en": 0.0145, "nd": 0.0135, "ti": 0.0134, "es": 0.0134,
    "or": 0.0128, "te": 0.0120, "of": 0.0117, "ed": 0.0117,
    "is": 0.0113, "it": 0.0112, "al": 0.0109, "ar": 0.0107,
    "st": 0.0105, "to": 0.0104, "nt": 0.0104, "ng": 0.0095,
    "se": 0.0093, "ha": 0.0093, "as": 0.0087, "ou": 0.0087,
    "io": 0.0083, "le": 0.0083, "ve": 0.0083, "co": 0.0079,
    "me": 0.0079, "de": 0.0076, "hi": 0.0076, "ri": 0.0073,
    "ro": 0.0073, "ic": 0.0070, "ne": 0.0069, "ea": 0.0069,
    "ra": 0.0069, "ce": 0.0065,
}

# ── Fallback dictionary if words_alpha.txt not available ──────────────────────
FALLBACK_DICT = {
    "error", "file", "user", "login", "network", "version", "failed", "success",
    "config", "system", "password", "key", "token", "secret", "server", "client",
    "request", "response", "data", "load", "save", "read", "write", "open",
    "close", "connect", "send", "receive", "path", "name", "type", "value",
    "time", "date", "host", "port", "address", "memory", "buffer", "size",
    "count", "index", "status", "code", "message", "format", "string", "invalid",
    "valid", "true", "false", "null", "none", "init", "start", "stop", "exit",
    "debug", "warn", "info", "fatal", "critical", "verbose", "mode", "flag",
    "hash", "cert", "auth", "access", "admin", "root", "home", "temp", "log",
}


def load_dictionary(path=None):
    paths = []
    if path:
        paths.append(path)
    paths += ["words_alpha.txt", "/usr/share/dict/words", "/usr/dict/words"]
    for p in paths:
        try:
            with open(p) as f:
                words = set(x.strip().lower() for x in f if len(x.strip()) > 3)
                if words:
                    return words
        except OSError:
            continue
    return FALLBACK_DICT


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter strings output — keep only English-like readable text."
    )
    parser.add_argument("-n", "--negate", action="store_true",
                        help="Print rejected strings instead of accepted ones.")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Print per-heuristic debug info.")
    parser.add_argument("--score", action="store_true",
                        help="Prefix each accepted line with its score (0-100).")
    parser.add_argument("--min-len", type=int, default=4,
                        help="Minimum string length to consider (default: 4).")
    parser.add_argument("--wordlist", type=str, default=None,
                        help="Path to a custom word list (one word per line).")
    parser.add_argument("input", nargs="?", type=str, default="-",
                        help="Ignored — reads from stdin.")
    return parser.parse_args()


# ── Heuristic functions ────────────────────────────────────────────────────────

def chi_square_english(s: str) -> float:
    """Lower is more English-like. Threshold ~ 100."""
    letters = [c for c in s.lower() if c.isalpha()]
    if len(letters) < 4:
        return 9999.0
    counts = Counter(letters)
    total = len(letters)
    chi = 0.0
    for letter, ef in EN_FREQ.items():
        observed = counts.get(letter, 0)
        expected = ef * total
        chi += (observed - expected) ** 2 / (expected + 1e-9)
    return chi


def bigram_score(s: str) -> float:
    """Returns sum of bigram frequencies found. Threshold ~ 0.03."""
    s = s.lower()
    score = 0.0
    for i in range(len(s) - 1):
        score += BIGRAM_FREQ.get(s[i:i+2], 0.0)
    return score


_PRINTF_RE = re.compile(
    r'%(?:[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcspn%])'
)

def printf_format_tokens(s: str):
    return _PRINTF_RE.findall(s)


_IP4_RE = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
)
_URL_RE = re.compile(
    r'https?://[^\s"\'<>]{6,}|ftp://[^\s"\'<>]{4,}'
)
_DOMAIN_RE = re.compile(
    r'\b(?:[a-zA-Z0-9-]{2,63}\.)+(?:com|net|org|io|gov|edu|mil|ru|cn|de|uk|fr|jp|xyz|onion)\b'
)
_OID_RE = re.compile(r'^[0-2](?:\.\d+)+$')
_PATH_RE = re.compile(
    r'(?:/[a-zA-Z0-9_./-]{3,})|(?:[A-Za-z]:\\[\\A-Za-z0-9_./ -]{3,})'
)
_REGISTRY_RE = re.compile(
    r'HKEY_(?:LOCAL_MACHINE|CURRENT_USER|CLASSES_ROOT|USERS|CURRENT_CONFIG)'
    r'(?:\\[\\A-Za-z0-9_. ()-]+)*'
)
_PEM_RE = re.compile(
    r'-----BEGIN [A-Z ]+-----|-----END [A-Z ]+-----'
    r'|PRIVATE KEY|PUBLIC KEY|CERTIFICATE|RSA|EC PARAMETERS'
)
_CRED_RE = re.compile(
    r'(?i)\b(?:password|passwd|secret|token|api.?key|bearer|auth|credential'
    r'|passphrase|private.?key|access.?key|client.?secret)\b'
)


def is_ipv4(s: str) -> bool:
    return bool(_IP4_RE.search(s))


def is_ipv6(s: str) -> bool:
    try:
        ipaddress.IPv6Address(s.strip())
        return True
    except ValueError:
        return False


def is_oid(s: str) -> bool:
    if not _OID_RE.match(s.strip()):
        return False
    try:
        return all(int(p) >= 0 for p in s.strip().split("."))
    except ValueError:
        return False


# ── Main scoring / filter ──────────────────────────────────────────────────────

def analyze(s: str, dictionary: set, min_len: int):
    """
    Returns (accepted: bool, score: int, reasons: list[str])
    score is 0-100 rough confidence.
    """
    reasons = []

    if len(s) < min_len:
        return False, 0, ["too_short"]

    # Fast-path: always-accept patterns (network IOCs, credentials, paths)
    if _URL_RE.search(s):
        return True, 90, ["url"]
    if is_ipv4(s) or is_ipv6(s):
        return True, 85, ["ip_address"]
    if is_oid(s):
        return True, 75, ["snmp_oid"]
    if _REGISTRY_RE.search(s):
        return True, 85, ["registry_key"]
    if _PEM_RE.search(s):
        return True, 95, ["pem_material"]
    if _CRED_RE.search(s):
        return True, 80, ["credential_keyword"]
    if _DOMAIN_RE.search(s):
        return True, 75, ["domain"]
    if _PATH_RE.search(s):
        return True, 70, ["filesystem_path"]

    # Printable ratio gate
    printable = sum(c.isalnum() or c in " .,:;'-_/%[]{}()\\/\t@#$^&*+=<>?!~`|" for c in s)
    ratio = printable / len(s)
    if ratio < 0.85:
        return False, 0, ["low_printable_ratio"]

    score = 0
    reasons = []

    # Dictionary hits
    tokens = re.findall(r"[A-Za-z]{3,}", s.lower())
    dict_hits = sum(1 for t in tokens if t in dictionary)
    if dict_hits >= 1:
        score += 40
        reasons.append(f"dict_hits={dict_hits}")

    # Chi-square on individual tokens
    chi_tokens = re.findall(r"[A-Za-z_]{4,}", s.lower())
    chi_hits = sum(1 for t in chi_tokens if chi_square_english(t) < 100)
    if chi_hits >= 1:
        score += 25
        reasons.append(f"chi_hits={chi_hits}")

    # Bigram score
    bs = bigram_score(s)
    if bs > 0.03:
        score += 20
        reasons.append(f"bigram={bs:.3f}")

    # Printf format strings
    fmt = printf_format_tokens(s)
    if fmt:
        score += 15
        reasons.append(f"printf={fmt}")

    accepted = score >= 25
    return accepted, min(score, 100), reasons


def main():
    global debug_enabled
    args = parse_args()
    if args.debug:
        debug_enabled = True

    dictionary = load_dictionary(args.wordlist)

    for line in sys.stdin:
        s = line.rstrip("\n")
        if not s:
            continue

        accepted, score, reasons = analyze(s, dictionary, args.min_len)

        if args.debug:
            print(f"[DEBUG] accepted={accepted} score={score} reasons={reasons} | {s!r}",
                  file=sys.stderr)

        if args.negate:
            if not accepted:
                print(s)
        else:
            if accepted:
                if args.score:
                    print(f"{score:3d}  {s}")
                else:
                    print(s)


if __name__ == "__main__":
    main()
