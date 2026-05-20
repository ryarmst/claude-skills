# Custom Column Bambda Templates

| Template | Location | Returns | When to use |
|----------|----------|---------|-------------|
| TEMPLATE - Response header value | `LOGGER` | `String` | Display any response header value in the table. Configurable via `bg.column-target-header` (default: `Server`). Start here — it's the official PortSwigger example pattern. |
| TEMPLATE - Request parameter count | `LOGGER` | `int` | Count all request parameters per row. Sorts numerically, making it ideal for attack-surface triage: sort descending to find the most complex endpoints first. |
| TEMPLATE - Regex extraction from response body | `LOGGER` | `String` | Extract the first regex match (or first capture group) from the response body. Default pattern finds JWTs. Configure via `bg.column-regex-pattern` and `bg.column-regex-maxlen`. |

## Key differences from CUSTOM_ACTION

| | CUSTOM_COLUMN | CUSTOM_ACTION |
|---|---|---|
| Trigger | Automatic, every visible row | Manual button click |
| Return value | `String`, `int`, or `boolean` | `void` (side effects only) |
| `api()` | ✗ Not available | ✓ Available |
| `logging()` | ✗ Not available | ✓ Available |
| `utilities` | Bare field: `utilities.base64Utils()` | Method: `utilities().base64Utils()` |
| `selection` | ✗ Not available | ✓ Available |
| Performance | Critical — runs per-row, per-update | Low concern — runs once on click |
| Burp Globals gate | Not used (column runs automatically) | Required (`bg.bambda-action`) |

## Supported locations

`LOGGER` is recommended as the default — it captures traffic from all tools (Proxy, Repeater, Scanner, etc.). Use `HTTP_HISTORY` or `WEBSOCKETS_HISTORY` if you want the column only in that specific table.

## Adding to Burp

1. Extensions → Bambda library → Import the `.bambda` file.
2. In the target table (Logger / HTTP history): options menu → **Add custom column** → Load → select the script.
3. Enter a column header name.
4. Click **Apply & close**.
