# Tests a stand-alone build by running it: every bundled site alone and the first two side
# by side. For each run the program is started with -LsnShot (it renders, saves one frame
# and quits) and this script records whether the frame was written, the largest GPU memory
# in use while it ran (nvidia-smi, whole GPU, minus the value before the start) and the
# network connections its processes opened.
#
#   unreal\Scripts\test_build.ps1 -Build C:\Projects\lsn-build\Windows
param(
    [Parameter(Mandatory = $true)][string]$Build,
    [string]$Out = "",
    [int]$ResX = 1920,
    [int]$ResY = 1080
)
$ErrorActionPreference = "Stop"
$Build = [System.IO.Path]::GetFullPath($Build)
$exe = Join-Path $Build "LunarSiteNavigator.exe"
if (-not (Test-Path $exe)) { Write-Host "No LunarSiteNavigator.exe in $Build"; exit 1 }
if ($Out -eq "") { $Out = Join-Path $Build "..\build_test" }
$Out = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force $Out | Out-Null
$index = Get-Content (Join-Path $Build "LunarSiteNavigator\Content\LsnPackages\index.json") -Raw | ConvertFrom-Json
$sites = @($index.packages | Where-Object { $_.kind -eq "site" })
Write-Host ("Build: {0}  ({1:N0} MB)" -f $Build, ((Get-ChildItem $Build -Recurse -File | Measure-Object Length -Sum).Sum / 1MB))
Write-Host ("Bundled sites: {0}" -f (($sites | ForEach-Object { "$($_.site_id) [$($_.package_id), synthetic=$($_.synthetic)]" }) -join "; "))

function Get-GpuMb {
    $value = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    if ($value) { [int]$value } else { -1 }
}
$failed = 0
function Run([string]$name, [string[]]$arguments) {
    $png = Join-Path $Out "$name.png"
    if (Test-Path $png) { Remove-Item $png }
    $before = Get-GpuMb
    $all = @("-windowed", "-ResX=$ResX", "-ResY=$ResY", "-LsnShot=`"$png`"") + $arguments
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $exe -ArgumentList $all -PassThru
    $peak = $before
    $connections = @{}
    while (-not $process.HasExited -and $watch.Elapsed.TotalSeconds -lt 180) {
        Start-Sleep -Milliseconds 500
        $now = Get-GpuMb
        if ($now -gt $peak) { $peak = $now }
        # The launcher starts the real program as a child process: look at every process of the build.
        foreach ($p in @(Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($Build, [System.StringComparison]::OrdinalIgnoreCase) })) {
            foreach ($c in @(Get-NetTCPConnection -OwningProcess $p.Id -ErrorAction SilentlyContinue)) { $connections["tcp $($c.RemoteAddress):$($c.RemotePort) $($c.State)"] = 1 }
            foreach ($u in @(Get-NetUDPEndpoint -OwningProcess $p.Id -ErrorAction SilentlyContinue)) { $connections["udp local $($u.LocalAddress):$($u.LocalPort)"] = 1 }
        }
        $process.Refresh()
    }
    if (-not $process.HasExited) { $process.Kill(); Write-Host "$name : did not finish in 180 s" ; $script:failed++; return }
    # The launcher may return before its child has written the frame.
    for ($i = 0; $i -lt 40 -and -not (Test-Path $png); $i++) { Start-Sleep -Milliseconds 500 }
    $ok = (Test-Path $png) -and ((Get-Item $png).Length -gt 20000)
    if (-not $ok) { $script:failed++ }
    $gpu = if ($before -ge 0) { "{0} MB above the {1} MB in use before the start" -f ($peak - $before), $before } else { "not measured (no nvidia-smi)" }
    $net = if ($connections.Count -eq 0) { "none" } else { ($connections.Keys | Sort-Object) -join ", " }
    Write-Host ("{0,-34} {1}  {2:N0} s  frame {3}  GPU memory peak {4}  network endpoints: {5}" -f $name, $(if ($ok) { "OK  " } else { "FAIL" }), $watch.Elapsed.TotalSeconds,
        $(if (Test-Path $png) { "{0:N0} kB" -f ((Get-Item $png).Length / 1KB) } else { "missing" }), $gpu, $net)
}
foreach ($site in $sites) { Run "site_$($site.site_id)" @("-LsnSite=$($site.site_id)", "-LsnTime=24") }
if ($sites.Count -ge 2) { Run "compare_two_sites" @("-LsnCompare=$($sites[0].site_id),$($sites[1].site_id)", "-LsnTime=24") }
Write-Host ("Frames in {0}. {1}" -f $Out, $(if ($failed -eq 0) { "All runs produced a frame." } else { "$failed run(s) FAILED." }))
exit $(if ($failed -eq 0) { 0 } else { 1 })
