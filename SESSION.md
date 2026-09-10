# MusicFree 开发会话记录

## 目标
- 给自己/其他人用的小软件：基于 MusicFree 桌面版，加“歌词高亮 + AI 解释歌词”。
- 优先验证需求，再逐步做登录/账号同步。

## 当前状态（2026-09-10）

- [x] 克隆本体 MusicFreeDesktop（dev 分支）到 `app/`
- [x] 克隆官方插件模板 MusicFreePluginTemplate 到 `plugins/template/`
- [x] 安装 app 依赖，修复 electron 二进制（Node 26 下 install.js 不完整，用 ditto 手动解包）
- [x] 验证插件构建：`./scripts/build-plugin.sh` 成功
- [x] song-analysis CLI 跑通：`analysis/bin/song-analyze run`（all-in-one-infer 结构 + 拆轨、basic-pitch 旋律、Genius 可选）
- [x] Vamp 插件（Chordino / NNLS Chroma）装好：`analysis/vamp/nnls-chroma.dylib`，不再走 librosa fallback
- [x] 新增 `music_install.sh` + `analysis/requirements.txt` + `analysis/requirements.vamp.txt`，Vamp 预编译不可达时自动源码构建（`analysis/patches/nnls-chroma-no-boost.patch`）
- [x] MusicFree 集成 Phase 1-3：`src/infra/songAnalysis/`（main/preload/renderer/common + 类型）、`FullscreenPlayer` 歌曲解析面板、Sonic Visualiser 子进程开关与退出同步
- [x] `npm run lint` / `tsc --noEmit` / SCSS 编译通过
- [x] `musicfree-dev` 独立 git repo 初始化：`/Users/a67_68/projects/musicfree-dev`（`app/`、`plugins/template/` 排除，各自独立 repo）
- [ ] 创建 GitHub fork 并接入 origin
- [ ] 验证 `./scripts/dev-app.sh` 能启动桌面端（webpack bundle 已用 HOME 重定向验证；GUI 启动待本地手测）
- [ ] 设计歌词高亮/AI 讲解的插件协议扩展

## 关键路径
- 工作区：`/Users/a67_68/projects/musicfree-dev/`（路径已迁移）
- song-analysis：`analysis/bin/song-analyze`，输出 `analysis/output/<artist>-<title>/`
- 模型缓存：`analysis/.cache/`（torch / hf / mpl）；Vamp 源码/构建缓存：`analysis/vamp-build/`
- Vamp 插件目录：`analysis/vamp/`（`VAMP_PATH`，由 CLI 自动注入）
- npm 缓存：`/tmp/npm-cache`（因 ~/.npm 权限问题）
- electron 缓存：`/tmp/electron-cache`
- app 上游：https://github.com/maotoumao/MusicFreeDesktop （当前 dev）
- 插件模板：https://github.com/maotoumao/MusicFreePluginTemplate

## 下一步
1. 用户在 GitHub fork `maotoumao/MusicFreeDesktop`。
2. 本地 app 把 origin 指向用户 fork，upstream 保留官方。
3. 跑通 `./scripts/dev-app.sh`，在本地歌曲上验证「歌曲解析」面板与 Sonic Visualiser 开关。
4. 在 fork 中扩展插件协议：登录态 + `getLyricExplanation`。
5. 接入 Genius 资料与 AI 逐句讲解（把 `report.md` 与歌词窗口联动）。
