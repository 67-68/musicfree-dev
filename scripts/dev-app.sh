#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/../app"
export npm_config_cache="${npm_config_cache:-/tmp/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/tmp/electron-cache}"
export electron_config_cache="${ELECTRON_CACHE}"

# 启动前确保 electron 二进制可用（Node 26 / pnpm 布局下 postinstall 可能没跑完整）
"$HERE/repair-electron.sh"

cd "$APP"
echo "==> MusicFreeDesktop dev (upstream dev branch)"
npm run start
