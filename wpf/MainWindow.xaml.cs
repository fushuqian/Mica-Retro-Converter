using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Win98Converter.Core;
using Wpf.Ui.Appearance;
using Wpf.Ui.Controls;
using Wpf.Ui.TaskBar;

namespace Win98Converter;

public sealed class FileItem : INotifyPropertyChanged
{
    public string FullPath { get; }
    public string DisplayName => Path.GetFileName(FullPath);

    private string _status = "等待中";
    public string Status
    {
        get => _status;
        set
        {
            _status = value;
            OnPropertyChanged(nameof(Status));
        }
    }

    private int _progress;
    public int Progress
    {
        get => _progress;
        set
        {
            _progress = value;
            OnPropertyChanged(nameof(Progress));
            OnPropertyChanged(nameof(ProgressText));
        }
    }

    public string ProgressText => _progress > 0 ? $"{_progress}%" : "";

    private string _info = "解析中";
    public string Info
    {
        get => _info;
        set
        {
            _info = value;
            OnPropertyChanged(nameof(Info));
        }
    }

    public FileItem(string fullPath) => FullPath = fullPath;

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged(string name) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

public partial class MainWindow : FluentWindow
{
    private sealed record PresetItem(Preset Preset)
    {
        public string Display => $"{Preset.Group} · {Preset.Name}";
        public bool IsEnabled => !Preset.Disabled;
        public override string ToString() => Display;
    }

    private sealed record FpsItem(string Label, double? Value)
    {
        public override string ToString() => Label;
    }

    private sealed record AspectItem(string Label, string? Value)
    {
        public override string ToString() => Label;
    }

    private readonly ObservableCollection<FileItem> _files = new();
    private CancellationTokenSource? _cts;
    private string? _ffmpeg;
    private string? _ffprobe;

    public MainWindow()
    {
        InitializeComponent();
        FileListView.ItemsSource = _files;
        
        // Initialize preset registry (loads from presets.builtin.json + user presets)
        Presets.Initialize(AppContext.BaseDirectory);
        
        InitPresets();
        InitFpsOptions();
        InitAspectOptions();

        _ffmpeg = ConversionEngine.FindFfmpeg(AppContext.BaseDirectory);
        _ffprobe = ConversionEngine.FindFfprobe(AppContext.BaseDirectory);
        if (_ffmpeg is null)
            AppendLog("[警告] 未找到 ffmpeg.exe，请将其放入程序所在目录的 ffmpeg 文件夹。");
        else
            AppendLog("[就绪] ffmpeg: " + _ffmpeg);
    }

    private void InitPresets()
    {
        PresetCombo.ItemsSource = Presets.All.Select(p => new PresetItem(p)).ToList();
        PresetCombo.SelectedIndex = 0;
    }

    private void InitFpsOptions()
    {
        FpsCombo.ItemsSource = Presets.FpsOptions.Select(o => new FpsItem(o.Label, o.Value)).ToList();
        FpsCombo.SelectedIndex = 0;
    }

    private void InitAspectOptions()
    {
        AspectCombo.ItemsSource = Presets.AspectRatioOptions.Select(o => new AspectItem(o.Label, o.Value)).ToList();
        AspectCombo.SelectedIndex = 0;
    }

    private void PresetCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (PresetCombo.SelectedItem is not PresetItem item)
            return;
        Preset preset = item.Preset;
        PresetDescText.Text = preset.Desc;
        FpsCombo.IsEnabled = !preset.ForceFps;
        SelectFps(preset.ForceFps ? preset.Fps : null);
    }

    private void EditPresets_Click(object sender, RoutedEventArgs e)
    {
        var editor = new PresetEditorWindow(Presets.Registry)
        {
            Owner = this
        };
        var result = editor.ShowDialog();
        if (result == true)
        {
            // Refresh preset combo after editing
            InitPresets();
            AppendLog("[预设] 用户预设已更新");
        }
    }

    private void SelectFps(double? value)
    {
        for (int i = 0; i < FpsCombo.Items.Count; i++)
        {
            if (FpsCombo.Items[i] is FpsItem fi && fi.Value == value)
            {
                FpsCombo.SelectedIndex = i;
                return;
            }
        }
        FpsCombo.SelectedIndex = 0;
    }

    private Preset ApplyOverrides(Preset preset)
    {
        if (preset.ForceFps)
            return preset;
        double? fps = (FpsCombo.SelectedItem as FpsItem)?.Value;
        return fps == preset.Fps ? preset : preset with { Fps = fps };
    }

    private void DropZone_DragOver(object sender, DragEventArgs e)
    {
        bool ok = e.Data.GetDataPresent(DataFormats.FileDrop);
        e.Effects = ok ? DragDropEffects.Copy : DragDropEffects.None;
        e.Handled = true;
    }

    private void DropZone_Drop(object sender, DragEventArgs e)
    {
        if (e.Data.GetData(DataFormats.FileDrop) is string[] paths)
            AddFiles(paths);
    }

    private void BrowseFiles_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new Microsoft.Win32.OpenFileDialog
        {
            Multiselect = true,
            Filter = "视频文件|" + string.Join(";", Presets.SupportedExts.OrderBy(x => x).Select(x => "*" + x))
                   + "|所有文件 (*.*)|*.*",
        };
        if (dlg.ShowDialog() == true)
            AddFiles(dlg.FileNames);
    }

    private void AddFiles(IEnumerable<string> paths)
    {
        var added = new List<FileItem>();
        foreach (string p in paths)
        {
            if (Directory.Exists(p))
            {
                try
                {
                    AddFiles(Directory.EnumerateFiles(p, "*", SearchOption.AllDirectories));
                }
                catch (Exception ex)
                {
                    AppendLog($"[警告] 遍历文件夹失败: {ex.Message}");
                }
                continue;
            }
            if (!File.Exists(p))
                continue;
            string ext = Path.GetExtension(p);
            if (!Presets.SupportedExts.Contains(ext))
            {
                AppendLog($"[跳过] 不支持的格式: {Path.GetFileName(p)}");
                continue;
            }
            if (_files.Any(f => string.Equals(f.FullPath, p, StringComparison.OrdinalIgnoreCase)))
                continue;
            var item = new FileItem(p);
            _files.Add(item);
            added.Add(item);
        }
        if (added.Count > 0)
            ProbeNewFiles(added);
    }

    private async void ProbeNewFiles(List<FileItem> items)
    {
        if (_ffprobe is null)
        {
            foreach (FileItem item in items)
                item.Info = "未找到 ffprobe";
            return;
        }
        foreach (FileItem item in items)
        {
            MediaInfo? info = await MediaProbe.ProbeAsync(_ffprobe, item.FullPath);
            item.Info = info switch
            {
                null => "解析失败",
                { Error: not null } => "解析失败",
                _ => info.Summary,
            };
        }
    }

    private void FileListView_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Delete)
        {
            foreach (FileItem item in FileListView.SelectedItems.Cast<FileItem>().ToList())
                _files.Remove(item);
        }
    }

    private void RemoveFile_Click(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.DataContext is FileItem item)
            _files.Remove(item);
    }

    private async void Start_Click(object sender, RoutedEventArgs e)
    {
        if (_ffmpeg is null)
        {
            ShowSnackbar("无法开始", "未找到 ffmpeg.exe");
            return;
        }
        if (_files.Count == 0)
        {
            ShowSnackbar("提示", "请先添加视频文件");
            return;
        }
        if (PresetCombo.SelectedItem is not PresetItem pi)
            return;

        Preset preset = ApplyOverrides(pi.Preset);
        bool letterbox = LetterboxCheck.IsChecked == true;
        bool burnSubs = BurnSubCheck.IsChecked == true;
        string? outDir = string.IsNullOrWhiteSpace(OutputDirBox.Text) ? null : OutputDirBox.Text.Trim();
        string? aspectRatio = (AspectCombo.SelectedItem as AspectItem)?.Value;

        SetBusy(true);
        _cts = new CancellationTokenSource();
        int done = 0, failed = 0;

        try
        {
            foreach (FileItem item in _files)
            {
                if (_cts.Token.IsCancellationRequested)
                    break;
                item.Status = "转换中";
                item.Progress = 0;
                UpdateTotalProgress();
                try
                {
                    var result = await ConversionEngine.ConvertAsync(
                        _ffmpeg, _ffprobe, item.FullPath, preset, outDir, burnSubs, letterbox, aspectRatio,
                        onProgress: p => Dispatcher.Invoke(() => item.Progress = p),
                        onLog: l => Dispatcher.Invoke(() => AppendLog(l)),
                        ct: _cts.Token);

                    if (result.Cancelled)
                    {
                        item.Status = "已取消";
                        break;
                    }
                    if (result.ExitCode == 0)
                    {
                        item.Status = "完成";
                        item.Progress = 100;
                        done++;
                        AppendLog("[完成] " + result.OutputFile);
                    }
                    else
                    {
                        item.Status = "失败";
                        failed++;
                    }
                }
                catch (Exception ex)
                {
                    item.Status = "失败";
                    failed++;
                    AppendLog("[异常] " + ex.Message);
                }
                UpdateTotalProgress();
            }
        }
        finally
        {
            SetBusy(false);
            TaskBarProgress.SetState(this, TaskBarProgressState.None);
        }

        string msg = $"转换结束：{done} 成功，{failed} 失败";
        AppendLog("[汇总] " + msg);
        ShowSnackbar("转换完成", msg);
    }

    private void Cancel_Click(object sender, RoutedEventArgs e) => _cts?.Cancel();

    private void SetBusy(bool busy)
    {
        StartButton.IsEnabled = !busy;
        CancelButton.IsEnabled = busy;
        PresetCombo.IsEnabled = !busy;
        FpsCombo.IsEnabled = !busy && !((PresetCombo.SelectedItem as PresetItem)?.Preset.ForceFps ?? false);
        AspectCombo.IsEnabled = !busy;
        LetterboxCheck.IsEnabled = !busy;
        BurnSubCheck.IsEnabled = !busy;
        if (busy)
            TaskBarProgress.SetState(this, TaskBarProgressState.Normal);
    }

    private void UpdateTotalProgress()
    {
        int total = _files.Count * 100;
        int current = _files.Sum(f => f.Progress);
        int pct = total == 0 ? 0 : current * 100 / total;
        TotalProgress.Value = pct;
        ProgressText.Text = $"{pct}%";
        TaskBarProgress.SetValue(this, TaskBarProgressState.Normal, pct);
    }

    private void AppendLog(string text)
    {
        LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {text}{Environment.NewLine}");
        if (LogBox.Text.Length > 50000)
            LogBox.Text = LogBox.Text[^30000..];
        LogBox.ScrollToEnd();
    }

    private void ShowSnackbar(string title, string message)
    {
        new Snackbar(MainSnackbar)
        {
            Title = title,
            Content = message,
            Appearance = ControlAppearance.Info,
            Icon = new SymbolIcon(SymbolRegular.Info24),
            Timeout = TimeSpan.FromSeconds(3)
        }.Show();
    }

    private void ToggleTheme_Click(object sender, RoutedEventArgs e)
    {
        var current = ApplicationThemeManager.GetAppTheme();
        var next = current == ApplicationTheme.Dark ? ApplicationTheme.Light : ApplicationTheme.Dark;
        ApplicationThemeManager.Apply(next, WindowBackdropType.Mica, true);
    }
}
