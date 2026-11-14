# Records a stretch of the timeline as a video: the scene plays the stretch once at a
# fixed frame rate, every frame is saved, and ffmpeg (must be on PATH) joins the frames.
# The frames are real renders of the running scene, HUD included.
#
# Example (de Gerlache rim, sunset of 9 February 2027):
#   unreal\Scripts\record.ps1 -Out docs\unreal\sunset.mp4 -Site de-gerlache-rim-crest -From 2088 -To 2100 -Seconds 25 -Yaw 213 -Pitch -2 -Fov 25
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [Parameter(Mandatory = $true)][double]$From,
    [Parameter(Mandatory = $true)][double]$To,
    [double]$Seconds = 25,
    [string]$Site = "",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [int]$Height = -1,
    [double]$Yaw = [double]::NaN,
    [double]$Pitch = [double]::NaN,
    [double]$Fov = 60,
    [int]$ResX = 1280,
    [int]$ResY = 720,
    [int]$Fps = 30,
    # Further arguments passed to the scene as they are, in one string separated by spaces.
    [string]$Extra = "",
    [switch]$HorizonLine
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "LunarSiteNavigator.uproject"
$outFull = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force (Split-Path -Parent $outFull) | Out-Null
$frames = Join-Path $root "Saved\Lsn\MovieFrames"
if (Test-Path $frames) { Remove-Item -Recurse -Force $frames }
$log = Join-Path $root "Saved\Logs\Record.log"
$inv = [System.Globalization.CultureInfo]::InvariantCulture
$args = @(
    "`"$project`"", "-game", "-windowed", "-ResX=$ResX", "-ResY=$ResY", "-RenderOffscreen", "-ForceRes",
    "-benchmark", "-fps=$Fps", "-LsnFov=$($Fov.ToString($inv))",
    "-LsnPlayFrom=$($From.ToString($inv))", "-LsnPlayTo=$($To.ToString($inv))", "-LsnPlaySeconds=$($Seconds.ToString($inv))",
    "-LsnMovieDir=`"$frames`"", "-abslog=`"$log`"", "-unattended", "-nopause", "-nosplash", "-nosound"
)
if ($Site -ne "") { $args += "-LsnSite=$Site" }
if ($Height -ge 0) { $args += "-LsnHeight=$Height" }
if (-not [double]::IsNaN($Yaw)) { $args += "-LsnYaw=$($Yaw.ToString($inv))" }
if (-not [double]::IsNaN($Pitch)) { $args += "-LsnPitch=$($Pitch.ToString($inv))" }
if ($HorizonLine) { $args += "-LsnHorizonLine" }
if ($Extra -ne "") { $args += $Extra }
$editor = "$EngineRoot\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$proc = Start-Process -FilePath $editor -ArgumentList $args -NoNewWindow -Wait -PassThru -RedirectStandardOutput (Join-Path $env:TEMP "lsn_record_stdout.txt")
$count = @(Get-ChildItem -Path $frames -Filter "frame_*.png" -ErrorAction SilentlyContinue).Count
if ($count -lt 2) { Write-Host "No frames were written (exit code $($proc.ExitCode)). Log: $log"; exit 1 }
if (Test-Path $outFull) { Remove-Item $outFull }
& ffmpeg -hide_banner -loglevel error -y -framerate $Fps -i (Join-Path $frames "frame_%05d.png") -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart $outFull
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $outFull)) { Write-Host "ffmpeg failed"; exit 1 }
Write-Host ("{0} frames at {1} fps = {2:N1} s -> {3} ({4:N1} MB)" -f $count, $Fps, ($count / $Fps), $outFull, ((Get-Item $outFull).Length / 1MB))
exit 0
