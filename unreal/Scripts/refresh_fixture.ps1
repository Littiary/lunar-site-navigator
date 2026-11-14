# Replaces unreal/TestData/contract-sample/packages with the contract sample of a git ref.
# The copy is never edited by hand.
param([Parameter(Mandatory = $true)][string]$Ref)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$target = Join-Path $repo "unreal\TestData\contract-sample"
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Force $target | Out-Null
$tar = Join-Path $env:TEMP "lsn_contract_sample.tar"
git -C $repo archive -o $tar $Ref docs/contract/sample/packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
tar -x -f $tar -C $target --strip-components=3
Remove-Item $tar
Write-Host "Fixture refreshed from $Ref"
