# Bambda Templates

Each template lives in `templates/` and is ready to import into the Bambda library. All require `bg.bambda-action=true` to run.

| Template | Function | Location | When to use |
|----------|----------|----------|-------------|
| TEMPLATE - Retry until status changes | `CUSTOM_ACTION` | `REPEATER` | Sequential retry of the current request until a different status code appears. Use for race-condition probing of single endpoints, or sanity-checking flaky responses. For true single-packet races, use the batch-send template instead. |
| TEMPLATE - Extract token and patch request | `CUSTOM_ACTION` | `REPEATER` | Pull a CSRF token (or any regex-matched value) out of the response body and substitute it for a placeholder string in the request editor. Customize via `bg.bambda-action-token-pattern` and `bg.bambda-action-placeholder`. |
| TEMPLATE - Batch send variants in parallel | `CUSTOM_ACTION` | `REPEATER` | Send a list of request variants in parallel using HTTP/2 single-packet attack or HTTP/1 last-byte sync, log each result, and forward all responses to the Organizer for comparison. The default variants exercise common access-control header tricks (X-Forwarded-For, X-Original-URL, Cookie removal). |

## Required Burp Globals

All three templates use the master gate `bambda-action`. Additional globals per template:

- **Retry**: `bambda-action-max-attempts` (int, default 20)
- **Extract token**: `bambda-action-token-pattern` (string, default matches CSRF tokens), `bambda-action-placeholder` (string, default `FUZZ_TOKEN`)
- **Batch send**: no additional globals; modify the `variants` list directly in the script

## Importing

1. In Burp: Extensions → Bambda library → Import.
2. Select the `.bambda` file or the whole `templates/` folder.
3. Open Repeater → Custom actions → Load to add the action to the side panel.
4. Set the relevant `bg.*` globals via the Burp Globals tab before clicking the action button.
