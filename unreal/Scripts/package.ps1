# Builds the stand-alone Windows program (no editor needed to run it).
#
# The published packages (packages/ at the root of the repository) are copied into the
# build as plain files, together with the terrain samples of Scripts/export_terrain.py, so
# the program shows them without any network access. The copy under Content/LsnPackages
# exists only while the build runs. The result is a folder with LunarSiteNavigator.exe;
# copy the whole folder.
#
# Example:
#   unreal\Scripts\package.ps1 -Out C:\Projects\lsn-build
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Configuration = "Shipping"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "LunarSiteNavigator.uproject"
$published = Join-Path (Split-Path -Parent $root) "packages"
if (-not (Test-Path (Join-Path $published "index.json"))) { Write-Host "No published packages at $published"; exit 1 }
$staging = Join-Path $root "Content\LsnPackages"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
Copy-Item -Recurse $published $staging
$commit = (git -C $root rev-parse --short HEAD).Trim()
Set-Content -Path (Join-Path $staging "COPIED_FROM.txt") -Encoding ascii -Value @("source=packages/ of the repository", "repository_commit=$commit")
$outFull = [System.IO.Path]::GetFullPath($Out)
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun "-project=$project" -noP4 -platform=Win64 "-clientconfig=$Configuration" `
    -build -cook -stage -pak -prereqs -archive "-archivedirectory=$outFull" -nodebuginfo -utf8output -unattended
$uat = $LASTEXITCODE
Remove-Item -Recurse -Force $staging
if ($uat -ne 0) { Write-Host "Packaging failed with exit code $uat"; exit $uat }
$exe = Get-ChildItem -Path $outFull -Recurse -Filter "LunarSiteNavigator.exe" | Select-Object -First 1
if (-not $exe) { Write-Host "Packaging reported success but no LunarSiteNavigator.exe is under $outFull"; exit 1 }
$staged = Get-ChildItem -Path $exe.DirectoryName -Recurse -Filter "index.json" | Where-Object { $_.FullName -like "*LsnPackages*" } | Select-Object -First 1
if (-not $staged) { Write-Host "The packages were not staged next to the program."; exit 1 }
Write-Host "Program:  $($exe.FullName)"
Write-Host "Packages: $($staged.DirectoryName)"
exit 0
