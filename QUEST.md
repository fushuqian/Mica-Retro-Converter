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
- [x] RMVB 预设替换为 RM(RV20 高画质)（2026-08-28）：RealNetworks 已退出编解码业务，无合法开源 RV30/RV40 编码器，将占位 RMVB 预设替换为基于 ffmpeg RV20 编码的高画质 RM 预设
- [x] 画面比例 SAR/`-aspect` 参数支持（2026-08-28）：UI 新增下拉（保持原比例/4:3/16:9/16:10/1:1/3:2/2.35:1），ConversionEngine 的 BuildFilterChain/BuildFfmpegCommand/ConvertAsync 全链路支持 aspectRatio 参数
- [x] 预设编辑器 Phase1（2026-08-28）：
  - [x] `presets.builtin.json` 生成内置预设数据文件
  - [x] `PresetRegistry` 类管理预设加载/保存/增删改查（区分内置与用户预设）
  - [x] `Presets` 静态类改为从 Registry 加载
  - [x] `PresetEditorWindow` 预设编辑窗口（DataGrid 编辑 + 新建/复制/删除/重置/导入/导出/保存 + 取消）
  - [x] 主窗口"编辑预设"按钮接入

## 待办 / 未来

- [ ] 真实视频 + 同名字幕的字幕烧录验证
- [ ] GUI 手动走查：多文件批量转换、取消按钮、主题切换按钮
- [ ] 预设编辑器 Phase2：内置预设字段校验（码率范围/分辨率合理性）、分组/搜索/排序、撤销重做
- [ ] 发布打包（单文件发布 / 安装包）