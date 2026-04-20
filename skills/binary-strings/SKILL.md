---
name: binary-strings
description: >
  Reverse engineering skill for extracting and analyzing interesting strings from binary files.
  Use this skill whenever a user uploads a binary, executable, firmware image, shared library,
  or any compiled file and wants to: find hardcoded secrets/credentials, enumerate API endpoints,
  analyze network indicators, identify crypto constants, filter noise from `strings` output,
  assess for malware indicators, or perform any triage-level static analysis. Also triggers when
  the user says "run strings on", "analyze this binary", "what's in this binary", "extract strings",
  "find hardcoded", "look for credentials in", "reverse engineer", or pastes raw strings output
  and asks for interpretation. When in doubt, use this skill — it covers the full workflow from
  raw binary through to categorized, actionable intelligence.
---

# Binary Strings Analysis Skill

A skill for extracting, filtering, and categorizing strings from binary files to support
reverse engineering, malware triage, CTF challenges, and application security assessment.

## When This Skill Applies

- User uploads a binary file (ELF, PE, Mach-O, firmware blob, .so/.dll, .pyc, packed file)
- User pastes output from `strings` and wants signal-from-noise filtering
- User wants to find hardcoded credentials, URLs, IPs, crypto material, or debug artifacts
- User asks for "static analysis" or "triage" of a binary
- CTF / reverse engineering challenge involving binary inspection

---

## Step-by-Step Workflow

### Step 1 – Identify the File

```bash
file <binary>
xxd <binary> | head -20          # magic bytes / file header
```

If the file is packed/encrypted (UPX, custom packer, high entropy sections), note this — strings
output will be limited. Use `upx -d` to unpack UPX, or flag for dynamic analysis.

Check entropy to detect packing/encryption:
```bash
python3 /path/to/scripts/entropy_check.py <binary>
# or: binwalk -E <binary>   # if binwalk available
```

### Step 2 – Extract Raw Strings

Prefer `strings` with UTF-16 LE support (Windows binaries often use wide strings):

```bash
strings -a -n 6 <binary>             # ASCII, min length 6
strings -a -n 6 -e l <binary>        # UTF-16 LE (Windows)
strings -a -n 6 -e b <binary>        # UTF-16 BE
# Combine:
{ strings -a -n 6 <binary>; strings -a -n 6 -e l <binary>; } | sort -u
```

If `strings` isn't available, use Python:
```bash
python3 scripts/extract_strings.py <binary> --min-len 6 --encoding ascii,utf16le
```

### Step 3 – Filter for English / Human-Readable

Run the `strings_english.py`-style filter to remove junk (base64 noise, binary fragments,
compiler artifacts):

```bash
strings -a -n 6 <binary> | python3 scripts/strings_english.py
# Invert (see what was filtered out):
strings -a -n 6 <binary> | python3 scripts/strings_english.py --negate
```

Heuristics applied (see `references/heuristics.md` for tuning):
- Dictionary word hits (English word list)
- Chi-square test against English letter frequencies
- Common English bigrams (th, he, in, er, an...)
- Printf format string detection (`%s`, `%d`, `%x`...)
- IP address validation (IPv4 + IPv6)
- SNMP OID detection
- Printable character ratio ≥ 0.85
- Minimum string length ≥ 4

### Step 4 – Categorize with `strings_categorize.py`

Pass filtered strings through the categorizer to bucket into IOC categories:

```bash
strings -a -n 6 <binary> | python3 scripts/strings_english.py \
  | python3 scripts/strings_categorize.py
```

Output sections:
- `[CREDENTIALS]` — passwords, tokens, API keys, secrets
- `[URLS]` — HTTP/HTTPS/FTP endpoints
- `[IPS]` — IP addresses (v4/v6)
- `[PATHS]` — filesystem paths (/etc/passwd, C:\Windows\...)
- `[REGISTRY]` — Windows registry keys (HKEY_*, Software\...)
- `[CRYPTO]` — PEM headers, key material, hash patterns
- `[COMMANDS]` — shell commands, cmd.exe invocations
- `[DEBUG]` — function names, assert paths, version strings
- `[NETWORK]` — domain names, hostnames
- `[FORMAT_STRINGS]` — printf-style format strings
- `[MISC]` — everything else that passed the English filter

### Step 5 – Deep Analysis

After categorization, investigate high-value hits:

**Credentials / Secrets**
```bash
# Check for common secret patterns
grep -Ei '(password|passwd|secret|token|api.?key|bearer|auth)' filtered.txt
# Base64 candidates
grep -E '^[A-Za-z0-9+/]{20,}={0,2}$' raw_strings.txt | while read b; do
    echo "$b" | base64 -d 2>/dev/null | strings -n 4
done
```

**Crypto Material** — see `references/crypto_patterns.md`

**Domain / Network IOCs**
```bash
# Extract and defang domains for reporting
grep -Eo '[a-zA-Z0-9.-]+\.(com|net|org|io|ru|cn|xyz)' filtered.txt \
  | sed 's/\./[.]/g'
```

**Format Strings as Logic Clues**
Format strings like `"Error: %s at line %d in %s"` reveal internal function names,
error handling paths, and code structure. Collect them for reconstructing program logic.

### Step 6 – Report

Use the structure in `references/report_template.md` to present findings.

---

## Quick Reference: Common Indicators by Binary Type

| Binary Type | Key Things to Look For |
|---|---|
| Malware | C2 IPs/domains, encoded payloads, mutex names, registry run keys |
| Firmware | Default creds, hardcoded IPs, `/etc/` paths, build paths |
| Windows PE | Registry keys, DLL names, COM GUIDs, WMI queries |
| Mobile APK | API keys, cloud bucket names, OAuth secrets, hardcoded endpoints |
| CTF Binary | Flag format strings (`HTB{`, `CTF{`), format string vulns, debug messages |
| Crypto app | PEM headers, key sizes, algorithm names, IV/nonce patterns |

---

## Tool Availability Check

```bash
which strings file xxd binwalk upx python3 2>/dev/null
```

If `strings` is unavailable, use the pure-Python `scripts/extract_strings.py`.
If `binwalk` is available, also run: `binwalk --signature <binary>` for embedded file detection.

---

## References

- `references/heuristics.md` — Tuning the English filter (chi-square thresholds, bigrams)
- `references/crypto_patterns.md` — Regex patterns for crypto material
- `references/report_template.md` — Output format for security reports
- `references/ioc_categories.md` — Full IOC category definitions and patterns

---

## Notes for Teaching / Live Demo Context

When demonstrating this in a live stream or classroom:

1. **Show the noise problem first** — raw `strings` on any binary is overwhelming. This motivates the filter.
2. **Walk through each heuristic** — chi-square English scoring is a great teaching moment (frequency analysis appears in both crypto and RE).
3. **Use a real-world sample** — a consumer router firmware blob makes a great demo: it always has hardcoded IPs, default creds, and debug paths.
4. **Layer the tools** — `strings | strings_english.py | strings_categorize.py` pipeline is a concrete example of Unix philosophy / tool composition.
