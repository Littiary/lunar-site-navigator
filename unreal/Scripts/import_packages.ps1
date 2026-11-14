# Copies a package root (a folder with index.json, written by the science core) into
# unreal/Content/LsnPackages, where the scene looks first and from where a packaged build
# stages it. The copy is not under version control and is never edited.
#
# Example (after `python -m validation.sites.run <sites.json> --out C:\Projects\lsn-packages\sites`):
#   unreal\Scripts\import_packages.ps1 C:\Projects\lsn-packages\sites
param([Parameter(Mandatory = $true)][string]$PackageRoot)
$ErrorActionPreference = "Stop"
$source = [System.IO.Path]::GetFullPath($PackageRoot)
if (-not (Test-Path (Join-Path $source "index.json"))) { Write-Host "$source has no index.json"; exit 1 }
$target = Join-Path (Split-Path -Parent $PSScriptRoot) "Content\LsnPackages"
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
Copy-Item -Recurse $source $target
$index = Get-Content (Join-Path $target "index.json") -Raw | ConvertFrom-Json
Set-Content -Path (Join-Path $target "IMPORTED_FROM.txt") -Encoding ascii -Value @(
    "source=$source",
    "imported_utc=$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))",
    "packages=$(($index.packages | ForEach-Object { $_.package_id }) -join ',')"
)
foreach ($p in $index.packages) { Write-Host ("{0,-16} {1}  synthetic={2}  {3}" -f $p.kind, $p.package_id, $p.synthetic, $p.name) }
Write-Host "Imported into $target"
