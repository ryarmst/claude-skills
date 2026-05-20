# Custom Column Bambda Templates

Each template lives in `templates/` and is ready to import into the Bambda library. Custom columns run automatically — there is no gate global.

| Template | Location | Returns | When to use |
|----------|----------|---------|-------------|
| TEMPLATE - Response header value | `LOGGER` | `String` | Display any response header. Tunable via `bg.column-target-header` (default: `Server`). Start here — matches the official PortSwigger pattern. |
| TEMPLATE - Request parameter count | `LOGGER` | `int` | Count all request parameters per row. Sorts numerically — sort descending to find complex endpoints first. |
| TEMPLATE - Regex extraction from response body | `LOGGER` | `String` | First regex match (or capture group) from the response body. Default pattern finds JWTs. Tune via `bg.column-regex-pattern` and `bg.column-regex-maxlen`. |

## Key differences from CUSTOM_ACTION

| | CUSTOM_COLUMN | CUSTOM_ACTION |
|---|---|---|
| Trigger | Automatic, every visible row | Manual button click |
| Return value | `String`, `int`, or `boolean` | `void` (side effects only) |
| `api()` | ✗ Not available | ✓ Available |
| `logging()` | ✗ Not available | ✓ Available |
| `utilities` | Bare field: `utilities.base64Utils()` | Method: `utilities().base64Utils()` |
| Performance | Critical — runs per-row, per-update | Low concern — runs once on click |
| Burp Globals gate | Not used | Required (`bg.bambda-action`) |
| Persistence | Avoid — see SKILL.md §8 | Use **burp-bambda-persistence** when needed |

## Supported locations

| `location:` | Table |
|---|---|
| `LOGGER` | Logger (recommended default — all tools) |
| `PROXY_HTTP_HISTORY` | Proxy HTTP history only |
| `PROXY_WS_HISTORY` | Proxy WebSockets history only |

## Adding to Burp

1. Extensions → Bambda library → Import the `.bambda` file.
2. In the target table: options menu → **Add custom column** → Load → select the script.
3. Enter a **Column header** name (this is what appears in the table, not the YAML `name:`).
4. Click **Apply & close**.
