---
name: burp-bambda-persistence
description: Persist state across Burp Bambda invocations - scan checks, custom actions, filters - using the BurpDB extension (preferred, zero setup), the Java Preferences API (built-in, no setup), or JDBC to a local database server (Postgres, MySQL, SQLite). Use when a Bambda needs to remember things between invocations - dedupe issues across hosts in a scan, store seen JWT signing keys, accumulate per-host baselines, track which Collaborator interactions have already been reported, share state between a passive check and an active check, or build a corpus of observations for later analysis. Bambdas have NO native persistence mechanism, so this skill is the only sanctioned way to do it. Triggers on phrases like "remember between scan runs", "dedupe across hosts", "track seen X in a Bambda", "store state in a Burp scan check", "persist data from a Bambda", "share state between Bambdas".
---

# Bambda Persistence

Bambdas have no native cross-invocation persistence. Every time Burp invokes your scan check / filter / action, it executes the script body fresh. Local variables, instance fields, anything you `var = new HashMap<>()` at the top of the script — all gone the moment the script returns.

This skill documents three viable strategies.

---

## When you need persistence

You actually need persistence when:

- You want to **dedupe findings** across many invocations of the same scan check (e.g. "only report this issue once per host" — but the per-host scan check type only fires once per host *per scan*, not across scans).
- You want to **track unique values across the scan**: every distinct JWT signing key seen, every distinct CSP nonce, every distinct error fingerprint.
- You want to **establish a baseline** in one phase and compare against it in another (e.g., a passive check records the response sizes for each endpoint; an active check later flags ones that have changed).
- You want to **share state between two different Bambdas** — e.g., a custom column reads what a scan check wrote.
- You want to **accumulate a corpus** for offline analysis.

You don't need persistence when:

- The state is only relevant within a single invocation. Just use a local `HashMap`.
- Burp's built-in deduplication is enough (it's keyed on issue title + URL).
- You can derive the answer from `requestResponse` alone.

---

## Three strategies

| Strategy | Setup cost | Good for | Bad for |
|---|---|---|---|
| **BurpDB extension** | Install the BurpDB extension | Structured queries, pre-provisioned tables, shared troubleshooting log, zero driver config | Requires BurpDB extension to be installed |
| **Java `Preferences` API** | Zero | Small key-value, < ~1MB total, primitive types | Anything large, multi-process sharing, structured queries |
| **JDBC to a self-managed DB** | Need a DB running + driver JAR | Large blobs, structured data, sharing across machines, custom schema | Single-machine quick hacks; driver setup overhead |

**Default recommendation:**
- If the user has the BurpDB extension (or is willing to install it): use BurpDB. Zero driver setup, pre-provisioned tables, built-in logging channel.
- If BurpDB is not available and the need is small key-value (< ~1MB): use Java Preferences.
- If BurpDB is not available and the need is large, structured, or shared: use JDBC to a self-managed DB.

Read `references/burpdb.md` for the BurpDB option, `references/preferences_api.md` for Preferences, and `references/jdbc.md` for self-managed JDBC.

---

## Critical caveats (all strategies)

1. **Bambdas run in a JVM sandbox.** You cannot load arbitrary JARs from inside a Bambda. For self-managed JDBC this means **the database driver must already be on Burp's classpath** — use a driver that ships with the JDK, or add the driver JAR via Burp's "Extensions → APIs → Java environment → Folder for loading library JAR files (.jar)" setting. **BurpDB is exempt from driver JAR setup** — the extension shades `sqlite-jdbc` and publishes the live driver object at `burp.db.driver.instance`. Bambdas connect via `driver.connect(dbUrl, new java.util.Properties())`, **not** `DriverManager.getConnection()` (Java 9+ caller-sensitivity rejects sibling-classloader drivers). Do not call `Class.forName("org.sqlite.JDBC")` — the driver class is not visible outside the extension JAR.

2. **Concurrency.** Burp runs scan checks in parallel. Whatever you write to must be safe for concurrent access:
   - `Preferences` is thread-safe at the API level but you still need to handle read-modify-write atomicity yourself (e.g., to increment a counter without losing updates).
   - JDBC: use transactions and `SELECT ... FOR UPDATE` or `INSERT ... ON CONFLICT` patterns to avoid races.

3. **Lifetime.** `Preferences` lives in the user's home directory and persists *forever* until manually cleared. A local DB lives until the DB is deleted. Neither is automatically scoped to a scan or a project — that's your responsibility. **Always namespace your keys** (e.g., prefix with the project name or a session UUID stored separately).

4. **Don't put secrets in either store.** `Preferences` is plaintext in `~/.java/.userPrefs/`. The local DB depends on its own access control.

5. **Performance.** Both are slower than in-memory access. Don't read/write on every per-insertion-point invocation in a hot loop — batch where possible, or cache reads in a script-local variable for the lifetime of the invocation.

---

## Workflow when the user asks for persistence

1. Ask (or infer) **what** they want to store: small key-value vs. records vs. blobs.
2. Ask (or infer) **what for**: dedupe, baseline, corpus, cross-Bambda sharing, troubleshooting log.
3. **Is the BurpDB extension installed and loaded?** Check `System.getProperties().get("burp.db.driver.instance")` and `System.getProperty("burp.db.url")`. If both are set (or if the user is willing to install BurpDB), use BurpDB — no driver JAR setup, pre-provisioned tables, standard logging channel. Read `references/burpdb.md`.
4. If BurpDB is not available:
   - Recommend Preferences for small key-value with <1MB total.
   - Recommend self-managed JDBC for anything else.
   - If JDBC, also confirm:
     - Which DB? (Postgres / MySQL / MariaDB / SQLite — see `references/jdbc.md` for the trade-offs)
     - Is the driver already on Burp's classpath? If unknown, instruct the user how to check.
     - Connection string and credentials.
5. Read the relevant reference file.
6. Generate the Bambda using the patterns from the reference file. The persistence code goes inline in the Bambda body — you can't factor it into a helper file because Bambdas don't import.

---

## Reference files

- `references/burpdb.md` — BurpDB extension patterns: `burp.db.driver.instance` + `burp.db.url` connection via `driver.connect()` (never `DriverManager.getConnection`), the pre-provisioned `kv` / `findings` / `logs` tables, the standard logging convention, concurrency rules, and a full dedupe example.
- `references/preferences_api.md` — Java `Preferences` API patterns: namespace setup, atomic increment, list-of-strings encoding, clearing, size limits.
- `references/jdbc.md` — Self-managed JDBC patterns: driver checklist, connection management (with caveats about per-invocation overhead), the schema-on-startup idiom, dedupe via `INSERT ... ON CONFLICT`, batching, and DB-specific notes for Postgres / SQLite / MySQL.
