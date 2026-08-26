"""
converter.py - ASF 转换核心逻辑（针对 Windows 98 兼容性设计）

默认编码参数:
  - 容器: ASF (Win98 自带 WMP 6.4+ 原生支持)
  - 视频: wmv2 (Windows Media Video 8)
  - 音频: wmav2 (Windows Media Audio v2)
  - 字幕: 烧录方式 (硬字幕，所有播放器通用)
"""

import os
import json
import shlex
import subprocess
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal, QProcess


# 转换预设：按分组排列的扁平 list。
# 每项字段说明:
#   group/name        : UI 显示用
#   vcodec/acodec      : FFmpeg 编码器名
#   container          : -f 容器名 (asf/vcd/svcd/dvd/avi/rm)
#   output_ext         : 输出文件扩展名
#   suffix              : 输出文件名后缀 (如 "win98" -> xxx_win98.asf)
#   width/height        : 目标分辨率
#   fps                 : None=保持原帧数; float=强制帧率
#   force_fps           : True 时 UI 锁定 fps 下拉（VCD/DVD 等规格要求）
#   video_bitrate       : 视频码率 kbps
#   audio_bitrate       : 音频码率 kbps
#   audio_sample_rate   : 音频采样率 Hz
#   vtag                : FourCC 标签 (DX50/XVID 等)
#   extra_args          : 额外 ffmpeg 参数列表
#   disabled            : True 时该项不可用（如 RMVB）
#   desc                : 简短说明
PRESETS = [
    # ── Win98 流媒体 ──
    {"name": "推荐 (Win98 兼容)", "group": "Win98 流媒体",
     "vcodec": "wmv2", "acodec": "wmav2",
     "container": "asf", "output_ext": "asf", "suffix": "win98",
     "width": 640, "height": 480, "fps": None, "force_fps": False,
     "video_bitrate": 800, "audio_bitrate": 96, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": [],
     "desc": "640×480 · WMV2+WMA2 in ASF · Pentium 2/3 流畅播放"},
    {"name": "高质量", "group": "Win98 流媒体",
     "vcodec": "wmv2", "acodec": "wmav2",
     "container": "asf", "output_ext": "asf", "suffix": "win98",
     "width": 800, "height": 600, "fps": None, "force_fps": False,
     "video_bitrate": 1500, "audio_bitrate": 128, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": [],
     "desc": "800×600 · 需 P3 800MHz+ 流畅播放"},
    {"name": "最小体积", "group": "Win98 流媒体",
     "vcodec": "wmv2", "acodec": "wmav2",
     "container": "asf", "output_ext": "asf", "suffix": "win98",
     "width": 320, "height": 240, "fps": None, "force_fps": False,
     "video_bitrate": 300, "audio_bitrate": 32, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": [],
     "desc": "320×240 · 极小体积，适合低速硬件/小容量存储"},

    # ── VCD/SVCD (MPEG-1/2) ──
    {"name": "VCD - PAL", "group": "VCD/SVCD 光盘 (MPEG-1/2)",
     "vcodec": "mpeg1video", "acodec": "mp2",
     "container": "vcd", "output_ext": "mpg", "suffix": "vcd",
     "width": 352, "height": 288, "fps": 25.0, "force_fps": True,
     "video_bitrate": 1150, "audio_bitrate": 224, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": ["-g", "18"],
     "desc": "352×288@25fps · 1150k MPEG-1 + 224k MP2 · PAL 标准"},
    {"name": "VCD - NTSC", "group": "VCD/SVCD 光盘 (MPEG-1/2)",
     "vcodec": "mpeg1video", "acodec": "mp2",
     "container": "vcd", "output_ext": "mpg", "suffix": "vcd",
     "width": 352, "height": 240, "fps": 29.97, "force_fps": True,
     "video_bitrate": 1150, "audio_bitrate": 224, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": ["-g", "18"],
     "desc": "352×240@29.97fps · NTSC 标准"},
    {"name": "SVCD - PAL", "group": "VCD/SVCD 光盘 (MPEG-1/2)",
     "vcodec": "mpeg2video", "acodec": "mp2",
     "container": "svcd", "output_ext": "mpg", "suffix": "svcd",
     "width": 480, "height": 576, "fps": 25.0, "force_fps": True,
     "video_bitrate": 2500, "audio_bitrate": 224, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": ["-g", "18"],
     "desc": "480×576@25fps · MPEG-2 + MP2 · PAL 标准"},
    {"name": "SVCD - NTSC", "group": "VCD/SVCD 光盘 (MPEG-1/2)",
     "vcodec": "mpeg2video", "acodec": "mp2",
     "container": "svcd", "output_ext": "mpg", "suffix": "svcd",
     "width": 480, "height": 480, "fps": 29.97, "force_fps": True,
     "video_bitrate": 2500, "audio_bitrate": 224, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": ["-g", "18"],
     "desc": "480×480@29.97fps · NTSC 标准"},

    # ── DVD (MPEG-2 + AC-3) ──
    {"name": "DVD - PAL", "group": "DVD 光盘 (MPEG-2)",
     "vcodec": "mpeg2video", "acodec": "ac3_fixed",
     "container": "dvd", "output_ext": "vob", "suffix": "dvd",
     "width": 720, "height": 576, "fps": 25.0, "force_fps": True,
     "video_bitrate": 6000, "audio_bitrate": 448, "audio_sample_rate": 48000,
     "vtag": None, "extra_args": ["-g", "15"],
     "desc": "720×576@25fps · 6000k MPEG-2 + 448k AC-3 · PAL 标准"},
    {"name": "DVD - NTSC", "group": "DVD 光盘 (MPEG-2)",
     "vcodec": "mpeg2video", "acodec": "ac3_fixed",
     "container": "dvd", "output_ext": "vob", "suffix": "dvd",
     "width": 720, "height": 480, "fps": 29.97, "force_fps": True,
     "video_bitrate": 6000, "audio_bitrate": 448, "audio_sample_rate": 48000,
     "vtag": None, "extra_args": ["-g", "15"],
     "desc": "720×480@29.97fps · NTSC 标准"},

    # ── MPEG-4 网络 (AVI + MP3) ──
    {"name": "DivX (DX50)", "group": "MPEG-4 网络 (AVI)",
     "vcodec": "mpeg4", "acodec": "libmp3lame",
     "container": "avi", "output_ext": "avi", "suffix": "divx",
     "width": 640, "height": 480, "fps": None, "force_fps": False,
     "video_bitrate": 1500, "audio_bitrate": 128, "audio_sample_rate": 44100,
     "vtag": "DX50", "extra_args": ["-g", "300"],
     "desc": "640×480 · MPEG-4 ASP + MP3 · 需 DivX 5 解码器"},
    {"name": "Xvid (XVID)", "group": "MPEG-4 网络 (AVI)",
     "vcodec": "libxvid", "acodec": "libmp3lame",
     "container": "avi", "output_ext": "avi", "suffix": "xvid",
     "width": 640, "height": 480, "fps": None, "force_fps": False,
     "video_bitrate": 1500, "audio_bitrate": 128, "audio_sample_rate": 44100,
     "vtag": "XVID", "extra_args": ["-g", "300"],
     "desc": "需 Xvid 解码器，画质比 DivX 略好"},

    # ── RealNetworks ──
    {"name": "RM (RV10)", "group": "RealNetworks",
     "vcodec": "rv10", "acodec": "real_144",
     "container": "rm", "output_ext": "rm", "suffix": "rm",
     "width": 320, "height": 240, "fps": None, "force_fps": False,
     "video_bitrate": 256, "audio_bitrate": 32, "audio_sample_rate": 8000,
     "vtag": None, "extra_args": [],
     "desc": "RealVideo 1.0 + RealAudio 1.0 · 早期 RM，需 RealPlayer"},
    {"name": "RMVB (不可用)", "group": "RealNetworks",
     "vcodec": None, "acodec": None,
     "container": None, "output_ext": None, "suffix": "rmvb",
     "width": 640, "height": 480, "fps": None, "force_fps": False,
     "video_bitrate": 800, "audio_bitrate": 96, "audio_sample_rate": 44100,
     "vtag": None, "extra_args": [],
     "disabled": True,
     "desc": "FFmpeg 不内置 RV30/RV40 编码器，无法生成真正 RMVB"},
]

# 常见帧率下拉选项：(显示文本, 实际值)。None=保持原帧数
FPS_OPTIONS = [
    ("保持原帧数", None),
    ("23.976 (电影)", 23.976),
    ("24", 24.0),
    ("25 (PAL)", 25.0),
    ("29.97 (NTSC)", 29.97),
    ("30", 30.0),
    ("50", 50.0),
    ("60", 60.0),
]


def find_ffmpeg(script_dir):
    """定位 ffmpeg.exe：优先与脚本同目录的 ffmpeg/ 子文件夹，其次同目录，最后系统 PATH"""
    candidates = [
        script_dir / "ffmpeg" / "ffmpeg.exe",
        script_dir / "ffmpeg.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # 回退：尝试系统 PATH
    import shutil
    sys_ff = shutil.which("ffmpeg")
    return sys_ff  # 可能为 None


def find_ffprobe(script_dir):
    """定位 ffprobe.exe，搜索逻辑同 ffmpeg"""
    candidates = [
        script_dir / "ffmpeg" / "ffprobe.exe",
        script_dir / "ffprobe.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    import shutil
    return shutil.which("ffprobe")


def get_media_duration(ffprobe_path, file_path):
    """通过 ffprobe 获取视频时长（秒），失败返回 None"""
    if not ffprobe_path:
        return None
    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             file_path],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        out = result.stdout.strip()
        # ffprobe 可能返回多行（多个 stream），取第一个有效值
        for line in out.splitlines():
            line = line.strip()
            if line and line != "N/A":
                try:
                    return float(line)
                except ValueError:
                    continue
        return None
    except Exception:
        return None


def find_subtitle_for_video(video_path):
    """自动查找与视频同名的字幕文件（.srt/.ass/.ssa/.sub）"""
    p = Path(video_path)
    base = p.stem
    directory = p.parent
    for ext in [".srt", ".ass", ".ssa", ".sub"]:
        candidate = directory / (base + ext)
        if candidate.exists():
            return str(candidate)
    return None


def build_filter_chain(settings, subtitle_path=None, letterbox=False):
    """构建 -vf 滤镜链。烧录字幕 + 缩放（可选 letterbox 加黑边到 4:3）"""
    width = settings.get("width", 640)
    height = settings.get("height", 480)

    filters = []
    if subtitle_path:
        # 烧录字幕（硬字幕）。使用 Windows 友好字体
        # force_style 参数: 字体、字号、白色
        style = "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2"
        # 注意: subtitles 滤镜的路径需要转义特殊字符
        escaped_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"subtitles='{escaped_path}':force_style='{style}'")

    if letterbox:
        # 保持源视频宽高比缩放到目标矩形内，再补黑边到目标分辨率
        # 适配 4:3 电视：16:9 源会上下加黑边 (pillarbox 反向时左右加)
        # force_original_aspect_ratio=decrease = 等比缩小到能放进目标的最大尺寸
        # pad 后黑边颜色默认黑色 (0x000000)
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    else:
        # 直接强制缩放到目标分辨率（可能拉伸变形，但兼容性最稳）
        filters.append(f"scale={width}:{height}")

    return ",".join(filters) if filters else None


def build_ffmpeg_command(ffmpeg_path, input_file, output_file, settings,
                          subtitle_path=None, letterbox=False):
    """构造 ffmpeg 转换命令行参数列表。支持任意容器/编码器/FourCC/额外参数"""
    cmd = [ffmpeg_path, "-y", "-i", input_file]

    # 滤镜链（letterbox: 4:3 适配加黑边）
    vf = build_filter_chain(settings, subtitle_path, letterbox)
    if vf:
        cmd += ["-vf", vf]

    # 视频编码器
    cmd += [
        "-c:v", settings.get("vcodec", "wmv2"),
        "-b:v", f"{settings.get('video_bitrate', 800)}k",
        "-pix_fmt", "yuv420p",  # 最大兼容性
    ]

    # 帧率：None=保持原帧数（不传 -r）；float=强制
    fps = settings.get("fps")
    if fps is not None:
        # NTSC 29.97 等浮点帧率用分数表达更精确，但 ffmpeg 接受小数
        cmd += ["-r", str(fps)]

    # FourCC 标签 (DivX=DX50 / Xvid=XVID)
    vtag = settings.get("vtag")
    if vtag:
        cmd += ["-vtag", vtag]

    # 音频编码器
    acodec = settings.get("acodec", "wmav2")
    cmd += ["-c:a", acodec]
    # RealAudio 1.0 (real_144) 是固定窄带语音，不接受 -b:a/-ar/-ac 参数
    if acodec not in ("real_144", "ra_144"):
        cmd += [
            "-b:a", f"{settings.get('audio_bitrate', 96)}k",
            "-ar", str(settings.get("audio_sample_rate", 44100)),
            "-ac", "2",
        ]

    # 额外参数 (GOP 等)
    extra = settings.get("extra_args") or []
    cmd += [str(a) for a in extra]

    # 容器输出
    container = settings.get("container", "asf")
    cmd += ["-f", container, output_file]

    return cmd


def parse_ffmpeg_progress(line, total_duration):
    """从 ffmpeg stderr 行解析进度百分比。返回百分比或 None"""
    if total_duration is None or total_duration <= 0:
        return None
    # 形如: "frame=  123 fps= 25 q=2.0 size=    256kB time=00:00:04.92 ..."
    # 找 time= 字段
    if "time=" not in line:
        return None
    try:
        idx = line.index("time=") + 5
        rest = line[idx:].strip()
        # 截取到第一个空格
        time_str = rest.split()[0]
        # 格式 HH:MM:SS.xx 或 SS.xx
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            seconds = int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            seconds = int(m) * 60 + float(s)
        else:
            seconds = float(time_str)
        pct = int(seconds / total_duration * 100)
        return max(0, min(100, pct))
    except (ValueError, IndexError):
        return None


class ConversionWorker(QThread):
    """
    转换工作线程。
    在独立的 QProcess 中运行 ffmpeg，实时解析 stderr 输出进度。
    """
    file_started = pyqtSignal(str)              # 文件名
    progress = pyqtSignal(str, int)             # 文件名, 百分比
    file_finished = pyqtSignal(str, bool, str) # 文件名, 成功?, 错误信息
    log_line = pyqtSignal(str)                  # ffmpeg 原始输出
    all_done = pyqtSignal()
    ffmpeg_missing = pyqtSignal()                # 找不到 ffmpeg

    def __init__(self, files, settings, ffmpeg_path, ffprobe_path,
                 output_dir, burn_subtitles=True, letterbox=True,
                 parent=None):
        super().__init__(parent)
        self.files = files                  # list[str]
        self.settings = settings            # dict
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        self.output_dir = output_dir
        self.burn_subtitles = burn_subtitles
        self.letterbox = letterbox
        self._cancel = False
        self._process = None

    def cancel(self):
        self._cancel = True
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass

    def run(self):
        if not self.ffmpeg or not os.path.exists(self.ffmpeg):
            self.ffmpeg_missing.emit()
            self.all_done.emit()
            return

        for file_path in self.files:
            if self._cancel:
                break
            self._convert_one(file_path)

        self.all_done.emit()

    def _convert_one(self, input_file):
        name = os.path.basename(input_file)
        self.file_started.emit(name)
        self.log_line.emit(f"=== 开始转换: {name} ===")

        # 1. 获取时长
        duration = get_media_duration(self.ffprobe, input_file)
        if duration:
            self.log_line.emit(f"  时长: {duration:.1f} 秒")

        # 2. 查找字幕
        subtitle = None
        if self.burn_subtitles:
            subtitle = find_subtitle_for_video(input_file)
            if subtitle:
                self.log_line.emit(f"  发现字幕: {os.path.basename(subtitle)}")

        # 3. 构造输出路径（文件后缀和扩展名由 preset 决定）
        out_dir = self.output_dir or os.path.dirname(input_file)
        os.makedirs(out_dir, exist_ok=True)
        suffix = self.settings.get("suffix") or "out"
        ext = self.settings.get("output_ext") or "asf"
        base = Path(input_file).stem + "_" + suffix
        output_file = os.path.join(out_dir, base + "." + ext)

        # 4. 构造命令
        cmd = build_ffmpeg_command(
            self.ffmpeg, input_file, output_file, self.settings,
            subtitle, self.letterbox
        )
        self.log_line.emit("  命令: " + " ".join(shlex.quote(c) for c in cmd))

        # 5. 启动 QProcess（合并 stderr 到 stdout 便于解析进度）
        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.MergedChannels)

        last_pct = -1

        def drain_output():
            """读取所有可用 stdout/stderr 数据并解析进度"""
            nonlocal last_pct
            data = bytes(self._process.readAllStandardOutput()).decode(
                "utf-8", errors="replace"
            )
            for line in data.splitlines():
                line = line.strip()
                if not line:
                    continue
                self.log_line.emit(line)
                pct = parse_ffmpeg_progress(line, duration)
                if pct is not None and pct != last_pct:
                    last_pct = pct
                    self.progress.emit(name, pct)

        # 6. 启动并轮询
        self._process.start(cmd[0], cmd[1:])
        if not self._process.waitForStarted(5000):
            self.file_finished.emit(name, False, "无法启动 ffmpeg")
            return

        # QThread.run() 默认无事件循环，信号不会触发，故用轮询读取 stdout
        while self._process.state() == QProcess.Running:
            if self._cancel:
                self._process.kill()
                self._process.waitForFinished(2000)
                break
            # 阻塞等待最多 100ms 直到有数据可读；返回后立即把缓冲区排空
            self._process.waitForReadyRead(100)
            drain_output()

        # 进程已退出，最后再排一次尾巴
        drain_output()

        exit_code = self._process.exitCode() if self._process else -1
        if self._cancel:
            self.file_finished.emit(name, False, "已取消")
            # 清理半成品
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
            except OSError:
                pass
            return

        if exit_code == 0 and os.path.exists(output_file):
            self.progress.emit(name, 100)
            self.file_finished.emit(name, True, output_file)
            self.log_line.emit(f"=== 完成: {os.path.basename(output_file)} ===")
        else:
            self.file_finished.emit(name, False, f"ffmpeg 退出码: {exit_code}")
            self.log_line.emit(f"=== 失败: {name} (exit={exit_code}) ===")
