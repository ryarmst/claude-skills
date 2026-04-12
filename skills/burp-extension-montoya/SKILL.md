---
name: burp-extension-montoya
description: >-
  Build Burp Suite extensions in Java using the Montoya API. Use when creating,
  modifying, or debugging Burp extensions, or when the user mentions Burp Suite,
  Montoya API, BurpExtension, HttpHandler, scan checks, bambdas, or Burp plugin
  development.
---

# Burp Suite Extension Development (Montoya API)

API Javadoc: https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/MontoyaApi.html

## Project Setup

**Build:** Gradle. Java 17+ required.

```groovy
plugins { id 'java' }
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
repositories { mavenCentral() }
dependencies {
    compileOnly 'net.portswigger.burp.extensions:montoya-api:2024.12'
}
```

- Montoya API is provided by Burp at runtime -- always `compileOnly`.
- Output a single JAR with extension classes only. Do NOT shade Montoya.
- If shading other libs, use `duplicatesStrategy(DuplicatesStrategy.EXCLUDE)`.

**Discovery:** Create `src/main/resources/META-INF/services/burp.api.montoya.BurpExtension` containing the fully-qualified entry point class name (one line).

**Build & load:**

```bash
./gradlew jar
# Output in build/libs/ -> load via Burp Extensions -> Installed -> Add
```

## Entry Point

```java
import burp.api.montoya.BurpExtension;
import burp.api.montoya.MontoyaApi;

public class MyExtension implements BurpExtension {
    @Override
    public void initialize(MontoyaApi api) {
        api.extension().setName("My Extension");
        // Register handlers, UI, etc. here.
        // Handlers are only enabled after initialize() completes.
    }
}
```

## MontoyaApi Top-Level Accessors

| Accessor | Purpose |
|----------|---------|
| `api.extension()` | Set name, register unload handler |
| `api.http()` | Register `HttpHandler`, send requests |
| `api.proxy()` | Register proxy request/response handlers |
| `api.scanner()` | Register `ActiveScanCheck` / `PassiveScanCheck` |
| `api.userInterface()` | Register suite tabs, context menus, editors, themes |
| `api.persistence()` | `extensionData()` (per-project) and `preferences()` (cross-project) |
| `api.logging()` | `logToOutput()`, `logToError()`, `raiseDebugEvent()`, `raiseErrorEvent()`, `raiseInfoEvent()` |
| `api.scope()` | Check/modify suite-wide target scope |
| `api.siteMap()` | Access the site map |
| `api.collaborator()` | Burp Collaborator (Pro only) |
| `api.utilities()` | Crypto, encoding, compression helpers |

## HTTP Request/Response Handling

Implement `HttpHandler` and register with `api.http().registerHttpHandler(handler)`.

```java
import burp.api.montoya.http.handler.*;
import burp.api.montoya.http.message.requests.HttpRequest;

public class MyHandler implements HttpHandler {
    @Override
    public RequestToBeSentAction handleHttpRequestToBeSent(HttpRequestToBeSent event) {
        // event extends HttpRequest -- use directly for headers/body/url
        String toolName = event.toolSource().toolType().toolName();
        // "Proxy", "Repeater", "Intruder", "Scanner", "Extensions"

        // Pass through unmodified:
        return RequestToBeSentAction.continueWith(event);

        // Or modify:
        // HttpRequest modified = event.withRemovedHeader("X-Old").withAddedHeader("X-New", "val");
        // return RequestToBeSentAction.continueWith(modified);
    }

    @Override
    public ResponseReceivedAction handleHttpResponseReceived(HttpResponseReceived event) {
        return ResponseReceivedAction.continueWith(event);
    }
}
```

### Key HttpRequest Methods

- `event.toString()` -- full request as string (first line + headers + body)
- `event.httpService()` -- host/port/protocol of the target
- `event.url()`, `event.path()`, `event.method()`
- `event.headers()` -- `List<HttpHeader>`
- `event.header("Name")` -- single `HttpHeader` or null
- `event.hasHeader("Name")` -- boolean
- `event.body()` -- `ByteArray`; use `.getBytes()` for raw `byte[]`
- `event.bodyToString()` -- body as `String`
- `event.isInScope()` -- whether URL is in Burp's target scope
- `event.toolSource().toolType().toolName()` -- originating tool name

### Modifying Requests

```java
HttpRequest modified = event
    .withRemovedHeader("Authorization")
    .withAddedHeader("Authorization", "Bearer " + token);

// Reconstruct from raw string (preserves HTTP service):
HttpRequest rebuilt = HttpRequest.httpRequest(event.httpService(), modifiedString);
// Fix Content-Length after body changes:
if (rebuilt.body().length() > 0)
    rebuilt = rebuilt.withBody(rebuilt.bodyToString());
```

### Fail-Open Pattern

Always catch exceptions in handlers and return the original request/response:

```java
try {
    // modification logic
    return RequestToBeSentAction.continueWith(modified);
} catch (Exception ex) {
    log.logToError("Handler error: " + ex.getMessage());
    return RequestToBeSentAction.continueWith(event);
}
```

## Persistence

Two storage tiers:

| Store | Scope | Access |
|-------|-------|--------|
| `api.persistence().extensionData()` | Per-project (lost without project file) | `PersistedObject` -- strings, booleans, string lists, child objects |
| `api.persistence().preferences()` | Cross-project (Java prefs, survives restarts) | `Preferences` -- primitives: `getString`/`setString`, `getBoolean`/`setBoolean`, `getInteger`/`setInteger` |

### PersistedObject (extensionData)

```java
PersistedObject data = api.persistence().extensionData();

// String lists (good for multi-field records):
PersistedList<String> list = PersistedList.persistedStringList();
list.add("value1");
list.add("value2");
data.setStringList("myKey", list);

// Reading:
PersistedList<String> loaded = data.getStringList("myKey");

// Enumerating keys:
Set<String> keys = data.stringListKeys();  // also: stringKeys(), booleanKeys()

// Deleting:
data.deleteStringList("myKey");
```

### Preferences

```java
Preferences prefs = api.persistence().preferences();
prefs.setBoolean("featureEnabled", true);
Boolean val = prefs.getBoolean("featureEnabled");  // returns null if unset
prefs.setString("apiKey", "secret");
```

### Unload Handler

Always save state in the unload handler:

```java
api.extension().registerUnloadingHandler(() -> {
    // Persist data here
    log.logToOutput("Extension unloaded.");
});
```

## UI: Suite Tabs

```java
JPanel panel = new JPanel();
// Build Swing UI...
api.userInterface().registerSuiteTab("Tab Name", panel);
```

- Use `api.userInterface().currentTheme()` to check `Theme.LIGHT` vs `Theme.DARK` for border colors.
- Use `api.userInterface().swingUtils().suiteFrame()` to get the parent `Frame` for dialogs.
- Use `api.userInterface().applyThemeToComponent(component)` to match Burp styling.

## UI: Context Menus

```java
import burp.api.montoya.ui.contextmenu.*;

public class MyContextMenu implements ContextMenuItemsProvider {
    @Override
    public List<Component> provideMenuItems(ContextMenuEvent event) {
        // Only show for message editor requests:
        if (!event.messageEditorRequestResponse().isPresent()
                || !event.isFrom(InvocationType.MESSAGE_EDITOR_REQUEST))
            return null;

        MessageEditorHttpRequestResponse editor =
            event.messageEditorRequestResponse().get();

        JMenuItem item = new JMenuItem("My Action");
        item.addActionListener(e -> {
            // Read caret position or selection:
            int caret = editor.caretPosition();
            // editor.selectionOffsets() -> Optional<Range>

            // Modify the request in the editor:
            HttpRequest original = editor.requestResponse().request();
            HttpRequest modified = HttpRequest.httpRequest(
                original.httpService(), modifiedString);
            editor.setRequest(modified);
        });
        return List.of(item);
    }
}

// Register:
api.userInterface().registerContextMenuItemsProvider(new MyContextMenu());
```

Return `null` (not empty list) when no items should be shown.

## Scanner: Custom Scan Checks

`ScanCheck` is deprecated. Use `ActiveScanCheck` or `PassiveScanCheck`:

```java
import burp.api.montoya.scanner.scancheck.PassiveScanCheck;
import burp.api.montoya.scanner.audit.issues.AuditIssue;

public class MyPassiveCheck implements PassiveScanCheck {
    @Override
    public AuditResult passiveAudit(HttpRequestResponse baseRequestResponse) {
        // Analyze response, return AuditResult with issues or empty
    }
}
// Register: api.scanner().registerScanCheck(new MyPassiveCheck());
```

## Thread Safety

Burp calls `HttpHandler` methods from multiple threads concurrently.

- Use `ConcurrentHashMap` for shared state, NOT `HashMap`.
- Use `AtomicBoolean` / `AtomicReference` for toggle flags and settings.
- Use `SwingUtilities.invokeLater()` for any table model / UI updates from handler threads.
- Never hold locks during HTTP processing -- deadlock risk with Burp internals.

## Swing UI Conventions

- `JTable` with `AbstractTableModel` for data grids. Prefer custom model over `DefaultTableModel` for type safety.
- `putClientProperty("terminateEditOnFocusLost", Boolean.TRUE)` on JTable to commit edits on focus loss.
- Use `table.convertRowIndexToModel(viewRow)` when using `TableRowSorter` or sorting.
- For search/filter, use `TableRowSorter<MyModel>` with `RowFilter.regexFilter(...)`.
- For dialogs, parent to `api.userInterface().swingUtils().suiteFrame()`.
- Check `api.userInterface().currentTheme()` for `Theme.LIGHT` vs `Theme.DARK` when picking border/line colors.

## Common Gotchas

1. **`DefaultCellEditor`** is in `javax.swing`, NOT `javax.swing.table`. The wildcard `javax.swing.*` covers it, but an explicit import from `javax.swing.table.DefaultCellEditor` will fail to compile.
2. **`TableCellEditor`** IS in `javax.swing.table`. Needs explicit import when `javax.swing.*` wildcard is used (wildcards do not cover sub-packages).
3. **`setMaxWidth` on columns** prevents user resizing. Use `setMinWidth` + `setPreferredWidth` instead.
4. **Binary bodies:** Always sign/hash raw `byte[]` from `body().getBytes()`. Never convert to `String` first.
5. **Content-Length:** After modifying a request body via string reconstruction, call `withBody(bodyToString())` to fix the Content-Length header.
6. **Proxy handler scope:** For Proxy tool, check `event.isInScope()` before modifying -- users expect non-scope traffic to pass untouched.
7. **Unload cleanup:** Always clear any JVM-wide side effects (system properties, thread pools, registered shutdownhooks) in the unload handler.
8. **Secrets in logs:** Never log sensitive variable values. Log lengths or masked previews at most.
9. **`provideMenuItems` return type:** Return `null` (not empty list) when no context menu items should appear.

## Logging

```java
Logging log = api.logging();
log.logToOutput("Info message");     // Extensions -> Output tab
log.logToError("Error details");     // Extensions -> Errors tab
log.raiseInfoEvent("User-visible");  // Burp event log (info level)
log.raiseErrorEvent("Problem");      // Burp event log (error level)
log.raiseDebugEvent("Debug info");   // Burp event log (debug level)
```

## Quick Reference: Extension Skeleton

```java
package myextension;

import burp.api.montoya.BurpExtension;
import burp.api.montoya.MontoyaApi;

public class MyExtension implements BurpExtension {
    @Override
    public void initialize(MontoyaApi api) {
        api.extension().setName("My Extension");
        var log = api.logging();
        var data = api.persistence().extensionData();
        var prefs = api.persistence().preferences();

        // UI
        // var tab = new MyTab(api, ...);
        // api.userInterface().registerSuiteTab("My Tab", tab);

        // HTTP handling
        // api.http().registerHttpHandler(new MyHandler(...));

        // Context menu
        // api.userInterface().registerContextMenuItemsProvider(new MyMenu(...));

        // Scan checks
        // api.scanner().registerScanCheck(new MyCheck(...));

        log.logToOutput("Extension loaded.");

        api.extension().registerUnloadingHandler(() -> {
            // Save state
            log.logToOutput("Extension unloaded.");
        });
    }
}
```

`META-INF/services/burp.api.montoya.BurpExtension`:
```
myextension.MyExtension
```
