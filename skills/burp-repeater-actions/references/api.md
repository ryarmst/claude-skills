# Repeater Custom Action — API Reference

Sources:
- [PortSwigger writing guide](https://portswigger.net/burp/documentation/desktop/extend-burp/bambdas/creating/writing-custom-actions/writing-guide)
- [PortSwigger worked example](https://portswigger.net/burp/documentation/desktop/extend-burp/bambdas/creating/writing-custom-actions/worked-example)
- [RetryUntilSuccess sample](https://github.com/PortSwigger/bambdas/blob/main/CustomAction/RetryUntilSuccess.bambda)
- [CookiePrefixBypass sample](https://github.com/PortSwigger/bambdas/blob/main/CustomAction/CookiePrefixBypass.bambda)
- [Montoya API JavaDoc](https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/MontoyaApi.html)

All `burp.api.montoya.*` types are **auto-imported**. Use simple names throughout.

---

## Objects in scope

The Custom actions writing guide names seven objects exposed to a `CUSTOM_ACTION` script:

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | Current request/response pair in the active Repeater tab |
| `selection` | `RequestResponseSelection` | User-highlighted text in the request or response pane |
| `httpEditor` | `HttpEditor` | Active HTTP editor; use to mutate request/response panes |
| `api()` | `MontoyaApi` | Full Montoya API root |
| `utilities()` | `Utilities` | Shorthand for `api().utilities()` |
| `logging()` | `Logging` | Output to Custom actions panel. **Only available in CUSTOM_ACTION.** |
| `ai()` | `Ai` | LLM integration (see PortSwigger AI docs for details) |

`api`, `utilities`, `logging`, and `ai` are available as both bare fields and parenthesised accessors — `logging.logToOutput("x")` and `logging().logToOutput("x")` are equivalent. The official sample bambdas use the method form; this reference does the same for consistency.

---

## `requestResponse` — reading

```java
requestResponse.hasResponse()                    // boolean — false if request not yet sent
requestResponse.request()                        // HttpRequest
requestResponse.response()                       // HttpResponse, may be null
requestResponse.httpService()                    // HttpService (host/port/scheme)
requestResponse.timingData()                     // Optional<TimingData>
```

---

## `HttpRequest` — building and mutating

```java
// Mutations (each returns a new immutable instance — chain freely)
req.withMethod("POST")
req.withPath("/api/v2/endpoint")
req.withBody("new body")
req.withBody(ByteArray.byteArray(bytes))
req.withHeader("X-Custom", "value")             // overwrites existing
req.withAddedHeader("X-Custom", "value")        // always adds
req.withRemovedHeader("Cookie")
req.withQueryParameter(HttpParameter.urlParameter("debug", "1"))
req.withAddedParameters(listOfParams)
req.withRemovedParameters(listOfParams)
req.withUpdatedHeader("X-Custom", "newValue")

// Construction from scratch
HttpRequest.httpRequestFromUrl("https://example.com/path")
HttpRequest.httpRequest(httpService, "GET /path HTTP/1.1\r\nHost: ...\r\n\r\n")
HttpRequest.httpRequest(httpService, ByteArray.byteArray(rawBytes))

// Reading
req.url()
req.method()
req.path()
req.pathWithoutQuery()
req.headerValue("Authorization")                // String or null
req.hasHeader("Authorization")
req.bodyToString()
req.body()                                       // ByteArray
req.parameters()                                 // List<HttpParameter>
req.httpVersion()                                // "HTTP/1.1" or "HTTP/2"
req.httpService()
req.isInScope()
req.toByteArray()                                // for httpEditor.requestPane().set(...)
```

---

## `HttpResponse` — reading

```java
res.statusCode()                                 // short
res.bodyToString()
res.body()                                       // ByteArray
res.headerValue("Set-Cookie")
res.hasHeader("X-Frame-Options")
res.headers()                                    // List<HttpHeader>
res.cookies()                                    // List<Cookie>
res.attributes(AttributeType.COOKIE_NAMES)       // List<Attribute>
res.isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
res.toByteArray()                                // for httpEditor.responsePane().set(...)
```

---

## `httpEditor` — mutating the editor in place

```java
httpEditor.requestPane().set(req.toByteArray())            // replace entire request
httpEditor.responsePane().set(rr.response().toByteArray()) // replace entire response
httpEditor.requestPane().set("plain text")                  // also accepts String
httpEditor.requestPane().replace("old", "new")              // substring replace in request
httpEditor.responsePane().replace("old", "new")             // substring replace in response
```

`set()` updates the editor only — it does NOT mutate the underlying `requestResponse.request()`. If you need the new value later in the script, capture it in a local variable first.

---

## `api().http()` — sending requests

```java
// Single request
var rr = api().http().sendRequest(req);
var rr = api().http().sendRequest(req, HttpMode.HTTP_2);   // force HTTP/2
var rr = api().http().sendRequest(req, HttpMode.HTTP_1);   // force HTTP/1.1

// Parallel batch — uses HTTP/2 single-packet attack or HTTP/1 last-byte sync.
// This is the right primitive for race-condition probing.
List<HttpRequestResponse> results = api().http().sendRequests(List.of(req1, req2));

// Fetch external data
var ext = api().http().sendRequest(HttpRequest.httpRequestFromUrl("https://example.com/feed"));

// Always guard the result:
if (!rr.hasResponse()) { logging().logToOutput("no response"); return; }
```

`HttpMode`: `HTTP_1`, `HTTP_2`, `AUTO`.

---

## `api().repeater()` / `api().organizer()` / `api().siteMap()`

```java
api().repeater().sendToRepeater(req);
api().organizer().sendToOrganizer(rr);           // accepts HttpRequestResponse

// Raise an issue from a custom action (see CookiePrefixBypass.bambda).
api().siteMap().add(AuditIssue.auditIssue(
    "Issue name",
    "Description (may include <b>HTML</b>)",
    "Remediation",
    req.url(),
    AuditIssueSeverity.LOW,
    AuditIssueConfidence.TENTATIVE,
    "Background",
    "References",
    AuditIssueSeverity.LOW,
    rr
));
```

---

## `logging()` — Custom actions output panel

```java
logging().logToOutput("info: " + value);
logging().logToOutput(someObject);               // calls .toString()
logging().logToError("error", exception);        // null exception is accepted
```

Output appears in the **Output** tab of the Custom actions side panel in Repeater.

---

## `selection` — user-selected text

```java
selection.hasRequestSelection()                  // boolean
selection.hasResponseSelection()                 // boolean

// Contents
selection.requestSelection().contents().toString()
selection.responseSelection().contents().toString()

// Byte offsets (useful for splicing into the message as a string)
int start = selection.responseSelection().offsets().startIndexInclusive();
int end   = selection.responseSelection().offsets().endIndexExclusive();
```

---

## `utilities()` — helper functions

```java
utilities().base64Utils().encode(ByteArray.byteArray(data))   // ByteArray
utilities().base64Utils().decode(str)                          // ByteArray
utilities().htmlUtils().encode(str)
utilities().htmlUtils().decode(str)
utilities().urlUtils().encode(str)
utilities().urlUtils().decode(str)
utilities().cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
utilities().cryptoUtils().computeHmac(keyBytes, dataBytes, HmacAlgorithm.HMAC_SHA256)
utilities().jsonUtils().isValidJson(str)
utilities().jsonUtils().readString(jsonStr, "data.token")
utilities().jsonUtils().readNumber(jsonStr, "count")
utilities().randomUtils().randomString(16)
utilities().randomUtils().randomBytes(16)
```

`DigestAlgorithm`: `MD5`, `SHA_1`, `SHA_256`, `SHA_384`, `SHA_512`.
`HmacAlgorithm`: `HMAC_SHA1`, `HMAC_SHA256`, `HMAC_SHA384`, `HMAC_SHA512`.

---

## `utilities().shellUtils()` — shell execution

Always prefer the split-arg form over `dangerouslyExecute` — the former has no shell injection risk.

```java
// Safe: command and arguments passed separately.
var result = utilities().shellUtils().execute("jq", ".token", "-r");
logging().logToOutput(result.output());          // stdout
logging().logToOutput(result.error());           // stderr
result.exitCode();                                // int

// With options.
var opts = executeOptions()
    .withTimeout(java.time.Duration.ofSeconds(15))
    .withTimeoutBehavior(TimeoutBehavior.ALLOW_TIMEOUT)
    .withStderrBehavior(StderrBehavior.MERGE)           // merge stderr into stdout
    .withExitCodeBehavior(ExitCodeBehavior.ALLOW_NON_ZERO)
    .withEnvironmentVariable("API_KEY", "secret");
var result = utilities().shellUtils().execute(opts, "curl", "-s", "https://example.com");

// UNSAFE: never use with user-controlled input.
utilities().shellUtils().dangerouslyExecute("echo hello");
```

---

## `ByteArray`

```java
ByteArray.byteArray("hello")                     // from String (UTF-8)
ByteArray.byteArray(new byte[]{1, 2, 3})         // from byte[]

ba.getBytes()                                    // byte[]
ba.toString()                                    // UTF-8 String
ba.length()
ba.indexOf("needle", true)                       // case-insensitive search
ba.subArray(start, end)
ba.setByte(idx, (byte) 0xE2)                     // mutating setter
```

---

## `HttpParameter` factories

```java
HttpParameter.urlParameter(name, value)
HttpParameter.bodyParameter(name, value)
HttpParameter.cookieParameter(name, value)
HttpParameter.parameter(name, value, HttpParameterType.JSON)
```

`HttpParameterType`: `URL`, `BODY`, `COOKIE`, `JSON`, `XML`, `XML_ATTRIBUTE`, `MULTIPART_ATTRIBUTE`.

---

## Burp Globals — reading variables

The Burp Globals extension (https://github.com/ryarmst/Burp-Globals) publishes each global as a JVM system property prefixed with `bg.`. Read them with `System.getProperty()`.

```java
// Boolean gate.
if (!"true".equalsIgnoreCase(System.getProperty("bg.bambda-action"))) {
    logging().logToOutput("[MyAction] disabled — set bg.bambda-action=true to enable");
    return;
}

// String with default.
final String TARGET = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.bambda-action-target"), "Authorization"
);

// Integer with default.
final int MAX = Integer.parseInt(
    java.util.Objects.requireNonNullElse(System.getProperty("bg.bambda-action-max"), "20")
);

// Boolean (no default = false).
final boolean VERBOSE =
    "true".equalsIgnoreCase(System.getProperty("bg.bambda-action-verbose"));
```

Globals are also expanded inside raw HTTP messages via `${bg:variable_name}` placeholders, which Burp Globals resolves at send time.
