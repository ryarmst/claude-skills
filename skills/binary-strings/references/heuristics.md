# Heuristics Reference

Tuning guide for the `strings_english.py` filter.

## Decision Flow

A string is **accepted** if it passes any of these gates (in order):

```
1. Fast-path IOC detection  → always accept
2. Printable ratio < 0.85   → reject
3. score >= 25              → accept (based on weighted heuristics below)
```

---

## Fast-path Patterns (Always Accept)

These bypass all scoring — they are high-value regardless of English resemblance:

| Pattern | Why Accept |
|---|---|
| `http://`, `https://`, `ftp://` | Network endpoints |
| IPv4 / IPv6 address | Network IOC |
| SNMP OID (`1.3.6.1.*`) | Network management |
| `HKEY_*` registry keys | Windows persistence / config |
| `-----BEGIN …-----` PEM headers | Crypto material |
| `password`, `secret`, `token`, `api_key` etc. | Credential keywords |
| Domain names (`.com`, `.net`, `.io`, `.onion` etc.) | Network IOC |
| Filesystem paths (`/etc/`, `C:\Windows\`) | Execution paths |

---

## Weighted Scoring Heuristics

| Heuristic | Points | Notes |
|---|---|---|
| **Dictionary hit** | +40 | ≥1 token from English word list |
| **Chi-square** | +25 | ≥1 token with χ² < 100 vs English |
| **Bigram score** | +20 | sum of bigram freqs > 0.03 |
| **Printf format string** | +15 | contains `%s`, `%d`, `%x`, etc. |

Acceptance threshold: **score ≥ 25**

---

## Chi-Square Threshold Tuning

The chi-square test measures how closely a string's letter distribution matches English.
Lower chi² = more English-like.

| χ² value | Interpretation |
|---|---|
| < 30 | Very likely English prose |
| 30 – 100 | Plausibly English (technical text, identifiers) |
| 100 – 300 | Borderline; may be encoded, foreign language |
| > 300 | Likely binary fragment, random bytes, or non-Latin |

**Current threshold: 100** — conservative enough to catch identifiers and technical strings
without false-positiving on random noise.

To tighten (fewer false positives): lower to 60.
To relax (more recall): raise to 200.

---

## Minimum String Length

Default: **4 characters**. For production triage, **6** is recommended (aligns with
`strings -n 6`) to avoid single-word fragments that generate noise.

---

## Word List Priority

1. User-supplied `--wordlist <path>`
2. `words_alpha.txt` (same directory)
3. `/usr/share/dict/words` (Linux)
4. Fallback ~50-word security-relevant built-in list

For best results, use a large English word list (~370k words). The `words_alpha.txt`
from https://github.com/dwyl/english-words works well.

---

## False Positive Tuning Tips

**Too much noise (lower precision):**
- Raise the minimum string length (`--min-len 8`)
- Lower chi-square threshold to 60
- Reduce the fast-path domain TLD list to only suspicious TLDs

**Missing strings (lower recall):**
- Lower `--min-len` to 4
- Raise chi-square threshold to 200
- Add domain-specific terms to the word list (e.g. mutex names, product names)
