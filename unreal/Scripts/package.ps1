# Builds the stand-alone Windows program (no editor needed to run it).
#
# The packages under Content/LsnPackages (see import_packages.ps1) are staged with it as
# plain files, so the program shows them without any network access. The result is a
# folder with LunarSiteNavigator.exe; copy the whole folder.
#
# Example:
#   unreal\Scripts\import_packages.ps1 C:\Projects\lsn-packages\sites
#   unreal\Scripts\package.ps1 -Out C:\Projects\lsn-build
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Configuration = "Shipping"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "LunarSiteNavigator.uproject"
$packages = Join-Path $root "Content\LsnPackages\index.json"
if (-not (Test-Path $packages)) { Write-Host "No packages under Content\LsnPackages: run import_packages.ps1 first."; exit 1 }
$outFull = [System.IO.Path]::GetFullPath($Out)
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$project" -noP4 -platform=Win64 "-clientconfig=$Configuration" `
    -build -cook -stage -pak -archive "-archivedirectory=$outFull" -nodebuginfo -utf8output -unattended
if ($LASTEXITCODE -ne 0) { Write-Host "Packaging failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }
$exe = Get-ChildItem -Path $outFull -Recurse -Filter "LunarSiteNavigator.exe" | Select-Object -First 1
if (-not $exe) { Write-Host "Packaging reported success but no LunarSiteNavigator.exe is under $outFull"; exit 1 }
$staged = Get-ChildItem -Path $exe.DirectoryName -Recurse -Filter "index.json" | Where-Object { $_.FullName -like "*LsnPackages*" } | Select-Object -First 1
if (-not $staged) { Write-Host "The packages were not staged next to the program."; exit 1 }
Write-Host "Program:  $($exe.FullName)"
Write-Host "Packages: $($staged.DirectoryName)"
exit 0
