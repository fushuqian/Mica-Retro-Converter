# MICA RETRO CONVERTER

将现代视频转换为 Windows 98 可播放的 ASF 格式。基于 Tauri 2.x + Python FastAPI + FFmpeg 构建的极简桌面工具。

---

## 功能

- 拖放添加视频文件（支持文件夹递归扫描）
- 转换为 Win98 兼容的 ASF 容器（WMV2 编码 + WMA2 音频）
- 可选 4:3 画面比例、烧录字幕
- 输出文件自动加 `_win98` 后缀，不覆盖原文件
- 窗口置顶（图钉按钮）
- 自定义标题栏，支持拖动
- 宽度锁定 320px，高度可调（520px 起）

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 桌面壳 | Tauri 2.x (Rust) | 无边框窗口、自定义标题栏、文件拖放捕获、Python sidecar 管理 |
| 前端 | Vite + Vanilla JS | 三段式布局：标题栏 / 任务列表 / 悬浮底部卡片 |
| 后端 | Python FastAPI | FFmpeg 进程调用、SSE 实时进度推送 |
| 转换核心 | FFmpeg | WMV2 视频编码 + WMA2 音频编码 → ASF 容器 |

---

## 目录结构

```
win98-asf-converter/
├── index.html              # 前端入口
├── src/
│   ├── app.js              # 前端逻辑（拖放、任务列表、窗口控制）
│   └── styles.css         # MICA 风格样式
├── vite.config.js          # Vite 配置（端口 1420）
├── server.py               # FastAPI 后端（SSE 进度推送）
├── converter_core.py       # FFmpeg 转换核心逻辑
├── converter.py            # 转换入口
├── main.py                # Python 独立运行入口
├── requirements.txt       # Python 依赖
├── ffmpeg/                # FFmpeg 二进制（需自行放入）
│   ├── ffmpeg.exe         # ← 不在仓库中，需下载
│   ├── ffprobe.exe        # ← 不在仓库中，需下载
│   └── .gitkeep
├── src-tauri/
│   ├── src/main.rs        # Rust 后端（窗口事件、sidecar、拖放）
│   ├── tauri.conf.json    # Tauri 窗口配置
│   ├── Cargo.toml         # Rust 依赖
│   ├── capabilities/
│   │   └── default.json  # 权限配置（拖放、置顶、拖拽窗口）
│   ├── build.rs           # Tauri 构建脚本
│   └── icons/             # 应用图标
└── package.json           # Node 依赖与脚本
```

---

## 环境要求

### 必需

- **Node.js** >= 18
- **Rust** (stable, `x86_64-pc-windows-gnu` 工具链)
- **Python** >= 3.10
- **FFmpeg** 二进制文件（放入 `ffmpeg/` 目录）

### Python 依赖

```bash
pip install -r requirements.txt
# fastapi, uvicorn, PyQt5
```

### FFmpeg 放置

从 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载 essentials build，将以下文件放入 `ffmpeg/` 目录：

```
ffmpeg/
├── ffmpeg.exe
└── ffprobe.exe
```

---

## 开发

```bash
# 安装 Node 依赖
npm install

# 安装 Python 依赖
pip install -r requirements.txt

# 启动开发模式（同时启动 Vite + Tauri + Python sidecar）
npm run tauri dev
```

### 构建发布版

```bash
npm run tauri:build
```

---

## 转换参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| 视频编码 | WMV2 | Windows Media Video 8，Win98 兼容 |
| 音频编码 | WMA2 | Windows Media Audio 9 |
| 容器 | ASF | Advanced Systems Format |
| 分辨率 | 可选 320x240 / 640x480 / 原始 | Win98 推荐 320x240 |
| 码率 | 可选 512K / 1M / 2M | 越低兼容性越好 |
| 帧率 | 可选 15 / 24 / 30 fps | Win98 推荐 24fps |
| 画面比例 | 可选 4:3 | 裁剪为 4:3 适配老式 CRT 显示器 |
| 字幕烧录 | 可选 | 将字幕硬编码到画面 |

---

## 窗口配置

```json
// tauri.conf.json
{
  "width": 320, "height": 640,
  "minWidth": 320, "maxWidth": 320,
  "minHeight": 520,
  "decorations": false,
  "transparent": false,
  "dragDropEnabled": true
}
```

- 宽度锁定 320px（`minWidth = maxWidth = 320`）
- 高度可调（`minHeight = 520`，无上限）
- 无系统边框（`decorations: false`），自定义标题栏
- 纯色背景（`transparent: false`）
- 允许文件拖放（`dragDropEnabled: true`）

---

## 拖放实现

拖放采用 Rust 层 `on_window_event(DragDrop)` 直接捕获，绕开 WebView2 沙箱限制，确保拿到操作系统级的绝对路径：

```
Explorer 拖入
  → Rust WindowEvent::DragDrop
  → emit("drag://drop", Vec<String> paths)
  → 前端 listen("drag://drop") → addFilePaths(paths)
```

同时保留 HTML5 DnD 作为 fallback，双通道 500ms 去重防止重复添加。

---

## License

MIT