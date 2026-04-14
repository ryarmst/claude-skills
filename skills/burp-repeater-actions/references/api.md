# Repeater Custom Action — API Reference

Source: [PortSwigger writing guide](https://portswigger.net/burp/documentation/desktop/extend-burp/bambdas/creating/writing-custom-actions/writing-guide), [RetryUntilSuccess official sample](https://raw.githubusercontent.com/PortSwigger/bambdas/main/CustomAction/RetryUntilSuccess.bambda).

All `burp.api.montoya.*` types are **auto-imported**. Use simple names throughout.

---

## Objects in scope

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | Current request/response pair in the active Repeater tab |
| `httpEditor` | `HttpRepeaterEditor` | Active HTTP editor in Repeater; use to mutate request/response panes |
| `wsEditor` | WebSocket editor | Active WebSocket editor; available instead of `httpEditor` in WS tabs |
| `api()` | `MontoyaApi` | Full Montoya API root |
| `utilities()` | `Utilities` | Shorthand for `api().utilities()` |
| `logging()` | `Logging` | Output to Custom actions panel. **Only available in CUSTOM_ACTION.** |
| `selection` | `RequestResponseSelection` | User-highlighted text in the request or response pane |
| `ai()` | `Ai` | LLM integration (see PortSwigger AI docs for details) |

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
res.isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
res.toByteArray()                                // for httpEditor.responsePane().set(...)
```

---

## `httpEditor` — mutating the editor in place

```java
httpEditor.requestPane().set(req.toByteArray())          // replace entire request
httpEditor.responsePane().set(rr.response().toByteArray()) // replace entire response
httpEditor.requestPane().replace("old", "new")           // substring replace in request
httpEditor.responsePane().replace("old", "new")          // substring replace in response
```

---

## `api().http()` — sending requests

```java
// Single request
var rr = api().http().sendRequest(req);
var rr = api().http().sendRequest(req, HttpMode.HTTP_2);   // force HTTP/2
var rr = api().http().sendRequest(req, HttpMode.HTTP_1);   // force HTTP/1.1

// Parallel batch
List<HttpRequestResponse> results = api().http().sendRequests(List.of(req1, req2));

// Always guard the result:
if (!rr.hasResponse()) { logging().logToOutput("no response"); return; }
```

`HttpMode`: `HTTP_1`, `HTTP_2`, `AUTO`.

---

## `api().repeater()` / `api().organizer()`

```java
api().repeater().sendToRepeater(req);
api().organizer().sendToOrganizer(rr);           // accepts HttpRequestResponse
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

// Byte offsets (useful for splicing into the request)
int start = selection.responseSelection().offsets().startIndexInclusive();
int end   = selection.responseSelection().offsets().endIndexExclusive();
```

---

## `utilities()` — helper functions

```java
utilities().base64Utils().encode(ByteArray.byteArray(data))
utilities().base64Utils().decode(str)            // returns ByteArray
utilities().htmlUtils().encode(str)
utilities().htmlUtils().decode(str)
utilities().urlUtils().encode(str)
utilities().urlUtils().decode(str)
utilities().cryptoUtils().generateDigest(byteArray, DigestAlgorithm.SHA_256)
utilities().cryptoUtils().computeHmac(...)
utilities().jsonUtils().isValidJson(str)
utilities().jsonUtils().readString(jsonStr, "data.token")
utilities().jsonUtils().readNumber(jsonStr, "count")
utilities().randomUtils().randomString(16)
utilities().randomUtils().randomBytes(16)
```

`DigestAlgorithm`: `MD5`, `SHA_1`, `SHA_256`, `SHA_384`, `SHA_512`.

---

## `utilities().shellUtils()` — shell execution

Always prefer the split-arg form over `dangerouslyExecute` — the former has no shell injection risk.

```java
// Safe: command and arguments passed separately.
var result = utilities().shellUtils().execute("jq", ".token", "-r");
logging().logToOutput(result.output());
logging().logToError("stderr", null);  // result.error() for stderr

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
```

---

## `HttpParameter` factories

```java
HttpParameter.urlParameter(name, value)
HttpParameter.bodyParameter(name, value)
HttpParameter.cookieParameter(name, value)
HttpParameter.parameter(name, value, HttpParameterType.JSON)
```

---

## Burp Globals — reading variables

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
```
