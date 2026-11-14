# Checks the buttons of a stand-alone build with real mouse clicks: starts the program in a
# window, moves the system pointer onto a button and presses the left mouse button. The
# clicks go through Windows like those of a hand; the program writes down every click it
# received and what it did with it (-LsnClickLog), and this script prints that list.
# Do not touch the mouse while it runs (about 30 s). Run it from an ordinary terminal on the
# desktop; a session that cannot move the desktop's pointer gets "received no click".
#
#   unreal\Scripts\click_test.ps1 -Build C:\Projects\lsn-build\Windows
param(
    [Parameter(Mandatory = $true)][string]$Build,
    [string]$Out = ""
)
$ErrorActionPreference = "Stop"
$Build = [System.IO.Path]::GetFullPath($Build)
$exe = Join-Path $Build "LunarSiteNavigator.exe"
if ($Out -eq "") { $Out = Join-Path $Build "..\click_test" }
$Out = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force $Out | Out-Null
$log = Join-Path $Out "clicks.txt"
if (Test-Path $log) { Remove-Item $log }
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class LsnWin {
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
}
"@
[LsnWin]::SetProcessDPIAware() | Out-Null
Start-Process -FilePath $exe -ArgumentList @("-windowed", "-ResX=1280", "-ResY=720", "-ForceRes", "-WinX=40", "-WinY=40", "-LsnTime=300", "-LsnClickLog=`"$log`"") | Out-Null
$window = [IntPtr]::Zero
for ($i = 0; $i -lt 60 -and $window -eq [IntPtr]::Zero; $i++) {
    Start-Sleep -Milliseconds 500
    $p = Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($Build, [System.StringComparison]::OrdinalIgnoreCase) -and $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
    if ($p) { $window = $p.MainWindowHandle }
}
if ($window -eq [IntPtr]::Zero) { Write-Host "The program did not open a window."; exit 1 }
Start-Sleep -Seconds 6
[LsnWin]::SetForegroundWindow($window) | Out-Null
$rect = New-Object LsnWin+RECT
[LsnWin]::GetClientRect($window, [ref]$rect) | Out-Null
$origin = New-Object LsnWin+POINT
[LsnWin]::ClientToScreen($window, [ref]$origin) | Out-Null
$w = $rect.R - $rect.L; $h = $rect.B - $rect.T
Write-Host "Window client area: $w x $h at $($origin.X),$($origin.Y)"
# Positions as fractions of the window, from the layout of the buttons (FLsnToolbar::Make): the bar has
# two rows of ten cells between 6 % and 94 % of the width; the main buttons are under the header.
function Click([double]$fx, [double]$fy) {
    [LsnWin]::SetCursorPos($origin.X + [int]($fx * $w), $origin.Y + [int]($fy * $h)) | Out-Null
    Start-Sleep -Milliseconds 300
    [LsnWin]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 80; [LsnWin]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 1200
}
$column = { param($i) 0.06 + 0.088 * ($i + 0.5) }
Click (& $column 6) 0.913      # Day >  (bar, upper row)
Click 0.70 0.836               # the whole-range strip, 70 % along
Click (& $column 9) 0.974      # Help (F1)  (bar, lower row)
Click (& $column 9) 0.974      # Help (F1) again
Click 0.240 0.165              # main button: Jump to next sunset
Click 0.087 0.165              # main button: Compare two sites
Start-Sleep -Seconds 2
Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($Build, [System.StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path $log) { Get-Content $log } else { Write-Host "The program received no click."; exit 1 }
exit 0
