---
name: apk-surface-map
description: >
  Comprehensively maps the attack surface of a decompiled Android APK by extracting
  deep links, HTTP endpoints and APIs, intents, exported components, insecure
  configurations, and other entry points. Stores findings in a SQLite database for
  queryable, persistent recon, and generates a structured markdown report. Use this
  skill whenever a user wants to map an app's surface area, enumerate entry points,
  understand what an app exposes, find attack vectors, or do recon before active
  testing. Trigger after apk-decompile completes, or any time the user has a jadx
  output directory and wants to understand what the app does and exposes.
compatibility:
  tools: [Bash, Read, Write, Agent]
  dependencies: [jadx, sqlite3, python3]
---

# APK Surface Map Skill

Maps the full attack surface of a decompiled APK into a SQLite database, then
generates a markdown report. Runs extraction domains in parallel subagents for speed.

## Prerequisites

This skill expects jadx output already on disk. If the user hasn't decompiled yet,
invoke the `apk-decompile` skill first.

Confirm inputs:
```bash
# jadx output dir should contain sources/ and resources/
ls <decompile_dir>/sources/ | head -5
ls <decompile_dir>/resources/AndroidManifest.xml
sqlite3 --version
python3 --version
```

Set two variables you'll use throughout:
- `DECOMPILE_DIR` — absolute path to jadx output (contains `sources/` and `resources/`)
- `WORK_DIR` — where to write the DB and report (default: `<DECOMPILE_DIR>/../surface-map/`)

```bash
mkdir -p "$WORK_DIR"
DB="$WORK_DIR/surface.db"
```

## Step 1 — Initialize the database

Run the schema script:
```bash
python3 /path/to/skill/scripts/init_db.py "$DB"
```

Or inline if the script isn't available — read `scripts/init_db.py` for the full schema.
The schema covers these tables: `deep_links`, `http_endpoints`, `intents`,
`exported_components`, `insecure_configs`, `crypto_issues`, `webviews`, `permissions`,
`native_libs`, `findings_summary`.

## Step 2 — Spawn parallel extraction subagents

Dispatch all six subagents simultaneously (they are fully independent):

| Subagent | File | Extracts |
|---|---|---|
| `surface-deep-links` | `.claude/agents/surface-deep-links.md` | Deep links, URI schemes, app links |
| `surface-http` | `.claude/agents/surface-http.md` | HTTP/S endpoints, API keys, base URLs |
| `surface-intents` | `.claude/agents/surface-intents.md` | Intents, intent filters, broadcast receivers |
| `surface-components` | `.claude/agents/surface-components.md` | Exported activities/services/providers/receivers |
| `surface-configs` | `.claude/agents/surface-configs.md` | Insecure configs, network policy, backup, debug flags |
| `surface-crypto` | `.claude/agents/surface-crypto.md` | Weak crypto, insecure RNG, hardcoded keys/certs |

Each subagent receives:
- `DECOMPILE_DIR` absolute path
- `DB` absolute path
- Its specific extraction instructions

Background all six with Ctrl+B after dispatch. When all six return, proceed to Step 3.

**Invocation template per subagent:**
```
Map the surface area of the decompiled APK at <DECOMPILE_DIR>.
Write findings to SQLite DB at <DB>.
Return a one-paragraph summary of what you found.
```

## Step 3 — Cross-reference and enrich

After all subagents complete, run these enrichment queries in the main session:

```bash
# Deep links that also have exported components (high-value targets)
sqlite3 "$DB" "
  SELECT d.scheme || '://' || d.host || d.path, e.component_name, e.component_type
  FROM deep_links d
  JOIN exported_components e ON d.activity = e.component_name
  WHERE e.permission IS NULL OR e.permission = '';
"

# APIs that match insecure config scope (cleartext domains)
sqlite3 "$DB" "
  SELECT h.url, i.detail
  FROM http_endpoints h
  JOIN insecure_configs i ON i.category = 'cleartext'
    AND (h.url LIKE '%http://%' OR i.detail LIKE '%' || h.host || '%');
"

# Exported components with no permission AND receiving external intents
sqlite3 "$DB" "
  SELECT e.component_name, e.component_type, GROUP_CONCAT(i.action, ' | ') as actions
  FROM exported_components e
  JOIN intents i ON i.component = e.component_name
  WHERE e.permission IS NULL OR e.permission = ''
  GROUP BY e.component_name;
"
```

Insert any cross-reference findings into `findings_summary` with severity ratings.

## Step 4 — Generate the markdown report

```bash
python3 /path/to/skill/scripts/generate_report.py "$DB" "$WORK_DIR/surface-map.md"
```

Or read `scripts/generate_report.py` and run equivalent logic. The report structure is
defined in `references/report-template.md`.

The report is the primary deliverable — tell the user where it is and give them a
high-level summary of the most interesting findings.

## Querying the database later

The DB persists so Claude Code can answer follow-up questions without re-running
extraction. Useful patterns:

```bash
# All unprotected exported entry points
sqlite3 -column -header "$DB" "
  SELECT component_type, component_name, package
  FROM exported_components
  WHERE permission IS NULL OR permission = ''
  ORDER BY component_type;
"

# All unique API hosts
sqlite3 "$DB" "SELECT DISTINCT host FROM http_endpoints ORDER BY host;"

# High-severity findings
sqlite3 -column -header "$DB" "
  SELECT category, title, detail, severity
  FROM findings_summary
  WHERE severity IN ('HIGH','CRITICAL')
  ORDER BY severity;
"

# Deep links with parameters (injection candidates)
sqlite3 "$DB" "
  SELECT scheme, host, path, parameters
  FROM deep_links
  WHERE parameters != '' AND parameters IS NOT NULL;
"
```

## Output format (end-of-run summary to user)

```
## Surface Map Complete — <app_package>

**Database:** <DB path>
**Report:** <surface-map.md path>
**Extraction time:** ~N minutes

### Coverage
- Deep links / URI schemes: N
- HTTP endpoints identified: N  
- Exported components: N (N unprotected)
- Intents / Intent filters: N
- Insecure configurations: N
- Crypto issues: N
- WebViews: N
- Dangerous permissions: N

### Critical Findings
<bullet list of CRITICAL/HIGH items — max 10>

### Recommended Attack Vectors
<top 3-5 based on cross-reference analysis>

Query the DB at <path> for deeper analysis.
```

## Edge cases

- **No sources/ dir:** jadx may have failed — rerun `apk-decompile` with `--show-bad-code`
- **Obfuscated class names:** extraction still works on string literals and manifest; flag
  that class-level findings may be incomplete
- **Very large apps (1000+ source files):** subagents may take 5-10 min; encourage user
  to background and do other work
- **React Native / Flutter apps:** JS bundle at `assets/index.android.bundle` or
  `assets/flutter_assets/` — note this in the report; grep patterns still find URLs/keys
  but class-level analysis won't apply

## References

Read these files when needed:
- `scripts/init_db.py` — full SQLite schema
- `scripts/generate_report.py` — report generation logic  
- `references/report-template.md` — markdown report structure and section definitions
- `references/grep-patterns.md` — all grep patterns by category (keep SKILL.md lean)
