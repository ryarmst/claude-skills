---
name: burp-repeater-actions
description: Author Burp Suite Repeater custom actions (CUSTOM_ACTION Bambdas). Use when the user wants to write, modify, debug, or review a script that runs as a button in Burp Repeater — including request signing, race-condition probes, batch sends, response decoding, token extraction, CSRF manipulation, automated retries, shell invocation, and AI-assisted analysis. Triggers on phrases like "Repeater action", "custom action", "Repeater button", "CUSTOM_ACTION", or any request for a script that runs manually inside Repeater against the current request/response pair.
---

# Burp Repeater Custom Actions

A Repeater custom action is a **`CUSTOM_ACTION` Bambda** — a Java code body that Burp executes when the user clicks a button in the Repeater (or Intruder) **Custom actions** side panel. It has side effects only (`void` return type) and operates on the currently loaded request/response pair.

Read this whole file. Then load `references/api.md`. Then write code.

---

## 1. What custom actions can do

- Retry requests with mutations (race conditions, status-code changes, header injection)
- Sign or transform the current request before sending (HMAC, OAuth, digest headers)
- Extract tokens/values from the response and apply them to the request (CSRF, session tokens)
- Send the request to Repeater / Organizer for further investigation
- Batch-send variants in parallel and compare responses
- Invoke a local shell command and inject the output into the request
- Log extracted data to the Custom actions output panel
- Use LLM analysis via `ai()` for payload generation or response analysis

Custom actions are **not** the right tool for vulnerability scanning — use a `SCAN_CHECK_*` Bambda for that.

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

- `location` is `REPEATER` for Repeater actions or `INTRUDER` for Intruder actions.
- The `burpglobal:` block follows the standard Bambdas framework (see §5).
- The gate check is **optional** for custom actions (they are manually triggered) but should still be included for consistency — it allows disabling without deleting the script.

---

## 3. Objects in scope

All `burp.api.montoya.*` types are auto-imported. Use them by simple name.

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | The current request/response in the active Repeater tab. |
| `httpEditor` | editor handle | Repeater HTTP editor. Use `.requestPane()` and `.responsePane()` to mutate in place. |
| `wsEditor` | WebSocket editor handle | Available in WebSocket Repeater tabs instead of `httpEditor`. |
| `api()` | `MontoyaApi` | Full Montoya API root. Use for HTTP sending, routing, utilities. |
| `utilities()` | `Utilities` | Helper functions (encoding, crypto, JSON, shell). Same as `api().utilities()`. |
| `logging()` | `Logging` | **Available in CUSTOM_ACTION only.** Outputs to the Custom actions side panel. |
| `selection` | `RequestResponseSelection` | Represents text the user has selected in the request or response pane. |
| `ai()` | `Ai` | LLM integration for analysis and payload generation. |

**Logging is available here.** Unlike other Bambda types (scan checks, filters, columns, M&R), custom actions have a full `logging()` interface. Use it freely.

---

## 4. Key APIs

### Sending HTTP requests

```java
// Send a single request, preserving HTTP version.
var version = requestResponse.request().httpVersion().equals("HTTP/2")
    ? HttpMode.HTTP_2 : HttpMode.HTTP_1;
var rr = api().http().sendRequest(requestResponse.request(), version);

// Send multiple requests in parallel.
var results = api().http().sendRequests(java.util.List.of(req1, req2, req3));
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

### Logging

```java
logging().logToOutput("status: " + status);
logging().logToOutput("token: " + token);
logging().logToError("unexpected response: " + body, null);
```

Output appears in the **Output** tab of the Custom actions side panel in Repeater.

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

// Get byte offsets of the selection.
int start = selection.responseSelection().offsets().startIndexInclusive();
int end   = selection.responseSelection().offsets().endIndexExclusive();
```

### Shell execution

```java
// Safe form — pass command and args separately (no injection risk).
var result = utilities().shellUtils().execute("jq", ".token", "-r");
logging().logToOutput("jq output: " + result.output());

// With options (timeout, env vars, stderr handling).
var opts = executeOptions()
    .withTimeout(java.time.Duration.ofSeconds(10))
    .withEnvironmentVariable("TARGET", "example.com");
var result = utilities().shellUtils().execute(opts, "nmap", "-p443", "example.com");

// UNSAFE — never use with user-controlled input.
utilities().shellUtils().dangerouslyExecute("echo hello world");
```

### Utilities

```java
// These reach the same object:
api().utilities().base64Utils().encode(ByteArray.byteArray(data))
utilities().base64Utils().decode(str)

utilities().htmlUtils().encode(str)
utilities().urlUtils().encode(str)
utilities().cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
utilities().jsonUtils().readString(jsonBody, "data.token")
utilities().randomUtils().randomString(16)
```

---

## 5. Burp Globals integration

Custom actions use the same **[Burp Globals](https://github.com/ryarmst/Burp-Globals)** framework as other Bambdas. Use `bambda-action` as the gate global.

```java
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-action"))) {
    logging().logToOutput("[MyAction] disabled — set bg.bambda-action=true to enable");
    return;
}
```

Note: Unlike scan checks, the gate log call IS appropriate here because custom actions have a logging interface.

Move any user-tunable constants to globals:

```java
final int MAX_ATTEMPTS = Integer.parseInt(
    java.util.Objects.requireNonNullElse(System.getProperty("bg.bambda-action-max-attempts"), "20")
);
```

Declare all globals in the YAML header:

```yaml
burpglobal:
  bambda-action: false                    # master on/off; set true to enable (bool)
  bambda-action-max-attempts: 20          # retry cap (int)
```

---

## 6. Common patterns

### Pattern 1 — Retry until status changes (race condition probe)

```java
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

### Pattern 2 — Extract CSRF token from response and patch request

```java
var body = requestResponse.response().bodyToString();
var m = java.util.regex.Pattern.compile("csrf[_-]?token[\"']?\\s*[=:]\\s*[\"']([^\"'\\s]+)")
    .matcher(body);
if (!m.find()) {
    logging().logToOutput("no CSRF token found");
    return;
}
var token = m.group(1);
logging().logToOutput("CSRF token: " + token);
httpEditor.requestPane().replace("FUZZ_CSRF", token);
```

### Pattern 3 — Parallel batch send and log results

```java
var base = requestResponse.request();
var variants = java.util.List.of(
    base.withAddedHeader("X-Forwarded-For", "127.0.0.1"),
    base.withAddedHeader("X-Forwarded-For", "::1"),
    base.withRemovedHeader("Cookie")
);
var results = api().http().sendRequests(variants);
for (int i = 0; i < results.size(); i++) {
    var rr = results.get(i);
    var status = rr.hasResponse() ? String.valueOf(rr.response().statusCode()) : "no response";
    logging().logToOutput("variant " + i + " -> " + status);
    api().organizer().sendToOrganizer(rr);
}
```

### Pattern 4 — HMAC request signing

```java
var body = requestResponse.request().bodyToString();
var key  = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.bambda-action-hmac-key"), "changeme"
);
var mac  = javax.crypto.Mac.getInstance("HmacSHA256");
mac.init(new javax.crypto.spec.SecretKeySpec(key.getBytes(), "HmacSHA256"));
var sig  = HexFormat.of().formatHex(mac.doFinal(body.getBytes()));
var signed = requestResponse.request().withHeader("X-Signature", sig);
httpEditor.requestPane().set(signed.toByteArray());
logging().logToOutput("signed: " + sig);
```

---

## 7. Gotchas

1. **`requestResponse.response()` may be null** if the request hasn't been sent yet. Guard with `requestResponse.hasResponse()` or a null check before accessing response fields.

2. **`httpEditor` vs `wsEditor`**: `httpEditor` is in scope for HTTP Repeater tabs; `wsEditor` is available for WebSocket tabs. For actions that target both, check the type or maintain separate `.bambda` files.

3. **No `insertionPoint` or `http` bare field.** Those are scan-check-only. Use `api().http().sendRequest(...)` for HTTP in custom actions.

4. **No `utilities` bare field.** In custom actions, utilities is a method: `utilities()`. Unlike filters/columns/M&R where it's a bare field.

5. **Shell execution**: always prefer `execute("cmd", "arg1", "arg2")` over `dangerouslyExecute("cmd arg1 arg2")`. Never pass user-controlled input to `dangerouslyExecute` — it does full shell expansion.

6. **Performance**: Repeater actions are manually triggered, so performance is less critical than scan checks. But parallel sends via `sendRequests()` are still preferred over sequential loops when order doesn't matter.

7. **`javax.crypto.*`** is available for HMAC/signing. It is part of the JDK and does not need importing as a JAR.

---

## 8. Workflow

1. **Clarify the use case**: what should the action do when the user clicks the button? Does it send new requests? Modify the editor? Log output? Route to another tool?
2. **Load `references/api.md`** for the full API surface.
3. **Pick a template** from `templates/` or Pattern in §6 that matches the use case.
4. **Wire up Burp Globals** (§5) — gate global first, then optional variables.
5. **Generate a fresh UUID** for the `.bambda` file.
6. **Self-check before delivering:**
   - Does the gate use `bambda-action` and log on disable? (`logging()` IS available here.)
   - Are configurable values globals, not hard-coded?
   - Is there a null guard on `requestResponse.response()`?
   - Does it use `api().http().sendRequest(...)` (not bare `http`)?
   - Does it use `utilities()` with parens (not bare `utilities`)?
   - No `import` statements, no `class` wrapper.
   - Does the `.bambda` YAML have `function: CUSTOM_ACTION` and a valid `location`?
