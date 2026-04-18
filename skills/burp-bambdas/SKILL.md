---
name: burp-bambdas
description: Author Burp Suite Bambda scripts (custom scan checks, HTTP/WebSocket history filters, custom columns, and match-and-replace rules). Use whenever the user wants to write, modify, debug, or review a `.bambda` file or any Java snippet that runs inside Burp Suite Professional/Community via the Bambda runtime — including scan checks (active/passive, per-host/per-request/per-insertion-point), Proxy HTTP/WS history view filters, custom table columns, or proxy match-and-replace rules. For Repeater custom actions specifically, use the `burp-repeater-actions` skill instead. Triggers on phrases like "Bambda", "custom scan check", "Burp filter script", "view filter", "custom column for Burp", "Montoya scan check", or any reference to Burp's `function: SCAN_CHECK_*`, `VIEW_FILTER`, `CUSTOM_COLUMN`, `MATCH_AND_REPLACE_*` constants.
---

# Burp Bambdas

This skill produces drop-in Burp Suite Bambda code. A Bambda is a Java *code body* (not a class, not a file with `import`s) executed inside a Burp-generated function. There are several distinct **function types**, each with completely different in-scope objects, return types, and constraints. **You must identify the function type before writing a single line.**

Read this whole file. Then load the reference file for the function type you're targeting. Then write code.

---

## 1. Step 1 — Pick the function type (mandatory)

Bambdas are not interchangeable. The same code that works as a scan check is a syntax error as a view filter. Before writing anything, determine which of these the user wants:

| Burp area | `function:` constant | Return type | Reference |
|---|---|---|---|
| Active scan check, runs once per host | `SCAN_CHECK_ACTIVE_PER_HOST` | `AuditResult` | `references/scan_checks.md` |
| Active scan check, runs per base request | `SCAN_CHECK_ACTIVE_PER_REQUEST` | `AuditResult` | `references/scan_checks.md` |
| Active scan check, runs per insertion point | `SCAN_CHECK_ACTIVE_PER_INSERTION_POINT` | `AuditResult` | `references/scan_checks.md` |
| Passive scan check, runs once per host | `SCAN_CHECK_PASSIVE_PER_HOST` | `AuditResult` | `references/scan_checks.md` |
| Passive scan check, runs per base request | `SCAN_CHECK_PASSIVE_PER_REQUEST` | `AuditResult` | `references/scan_checks.md` |
| Passive scan check, runs per insertion point | `SCAN_CHECK_PASSIVE_PER_INSERTION_POINT` | `AuditResult` | `references/scan_checks.md` |
| Proxy HTTP/WS history view filter | `VIEW_FILTER` | `boolean` | `references/filters_columns_actions_mr.md` |
| Custom table column | `CUSTOM_COLUMN` | `String` | `references/filters_columns_actions_mr.md` |
| Repeater/Intruder custom action | `CUSTOM_ACTION` | `void` (side effects via editor APIs) | `references/filters_columns_actions_mr.md` |
| Proxy match & replace, request | `MATCH_AND_REPLACE_REQUEST` | `HttpRequest` | `references/filters_columns_actions_mr.md` |
| Proxy match & replace, response | `MATCH_AND_REPLACE_RESPONSE` | `HttpResponse` | `references/filters_columns_actions_mr.md` |

### How to choose

If the user just says "write me a Bambda for X", use this decision tree, and **only ask the user when the request is genuinely ambiguous after running through it**:

1. Does the user want to *find a vulnerability* / report an issue? → **Scan check.** Now disambiguate (see below).
2. Does the user want to *show/hide rows in HTTP history or WS history*? → `VIEW_FILTER`.
3. Does the user want to *add a column* to a Burp table? → `CUSTOM_COLUMN`.
4. Does the user want to *transform a request or response in flight*? → `MATCH_AND_REPLACE_REQUEST` or `_RESPONSE`.
5. Does the user want a *button in Repeater/Intruder* that operates on the current request? → `CUSTOM_ACTION`.

### Disambiguating scan checks

If it's a scan check, you **must** decide three orthogonal axes. If any is unclear from context, ask the user a single consolidated question — do not guess silently for scan checks, because the wrong axis produces a working-but-wasteful or working-but-broken script (e.g., a per-insertion-point check coded as per-request will never see `insertionPoint`).

1. **Active or passive?**
   - *Passive* = inspect the existing `requestResponse` only, send no traffic. Use for missing headers, error message disclosure, info leaks, cookie attribute checks.
   - *Active* = send additional crafted requests via `http.sendRequest(...)`. Use for SQLi, SSTI, CORS reflection, prototype pollution, command injection.

2. **Per host / per request / per insertion point?**
   - *Per host* = runs once per origin during a scan. Use for host-level configuration probes (e.g., is `/.git/HEAD` exposed, does `OPTIONS *` work, TLS-level checks). `requestResponse` is the seed request for the host.
   - *Per request* = runs once per audited base request. Use when the test depends on the specific URL/method/body but does not need to mutate a single parameter. CORS reflection, missing CSP, TRACE method, server-side prototype pollution against a JSON endpoint.
   - *Per insertion point* = runs once per parameter / header / cookie / body location Burp identifies. The variable `insertionPoint` is in scope. Use when payloads must replace a specific input value: SQLi, XSS, SSTI, command injection, parameter-level SSRF.

3. **Use Collaborator?** Only if testing OOB issues (blind SSRF, blind SQLi, blind XSS, email splitting, log injection that escapes to a logger that resolves URLs, etc.). Collaborator must be enabled in the script settings; the variable `collaboratorClient` is then in scope, OR you can create one explicitly with `api().collaborator().createClient()`.

When you ask the user, present these as one batched multi-choice elicitation, not three rounds of questions.

---

## 2. The .bambda file format

A `.bambda` file is YAML-with-embedded-source. Burp's GitHub samples all use this format and it's what the user will import. When the user wants a "Bambda file" (as opposed to "just the code body"), produce the full file:

```yaml
id: <UUIDv4>
name: <Human readable name>
function: <ONE OF THE CONSTANTS ABOVE>
location: <SCANNER | PROXY_HTTP_HISTORY | PROXY_WS_HISTORY | REPEATER | INTRUDER | LOGGER | SITE_MAP>
burpglobal:
  <gate-global>: false  # master on/off; set true to enable (bool)
  <optional-global>: <default>  # brief purpose (type)
source: |
  /**
   * <One-line purpose>
   * @author <name or handle>
   **/

  <java code body>
```

Notes:
- `id` must be a fresh random UUIDv4. Generate one — never reuse one from samples.
- `location` for scan checks is always `SCANNER`.
- `location` for `VIEW_FILTER` is `PROXY_HTTP_HISTORY`, `PROXY_WS_HISTORY`, `LOGGER`, or `SITE_MAP` depending on where the user wants the filter to apply. Default to `PROXY_HTTP_HISTORY` if unspecified.
- `location` for `CUSTOM_COLUMN` matches the table the column lives in: `PROXY_HTTP_HISTORY`, `PROXY_WS_HISTORY`, `LOGGER`.
- `location` for `CUSTOM_ACTION` is `REPEATER` or `INTRUDER`.
- `location` for `MATCH_AND_REPLACE_*` is `PROXY_HTTP_HISTORY`.
- Indent the source body with 2 spaces under `source: |`. Burp tolerates `|+` (preserve trailing newlines) — either is fine.

If the user only wants the code body (e.g., they're pasting into Burp's editor directly), skip the YAML wrapper and emit just the Java.

---

## 3. Universal rules — what is and is NOT in a Bambda

A Bambda is a Java method body, **not** a Java file. Cursor-style prompts that tell you to write `import` statements or `class { }` wrappers are wrong. Real Burp samples confirm the following.

**NEVER write:**
- `import` statements
- `package` statements
- A `class`, `interface`, or `enum` declaration wrapping the code
- A `public static void main`
- Code that requires loading external JARs or Maven dependencies

**You CAN use:**
- `var` and modern Java syntax (records, text blocks, lambdas, switch expressions). Real samples use Java 17+.
- The fully-qualified Java standard library where needed: `java.util.ArrayList`, `java.util.HashMap`, `java.util.concurrent.TimeUnit`, `java.util.UUID`, `java.util.regex.Pattern`, `java.util.function.Function`, `java.time.*`, `java.nio.charset.StandardCharsets`, `java.util.HexFormat`, etc.
- Local helper methods declared inline at the bottom of the script (Java 17 supports this in instance method bodies as anonymous local methods only via lambdas; in Bambdas you generally inline logic or use `java.util.function.Function<>` lambdas instead — see the EmailSplitting sample).
- Threads and `Thread.sleep` / `TimeUnit.MILLISECONDS.sleep(...)`. The `EmailSplittingCollaboratorClient` sample explicitly sleeps in a poll loop. Threads are necessary for scan checks that wait on Collaborator — do not remove them.
- All Montoya types **without imports** — Burp's Bambda compiler auto-imports the entire `burp.api.montoya.*` tree. So `HttpRequest`, `HttpResponse`, `HttpRequestResponse`, `ByteArray`, `AuditIssue`, `AuditIssueSeverity`, `AuditIssueConfidence`, `AuditResult`, `HttpParameter`, `HttpParameterType`, `MimeType`, `StatusCodeClass`, `HttpMode`, `Interaction`, `DigestAlgorithm`, `AttributeType`, etc. are all directly usable.

**The entry point varies by function type** — this is a common source of bugs. Real Burp samples confirm:

| Function type | How to access utilities | How to send HTTP | Notes |
|---|---|---|---|
| `SCAN_CHECK_*` | `api().utilities()` (sometimes `utilities()` works depending on Burp version — prefer `api().utilities()`) | `http.sendRequest(...)` (bare `http` is in scope) | **No logging interface.** Do not use `api().logging()` or `logging`. |
| `VIEW_FILTER`, `CUSTOM_COLUMN`, `MATCH_AND_REPLACE_*` | `utilities` (no parens — it's a field, not a method) | n/a (filters/columns are passive) | **No logging interface.** Do not use `logging` or `api().logging()`. |
| `CUSTOM_ACTION` | `utilities()` and `logging()` and `api().http()` for sending | `api().http().sendRequest(...)` | `logging()` **IS available**. `httpEditor`/`wsEditor` is in scope to mutate the active editor pane. |

If you're unsure for a given function type, the safest universal pattern is: in scan checks use `api().utilities()`; in everything else use `utilities` as a bare identifier. See `references/montoya_api_cheatsheet.md` for the full surface.

---

## 4. Common gotchas (read these — they cause silent failures)

1. **`requestResponse` may have no response.** Always guard:
   ```java
   if (!requestResponse.hasResponse()) return AuditResult.auditResult();
   ```
   For passive checks this is a hard requirement. For active per-request checks, sometimes you still want to proceed (the active check provides its own response).

2. **`insertionPoint` is only in scope for `SCAN_CHECK_*_PER_INSERTION_POINT`.** Never reference it from a per-host or per-request check — it will fail to compile. Conversely, in per-insertion-point checks, do **not** mutate `requestResponse.request()` directly to insert payloads; use:
   ```java
   var attackReq = insertionPoint.buildHttpRequestWithPayload(ByteArray.byteArray(payload));
   var attackRR = http.sendRequest(attackReq);
   ```
   Burp handles encoding the payload into the right place (URL-encoded query, JSON-escaped body, header value, etc.).

3. **Returning `null` vs `AuditResult.auditResult()`.** Both are accepted by Burp's scan-check runtime as "no issue". `AuditResult.auditResult()` is clearer; `return null;` appears in several official samples. Either is fine — be consistent within a script.

4. **Duplicate issue suppression.** Burp deduplicates on issue title + URL by default. If your check legitimately wants to report the same title for multiple findings, vary the title (e.g., include the affected parameter name).

5. **HTML in issue detail/background fields.** Burp renders these as HTML. Always run untrusted text (payloads, response snippets, parameter values) through `api().utilities().htmlUtils().encode(...)` before concatenation. **`<table>` is not supported** — Burp's renderer does not recognise table tags and displays them as raw text. Use `<ul>`/`<li>` with inline labels to present tabular data instead.

6. **Thread safety.** Burp may run multiple instances of your check in parallel for different requests. Do **not** use script-level mutable static state for cross-invocation memory — it isn't shared and isn't safe. For genuine cross-invocation persistence, see the separate `burp-bambda-persistence` skill.

7. **Performance.** Burp warns that slow scripts slow down the whole scan. Bound your loops, cap retry counts, and never loop on Collaborator polling without a `TOTAL_TIME` ceiling.

8. **`requestResponse` shape differs by function type.** In scan checks it's an `AuditInsertionPoint`-aware `HttpRequestResponse`. In `VIEW_FILTER` / `CUSTOM_COLUMN` it's a `ProxyHttpRequestResponse` (or the Logger equivalent) and has `.annotations()`, `.mimeType()`, `.finalResponse()` etc. that don't exist on the scan-check version. The reference files document the precise type for each context.

---

## 5. Burp Globals — execution gates and configurable variables

Every Bambda **must** use the **[Burp Globals](https://github.com/ryarmst/Burp-Globals)** extension for:

1. **Execution gate** — a boolean global that turns the entire script on/off without removing it from Burp.
2. **Configurable variables** — any value the user might want to change (thresholds, target paths, header names, regex patterns, etc.) should be a global rather than a hard-coded Java constant.

Variables are set in the Burp Globals tab and read in Bambda code with:

```java
System.getProperty("bg.<variable-name>")   // always returns String or null
```

### 5.1 Declaring globals in the YAML header

All Burp Globals used by a Bambda are declared in a `burpglobal:` block in the `.bambda` file header — **not** as Java comments inside `source:`. This keeps the manifest separate from the code and makes it trivially inspectable without parsing Java.

Each entry is one line: the variable name (without the `bg.` prefix), its default value, and a `#` comment with a one-phrase description and type hint:

```yaml
burpglobal:
  bambda-injection: false           # master on/off; set true to enable (bool)
  bambda-injection-max-probes: 5    # cap on probes per insertion point (int)
```

Rules:
- List the gate global **first**.
- The value shown is the default baked into the Java code (or `false`/`""` for required fields the user must set).
- Keep comments to one phrase — the Java code is the authoritative spec for behaviour.

Inside `source:`, the gate check and `System.getProperty()` calls are still required — they are functional code. Only the **documentation** comment block moves to the YAML header.

**Important: most Bambda types have no logging interface.** Only `CUSTOM_ACTION` supports `logging()`. For scan checks, filters, columns, and M&R rules, the gate check silently returns — there is no logging call to add.

```java
// Scan check gate (no logging available — just return):
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-injection"))) {
    return AuditResult.auditResult();   // swap for false / "" / return; — match function return type
}
final int MAX_PROBES = Integer.parseInt(
    java.util.Objects.requireNonNullElse(System.getProperty("bg.bambda-injection-max-probes"), "5")
);

// CUSTOM_ACTION gate (logging IS available):
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-action"))) {
    logging().logToOutput("[MyAction] disabled — set bg.bambda-action=true to enable");
    return;
}
```

### 5.2 Execution gate — choosing the right category global

Use the closest category. If none fits, add a new one to `templates/globals.csv` and document it in `README.md`.

| Global | Default | Used for |
|--------|---------|----------|
| `bambda-injection` | `false` | Active per-insertion-point injection checks (SQLi, SSTI, XSS, command injection) |
| `bambda-fuzzing` | `false` | Active per-insertion-point fuzzing |
| `bambda-pathdisco` | `false` |  Active per-host path guessing |
| `bambda-oob` | `false` | Active OOB/blind checks via Burp Collaborator or custom listener |
| `bambda-active` | `false` | Active per-request checks (CORS, method probing, header injection) |
| `bambda-recon` | `false` | Active per-host recon probes (well-known paths, exposed metadata) |
| `bambda-passive` | `false` | Passive checks (missing headers, info disclosure, JWT detection) |

### 5.3 No-op return values by function type

| Function type | Gate return when disabled |
|---|---|
| Any `SCAN_CHECK_*` | `return AuditResult.auditResult();` |
| `VIEW_FILTER` | `return false;` |
| `CUSTOM_COLUMN` | `return "";` |
| `CUSTOM_ACTION` | `return;` |
| `MATCH_AND_REPLACE_REQUEST` | `return requestResponse.request();` |
| `MATCH_AND_REPLACE_RESPONSE` | `return requestResponse.response();` |

### 5.4 globals.csv

`templates/globals.csv` is the canonical list of all gate and configurable globals for the set of Bambdas in this folder. Format: `name,value,regex` — no header row. The user imports it via **Burp Globals → Options → Import variables**.

When writing a new Bambda, add any new globals it introduces to this file. The `burpglobal:` YAML header in the `.bambda` file is the human-readable manifest; `globals.csv` is the machine-importable counterpart.

---

## 6. Workflow

When the user asks for a Bambda:

1. **Identify the function type** using §1. If scan check, use the elicitation pattern in §1's "Disambiguating scan checks". If any axis is unclear, ask the user in one consolidated question — not three rounds.
2. **Load the relevant reference file:**
   - Scan checks → read `references/scan_checks.md`
   - Filters/columns/actions/M&R → read `references/filters_columns_actions_mr.md`
   - Always-useful API surface → `references/montoya_api_cheatsheet.md` (consult as needed)
   - Collaborator → `references/collaborator.md`
3. **Pick a template** from `templates/` that matches the function type. Adapt it. Don't write from scratch.
4. **Wire up Burp Globals** (see §5):
   - Choose the appropriate gate global from the category table in §5.2.
   - Add a `burpglobal:` block to the YAML header listing the gate global first, then any optional globals with their defaults and a `#` description.
   - Move any user-tunable constants (thresholds, paths, header names, etc.) to globals read via `System.getProperty("bg....")` rather than hard-coded Java `final` values.
   - In `source:`, keep the gate check and `System.getProperty()` calls — but no documentation comment block. The gate check must log when it fires.
   - Add any new globals to `globals.csv`.
5. **Generate a fresh UUID** if producing a full `.bambda` file (`java.util.UUID.randomUUID()` or just any random UUIDv4 string).
6. **Output** either the bare code body or the full `.bambda` file based on user preference. Default to a full `.bambda` file if the user said "write me a Bambda" without further qualification — they almost always want something importable.
7. **Self-check before delivering:**
   - Does the `.bambda` file have a `burpglobal:` header block listing the gate global first, then any optional globals?
   - Does the gate check in `source:` return the correct no-op value for this function type (see §5.3)? (Only `CUSTOM_ACTION` may include a `logging()` call in the gate — all other types have no logging interface.)
   - Does the script use `logging` or `api().logging()` outside a `CUSTOM_ACTION`? If yes, remove it — Bambdas have no logging interface except in Repeater custom actions.
   - Are configurable values read from globals rather than hard-coded?
   - Does the script return the right type for its function?
   - Does it guard `hasResponse()` where needed?
   - Are HTML inserts encoded?
   - For per-insertion-point: does it use `insertionPoint.buildHttpRequestWithPayload`?
   - For Collaborator: does it have a bounded poll loop?
   - For active checks: are loops bounded and payload counts reasonable?
   - Are there any `import` statements? (If yes, delete them.)
   - Is there a `class` wrapper? (If yes, unwrap it.)

---

## 7. Persistence across runs

Bambdas have **no native persistence**. Every invocation gets a fresh script-level scope.

**Simple key-value across runs:** Use Burp Globals (§5). Globals survive for the lifetime of the Burp process. An auto-update regex on a global can extract and store a value from a response automatically (e.g., capture a CSRF token, a session ID, or a bearer token). This covers most "remember this across requests" needs.

**Cross-invocation analysis state** (e.g., dedupe findings across hosts in the same scan, accumulate a corpus, compare against a baseline collected earlier): use the **`burp-bambda-persistence`** skill. It documents three strategies (best first):

1. **BurpDB extension** (preferred when available) — opens via `DriverManager.getConnection(System.getProperty("burp.db.url"))`. No driver JAR needed. Pre-provisioned tables: `kv`, `findings`, `logs`. Use `logs` for troubleshooting (`created_at = strftime('%s','now')`, `reporter` = Bambda name, `details` = short message).
2. **Java `Preferences` API** — built-in, no setup, fine for small key-value (< ~1MB).
3. **JDBC to a self-managed DB** — Postgres/SQLite/etc., for anything large, structured, or shared with external tools. Requires adding the driver JAR to Burp's classpath.

Mention this option to the user proactively if their request implies durable state beyond what Burp Globals provides.

---

## 8. Reference files in this skill

- `README.md` — quick-start guide for the generated Bambda folder, including Burp Globals setup.
- `references/scan_checks.md` — full reference for all 6 scan-check categories. Object scope, return types, full skeletons, worked examples for each combination of axis.
- `references/filters_columns_actions_mr.md` — view filters, custom columns, custom actions, match-and-replace.
- `references/montoya_api_cheatsheet.md` — the actually-working API surface, drawn from real Burp samples. Use this to look up method names instead of guessing.
- `references/collaborator.md` — Collaborator client patterns: payload generation, the poll loop pattern, mapping interactions back to the request that caused them.
- `templates/` — drop-in skeletons named after the `function:` constant they target. All share a `globals.csv` file listing every gate and configurable global.
