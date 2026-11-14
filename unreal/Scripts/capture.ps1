# Runs the view scene without a window and saves one real capture of it.
# Example:
#   unreal\Scripts\capture.ps1 -Out docs\unreal\site_view.png -Time 456 -HorizonLine
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Package = "",
    [string]$Site = "",
    # Further arguments passed to the scene as they are, in one string separated by spaces,
    # for example -Extra "-LsnCompare=a,b -LsnNoHud".
    [string]$Extra = "",
    [int]$Time = 0,
    [int]$Height = -1,
    [double]$Yaw = [double]::NaN,
    [double]$Pitch = [double]::NaN,
    [double]$Fov = 60,
    [int]$ResX = 1920,
    [int]$ResY = 1080,
    [switch]$HorizonLine
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "LunarSiteNavigator.uproject"
$outFull = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force (Split-Path -Parent $outFull) | Out-Null
if (Test-Path $outFull) { Remove-Item $outFull }
$log = Join-Path $root "Saved\Logs\Capture.log"
$inv = [System.Globalization.CultureInfo]::InvariantCulture
$args = @(
    "`"$project`"", "-game", "-windowed", "-ResX=$ResX", "-ResY=$ResY", "-RenderOffscreen", "-ForceRes",
    "-LsnTime=$Time", "-LsnFov=$($Fov.ToString($inv))", "-LsnShot=`"$outFull`"",
    "-abslog=`"$log`"", "-unattended", "-nopause", "-nosplash", "-nosound"
)
if ($Package -ne "") { $args += "-LsnPackage=`"$([System.IO.Path]::GetFullPath($Package))`"" }
if ($Site -ne "") { $args += "-LsnSite=$Site" }
if ($Extra -ne "") { $args += $Extra }
if ($Height -ge 0) { $args += "-LsnHeight=$Height" }
if (-not [double]::IsNaN($Yaw)) { $args += "-LsnYaw=$($Yaw.ToString($inv))" }
if (-not [double]::IsNaN($Pitch)) { $args += "-LsnPitch=$($Pitch.ToString($inv))" }
if ($HorizonLine) { $args += "-LsnHorizonLine" }
$editor = "$EngineRoot\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$proc = Start-Process -FilePath $editor -ArgumentList $args -NoNewWindow -Wait -PassThru -RedirectStandardOutput (Join-Path $env:TEMP "lsn_capture_stdout.txt")
if (-not (Test-Path $outFull)) { Write-Host "No capture was written (exit code $($proc.ExitCode)). Log: $log"; exit 1 }
Write-Host "Capture written: $outFull"
exit 0

