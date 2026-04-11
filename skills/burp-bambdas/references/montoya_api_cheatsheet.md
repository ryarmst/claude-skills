# Montoya API Cheatsheet (Bambda Edition)

This is the **actually-working** API surface drawn from real PortSwigger Bambda samples — not from the published Montoya Javadoc, which assumes you're writing a full Java extension. Several things differ in Bambda context.

All `burp.api.montoya.*` types are auto-imported. Use them by simple name.

---

## 1. Entry points — they vary by function type

The biggest pitfall. The same Montoya API is reached by different identifiers depending on which Bambda function type you're writing.

| Identifier | Available in | Returns | Example |
|---|---|---|---|
| `api()` | `SCAN_CHECK_*`, `CUSTOM_ACTION` | `MontoyaApi` | `api().utilities().htmlUtils().encode(s)` |
| `utilities` (bare field) | `VIEW_FILTER`, `CUSTOM_COLUMN`, `MATCH_AND_REPLACE_*` | `Utilities` | `utilities.jsonUtils().readString(body, "id")` |
| `utilities()` (method) | `CUSTOM_ACTION`, `SCAN_CHECK_*` (works in some Burp versions) | `Utilities` | `utilities().randomUtils().randomString(8)` |
| `http` (bare field) | `SCAN_CHECK_*` | `Http` | `http.sendRequest(req)` |
| `logging` (bare field) | `VIEW_FILTER`, `CUSTOM_COLUMN`, `MATCH_AND_REPLACE_*` | `Logging` | `logging.logToOutput("hi")` |
| `logging()` (method) | `CUSTOM_ACTION` | `Logging` | `logging().logToOutput("hi")` |
| `requestResponse` | All function types | varies (see below) | `requestResponse.request()` |
| `insertionPoint` | `SCAN_CHECK_*_PER_INSERTION_POINT` only | `AuditInsertionPoint` | |
| `collaboratorClient` | Scan checks with "Use Collaborator" enabled | `CollaboratorClient` | |
| `httpEditor` / `wsEditor` | `CUSTOM_ACTION` (Repeater) | editor handle | `httpEditor.responsePane().set(bytes)` |

**Safe universal pattern when in doubt:**

- In a scan check: prefer `api().utilities()`, use bare `http`.
- In a filter/column/M&R: use bare `utilities` and `logging`.
- In a custom action: use `api().http()`, `utilities()`, `logging()`, and the editor handles.

---

## 2. `requestResponse` — type varies

| Function type | Type of `requestResponse` |
|---|---|
| `SCAN_CHECK_*` | `HttpRequestResponse` |
| `VIEW_FILTER` (HTTP), `CUSTOM_COLUMN` (HTTP), `MATCH_AND_REPLACE_*` | `ProxyHttpRequestResponse` |
| `VIEW_FILTER` (WS), `CUSTOM_COLUMN` (WS) | `ProxyWebSocketMessage` |
| `CUSTOM_ACTION` | `HttpRequestResponse` |

`ProxyHttpRequestResponse` extends `HttpRequestResponse` with proxy-only methods like `mimeType()`, `annotations()`, `finalResponse()`, `listenerInterface()`.

### Common methods (HTTP)

```java
requestResponse.hasResponse()                          // boolean
requestResponse.request()                              // HttpRequest
requestResponse.response()                             // HttpResponse, may be null
requestResponse.httpService()                          // HttpService (host/port/secure)
requestResponse.timingData()                           // Optional<TimingData>
requestResponse.annotations()                          // Annotations (notes, highlight color)

// Proxy-only:
requestResponse.mimeType()                             // MimeType enum
requestResponse.finalResponse()                        // post-response-modification
requestResponse.listenerInterface()                    // String "127.0.0.1:8080"
```

---

## 3. `HttpRequest` — building and mutating

### Constructing from scratch

```java
// From a URL string (parses host/port/scheme)
HttpRequest.httpRequestFromUrl("https://example.com/path?a=1")

// From a service + raw request string
HttpRequest.httpRequest(service, "GET / HTTP/1.1\r\nHost: x\r\n\r\n")

// From a service + body bytes (used after building a raw text request)
HttpRequest.httpRequest(service, ByteArray.byteArray(rawBytes))
```

### Mutating (returns a new immutable request — chain freely)

```java
req.withMethod("POST")
req.withPath("/admin")
req.withBody("payload")
req.withBody(ByteArray.byteArray(bytes))
req.withHeader("X-Foo", "bar")              // overwrites
req.withAddedHeader("X-Foo", "bar")         // adds
req.withRemovedHeader("Cookie")
req.withService(otherService)
req.withQueryParameter(HttpParameter.urlParameter("debug", "1"))
req.withAddedParameters(listOfHttpParameter)
req.withRemovedParameters(listOfHttpParameter)
req.withDefaultHeaders()
```

### Reading

```java
req.url()                                   // String
req.method()                                // String "GET"
req.path()                                  // String with query
req.pathWithoutQuery()
req.headers()                               // List<HttpHeader>
req.headerValue("Authorization")            // String, null if missing
req.hasHeader("X-Foo")
req.body()                                  // ByteArray
req.bodyToString()                          // String
req.parameters()                            // List<HttpParameter>
req.parameter("name", HttpParameterType.URL)
req.hasParameter("name", HttpParameterType.COOKIE)
req.contains("needle", true)                // case-sensitive substring
req.contains(java.util.regex.Pattern.compile("..."))
req.isInScope()
req.httpVersion()                           // "HTTP/1.1" or "HTTP/2"
req.httpService()
```

### `HttpParameter` factories

```java
HttpParameter.urlParameter(name, value)
HttpParameter.bodyParameter(name, value)
HttpParameter.cookieParameter(name, value)
HttpParameter.parameter(name, value, HttpParameterType.JSON)
```

`HttpParameterType` values: `URL`, `BODY`, `COOKIE`, `JSON`, `XML`, `XML_ATTRIBUTE`, `MULTIPART_ATTRIBUTE`.

---

## 4. `HttpResponse` — reading

```java
res.statusCode()                            // short
res.reasonPhrase()                          // String
res.isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
res.headers()                               // List<HttpHeader>
res.headerValue("Server")
res.hasHeader("Set-Cookie")
res.body()                                  // ByteArray
res.bodyToString()
res.cookies()                               // List<Cookie>
res.cookie("session")                       // Cookie or null
res.mimeType()                              // MimeType enum (response's reported type)
res.statedMimeType()
res.inferredMimeType()
res.attributes(AttributeType.COOKIE_NAMES)  // List<Attribute>
```

`StatusCodeClass`: `CLASS_1XX_INFORMATIONAL`, `CLASS_2XX_SUCCESS`, `CLASS_3XX_REDIRECTION`, `CLASS_4XX_CLIENT_ERRORS`, `CLASS_5XX_SERVER_ERRORS`.

`MimeType` enum values include: `HTML`, `JSON`, `XML`, `JAVASCRIPT`, `CSS`, `IMAGE_JPEG`, `IMAGE_PNG`, `IMAGE_GIF`, `IMAGE_BMP`, `IMAGE_TIFF`, `IMAGE_UNKNOWN`, `FONT_WOFF`, `FONT_WOFF2`, `SOUND`, `VIDEO`, `APPLICATION_UNKNOWN`, `UNRECOGNIZED`, `PLAIN_TEXT`, `SCRIPT`, `RTF`.

### Mutating (M&R response context)

```java
res.withStatusCode((short)200)
res.withHeader("X-Foo", "bar")
res.withAddedHeader("X-Foo", "bar")
res.withRemovedHeader("Content-Security-Policy")
res.withBody("new body")
```

---

## 5. `Http` — sending requests (scan checks, custom actions)

```java
http.sendRequest(req)                                // HttpRequestResponse
http.sendRequest(req, HttpMode.HTTP_1)               // force HTTP/1.1
http.sendRequest(req, HttpMode.HTTP_2)               // force HTTP/2
http.sendRequest(req, requestOptions)                // with RequestOptions
```

`HttpMode`: `HTTP_1`, `HTTP_2`, `AUTO`.

**The result `HttpRequestResponse` may have no response** (network error, timeout). Always:

```java
var rr = http.sendRequest(req);
if (!rr.hasResponse()) continue;  // or return
```

---

## 6. `Utilities`

Reached as `api().utilities()`, `utilities()`, or `utilities` depending on context.

```java
utilities.htmlUtils().encode(str)                    // HTML-escape for issue HTML
utilities.htmlUtils().decode(str)
utilities.urlUtils().encode(str)
utilities.urlUtils().decode(str)
utilities.base64Utils().encode(bytes)
utilities.base64Utils().decode(str)                  // returns ByteArray
utilities.randomUtils().randomString(8)              // alphanumeric
utilities.randomUtils().randomBytes(16)
utilities.cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
utilities.cryptoUtils().computeHmac(...)
utilities.byteUtils().convertFromString(str)
utilities.compressionUtils().decompress(byteArray, CompressionType.GZIP)
utilities.compressionUtils().compress(byteArray, CompressionType.GZIP)
utilities.jsonUtils().isValidJson(str)
utilities.jsonUtils().readString(jsonStr, "operationName")
utilities.jsonUtils().readString(jsonStr, "data.user.email")  // dotted path
utilities.jsonUtils().readNumber(jsonStr, "count")
utilities.jsonUtils().readBoolean(jsonStr, "active")
```

`DigestAlgorithm`: `MD5`, `SHA_1`, `SHA_256`, `SHA_384`, `SHA_512`, etc.

---

## 7. `ByteArray`

Many Montoya methods return `ByteArray` instead of `byte[]`. Convert as needed:

```java
ByteArray.byteArray("hello")                         // from String
ByteArray.byteArray(byteArray)                       // copy
ByteArray.byteArray(new byte[]{1,2,3})              // from byte[]

ba.getBytes()                                        // byte[]
ba.toString()                                        // String (UTF-8 by default)
ba.length()
ba.indexOf("needle")                                 // int, -1 if missing
ba.indexOf("needle", false)                          // case-insensitive
ba.contains("needle", true)
ba.subArray(start, end)
ba.setByte(index, (byte) 0x00)                       // mutable!
```

`ByteArray` is **mutable** when you do byte-level edits — be careful in shared references.

---

## 8. `AuditIssue` and friends

```java
AuditIssue.auditIssue(
    String name,
    String detail,
    String remediation,
    String baseUrl,
    AuditIssueSeverity severity,
    AuditIssueConfidence confidence,
    String background,                  // may be ""
    String remediationBackground,       // may be ""
    AuditIssueSeverity typicalSeverity,
    HttpRequestResponse... evidence
)
```

`AuditIssueSeverity`: `INFORMATION`, `LOW`, `MEDIUM`, `HIGH`.
`AuditIssueConfidence`: `CERTAIN`, `FIRM`, `TENTATIVE`.

```java
AuditResult.auditResult()                            // empty
AuditResult.auditResult(issue)                       // varargs
AuditResult.auditResult(issue1, issue2, issue3)
AuditResult.auditResult(listOfIssues)                // List<AuditIssue>
```

---

## 9. `AuditInsertionPoint` (per-insertion-point checks)

```java
insertionPoint.name()                                // parameter name
insertionPoint.baseValue()                           // current value
insertionPoint.type()                                // AuditInsertionPointType
insertionPoint.buildHttpRequestWithPayload(byteArray)   // HttpRequest
insertionPoint.issueHighlights(payload)              // List<Marker> for evidence highlighting
```

`AuditInsertionPointType` values include: `PARAM_URL`, `PARAM_BODY`, `PARAM_COOKIE`, `PARAM_JSON`, `PARAM_XML`, `PARAM_XML_ATTR`, `PARAM_MULTIPART_ATTR`, `PARAM_NAME_URL`, `PARAM_NAME_BODY`, `HEADER`, `URL_PATH_FILENAME`, `URL_PATH_FOLDER`.

You can use the type to skip irrelevant insertion points:

```java
if (insertionPoint.type() == AuditInsertionPointType.HEADER) {
    return AuditResult.auditResult();   // skip headers for this check
}
```

---

## 10. `Cookie`

```java
cookie.name()
cookie.value()
cookie.path()
cookie.domain()
cookie.expiration()                                  // Optional<ZonedDateTime>
```

---

## 11. `TimingData` (response timing)

```java
var t = rr.timingData();
if (t.isPresent()) {
    long ms = t.get().timeBetweenRequestSentAndStartOfResponse().toMillis();
}
```

Use this for time-based blind SQLi / blind command injection / SSRF detection — much better than `System.currentTimeMillis()` around the call.

---

## 12. Logging

```java
logging.logToOutput("info: " + value);               // filter/column/M&R
logging().logToOutput("info: " + value);             // custom action
api().logging().logToOutput("info: " + value);       // scan check (or just use System.out?)
api().logging().logToError("error: " + e);
api().logging().raiseInfoEvent("audit started");
api().logging().raiseErrorEvent("audit failed: " + e);
```

`raiseInfoEvent` / `raiseErrorEvent` show in the Burp Dashboard event log; `logToOutput` goes to the extension output console.
