# 交接文档 — Mica Retro Converter

> 本文档供后续接手开发者使用，记录当前项目状态、架构要点、已解决问题及待办事项。

---

## 1. 项目概述

将现代视频（MP4/MKV/AVI 等）转换为 Windows 98 可播放的 ASF 格式（WMV2 + WMA2 编码）。基于 Tauri 2.x 桌面框架，前端 Vanilla JS，后端 Python FastAPI，转换核心 FFmpeg。

- **仓库地址**: https://github.com/fushuqian/Mica-Retro-Converter
- **本地路径**: `c:\Syncthing\Trae-Workspace\Mica-Retro-Converter`
- **目标平台**: Windows（开发环境为 Windows 11）

---

## 2. 环境搭建

### 必需组件

| 组件 | 版本 | 安装方式 |
|------|------|----------|
| Node.js | >= 18 | https://nodejs.org/ |
| Rust | stable (msvc 工具链) | https://rustup.rs/ |
| Python | >= 3.10 | https://python.org/ |
| FFmpeg | GPL full build | 见下方说明 |

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/fushuqian/Mica-Retro-Converter.git
cd Mica-Retro-Converter

# 2. 安装 Node 依赖
npm install

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 下载 FFmpeg
# 从 https://gh-proxy.com/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip 下载
# 解压后将 ffmpeg.exe 和 ffprobe.exe 放入 ffmpeg/ 目录

# 5. 启动开发模式
npm run dev
# 这会同时启动: Vite 前端 (端口 1420) + Tauri 窗口 + Python sidecar (端口 8765)
```

---

## 3. 架构详解

### 3.1 三层架构

```
┌─────────────────────────────────────────────┐
│  Tauri 窗口 (Rust)                           │
│  - 无边框窗口 320x640, 自定义标题栏           │
│  - 拖放捕获 (on_window_event DragDrop)       │
│  - Python sidecar 进程管理                    │
│  - 日志输出到 sidecar.log                     │
├─────────────────────────────────────────────┤
│  前端 (Vite + Vanilla JS)                    │
│  - index.html / src/app.js / src/styles.css  │
│  - SSE EventSource 接收实时进度               │
│  - 文件拖放 (Rust 通道 + HTML5 DnD 双通道)    │
│  - 卡片 UI: 格式胶囊/文件名滚动/信息胶囊       │
├─────────────────────────────────────────────┤
│  Python 后端 (FastAPI, 端口 8765)            │
│  - server.py: API 路由 + SSE 推送            │
│  - converter_core.py: FFmpeg 调用逻辑        │
│  - converter.py / main.py: 独立运行入口       │
└─────────────────────────────────────────────┘
```

### 3.2 关键数据流

**转换进度推送链路:**

```
FFmpeg subprocess (stderr 解析 progress)
  → converter_core.py (计算百分比, push 到事件队列)
  → server.py /api/events (SSE 推送)
  → 前端 EventSource (handleServerEvent)
  → updateTaskCardProgress (直接更新 DOM, 不触发完整重渲染)
```

**文件添加链路:**

```
用户拖放文件
  → Rust on_window_event(DragDrop) → emit("drag://drop", paths)
  → 前端 listen("drag://drop") → addFilePaths(paths)
  → 异步调用 /api/files/info 获取视频元数据
  → updateTaskCardMeta (更新格式胶囊/滚动/信息胶囊)
```

### 3.3 API 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查，返回 ffmpeg/ffprobe 路径 |
| GET | `/api/presets` | 获取转换预设列表 (13 个预设 + 8 个帧率选项) |
| POST | `/api/files/validate` | 验证文件路径有效性，返回文件大小和视频元数据 |
| GET | `/api/files/info?path=...` | 获取单个文件视频元数据 (编码/分辨率/帧率/宽高比/码率) |
| POST | `/api/convert/start` | 启动转换任务 |
| GET | `/api/convert/status` | 查询转换状态 (进度/状态/输出路径) |
| POST | `/api/convert/cancel` | 取消当前转换 |
| GET | `/api/events` | SSE 事件流 (progress/file_started/file_finished/all_done/log) |

---

## 4. 本次开发改动记录

### 4.1 已修复的问题

#### Bug 1: SSE 422 错误导致界面无反馈
- **根因**: 前端请求 `/api/events?since=` 传空参数，FastAPI float 类型校验失败返回 422
- **修复**:
  - 前端 `src/app.js:700`: 仅在 `lastEventTs > 0` 时添加 since 参数
  - 后端 `server.py:280-305`: 参数类型改为 `str | None`，手动容错解析

#### Bug 2: Windows 路径文件名提取失败
- **根因**: `split(/[\/]/)` 无法匹配 Windows 反斜杠 `\`
- **修复**: `src/app.js:339`: 改为 `split(/[\\\/]/)` 同时兼容正反斜杠

#### Bug 3: 进度更新打断文件名滚动动画
- **根因**: 每次 SSE progress 事件调用 `renderTaskList()` → `updateTaskCard()`，重置 marquee 动画
- **修复**: 拆分为 `updateTaskCardMeta`（文件名/胶囊/滚动）和 `updateTaskCardProgress`（进度条/状态），progress 事件仅调用后者

#### Bug 4: 预设下拉菜单无法展开
- **根因**: 频繁的 `renderTaskList()` 调用造成 UI 线程拥堵
- **修复**: 同 Bug 3，progress 事件改为直接 DOM 更新

#### Bug 5: sidecar 日志不可见
- **根因**: Rust 代码中 sidecar stdout/stderr 被重定向到 `Stdio::null()`
- **修复**: `src-tauri/src/main.rs:119-154`: 改为追加写入 `sidecar.log`

### 4.2 新增功能

#### 视频元数据提取
- `converter_core.py:210-297`: 新增 `probe_video_info()` 函数
- 通过 ffprobe 获取: 视频编码、音频编码、分辨率、帧率、宽高比(display_aspect_ratio)、视频码率、音频码率、时长
- `server.py`: 新增 `/api/files/info` 接口，`/api/files/validate` 也返回元数据

#### 卡片 UI 改造
- **格式胶囊**: 文件名前显示文件格式（MKV/AVI/MP4 等），从扩展名提取
- **文件名滚动**: 超长文件名从右往左滚动，CSS 变量 `--marquee-distance` 精确控制位移，首尾各 8% 停顿
- **视频胶囊**: 蓝色，显示 `🎬 H.264 704x480 29.97FPS 4:3 1 Mbps`
- **音频胶囊**: 绿色，显示 `🔊 AAC 262 kbps`
- **关闭按钮**: 移至文件名右侧，卡片悬停时显示

### 4.3 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `converter_core.py` | 新增 `probe_video_info()` 函数 + `aspect_ratio` 字段 |
| `server.py` | SSE 参数容错 + `/api/files/info` 接口 + validate 返回元数据 |
| `src/app.js` | UI 重构: 文件名提取/滚动/胶囊/进度拆分/事件处理优化 |
| `src/styles.css` | 滚动动画 + 胶囊样式 + flex 布局调整 |
| `src-tauri/src/main.rs` | sidecar 日志重定向到 sidecar.log |

---

## 5. 关键代码位置索引

### 前端 (src/app.js)

| 函数 | 行号 | 说明 |
|------|------|------|
| `renderTaskList()` | ~202 | 渲染任务列表，新增卡片用 createTaskCard，已有卡片仅更新进度 |
| `createTaskCard(f)` | ~234 | 创建卡片 DOM，含格式胶囊/滚动容器/关闭按钮/进度条 |
| `updateTaskCardMeta(card, f)` | ~272 | 更新文件名/格式/滚动/胶囊，仅在文件添加或元数据到达时调用 |
| `updateTaskCardProgress(card, f)` | ~320 | 仅更新进度条/百分比/状态，progress 事件直接调用 |
| `buildChipsForInfo(info)` | ~330 | 构建视频/音频胶囊数据 |
| `fileFormat(name)` | ~338 | 从文件名提取扩展名（大写） |
| `handleServerEvent(event, payload)` | ~712 | SSE 事件处理: progress/file_started/file_finished/all_done |
| `connectEventSource()` | ~697 | 建立 SSE 连接 |
| `enrichFilesWithMeta(files)` | ~418 | 异步获取文件元数据 |
| `addFilePaths(paths, sizeMap)` | ~460 | 添加文件到列表 |
| `startConvert()` | ~778 | 启动转换 |
| `syncFromServerStatus()` | ~111 | 从后端同步状态（轮询备用） |

### 后端 (server.py)

| 函数/路由 | 说明 |
|-----------|------|
| `GET /api/events` | SSE 事件流，参数 since 兼容空字符串 |
| `GET /api/files/info` | 返回视频元数据 JSON |
| `POST /api/files/validate` | 验证文件 + 返回元数据 |
| `POST /api/convert/start` | 启动转换 |
| `GET /api/convert/status` | 查询状态 |

### 转换核心 (converter_core.py)

| 函数 | 说明 |
|------|------|
| `probe_video_info(ffprobe_path, file_path)` | ffprobe 获取视频元数据 |
| `convert_video(...)` | FFmpeg 转换主逻辑 |
| `find_subtitle_for_video(video_path)` | 自动查找同名字幕文件 |

### Rust (src-tauri/src/main.rs)

| 位置 | 说明 |
|------|------|
| `main()` | 窗口创建 + sidecar 启动 |
| `on_window_event(DragDrop)` | 文件拖放捕获 |
| sidecar stdout/stderr | 重定向到 sidecar.log |

---

## 6. 已知问题与待办

### 可能需要改进的点

1. **多文件转换**: 当前单文件转换已验证，多文件队列转换的 UI 更新逻辑可能需要进一步测试
2. **错误处理**: FFmpeg 转换失败时的用户提示可以更友好
3. **取消转换**: `cancel` 接口已实现，但前端取消按钮的交互可能需要完善
4. **构建发布**: `npm run tauri:build` 需要测试，确保 Python sidecar 正确打包
5. **跨平台**: 目前仅支持 Windows，macOS/Linux 需要适配 FFmpeg 路径和 sidecar 启动方式
6. **字幕编码**: 烧录字幕时中文字幕可能需要指定字符编码（如 GB2312）
7. **FFmpeg 下载**: 当前使用 gh-proxy.com 加速，正式发布版应考虑内置或提供多种下载源

### 调试技巧

- **查看后端日志**: `sidecar.log`（项目根目录，运行时生成）
- **手动测试 API**: 后端运行在 `http://127.0.0.1:8765`
  ```bash
  curl http://127.0.0.1:8765/api/health
  curl "http://127.0.0.1:8765/api/files/info?path=<URL_ENCODED_PATH>"
  curl http://127.0.0.1:8765/api/convert/status
  ```
- **查看 SSE 事件**: 
  ```bash
  curl -N http://127.0.0.1:8765/api/events
  ```
- **前端热更新**: Vite 自动热更新 JS/CSS，修改后刷新窗口即可
- **Rust 修改**: 需要重启 `npm run dev`（cargo 会重新编译）
- **Python 修改**: 需要重启 `npm run dev`（sidecar 会重新启动）

---

## 7. 技术决策记录

### 为什么用 SSE 而非 WebSocket?
SSE 是单向推送（服务器→客户端），适合进度推送场景。比 WebSocket 更简单，不需要双向通信。FastAPI 原生支持 SSE。

### 为什么进度更新要拆分 renderTaskList?
`renderTaskList()` 会遍历所有卡片并调用 `updateTaskCard`，其中 marquee 动画重置会导致滚动中断。拆分后，progress 事件仅更新进度条 DOM，不干扰文件名滚动。

### 为什么用双通道拖放?
Rust 层 `on_window_event(DragDrop)` 能拿到操作系统级绝对路径，但有时不稳定。HTML5 DnD 作为 fallback，双通道 500ms 去重防止重复添加。

### 为什么 sidecar 日志重定向到文件?
Tauri sidecar 的 stdout/stderr 默认被丢弃（`Stdio::null()`），调试时无法看到 Python 后端输出。重定向到 `sidecar.log` 后可以查看启动日志和错误信息。

---

## 8. Git 信息

- **仓库**: https://github.com/fushuqian/Mica-Retro-Converter
- **分支**: main
- **最近提交**:
  - `f40d8d5` feat: 实时进度反馈 + UI 改造（文件名滚动/胶囊标签/格式显示）
  - `7a5793c` docs: add README
  - `d66aef3` chore: init Mica Retro Converter — Tauri 2.x + FastAPI FFmpeg Win98 converter

---

## 9. 联系方式

如有疑问，请联系原开发者。
