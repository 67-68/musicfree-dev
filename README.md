# musicfree-dev

MusicFree 本地开发工作区（类似 dsh-plugins 的组织方式，但面向 MusicFree）。

本仓库是**独立 git repo**（位于 `projects/musicfree-dev`）。`app/` 与 `plugins/template/` 是各自独立的 git clone（有自己的 `.git` 和 remote），在本仓库中被 `.gitignore` 排除，代码请在各自仓库里提交。


## 目录

```
musicfree-dev/
├── app/                     # 本体：MusicFreeDesktop（fork，含歌曲解析面板）
├── plugins/
│   └── template/            # 官方插件模板（MusicFreePluginTemplate，MIT）
├── analysis/                # song-analysis CLI（结构/和弦/旋律/Genius/SV）
│   ├── bin/song-analyze     # CLI 入口
│   ├── pipeline/            # Python 实现
│   ├── patches/             # nnls-chroma 的 boost-free 补丁
│   ├── vamp/                # Vamp 插件（music_install.sh 生成，不提交）
│   ├── requirements.txt     # Python 依赖
│   └── requirements.vamp.txt# Vamp 插件/SDK 下载清单
├── scripts/
│   ├── dev-app.sh           # 启动桌面端开发模式
│   ├── build-plugin.sh      # 构建指定插件目录为 dist/plugin.js
│   └── install-app.sh       # 安装 app 依赖（含 electron 缓存修复）
├── music_install.sh         # 安装分析侧环境 + Vamp 插件
└── README.md
```

## 已克隆的仓库

- `app` 上游：https://github.com/maotoumao/MusicFreeDesktop （当前 `dev` 分支）
- `plugins/template` 上游：https://github.com/maotoumao/MusicFreePluginTemplate （`master`）

## 日常命令

```bash
# 1. 安装 app 依赖（含 electron 缓存修复）
./scripts/install-app.sh

# 2. 安装分析侧环境：Python venv + Vamp 插件（Chordino/NNLS Chroma）
./music_install.sh

# 3. 启动播放器开发模式
./scripts/dev-app.sh

# 4. 构建插件（默认 template，可传其他目录名）
./scripts/build-plugin.sh [插件目录名]
```

## song-analysis CLI

```bash
# 完整分析（拆轨 + 结构 + 和弦/节拍/旋律 + 可选 Genius）
analysis/bin/song-analyze run <audio> --artist "艺术家" --title "歌名"

# 用 Sonic Visualiser 打开波形与标注层
analysis/bin/song-analyze open <audio>

# 拉取 Genius 资料（需要 GENIUS_ACCESS_TOKEN）
analysis/bin/song-analyze genius "艺术家" "歌名" --out-dir analysis/output/<artist>-<title>
```

输出在 `analysis/output/<artist>-<title>/`：`analysis.json`、`report.md`、`stems/`、`chords.csv`、`beats.csv`、`melody.mid`。

首次运行会下载模型到 `analysis/.cache/`，耗时较长。

`music_install.sh` 会把 Chordino / NNLS Chroma 装到 `analysis/vamp/`。CLI 启动时会自动把该目录加入 `VAMP_PATH`，因此通常不需要手动设置；如需手动运行 Sonic Annotator，可 `export VAMP_PATH="$PWD/analysis/vamp"`。

## MusicFree 集成

- **入口**：全屏播放页（歌词页）右下角工具栏 →「歌曲解析」按钮。
- **面板能力**：开始分析（仅本地歌曲，需要 `musicItem.localPath`）、打开/关闭 Sonic Visualiser、查看结构时间轴与 `report.md`。
- **主进程**：`app/src/infra/songAnalysis/` 负责调用 `analysis/bin/song-analyze run`、读取 `analysis.json` / `report.md`，并 spawn / kill Sonic Visualiser 子进程；子进程退出后会自动把开关状态同步回渲染层。
- **插件安装**：Vamp 预编译包不可达时会自动从源码构建（`analysis/patches/nnls-chroma-no-boost.patch`），不依赖 Boost。

## 环境备注

- 本机 Node 版本较新，npm 安装 electron 时安装脚本可能不完整，`install-app.sh` 已处理。
- npm 缓存被重定向到 `/tmp/npm-cache`，electron 缓存到 `/tmp/electron-cache`，因为 `~/.npm` 与 `~/Library/Caches` 存在权限问题。
- `music_install.sh` 只负责分析侧；`app` 本体依赖仍走 `scripts/install-app.sh`，两者分开执行。
