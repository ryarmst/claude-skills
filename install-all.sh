# install-all.sh
#!/bin/bash
set -e

MARKETPLACE="ryarmst"
PLUGINS=(
  apk-decompile
  markdown-document
  jadx-decompiler
)

for plugin in "${PLUGINS[@]}"; do
  echo "Installing $plugin..."
  claude plugin install "$plugin@$MARKETPLACE"
done

echo "Done."
