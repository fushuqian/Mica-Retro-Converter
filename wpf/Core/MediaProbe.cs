using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace Win98Converter.Core;

public sealed record MediaInfo
{
    public string? VideoCodec { get; init; }
    public string? AudioCodec { get; init; }
    public int Width { get; init; }
    public int Height { get; init; }
    public double? Fps { get; init; }
    public long? Bitrate { get; init; }
    public double? Duration { get; init; }
    public string Summary { get; init; } = "";
    public string? Error { get; init; }
}

public static class MediaProbe
{
    public static async Task<MediaInfo?> ProbeAsync(string? ffprobePath, string filePath, CancellationToken ct = default)
    {
        if (string.IsNullOrEmpty(ffprobePath) || !File.Exists(ffprobePath) || !File.Exists(filePath))
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
            foreach (string a in new[] { "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", filePath })
                psi.ArgumentList.Add(a);

            using var proc = Process.Start(psi);
            if (proc is null)
                return null;

            using var timeoutCts = new CancellationTokenSource(TimeSpan.FromSeconds(20));
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token);

            var outTask = proc.StandardOutput.ReadToEndAsync(linked.Token);
            var errTask = proc.StandardError.ReadToEndAsync(linked.Token);
            await proc.WaitForExitAsync(linked.Token);
            string json = await outTask;
            _ = await errTask;

            if (proc.ExitCode != 0 || string.IsNullOrWhiteSpace(json))
                return new MediaInfo { Error = "ffprobe 无输出" };

            return Parse(json);
        }
        catch (OperationCanceledException)
        {
            return new MediaInfo { Error = "解析超时" };
        }
        catch (Exception ex)
        {
            return new MediaInfo { Error = ex.Message };
        }
    }

    private static MediaInfo Parse(string json)
    {
        var opts = new JsonDocumentOptions { AllowTrailingCommas = true };
        using var doc = JsonDocument.Parse(json, opts);
        var root = doc.RootElement;

        string? vCodec = null, aCodec = null;
        int width = 0, height = 0;
        double? fps = null;
        long? vBitrate = null, aBitrate = null;

        if (root.TryGetProperty("streams", out var streams))
        {
            foreach (var s in streams.EnumerateArray())
            {
                string type = GetString(s, "codec_type") ?? "";
                if (type == "video" && vCodec is null)
                {
                    vCodec = GetString(s, "codec_name");
                    width = GetInt(s, "width");
                    height = GetInt(s, "height");
                    fps = ParseFraction(GetString(s, "r_frame_rate"));
                    vBitrate = GetLong(s, "bit_rate");
                }
                else if (type == "audio" && aCodec is null)
                {
                    aCodec = GetString(s, "codec_name");
                    aBitrate = GetLong(s, "bit_rate");
                }
            }
        }

        double? duration = null;
        long? fmtBitrate = null;
        if (root.TryGetProperty("format", out var fmt))
        {
            duration = ParseDouble(GetString(fmt, "duration"));
            fmtBitrate = GetLong(fmt, "bit_rate");
        }

        long? totalBitrate = vBitrate ?? fmtBitrate;

        var parts = new List<string>();
        if (width > 0 && height > 0)
            parts.Add($"{width}×{height}");
        if (vCodec is not null)
            parts.Add(vCodec);
        if (fps is > 0)
            parts.Add(fps.Value.ToString("0.##", CultureInfo.InvariantCulture) + "fps");
        if (totalBitrate is > 0)
            parts.Add(FormatBitrate(totalBitrate.Value));
        if (duration is > 0)
            parts.Add(FormatDuration(duration.Value));
        if (aCodec is not null)
            parts.Add(aCodec + (aBitrate is > 0 ? " " + FormatBitrate(aBitrate.Value) : ""));

        return new MediaInfo
        {
            VideoCodec = vCodec,
            AudioCodec = aCodec,
            Width = width,
            Height = height,
            Fps = fps,
            Bitrate = totalBitrate,
            Duration = duration,
            Summary = parts.Count > 0 ? string.Join(" · ", parts) : "无媒体流",
        };
    }

    private static string? GetString(JsonElement e, string name)
    {
        if (!e.TryGetProperty(name, out var v))
            return null;
        return v.ValueKind switch
        {
            JsonValueKind.String => v.GetString(),
            JsonValueKind.Number => v.GetRawText(),
            _ => null,
        };
    }

    private static int GetInt(JsonElement e, string name) =>
        int.TryParse(GetString(e, name), NumberStyles.Integer, CultureInfo.InvariantCulture, out int r) ? r : 0;

    private static long? GetLong(JsonElement e, string name) =>
        long.TryParse(GetString(e, name), NumberStyles.Integer, CultureInfo.InvariantCulture, out long r) ? r : null;

    private static double? ParseDouble(string? s) =>
        double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out double r) ? r : null;

    private static double? ParseFraction(string? s)
    {
        if (string.IsNullOrEmpty(s))
            return null;
        string[] parts = s.Split('/');
        if (parts.Length == 2
            && double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out double num)
            && double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out double den)
            && den > 0)
            return num / den;
        return ParseDouble(s);
    }

    private static string FormatBitrate(long bps) =>
        bps >= 1_000_000
            ? (bps / 1_000_000.0).ToString("0.#", CultureInfo.InvariantCulture) + "Mbps"
            : (bps / 1000).ToString("0", CultureInfo.InvariantCulture) + "kbps";

    private static string FormatDuration(double seconds)
    {
        var ts = TimeSpan.FromSeconds(seconds);
        return ts.TotalHours >= 1
            ? $"{(int)ts.TotalHours}:{ts.Minutes:D2}:{ts.Seconds:D2}"
            : $"{ts.Minutes:D2}:{ts.Seconds:D2}";
    }
}
