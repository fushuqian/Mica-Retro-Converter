# 更新日志

## 2026-08-27 — WPF 原生重构（v3.0.0）

用 WPF (.NET 8) + WPF-UI 3.0.5 重写了整个程序，替代 Python/Qt 和 Web 版。新程序在 `wpf/` 目录。

- **转换核心完整移植**：15 个预设（Win98 ASF、VCD/SVCD/DVD 的 PAL/NTSC、DivX/Xvid、RM）参数与 Python 版逐项一致；ffmpeg 命令构造、进度解析、输出路径规则逐行对应，未改任何行为（包括 VCD-PAL 的 `-g 18` 存疑项）
- **Win11 特性**：Mica 背景、窗口圆角、明暗主题跟随系统并可手动切换、任务栏图标进度条、Snackbar 完成通知
- **主界面**：拖拽添加文件（支持文件夹）、文件列表带单文件进度、预设/帧率/黑边/字幕烧录设置、实时日志
- **`--selftest` 自测**：自动生成测试源视频并跑一遍 ASF 转换，用 ffprobe 校验编码与容器，已通过
- **ffmpeg 查找逻辑增强**：除原目录搜索外，支持从可执行文件位置向上最多 5 层查找 `ffmpeg/` 目录（适配 `bin\Debug` 深层输出路径）

构建：`dotnet build wpf\Win98Converter.csproj`（需 .NET 8 SDK）
