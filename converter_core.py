"""
converter_core.py - 转换核心纯函数库（无 UI 依赖，可被 FastAPI / CLI / sidecar 共用）

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
import sys
from pathlib import Path


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

# 常见帧率选项：(显示文本, 实际值)。None=保持原帧数
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

SUPPORTED_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".mpg", ".mpeg",
    ".m4v", ".webm", ".ts", ".m2ts", ".vob", ".3gp", ".rm", ".rmvb",
}


def find_ffmpeg(script_dir: Path) -> str | None:
    """定位 ffmpeg.exe：优先脚本同目录 ffmpeg/ 子文件夹，其次同目录，最后系统 PATH"""
    candidates = [
        script_dir / "ffmpeg" / "ffmpeg.exe",
        script_dir / "ffmpeg.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    import shutil
    return shutil.which("ffmpeg")


def find_ffprobe(script_dir: Path) -> str | None:
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


def get_media_duration(ffprobe_path: str, file_path: str) -> float | None:
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


def probe_video_info(ffprobe_path: str, file_path: str) -> dict:
    """通过 ffprobe 获取视频元数据：视频/音频编码、分辨率、帧率、码率、时长等。
    返回 dict，失败时返回含 error 键的 dict。"""
    info = {
        "video_codec": None, "audio_codec": None,
        "width": None, "height": None,
        "fps": None, "bitrate": None,
        "duration": None, "audio_bitrate": None,
        "aspect_ratio": None,
    }
    if not ffprobe_path:
        info["error"] = "ffprobe not found"
        return info
    try:
        result = subprocess.run(
            [ffprobe_path, "-v", "quiet",
             "-print_format", "json",
             "-show_streams",
             "-show_format",
             file_path],
            capture_output=True, text=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            info["error"] = result.stderr.strip() or "ffprobe failed"
            return info
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        # duration
        dur = fmt.get("duration")
        if dur:
            try:
                info["duration"] = round(float(dur), 1)
            except (ValueError, TypeError):
                pass

        # video stream
        vs = None
        for s in streams:
            if s.get("codec_type") == "video":
                vs = s
                break
        if vs:
            info["video_codec"] = vs.get("codec_name")
            info["width"] = int(vs.get("width", 0)) or None
            info["height"] = int(vs.get("height", 0)) or None
            # display aspect ratio (e.g. "4:3", "16:9")
            dar = vs.get("display_aspect_ratio")
            if dar:
                info["aspect_ratio"] = dar
            # fps
            fps_str = vs.get("r_frame_rate", "")
            if fps_str and "/" in fps_str:
                try:
                    num, den = fps_str.split("/")
                    if float(den) != 0:
                        info["fps"] = round(float(num) / float(den), 2)
                except (ValueError, ZeroDivisionError):
                    pass
            # video bitrate
            vbr = vs.get("bit_rate")
            if vbr:
                try:
                    info["bitrate"] = int(vbr)
                except (ValueError, TypeError):
                    pass

        # audio stream
        for s in streams:
            if s.get("codec_type") == "audio":
                info["audio_codec"] = s.get("codec_name")
                abr = s.get("bit_rate")
                if abr:
                    try:
                        info["audio_bitrate"] = int(abr)
                    except (ValueError, TypeError):
                        pass
                break

        # fallback: format-level bitrate if stream-level not found
        if not info.get("bitrate") and fmt.get("bit_rate"):
            try:
                info["bitrate"] = int(fmt["bit_rate"])
            except (ValueError, TypeError):
                pass

    except subprocess.TimeoutExpired:
        info["error"] = "ffprobe timed out"
    except Exception as e:
        info["error"] = str(e)
    return info


def find_subtitle_for_video(video_path: str) -> str | None:
    """自动查找与视频同名的字幕文件（.srt/.ass/.ssa/.sub）"""
    p = Path(video_path)
    base = p.stem
    directory = p.parent
    for ext in [".srt", ".ass", ".ssa", ".sub"]:
        candidate = directory / (base + ext)
        if candidate.exists():
            return str(candidate)
    return None


def build_filter_chain(settings: dict, subtitle_path: str | None = None, letterbox: bool = False) -> str | None:
    """构建 -vf 滤镜链。烧录字幕 + 缩放（可选 letterbox 加黑边到 4:3）"""
    width = settings.get("width", 640)
    height = settings.get("height", 480)

    filters = []
    if subtitle_path:
        style = "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2"
        escaped_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"subtitles='{escaped_path}':force_style='{style}'")

    if letterbox:
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    else:
        filters.append(f"scale={width}:{height}")

    return ",".join(filters) if filters else None


def build_ffmpeg_command(ffmpeg_path: str, input_file: str, output_file: str, settings: dict,
                         subtitle_path: str | None = None, letterbox: bool = False) -> list[str]:
    """构造 ffmpeg 转换命令行参数列表。支持任意容器/编码器/FourCC/额外参数"""
    cmd = [ffmpeg_path, "-y", "-i", input_file]

    vf = build_filter_chain(settings, subtitle_path, letterbox)
    if vf:
        cmd += ["-vf", vf]

    cmd += [
        "-c:v", settings.get("vcodec", "wmv2"),
        "-b:v", f"{settings.get('video_bitrate', 800)}k",
        "-pix_fmt", "yuv420p",
    ]

    fps = settings.get("fps")
    if fps is not None:
        cmd += ["-r", str(fps)]

    vtag = settings.get("vtag")
    if vtag:
        cmd += ["-vtag", vtag]

    acodec = settings.get("acodec", "wmav2")
    cmd += ["-c:a", acodec]
    if acodec not in ("real_144", "ra_144"):
        cmd += [
            "-b:a", f"{settings.get('audio_bitrate', 96)}k",
            "-ar", str(settings.get("audio_sample_rate", 44100)),
            "-ac", "2",
        ]

    extra = settings.get("extra_args") or []
    cmd += [str(a) for a in extra]

    container = settings.get("container", "asf")
    cmd += ["-f", container, output_file]

    return cmd


def parse_ffmpeg_progress(line: str, total_duration: float | None) -> int | None:
    """从 ffmpeg stderr 行解析进度百分比。返回百分比或 None"""
    if total_duration is None or total_duration <= 0:
        return None
    if "time=" not in line:
        return None
    try:
        idx = line.index("time=") + 5
        rest = line[idx:].strip()
        time_str = rest.split()[0]
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


def resolve_output_path(input_file: str, settings: dict, output_dir: str | None) -> str:
    """根据输入路径、preset、输出目录，计算最终输出文件路径"""
    out_dir = output_dir or os.path.dirname(input_file)
    os.makedirs(out_dir, exist_ok=True)
    suffix = settings.get("suffix") or "out"
    ext = settings.get("output_ext") or "asf"
    base = Path(input_file).stem + "_" + suffix
    return os.path.join(out_dir, base + "." + ext)
