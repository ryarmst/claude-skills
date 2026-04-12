# Burp Bambdas

Drop-in Bambda scripts for Burp Suite Professional.

## Prerequisites

Install the **[Burp Globals](https://github.com/ryarmst/Burp-Globals)** extension before using any script here. Every Bambda reads one or more named variables from it at runtime via `System.getProperty("bg.<name>")`.

## Quick start

1. In Burp, open **Burp Globals → Options → Import variables** and load `globals.csv` from this folder.
2. Enable only the categories you want to run (set the relevant gate variable to `true`).
3. Import the `.bambda` file(s) via **Extensions → Bambdas → Import**.

## Execution gates

Every Bambda has a gate global that must be `true` for the script to do anything. Set them in the Burp Globals tab.

| Global | Controls |
|--------|----------|
| `bambda-injection` | Active per-insertion-point injection checks (SQLi, SSTI, XSS, …) |
| `bambda-fuzzing` | Active per-insertion-point brute-force / enumeration checks |
| `bambda-oob` | Active OOB/blind checks via Burp Collaborator |
| `bambda-active` | Active per-request checks (CORS, method probing, header injection) |
| `bambda-recon` | Active per-host recon probes (well-known paths, banners) |
| `bambda-passive` | Passive checks (missing headers, info disclosure, JWT detection) |
| `bambda-filter` | Proxy HTTP history view filters |
| `bambda-column` | Custom table columns |
| `bambda-action` | Repeater / Intruder custom actions |
| `bambda-proxy` | Proxy match-and-replace rules |

## Per-script globals

Each script lists its required and optional globals near the top in a `// === BURP GLOBALS ===` comment block. Add any script-specific globals to `globals.csv` (name, value, regex — no header row) and re-import.

## Adding a new global to globals.csv

Append a line: `variable-name,default-value,` (leave the regex column empty unless you want auto-update).
