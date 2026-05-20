---
name: burp-custom-columns
description: Author Burp Suite Custom Column Bambdas (CUSTOM_COLUMN function). Use when the user wants to write, modify, debug, or review a script that adds a column to the HTTP history, Logger, or WebSockets history table — including extracting header values, parsing JWT claims, counting parameters, detecting content types, decoding tokens, scoring requests, and any other per-row data extraction. Triggers on phrases like "custom column", "table column", "Logger column", "HTTP history column", "CUSTOM_COLUMN", or any request for a script that surfaces per-row data in a Burp table.
---

# Burp Custom Column Bambdas

A Custom Column Bambda is a **`CUSTOM_COLUMN` Bambda** — a Java code body that Burp runs against every visible row in a table (Logger, HTTP history, or WebSockets history) to compute a cell value. The script returns a value which Burp displays in the column. The column is also sortable, enabling triage and prioritisation across large traffic sets.

Read this whole file. Then load `references/api.md`. Then write code.

---

## 1. What custom columns can do

- Surface any request or response field as a column: header values, parameter counts, body fragments, HTTP version, in-scope flag
- Decode and display opaque tokens: JWT claims, base64 values, serialised objects
- Score or classify rows for triage: "hackable" score, CSP quality, interesting parameter names
- Count things: parameters, cookies, headers, matches of a pattern
- Detect patterns: SameSite=None cookies, dangerous CSP directives, GraphQL operation names
- Apply regex extraction to request or response bodies
- Format multi-value results as comma-joined strings for readability

Custom columns **cannot** send HTTP requests, modify the traffic, log to an output panel, or interact with other Burp tools — those are CUSTOM_ACTION capabilities. Custom columns are read-only observers.

---

## 2. The .bambda file format

```yaml
id: <UUIDv4>
name: <Human readable name>
function: CUSTOM_COLUMN
location: <LOGGER | HTTP_HISTORY | WEBSOCKETS_HISTORY>
source: |
  /**
   * <One-line purpose>
   * @author <name or handle>
   **/

  <java code body — must return a String or Number>
```

### Location values

| Location | Table |
|---|---|
| `LOGGER` | Logger tab |
| `HTTP_HISTORY` | Proxy → HTTP history |
| `WEBSOCKETS_HISTORY` | Proxy → WebSockets history |

A script works identically in Logger and HTTP history — the same `requestResponse` API is available in both. Create one per location if you want it in multiple tables, or use `LOGGER` as the default (it captures all traffic from all tools).

### Column naming

The name shown in the column header is set in the UI at load time (**Column header** field), not in the `.bambda` file. The `name:` YAML field is the library display name only.

---

## 3. Objects in scope

Only **two** objects are available — a critical difference from CUSTOM_ACTION:

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | The request/response pair for this row. Read-only. |
| `utilities` | `Utilities` | Helper functions (encoding, crypto, JSON, byte utils). **Bare field — no parens.** |

### Critical differences from CUSTOM_ACTION

- **No `api()`** — cannot send requests, route to tools, or access Montoya API root.
- **No `logging()`** — there is no output panel for columns. Use the Burp Bambda output console for debugging during development.
- **No `selection`** — columns have no concept of user text selection.
- **`utilities` is a bare field**, not a method: `utilities.base64Utils()`, not `utilities()`.
- **No Burp Globals gate** — columns run automatically on every row. Do not add a gate check; there's nothing to gate. If Burp Globals values are needed (e.g. a configurable pattern), read them with `System.getProperty("bg.variable-name")` directly, with a hardcoded default as fallback.

### Return type

The script must end with a `return` statement. The value determines column behaviour:

| Return type | Column behaviour |
|---|---|
| `String` | Displayed as text; sorted lexicographically |
| `Integer` / `int` | Displayed as number; sorted numerically — use for counts and scores |
| `Boolean` / `boolean` | Displayed as `true`/`false`; useful for flag columns |
| `""` (empty string) | Cell is blank — the correct sentinel for "not applicable" |

Always return `""` (never `null`) when there is nothing to show. Returning `null` may display as the string `"null"` in some Burp versions.

### NullPointerExceptions

Burp catches NPEs at the row level and leaves the cell blank. The PortSwigger research team explicitly relies on this: *"we haven't bothered avoiding null pointer exceptions — they're handled for us at the row-level."*

You may omit null guards for brevity in simple scripts, but a `hasResponse()` guard is still recommended for clarity when accessing response fields, since it makes intent explicit and avoids spurious blank cells during traffic capture.

---

## 4. Performance

**This is the most important constraint for custom columns.** The script runs on every visible row every time the table updates — which can be thousands of times per second under active traffic. An expensive script will freeze Burp.

Rules:
- **No network calls** — even if `api()` were available (it isn't), making HTTP requests per row would be catastrophic.
- **No blocking operations** — no file I/O, no sleeps, no locks.
- **Prefer built-in API methods** over hand-rolled string scanning. `headerValue("X-Foo")` is faster than iterating `headers()` manually.
- **Prefer `contains()` over regex** when a simple substring check suffices.
- **Compile `Pattern` objects once** — if regex is unavoidable, declare the pattern as a `static final` equivalent using a variable hoisted before the return, or accept that it will be recompiled each row.
- **Short-circuit early** — check `hasResponse()` before any response access; check `hasHeader()` before `headerValue()`.
- Return `""` as soon as you know the row is not relevant.

---

## 5. Common patterns

### Pattern 1 — Extract a response header value

```java
if (!requestResponse.hasResponse()) {
    return "";
}
return requestResponse.response().hasHeader("Server")
    ? requestResponse.response().headerValue("Server")
    : "";
```

The simplest and most common pattern. Works for any header. Use for: `Server`, `X-Powered-By`, `Content-Type`, `X-Frame-Options`, `Access-Control-Allow-Origin`, etc.

### Pattern 2 — Count something (returns Integer for numeric sort)

```java
// Number of request parameters — good for attack-surface triage.
return requestResponse.request().parameters().size();
```

```java
// Number of Set-Cookie headers in the response.
if (!requestResponse.hasResponse()) {
    return 0;
}
return (int) requestResponse.response().headers().stream()
    .filter(h -> h.name().equalsIgnoreCase("Set-Cookie"))
    .count();
```

Returning an `int` or `Integer` enables numeric sorting — far more useful than lexicographic for counts.

### Pattern 3 — Regex extraction from body

```java
// Extract GraphQL operation name from request body.
var body = requestResponse.request().bodyToString();
var m = java.util.regex.Pattern.compile("\"operationName\"\\s*:\\s*\"([^\"]+)\"").matcher(body);
return m.find() ? m.group(1) : "";
```

### Pattern 4 — Multi-value detection (joined string)

```java
// Find cookies with SameSite=None — security-relevant for CSRF analysis.
if (!requestResponse.hasResponse()) {
    return "";
}
var names = new java.util.ArrayList<String>();
var pattern = java.util.regex.Pattern.compile("^\\s*([^=]+).+;\\s*SameSite=None", java.util.regex.Pattern.CASE_INSENSITIVE);
for (var header : requestResponse.response().headers()) {
    if (!header.name().equalsIgnoreCase("Set-Cookie")) continue;
    var matcher = pattern.matcher(header.value());
    if (matcher.find()) {
        names.add(matcher.group(1).trim());
    }
}
return String.join(", ", names);
```

### Pattern 5 — Decode a request header value

```java
// Base64-decode the Authorization bearer token payload (first 100 chars).
var auth = requestResponse.request().headerValue("Authorization");
if (auth == null || !auth.startsWith("Bearer ")) {
    return "";
}
var token = auth.substring(7).trim();
try {
    var decoded = new String(java.util.Base64.getUrlDecoder().decode(token));
    return decoded.length() > 100 ? decoded.substring(0, 100) + "…" : decoded;
} catch (Exception e) {
    return token;  // show raw if not decodable
}
```

### Pattern 6 — JSON field extraction from response body

```java
// Extract a specific field from a JSON response.
if (!requestResponse.hasResponse()) {
    return "";
}
var contentType = requestResponse.response().headerValue("Content-Type");
if (contentType == null || !contentType.contains("application/json")) {
    return "";
}
return utilities.jsonUtils().readString(requestResponse.response().bodyToString(), "user.role");
```

### Pattern 7 — Boolean / flag column

```java
// Flag requests that are in scope.
return requestResponse.request().isInScope();
```

```java
// Flag responses missing HSTS.
if (!requestResponse.hasResponse()) {
    return false;
}
return !requestResponse.response().hasHeader("Strict-Transport-Security");
```

### Pattern 8 — Display request metadata

```java
// HTTP version — useful for HTTP/2 vs HTTP/1.1 smuggling triage.
return requestResponse.request().httpVersion();
```

```java
// Referer header — useful for understanding request flow.
var ref = requestResponse.request().headerValue("Referer");
return ref != null ? ref : "";
```

---

## 6. Gotchas

1. **`utilities` is a bare field.** Use `utilities.base64Utils()`, `utilities.jsonUtils()`, etc. — no parens on `utilities` itself. This is the opposite of CUSTOM_ACTION where `utilities()` is a method.

2. **No `logging()`.** There is no output panel. For debugging during development, use the Burp Bambda output console (available when editing the script in the Add custom column dialog).

3. **Return `""` not `null`.** Returning null may render as the literal string `"null"` in some Burp versions. Always return an explicit empty string for the "nothing to show" case.

4. **Return type sets sort behaviour.** If a column should sort numerically (counts, scores), return `int`. If it should sort lexicographically, return `String`. Mixed types within a column cause unpredictable sort order — be consistent.

5. **NullPointerExceptions are swallowed.** Burp catches them at row level. This is intentional and documented. For quick scripts, you can omit null guards and rely on this behaviour. For production-quality scripts, guard explicitly.

6. **No `import` statements, no `class` wrapper.** Use fully-qualified names for types outside `burp.api.montoya.*`: `java.util.ArrayList`, `java.util.regex.Pattern`, etc.

7. **`hasResponse()` vs null check.** `requestResponse.hasResponse()` is the idiomatic guard. Equivalent to `requestResponse.response() != null` but more readable.

8. **`utilities.byteUtils().countMatches()`** is available for byte-level scanning and more efficient than converting to String when the data is binary.

9. **The column name is set in the UI.** The `name:` in the YAML is the Bambda library display name. The column header the user sees in the table is configured separately in the **Column header** field of the Add custom column dialog.

10. **Columns can be sorted.** This is a major feature — design your return values with sorting in mind. A numeric score column lets the user sort by "most interesting" instantly.

---

## 7. Workflow

1. **Identify what to surface**: what field, pattern, or derived value would help triage this table?
2. **Choose the location**: `LOGGER` (all tools), `HTTP_HISTORY` (Proxy only), or `WEBSOCKETS_HISTORY`.
3. **Load `references/api.md`** for the available API surface.
4. **Pick a pattern** from §5 or combine patterns.
5. **Keep it fast**: no regex if a simple `contains()` works; short-circuit with `hasResponse()` early.
6. **Generate a fresh UUIDv4** for the `id` field.
7. **Self-check before delivering:**
   - Returns `String`, `int`/`Integer`, or `boolean`/`Boolean`?
   - Returns `""` (not `null`) for the empty case?
   - No `logging()`, no `api()`, no `selection`?
   - Uses `utilities.base64Utils()` (bare field), not `utilities().base64Utils()`?
   - No `import` statements, no `class` wrapper?
   - `function: CUSTOM_COLUMN` and valid `location` in YAML?
   - JavaDoc header with description and `@author` tag?
   - Fresh UUID in `id`?
