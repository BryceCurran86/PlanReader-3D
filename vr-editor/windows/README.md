# PlanReader VR Desktop Preview — Windows installer

This is a **review-only desktop installer** for the existing React/Three.js
viewer. It is not a Unity 6 player, PS VR2 hardware driver, OpenXR native
capture plugin, measuring engine or commercial revision/approval client.

## Building on Windows

Prerequisites: Windows x64, Node 22, .NET SDK 8, Inno Setup 6 and the
Microsoft Edge WebView2 Runtime. From the repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\vr-editor\windows\Build-Desktop.ps1
```

The output is `vr-editor/windows/out/installer/PlanReader-VR-Desktop-Preview-Setup.exe`.
The unsigned per-user installer creates a Start menu shortcut and optional
desktop shortcut. It runs without a locally hosted HTTP server, uses a synthetic
local HTTPS origin mapped to the bundled static assets, and never includes
source PDFs, project/customer data, tokens or production API access.

Use `-SkipInstaller` for an executable-only smoke build. GitHub Actions
also packages the installer for Windows x64 as an **unsigned test artifact**
on a successful workflow run. CI packaging does not constitute a real
Windows graphics or headset acceptance test.

Local preview allows file-imported review scenes, desktop orbit/selection,
existing walls/visual studies and source-bound annotations. The host refuses
all remote resource/API requests and denies browser permissions; only official
PlayStation and Steam setup links may open in the OS browser.

## Important limitations

The bundled WebView2 shell is desktop-only. Embedded WebView2 is **not proven
to support immersive WebXR/OpenXR** or PS VR2 hardware. The existing browser
viewer may be tested with SteamVR/OpenXR in a compatible external browser.
A Unity 6 native player, device/capture plugin, signed installer and real
headset verification are separate work and are not delivered here.

Windows may show a SmartScreen warning for this unsigned build. Do not bypass
organizational security policy to install it. Before shipping: test install,
uninstall, launch, rendering, local manifest import, external API refusal,
GPU performance, WebView2 runtime availability, code signing and release
security. No user data or approved quantity may be inferred from a synthetic
review scene. Original PlanReader `pb_*` measurement and frozen120 are untouched.
