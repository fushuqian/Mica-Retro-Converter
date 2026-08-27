using System.Linq;
using System.Windows;
using Win98Converter.Core;
using Wpf.Ui.Appearance;
using Wpf.Ui.Controls;

namespace Win98Converter;

public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        if (e.Args.Contains("--selftest"))
        {
            int code = await SelfTest.RunAsync();
            Environment.Exit(code);
            return;
        }

        var systemTheme = ApplicationThemeManager.GetSystemTheme();
        ApplicationThemeManager.Apply(
            systemTheme == SystemTheme.Dark ? ApplicationTheme.Dark : ApplicationTheme.Light,
            WindowBackdropType.Mica,
            true);

        MainWindow = new MainWindow();
        MainWindow.Show();
    }
}
