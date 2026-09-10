#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/../app"
cd "$APP"
export npm_config_cache="${npm_config_cache:-/tmp/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/tmp/electron-cache}"
export electron_config_cache="${ELECTRON_CACHE}"
mkdir -p "$ELECTRON_CACHE"

# 优先使用 pnpm（本仓库 app 使用 pnpm-lock.yaml / node_modules/.pnpm 布局）；
# 没有 pnpm 时退回 npm。
if [ -f "$APP/pnpm-lock.yaml" ] && command -v pnpm >/dev/null 2>&1; then
    echo "==> pnpm install"
    pnpm install
else
    echo "==> npm install"
    npm install --no-audit --no-fund
fi

# electron postinstall 在新版 Node / pnpm 下可能没写出 dist/ 与 path.txt，
# 统一交给 repair-electron.sh（兼容 npm 扁平与 pnpm 嵌套布局）。
"$HERE/repair-electron.sh"
