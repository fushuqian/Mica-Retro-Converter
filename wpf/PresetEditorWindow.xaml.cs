using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Win98Converter.Core;
using Wpf.Ui;
using Wpf.Ui.Controls;

namespace Win98Converter;

public partial class PresetEditorWindow : FluentWindow
{
    private readonly PresetRegistry _registry;
    private ObservableCollection<PresetRow> _rows = [];

    public PresetEditorWindow(PresetRegistry registry)
    {
        InitializeComponent();
        _registry = registry;
        LoadPresets();
    }

    private void LoadPresets()
    {
        _rows = [];
        foreach (var p in _registry.Builtin)
            _rows.Add(new PresetRow(p, isBuiltin: true));
        foreach (var p in _registry.User)
            _rows.Add(new PresetRow(p, isBuiltin: false));
        PresetGrid.ItemsSource = _rows;
        UpdateStatus();
    }

    private void UpdateStatus()
    {
        int userCount = _rows.Count(r => !r.IsBuiltin);
        StatusText.Text = $"共 {_rows.Count} 个预设（{_registry.Builtin.Count} 内置 + {userCount} 用户）";
    }

    private void New_Click(object sender, RoutedEventArgs e)
    {
        var newPreset = new Preset
        {
            Name = "新预设",
            Group = "自定义",
            VideoCodec = "wmv2",
            AudioCodec = "wmav2",
            Container = "asf",
            OutputExt = "asf",
            Suffix = "custom",
            Width = 640,
            Height = 480,
            VideoBitrate = 800,
            AudioBitrate = 96,
            AudioSampleRate = 44100,
            Desc = "自定义预设",
        };
        _rows.Add(new PresetRow(newPreset, isBuiltin: false));
        UpdateStatus();
    }

    private void Copy_Click(object sender, RoutedEventArgs e)
    {
        if (PresetGrid.SelectedItem is not PresetRow row)
        {
            ShowMsg("提示", "请先选择一个预设");
            return;
        }
        var copy = row.Preset with
        {
            Name = row.Preset.Name + " (副本)",
        };
        _rows.Add(new PresetRow(copy, isBuiltin: false));
        StatusText.Text = $"已复制：{copy.Name}";
        UpdateStatus();
    }

    private void Delete_Click(object sender, RoutedEventArgs e)
    {
        if (PresetGrid.SelectedItem is not PresetRow row)
        {
            ShowMsg("提示", "请先选择一个预设");
            return;
        }
        if (row.IsBuiltin)
        {
            ShowMsg("不能删除", "内置预设不可删除，请复制后修改");
            return;
        }
        _rows.Remove(row);
        UpdateStatus();
    }

    private void Reset_Click(object sender, RoutedEventArgs e)
    {
        var result = System.Windows.MessageBox.Show(this, "确定要删除所有用户预设并恢复默认吗？",
            "确认", System.Windows.MessageBoxButton.YesNo, System.Windows.MessageBoxImage.Warning);
        if (result != System.Windows.MessageBoxResult.Yes)
            return;

        var userRows = _rows.Where(r => !r.IsBuiltin).ToList();
        foreach (var r in userRows)
            _rows.Remove(r);

        UpdateStatus();
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        var userPresets = _rows
            .Where(r => !r.IsBuiltin)
            .Select(r => r.Preset)
            .ToList();

        var names = userPresets.Select(p => p.Name).ToList();
        if (names.Distinct(StringComparer.OrdinalIgnoreCase).Count() != names.Count)
        {
            ShowMsg("保存失败", "用户预设中存在重复名称，请修改后再保存");
            return;
        }

        _registry.User.Clear();
        foreach (var p in userPresets)
            _registry.User.Add(p);

        _registry.SaveUser();
        DialogResult = true;
        Close();
    }

    private void Cancel_Click(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }

    private void Import_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "JSON 文件|*.json|所有文件 (*.*)|*.*",
            Title = "导入预设 JSON"
        };
        if (dlg.ShowDialog(this) != true)
            return;

        try
        {
            string json = File.ReadAllText(dlg.FileName);
            var opts = new System.Text.Json.JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            };
            var presets = System.Text.Json.JsonSerializer.Deserialize<List<Preset>>(json, opts) ?? [];

            int imported = 0;
            foreach (var p in presets)
            {
                if (!_rows.Any(r => r.Preset.Name.Equals(p.Name, StringComparison.OrdinalIgnoreCase)))
                {
                    _rows.Add(new PresetRow(p, isBuiltin: false));
                    imported++;
                }
            }
            StatusText.Text = $"导入完成：新增 {imported} 个预设";
            UpdateStatus();
        }
        catch (Exception ex)
        {
            ShowMsg("导入失败", ex.Message);
        }
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        var userPresets = _rows.Where(r => !r.IsBuiltin).Select(r => r.Preset).ToList();
        if (userPresets.Count == 0)
        {
            ShowMsg("提示", "没有用户预设可导出");
            return;
        }

        var dlg = new Microsoft.Win32.SaveFileDialog
        {
            Filter = "JSON 文件|*.json",
            FileName = "presets.user.export.json",
            Title = "导出用户预设"
        };
        if (dlg.ShowDialog(this) != true)
            return;

        try
        {
            var opts = new System.Text.Json.JsonSerializerOptions { WriteIndented = true };
            string json = System.Text.Json.JsonSerializer.Serialize(userPresets, opts);
            File.WriteAllText(dlg.FileName, json);
            StatusText.Text = $"已导出 {userPresets.Count} 个预设到 {dlg.FileName}";
        }
        catch (Exception ex)
        {
            ShowMsg("导出失败", ex.Message);
        }
    }

    private void ShowMsg(string title, string message)
    {
        System.Windows.MessageBox.Show(this, message, title,
            System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information);
    }

    private sealed class PresetRow
    {
        public Preset Preset { get; private set; }
        public bool IsBuiltin { get; }

        public PresetRow(Preset preset, bool isBuiltin)
        {
            Preset = preset;
            IsBuiltin = isBuiltin;
        }

        public string IsBuiltinText => IsBuiltin ? "内置" : "用户";

        public string Name
        {
            get => Preset.Name;
            set => Preset = Preset with { Name = value };
        }

        public string Group
        {
            get => Preset.Group;
            set => Preset = Preset with { Group = value };
        }

        public string VideoCodec
        {
            get => Preset.VideoCodec;
            set => Preset = Preset with { VideoCodec = value };
        }

        public string AudioCodec
        {
            get => Preset.AudioCodec;
            set => Preset = Preset with { AudioCodec = value };
        }

        public string Container
        {
            get => Preset.Container;
            set => Preset = Preset with { Container = value };
        }

        public int Width
        {
            get => Preset.Width;
            set => Preset = Preset with { Width = value };
        }

        public int Height
        {
            get => Preset.Height;
            set => Preset = Preset with { Height = value };
        }

        public int VideoBitrate
        {
            get => Preset.VideoBitrate;
            set => Preset = Preset with { VideoBitrate = value };
        }

        public int AudioBitrate
        {
            get => Preset.AudioBitrate;
            set => Preset = Preset with { AudioBitrate = value };
        }

        public string OutputExt
        {
            get => Preset.OutputExt;
            set => Preset = Preset with { OutputExt = value };
        }

        public string Desc
        {
            get => Preset.Desc;
            set => Preset = Preset with { Desc = value };
        }
    }
}