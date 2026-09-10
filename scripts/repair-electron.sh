#!/usr/bin/env bash
# ============================================================================
# repair-electron.sh — 修复 Electron 二进制缺失（Node 26 / pnpm 布局）
#
# 背景：新版 Node 下 electron 的 postinstall 可能没有正确写出
#       dist/ 与 path.txt；pnpm 还会把包放在 node_modules/.pnpm/...。
#       本脚本兼容 npm 扁平布局与 pnpm 嵌套布局，幂等。
#
# 用法：
#   ./scripts/repair-electron.sh
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/../app"
export ELECTRON_CACHE="${ELECTRON_CACHE:-/tmp/electron-cache}"
export electron_config_cache="${ELECTRON_CACHE}"
mkdir -p "$ELECTRON_CACHE"

if [ ! -d "$APP" ]; then
    echo "app dir not found: $APP" >&2
    exit 1
fi

resolve_electron_dir() {
    local resolved=""
    resolved="$(cd "$APP" && node -e "try{console.log(require('path').dirname(require.resolve('electron/package.json')))}catch(e){}" 2>/dev/null || true)"
    if [ -n "$resolved" ] && [ -d "$resolved" ]; then
        printf '%s\n' "$resolved"
        return 0
    fi

    local candidate
    for candidate in \
        "$APP/node_modules/electron" \
        "$APP"/node_modules/.pnpm/electron@*/node_modules/electron; do
        if [ -d "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

ELECTRON_DIR="$(resolve_electron_dir || true)"
if [ -z "$ELECTRON_DIR" ]; then
    echo "electron package not found; run ./scripts/install-app.sh first" >&2
    exit 1
fi

electron_ok() {
    [ -f "$ELECTRON_DIR/path.txt" ] &&
        [ -f "$ELECTRON_DIR/dist/version" ] &&
        [ -x "$ELECTRON_DIR/dist/Electron.app/Contents/MacOS/Electron" ] 2>/dev/null
}

if electron_ok; then
    echo "==> electron OK ($(cat "$ELECTRON_DIR/dist/version" 2>/dev/null || echo unknown))"
    exit 0
fi

echo "==> Repairing electron binary: $ELECTRON_DIR"

find_zip() {
    find "$ELECTRON_CACHE" -type f \
        \( -name 'electron-v*-darwin-arm64.zip' -o -name 'electron-v*.zip' \) \
        2>/dev/null | head -1
}

ZIP="$(find_zip)"
if [ -z "$ZIP" ]; then
    echo "==> Cache miss, running electron install.js to download..."
    (cd "$ELECTRON_DIR" && node install.js) || true
    ZIP="$(find_zip)"
fi

if [ -z "$ZIP" ]; then
    echo "electron zip not cached and download failed." >&2
    echo "Try: cd $ELECTRON_DIR && node install.js" >&2
    exit 1
fi

echo "==> Extracting $(basename "$ZIP")"
rm -rf "$ELECTRON_DIR/dist"
mkdir -p "$ELECTRON_DIR/dist"
if command -v ditto >/dev/null 2>&1; then
    ditto -x -k "$ZIP" "$ELECTRON_DIR/dist"
else
    unzip -q "$ZIP" -d "$ELECTRON_DIR/dist"
fi
printf 'Electron.app/Contents/MacOS/Electron' > "$ELECTRON_DIR/path.txt"

if ! electron_ok; then
    echo "electron repair failed: $ELECTRON_DIR" >&2
    exit 1
fi

echo "==> electron OK ($(cat "$ELECTRON_DIR/dist/version" 2>/dev/null || echo unknown))"
