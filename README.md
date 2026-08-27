# MICA RETRO CONVERTER

把现代视频转换为 Windows 98 能直接播放的老格式。WPF (.NET 8) 原生 Windows 程序，基于 FFmpeg。

一台现代电脑上的时光机：拖进去一个 4K 视频，拿出来一张能塞进当年 VCD 机的碟片内容。

---

## 功能

- **拖放添加**视频文件（支持整个文件夹递归扫描），列表自动显示文件信息（分辨率/编码/帧率/码率/时长）
- **15 个预设**，覆盖当年主流格式（见下表）
- **Letterbox 4:3 黑边**（默认开启）：宽屏视频加黑边适配老电视，不拉伸变形
- **帧率控制**：VCD/DVD 强制规格帧率，其他格式可选常见帧率或保持原帧率
- **字幕烧录**：自动发现同名 `.srt/.ass/.ssa/.sub` 字幕并烧录进画面
- **批量转换**：单文件进度 + 总进度，可随时取消
- **Windows 11 原生体验**：Mica 材质背景、窗口圆角、明暗主题跟随系统（可手动切换）、任务栏图标进度条、Snackbar 完成通知
- **`--selftest` 自测**：自动生成测试源 → 转 ASF → ffprobe 校验编码，一条命令验证环境完好
- 输出文件自动加后缀（如 `_win98`），永不覆盖原文件

---

## 预设一览

| 分组 | 预设 | 规格要点 |
|---|---|---|
| Win98 流媒体 | ASF 标准 / 高质量 / 最小体积 | WMV2 + WMA2 → ASF，640×480 / 800×600 / 320×240 |
| VCD | PAL / NTSC | MPEG-1 + MP2，352×288@25 / 352×240@29.97，1150k |
| SVCD | PAL / NTSC | MPEG-2 + MP2，480×576 / 480×480，2500k |
| DVD | PAL / NTSC | MPEG-2 + AC-3，720×576 / 720×480，6000k，输出 .vob |
| MPEG-4 AVI | DivX / Xvid | MPEG-4（DX50/XVID 标签） |
| RealNetworks | RM | RV10 + real_144 音频 |
| 占位 | RMVB | 暂不可用（置灰） |

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 界面 | WPF (.NET 8) + WPF-UI 3.0.5 | FluentWindow / Mica / Snackbar / TaskBarProgress |
| 转换核心 | FFmpeg | 进程调用，stderr 实时解析进度，双管道并行读取防死锁 |
| 探测 | FFprobe | JSON 输出，解析分辨率/编码/帧率/码率/时长 |

---

## 目录结构

```
win98-asf-converter/
├── wpf/                       # WPF 程序（当前实现）
│   ├── Win98Converter.csproj
│   ├── AssemblyInfo.cs        # WPF 主题资源程序集信息
│   ├── App.xaml(.cs)          # 启动：--selftest 分支 / 主题初始化
│   ├── MainWindow.xaml(.cs)   # 主界面：拖放、列表、设置、日志
│   └── Core/
│       ├── Preset.cs          # 预设数据模型
│       ├── Presets.cs         # 15 个预设定义 + 帧率选项
│       ├── ConversionEngine.cs # ffmpeg 命令构造/进度解析/转换执行
│       ├── MediaProbe.cs      # ffprobe 文件信息探测
│       └── SelfTest.cs        # --selftest 端到端自测
├── ffmpeg/                    # FFmpeg 二进制（不在仓库中，需自行放入）
├── docs/                      # 设计文档（预设编辑器 v3.1 规划等）
├── QUEST.md                   # 任务清单（已完成 / 待办）
└── CHANGELOG.md               # 更新日志
```

---

## 环境要求

- **Windows 10/11**（运行）
- **.NET 8 SDK**（仅编译时需要）
- **FFmpeg**：从 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 或 BtbN builds 下载，把 `ffmpeg.exe` 和 `ffprobe.exe` 放入项目的 `ffmpeg/` 目录

---

## 构建与运行

```powershell
# 编译
dotnet build wpf\Win98Converter.csproj -c Debug

# 运行
.\wpf\bin\Debug\net8.0-windows10.0.19041.0\Win98Converter.exe

# 环境自测（退出码 0 = 通过）
.\wpf\bin\Debug\net8.0-windows10.0.19041.0\Win98Converter.exe --selftest
```

FFmpeg 查找顺序：程序目录的 `ffmpeg/` 子目录 → 程序同级目录 → 向上最多 5 层父目录的 `ffmpeg/` → 系统 PATH。

---

## 历史版本

v1 为 Python FastAPI + Web 前端，v2 为 Tauri 2.x 桌面版，均已被 WPF 版（v3）取代。旧实现代码保留在 git 历史中。

## License

MIT
