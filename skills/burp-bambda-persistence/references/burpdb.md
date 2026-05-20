# BurpDB — Managed SQLite via the BurpDB Extension

BurpDB is a Burp extension that provisions a shared SQLite database for cross-invocation persistence in Bambdas (scan checks, custom columns, filters, Repeater actions). It shades `sqlite-jdbc` into its JAR, creates the schema on load, and exposes connection details via JVM system properties. No external JDBC JAR or classpath setup is required.

**When to prefer BurpDB over a self-managed DB:**
- You want persistence with zero setup (no driver JAR, no external server).
- You're sharing state between Bambdas in the same Burp session.
- The pre-provisioned tables (`kv`, `findings`, `logs`) are sufficient for your use case.
- You want a standard troubleshooting/logging channel that other BurpDB-aware Bambdas can read.

Source of truth: [BurpDB BAMBDA_PROMPT.md](https://github.com/ryarmst/BurpDB/blob/main/BAMBDA_PROMPT.md)

---

## 1. How it works

On load, BurpDB:

1. Loads the shaded SQLite driver in the extension classloader.
2. Publishes the live `java.sql.Driver` object in `System.getProperties()` under `burp.db.driver.instance`.
3. Sets `burp.db.url` to `jdbc:sqlite:<path>` (default file: `~/.burp/burpdb.db`, changeable in the BurpDB suite tab).
4. Creates `kv`, `findings`, and `logs` if missing (WAL mode, 5s busy timeout).

Bambdas run in Burp's classloader, not the extension's. **`DriverManager.getConnection()` fails from Bambdas** because Java 9+ caller-sensitivity checks reject drivers registered by sibling classloaders. Bambdas must call `driver.connect()` on the instance published in `System.getProperties()` — a `Hashtable<Object,Object>` singleton visible to every classloader.

Do not call `Class.forName("org.sqlite.JDBC")` or add `sqlite-jdbc` to Burp's library JAR folder. The driver class is not visible outside the extension JAR.

All three system properties are JVM-global. If BurpDB is unloaded, they are cleared.

---

## 2. System properties

| Property | Type | Meaning |
|---|---|---|
| `burp.db.driver.instance` | `java.sql.Driver` | Live driver object — **use this to connect** |
| `burp.db.url` | `String` | JDBC URL, e.g. `jdbc:sqlite:/home/user/.burp/burpdb.db` |
| `burp.db.driver` | `String` | Driver class name (`org.sqlite.JDBC`) — presence confirms extension loaded |

---

## 3. Opening a connection

```java
var driver = (java.sql.Driver) System.getProperties().get("burp.db.driver.instance");
if (driver == null) return;  // extension not loaded

var dbUrl = System.getProperty("burp.db.url");
if (dbUrl == null || dbUrl.isBlank()) return;

try (var conn = driver.connect(dbUrl, new java.util.Properties())) {
    // standard JDBC from here
}
```

Rules:
- Check `burp.db.driver.instance` first — if null, BurpDB is not installed, not loaded, or failed to initialize.
- Optionally verify `burp.db.driver` is `org.sqlite.JDBC` as a secondary health signal.
- **Never** call `DriverManager.getConnection()` from a Bambda when using BurpDB.
- **Never** hard-code DB paths — always read `burp.db.url`.
- No username or password — the extension manages the SQLite file.
- **Always use try-with-resources** for every `Connection`, `Statement`, `PreparedStatement`, and `ResultSet`.

### Health check (custom column or Repeater action)

```java
var driver = (java.sql.Driver) System.getProperties().get("burp.db.driver.instance");
if (driver == null) return "no driver";
try (var conn = driver.connect(System.getProperty("burp.db.url"), new java.util.Properties());
     var stmt = conn.createStatement();
     var rs = stmt.executeQuery("SELECT 1")) {
    return rs.next() ? "ok" : "no rows";
} catch (Exception e) {
    return e.getMessage();
}
```

Expect `ok` when BurpDB is loaded. If you see `no driver`, reload the BurpDB extension.

---

## 4. Pre-provisioned tables

The extension guarantees these tables exist before your Bambda runs. Do **not** `CREATE TABLE`.

### `kv(key, value, updated_at)`

General-purpose key-value store. Use for counters, flags, dedupe keys, last-seen tokens, or any scalar state.

```java
// Write (upsert)
try (var conn = driver.connect(dbUrl, new java.util.Properties());
     var ps = conn.prepareStatement(
         "INSERT INTO kv(key, value, updated_at) VALUES(?, ?, strftime('%s','now')) " +
         "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at")) {
    ps.setString(1, "my-bambda.last-host");
    ps.setString(2, host);
    ps.executeUpdate();
}

// Read
try (var conn = driver.connect(dbUrl, new java.util.Properties());
     var ps = conn.prepareStatement("SELECT value FROM kv WHERE key = ?")) {
    ps.setString(1, "my-bambda.last-host");
    try (var rs = ps.executeQuery()) {
        if (rs.next()) {
            var lastHost = rs.getString("value");
        }
    }
}
```

**Namespace your keys.** Prefix with the Bambda/tool name (e.g., `cors-check.seen-host:example.com`) to avoid collisions with other Bambdas sharing the same DB.

For dedupe, use `INSERT ... ON CONFLICT DO NOTHING` on a namespaced key:

```java
try (var conn = driver.connect(dbUrl, new java.util.Properties());
     var ps = conn.prepareStatement(
         "INSERT INTO kv(key, value, updated_at) VALUES(?, '1', strftime('%s','now')) " +
         "ON CONFLICT(key) DO NOTHING")) {
    ps.setString(1, "xcto-check.seen-host:" + host);
    if (ps.executeUpdate() == 0) return AuditResult.auditResult();  // already seen
}
```

### `findings(id, host, issue, detail, severity, created_at)`

Structured finding records. Use for building a corpus of observations that non-Burp tools can read.

```java
try (var conn = driver.connect(dbUrl, new java.util.Properties());
     var ps = conn.prepareStatement(
         "INSERT INTO findings(host, issue, detail, severity, created_at) " +
         "VALUES(?, ?, ?, ?, strftime('%s','now'))")) {
    ps.setString(1, host);
    ps.setString(2, "CORS: arbitrary origin reflection");
    ps.setString(3, detail);
    ps.setString(4, "MEDIUM");
    ps.executeUpdate();
}
```

Prefer `kv` for dedupe — the `findings` table has no unique constraint on `(host, issue)`.

### `logs(created_at, reporter, details)`

The standard troubleshooting channel. **Every Bambda should write here when something unexpected happens** — it creates a shared audit trail that any BurpDB-aware tool can read.

```java
try (var conn = driver.connect(dbUrl, new java.util.Properties());
     var ps = conn.prepareStatement(
         "INSERT INTO logs(created_at, reporter, details) VALUES(strftime('%s','now'), ?, ?)")) {
    ps.setString(1, "my-bambda");
    ps.setString(2, "driver instance missing; skipping check");
    ps.executeUpdate();
}
```

Logging rules:
- `created_at`: always `strftime('%s','now')` — Unix epoch seconds.
- `reporter`: the Bambda or tool name (a static string literal).
- `details`: short, human-readable, no secrets.
- Log for: missing driver, unexpected exceptions, and any state transitions worth auditing.

Prefer `PreparedStatement` for writes. Keep `logs.details` short; no secrets.

---

## 5. Connection guard

Always resolve the driver and URL before connecting:

```java
var driver = (java.sql.Driver) System.getProperties().get("burp.db.driver.instance");
var dbUrl  = System.getProperty("burp.db.url");
if (driver == null || dbUrl == null || dbUrl.isBlank()) {
    api().logging().logToOutput("[my-bambda] BurpDB not loaded — skipping persistence");
    return AuditResult.auditResult();
}
try (var conn = driver.connect(dbUrl, new java.util.Properties())) {
    // ...
} catch (java.sql.SQLException e) {
    api().logging().logToError("[my-bambda] DB error: " + e.getMessage());
    return AuditResult.auditResult();
}
```

In Repeater custom actions, use `logging()` instead of `api().logging()`.

---

## 6. Concurrency

Burp runs scan checks (and parallel Repeater sends) concurrently. SQLite serializes writes:

- Concurrent reads are fine.
- Use `INSERT ... ON CONFLICT DO NOTHING/DO UPDATE` instead of check-then-insert.
- Do not hold write transactions open across slow I/O (HTTP probes).
- For multi-statement atomicity: `conn.setAutoCommit(false)` + `conn.commit()`.
- Cache reads in script-local variables within a single invocation; avoid a DB round-trip on every cheap early-return path.

---

## 7. Full example: dedupe scan check via BurpDB

```java
/**
 * Passive check: report missing X-Content-Type-Options, deduplicated per host via BurpDB.
 **/

// === BURP GLOBALS ===
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-passive"))) {
    return AuditResult.auditResult();
}

// === SANITY ===
if (!requestResponse.hasResponse()) return AuditResult.auditResult();

// === IN-MEMORY FILTER (cheap rejection before touching DB) ===
var xcto = requestResponse.response().headerValue("X-Content-Type-Options");
if (xcto != null && xcto.equalsIgnoreCase("nosniff")) return AuditResult.auditResult();

// === BURPDB DEDUPE ===
var host = requestResponse.request().httpService().host();
var driver = (java.sql.Driver) System.getProperties().get("burp.db.driver.instance");
var dbUrl  = System.getProperty("burp.db.url");

if (driver == null || dbUrl == null || dbUrl.isBlank()) {
    api().logging().logToOutput("[xcto-check] BurpDB not available; reporting without dedupe");
} else {
    boolean isNew = true;
    try (var conn = driver.connect(dbUrl, new java.util.Properties());
         var ps = conn.prepareStatement(
             "INSERT INTO kv(key, value, updated_at) VALUES(?, '1', strftime('%s','now')) " +
             "ON CONFLICT(key) DO NOTHING")) {
        ps.setString(1, "xcto-check.seen-host:" + host);
        isNew = ps.executeUpdate() > 0;
    } catch (java.sql.SQLException e) {
        // Log and fail open — better a duplicate finding than a missed one
        try (var conn2 = driver.connect(dbUrl, new java.util.Properties());
             var ps = conn2.prepareStatement(
                 "INSERT INTO logs(created_at, reporter, details) VALUES(strftime('%s','now'), ?, ?)")) {
            ps.setString(1, "xcto-check");
            ps.setString(2, "DB error on dedupe: " + e.getMessage());
            ps.executeUpdate();
        } catch (java.sql.SQLException ignored) {}
        isNew = true;
    }

    if (!isNew) return AuditResult.auditResult();
}

// === REPORT ===
return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "Missing X-Content-Type-Options",
        "<p>The response from <b>" + api().utilities().htmlUtils().encode(host) + "</b> "
            + "does not include the <code>X-Content-Type-Options: nosniff</code> header.</p>",
        "<p>Add <code>X-Content-Type-Options: nosniff</code> to all responses.</p>",
        requestResponse.request().url(),
        AuditIssueSeverity.LOW,
        AuditIssueConfidence.CERTAIN,
        "", "",
        AuditIssueSeverity.LOW,
        requestResponse
    )
);
```
