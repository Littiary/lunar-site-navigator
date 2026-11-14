# Measures the frame time of a stand-alone build by running it: one site and two sites side
# by side, each at normal and at low quality, with the timeline playing (the shadows move in
# every frame). The program measures itself (-LsnBench): it waits six seconds, records the
# time of every frame for the given number of seconds, without vertical sync and without a
# frame limit, writes the result and quits. This script also records the largest GPU memory
# in use (nvidia-smi, whole GPU, minus the value before the start).
#
#   unreal\Scripts\bench.ps1 -Build C:\Projects\lsn-build\Windows
param(
    [Parameter(Mandatory = $true)][string]$Build,
    [string]$Out = "",
    [int]$ResX = 1920,
    [int]$ResY = 1080,
    [int]$Seconds = 20
)
$ErrorActionPreference = "Stop"
$Build = [System.IO.Path]::GetFullPath($Build)
$exe = Join-Path $Build "LunarSiteNavigator.exe"
if (-not (Test-Path $exe)) { Write-Host "No LunarSiteNavigator.exe in $Build"; exit 1 }
if ($Out -eq "") { $Out = Join-Path $Build "..\bench" }
$Out = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force $Out | Out-Null
$index = Get-Content (Join-Path $Build "LunarSiteNavigator\Content\LsnPackages\index.json") -Raw | ConvertFrom-Json
$sites = @($index.packages | Where-Object { $_.kind -eq "site" })

function Get-GpuMb {
    $value = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    if ($value) { [int]$value } else { -1 }
}
function Run([string]$name, [string[]]$arguments) {
    $file = Join-Path $Out "$name.txt"
    if (Test-Path $file) { Remove-Item $file }
    $before = Get-GpuMb
    # The timeline plays through 400 samples while the frames are measured.
    $all = @("-windowed", "-ResX=$ResX", "-ResY=$ResY", "-ForceRes", "-LsnBench=`"$file`"", "-LsnBenchSeconds=$Seconds", "-LsnPlayFrom=24", "-LsnPlayTo=424", "-LsnPlaySeconds=$($Seconds + 8)") + $arguments
    $process = Start-Process -FilePath $exe -ArgumentList $all -PassThru
    $peak = $before
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    while (-not (Test-Path $file) -and $watch.Elapsed.TotalSeconds -lt ($Seconds + 120)) {
        Start-Sleep -Milliseconds 500
        $now = Get-GpuMb
        if ($now -gt $peak) { $peak = $now }
    }
    Start-Sleep -Seconds 3
    Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($Build, [System.StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path $file)) { Write-Host "$name : no result"; return }
    $r = @{}
    foreach ($line in Get-Content $file) { $k, $v = $line -split " ", 2; $r[$k] = $v }
    Write-Host ("{0,-28} mean {1,7} ms ({2,5:N0} fps)  median {3,7} ms  95 % under {4,7} ms  99 % under {5,7} ms  {6}  GPU memory +{7} MB  [{8}]" -f $name, $r.mean_ms,
        (1000.0 / [double]::Parse($r.mean_ms, [cultureinfo]::InvariantCulture)), $r.median_ms, $r.p95_ms, $r.p99_ms, $r.resolution, ($peak - $before), $r.gpu)
}
$one = "-LsnSite=$($sites[0].site_id)"
Run "one_site" @($one)
Run "one_site_low" @($one, "-LsnLowQuality")
if ($sites.Count -ge 2) {
    $two = "-LsnCompare=$($sites[0].site_id),$($sites[1].site_id)"
    Run "two_sites" @($two)
    Run "two_sites_low" @($two, "-LsnLowQuality")
}
Write-Host "Results in $Out"

exit 0
