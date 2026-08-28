using System.Collections.ObjectModel;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Win98Converter.Core;

public sealed class PresetRegistry
{
    private static readonly string UserPresetDir =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Win98Converter");
    private static readonly string UserPresetFile = Path.Combine(UserPresetDir, "presets.user.json");

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() },
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private ObservableCollection<Preset> _builtin = [];
    private ObservableCollection<Preset> _user = [];

    public ObservableCollection<Preset> Builtin => _builtin;
    public ObservableCollection<Preset> User => _user;

    public IReadOnlyList<Preset> All => _builtin.Concat(_user).ToList().AsReadOnly();

    public event EventHandler? PresetsChanged;

    public static PresetRegistry Load(string baseDir)
    {
        var registry = new PresetRegistry();
        registry.LoadBuiltin(baseDir);
        registry.LoadUser();
        return registry;
    }

    private void LoadBuiltin(string baseDir)
    {
        string[] candidates =
        {
            Path.Combine(baseDir, "Core", "presets.builtin.json"),
            Path.Combine(baseDir, "presets.builtin.json"),
            Path.Combine(AppContext.BaseDirectory, "Core", "presets.builtin.json"),
            Path.Combine(AppContext.BaseDirectory, "presets.builtin.json"),
        };

        string? path = candidates.FirstOrDefault(File.Exists);
        if (path is null)
        {
            _builtin = new ObservableCollection<Preset>(GetFallbacks());
            return;
        }

        try
        {
            string json = File.ReadAllText(path);
            var presets = JsonSerializer.Deserialize<List<Preset>>(json, JsonOpts) ?? [];
            _builtin = new ObservableCollection<Preset>(presets);
        }
        catch
        {
            _builtin = new ObservableCollection<Preset>(GetFallbacks());
        }
    }

    private void LoadUser()
    {
        if (!File.Exists(UserPresetFile))
            return;

        try
        {
            string json = File.ReadAllText(UserPresetFile);
            var presets = JsonSerializer.Deserialize<List<Preset>>(json, JsonOpts) ?? [];
            _user = new ObservableCollection<Preset>(presets);
        }
        catch
        {
            _user = [];
        }
    }

    public void SaveUser()
    {
        Directory.CreateDirectory(UserPresetDir);
        string json = JsonSerializer.Serialize(_user.ToList(), JsonOpts);
        File.WriteAllText(UserPresetFile, json);
        PresetsChanged?.Invoke(this, EventArgs.Empty);
    }

    public void AddUserPreset(Preset preset)
    {
        _user.Add(preset);
        SaveUser();
    }

    public void UpdateUserPreset(int index, Preset preset)
    {
        if (index < 0 || index >= _user.Count)
            return;
        _user[index] = preset;
        SaveUser();
    }

    public void RemoveUserPreset(int index)
    {
        if (index < 0 || index >= _user.Count)
            return;
        _user.RemoveAt(index);
        SaveUser();
    }

    public static string GetUserPresetPath() => UserPresetFile;

    private static IEnumerable<Preset> GetFallbacks()
    {
        return
        [
            new Preset
            {
                Name = "推荐 (Win98 兼容)", Group = "Win98 流媒体",
                VideoCodec = "wmv2", AudioCodec = "wmav2",
                Container = "asf", OutputExt = "asf", Suffix = "win98",
                Width = 640, Height = 480,
                VideoBitrate = 800, AudioBitrate = 96, AudioSampleRate = 44100,
                Desc = "640×480 · WMV2+WMA2 in ASF · Fallback (presets.builtin.json 未找到)",
            }
        ];
    }
}