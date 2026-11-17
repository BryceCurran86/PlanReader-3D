using System.Diagnostics;
using System.Text;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
namespace PlanReaderDesktop;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new ViewerWindow());
    }
}

/// <summary>Review-only local shell: no source PDF, production API or approval gateway.</summary>
internal sealed class ViewerWindow : Form
{
    private const string LocalHost = "planreader-desktop.invalid";
    private const string LocalHome = "https://" + LocalHost + "/index.html";
    private readonly WebView2 _viewer = new() { Dock = DockStyle.Fill };

    public ViewerWindow()
    {
        Text = "PlanReader VR | Desktop review preview";
        Width = 1440;
        Height = 900;
        MinimumSize = new Size(850, 550);
        Controls.Add(_viewer);
        Shown += async (_, _) => await StartAsync();
    }

    private static bool IsLocal(Uri uri) =>
        uri.Scheme == Uri.UriSchemeHttps && uri.Host == LocalHost &&
        uri.Port == 443 && uri.UserInfo.Length == 0;

    private static bool IsApprovedHelpLink(Uri uri) =>
        uri.Scheme == Uri.UriSchemeHttps && uri.Port == 443 &&
        uri.UserInfo.Length == 0 &&
        (uri.Host == "www.playstation.com" ||
         uri.Host == "store.steampowered.com");

    private static void OpenApprovedHelpLink(string address)
    {
        if (!Uri.TryCreate(address, UriKind.Absolute, out var uri) ||
            !IsApprovedHelpLink(uri)) return;
        try { Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); }
        catch (Exception) { /* Help is optional; no arbitrary URL fallback. */ }
    }

    private async Task StartAsync()
    {
        var assetRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "web"));
        if (!File.Exists(Path.Combine(assetRoot, "index.html")))
        {
            ShowFailure("Packaged VR viewer assets are missing. Reinstall the preview.");
            return;
        }

        try
        {
            var userData = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "PlanReader", "VRDesktop", "WebView2");
            Directory.CreateDirectory(userData);
            var env = await CoreWebView2Environment.CreateAsync(userDataFolder: userData);
            await _viewer.EnsureCoreWebView2Async(env);
            var core = _viewer.CoreWebView2;

            // No JavaScript/native bridge and no credential autofill.
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.AreHostObjectsAllowed = false;
            core.Settings.IsWebMessageEnabled = false;
            core.Settings.IsPasswordAutosaveEnabled = false;
            core.Settings.IsGeneralAutofillEnabled = false;
            core.SetVirtualHostNameToFolderMapping(
                LocalHost, assetRoot, CoreWebView2HostResourceAccessKind.DenyCors);

            core.PermissionRequested += (_, args) =>
            {
                args.State = CoreWebView2PermissionState.Deny;
            };
            core.NavigationStarting += (_, args) =>
            {
                if (Uri.TryCreate(args.Uri, UriKind.Absolute, out var uri) && IsLocal(uri))
                    return;
                args.Cancel = true;
                OpenApprovedHelpLink(args.Uri);
            };
            core.NewWindowRequested += (_, args) =>
            {
                args.Handled = true;
                OpenApprovedHelpLink(args.Uri);
            };

            // Neither /api/ nor any external resource may be accessed in review mode.
            core.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
            core.WebResourceRequested += (_, args) =>
            {
                if (Uri.TryCreate(args.Request.Uri, UriKind.Absolute, out var uri) &&
                    IsLocal(uri) && !uri.AbsolutePath.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
                    return;
                var bytes = Encoding.UTF8.GetBytes("Offline review only; remote and mutation APIs disabled.");
                args.Response = core.Environment.CreateWebResourceResponse(
                    new MemoryStream(bytes), 403, "Offline preview only",
                    "Content-Type: text/plain\r\nCache-Control: no-store");
            };
            core.Navigate(LocalHome);
        }
        catch (Exception error)
        {
            ShowFailure("Microsoft Edge WebView2 Runtime is required. Install or repair it and reopen the desktop preview.\n\n" +
                        error.GetType().Name);
        }
    }

    private void ShowFailure(string message) =>
        MessageBox.Show(this, message, "PlanReader VR Desktop preview",
            MessageBoxButtons.OK, MessageBoxIcon.Warning);
}
