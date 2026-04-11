# Java `Preferences` API for Bambda Persistence

`java.util.prefs.Preferences` is part of the JDK, so it's available in any Bambda with no setup. It's a hierarchical key-value store that persists to:

- **Linux/macOS:** `~/.java/.userPrefs/<node-path>/prefs.xml`
- **Windows:** the registry under `HKCU\Software\JavaSoft\Prefs\<node-path>`

This makes it a fine choice for **small, frequently-accessed state** that you want to survive Burp restarts.

---

## 1. Get a node, namespaced

Always namespace under your own path. Don't dump keys at the root — Preferences is shared across the entire JVM process, including any Burp extension that uses it.

```java
var prefs = java.util.prefs.Preferences.userRoot()
    .node("burp/bambdas/my-check-name");
```

You can nest nodes for organization:

```java
var hostNode = prefs.node("hosts/" + sanitize(host));
```

`Preferences` keys can contain any character, but `/` is interpreted as a path separator. **Sanitize input before using it as a key or node name** — strip slashes and control characters:

```java
String sanitize(String s) {
    return s.replaceAll("[^A-Za-z0-9._-]", "_");
}
```

---

## 2. Reading and writing primitives

```java
// Strings
prefs.put("last_seen_token", token);
var t = prefs.get("last_seen_token", "");           // second arg is default

// Booleans
prefs.putBoolean("baseline_recorded", true);
var b = prefs.getBoolean("baseline_recorded", false);

// Integers
prefs.putInt("seen_count", 0);
var n = prefs.getInt("seen_count", 0);

// Longs (use for timestamps)
prefs.putLong("baseline_ms", System.currentTimeMillis());

// Byte arrays (limited to ~3/4 of MAX_VALUE_LENGTH after Base64)
prefs.putByteArray("digest", bytes);
var bytes = prefs.getByteArray("digest", new byte[0]);
```

---

## 3. Atomic increment (the read-modify-write race)

The naive `getInt` + `putInt` is racy under Burp's parallel scan execution. Synchronize on the node:

```java
int incrementCounter(java.util.prefs.Preferences node, String key) {
    synchronized (node) {
        var current = node.getInt(key, 0);
        node.putInt(key, current + 1);
        return current + 1;
    }
}
```

This protects against races *within* the same JVM process. Burp scan checks all run in the same process so this is sufficient. If you need cross-process safety, use JDBC instead.

---

## 4. Dedupe pattern: "have I reported this before?"

This is the most common reason scan checks need persistence — to avoid reporting the same finding repeatedly across invocations.

```java
var prefs = java.util.prefs.Preferences.userRoot()
    .node("burp/bambdas/cors-reflection/seen");

var key = sanitize(requestResponse.request().url());

synchronized (prefs) {
    if (prefs.getBoolean(key, false)) {
        return AuditResult.auditResult();   // already reported
    }
    prefs.putBoolean(key, true);
    try { prefs.flush(); } catch (Exception ignored) {}
}

// ... build and return the issue ...
```

`flush()` forces the change to disk immediately. If you skip it, the JVM may delay writing for some time, and a Burp crash mid-scan will lose the dedupe state.

**Caveat:** this dedupe is *forever*. If the user wants per-scan dedupe, generate a session UUID at the top of the script and put it in the key:

```java
var sessionId = prefs.get("__session_id__", "");
// ...except the session ID itself needs to come from somewhere stable per-scan,
// which Bambdas can't easily provide. For per-scan dedupe, use the per-host
// scan check type instead - it's the right tool.
```

---

## 5. Storing a list of strings (Preferences has no native list type)

Use a delimiter-separated value, with the delimiter being something that can't appear in your data:

```java
final String SEP = "\u0001";  // SOH - never appears in normal text

void appendToList(java.util.prefs.Preferences node, String key, String value) {
    synchronized (node) {
        var existing = node.get(key, "");
        var updated  = existing.isEmpty() ? value : existing + SEP + value;
        node.put(key, updated);
    }
}

java.util.List<String> readList(java.util.prefs.Preferences node, String key) {
    var raw = node.get(key, "");
    if (raw.isEmpty()) return java.util.List.of();
    return java.util.Arrays.asList(raw.split(SEP));
}
```

**Watch the limit.** Each value is capped at `Preferences.MAX_VALUE_LENGTH` (8192 chars on most JDKs). For longer lists, use child nodes instead:

```java
var listNode = prefs.node("seen_tokens");
listNode.put(sanitize(token), "");   // each token is its own key, value is empty
// Later:
var tokens = listNode.keys();         // String[]
```

This scales to thousands of entries without hitting the value-length cap.

---

## 6. Clearing state

The user will occasionally want to wipe accumulated state. Document the cleanup approach in the script's javadoc comment, and provide a reset switch via config:

```java
final boolean RESET_STATE = false;

var prefs = java.util.prefs.Preferences.userRoot()
    .node("burp/bambdas/my-check");

if (RESET_STATE) {
    try {
        prefs.removeNode();
        prefs.flush();
    } catch (java.util.prefs.BackingStoreException e) {
        api().logging().logToError("Failed to reset state: " + e);
    }
    return AuditResult.auditResult();
}
```

The user flips `RESET_STATE` to `true`, runs the check once, then flips it back.

---

## 7. Size and shape limits

| Limit | Value | Notes |
|---|---|---|
| `Preferences.MAX_KEY_LENGTH` | 80 chars | Sanitize and truncate |
| `Preferences.MAX_VALUE_LENGTH` | 8192 chars | Use child nodes for larger |
| `Preferences.MAX_NAME_LENGTH` | 80 chars | For node names |
| Total store size | OS-dependent | Treat <1MB as the soft cap |

If you bump into any of these, you've outgrown Preferences. Switch to JDBC.

---

## 8. Full example: dedupe + count

```java
// === CONFIG ===
final boolean RESET_STATE = false;
final String  CHECK_ID    = "missing-csp";

// === SETUP ===
var prefs = java.util.prefs.Preferences.userRoot()
    .node("burp/bambdas/" + CHECK_ID);
var seen  = prefs.node("seen");

if (RESET_STATE) {
    try { prefs.removeNode(); prefs.flush(); } catch (Exception ignored) {}
    return AuditResult.auditResult();
}

if (!requestResponse.hasResponse()) return AuditResult.auditResult();
if (requestResponse.response().hasHeader("Content-Security-Policy")) {
    return AuditResult.auditResult();
}

// === DEDUPE ===
var url = requestResponse.request().url();
var key = url.replaceAll("[^A-Za-z0-9._-]", "_");
if (key.length() > 80) key = key.substring(0, 80);

synchronized (seen) {
    if (seen.getBoolean(key, false)) {
        return AuditResult.auditResult();
    }
    seen.putBoolean(key, true);

    // Bump the global counter too.
    var count = prefs.getInt("total_findings", 0) + 1;
    prefs.putInt("total_findings", count);

    try { prefs.flush(); } catch (Exception ignored) {}
}

// === REPORT ===
return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "Missing CSP header",
        "<p>Response lacks <code>Content-Security-Policy</code>.</p>",
        "<p>Add a CSP header.</p>",
        url,
        AuditIssueSeverity.LOW,
        AuditIssueConfidence.FIRM,
        "", "",
        AuditIssueSeverity.LOW,
        requestResponse
    )
);
```
