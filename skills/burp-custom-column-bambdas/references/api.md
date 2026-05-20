# Custom Column Bambda — API Reference

Sources:
- [PortSwigger: Logger custom columns](https://portswigger.net/burp/documentation/desktop/tools/logger/custom-columns)
- [PortSwigger: HTTP history custom columns](https://portswigger.net/burp/documentation/desktop/tools/proxy/http-history/custom-columns)
- [PortSwigger Research: Refining your HTTP perspective, with bambdas](https://portswigger.net/research/adjusting-your-http-perspective-with-bambdas)
- [PortSwigger/bambdas — CustomColumn/](https://github.com/PortSwigger/bambdas/tree/main/CustomColumn)
- [Montoya API JavaDoc](https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/MontoyaApi.html)

All `burp.api.montoya.*` types are **auto-imported**. Use simple names throughout.

---

## Objects in scope

Only two objects are available in a `CUSTOM_COLUMN` script:

| Variable | Type | Access |
|---|---|---|
| `requestResponse` | `ProxyHttpRequestResponse` (HTTP) or `ProxyWebSocketMessage` (WS) | Bare field — read-only |
| `utilities` | `Utilities` | Bare field — **no parens** |

There is no `api()`, no `logging()`, no `selection`. Custom columns cannot send requests or interact with other Burp tools.

> Some community samples call `utilities()` with parens. Prefer the bare field `utilities` — it matches Burp's documented CUSTOM_COLUMN context and the official PortSwigger samples.

---

## Return type

The script must `return` a value. Burp uses the type to determine column sort behaviour:

| Return type | Sort behaviour |
|---|---|
| `String` | Lexicographic |
| `int` / `Integer` | Numeric |
| `boolean` / `Boolean` | As text (`true`/`false`) |

Return `""` for empty/not-applicable. Never return `null`.

NullPointerExceptions are caught at the row level by Burp — cells that throw are left blank. Guard anyway when it makes intent clearer.

---

## `requestResponse` — common methods

```java
requestResponse.hasResponse()              // boolean — check before response access
requestResponse.request()                  // HttpRequest
requestResponse.response()                 // HttpResponse — may be null / NPE if no response yet
requestResponse.httpService()              // HttpService — host, port, protocol
requestResponse.timingData()               // TimingData or empty — response timing when available
```

### Proxy / Logger row extras (HTTP)

These exist on the proxy/logger row type but not on scan-check `requestResponse`:

```java
requestResponse.finalRequest()             // HttpRequest after match-and-replace mangling
requestResponse.finalResponse()            // HttpResponse after mangling, if any
requestResponse.mimeType()                 // MimeType enum — fast content-type classification
requestResponse.annotations()              // notes / highlight color on the row
```

Use `finalRequest()` when the column should reflect traffic as actually sent (after proxy transformations). Use `request()` for the original captured request.

---

## `HttpRequest`

```java
req.method()                               // String: "GET", "POST", etc.
req.url()                                  // String: full URL
req.path()                                 // String: path + query string
req.pathWithoutQuery()                     // String: path only
req.httpVersion()                          // String: "HTTP/1.1" or "HTTP/2"
req.isInScope()                            // boolean

// Headers
req.headerValue("Authorization")           // String or null
req.hasHeader("Authorization")             // boolean
req.headers()                              // List<HttpHeader>

// Parameters
req.parameters()                           // List<HttpParameter>
req.parameters().size()                    // int — total parameter count
req.hasParameter("id", HttpParameterType.URL)         // boolean
req.parameterValue("id", HttpParameterType.URL)       // String or null
req.parameter("session", HttpParameterType.COOKIE)    // HttpParameter

// Body
req.bodyToString()                         // String
req.body()                                 // ByteArray
```

`HttpParameterType`: `URL`, `BODY`, `COOKIE`, `JSON`, `XML`, `XML_ATTRIBUTE`, `MULTIPART_ATTRIBUTE`

---

## `HttpResponse`

```java
res.statusCode()                           // short
res.hasHeader("X-Frame-Options")           // boolean
res.hasHeader("Access-Control-Allow-Origin", "*")  // boolean — value-specific overload
res.headerValue("Content-Type")            // String or null
res.headers()                              // List<HttpHeader>
res.cookies()                              // List<Cookie>
res.bodyToString()                         // String
res.body()                                 // ByteArray
res.isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)  // boolean
```

`StatusCodeClass`: `CLASS_1XX_INFORMATIONAL`, `CLASS_2XX_SUCCESS`, `CLASS_3XX_REDIRECTION`,
`CLASS_4XX_CLIENT_ERRORS`, `CLASS_5XX_SERVER_ERRORS`

---

## `HttpService`

```java
requestResponse.httpService().host()       // String: hostname
requestResponse.httpService().port()       // int
requestResponse.httpService().secure()     // boolean: true = HTTPS
requestResponse.httpService().ipAddress()  // String: resolved IP
```

---

## `TimingData`

When timing is available (Logger and HTTP history rows that have been fully captured):

```java
var delta = requestResponse.timingData().timeBetweenRequestSentAndStartOfResponse();
// delta is Duration or null — guard before calling toMillis()

if (delta != null && delta.toMillis() >= 3000) {
    return delta.toMillis();   // numeric sort for slow-response triage
}
return "";
```

---

## `utilities` — helper functions (bare field)

```java
// Base64
utilities.base64Utils().encode(ByteArray.byteArray(data))   // ByteArray
utilities.base64Utils().decode("base64string")               // ByteArray
utilities.base64Utils().decode(jwtPart, Base64DecodingOptions.URL)  // JWT payloads

// URL encoding
utilities.urlUtils().encode("value with spaces")            // String
utilities.urlUtils().decode("value%20with%20spaces")        // String

// HTML
utilities.htmlUtils().encode("<script>")                    // String
utilities.htmlUtils().decode("&lt;script&gt;")              // String

// JSON
utilities.jsonUtils().isValidJson(str)                      // boolean
utilities.jsonUtils().readString(jsonStr, "user.role")      // String
utilities.jsonUtils().readNumber(jsonStr, "count")          // Number

// Byte utils
utilities.byteUtils().countMatches(bytes, pattern)          // int

// Crypto (avoid in columns — expensive per row)
utilities.cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
```

For base64url outside Montoya helpers, `java.util.Base64.getUrlDecoder()` is fine.

---

## `HttpHeader`, `HttpParameter`, `Cookie`, `ByteArray`

Same shapes as other Bambda types — see `burp-bambdas/references/montoya_api_cheatsheet.md` for full listings.

---

## Burp Globals — optional tunables (no gate)

Custom columns run automatically on every visible row. **Do not add a gate global** that returns `""` when disabled — remove the column from the table instead.

If the script needs a configurable value (header name, regex pattern, threshold), read it with a fallback default:

```java
final String HEADER = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.column-target-header"), "Server"
);
```

Declare tunables in the YAML `burpglobal:` block when delivering a `.bambda` file. There is no standard gate global for columns.

---

## Quick reference: common one-liners

```java
// Response header value
return requestResponse.hasResponse() ? requestResponse.response().headerValue("Server") : "";

// Request parameter count (numeric sort)
return requestResponse.request().parameters().size();

// HTTP version
return requestResponse.request().httpVersion();

// In-scope flag
return requestResponse.request().isInScope();

// Referer
var ref = requestResponse.request().headerValue("Referer");
return ref != null ? ref : "";

// Response status class
return requestResponse.hasResponse()
    ? requestResponse.response().isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
    : false;

// Response body length (numeric sort)
return requestResponse.hasResponse() ? requestResponse.response().body().length() : 0;

// Resolved IP
return requestResponse.httpService().ipAddress();

// JWT claim from Authorization header
var auth = requestResponse.request().headerValue("Authorization");
if (auth == null || !auth.startsWith("Bearer ")) return "";
var parts = auth.substring(7).split("\\.");
if (parts.length != 3) return "";
try {
    var payload = utilities.base64Utils().decode(parts[1], Base64DecodingOptions.URL).toString();
    return utilities.jsonUtils().readString(payload, "sub");
} catch (Exception e) { return ""; }
```
