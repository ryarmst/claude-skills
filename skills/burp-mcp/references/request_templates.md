# Request Templates

Use for the `content` parameter of `send_http1_request` and `create_repeater_tab`.

Line separators must be real CR+LF bytes — not the four-character escape `\r\n`. See SKILL.md §2.

`<N>` = UTF-8 byte count of the body as sent. For ASCII-only bodies, byte count = character count.

---

## GET

```
GET /path HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Accept: application/json
Connection: close

```

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

## POST — form-encoded with session + CSRF

```
POST /path HTTP/1.1
Host: hostname:port
Content-Type: application/x-www-form-urlencoded
Content-Length: <N>
Connection: close
Cookie: session=VALUE

csrf_token=TOKEN&field=value
```

---

## POST — no body

```
POST /path HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Connection: close

```

---

## PUT

```
PUT /path/ID HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Content-Type: application/json
Content-Length: <N>
Connection: close

{"field":"value"}
```

---

## DELETE

```
DELETE /path/ID HTTP/1.1
Host: hostname:port
Authorization: Bearer TOKEN
Connection: close

```
