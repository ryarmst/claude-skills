---
name: burp-repeater-actions
description: Author Burp Suite Repeater custom actions (CUSTOM_ACTION Bambdas). Use when the user wants to write, modify, debug, or review a script that runs as a button in Burp Repeater's Custom actions side panel — including request signing, race-condition probes, batch sends, response decoding, token extraction, CSRF manipulation, automated retries, shell invocation, and AI-assisted analysis. Triggers on phrases like "Repeater action", "custom action", "Repeater button", "CUSTOM_ACTION", or any request for a script that runs manually inside Repeater against the current request/response pair.
---

# Burp Repeater Custom Actions

A Repeater custom action is a **`CUSTOM_ACTION` Bambda** — a Java code body that Burp executes when the user clicks a button in the Repeater **Custom actions** side panel. It has side effects only (`void` return type) and operates on the currently loaded request/response pair.

Read this whole file. Then load `references/api.md`. Then write code.

---

## 1. What custom actions can do

- Retry requests with mutations (race conditions, status-code changes, header injection)
- Sign or transform the current request before sending (HMAC, OAuth, digest headers)
- Extract tokens/values from the response and apply them to the request (CSRF, session tokens)
- Send the request to Repeater / Organizer for further investigation
- Batch-send variants in parallel and compare responses (single-packet attack for HTTP/2, last-byte sync for HTTP/1)
- Invoke a local shell command and use the output to modify the request
- Log extracted data to the Custom actions output panel
- Fetch external data via outbound HTTP requests
- Raise scanner audit issues (see PortSwigger's official `CookiePrefixBypass.bambda`)
- Use LLM analysis via `ai()` for payload generation or response analysis

Custom actions run only in Burp Repeater. They're not the primary mechanism for continuous vulnerability scanning — a `SCAN_CHECK_*` Bambda is — but they can call `api().siteMap().add(...)` to raise findings when appropriate.

---

## 2. The .bambda file format

```yaml
id: <UUIDv4>
name: <Human readable name>
function: CUSTOM_ACTION
location: REPEATER
burpglobal:
  bambda-action: false              # master on/off; set true to enable (bool)
  <optional-variable>: <default>   # brief purpose (type)
source: |
  /**
   * <One-line purpose>
   * @author <name or handle>
   **/

  <java code body>
```

- `location` is always `REPEATER` for custom actions. The Custom actions feature is Repeater-only — there is no Intruder custom-action location.
- The `id` must be a unique UUIDv4. Burp uses this to recognize the same Bambda across re-imports so it can update rather than duplicate.
- `name`, `function`, and `location` are the official metadata fields Burp parses; PortSwigger's contributing guide lists these as the required header fields.
- The `burpglobal:` block is **not** parsed by Burp itself. It's a convention used by the Burp Globals framework (see §5) and by tooling that processes `.bambda` files. Burp ignores unknown YAML keys, so including it is safe.
- Indentation in the YAML is four spaces (per PortSwigger's contributing guidelines).

### Comment header

The JavaDoc-style comment at the top of `source:` is required by the official Bambda Checker for contributions to the PortSwigger repo. It must contain a short description and an `@author` tag. Keep this convention for your own bambdas too.

---

## 3. Objects in scope

All `burp.api.montoya.*` types are auto-imported. Use them by simple name. The Custom actions writing guide names seven objects exposed to the script:

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | The current request/response in the active Repeater tab. |
| `selection` | `RequestResponseSelection` | Text the user has selected in the request or response pane. |
| `httpEditor` | `HttpEditor` | Active HTTP editor. Use `.requestPane()` and `.responsePane()` to mutate in place. |
| `api()` | `MontoyaApi` | Full Montoya API root. |
| `utilities()` | `Utilities` | Helper functions (encoding, crypto, JSON, shell). Same as `api().utilities()`. |
| `logging()` | `Logging` | Outputs to the Custom actions Output panel. |
| `ai()` | `Ai` | LLM integration for analysis and payload generation. |

### Field vs method form

`api`, `utilities`, `logging`, and `ai` are each available **both** as a bare field and as a parenthesised accessor. `logging.logToOutput("x")` and `logging().logToOutput("x")` are equivalent.

The PortSwigger worked example (the tutorial walkthrough) uses the bare-field form. The official sample bambdas in the `PortSwigger/bambdas` repo (`RetryUntilSuccess`, `Screenshot`, `CookiePrefixBypass`, `InlineStyleAttributeStealer`) and PortSwigger's marketing blog examples consistently use the **method form**. This skill uses the method form throughout to match what you'll see in the official samples repo, but the bare-field form is equally valid if you prefer it.

### Logging is available here

Unlike scan checks, filters, custom columns, or match-and-replace bambdas, `CUSTOM_ACTION` has full access to `logging()`. Use it freely — output appears in the **Output** tab of the Custom actions side panel.

---

## 4. Key APIs

### Sending HTTP requests

```java
// Send a single request, preserving HTTP version.
var version = requestResponse.request().httpVersion().equals("HTTP/2")
    ? HttpMode.HTTP_2 : HttpMode.HTTP_1;
var rr = api().http().sendRequest(requestResponse.request(), version);

// Send multiple requests in parallel.
// IMPORTANT: sendRequests uses the single-packet attack on HTTP/2 and
// last-byte synchronization on HTTP/1, which is exactly what you want
// for race-condition probing.
var results = api().http().sendRequests(java.util.List.of(req1, req2, req3));

// Fetch external data.
var ext = api().http().sendRequest(HttpRequest.httpRequestFromUrl("https://example.com/feed.rss"));
```

### Editor manipulation

```java
// Replace the request in the editor.
httpEditor.requestPane().set(newRequest.toByteArray());

// Replace the response in the editor.
httpEditor.responsePane().set(rr.response().toByteArray());

// Replace a substring in the request pane.
httpEditor.requestPane().replace("old-value", "new-value");
```

Note: `EditorPane.set()` only updates what's displayed in the editor. It does NOT mutate `requestResponse.request()` in-place. If you need to use the new value later in the same script, capture it in a local variable.

### Logging

```java
logging().logToOutput("status: " + status);
logging().logToOutput("token: " + token);
logging().logToError("unexpected response: " + body, null);
```

Output appears in the **Output** tab of the Custom actions side panel.

### Routing to other tools

```java
api().repeater().sendToRepeater(req);
api().organizer().sendToOrganizer(rr);
```

### Selection (user-highlighted text)

```java
if (selection.hasResponseSelection()) {
    var selected = selection.responseSelection().contents().toString();
    logging().logToOutput("selected: " + selected);
}

// Get byte offsets, useful for splicing into the request as a string.
int start = selection.responseSelection().offsets().startIndexInclusive();
int end   = selection.responseSelection().offsets().endIndexExclusive();
```

### Shell execution

```java
// Safe form — pass command and args separately (no injection risk).
var result = utilities().shellUtils().execute("jq", ".token", "-r");
logging().logToOutput("jq output: " + result.output());

// With options (timeout, env vars, stderr handling, exit-code behavior).
var opts = executeOptions()
    .withTimeout(java.time.Duration.ofSeconds(10))
    .withTimeoutBehavior(TimeoutBehavior.ALLOW_TIMEOUT)
    .withStderrBehavior(StderrBehavior.MERGE)
    .withExitCodeBehavior(ExitCodeBehavior.ALLOW_NON_ZERO)
    .withEnvironmentVariable("TARGET", "example.com");
var result = utilities().shellUtils().execute(opts, "nmap", "-p443", "example.com");

// UNSAFE — never use with user-controlled input. Passes a single string
// to the shell with full expansion, so any data containing shell
// metacharacters becomes a command-injection vector.
utilities().shellUtils().dangerouslyExecute("echo hello world");
```

### Utilities

```java
utilities().base64Utils().encode(ByteArray.byteArray(data))
utilities().base64Utils().decode(str)
utilities().htmlUtils().encode(str)
utilities().urlUtils().encode(str)
utilities().cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
utilities().cryptoUtils().computeHmac(keyBytes, dataBytes, HmacAlgorithm.HMAC_SHA256)
utilities().jsonUtils().readString(jsonBody, "data.token")
utilities().randomUtils().randomString(16)
```

Prefer `utilities().cryptoUtils().computeHmac(...)` over hand-rolled `javax.crypto.Mac` for HMAC signing — it's the documented Montoya API path.

---

## 5. Burp Globals integration

Custom actions integrate with the **[Burp Globals](https://github.com/ryarmst/Burp-Globals)** extension, which provides a centralized place to define variables (tokens, target hosts, tunable knobs) that can be referenced from both raw HTTP messages and Bambda code.

### How Burp Globals works

Once the extension is installed, in Burp:

1. Open the **Burp Globals** tab and add variables.
2. Use `${bg:variable_name}` anywhere in a request to reference a variable. Burp expands the placeholder at send time.
3. Access variables from Java code (Bambdas, custom scan checks) with:
   ```java
   String token = System.getProperty("bg.auth_token");
   ```
4. Right-click in a message editor → **Burp Globals** to insert placeholders or code references.

The extension publishes every global as a JVM system property prefixed with `bg.`, so any Bambda that needs configuration can read it without hard-coding.

### Conventions used by this skill

- The gate global for custom actions is **`bambda-action`**. The script returns early unless `bg.bambda-action` is `true`. This lets you keep an action loaded but disabled, which is useful when the action has side effects (sends requests, runs shell commands) and you want a single switch to arm/disarm it.
- Tunable values (retry caps, regex patterns, header names) become globals named `bambda-action-<purpose>`.
- All globals the script uses are declared in the `burpglobal:` YAML block at the top of the `.bambda` file. Burp itself ignores this block — it's metadata for the Burp Globals tooling and for anyone reading the file to know which `bg.*` variables the script consults.

### Gate pattern

```java
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-action"))) {
    logging().logToOutput("[MyAction] disabled — set bg.bambda-action=true to enable");
    return;
}
```

The disable log line is appropriate here because custom actions have a full `logging()` interface (scan checks don't, which is why their gates are silent).

### Reading typed globals with defaults

```java
// Integer with default.
final int MAX_ATTEMPTS = Integer.parseInt(
    java.util.Objects.requireNonNullElse(System.getProperty("bg.bambda-action-max-attempts"), "20")
);

// String with default.
final String PLACEHOLDER = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.bambda-action-placeholder"), "FUZZ_TOKEN"
);

// Boolean.
final boolean VERBOSE =
    "true".equalsIgnoreCase(System.getProperty("bg.bambda-action-verbose"));
```

### Declaring globals in the YAML header

```yaml
burpglobal:
  bambda-action: false                    # master on/off; set true to enable (bool)
  bambda-action-max-attempts: 20          # retry cap (int)
  bambda-action-placeholder: FUZZ_TOKEN   # placeholder in request to replace (string)
```

---

## 6. Common patterns

### Pattern 1 — Retry until status changes (race condition probe)

```java
if (!requestResponse.hasResponse()) {
    logging().logToOutput("no base response — send the request first");
    return;
}

var version = requestResponse.request().httpVersion().equals("HTTP/2")
    ? HttpMode.HTTP_2 : HttpMode.HTTP_1;
var boring  = requestResponse.response().statusCode();

for (int i = 0; i < MAX_ATTEMPTS; i++) {
    var attack = api().http().sendRequest(requestResponse.request(), version);
    if (!attack.hasResponse()) {
        logging().logToOutput("attempt " + i + ": no response");
        continue;
    }
    var status = attack.response().statusCode();
    logging().logToOutput("attempt " + i + " -> " + status);
    if (status != boring) {
        httpEditor.responsePane().set(attack.response().toByteArray());
        return;
    }
}
logging().logToOutput("no status change after " + MAX_ATTEMPTS + " attempts");
```

For a true single-packet race, use `sendRequests(List.of(req, req, req, ...))` instead — that path applies HTTP/2 single-packet attack semantics or HTTP/1 last-byte synchronization automatically. See Pattern 3.

### Pattern 2 — Extract token from response and patch request

```java
if (!requestResponse.hasResponse()) {
    logging().logToOutput("no response — send the request first");
    return;
}

var body = requestResponse.response().bodyToString();
// Permissive pattern: allows quoted or unquoted values, =, :, or > as separator.
var m = java.util.regex.Pattern.compile(
    "csrf[_-]?token[\"']?\\s*[=:>]\\s*[\"']?([^\"'\\s<>&]+)",
    java.util.regex.Pattern.CASE_INSENSITIVE
).matcher(body);
if (!m.find()) {
    logging().logToOutput("no CSRF token found");
    return;
}
var token = m.group(1);
logging().logToOutput("CSRF token: " + token);
httpEditor.requestPane().replace("FUZZ_CSRF", token);
```

Alternative: if the response is JSON, prefer `utilities().jsonUtils().readString(body, "data.csrf_token")` over regex.

### Pattern 3 — Parallel batch send (header injection sweep)

```java
var base = requestResponse.request();
var variants = java.util.List.of(
    base.withAddedHeader("X-Forwarded-For", "127.0.0.1"),
    base.withAddedHeader("X-Forwarded-For", "::1"),
    base.withAddedHeader("X-Original-URL", "/admin"),
    base.withRemovedHeader("Cookie")
);
var results = api().http().sendRequests(variants);
for (int i = 0; i < results.size(); i++) {
    var rr = results.get(i);
    if (!rr.hasResponse()) {
        logging().logToOutput("variant " + i + ": no response");
        continue;
    }
    var status = rr.response().statusCode();
    var length = rr.response().body().length();
    logging().logToOutput("variant " + i + " -> " + status + " (" + length + " bytes)");
    api().organizer().sendToOrganizer(rr);
}
```

### Pattern 4 — HMAC request signing

```java
var body = requestResponse.request().body();   // ByteArray
var key  = ByteArray.byteArray(java.util.Objects.requireNonNullElse(
    System.getProperty("bg.bambda-action-hmac-key"), "changeme"
));
var sigBytes = utilities().cryptoUtils()
    .computeHmac(key, body, HmacAlgorithm.HMAC_SHA256);
var sig = java.util.HexFormat.of().formatHex(sigBytes.getBytes());

var signed = requestResponse.request().withHeader("X-Signature", sig);
httpEditor.requestPane().set(signed.toByteArray());
logging().logToOutput("signed: " + sig);
```

### Pattern 5 — Replace selected text with an encoded form

```java
if (!selection.hasRequestSelection()) {
    logging().logToOutput("select text in the request first");
    return;
}
var input = selection.requestSelection().contents().toString();
var encoded = utilities().base64Utils().encode(ByteArray.byteArray(input)).toString();

var reqStr = requestResponse.request().toString();
int start  = selection.requestSelection().offsets().startIndexInclusive();
int end    = selection.requestSelection().offsets().endIndexExclusive();

httpEditor.requestPane().set(reqStr.substring(0, start) + encoded + reqStr.substring(end));
logging().logToOutput("replaced selection with base64: " + encoded);
```

---

## 7. Gotchas

1. **`requestResponse.response()` may be null** if the user hasn't sent the request yet. Guard with `requestResponse.hasResponse()` before accessing response fields. This is the single most common runtime failure.

2. **`location: REPEATER` only.** Custom actions are a Repeater-only feature. There is no `INTRUDER` custom-action location, despite the side panel also being accessible from Intruder views. Match-and-replace, scan checks, and table customizations have their own Bambda function types.

3. **No `wsEditor`.** The custom actions API documents one editor: `httpEditor`. WebSocket Repeater traffic isn't addressed by the CUSTOM_ACTION mechanism.

4. **`EditorPane.set()` doesn't update `requestResponse`.** It updates the editor display only. If subsequent logic in the same script needs the new value, store it in a variable before the `set()` call.

5. **`statusCode()` returns `short`**, not `int`. Comparisons with `int` literals work via promotion, but be aware if you store it.

6. **No `import` statements, no `class` wrapper.** The script body is a code fragment, not a compilation unit. For types outside the auto-imported `burp.api.montoya.*` packages, use fully qualified names (e.g. `java.util.regex.Pattern`, `javax.crypto.Mac`).

7. **Shell execution**: always prefer `execute("cmd", "arg1", "arg2")` over `dangerouslyExecute("cmd arg1 arg2")`. Never pass user-controlled input to `dangerouslyExecute` — it does full shell expansion. Never use a user-controlled value as the first argument of `execute()` either; that controls which binary is run.

8. **`sendRequests()` is the right tool for race conditions.** It applies the HTTP/2 single-packet attack or HTTP/1 last-byte synchronization automatically. A sequential `for` loop calling `sendRequest()` does neither and will not race effectively.

9. **`javax.crypto.*` is available** for cases the Montoya `cryptoUtils` API doesn't cover (custom modes, asymmetric, etc.). Part of the JDK; no JAR import needed. For HMAC specifically, prefer the Montoya path.

10. **Test in the editor before saving.** The Custom actions editor has a built-in **Test** function that runs the script against a sample message and shows compilation errors in a panel. Use it — it's faster than the load-fail-edit-reload cycle.

11. **Re-importing a Bambda with the same `id`** updates the existing entry in the library; a different `id` creates a duplicate. Preserve the UUID across edits.

---

## 8. Workflow

1. **Clarify the use case**: what should the action do when the user clicks the button? Does it send new requests? Modify the editor? Log output? Route to another tool? Raise a finding?
2. **Load `references/api.md`** for the full API surface.
3. **Pick a template** from `templates/` or a Pattern in §6 that matches the use case.
4. **Wire up Burp Globals** (§5): gate global first, then any tunables.
5. **Generate a fresh UUIDv4** for the `id` field.
6. **Test in the editor** with the built-in Test function before saving to the library.
7. **Self-check before delivering:**
   - Does the gate use `bambda-action` and log on disable?
   - Are configurable values globals, not hard-coded?
   - Is there a null guard on `requestResponse.response()` if the script reads it?
   - Are HTTP calls via `api().http().sendRequest(...)` or `sendRequests(...)`?
   - No `import` statements, no `class` wrapper.
   - `.bambda` YAML has `function: CUSTOM_ACTION` and `location: REPEATER`?
   - JavaDoc header with description and `@author` tag?
   - Fresh, unique UUID in `id`?
