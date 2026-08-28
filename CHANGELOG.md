# 更新日志

## 2026-08-28 — 文件信息显示 + 目录整理

- **文件信息显示**：文件列表新增"文件信息"列，拖入文件后自动用 ffprobe 探测并显示分辨率、视频/音频编码、帧率、码率、时长（如 `1920×1080 · h264 · 23.98fps · 2.1Mbps · 01:23:45`）。新增 `wpf/Core/MediaProbe.cs`，解析 JSON 输出，20 秒超时保护，探测失败不阻塞转换
- **目录整理**：旧的 Python/Web/Tauri 实现、设计稿、过时的 HANDOVER.md 全部移入 `toberemoved/`（.gitignore 已排除，待老板确认后删除）
- **Git**：合并推送了远程两个旧提交（实时进度反馈功能、交接文档），未覆盖历史
- **清理**：确认 `toberemoved/` 不需要后整个删除，释放约 40MB；发现遗留的预设编辑器设计稿 `docs/preset-editor-spec.md`（v3.1 规划），保留待用
- **文档**：README 重写为 WPF 版说明（功能/预设表/构建方法），替换已废弃的 Tauri 版描述
- **文件列表改为卡片式**：每个文件一张圆角卡片（文件名/文件信息/状态行）替换原表格视图；状态按颜色区分（转换中/完成/失败）；卡片悬停显示完整路径；新增卡片内删除按钮（Delete 键删除仍保留）
- **修复 VCD-PAL GOP**：`-g 18` → `-g 15`（PAL 25fps 按 VCD 规格 GOP 应为 0.6 秒=15 帧，原值沿用自旧版笔误）；已实测 25fps+`-g 15`+vcd 容器编码通过
- **修复卡片视图闪退**：`MainWindow.xaml` 中"转换中"状态的 `SystemAccentColorDefaultBrush` → `SystemAccentColorPrimaryBrush`（WPF-UI 3.0.5 枚举中不存在 DefaultBrush，DataTemplate 实例化时抛 XamlParseException 导致进程崩溃）
- **修复 SVCD-PAL GOP**：`-g 18` → `-g 15`（与 VCD-PAL 同理，MPEG-2 PAL 25fps × 0.6s = 15 帧）
- **修复 DVD-NTSC GOP**：`-g 15` → `-g 18`（NTSC 29.97fps × 0.6s ≈ 18 帧，与前两次对称的 PAL/NTSC 写反问题）

## 2026-08-27 — WPF 原生重构（v3.0.0）

用 WPF (.NET 8) + WPF-UI 3.0.5 重写了整个程序，替代 Python/Qt 和 Web 版。新程序在 `wpf/` 目录。

- **转换核心完整移植**：15 个预设（Win98 ASF、VCD/SVCD/DVD 的 PAL/NTSC、DivX/Xvid、RM）参数与 Python 版逐项一致；ffmpeg 命令构造、进度解析、输出路径规则逐行对应，未改任何行为（包括 VCD-PAL 的 `-g 18` 存疑项）
- **Win11 特性**：Mica 背景、窗口圆角、明暗主题跟随系统并可手动切换、任务栏图标进度条、Snackbar 完成通知
- **主界面**：拖拽添加文件（支持文件夹）、文件列表带单文件进度、预设/帧率/黑边/字幕烧录设置、实时日志
- **`--selftest` 自测**：自动生成测试源视频并跑一遍 ASF 转换，用 ffprobe 校验编码与容器，已通过
- **ffmpeg 查找逻辑增强**：除原目录搜索外，支持从可执行文件位置向上最多 5 层查找 `ffmpeg/` 目录（适配 `bin\Debug` 深层输出路径）

构建：`dotnet build wpf\Win98Converter.csproj`（需 .NET 8 SDK）
