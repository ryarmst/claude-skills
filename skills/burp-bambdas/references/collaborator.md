# Burp Collaborator in Bambdas

Use Collaborator when the vulnerability is **out-of-band** — the application's response doesn't reveal whether your payload worked, but a DNS / HTTP / SMTP callback to an attacker-controlled server does. Examples: blind SSRF, blind XXE, blind command injection (curl/wget out), blind SQLi via DNS/HTTP exfil, log injection that resolves URLs, email splitting where the SMTP dialogue lands at your server.

---

## 1. Two ways to get a `CollaboratorClient`

### A. Implicit (preferred when available)

In a scan check, **enable the "Use Collaborator" toggle in the script settings panel**. Burp then injects a pre-made `collaboratorClient` variable into your script's scope. You don't construct it yourself.

```java
// collaboratorClient is just there
var payload = collaboratorClient.generatePayload();
```

When you use the implicit client, Burp also handles polling for you in some scenarios — but for explicit `getAllInteractions()` you still need to drive the loop yourself.

### B. Explicit

In any function type with `api()` available (scan checks, custom actions), construct one:

```java
var client = api().collaborator().createClient();
```

The PortSwigger `EmailSplittingCollaboratorClient.bambda` sample uses this form because it wants explicit control over the polling lifecycle.

---

## 2. Generating payloads

```java
var payload = collaboratorClient.generatePayload();

payload.toString()                       // full Collaborator domain: "abc123.oastify.com"
payload.id()                             // CollaboratorPayloadId — the unique part
payload.id().toString()                  // String form of the id
payload.server()                         // Optional<CollaboratorServer>
payload.server().get().address()         // "oastify.com" or your private collaborator server
```

You typically embed `payload.toString()` somewhere in your attack:

```java
var attackUrl = "http://" + payload.toString() + "/x";
var probe = http.sendRequest(insertionPoint.buildHttpRequestWithPayload(
    ByteArray.byteArray(attackUrl)
));
```

Or, if your injection format requires the id and server separately (e.g., the email-splitting encoded-word technique):

```java
var p = collaboratorClient.generatePayload();
var technique = template
    .replace("$COLLABORATOR_PAYLOAD", p.id().toString())
    .replace("$COLLABORATOR_SERVER", p.server().get().address());
```

---

## 3. The mapping problem

You will fire off N payloads, each with a unique Collaborator subdomain, and you must remember **which request each payload belongs to** so that when an interaction comes back, you can build the issue against the right `HttpRequestResponse` evidence.

The standard idiom is a `HashMap<String, HttpRequestResponse>` keyed by `payload.id().toString()`:

```java
var sent = new java.util.HashMap<String, HttpRequestResponse>();

for (var template : techniques) {
    var p = collaboratorClient.generatePayload();
    var rendered = template
        .replace("$COLLABORATOR_PAYLOAD", p.id().toString())
        .replace("$COLLABORATOR_SERVER", p.server().get().address());

    var rr = http.sendRequest(insertionPoint.buildHttpRequestWithPayload(
        ByteArray.byteArray(rendered)
    ));
    sent.put(p.id().toString(), rr);
}
```

Then, when polling, look up `sent.get(interaction.id().toString())` to attach evidence to the right request.

---

## 4. The bounded poll loop (canonical pattern)

This is the pattern from `EmailSplittingCollaboratorClient.bambda`. **Always bound the total wait time** — Burp will hang the entire scan thread otherwise.

```java
final long POLL_SLEEP_MS = 1_000;
final long TOTAL_TIME_MS = 10_000;

var issues = new java.util.ArrayList<AuditIssue>();

try {
    long start = System.currentTimeMillis();
    while (System.currentTimeMillis() - start < TOTAL_TIME_MS) {
        var interactions = collaboratorClient.getAllInteractions();
        for (var i : interactions) {
            var rr = sent.get(i.id().toString());
            if (rr == null) continue;          // not one of ours

            issues.add(buildIssueFromInteraction(i, rr));
        }
        if (!interactions.isEmpty()) break;    // optional: stop on first hit
        java.util.concurrent.TimeUnit.MILLISECONDS.sleep(POLL_SLEEP_MS);
    }
} catch (InterruptedException ignored) {
    Thread.currentThread().interrupt();
}

return AuditResult.auditResult(issues);
```

**Tuning:**
- For per-insertion-point checks, keep `TOTAL_TIME_MS` short (5–15s). The check runs many times.
- For per-host checks, you can afford 30–60s.
- Don't set `POLL_SLEEP_MS` below ~500ms — you'll just hammer the Collaborator server with no benefit; interactions take longer than that to propagate anyway.

---

## 5. Inspecting an `Interaction`

```java
i.id()                                  // CollaboratorPayloadId
i.id().toString()                       // String
i.timeStamp()                           // ZonedDateTime
i.clientIp()                            // InetAddress of the caller
i.type()                                // InteractionType: DNS, HTTP, SMTP

// Protocol-specific (Optional<>):
i.dnsDetails()                          // Optional<DnsDetails>
i.httpDetails()                         // Optional<HttpDetails>
i.smtpDetails()                         // Optional<SmtpDetails>
```

### DNS

```java
if (i.dnsDetails().isPresent()) {
    var dns = i.dnsDetails().get();
    var qtype = dns.queryType();        // DnsQueryType.A, AAAA, etc.
    var rawQuery = dns.query();         // ByteArray of the raw DNS packet
}
```

DNS-only interactions are the lowest-confidence signal — they prove your payload was *parsed* somewhere that did a name resolution, not necessarily that it was *fetched*. Still useful for blind SSRF / log injection / SQLi DNS exfil.

### HTTP

```java
if (i.httpDetails().isPresent()) {
    var http = i.httpDetails().get();
    var protocol = http.protocol();     // HTTP or HTTPS
    var req = http.requestResponse().request();
    var res = http.requestResponse().response();
    // .requestResponse() is the interaction's own captured req/res, NOT your audited target
}
```

HTTP interactions are high-confidence: someone actually fetched your URL.

### SMTP

```java
if (i.smtpDetails().isPresent()) {
    var smtp = i.smtpDetails().get();
    var conversation = smtp.conversation();  // String — full SMTP dialogue
    var protocol = smtp.protocol();          // SMTP or SMTPS
}
```

Use for email-splitting and SMTP-injection-style bugs. Truncate `conversation` before putting it in an issue (it can be huge).

---

## 6. Reporting an interaction-based issue

```java
AuditIssue buildIssueFromInteraction(Interaction i, HttpRequestResponse rr) {
    var detail = new StringBuilder("<p>Out-of-band interaction received from <code>")
        .append(api().utilities().htmlUtils().encode(i.clientIp().getHostAddress()))
        .append("</code> at ")
        .append(i.timeStamp())
        .append(" via <code>")
        .append(i.type())
        .append("</code>.</p>");

    if (i.smtpDetails().isPresent()) {
        var convo = i.smtpDetails().get().conversation();
        if (convo.length() > 1000) convo = convo.substring(0, 1000) + "...";
        detail.append("<pre>")
              .append(api().utilities().htmlUtils().encode(convo))
              .append("</pre>");
    }

    return AuditIssue.auditIssue(
        "Out-of-band interaction (" + i.type() + ")",
        detail.toString(),
        "Validate and sanitize the affected input. Block outbound traffic from the application to untrusted destinations.",
        rr.request().url(),
        AuditIssueSeverity.HIGH,
        AuditIssueConfidence.FIRM,
        "", "",
        AuditIssueSeverity.HIGH,
        rr
    );
}
```

**Note on evidence:** when you report a Collaborator-driven issue, Burp's UI shows the `rr` you pass as the "Request" tab — but Burp documents that for Collaborator-sourced issues it stores the *base* request rather than the modified one, because it can't reconstruct the mutation. If you want the modified request visible, store the post-mutation `HttpRequestResponse` in your `sent` map (which is what the example above does), and pass that — it works in practice.

---

## 7. Common pitfalls

1. **Forgetting to bound the poll loop.** A Bambda that calls `getAllInteractions()` in an unbounded `while (true)` will freeze the scan thread forever.
2. **Polling too fast.** Below 500ms is wasted CPU.
3. **Not mapping interactions to requests.** Without the `sent` map, you can't tell which payload triggered which callback, so your issue evidence is wrong.
4. **Using Collaborator in a `VIEW_FILTER` / `CUSTOM_COLUMN`.** Collaborator is only available where `api()` or `collaboratorClient` is in scope — i.e. scan checks and custom actions.
5. **Per-insertion-point + long polls = scan death.** A 60-second poll loop multiplied by hundreds of insertion points is hours of wall-clock time. Either drop to per-request, or use a very short poll, or fire-and-forget the payloads in one pass and verify at the end.
6. **Confusing `payload.id()` with `payload.toString()`.** `id()` is just the unique label part; `toString()` is the full domain name. Use `toString()` when embedding in URLs/hostnames; use `id().toString()` as the map key.
