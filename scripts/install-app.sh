#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/../app"
cd "$APP"
export npm_config_cache="${npm_config_cache:-/tmp/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/tmp/electron-cache}"
export electron_config_cache="${ELECTRON_CACHE}"
mkdir -p "$ELECTRON_CACHE"
echo "==> npm install"
npm install --no-audit --no-fund

# electron postinstall may not write path.txt under newer Node; repair if needed.
if [ ! -f node_modules/electron/path.txt ] || ! npx --no-install electron --version >/dev/null 2>&1; then
  echo "==> Repairing electron binary"
  ZIP="$(find "$ELECTRON_CACHE" -name 'electron-v*-darwin-arm64.zip' | head -1)"
  if [ -z "$ZIP" ]; then
    echo "electron zip not cached; run: node node_modules/electron/install.js" >&2
    exit 1
  fi
  rm -rf node_modules/electron/dist
  mkdir -p node_modules/electron/dist
  ditto -x -k "$ZIP" node_modules/electron/dist
  printf 'Electron.app/Contents/MacOS/Electron' > node_modules/electron/path.txt
fi
echo "==> electron $(npx --no-install electron --version 2>/dev/null || true)"
