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
  - [x] 文件信息显示：添加文件后自动探测分辨率/编码/帧率/码率/时长，显示在列表"文件信息"列
- [x] 目录整理（2026-08-28）：旧 Python/Web/Tauri 实现、设计稿、HANDOVER.md 全部移入 `toberemoved/`（git 忽略，待删除）
- [x] 合并 GitHub 远程旧提交（实时进度反馈功能 + 交接文档）并推送，提交历史完整保留
- [x] 确认并删除 `toberemoved/`（2026-08-28），释放约 40MB
- [x] 修复卡片视图闪退（2026-08-28）：`MainWindow.xaml` 中 `SystemAccentColorDefaultBrush` → `SystemAccentColorPrimaryBrush`（WPF-UI 3.0.5 中前者不存在，卡片首次实例化时抛 XamlParseException 崩溃）

## 待办 / 未来

- [ ] 画面比例参数（SAR/`-aspect`）：曾讨论给 VCD/SVCD/DVD 预设加 DAR 选项（方案B：UI 下拉，支持 16:9 宽屏 DVD），老板决定先搁置——当前统一 4:3 letterbox 已够用，当年电视清一色 4:3，宽屏碟片场景以后再说
- [x] ~~决定是否修复 VCD/SVCD/DVD 预设 GOP 值~~ → 已修复：
  - VCD-PAL `-g 18` → `-g 15`（PAL 25fps × 0.6s = 15 帧）
  - SVCD-PAL `-g 18` → `-g 15`（同上，MPEG-2 同样规格）
  - DVD-NTSC `-g 15` → `-g 18`（NTSC 29.97fps × 0.6s ≈ 18 帧）
  - 修复时间 2026-08-28
- [ ] RMVB 预设补全（当前占位置灰，vcodec/acodec/container 待定）
- [ ] 真实视频 + 同名字幕的字幕烧录验证
- [ ] GUI 手动走查：多文件批量转换、取消按钮、主题切换按钮
- [ ] 预设编辑器（v3.1 规划）：自定义预设增删改查/持久化/JSON 导入导出，设计稿 `docs/preset-editor-spec.md` 已就绪，待老板拍板开工
- [ ] 发布打包（单文件发布 / 安装包）

