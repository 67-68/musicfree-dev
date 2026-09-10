#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/../app"
cd "$APP"
export npm_config_cache="${npm_config_cache:-/tmp/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/tmp/electron-cache}"
export electron_config_cache="${ELECTRON_CACHE}"
echo "==> MusicFreeDesktop dev (upstream dev branch)"
npm run start
