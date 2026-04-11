# View Filters, Custom Columns, Custom Actions, Match & Replace

These four function types are non-scan-check Bambdas. They run in different parts of Burp and have different return types.

---

## VIEW_FILTER

**Where:** Proxy HTTP history, Proxy WS history, Logger, Site map.
**Locations (`location:` field):** `PROXY_HTTP_HISTORY`, `PROXY_WS_HISTORY`, `LOGGER`, `SITE_MAP`.
**Return type:** `boolean`. `true` = show this row, `false` = hide it.
**Objects in scope:**

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `ProxyHttpRequestResponse` (HTTP) or `ProxyWebSocketMessage` (WS) | The current row being filtered. |
| `utilities` | `Utilities` | **Bare field, no parens.** Different from scan checks! |
| `logging` | `Logging` | For `logging.logToOutput(...)` debugging. |

**Useful methods on the HTTP variant:**

```java
requestResponse.hasResponse()
requestResponse.request()              // HttpRequest
requestResponse.response()             // HttpResponse, may be null
requestResponse.finalResponse()        // post-mangler, if any
requestResponse.mimeType()             // MimeType enum
requestResponse.annotations()          // notes / highlight color
requestResponse.request().isInScope()
requestResponse.request().pathWithoutQuery()
requestResponse.response().statusCode()
requestResponse.response().isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
requestResponse.response().bodyToString()
requestResponse.response().hasHeader("X-Foo")
```

**Skeleton:**

```java
// === CONFIG ===
final boolean SHOW_OUT_OF_SCOPE = false;
final boolean HIDE_STATIC_ASSETS = true;

if (!requestResponse.hasResponse()) return false;

var req = requestResponse.request();
var res = requestResponse.response();

if (!SHOW_OUT_OF_SCOPE && !req.isInScope()) return false;

if (HIDE_STATIC_ASSETS) {
    var mt = requestResponse.mimeType();
    if (mt == MimeType.CSS || mt == MimeType.IMAGE_JPEG || mt == MimeType.IMAGE_PNG
        || mt == MimeType.IMAGE_GIF || mt == MimeType.FONT_WOFF || mt == MimeType.FONT_WOFF2
        || mt == MimeType.SOUND || mt == MimeType.VIDEO) {
        return false;
    }
}

// === MATCH ===
return res.isStatusCodeClass(StatusCodeClass.CLASS_2XX_SUCCESS)
    && req.hasHeader("Authorization");
```

**Return early and return often.** Filters run on every row in the table on every keystroke; cheap rejections first.

---

## CUSTOM_COLUMN

**Where:** Proxy HTTP history, WS history, Logger.
**Locations:** `PROXY_HTTP_HISTORY`, `PROXY_WS_HISTORY`, `LOGGER`.
**Return type:** `String`. Whatever you return becomes the cell text. Empty string = empty cell.
**Objects in scope:** same as `VIEW_FILTER`. `utilities` is a bare field.

**Skeleton:**

```java
if (!requestResponse.hasResponse()) return "";

var body = requestResponse.request().bodyToString();
if (!utilities.jsonUtils().isValidJson(body)) return "";

return utilities.jsonUtils().readString(body, "operationName");
```

**Common patterns:**

- **Extract a JWT claim:**
  ```java
  var auth = requestResponse.request().headerValue("Authorization");
  if (auth == null || !auth.startsWith("Bearer ")) return "";
  var parts = auth.substring(7).split("\\.");
  if (parts.length != 3) return "";
  try {
      var payload = new String(java.util.Base64.getUrlDecoder().decode(parts[1]),
                               java.nio.charset.StandardCharsets.UTF_8);
      return utilities.jsonUtils().readString(payload, "sub");
  } catch (Exception e) { return ""; }
  ```

- **Response time (ms):**
  ```java
  var t = requestResponse.timingData();
  if (t.isEmpty()) return "";
  return String.valueOf(t.get().timeBetweenRequestSentAndStartOfResponse().toMillis());
  ```

Return `String.valueOf(...)` for numerics — Burp sorts columns lexicographically by default unless the value parses cleanly as a number.

---

## CUSTOM_ACTION

**Where:** Repeater, Intruder.
**Locations:** `REPEATER`, `INTRUDER`.
**Return type:** `void`. Side effects only.
**Objects in scope:**

| Variable | Type | Notes |
|---|---|---|
| `requestResponse` | `HttpRequestResponse` | The current request/response in the active editor. |
| `httpEditor` (Repeater) / `wsEditor` | editor handle | Has `.requestPane().set(byte[])` and `.responsePane().set(byte[])` to mutate the editor in place. |
| `api()` | `MontoyaApi` | Use `api().http().sendRequest(...)` to send. |
| `logging()` | `Logging` | `logging().logToOutput(...)` and `.logToError(...)` |
| `utilities()` | `Utilities` | Method form here. |

**Skeleton: retry until status code changes**

```java
var maxAttempts = 20;
var boring = requestResponse.response().statusCode();
var version = requestResponse.request().httpVersion().equals("HTTP/2") ? HttpMode.HTTP_2 : HttpMode.HTTP_1;

for (int i = 0; i < maxAttempts; i++) {
    var attack = api().http().sendRequest(requestResponse.request(), version);
    var status = attack.response().statusCode();
    logging().logToOutput("attempt " + i + " -> " + status);
    if (status != boring) {
        httpEditor.responsePane().set(attack.response().toByteArray());
        return;
    }
}
```

Custom actions are the right place for "do something useful with the current request": race-condition probes, batch sends, request signing, response decoding, etc. They are **not** the right place for vulnerability scanning — use a scan check.

---

## MATCH_AND_REPLACE_REQUEST

**Where:** Proxy.
**Location:** `PROXY_HTTP_HISTORY`.
**Return type:** `HttpRequest`. Return the modified request, or return the original unchanged to pass through.
**Objects in scope:**

| Variable | Type |
|---|---|
| `requestResponse` | The pair the proxy is currently processing |
| `utilities` | bare field, not method |
| `logging` | bare field |

**Skeleton: add a signature header derived from the body**

```java
var digest = utilities.cryptoUtils().generateDigest(
    requestResponse.request().body(),
    DigestAlgorithm.SHA_256
);
var signature = HexFormat.of().formatHex(digest.getBytes());
return requestResponse.request().withAddedHeader("Content-Sha256", signature);
```

**Skeleton: substitute a placeholder with random data**

```java
if (!requestResponse.request().contains("randomplz", true)) {
    return requestResponse.request();
}
var rewritten = requestResponse.request().toString()
    .replace("randomplz", utilities.randomUtils().randomString(8));
return HttpRequest.httpRequest(requestResponse.httpService(), rewritten);
```

**Always return an `HttpRequest`.** Returning `null` drops the request — almost never what you want. If the rule shouldn't apply, `return requestResponse.request();` (the original).

---

## MATCH_AND_REPLACE_RESPONSE

**Same as above but:**
- `function: MATCH_AND_REPLACE_RESPONSE`
- Return type is `HttpResponse`
- Default pass-through is `return requestResponse.response();`

**Skeleton: strip a security header to test how the browser behaves without it**

```java
var res = requestResponse.response();
if (res == null) return null;
return res.withRemovedHeader("Content-Security-Policy")
          .withRemovedHeader("X-Frame-Options");
```
