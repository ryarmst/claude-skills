# Request Templates

Use for the `content` parameter of `send_http1_request` and `create_repeater_tab`.

`\r\n` in these templates = actual CR+LF bytes (0x0D 0x0A). If Burp Repeater displays `\r\n` as visible text, the encoding is wrong — see SKILL.md §2.

`<N>` = UTF-8 byte count of the body as it will be sent. For ASCII bodies, byte count = character count.

---

## GET

```
GET /path HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Accept: application/json
Connection: close

```

(Drop `Authorization` if unauthenticated.)

---

## POST — JSON body

```
POST /path HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Content-Type: application/json
Accept: application/json
Content-Length: <N>
Connection: close

{"key":"value"}
```

---

## POST — form-encoded with CSRF

```
POST /path HTTP/1.1
Host: hostname:port
Content-Type: application/x-www-form-urlencoded
Accept: text/html,application/xhtml+xml
Content-Length: <N>
Connection: close
Cookie: session=VALUE

_token=CSRF_TOKEN&field=value
```

---

## POST — no body

```
POST /path/ID/action HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Content-Type: application/json
Content-Length: 0
Connection: close

```

---

## PUT / DELETE

```
PUT /path/ID HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Content-Type: application/json
Content-Length: <N>
Connection: close

{"field":"value"}
```

```
DELETE /path/ID HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Connection: close

```
