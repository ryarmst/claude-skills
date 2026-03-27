---
name: apk-decompile
description: >
  Decompiles Android APK files using jadx, spawning an async subagent so decompilation
  runs in the background while the main session stays free for other work. Use this skill
  whenever a user mentions decompiling, reverse engineering, or analyzing an APK; wants
  to inspect Android app source code, manifest, or resources; or asks to set up for
  mobile security testing or bug bounty recon on an Android target.
compatibility:
  tools: [Bash, Read, Write, Agent]
  dependencies: [jadx]
---

# APK Decompile Skill

This skill decompiles an APK with `jadx` via an async background subagent, then
surfaces the output for triage. The main session stays unblocked during decompilation.

## Workflow

### Step 1 — Preflight

Before spawning the subagent, verify the environment:
```bash
which jadx || (echo "jadx not found" && exit 1)
jadx --version
```

If `jadx` is missing, tell the user and suggest install options:
- **Linux:** download the release jar from https://github.com/skylot/jadx/releases and add to PATH, or `apt install jadx` on Debian/Ubuntu
- **All platforms:** the `jadx-gui` bundle includes the CLI

Verify the APK exists and is a valid ZIP/APK:
```bash
file <apk_path>
unzip -t <apk_path> | head -5
```

### Step 2 — Spawn the decompile subagent

Delegate to the `jadx-decompiler` subagent (defined in `.claude/agents/jadx-decompiler.md`).
Pass it:
- Absolute path to the APK
- Absolute output directory path (default: `<apk_name>_decompiled/` next to the APK)
- Any flags the user requested (see Flag Reference below)

The subagent handles the full jadx invocation and produces a structured summary.
Background it with Ctrl+B so the user can keep working. When it completes, the main
session receives the summary automatically.

**Invocation template:**
```
Decompile the APK at <abs_apk_path> to <abs_output_dir>.
Use flags: <flags>.
Return the structured summary as specified in your instructions.
```

### Step 3 — Post-decompile triage (on subagent return)

Once the subagent reports back, perform these quick-win checks in the main session:

1. **Manifest review** — read `<output_dir>/resources/AndroidManifest.xml`
   - Exported activities, services, receivers, providers
   - `android:debuggable="true"` or `android:allowBackup="true"`
   - Dangerous permissions
   - Custom permissions with `protectionLevel="normal"`

2. **Surface-level secret scan** — run from the sources root:
```bash
   grep -rn --include="*.java" \
     -e "api_key\|apikey\|secret\|password\|token\|private_key\|AWS\|Bearer" \
     <output_dir>/sources/ | head -60
```

3. **Network config** — check for cleartext traffic:
```bash
   find <output_dir>/resources -name "network_security_config.xml" | xargs cat 2>/dev/null
   grep -rn "cleartextTrafficPermitted\|usesCleartextTraffic" <output_dir>/resources/
```

4. **Crypto red flags** — weak algorithms:
```bash
   grep -rn --include="*.java" \
     "\"DES\"\|\"RC4\"\|\"MD5\"\|ECB\|\"AES/ECB\"\|SecureRandom.*seed" \
     <output_dir>/sources/ | head -30
```

5. **WebView checks**:
```bash
   grep -rn --include="*.java" \
     "setJavaScriptEnabled\|addJavascriptInterface\|setAllowFileAccess\|loadUrl" \
     <output_dir>/sources/ | head -30
```

Report findings using the output format below.

## Flag Reference

Choose flags based on the user's goal:

| Goal | Recommended flags |
|---|---|
| Standard analysis (default) | `--deobf --show-bad-code` |
| Max readability | `--deobf --deobf-min 3 --show-bad-code --no-imports` |
| Resources only (no source) | `--no-src` |
| Source only (skip resources) | `--no-res` |
| Kotlin app | `--deobf --show-bad-code` (jadx handles Kotlin natively) |
| Heavily obfuscated | `--deobf --deobf-min 3 --deobf-max 50 --show-bad-code` |
| Fast/CI mode | `--no-debug-info --no-comments` |

Always pass `--log-level ERROR` to suppress noise unless the user is debugging jadx itself.

## Output Format

After triage, report using this structure:
```
## APK Decompile Summary — <app_name>

**Package:** <package_name>
**Output:** <output_dir>
**jadx flags:** <flags used>

### Quick Stats
- Java/Kotlin source files: N
- Resources: N
- Native libs (.so): N

### Manifest Findings
<bullet list — exported components, dangerous flags, permissions of note>

### Potential Secrets / Hardcoded Credentials
<grep hits or "none found">

### Crypto / Crypto-Adjacent Issues
<findings or "none found">

### WebView Surface
<findings or "none found">

### Network Config
<cleartext permitted? custom CAs? pinning config?>

### Recommended Next Steps
<top 3 follow-up actions based on findings>
```

## Edge Cases

- **Multi-APK / APKS bundles:** jadx can decompile `.apks` split bundles directly —
  pass the bundle path unchanged.
- **Large APKs (>100MB):** add `--threads-count 4` (or match CPU count) and warn the
  user decompilation may take several minutes — async subagent is especially valuable here.
- **jadx failures / bad code:** `--show-bad-code` ensures partial output is still
  written; check `<output_dir>/classes/` for raw `.dex` if jadx gives up on a class.
- **ProGuard/R8 obfuscation:** deobf flags help but won't fully recover names — flag
  to the user that manual smali review or Ghidra may be needed for obfuscated classes.
- **AAB (Android App Bundle):** jadx does not support `.aab` directly. Tell the user
  to first build a universal APK with `bundletool` or obtain the APK from the device.

## References

- jadx GitHub & releases: https://github.com/skylot/jadx
- Android Manifest reference: https://developer.android.com/guide/topics/manifest/manifest-intro
- For native lib analysis after decompile, see `ghidra-assist` skill (if available)
