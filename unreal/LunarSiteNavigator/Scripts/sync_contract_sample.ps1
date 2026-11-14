# Exports the contract sample of the core stream into an ignored folder of this project,
# so that the Unreal tests can read it before the core branch is merged into main.
# Nothing is copied into tracked files. Usage: powershell -File sync_contract_sample.ps1 [ref]
param([string]$Ref = "origin/claude/core-649481")
$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$repo = (& git -C $project rev-parse --show-toplevel).Trim()
$out = Join-Path $project "Saved\ContractSample"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null
& git -C $repo fetch origin
$tar = Join-Path $out "sample.tar"
& git -C $repo archive --format=tar -o $tar $Ref docs/contract/sample
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
# The Windows tar is named explicitly: a GNU tar on PATH reads "C:" as a host name.
& (Join-Path $env:SystemRoot "System32/tar.exe") -xf $tar -C $out
if ($LASTEXITCODE -ne 0) { throw "tar failed" }
Remove-Item $tar
$commit = (& git -C $repo rev-parse $Ref).Trim()
Set-Content -Path (Join-Path $out "SOURCE.txt") -Value "ref=$Ref`ncommit=$commit" -Encoding ascii
Write-Output "Contract sample from $Ref ($commit) exported to $out"
