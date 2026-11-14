# Everything to do once new packages are published in packages/ on main, in one command:
#
#   1. merge origin/main into the current branch (skipped with -NoMerge);
#   2. sample the terrain for the new packages (Scripts/export_terrain.py, drawing only);
#   3. build the editor target and run all tests;
#   4. produce the pitch clip and the six stills (Scripts/pitch.ps1); a still whose field the
#      packages do not carry is skipped and named in docs/unreal/pitch/README.txt;
#   5. build the stand-alone program, run it for every site and side by side
#      (Scripts/test_build.ps1) and measure its frame time (Scripts/bench.ps1).
#
# The script stops at the first step that fails. It commits and pushes nothing: look at the
# results first. Close the Unreal editor before running it (the build replaces its files).
#
#   unreal\Scripts\after_packages.ps1
#   unreal\Scripts\after_packages.ps1 -NoMerge -SkipBuild     # material only
param(
    [switch]$NoMerge,
    [switch]$SkipPitch,
    [switch]$SkipBuild,
    [string]$Python = "C:\Projects\lsn-venv\Scripts\python.exe",
    [string]$BuildOut = "C:\Projects\lsn-build",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $root
$watch = [System.Diagnostics.Stopwatch]::StartNew()
function Step([string]$title, [scriptblock]$body) {
    Write-Host ""
    Write-Host ("==== {0}   ({1:N0} min since the start)" -f $title, $watch.Elapsed.TotalMinutes)
    $global:LASTEXITCODE = 0
    & $body
    if ($LASTEXITCODE -ne 0) { Write-Host "STOPPED: '$title' failed with exit code $LASTEXITCODE."; exit 1 }
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { Write-Host "The Unreal editor is running. Close it first."; exit 1 }

if (-not $NoMerge) {
    Step "Merge origin/main" {
        if (git -C $repo status --porcelain --untracked-files=no) { Write-Host "The working tree has changes; commit them first."; $global:LASTEXITCODE = 1; return }
        git -C $repo fetch origin
        if ($LASTEXITCODE -eq 0) { git -C $repo merge --no-edit origin/main }
    }
}
Step "What is published" {
    $index = Get-Content (Join-Path $repo "packages\index.json") -Raw | ConvertFrom-Json
    Write-Host ("contract {0}, generated {1}" -f $index.contract.version, $index.generated_utc)
    foreach ($p in $index.packages) { Write-Host ("  {0,-16} {1,-28} {2}  synthetic={3}" -f $p.kind, $p.site_id, $p.package_id, $p.synthetic) }
}
Step "Terrain samples for the published packages" { & $Python (Join-Path $PSScriptRoot "export_terrain.py") (Join-Path $repo "packages") }
Step "Build" { & (Join-Path $PSScriptRoot "build.ps1") -EngineRoot $EngineRoot }
Step "Tests" { & (Join-Path $PSScriptRoot "run_tests.ps1") -EngineRoot $EngineRoot }
if (-not $SkipPitch) {
    Step "Pitch clip and stills" { & (Join-Path $PSScriptRoot "pitch.ps1") -EngineRoot $EngineRoot }
    Get-Content (Join-Path $repo "docs\unreal\pitch\README.txt") | Where-Object { $_ -match "NOT PRODUCED" } | ForEach-Object { Write-Host "  $_" }
}
if (-not $SkipBuild) {
    Step "Stand-alone program" { & (Join-Path $PSScriptRoot "package.ps1") -Out $BuildOut -EngineRoot $EngineRoot }
    Step "Run the stand-alone program" { & (Join-Path $PSScriptRoot "test_build.ps1") -Build (Join-Path $BuildOut "Windows") }
    Step "Frame time of the stand-alone program" { & (Join-Path $PSScriptRoot "bench.ps1") -Build (Join-Path $BuildOut "Windows") }
}
Write-Host ""
Write-Host ("Done in {0:N0} min. Nothing was committed. Changed files:" -f $watch.Elapsed.TotalMinutes)
git -C $repo status --short
