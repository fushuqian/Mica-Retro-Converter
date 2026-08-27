# QUEST — 任务清单

## 项目：Win98 ASF 视频转换器

把视频转换为 Windows 98 原生支持的 ASF（WMV2/WMAV2）格式，并逐步扩展当年流行的老格式预设。

## 已完成

- [x] 拖拽视频 → 转换为 Win98 可播放的 ASF（Python 版：FastAPI 后端 + Web 前端）
- [x] ffmpeg 部署（`ffmpeg/` 目录，随项目携带）
- [x] 15 个预设转换模式：Win98 流媒体（推荐/高质量/最小体积）、VCD PAL/NTSC、SVCD PAL/NTSC、DVD PAL/NTSC、DivX、Xvid、RM（RMVB 占位置灰）
- [x] 黑边（letterbox）选项，默认勾选，适配当年 4:3 电视
- [x] 帧率选项：VCD/DVD 强制规格帧率，其他格式可选常见帧率或保持原帧率
- [x] WPF (.NET 8) 原生重构（`wpf/` 目录）：
  - [x] 转换核心移植（预设表/命令构造/进度解析，与 Python 版逐行一致）
  - [x] Win11 窗口特性：Mica 背景、圆角、主题跟随系统、任务栏进度、Snackbar 通知
  - [x] 主界面：拖拽区、文件列表、设置面板、日志窗口
  - [x] `--selftest` 端到端自测（生成测试源 → 转 ASF → ffprobe 校验，已 PASS）

## 待办 / 未来

- [ ] 画面比例参数（SAR/`-aspect`）：曾讨论给 VCD/SVCD/DVD 预设加 DAR 选项（方案B：UI 下拉，支持 16:9 宽屏 DVD），老板决定先搁置——当前统一 4:3 letterbox 已够用，当年电视清一色 4:3，宽屏碟片场景以后再说
- [ ] 决定是否修复 VCD-PAL 预设 `-g 18`（PAL GOP 规格应为 15；移植时按原样保留，未改行为）
- [ ] RMVB 预设补全（当前占位置灰，vcodec/acodec/container 待定）
- [ ] 真实视频 + 同名字幕的字幕烧录验证
- [ ] GUI 手动走查：多文件批量转换、取消按钮、主题切换按钮
- [ ] 清理旧实现（`server.py`/`frontend/`/`src-tauri/` 等）——待 WPF 版稳定后由老板决定
- [ ] 发布打包（单文件发布 / 安装包）
