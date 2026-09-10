#!/usr/bin/env bash
# ============================================================================
# music_install.sh — MusicFree song-analysis 环境安装脚本
#
# 幂等：可以反复执行。负责安装：
#   1. analysis/venv + Python 依赖 (requirements.txt)
#   2. Sonic Visualiser.app / sonic-annotator（已存在则跳过）
#   3. Vamp 插件（优先官方预编译包，失败则用源码 + patches 本机构建）
#
# 仅针对 macOS 做了完整支持；Linux 上会跳过 Sonic Visualiser 相关步骤，
# 并把 Vamp 插件构建到 analysis/vamp（可用 VAMP_PATH 指向它）。
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS="$HERE/analysis"
VENV="$ANALYSIS/venv"
BIN_DIR="$ANALYSIS/bin"
APPS_DIR="$ANALYSIS/apps"
VAMP_DIR="$ANALYSIS/vamp"
BUILD_DIR="$ANALYSIS/vamp-build"
CACHE_DIR="$ANALYSIS/.cache/vamp"
PATCH_DIR="$ANALYSIS/patches"
REQ="$ANALYSIS/requirements.txt"
VAMP_REQ="$ANALYSIS/requirements.vamp.txt"

PYTHON="${PYTHON:-python3}"
CXX="${CXX:-clang++}"
CC="${CC:-clang}"
AR="${AR:-ar}"

OS="$(uname -s)"
ARCH="$(uname -m)"

log() { printf '\n==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }

if [ "$OS" = "Darwin" ]; then
    if [ "$ARCH" = "arm64" ]; then
        ARCHFLAGS="${ARCHFLAGS:--arch arm64 -mmacosx-version-min=11.0}"
    else
        ARCHFLAGS="${ARCHFLAGS:--arch x86_64 -mmacosx-version-min=10.15}"
    fi
else
    # Linux: 不指定 -arch / -mmacosx-version-min
    ARCHFLAGS="${ARCHFLAGS:--fPIC}"
fi

mkdir -p "$CACHE_DIR" "$BUILD_DIR" "$VAMP_DIR" "$PATCH_DIR"

# ---------------------------------------------------------------------------
# 1. Python venv + requirements
# ---------------------------------------------------------------------------
install_python() {
    log "Python 依赖 -> $VENV"
    if [ ! -x "$VENV/bin/python" ]; then
        "$PYTHON" -m venv "$VENV"
    fi
    "$VENV/bin/python" -m pip install --upgrade pip
    "$VENV/bin/python" -m pip install -r "$REQ"
}

# ---------------------------------------------------------------------------
# 2. Sonic Visualiser / Sonic Annotator
# ---------------------------------------------------------------------------
install_sonic_visualiser() {
    if [ "$OS" != "Darwin" ]; then
        warn "非 macOS：跳过 Sonic Visualiser 安装（可自行安装系统版本）"
        return 0
    fi

    if [ -d "$APPS_DIR/Sonic Visualiser.app" ]; then
        log "Sonic Visualiser 已存在，跳过"
    else
        warn "未找到 analysis/apps/Sonic Visualiser.app"
        warn "请手动下载 macOS 版 Sonic Visualiser 后解压到 analysis/apps/："
        warn "  https://www.sonicvisualiser.org/download.html"
    fi
}

install_sonic_annotator() {
    if [ -x "$BIN_DIR/sonic-annotator" ]; then
        log "sonic-annotator 已存在，跳过"
        return 0
    fi
    warn "未找到 analysis/bin/sonic-annotator"
    warn "请手动下载 Sonic Annotator 并放到 analysis/bin/sonic-annotator："
    warn "  https://www.sonicvisualiser.org/sonic-annotator/"
}

# ---------------------------------------------------------------------------
# 3. Vamp plugins
# ---------------------------------------------------------------------------
download() {
    # download <url> <dest>; returns non-zero on failure
    local url="$1" dest="$2"
    if [ -s "$dest" ]; then
        return 0
    fi
    curl -fL --connect-timeout 10 --max-time 90 --retry 1 -o "$dest" "$url" 2>/dev/null
}

untar() {
    # untar <archive> <dest-dir>
    local archive="$1" dest="$2"
    mkdir -p "$dest"
    case "$archive" in
        *.tar.gz|*.tgz) tar -xzf "$archive" -C "$dest" ;;
        *.tar.bz2)      tar -xjf "$archive" -C "$dest" ;;
        *.zip)          unzip -q "$archive" -d "$dest" ;;
        *)              tar -xf "$archive" -C "$dest" ;;
    esac
}

install_prebuilt_plugin() {
    # install_prebuilt_plugin <name> <url>
    local name="$1" url="$2"
    local ext=".tar.gz"
    case "$url" in
        *.tar.bz2) ext=".tar.bz2" ;;
        *.zip)     ext=".zip" ;;
        *.tgz)     ext=".tgz" ;;
    esac
    local archive="$CACHE_DIR/${name}-prebuilt${ext}"
    local extract="$BUILD_DIR/${name}-prebuilt"

    if download "$url" "$archive"; then
        rm -rf "$extract"
        if untar "$archive" "$extract"; then
            find "$extract" -type f \( -name '*.dylib' -o -name '*.so' \) \
                -exec cp {} "$VAMP_DIR/" \;
            if ls "$VAMP_DIR"/*.dylib >/dev/null 2>&1 || ls "$VAMP_DIR"/*.so >/dev/null 2>&1; then
                log "已安装预编译 Vamp 插件：$name"
                return 0
            fi
        fi
        warn "预编译包内容无法识别：$name"
    else
        warn "预编译包下载失败（${url}），改用源码构建"
    fi
    return 1
}

build_vamp_sdk() {
    # build_vamp_sdk <sdk-source-archive>
    local archive="$1"
    local src_root="$BUILD_DIR/src"
    local plugin_sdk_src="$src_root/vamp-plugin-sdk-master"
    local sdk_dir="$BUILD_DIR/sdk"
    local obj_dir="$BUILD_DIR/sdk-obj"

    rm -rf "$src_root/vamp-plugin-sdk-master" "$sdk_dir" "$obj_dir"
    untar "$archive" "$src_root"

    if [ ! -d "$plugin_sdk_src" ]; then
        # tarball 目录名可能变化，兜底查找
        plugin_sdk_src="$(find "$src_root" -maxdepth 1 -type d -name 'vamp-plugin-sdk*' | head -1)"
    fi
    if [ -z "$plugin_sdk_src" ] || [ ! -d "$plugin_sdk_src" ]; then
        warn "Vamp SDK 源码解压失败"
        return 1
    fi

    mkdir -p "$sdk_dir" "$obj_dir"
    cp -R "$plugin_sdk_src/vamp" "$plugin_sdk_src/vamp-sdk" "$sdk_dir/"

    local f
    for f in FFT PluginAdapter RealTime; do
        $CXX -std=c++11 -O2 -I"$plugin_sdk_src" $ARCHFLAGS \
            -c "$plugin_sdk_src/src/vamp-sdk/$f.cpp" -o "$obj_dir/$f.o"
    done
    $CC -O2 -I"$plugin_sdk_src" $ARCHFLAGS \
        -c "$plugin_sdk_src/src/vamp-sdk/acsymbols.c" -o "$obj_dir/acsymbols.o"

    $AR rcs "$sdk_dir/libvamp-sdk.a" "$obj_dir"/FFT.o "$obj_dir"/PluginAdapter.o \
        "$obj_dir"/RealTime.o "$obj_dir"/acsymbols.o
    log "Vamp plugin SDK 静态库构建完成：$sdk_dir/libvamp-sdk.a"
}

build_nnls_chroma() {
    # build_nnls_chroma <source-archive> <sdk-build-dir>
    local archive="$1"
    local sdk_dir="$2"
    local src_root="$BUILD_DIR/src"
    local plugin_src="$src_root/nnls-chroma-1.1"

    rm -rf "$plugin_src"
    untar "$archive" "$src_root"
    if [ ! -d "$plugin_src" ]; then
        plugin_src="$(find "$src_root" -maxdepth 1 -type d -name 'nnls-chroma*' | head -1)"
    fi
    if [ -z "$plugin_src" ] || [ ! -d "$plugin_src" ]; then
        warn "nnls-chroma 源码解压失败"
        return 1
    fi

    cp "$PATCH_DIR/boost_compat.hpp" "$plugin_src/"
    if [ -f "$PATCH_DIR/nnls-chroma-no-boost.patch" ]; then
        if ! patch -p1 -d "$plugin_src" < "$PATCH_DIR/nnls-chroma-no-boost.patch"; then
            warn "应用 nnls-chroma patch 失败（可能版本不匹配）"
            return 1
        fi
    fi

    if ! make -C "$plugin_src" -f Makefile.osx \
        VAMP_SDK_DIR="$sdk_dir" \
        BOOST_ROOT="$BUILD_DIR/no-boost" \
        ARCHFLAGS="$ARCHFLAGS" \
        CXX="$CXX" \
        CC="$CC"; then
        # Linux 上没有 Makefile.osx，尝试 linux 版本
        make -C "$plugin_src" -f Makefile.linux \
            VAMP_SDK_DIR="$sdk_dir" \
            ARCHFLAGS="$ARCHFLAGS" \
            CXX="$CXX" \
            CC="$CC" || return 1
    fi

    local built
    built="$(find "$plugin_src" -maxdepth 1 -type f \( -name 'nnls-chroma.dylib' -o -name 'nnls-chroma.so' \) | head -1)"
    if [ -z "$built" ]; then
        warn "nnls-chroma 构建产物未找到"
        return 1
    fi
    cp "$built" "$VAMP_DIR/"
    log "nnls-chroma 构建完成：$VAMP_DIR/$(basename "$built")"
}

install_vamp_plugins() {
    log "Vamp 插件（Chordino / NNLS Chroma）"

    if [ ! -f "$VAMP_REQ" ]; then
        warn "缺少 ${VAMP_REQ}，跳过 Vamp 插件安装"
        return 0
    fi

    local prebuilt_url="" nnls_src_url="" sdk_src_url=""
    local name version kind url sha
    while IFS='|' read -r name version kind url sha; do
        # 去注释 / 空行 / 首尾空白
        name="$(printf '%s' "$name" | sed 's/#.*//' | tr -d '[:space:]')"
        [ -z "$name" ] && continue
        case "${name}:${kind}" in
            nnls-chroma:plugin-prebuilt) prebuilt_url="$url" ;;
            nnls-chroma:plugin-source)   nnls_src_url="$url" ;;
            vamp-plugin-sdk:sdk-source)  sdk_src_url="$url" ;;
        esac
    done < "$VAMP_REQ"

    # 已经有可用插件就直接跳过
    if ls "$VAMP_DIR"/nnls-chroma.* >/dev/null 2>&1; then
        log "已存在 nnls-chroma，跳过 Vamp 构建（删除 $VAMP_DIR 可强制重装）"
        return 0
    fi

    # 3.1 先试官方预编译包
    if [ -n "$prebuilt_url" ]; then
        if install_prebuilt_plugin "nnls-chroma" "$prebuilt_url"; then
            return 0
        fi
    fi

    # 3.2 源码构建
    if [ -z "$nnls_src_url" ] || [ -z "$sdk_src_url" ]; then
        warn "requirements.vamp.txt 缺少源码 URL，无法本机构建"
        return 1
    fi

    local nnls_archive="$CACHE_DIR/nnls-chroma.tar.gz"
    local sdk_archive="$CACHE_DIR/vamp-plugin-sdk.tar.gz"

    log "下载 Vamp SDK 源码"
    download "$sdk_src_url" "$sdk_archive" || { warn "SDK 下载失败"; return 1; }
    log "下载 nnls-chroma 源码"
    download "$nnls_src_url" "$nnls_archive" || { warn "插件源码下载失败"; return 1; }

    build_vamp_sdk "$sdk_archive" || return 1
    build_nnls_chroma "$nnls_archive" "$BUILD_DIR/sdk" || return 1

    log "Vamp 插件安装到：$VAMP_DIR"
}

verify_vamp() {
    local annotator="$BIN_DIR/sonic-annotator"
    if [ ! -x "$annotator" ]; then
        return 0
    fi
    log "验证 Vamp 插件"
    if VAMP_PATH="$VAMP_DIR" "$annotator" -q -l 2>/dev/null | grep -q 'nnls-chroma'; then
        printf '  ✔ nnls-chroma / Chordino 已被 sonic-annotator 识别\n'
    else
        warn "sonic-annotator 未识别到 nnls-chroma，请检查 VAMP_PATH=$VAMP_DIR"
        return 1
    fi
}

main() {
    install_python
    install_sonic_visualiser
    install_sonic_annotator
    install_vamp_plugins
    verify_vamp
    log "音乐分析环境安装完成"
    printf '  VAMP_PATH=%s\n' "$VAMP_DIR"
    printf '  CLI: %s/bin/song-analyze\n' "$ANALYSIS"
    printf '  示例: VAMP_PATH=%s %s/bin/song-analyze run <audio> --artist "艺术家" --title "歌名"\n' \
        "$VAMP_DIR" "$ANALYSIS"
}

main "$@"
