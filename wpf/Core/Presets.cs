using System.Collections.ObjectModel;

namespace Win98Converter.Core;

public static class Presets
{
    private static PresetRegistry? _registry;
    private static string? _baseDir;

    public static void Initialize(string baseDir)
    {
        _baseDir = baseDir;
        _registry = PresetRegistry.Load(baseDir);
    }

    public static PresetRegistry Registry => _registry ?? throw new InvalidOperationException("Presets.Initialize() 未调用");

    public static IReadOnlyList<Preset> All => Registry.All;

    public static ObservableCollection<Preset> Builtin => Registry.Builtin;

    public static ObservableCollection<Preset> User => Registry.User;

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

    public static IReadOnlyList<(string Label, string? Value)> AspectRatioOptions { get; } = new (string, string?)[]
    {
        ("保持原比例", null),
        ("4:3", "4:3"),
        ("16:9", "16:9"),
        ("16:10", "16:10"),
        ("1:1", "1:1"),
        ("3:2", "3:2"),
        ("2.35:1 (宽银幕)", "2.35:1"),
    };

    public static IReadOnlyCollection<string> SupportedExts { get; } = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".mpg", ".mpeg",
        ".m4v", ".webm", ".ts", ".m2ts", ".vob", ".3gp", ".rm", ".rmvb",
    };

    // Legacy helper for backward compatibility
    public static IReadOnlyList<Preset> GetAll() => All;
}