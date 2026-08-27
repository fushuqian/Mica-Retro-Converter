using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;

namespace Win98Converter.Core;

public sealed class ConversionResult
{
    public int ExitCode { get; init; }
    public string OutputFile { get; init; } = "";
    public bool Cancelled { get; init; }
}

public static class ConversionEngine
{
    public static string? FindFfmpeg(string baseDir) => FindTool(baseDir, "ffmpeg.exe");

    public static string? FindFfprobe(string baseDir) => FindTool(baseDir, "ffprobe.exe");

    public static string? FindTool(string baseDir, string toolName)
    {
        if (File.Exists(Path.Combine(baseDir, "ffmpeg", toolName)))
            return Path.Combine(baseDir, "ffmpeg", toolName);
        if (File.Exists(Path.Combine(baseDir, toolName)))
            return Path.Combine(baseDir, toolName);

        var dir = new DirectoryInfo(baseDir);
        for (int i = 0; i < 5 && dir.Parent is not null; i++)
        {
            dir = dir.Parent;
            string candidate = Path.Combine(dir.FullName, "ffmpeg", toolName);
            if (File.Exists(candidate))
                return candidate;
        }

        return FindOnPath(toolName);
    }

    private static string? FindOnPath(string toolName)
    {
        string pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in pathVar.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            try
            {
                string full = Path.Combine(dir.Trim(), toolName);
                if (File.Exists(full))
                    return full;
            }
            catch
            {
            }
        }
        return null;
    }

    public static async Task<double?> GetMediaDurationAsync(string? ffprobePath, string filePath)
    {
        if (string.IsNullOrEmpty(ffprobePath) || !File.Exists(ffprobePath))
            return null;
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = ffprobePath,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            foreach (string a in new[] { "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filePath })
                psi.ArgumentList.Add(a);

            using var proc = Process.Start(psi);
            if (proc is null)
                return null;

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var outTask = proc.StandardOutput.ReadToEndAsync(cts.Token);
            var errTask = proc.StandardError.ReadToEndAsync(cts.Token);
            await proc.WaitForExitAsync(cts.Token);
            string output = await outTask;
            _ = await errTask;

            foreach (string raw in output.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line == "N/A")
                    continue;
                if (double.TryParse(line, NumberStyles.Float, CultureInfo.InvariantCulture, out double d))
                    return d;
            }
            return null;
        }
        catch
        {
            return null;
        }
    }

    public static string? FindSubtitleForVideo(string videoPath)
    {
        string dir = Path.GetDirectoryName(videoPath) ?? ".";
        string stem = Path.GetFileNameWithoutExtension(videoPath);
        foreach (string ext in new[] { ".srt", ".ass", ".ssa", ".sub" })
        {
            string candidate = Path.Combine(dir, stem + ext);
            if (File.Exists(candidate))
                return candidate;
        }
        return null;
    }

    public static string? BuildFilterChain(Preset settings, string? subtitlePath, bool letterbox)
    {
        int width = settings.Width > 0 ? settings.Width : 640;
        int height = settings.Height > 0 ? settings.Height : 480;

        var filters = new List<string>();
        if (!string.IsNullOrEmpty(subtitlePath))
        {
            const string style = "FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2";
            string escapedPath = subtitlePath.Replace("\\", "/").Replace(":", "\\:");
            filters.Add($"subtitles='{escapedPath}':force_style='{style}'");
        }

        if (letterbox)
        {
            filters.Add(
                $"scale={width}:{height}:force_original_aspect_ratio=decrease," +
                $"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black");
        }
        else
        {
            filters.Add($"scale={width}:{height}");
        }

        return filters.Count > 0 ? string.Join(",", filters) : null;
    }

    public static List<string> BuildFfmpegCommand(string ffmpegPath, string inputFile, string outputFile,
        Preset settings, string? subtitlePath = null, bool letterbox = false)
    {
        var cmd = new List<string> { ffmpegPath, "-y", "-i", inputFile };

        string? vf = BuildFilterChain(settings, subtitlePath, letterbox);
        if (vf is not null)
        {
            cmd.Add("-vf");
            cmd.Add(vf);
        }

        cmd.AddRange(new[] { "-c:v", settings.VideoCodec, "-b:v", $"{settings.VideoBitrate}k", "-pix_fmt", "yuv420p" });

        if (settings.Fps.HasValue)
        {
            cmd.Add("-r");
            cmd.Add(settings.Fps.Value.ToString(CultureInfo.InvariantCulture));
        }

        if (!string.IsNullOrEmpty(settings.VideoTag))
        {
            cmd.Add("-vtag");
            cmd.Add(settings.VideoTag);
        }

        cmd.Add("-c:a");
        cmd.Add(settings.AudioCodec);
        if (settings.AudioCodec is not ("real_144" or "ra_144"))
        {
            cmd.AddRange(new[]
            {
                "-b:a", $"{settings.AudioBitrate}k",
                "-ar", settings.AudioSampleRate.ToString(CultureInfo.InvariantCulture),
                "-ac", "2",
            });
        }

        foreach (string a in settings.ExtraArgs)
            cmd.Add(a);

        cmd.Add("-f");
        cmd.Add(settings.Container);
        cmd.Add(outputFile);

        return cmd;
    }

    public static int? ParseFfmpegProgress(string line, double? totalDuration)
    {
        if (totalDuration is null or <= 0)
            return null;
        int idx = line.IndexOf("time=", StringComparison.Ordinal);
        if (idx < 0)
            return null;
        try
        {
            string rest = line[(idx + 5)..].Trim();
            string timeStr = rest.Split(' ', StringSplitOptions.RemoveEmptyEntries)[0];
            string[] parts = timeStr.Split(':');
            double seconds;
            if (parts.Length == 3)
            {
                seconds = int.Parse(parts[0], CultureInfo.InvariantCulture) * 3600
                        + int.Parse(parts[1], CultureInfo.InvariantCulture) * 60
                        + double.Parse(parts[2], CultureInfo.InvariantCulture);
            }
            else if (parts.Length == 2)
            {
                seconds = int.Parse(parts[0], CultureInfo.InvariantCulture) * 60
                        + double.Parse(parts[1], CultureInfo.InvariantCulture);
            }
            else
            {
                seconds = double.Parse(timeStr, CultureInfo.InvariantCulture);
            }
            int pct = (int)(seconds / totalDuration.Value * 100);
            return Math.Clamp(pct, 0, 100);
        }
        catch (Exception)
        {
            return null;
        }
    }

    public static string ResolveOutputPath(string inputFile, Preset settings, string? outputDir)
    {
        string outDir = string.IsNullOrWhiteSpace(outputDir)
            ? Path.GetDirectoryName(inputFile) ?? "."
            : outputDir;
        Directory.CreateDirectory(outDir);
        string suffix = string.IsNullOrEmpty(settings.Suffix) ? "out" : settings.Suffix;
        string ext = string.IsNullOrEmpty(settings.OutputExt) ? "asf" : settings.OutputExt;
        string baseName = Path.GetFileNameWithoutExtension(inputFile) + "_" + suffix;
        return Path.Combine(outDir, baseName + "." + ext);
    }

    public static async Task<ConversionResult> ConvertAsync(
        string ffmpegPath, string? ffprobePath, string inputFile, Preset settings,
        string? outputDir, bool burnSubtitles, bool letterbox,
        Action<int>? onProgress, Action<string>? onLog, CancellationToken ct)
    {
        string outputFile = ResolveOutputPath(inputFile, settings, outputDir);
        string? subtitlePath = burnSubtitles ? FindSubtitleForVideo(inputFile) : null;
        if (burnSubtitles && subtitlePath is not null)
            onLog?.Invoke($"[字幕] 发现同名字幕: {subtitlePath}");

        List<string> cmd = BuildFfmpegCommand(ffmpegPath, inputFile, outputFile, settings, subtitlePath, letterbox);
        onLog?.Invoke("$ \"" + string.Join("\" \"", cmd) + "\"");

        double? duration = await GetMediaDurationAsync(ffprobePath, inputFile);

        var psi = new ProcessStartInfo
        {
            FileName = ffmpegPath,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardErrorEncoding = Encoding.UTF8,
            CreateNoWindow = true,
        };
        for (int i = 1; i < cmd.Count; i++)
            psi.ArgumentList.Add(cmd[i]);

        using var proc = new Process { StartInfo = psi };
        proc.Start();

        using var killReg = ct.Register(() =>
        {
            try
            {
                if (!proc.HasExited)
                    proc.Kill(true);
            }
            catch
            {
            }
        });

        var stdoutTask = proc.StandardOutput.ReadToEndAsync(ct);

        var tail = new Queue<string>();
        try
        {
            string? line;
            while ((line = await proc.StandardError.ReadLineAsync(ct)) is not null)
            {
                tail.Enqueue(line);
                while (tail.Count > 12)
                    tail.Dequeue();
                int? pct = ParseFfmpegProgress(line, duration);
                if (pct.HasValue)
                    onProgress?.Invoke(pct.Value);
            }
        }
        catch (OperationCanceledException)
        {
        }

        try
        {
            await proc.WaitForExitAsync(CancellationToken.None);
        }
        catch
        {
        }
        try
        {
            _ = await stdoutTask;
        }
        catch
        {
        }

        bool cancelled = ct.IsCancellationRequested;
        if (!cancelled && proc.ExitCode != 0)
        {
            onLog?.Invoke($"[错误] ffmpeg 退出码 {proc.ExitCode}，最后日志:");
            foreach (string l in tail)
                onLog?.Invoke("  " + l);
        }

        return new ConversionResult
        {
            ExitCode = proc.ExitCode,
            OutputFile = outputFile,
            Cancelled = cancelled,
        };
    }
}
