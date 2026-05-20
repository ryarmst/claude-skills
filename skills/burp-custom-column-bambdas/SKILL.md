---
name: burp-custom-column-bambdas
description: Author Burp Suite Custom Column Bambdas (CUSTOM_COLUMN function). Use when the user wants to write, modify, debug, or review a script that adds a column to the HTTP history, Logger, or WebSockets history table — including extracting header values, parsing JWT claims, counting parameters, detecting content types, decoding tokens, scoring requests, and any other per-row data extraction. Triggers on phrases like "custom column", "table column", "Logger column", "HTTP history column", "CUSTOM_COLUMN", or any request for a script that surfaces per-row data in a Burp table.
---

# Burp Custom Column Bambdas

A Custom Column Bambda is a **`CUSTOM_COLUMN` Bambda** — a Java code body that Burp runs against every visible row in a table (Logger, Proxy HTTP history, or WebSockets history) to compute a cell value. The return value becomes the cell text; the column is sortable for triage across large traffic sets.

For other Bambda types (scan checks, filters, match-and-replace), use **burp-bambdas**. For Repeater custom actions, use **burp-repeater-actions**.

Read this whole file. Then load `references/api.md`. Then write code.

---

## 1. What custom columns can do

- Surface any request or response field: header values, parameter counts, body fragments, HTTP version, in-scope flag
- Decode and display opaque tokens: JWT claims, base64 values
- Score or classify rows for triage: CSP quality, interesting parameter names, CORS reflection hints
- Count things: parameters, cookies, headers, pattern matches
- Detect patterns: SameSite=None cookies, dangerous CSP directives, GraphQL operation names
- Apply regex extraction to request or response bodies
- Format multi-value results as comma-joined strings
- Show timing data when rows include `timingData()` (slow-response triage)

Custom columns **cannot** send HTTP requests, modify traffic, log to an output panel, or interact with other Burp tools — those are **burp-repeater-actions** or scan-check capabilities. Custom columns are read-only observers.

---

## 2. The .bambda file format

```yaml
id: <UUIDv4>
name: <Human readable name>
function: CUSTOM_COLUMN
location: <LOGGER | PROXY_HTTP_HISTORY | PROXY_WS_HISTORY>
burpglobal:
  column-target-header: Server       # optional tunable (string)
source: |
  /**
   * <One-line purpose>
   * @author <name or handle>
   **/

  <java code body — must return a String, Number, or boolean>
```

### Location values

| `location:` | Table |
|---|---|
| `LOGGER` | Logger tab (all tools — recommended default) |
| `PROXY_HTTP_HISTORY` | Proxy → HTTP history |
| `PROXY_WS_HISTORY` | Proxy → WebSockets history |

Use `LOGGER` when the column should appear across traffic from Proxy, Repeater, Scanner, and other tools. Create separate `.bambda` files per location if the same logic is needed in multiple tables.

### Column naming

The header shown in the table is set in the UI (**Column header** field when adding the column), not in the YAML. The `name:` field is the Bambda library display name only.

---

## 3. Objects in scope

Only **two** objects are available:

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `ProxyHttpRequestResponse` or `ProxyWebSocketMessage` | Read-only row data. |
| `utilities` | `Utilities` | Bare field — `utilities.jsonUtils()`, **not** `utilities()`. |

### Critical differences from CUSTOM_ACTION

| | CUSTOM_COLUMN | CUSTOM_ACTION |
|---|---|---|
| Trigger | Automatic, every visible row | Manual button click |
| Return | `String`, `int`, or `boolean` | `void` (side effects) |
| `api()` | ✗ | ✓ |
| `logging()` | ✗ | ✓ |
| `utilities` | Bare field | Method: `utilities()` |
| Performance | Critical — per-row, per-update | Low concern |

- **No `api()`** — cannot send requests or access Montoya API root.
- **No `logging()`** — debug via the Bambda editor's Test function and output console.
- **No gate global** — columns run on every row automatically. Remove unwanted columns from the table; do not gate with `return ""`.
- **Optional tunables** — read `System.getProperty("bg.column-*")` with hardcoded fallbacks for configurable header names, patterns, or thresholds.

### Return type and sorting

| Return type | Column behaviour |
|---|---|
| `String` | Text; sorted lexicographically |
| `Integer` / `int` | Number; sorted numerically — use for counts and scores |
| `Boolean` / `boolean` | Displayed as `true`/`false` |
| `""` | Blank cell — use for "not applicable" |

Always return `""` (never `null`) when there is nothing to show.

Burp catches NullPointerExceptions at the row level and leaves the cell blank. Guard with `hasResponse()` when accessing response fields to keep intent explicit.

---

## 4. Performance

**The most important constraint.** The script runs on every visible row every time the table updates — potentially thousands of invocations per second under active traffic.

Rules:
- **No network calls** — `api()` is unavailable; HTTP per row would freeze Burp anyway.
- **No database / persistence I/O** — see §8. Never query BurpDB, Preferences, or JDBC per row.
- **No blocking operations** — no file I/O, sleeps, or locks.
- **Prefer built-in methods** — `headerValue("X-Foo")` beats manual header iteration.
- **Prefer `contains()` over regex** when a substring check suffices.
- **Short-circuit early** — `hasResponse()` first; return `""` as soon as the row is irrelevant.
- **Keep regex simple** — compile `Pattern` once if possible; avoid heavy body scans on large responses.

---

## 5. Burp Globals — optional tunables

Unlike scan checks and Repeater actions, custom columns **do not use a gate global**. Optional configuration only:

```java
final String HEADER = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.column-target-header"), "Server"
);
```

Declare tunables in the YAML `burpglobal:` block. Read with `bg.` prefix at runtime.

---

## 6. Common patterns

### Pattern 1 — Extract a response header value

```java
if (!requestResponse.hasResponse()) {
    return "";
}
return requestResponse.response().hasHeader("Server")
    ? requestResponse.response().headerValue("Server")
    : "";
```

### Pattern 2 — Count something (numeric sort)

```java
return requestResponse.request().parameters().size();
```

### Pattern 3 — Regex extraction from body

```java
var body = requestResponse.request().bodyToString();
var m = java.util.regex.Pattern.compile("\"operationName\"\\s*:\\s*\"([^\"]+)\"").matcher(body);
return m.find() ? m.group(1) : "";
```

### Pattern 4 — JWT claim from Authorization header

```java
var auth = requestResponse.request().headerValue("Authorization");
if (auth == null || !auth.startsWith("Bearer ")) return "";
var parts = auth.substring(7).split("\\.");
if (parts.length != 3) return "";
try {
    var payload = utilities.base64Utils().decode(parts[1], Base64DecodingOptions.URL).toString();
    return utilities.jsonUtils().readString(payload, "sub");
} catch (Exception e) {
    return "";
}
```

Use `finalRequest()` instead of `request()` when proxy match-and-replace may have altered headers.

### Pattern 5 — Slow responses (timing column)

```java
var delta = requestResponse.timingData().timeBetweenRequestSentAndStartOfResponse();
if (delta != null && delta.toMillis() >= 3000) {
    return delta.toMillis();
}
return "";
```

### Pattern 6 — Boolean flag column

```java
if (!requestResponse.hasResponse()) return false;
return !requestResponse.response().hasHeader("Strict-Transport-Security");
```

### Pattern 7 — JSON field from response body

```java
if (!requestResponse.hasResponse()) return "";
var ct = requestResponse.response().headerValue("Content-Type");
if (ct == null || !ct.contains("application/json")) return "";
return utilities.jsonUtils().readString(requestResponse.response().bodyToString(), "user.role");
```

See `templates/` for drop-in starting points and `references/api.md` for the full API surface.

---

## 7. Gotchas

1. **`utilities` is a bare field** — `utilities.base64Utils()`, not `utilities().base64Utils()`.

2. **Correct `location:` values** — `PROXY_HTTP_HISTORY` and `PROXY_WS_HISTORY`, not `HTTP_HISTORY` or `WEBSOCKETS_HISTORY`.

3. **No `logging()`.** Debug in the Add custom column editor's Test function.

4. **Return `""` not `null`.** Null may render as the literal `"null"`.

5. **Return type sets sort behaviour.** Use `int` for counts/scores; `String` for text.

6. **No `import` statements, no `class` wrapper.** Use fully-qualified JDK types where needed.

7. **`finalRequest()` vs `request()`.** After proxy transformations, `finalRequest()` reflects what was actually sent.

8. **Columns are sortable.** Design return values with sorting in mind — numeric scores sort usefully; padded strings do not.

9. **Re-importing with the same `id`** updates the library entry; a new `id` creates a duplicate.

---

## 8. Persistence — almost never

Custom columns re-run on **every visible row on every table refresh**. Cross-invocation persistence (BurpDB, Java Preferences, JDBC) is documented in **burp-bambda-persistence**, but **do not use it in custom columns under normal circumstances** — a per-row database round-trip will freeze Burp.

Acceptable alternatives:
- Derive the cell value from `requestResponse` alone (headers, body, timing, scope).
- For small shared config (e.g. a regex pattern), use **Burp Globals** tunables — not a database.
- If the user needs durable cross-run state displayed in a table, recommend a **scan check** or **Repeater action** that writes findings, not a column that reads a store per row.

---

## 9. Workflow

1. **Identify what to surface**: which field, pattern, or derived value helps triage?
2. **Choose location**: `LOGGER` (default), `PROXY_HTTP_HISTORY`, or `PROXY_WS_HISTORY`.
3. **Load `references/api.md`** for method names and proxy-row extras.
4. **Pick a template** from `templates/` or a pattern from §6.
5. **Keep it fast**: short-circuit early; no I/O; prefer API helpers over regex.
6. **Generate a fresh UUIDv4** for the `id` field.
7. **Test in the editor** with the built-in Test function before saving to the library.
8. **Self-check before delivering:**
   - Returns `String`, `int`/`Integer`, or `boolean`/`Boolean`?
   - Returns `""` (not `null`) for the empty case?
   - No `logging()`, no `api()`, no persistence I/O?
   - Uses `utilities.base64Utils()` (bare field)?
   - No `import` statements, no `class` wrapper?
   - `function: CUSTOM_COLUMN` and valid `location` in YAML?
   - JavaDoc header with description and `@author` tag?
   - Fresh UUID in `id`?

---

## Reference files

- `references/api.md` — full API surface, proxy-row extras, timing, JWT helpers, one-liners.
- `templates/` — drop-in `.bambda` skeletons (header extract, param count, regex extract).
- `summary.md` — template index and import steps.
