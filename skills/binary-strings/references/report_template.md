# Binary Strings Analysis Report Template

Use this structure for reporting findings from binary string analysis.

---

# Binary String Analysis: `<filename>`

**Date:** YYYY-MM-DD  
**Analyst:** [Name]  
**File hash (SHA-256):** `<hash>`  
**File type:** ELF/PE/Mach-O/Firmware blob  
**File size:** X bytes  

---

## Executive Summary

[2-3 sentences: what was found, severity, recommended action]

Example:
> Analysis of `router_firmware_v2.3.bin` revealed hardcoded default credentials
> (`admin:admin`), a C2 domain (`update.malicious[.]io`), and an exposed SSH private key.
> Immediate patching and key rotation are recommended.

---

## Findings

### 🔴 CRITICAL

| # | Category | Finding | Evidence |
|---|---|---|---|
| 1 | CREDENTIALS | Hardcoded admin password | `password=SuperSecret123` |
| 2 | CRYPTO | Embedded RSA private key | `-----BEGIN RSA PRIVATE KEY-----` |

### 🟠 HIGH

| # | Category | Finding | Evidence |
|---|---|---|---|
| 1 | URLS | C2 callback endpoint | `http://185.220.101.4/beacon` |
| 2 | COMMANDS | Shell execution | `/bin/sh -c wget http://...` |

### 🟡 MEDIUM

| # | Category | Finding | Evidence |
|---|---|---|---|
| 1 | PATHS_UNIX | Debug/build path exposed | `/home/developer/project/src/main.c` |
| 2 | NETWORK_PROTO | Unencrypted protocol | `FTP` references in network code |

### 🔵 INFORMATIONAL

| # | Category | Finding | Evidence |
|---|---|---|---|
| 1 | DEBUG | Version string | `v2.3.0-dev-build-20240815` |
| 2 | IPS | Internal IP range | `192.168.1.1`, `10.0.0.0/8` |

---

## Network Indicators of Compromise (IOCs)

**Domains (defanged):**
```
update[.]malicious[.]io
cdn[.]evilhost[.]net
```

**IP Addresses (defanged):**
```
185[.]220[.]101[.]4
```

**URLs (defanged):**
```
hxxp://185[.]220[.]101[.]4/beacon
hxxps://update[.]malicious[.]io/update?id=
```

---

## Extracted Strings by Category

### CREDENTIALS
```
[paste credential strings here]
```

### CRYPTO
```
[paste crypto material here]
```

### URLS
```
[paste URL strings here]
```

### COMMANDS
```
[paste command strings here]
```

---

## Analysis Notes

- **Packing/Obfuscation:** [Was binary packed? UPX? Custom packer? High-entropy sections?]
- **Encoding:** [Any base64/hex encoded payloads decoded?]
- **String extraction method:** [strings utility version, encoding flags used]
- **Filter settings:** [min-len, heuristic thresholds used]

---

## Recommendations

1. [Specific remediation action]
2. [Specific remediation action]
3. [Escalate to / notify]

---

*Report generated using the Claude Binary Strings Skill.*
