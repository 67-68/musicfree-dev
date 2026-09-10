#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR_NAME="${1:-template}"
PLUGIN="$HERE/../plugins/$PLUGIN_DIR_NAME"
if [ ! -d "$PLUGIN" ]; then
  echo "plugin dir not found: $PLUGIN" >&2
  exit 1
fi
cd "$PLUGIN"
export npm_config_cache="${npm_config_cache:-/tmp/npm-cache}"
echo "==> Building plugin: $PLUGIN_DIR_NAME"
npm run build
echo "==> Output: $PLUGIN/dist/plugin.js"
