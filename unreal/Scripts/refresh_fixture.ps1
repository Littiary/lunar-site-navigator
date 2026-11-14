# Replaces unreal/TestData/contract-sample/packages with the contract sample of a git ref.
# The copy is never edited by hand.
param([Parameter(Mandatory = $true)][string]$Ref)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$target = Join-Path $repo "unreal\TestData\contract-sample"
$staging = Join-Path $env:TEMP "lsn_contract_sample"
$tar = Join-Path $env:TEMP "lsn_contract_sample.tar"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force $staging | Out-Null
# No end-of-line conversion: the copy must equal the blobs of the ref byte for byte.
git -C $repo -c core.autocrlf=false -c core.eol=lf archive -o $tar $Ref docs/contract/sample/packages
if ($LASTEXITCODE -ne 0) { Write-Host "git archive failed for $Ref"; exit 1 }
# The Windows tar is named explicitly: a GNU tar on PATH reads "C:" as a host name.
& (Join-Path $env:SystemRoot "System32/tar.exe") -x -f $tar -C $staging --strip-components=3
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $staging "packages\index.json"))) { Write-Host "Extracting the sample failed; the fixture was left as it was."; exit 1 }
Remove-Item $tar
# Only now is the old copy replaced.
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
Move-Item $staging $target
$commit = (git -C $repo rev-parse --short $Ref).Trim()
Write-Host "Fixture refreshed from $Ref ($commit)"
