---
name: burp-mcp
description: Send HTTP requests and manage Burp Suite via the Burp MCP tools. Use whenever Burp Suite MCP tools are available and you need to issue HTTP requests during security testing — including sending proof-of-concept requests, creating Repeater tabs, reading proxy history, or managing scanner issues. This skill takes priority over curl, wget, or any other HTTP client when Burp MCP tools are in scope.
---

# Burp MCP

## 1. Tool priority — always use Burp MCP over curl

When `mcp__burpsuite__*` tools are available, **never use `curl`, `wget`, or any other HTTP client**. Every request must go through Burp to appear in proxy history and remain reproducible.

| Tool | When to use |
|---|---|
| `mcp__burpsuite__send_http1_request` | Need the response immediately to decide the next step |
| `mcp__burpsuite__create_repeater_tab` | Confirmed finding — leave a reproducible PoC tab for the user |

Create a Repeater tab for every confirmed finding. Use `send_http1_request` for exploratory requests.

---

## 2. CRLF encoding — the most common failure

The `content` parameter for both tools is an **already-decoded string**: the JSON parsing layer has already run before the value reaches the MCP tool. This means:

- `\r\n` written as **JSON escape sequences** → actual CR+LF bytes ✅
- `\r\n` written as **four literal characters** → Repeater shows `\r\n` as visible text; request is broken ❌

**Never concatenate the request as a single escaped string.** Write the content with real line breaks. Each header must be on its own line, separated by actual CR+LF. There must be a blank line (two CRLFs) between the last header and the body.

If Burp Repeater shows `\r\n` as visible text, the content was double-escaped.

---

## 3. Request construction rules

- **Host**: always include; match target hostname and port.
- **Content-Type**: required whenever there is a body.
- **Content-Length**: include when there is a body; value is the UTF-8 byte count of the body exactly as sent.
- **Connection: close**: include on all requests.
- **Accept: application/json**: include when the target returns JSON, to get JSON (not HTML) on error responses.

See `references/request_templates.md` for ready-to-use templates.

---

## 4. Workflow

1. Send the PoC with `send_http1_request`; examine status, headers, body.
2. If confirmed, create a Repeater tab with `create_repeater_tab`. Tab name: `FIND-Na — short description` (e.g. `FIND-2a — Create SSRF Webhook`). Multi-step chains get sequential tabs: `FIND-2a`, `FIND-2b`, etc.
3. For blind/OOB issues: use `mcp__burpsuite__generate_collaborator_payload` for the payload, then `mcp__burpsuite__get_collaborator_interactions` to check callbacks.
4. To find a baseline request to modify: `mcp__burpsuite__get_proxy_http_history` or `mcp__burpsuite__get_proxy_http_history_regex`.

---

## 5. Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Literal `\r\n` in content | Repeater shows `\r\n` as text | Use actual CR+LF (see §2) |
| Missing blank line after headers | Body treated as headers; server returns 400 | Two CRLFs after the last header |
| Wrong Content-Length | Request truncated or server returns 400 | Recalculate from exact body byte count |
| Using curl instead of MCP | Request absent from proxy history | Use `send_http1_request` |
| Tab name too generic | Can't locate the tab later | Follow `FIND-Na — description` convention |
