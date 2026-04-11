# Scan Checks — Full Reference

Six categories. They are NOT interchangeable.

```
            │ Per host                            │ Per request                         │ Per insertion point
────────────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────────
 Active     │ SCAN_CHECK_ACTIVE_PER_HOST          │ SCAN_CHECK_ACTIVE_PER_REQUEST       │ SCAN_CHECK_ACTIVE_PER_INSERTION_POINT
 Passive    │ SCAN_CHECK_PASSIVE_PER_HOST         │ SCAN_CHECK_PASSIVE_PER_REQUEST      │ SCAN_CHECK_PASSIVE_PER_INSERTION_POINT
```

## Objects in scope (all scan checks)

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | Always present. For per-host checks it's a representative request for the host; for per-request it's the audited base request; for per-insertion-point it's the base request the insertion point was derived from. |
| `http` | `Http` | The HTTP service. Use `http.sendRequest(request)` for active checks. |
| `api()` | `MontoyaApi` | Full API root. Use `api().utilities()`, `api().collaborator()`, `api().logging()`, `api().http()`, etc. |
| `insertionPoint` | `AuditInsertionPoint` | **Only in `*_PER_INSERTION_POINT` checks.** Build mutated requests with `insertionPoint.buildHttpRequestWithPayload(...)`. |
| `collaboratorClient` | `CollaboratorClient` | **Only when "Use Collaborator" is enabled in the script settings.** Otherwise create one explicitly with `api().collaborator().createClient()`. |

## Return type

All scan checks return `AuditResult`. Construct it with:

```java
return AuditResult.auditResult();                                  // no issues
return AuditResult.auditResult(issue1, issue2);                    // varargs
return AuditResult.auditResult(listOfIssues);                      // List<AuditIssue>
return null;                                                       // also legal — Burp treats as no issues
```

## Building an AuditIssue

Use the static factory `AuditIssue.auditIssue(...)`. The full signature (the one used by every real PortSwigger sample):

```java
AuditIssue.auditIssue(
    String   name,                       // issue title
    String   detail,                     // HTML — encode untrusted text!
    String   remediation,                // HTML
    String   baseUrl,                    // typically requestResponse.request().url()
    AuditIssueSeverity   severity,       // INFORMATION, LOW, MEDIUM, HIGH
    AuditIssueConfidence confidence,     // CERTAIN, FIRM, TENTATIVE
    String   background,                 // HTML — may be ""
    String   remediationBackground,      // HTML — may be ""
    AuditIssueSeverity   typicalSeverity,
    HttpRequestResponse... requestResponses   // the evidence; pass the response that demonstrates the issue
)
```

`background` and `remediationBackground` may be `null` or `""`. The `requestResponses` varargs is the evidence shown in the Issue Activity panel — pass the response that *demonstrates* the issue, not the base request, when they differ.

## Universal skeleton

```java
// === CONFIG ===
final boolean DEBUG = false;
final int     MAX_PROBES = 10;

// === SANITY ===
if (!requestResponse.hasResponse()) {
    return AuditResult.auditResult();
}

// === LOGIC ===
var issues = new java.util.ArrayList<AuditIssue>();

// ... do work, append to issues ...

// === RETURN ===
return issues.isEmpty()
    ? AuditResult.auditResult()
    : AuditResult.auditResult(issues.toArray(new AuditIssue[0]));
```

---

## 1. SCAN_CHECK_PASSIVE_PER_REQUEST

The simplest case. Look at `requestResponse`, decide whether to report.

**When to use:** missing security headers, info disclosure in responses, insecure cookie attributes, error message leakage, technology fingerprinting, hardcoded secrets in JS bundles.

**Example: missing CSP header**

```java
if (!requestResponse.hasResponse()) {
    return AuditResult.auditResult();
}

if (requestResponse.response().hasHeader("Content-Security-Policy")) {
    return AuditResult.auditResult();
}

return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "Content Security Policy header missing",
        "The response does not include a Content-Security-Policy header. Without this header the browser cannot enforce a restrictive policy for scripts, styles, images and other resources, increasing exposure to XSS, click-jacking and content-injection attacks.",
        "Add a suitable Content-Security-Policy header, for example: <code>default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none';</code>",
        requestResponse.request().url(),
        AuditIssueSeverity.LOW,
        AuditIssueConfidence.FIRM,
        "Content Security Policy (CSP) is an HTTP response header that tells the browser which sources are permitted for each resource type.",
        "Create a baseline policy in report-only mode, review violation reports, then switch to enforcement.",
        AuditIssueSeverity.LOW,
        requestResponse
    )
);
```

---

## 2. SCAN_CHECK_PASSIVE_PER_HOST

Same as per-request, but Burp only invokes the script once per host instead of once per audited request. Use this when the finding is a property of the host (e.g., presence of a server banner, exposed `/robots.txt`, server software version) and reporting it per request would be noise.

The `requestResponse` is a representative request — typically the first or root request seen for that host. **Do not** assume it's any particular path.

**Example: server banner disclosure**

```java
if (!requestResponse.hasResponse()) return AuditResult.auditResult();

var server = requestResponse.response().headerValue("Server");
if (server == null || server.isBlank()) {
    return AuditResult.auditResult();
}

// Only flag if it includes a version number — bare "nginx" is uninteresting.
if (!server.matches(".*\\d+\\.\\d+.*")) {
    return AuditResult.auditResult();
}

return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "Server banner discloses version",
        "The host returns a <code>Server</code> header containing a version number: <code>"
            + api().utilities().htmlUtils().encode(server) + "</code>",
        "Strip or anonymize the <code>Server</code> header at the reverse proxy.",
        requestResponse.request().url(),
        AuditIssueSeverity.INFORMATION,
        AuditIssueConfidence.CERTAIN,
        "",
        "",
        AuditIssueSeverity.INFORMATION,
        requestResponse
    )
);
```

---

## 3. SCAN_CHECK_PASSIVE_PER_INSERTION_POINT

Rare. Used when the *passive* finding depends on a specific insertion point — for example, a parameter value that already looks like a JWT, or a parameter named `redirect`/`url`/`next` that should be flagged for manual review.

`insertionPoint` is in scope. You read its `name()` and `baseValue()` but you do **not** send any new requests (otherwise it would be active).

```java
if (insertionPoint == null) return AuditResult.auditResult();

var name  = insertionPoint.name();
var value = insertionPoint.baseValue();

if (value == null || value.isEmpty()) return AuditResult.auditResult();

// Looks like a JWT?
if (!value.matches("^eyJ[A-Za-z0-9_-]+\\.eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]*$")) {
    return AuditResult.auditResult();
}

return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "JWT in parameter: " + name,
        "Parameter <code>" + api().utilities().htmlUtils().encode(name) +
            "</code> contains a JSON Web Token. Verify signature validation, algorithm pinning, and expiration enforcement.",
        "Review JWT handling.",
        requestResponse.request().url(),
        AuditIssueSeverity.INFORMATION,
        AuditIssueConfidence.FIRM,
        "", "",
        AuditIssueSeverity.INFORMATION,
        requestResponse
    )
);
```

---

## 4. SCAN_CHECK_ACTIVE_PER_REQUEST

Sends crafted requests derived from the base request, but does **not** target a specific parameter. Good for whole-request mutations: changing the method, adding headers, replacing the body wholesale.

**Pattern: clone-mutate-send-compare**

```java
if (!requestResponse.hasResponse()) return null;

var baseReq = requestResponse.request();

// Generate a random origin to test reflection.
var evil = "https://" + api().utilities().randomUtils().randomString(8) + ".example.invalid";

var probe = http.sendRequest(baseReq.withAddedHeader("Origin", evil));
if (!probe.hasResponse()) return AuditResult.auditResult();

var aco = probe.response().headerValue("Access-Control-Allow-Origin");
if (aco == null || !aco.equalsIgnoreCase(evil)) {
    return AuditResult.auditResult();
}

var creds = "true".equalsIgnoreCase(probe.response().headerValue("Access-Control-Allow-Credentials"));
var sev   = creds ? AuditIssueSeverity.HIGH : AuditIssueSeverity.MEDIUM;

return AuditResult.auditResult(
    AuditIssue.auditIssue(
        "CORS: arbitrary origin reflection" + (creds ? " with credentials" : ""),
        "The server reflected an attacker-controlled <code>Origin</code> header in <code>Access-Control-Allow-Origin</code>"
            + (creds ? " and set <code>Access-Control-Allow-Credentials: true</code>." : "."),
        "Use a strict allowlist of permitted origins. Always include <code>Vary: Origin</code>.",
        baseReq.url(),
        sev,
        AuditIssueConfidence.FIRM,
        "", "",
        sev,
        probe
    )
);
```

**Common request mutations:**

```java
baseReq.withMethod("OPTIONS")
baseReq.withAddedHeader("X-Forwarded-For", "127.0.0.1")
baseReq.withHeader("Host", "evil.example")        // overwrites
baseReq.withRemovedHeader("Cookie")
baseReq.withBody("{\"a\":1}")
baseReq.withBody(ByteArray.byteArray(new byte[]{0x00, 0x01}))
baseReq.withPath("/admin")
baseReq.withQueryParameter(HttpParameter.urlParameter("debug","1"))
baseReq.withService(otherHttpService)
```

---

## 5. SCAN_CHECK_ACTIVE_PER_HOST

Runs **once per host** and sends crafted requests. Use for host-level probes that don't depend on any particular base request: existence of well-known paths (`/.git/HEAD`, `/.env`, `/server-status`), `OPTIONS *`, weird HTTP methods, TLS-level checks, host-header injection probes against the document root.

```java
var hostReq = HttpRequest.httpRequestFromUrl(
    requestResponse.request().httpService().secure() ? "https://" : "http://"
        + requestResponse.request().httpService().host()
        + ":" + requestResponse.request().httpService().port()
        + "/.git/HEAD"
);

var probe = http.sendRequest(hostReq);
if (!probe.hasResponse()) return AuditResult.auditResult();

if (probe.response().statusCode() == 200
    && probe.response().bodyToString().startsWith("ref: ")) {
    return AuditResult.auditResult(
        AuditIssue.auditIssue(
            "Exposed .git repository",
            "The host serves <code>/.git/HEAD</code> with a valid Git ref, indicating the source repository is publicly accessible.",
            "Block <code>/.git/</code> at the reverse proxy or remove the directory from the document root.",
            probe.request().url(),
            AuditIssueSeverity.HIGH,
            AuditIssueConfidence.CERTAIN,
            "", "",
            AuditIssueSeverity.HIGH,
            probe
        )
    );
}

return AuditResult.auditResult();
```

---

## 6. SCAN_CHECK_ACTIVE_PER_INSERTION_POINT

The most powerful and most common active check shape. `insertionPoint` is in scope; Burp has already identified a specific input location and you provide payloads.

**Always** use `insertionPoint.buildHttpRequestWithPayload(ByteArray.byteArray(payload))`. Burp handles the encoding (URL-encoding query params, JSON-escaping body params, header value placement, etc.). Do not manually splice payloads into a request string — you'll mis-encode and miss findings.

**Reading the base value:**

```java
var name = insertionPoint.name();
var base = insertionPoint.baseValue();
```

**Example: SSTI sampler (from official sample, lightly cleaned)**

```java
if (insertionPoint == null) return AuditResult.auditResult();

record Probe(String engine, String[] payloads, String expect) {}

var probes = java.util.List.of(
    new Probe("Jinja/Twig",                  new String[]{"{{7*7}}", "}} {{7*7}} {{", "#{7*7}#"}, "\\b49\\b"),
    new Probe("Velocity/Thymeleaf/Freemarker", new String[]{"${7*7}", "}}${7*7}{{"},               "\\b49\\b"),
    new Probe("Go template",                  new String[]{"{{print 7*7}}", "}} {{print 7*7}} {{"},"\\b49\\b")
);

for (var probe : probes) {
    for (var payload : probe.payloads()) {
        var rr = http.sendRequest(insertionPoint.buildHttpRequestWithPayload(ByteArray.byteArray(payload)));
        if (!rr.hasResponse()) continue;

        var body = rr.response().bodyToString();
        // Match the expected output AND ensure it isn't the literal payload reflected.
        if (body.matches("(?s).*" + probe.expect() + ".*") && !body.contains(payload)) {
            return AuditResult.auditResult(
                AuditIssue.auditIssue(
                    "Server-Side Template Injection (" + probe.engine() + ")",
                    "Evaluated with payload: <code>" + api().utilities().htmlUtils().encode(payload) + "</code> in parameter <code>"
                        + api().utilities().htmlUtils().encode(insertionPoint.name()) + "</code>.",
                    "Avoid evaluating user input as a template. Sandbox templating engines and use logic-less templates where possible.",
                    rr.request().url(),
                    AuditIssueSeverity.HIGH,
                    AuditIssueConfidence.FIRM,
                    "", "",
                    AuditIssueSeverity.HIGH,
                    rr
                )
            );
        }
    }
}

return AuditResult.auditResult();
```

**Ordering payloads:** put cheap, high-signal probes first and `return` on first hit. Per-insertion-point checks run a *lot* — Burp may invoke yours hundreds of times for a single audited request — so every wasted HTTP send compounds.

---

## Choosing between per-request and per-insertion-point

Easy mistake: writing a per-insertion-point check when per-request would do (or vice versa). Rule of thumb:

- If the *test* mutates a single input value → per insertion point. Burp will run your check against query params, body params, cookies, headers, JSON values, XML values, multipart fields, etc., automatically.
- If the *test* needs to mutate the request as a whole (change method, add headers, replace body) → per request.
- If the *test* is host-wide and request-independent → per host.

Don't write a per-request check that loops over `request.parameters()` and tests each one — that's what per-insertion-point exists for, and Burp's insertion-point detection is more complete than yours will be.
