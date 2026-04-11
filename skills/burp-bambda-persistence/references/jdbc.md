# JDBC for Bambda Persistence

For anything beyond small key-value, use JDBC to a local database server. The connection lives in your Bambda script, opens on each invocation, runs queries, and closes. There is no shared connection pool — Bambdas can't carry state between invocations, so neither can a connection.

This is heavier than the Preferences API but unlocks: structured queries, blobs, sharing across machines, sharing with non-Burp tools (your dashboard, your reporting pipeline), and proper concurrent safety via DB transactions.

---

## 1. Driver checklist (do this first)

Bambdas can't add JARs themselves. The JDBC driver must already be visible to the JVM that runs Burp. Confirm one of the following before writing a single line:

| DB | Driver class | Where to get it |
|---|---|---|
| **PostgreSQL** | `org.postgresql.Driver` | `postgresql-<version>.jar` from jdbc.postgresql.org |
| **MySQL / MariaDB** | `com.mysql.cj.jdbc.Driver` or `org.mariadb.jdbc.Driver` | mysql.com or mariadb.org |
| **SQLite** | `org.sqlite.JDBC` | `sqlite-jdbc-<version>.jar` from xerial.org |
| **H2** (embedded) | `org.h2.Driver` | h2database.com |
| **HSQLDB** (embedded) | `org.hsqldb.jdbc.JDBCDriver` | hsqldb.org |

To make a driver available to Burp:

1. Download the driver JAR.
2. In Burp: **Extensions → Settings → Java environment → Folder for loading library JAR files**.
3. Set this to a folder containing the driver JAR.
4. Restart Burp.
5. Verify in a Bambda:
   ```java
   try {
       Class.forName("org.postgresql.Driver");
       api().logging().logToOutput("driver OK");
   } catch (ClassNotFoundException e) {
       api().logging().logToError("driver missing: " + e);
   }
   return AuditResult.auditResult();
   ```

If `Class.forName` throws, the driver isn't on the classpath and JDBC will not work. Don't try to download the driver from the Bambda — just tell the user to do step 1–4.

**Recommendation:** for most users, **SQLite** is the path of least resistance. It's a single JAR, no server to run, the file lives wherever you point it, and it's perfectly adequate for hundreds of thousands of rows of scan state. PostgreSQL is the right choice when multiple machines or non-Burp tools also need to read/write the data.

---

## 2. Connection management — there is no pool

Every Bambda invocation opens a fresh connection, runs its work, closes the connection. Per-invocation overhead is real — for SQLite (file) it's milliseconds; for Postgres over a network it can be tens of milliseconds. Per-insertion-point checks invoke many times, so:

- **Don't open a connection on every iteration of an inner loop.** One connection per invocation.
- **Use try-with-resources** so the connection always closes.
- **Cache prepared statements within the invocation**, not across invocations.

```java
final String JDBC_URL  = "jdbc:postgresql://127.0.0.1:5432/burp_state";
final String JDBC_USER = "burp";
final String JDBC_PASS = "burp";

try (var conn = java.sql.DriverManager.getConnection(JDBC_URL, JDBC_USER, JDBC_PASS)) {
    conn.setAutoCommit(false);
    // ... do work ...
    conn.commit();
} catch (java.sql.SQLException e) {
    api().logging().logToError("DB error: " + e.getMessage());
    return AuditResult.auditResult();   // fail closed - don't crash the scan
}
```

**Always wrap in try-catch.** A DB error must not abort the scan check; degrade gracefully and log.

---

## 3. The schema-on-startup idiom

You can't run schema migrations separately from your Bambda. Instead, run `CREATE TABLE IF NOT EXISTS` at the top of every invocation. It's cheap and idempotent.

```java
try (var stmt = conn.createStatement()) {
    stmt.executeUpdate("""
        CREATE TABLE IF NOT EXISTS findings (
            id           BIGSERIAL PRIMARY KEY,
            check_id     TEXT      NOT NULL,
            host         TEXT      NOT NULL,
            url          TEXT      NOT NULL,
            evidence     TEXT,
            first_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (check_id, url)
        )
    """);
    stmt.executeUpdate("""
        CREATE INDEX IF NOT EXISTS idx_findings_host ON findings(host)
    """);
}
```

For SQLite, the syntax is slightly different: `INTEGER PRIMARY KEY AUTOINCREMENT` instead of `BIGSERIAL`, `DATETIME` instead of `TIMESTAMPTZ`, etc. If you're targeting both, write to the lowest common denominator and skip features like `BIGSERIAL` in favor of `INTEGER PRIMARY KEY`.

---

## 4. Dedupe via INSERT ... ON CONFLICT

The race-free way to dedupe: let the database tell you whether the insert was new.

### PostgreSQL / SQLite

```java
try (var ps = conn.prepareStatement("""
        INSERT INTO findings (check_id, host, url, evidence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (check_id, url) DO NOTHING
        """)) {
    ps.setString(1, "missing-csp");
    ps.setString(2, host);
    ps.setString(3, url);
    ps.setString(4, evidence);
    var inserted = ps.executeUpdate();   // 0 if duplicate, 1 if new
    if (inserted == 0) {
        return AuditResult.auditResult();   // already reported
    }
}

conn.commit();

// ... build and return the AuditIssue ...
```

### MySQL

```sql
INSERT INTO findings (...) VALUES (...)
ON DUPLICATE KEY UPDATE id = id
```

`executeUpdate()` returns 1 for a new insert, 0 for an ignored duplicate. (MySQL is annoying here — under some configurations it returns 2 for an UPDATE. The `id = id` no-op is the standard workaround.)

---

## 5. Querying past state (baselines)

The classic two-phase pattern: a passive check records baselines, an active check compares against them.

### Phase 1 (passive per request) — record baseline

```java
try (var conn = java.sql.DriverManager.getConnection(JDBC_URL, JDBC_USER, JDBC_PASS);
     var ps = conn.prepareStatement("""
         INSERT INTO baselines (url, body_size, status, recorded_at)
         VALUES (?, ?, ?, now())
         ON CONFLICT (url) DO UPDATE SET
             body_size = EXCLUDED.body_size,
             status    = EXCLUDED.status,
             recorded_at = EXCLUDED.recorded_at
         """)) {
    ps.setString(1, requestResponse.request().url());
    ps.setInt(2, requestResponse.response().body().length());
    ps.setInt(3, requestResponse.response().statusCode());
    ps.executeUpdate();
} catch (java.sql.SQLException e) {
    api().logging().logToError("baseline write failed: " + e);
}

return AuditResult.auditResult();
```

### Phase 2 (active per request, later) — compare

```java
try (var conn = java.sql.DriverManager.getConnection(JDBC_URL, JDBC_USER, JDBC_PASS);
     var ps = conn.prepareStatement("SELECT body_size, status FROM baselines WHERE url = ?")) {
    ps.setString(1, requestResponse.request().url());
    try (var rs = ps.executeQuery()) {
        if (!rs.next()) return AuditResult.auditResult();   // no baseline yet
        var baselineSize   = rs.getInt("body_size");
        var baselineStatus = rs.getInt("status");

        var probe = http.sendRequest(requestResponse.request().withAddedHeader("X-Test", "1"));
        if (!probe.hasResponse()) return AuditResult.auditResult();

        if (probe.response().statusCode() != baselineStatus
            || Math.abs(probe.response().body().length() - baselineSize) > 100) {
            // ... report issue: response differs from baseline ...
        }
    }
}
```

This pattern is impossible with the Preferences API at scale because you can't run queries.

---

## 6. Cross-Bambda sharing

Two different Bambdas (e.g., a custom column and a scan check) can read each other's data through the same DB. Use distinct table names and conventions:

```sql
CREATE TABLE IF NOT EXISTS jwt_observations (
    id          INTEGER PRIMARY KEY,
    url         TEXT,
    parameter   TEXT,
    kid         TEXT,
    alg         TEXT,
    sub         TEXT,
    seen_at     DATETIME DEFAULT (datetime('now'))
);
```

A passive scan check `INSERT`s into it whenever it sees a JWT; a custom column `SELECT`s the latest row for the current URL to display in HTTP history; an active check queries the table to find unique `(kid, alg)` pairs to attack.

---

## 7. Concurrency safety

Burp runs scan checks in parallel. The DB takes care of most race conditions if you:

- Use `INSERT ... ON CONFLICT` instead of "check then insert".
- Wrap multi-statement logic in a transaction (`setAutoCommit(false)` + `commit()`).
- For critical sections, use `SELECT ... FOR UPDATE` (Postgres/MySQL) or just rely on SQLite's full-database lock (SQLite serializes all writes — fine in practice for Bambda use).

**SQLite gotcha:** with the default driver, concurrent writes can throw `SQLITE_BUSY`. Set a busy timeout:

```java
try (var conn = java.sql.DriverManager.getConnection("jdbc:sqlite:/path/to/burp.db?busy_timeout=5000")) {
    // ...
}
```

5 seconds is enough for any reasonable scan-check workload.

---

## 8. Performance — don't be slow

Per-insertion-point checks may invoke your script hundreds of times for a single base request. Even 5 ms of DB overhead per call adds up.

Tactics:

- **Skip the DB on the cheap rejection paths.** Run your in-memory filters first; only touch the DB when you actually have something to report or compare.
- **Batch writes.** If you're inserting many rows in one invocation, use `addBatch()` / `executeBatch()`.
- **Use indexes.** Any column you query by needs an index. Add `CREATE INDEX IF NOT EXISTS` alongside the table creation.
- **Don't `SELECT *`.** Select only the columns you need.

---

## 9. Connection string examples

```java
// SQLite (file in user home)
"jdbc:sqlite:" + System.getProperty("user.home") + "/burp_state.db?busy_timeout=5000"

// PostgreSQL (local server)
"jdbc:postgresql://127.0.0.1:5432/burp_state"

// MySQL/MariaDB
"jdbc:mysql://127.0.0.1:3306/burp_state?useSSL=false&serverTimezone=UTC"

// H2 (embedded, file mode)
"jdbc:h2:" + System.getProperty("user.home") + "/burp_state;AUTO_SERVER=TRUE"
```

For Postgres/MySQL, **don't hardcode credentials in the script** — the Bambda file may be shared. Read them from environment variables:

```java
final String JDBC_URL  = System.getenv().getOrDefault("BURP_DB_URL", "jdbc:sqlite:/tmp/burp.db");
final String JDBC_USER = System.getenv().getOrDefault("BURP_DB_USER", "");
final String JDBC_PASS = System.getenv().getOrDefault("BURP_DB_PASS", "");
```

Or pull them from a file outside the script:

```java
var props = new java.util.Properties();
try (var in = new java.io.FileInputStream(System.getProperty("user.home") + "/.burp-db.properties")) {
    props.load(in);
}
var url  = props.getProperty("url");
var user = props.getProperty("user");
var pass = props.getProperty("password");
```

---

## 10. Full example: dedupe-with-DB scan check

```java
// === CONFIG ===
final String JDBC_URL  = "jdbc:sqlite:" + System.getProperty("user.home") + "/burp_state.db?busy_timeout=5000";
final String CHECK_ID  = "cors-reflection";

// === SANITY ===
if (!requestResponse.hasResponse()) return AuditResult.auditResult();

// === DRIVER ===
try { Class.forName("org.sqlite.JDBC"); }
catch (ClassNotFoundException e) {
    api().logging().logToError("SQLite driver missing - install from xerial.org");
    return AuditResult.auditResult();
}

// === PROBE ===
var canary = "https://" + api().utilities().randomUtils().randomString(10) + ".example.invalid";
var probe = http.sendRequest(requestResponse.request().withHeader("Origin", canary));
if (!probe.hasResponse()) return AuditResult.auditResult();

var aco = probe.response().headerValue("Access-Control-Allow-Origin");
if (aco == null || !aco.equalsIgnoreCase(canary)) return AuditResult.auditResult();

// === DEDUPE VIA DB ===
var url = requestResponse.request().url();
boolean isNew = false;
try (var conn = java.sql.DriverManager.getConnection(JDBC_URL)) {
    conn.setAutoCommit(false);

    try (var stmt = conn.createStatement()) {
        stmt.executeUpdate("""
            CREATE TABLE IF NOT EXISTS findings (
                check_id TEXT NOT NULL,
                url      TEXT NOT NULL,
                seen_at  DATETIME DEFAULT (datetime('now')),
                PRIMARY KEY (check_id, url)
            )
        """);
    }

    try (var ps = conn.prepareStatement(
            "INSERT OR IGNORE INTO findings (check_id, url) VALUES (?, ?)")) {
        ps.setString(1, CHECK_ID);
        ps.setString(2, url);
        isNew = ps.executeUpdate() > 0;
    }

    conn.commit();
} catch (java.sql.SQLException e) {
    api().logging().logToError("DB error: " + e.getMessage());
    // fail open: still report the issue this time
    isNew = true;
}

if (!isNew) return AuditResult.auditResult();

// === REPORT ===
return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "CORS: arbitrary origin reflection",
        "<p>The server reflected the attacker-controlled <code>Origin</code> header "
            + "<code>" + api().utilities().htmlUtils().encode(canary) + "</code>.</p>",
        "<p>Use a strict allowlist of permitted origins.</p>",
        url,
        AuditIssueSeverity.MEDIUM,
        AuditIssueConfidence.FIRM,
        "", "",
        AuditIssueSeverity.MEDIUM,
        probe
    )
);
```

Notice: SQLite uses `INSERT OR IGNORE` (not `ON CONFLICT DO NOTHING`, although that also works in modern SQLite). The check fails *open* on DB errors — better to occasionally report a duplicate than to miss a finding because the DB is down.
