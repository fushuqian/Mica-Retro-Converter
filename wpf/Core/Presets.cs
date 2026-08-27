namespace Win98Converter.Core;

public static class Presets
{
    public static IReadOnlyList<Preset> All { get; } = new List<Preset>
    {
        new()
        {
            Name = "推荐 (Win98 兼容)", Group = "Win98 流媒体",
            VideoCodec = "wmv2", AudioCodec = "wmav2",
            Container = "asf", OutputExt = "asf", Suffix = "win98",
            Width = 640, Height = 480, Fps = null, ForceFps = false,
            VideoBitrate = 800, AudioBitrate = 96, AudioSampleRate = 44100,
            Desc = "640×480 · WMV2+WMA2 in ASF · Pentium 2/3 流畅播放",
        },
        new()
        {
            Name = "高质量", Group = "Win98 流媒体",
            VideoCodec = "wmv2", AudioCodec = "wmav2",
            Container = "asf", OutputExt = "asf", Suffix = "win98",
            Width = 800, Height = 600, Fps = null, ForceFps = false,
            VideoBitrate = 1500, AudioBitrate = 128, AudioSampleRate = 44100,
            Desc = "800×600 · 需 P3 800MHz+ 流畅播放",
        },
        new()
        {
            Name = "最小体积", Group = "Win98 流媒体",
            VideoCodec = "wmv2", AudioCodec = "wmav2",
            Container = "asf", OutputExt = "asf", Suffix = "win98",
            Width = 320, Height = 240, Fps = null, ForceFps = false,
            VideoBitrate = 300, AudioBitrate = 32, AudioSampleRate = 44100,
            Desc = "320×240 · 极小体积，适合低速硬件/小容量存储",
        },

        new()
        {
            Name = "VCD - PAL", Group = "VCD/SVCD 光盘 (MPEG-1/2)",
            VideoCodec = "mpeg1video", AudioCodec = "mp2",
            Container = "vcd", OutputExt = "mpg", Suffix = "vcd",
            Width = 352, Height = 288, Fps = 25.0, ForceFps = true,
            VideoBitrate = 1150, AudioBitrate = 224, AudioSampleRate = 44100,
            ExtraArgs = new[] { "-g", "15" },
            Desc = "352×288@25fps · 1150k MPEG-1 + 224k MP2 · PAL 标准",
        },
        new()
        {
            Name = "VCD - NTSC", Group = "VCD/SVCD 光盘 (MPEG-1/2)",
            VideoCodec = "mpeg1video", AudioCodec = "mp2",
            Container = "vcd", OutputExt = "mpg", Suffix = "vcd",
            Width = 352, Height = 240, Fps = 29.97, ForceFps = true,
            VideoBitrate = 1150, AudioBitrate = 224, AudioSampleRate = 44100,
            ExtraArgs = new[] { "-g", "18" },
            Desc = "352×240@29.97fps · NTSC 标准",
        },
        new()
        {
            Name = "SVCD - PAL", Group = "VCD/SVCD 光盘 (MPEG-1/2)",
            VideoCodec = "mpeg2video", AudioCodec = "mp2",
            Container = "svcd", OutputExt = "mpg", Suffix = "svcd",
            Width = 480, Height = 576, Fps = 25.0, ForceFps = true,
            VideoBitrate = 2500, AudioBitrate = 224, AudioSampleRate = 44100,
            ExtraArgs = new[] { "-g", "18" },
            Desc = "480×576@25fps · MPEG-2 + MP2 · PAL 标准",
        },
        new()
        {
            Name = "SVCD - NTSC", Group = "VCD/SVCD 光盘 (MPEG-1/2)",
            VideoCodec = "mpeg2video", AudioCodec = "mp2",
            Container = "svcd", OutputExt = "mpg", Suffix = "svcd",
            Width = 480, Height = 480, Fps = 29.97, ForceFps = true,
            VideoBitrate = 2500, AudioBitrate = 224, AudioSampleRate = 44100,
            ExtraArgs = new[] { "-g", "18" },
            Desc = "480×480@29.97fps · NTSC 标准",
        },

        new()
        {
            Name = "DVD - PAL", Group = "DVD 光盘 (MPEG-2)",
            VideoCodec = "mpeg2video", AudioCodec = "ac3_fixed",
            Container = "dvd", OutputExt = "vob", Suffix = "dvd",
            Width = 720, Height = 576, Fps = 25.0, ForceFps = true,
            VideoBitrate = 6000, AudioBitrate = 448, AudioSampleRate = 48000,
            ExtraArgs = new[] { "-g", "15" },
            Desc = "720×576@25fps · 6000k MPEG-2 + 448k AC-3 · PAL 标准",
        },
        new()
        {
            Name = "DVD - NTSC", Group = "DVD 光盘 (MPEG-2)",
            VideoCodec = "mpeg2video", AudioCodec = "ac3_fixed",
            Container = "dvd", OutputExt = "vob", Suffix = "dvd",
            Width = 720, Height = 480, Fps = 29.97, ForceFps = true,
            VideoBitrate = 6000, AudioBitrate = 448, AudioSampleRate = 48000,
            ExtraArgs = new[] { "-g", "15" },
            Desc = "720×480@29.97fps · NTSC 标准",
        },

        new()
        {
            Name = "DivX (DX50)", Group = "MPEG-4 网络 (AVI)",
            VideoCodec = "mpeg4", AudioCodec = "libmp3lame",
            Container = "avi", OutputExt = "avi", Suffix = "divx",
            Width = 640, Height = 480, Fps = null, ForceFps = false,
            VideoBitrate = 1500, AudioBitrate = 128, AudioSampleRate = 44100,
            VideoTag = "DX50", ExtraArgs = new[] { "-g", "300" },
            Desc = "640×480 · MPEG-4 ASP + MP3 · 需 DivX 5 解码器",
        },
        new()
        {
            Name = "Xvid (XVID)", Group = "MPEG-4 网络 (AVI)",
            VideoCodec = "libxvid", AudioCodec = "libmp3lame",
            Container = "avi", OutputExt = "avi", Suffix = "xvid",
            Width = 640, Height = 480, Fps = null, ForceFps = false,
            VideoBitrate = 1500, AudioBitrate = 128, AudioSampleRate = 44100,
            VideoTag = "XVID", ExtraArgs = new[] { "-g", "300" },
            Desc = "需 Xvid 解码器，画质比 DivX 略好",
        },

        new()
        {
            Name = "RM (RV10)", Group = "RealNetworks",
            VideoCodec = "rv10", AudioCodec = "real_144",
            Container = "rm", OutputExt = "rm", Suffix = "rm",
            Width = 320, Height = 240, Fps = null, ForceFps = false,
            VideoBitrate = 256, AudioBitrate = 32, AudioSampleRate = 8000,
            Desc = "RealVideo 1.0 + RealAudio 1.0 · 早期 RM，需 RealPlayer",
        },
        new()
        {
            Name = "RMVB (不可用)", Group = "RealNetworks",
            Container = "", OutputExt = "", Suffix = "rmvb",
            Width = 640, Height = 480, Fps = null, ForceFps = false,
            VideoBitrate = 800, AudioBitrate = 96, AudioSampleRate = 44100,
            Disabled = true,
            Desc = "FFmpeg 不内置 RV30/RV40 编码器，无法生成真正 RMVB",
        },
    };

    public static IReadOnlyList<(string Label, double? Value)> FpsOptions { get; } = new (string, double?)[]
    {
        ("保持原帧数", null),
        ("23.976 (电影)", 23.976),
        ("24", 24.0),
        ("25 (PAL)", 25.0),
        ("29.97 (NTSC)", 29.97),
        ("30", 30.0),
        ("50", 50.0),
        ("60", 60.0),
    };

    public static IReadOnlyCollection<string> SupportedExts { get; } = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".mpg", ".mpeg",
        ".m4v", ".webm", ".ts", ".m2ts", ".vob", ".3gp", ".rm", ".rmvb",
    };
}
