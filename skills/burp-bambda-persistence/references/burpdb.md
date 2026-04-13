# BurpDB — Managed SQLite via the BurpDB Extension

BurpDB is a Burp extension that provisions a SQLite database and exposes its JDBC URL via a JVM system property. No driver JAR setup, no server, no connection string to configure — the extension handles all of it.

**When to prefer BurpDB over a self-managed DB:**
- You want persistence with zero setup (no driver JAR, no external server).
- You're sharing state between Bambdas in the same Burp session.
- The pre-provisioned tables (`kv`, `findings`, `logs`) are sufficient for your use case.
- You want a standard troubleshooting/logging channel that other BurpDB-aware Bambdas can read.

---

## 1. Opening a connection

```java
try (var conn = java.sql.DriverManager.getConnection(System.getProperty("burp.db.url"))) {
    // ... work ...
}
```

Rules:
- `System.getProperty("burp.db.url")` is set by the BurpDB extension when Burp starts. If it returns `null`, the extension is not installed or not loaded — handle this gracefully (log to Burp output and return a no-op).
- No username or password — the extension manages the SQLite file.
- No `Class.forName(...)` needed — the BurpDB extension adds the SQLite driver to Burp's classpath automatically.
- **Always use try-with-resources** for every `Connection`, `Statement`, `PreparedStatement`, and `ResultSet`.

---

## 2. Pre-provisioned tables

The extension guarantees these tables exist before your Bambda runs. Do **not** re-create them with `CREATE TABLE IF NOT EXISTS`.

### `kv(key, value, updated_at)`

General-purpose key-value store. Use for counters, flags, last-seen tokens, or any scalar state that doesn't fit the other tables.

```java
// Write
try (var conn = java.sql.DriverManager.getConnection(System.getProperty("burp.db.url"));
     var ps = conn.prepareStatement(
         "INSERT INTO kv(key, value, updated_at) VALUES(?, ?, strftime('%s','now')) " +
         "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at")) {
    ps.setString(1, "my-bambda.last-host");
    ps.setString(2, host);
    ps.executeUpdate();
}

// Read
try (var conn = java.sql.DriverManager.getConnection(System.getProperty("burp.db.url"));
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

### `findings(id, host, issue, detail, severity, created_at)`

Structured finding records. Use for deduplication or to build a corpus of findings that non-Burp tools can read.

```java
// Insert (dedupe by host + issue)
try (var conn = java.sql.DriverManager.getConnection(System.getProperty("burp.db.url"));
     var ps = conn.prepareStatement(
         "INSERT INTO findings(host, issue, detail, severity, created_at) " +
         "VALUES(?, ?, ?, ?, strftime('%s','now')) " +
         "ON CONFLICT(host, issue) DO NOTHING")) {
    ps.setString(1, host);
    ps.setString(2, "CORS: arbitrary origin reflection");
    ps.setString(3, detail);
    ps.setString(4, "MEDIUM");
    var inserted = ps.executeUpdate();   // 0 = duplicate, 1 = new
    if (inserted == 0) return AuditResult.auditResult();
}
```

> Note: the `ON CONFLICT` behaviour depends on whether the table has a `UNIQUE` constraint on `(host, issue)`. If the extension schema omits it, use a `SELECT` check before inserting, or rely on a different dedupe column.

### `logs(created_at, reporter, details)`

The standard troubleshooting channel. **Every Bambda should write here when something unexpected happens** — it creates a shared audit trail that any BurpDB-aware tool can read.

```java
try (var conn = java.sql.DriverManager.getConnection(System.getProperty("burp.db.url"));
     var ps = conn.prepareStatement(
         "INSERT INTO logs(created_at, reporter, details) VALUES(strftime('%s','now'), ?, ?)")) {
    ps.setString(1, "cors-check");                    // Bambda/tool name
    ps.setString(2, "DB URL missing; skipping check"); // short human-readable message
    ps.executeUpdate();
}
```

Logging rules:
- `created_at`: always `strftime('%s','now')` — Unix epoch seconds, matching SQLite conventions.
- `reporter`: the Bambda or tool name (a static string literal, not a computed value).
- `details`: short, human-readable, no secrets. Good: `"found CORS reflection on example.com"`. Bad: `"Bearer eyJhbGc..."`.
- Log for: missing DB URL, unexpected exceptions, deduplication hits worth tracking, and any state transitions a human might want to audit.

---

## 3. Connection guard

Always check that the property is set before calling `getConnection`:

```java
var dbUrl = System.getProperty("burp.db.url");
if (dbUrl == null) {
    api().logging().logToOutput("[my-bambda] burp.db.url not set — BurpDB extension not loaded");
    return AuditResult.auditResult();
}
try (var conn = java.sql.DriverManager.getConnection(dbUrl)) {
    // ...
} catch (java.sql.SQLException e) {
    api().logging().logToError("[my-bambda] DB error: " + e.getMessage());
    return AuditResult.auditResult();
}
```

---

## 4. Concurrency

BurpDB uses SQLite under the hood. The same concurrency rules as self-managed SQLite apply:

- Concurrent reads are fine.
- Concurrent writes serialize via SQLite's full-database write lock. The extension sets a busy timeout — you can rely on it, but don't hold write transactions open across slow operations (e.g., HTTP probes).
- Use `INSERT ... ON CONFLICT DO NOTHING/DO UPDATE` instead of "check then insert" patterns.
- For multi-statement atomic work: `conn.setAutoCommit(false)` + `conn.commit()`.

---

## 5. Full example: dedupe scan check via BurpDB

```java
/**
 * Passive check: report missing X-Content-Type-Options, deduplicated per host via BurpDB.
 **/

// === BURP GLOBALS ===
// Required:
//   bambda-passive  (boolean: "true"/"false") — master on/off for passive checks
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
var dbUrl = System.getProperty("burp.db.url");
if (dbUrl == null) {
    api().logging().logToOutput("[xcto-check] BurpDB not available; reporting without dedupe");
} else {
    boolean isNew = false;
    try (var conn = java.sql.DriverManager.getConnection(dbUrl)) {
        conn.setAutoCommit(false);

        try (var ps = conn.prepareStatement(
                "INSERT INTO findings(host, issue, detail, severity, created_at) " +
                "VALUES(?, ?, ?, ?, strftime('%s','now')) " +
                "ON CONFLICT(host, issue) DO NOTHING")) {
            ps.setString(1, host);
            ps.setString(2, "Missing X-Content-Type-Options");
            ps.setString(3, "Header absent on " + requestResponse.request().url());
            ps.setString(4, "LOW");
            isNew = ps.executeUpdate() > 0;
        }

        conn.commit();
    } catch (java.sql.SQLException e) {
        // Log and fail open — better a duplicate finding than a missed one
        try (var conn2 = java.sql.DriverManager.getConnection(dbUrl);
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
