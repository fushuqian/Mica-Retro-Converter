using System.Diagnostics;
using System.IO;

namespace Win98Converter.Core;

public static class SelfTest
{
    private static readonly List<string> LogLines = new();
    private static string _logFile = "";

    public static async Task<int> RunAsync()
    {
        _logFile = Path.Combine(Path.GetTempPath(), "win98_selftest.log");
        try
        {
            return await RunCoreAsync();
        }
        catch (Exception ex)
        {
            Log("未处理异常: " + ex);
            return 1;
        }
        finally
        {
            try
            {
                File.WriteAllText(_logFile, string.Join(Environment.NewLine, LogLines));
            }
            catch
            {
            }
        }
    }

    private static async Task<int> RunCoreAsync()
    {
        string baseDir = AppContext.BaseDirectory;
        Presets.Initialize(baseDir);
        string? ffmpeg = ConversionEngine.FindFfmpeg(baseDir);
        string? ffprobe = ConversionEngine.FindFfprobe(baseDir);
        Log("ffmpeg : " + (ffmpeg ?? "未找到"));
        Log("ffprobe: " + (ffprobe ?? "未找到"));
        if (ffmpeg is null)
        {
            Log("FAIL: 缺少 ffmpeg");
            return 2;
        }

        string workDir = Path.Combine(Path.GetTempPath(), "win98_selftest");
        Directory.CreateDirectory(workDir);
        string source = Path.Combine(workDir, "source.mp4");
        if (File.Exists(source))
            File.Delete(source);

        int genCode = await RunSilentAsync(new List<string>
        {
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc2=duration=2:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=duration=2:frequency=440",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", source,
        });
        if (genCode != 0 || !File.Exists(source))
        {
            Log("FAIL: 生成测试源视频失败");
            return 3;
        }
        Log("测试源视频已生成: " + source);

        Preset preset = Presets.All[0];
        var result = await ConversionEngine.ConvertAsync(
            ffmpeg, ffprobe, source, preset, workDir,
            burnSubtitles: false, letterbox: true,
            onProgress: _ => { }, onLog: Log, ct: CancellationToken.None);
        if (result.ExitCode != 0)
        {
            Log($"FAIL: 转换失败，ExitCode={result.ExitCode}");
            return 4;
        }
        Log("转换完成: " + result.OutputFile);

        if (ffprobe is null)
        {
            Log("WARN: 无 ffprobe，跳过编码校验");
            return 0;
        }

        string streams = await ProbeAsync(ffprobe, "stream=codec_name", result.OutputFile);
        string format = await ProbeAsync(ffprobe, "format=format_name", result.OutputFile);
        Log("streams: " + streams.Trim());
        Log("format : " + format.Trim());

        bool ok = streams.Contains("wmv2") && streams.Contains("wmav2") && format.Contains("asf");
        Log(ok ? "PASS" : "FAIL: 编码/容器与预期不符");
        return ok ? 0 : 5;
    }

    private static void Log(string line)
    {
        Console.WriteLine("[SelfTest] " + line);
        LogLines.Add("[SelfTest] " + line);
    }

    private static async Task<int> RunSilentAsync(List<string> cmd)
    {
        var psi = new ProcessStartInfo
        {
            FileName = cmd[0],
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        for (int i = 1; i < cmd.Count; i++)
            psi.ArgumentList.Add(cmd[i]);

        using var p = Process.Start(psi);
        if (p is null)
            return -1;
        var outTask = p.StandardOutput.ReadToEndAsync();
        var errTask = p.StandardError.ReadToEndAsync();
        await p.WaitForExitAsync();
        _ = await outTask;
        _ = await errTask;
        return p.ExitCode;
    }

    private static async Task<string> ProbeAsync(string ffprobe, string entries, string file)
    {
        var psi = new ProcessStartInfo
        {
            FileName = ffprobe,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        foreach (string a in new[] { "-v", "error", "-show_entries", entries, "-of", "default=noprint_wrappers=1", file })
            psi.ArgumentList.Add(a);

        using var p = Process.Start(psi);
        if (p is null)
            return "";
        var outTask = p.StandardOutput.ReadToEndAsync();
        var errTask = p.StandardError.ReadToEndAsync();
        await p.WaitForExitAsync();
        string stdout = await outTask;
        _ = await errTask;
        return stdout;
    }
}
