# Custom Column Bambda — API Reference

Sources:
- [PortSwigger: Adding custom columns in Logger](https://portswigger.net/burp/documentation/desktop/tools/logger/custom-columns)
- [PortSwigger: Adding custom columns in HTTP history](https://portswigger.net/burp/documentation/desktop/tools/proxy/http-history/custom-columns)
- [PortSwigger Research: Refining your HTTP perspective, with bambdas](https://portswigger.net/research/adjusting-your-http-perspective-with-bambdas)
- [PortSwigger/bambdas GitHub — CustomColumn/](https://github.com/PortSwigger/bambdas/tree/main/CustomColumn)
- [Montoya API JavaDoc](https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/MontoyaApi.html)

All `burp.api.montoya.*` types are **auto-imported**. Use simple names throughout.

---

## Objects in scope

Only two objects are available in a `CUSTOM_COLUMN` script:

| Variable | Type | Access |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | Bare field |
| `utilities` | `Utilities` | Bare field — **no parens** |

There is no `api()`, no `logging()`, no `selection`. Custom columns are read-only — they cannot send requests or interact with other tools.

---

## Return type

The script must `return` a value. Burp uses the type to determine column sort behaviour:

| Return type | Sort behaviour |
|---|---|
| `String` | Lexicographic |
| `int` / `Integer` | Numeric |
| `boolean` / `Boolean` | As text (`true`/`false`) |

Return `""` for empty/not-applicable. Never return `null`.

NullPointerExceptions are caught at the row level by Burp — cells that throw are left blank.

---

## `requestResponse`

```java
requestResponse.hasResponse()              // boolean — always check before accessing response
requestResponse.request()                  // HttpRequest
requestResponse.response()                 // HttpResponse, may cause NPE if no response yet
requestResponse.httpService()              // HttpService — host, port, protocol
requestResponse.timingData()              // Optional<TimingData>
```

---

## `HttpRequest`

```java
// Reading fields
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

## `utilities` — helper functions (bare field)

```java
// Base64
utilities.base64Utils().encode(ByteArray.byteArray(data))   // ByteArray
utilities.base64Utils().decode("base64string")               // ByteArray
// For base64url, use java.util.Base64.getUrlDecoder() directly

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
// bytes = ByteArray.byteArray(str) or response.body().getBytes()

// Crypto (rarely needed in columns — avoid for performance)
utilities.cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
```

---

## `HttpHeader`

```java
header.name()                              // String
header.value()                             // String
header.toString()                          // "Name: Value"
```

---

## `HttpParameter`

```java
param.name()                               // String
param.value()                              // String
param.type()                               // HttpParameterType
```

---

## `Cookie`

```java
cookie.name()                              // String
cookie.value()                             // String
cookie.domain()                            // Optional<String>
cookie.path()                              // Optional<String>
cookie.secure()                            // boolean
cookie.httpOnly()                          // boolean
cookie.sameSite()                          // Optional<String>
```

---

## `ByteArray`

```java
ByteArray.byteArray("string")              // from String (UTF-8)
ByteArray.byteArray(new byte[]{...})       // from byte[]
ba.toString()                              // UTF-8 String
ba.length()                                // int
ba.getBytes()                              // byte[]
ba.indexOf("needle", true)                 // int, case-insensitive search
```

---

## Burp Globals — reading configurable values

Custom columns do not use a gate global (they run automatically). If the script needs a configurable value — e.g. a header name or a regex pattern — read it with a fallback default:

```java
final String HEADER = java.util.Objects.requireNonNullElse(
    System.getProperty("bg.column-target-header"), "X-Custom-Header"
);
```

Do not add a gate check. There is no mechanism to disable a column without removing it from the table.

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
return requestResponse.request().headerValue("Referer");

// Response status class
return requestResponse.hasResponse()
    ? requestResponse.response().isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
    : false;

// Response body length (numeric sort)
return requestResponse.hasResponse() ? requestResponse.response().body().length() : 0;

// Resolved IP
return requestResponse.httpService().ipAddress();
```
