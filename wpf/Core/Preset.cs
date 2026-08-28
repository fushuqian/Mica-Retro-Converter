namespace Win98Converter.Core;

public sealed record Preset
{
    public required string Name { get; init; }
    public required string Group { get; init; }
    public string VideoCodec { get; init; } = "";
    public string AudioCodec { get; init; } = "";
    public string Container { get; init; } = "";
    public string OutputExt { get; init; } = "";
    public string Suffix { get; init; } = "out";
    public int Width { get; init; }
    public int Height { get; init; }
    public double? Fps { get; init; }
    public bool ForceFps { get; init; }
    public int VideoBitrate { get; init; }
    public int AudioBitrate { get; init; }
    public int AudioSampleRate { get; init; }
    public string VideoTag { get; init; } = "";
    public IReadOnlyList<string> ExtraArgs { get; init; } = [];
    public string Desc { get; init; } = "";
    public bool Disabled { get; init; }
    public string? AspectRatio { get; init; }
}
