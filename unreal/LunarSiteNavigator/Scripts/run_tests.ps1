# Runs the automated tests of the Unreal stream without opening the editor window.
# Exit code 0 only if every "Lsn." test passed. Usage: powershell -File run_tests.ps1 [-Engine <dir>]
param([string]$Engine = "C:\Program Files\Epic Games\UE_5.8")
$ErrorActionPreference = "Stop"
$project = Join-Path (Split-Path -Parent $PSScriptRoot) "LunarSiteNavigator.uproject"
$saved = Join-Path (Split-Path -Parent $PSScriptRoot) "Saved"
$log = Join-Path $saved "Lsn\tests.log"
$report = Join-Path $saved "Lsn\TestReport"
New-Item -ItemType Directory -Force (Split-Path -Parent $log) | Out-Null
if (Test-Path $report) { Remove-Item -Recurse -Force $report }
$editor = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$arguments = @("`"$project`"", "-ExecCmds=`"Automation RunTests Lsn.; Quit`"", "-TestExit=`"Automation Test Queue Empty`"",
    "-ReportExportPath=`"$report`"", "-unattended", "-nullrhi", "-nosplash", "-nosound", "-nopause", "-abslog=`"$log`"")
$process = Start-Process -FilePath $editor -ArgumentList $arguments -Wait -PassThru -NoNewWindow
$json = Join-Path $report "index.json"
if (-not (Test-Path $json)) { Write-Output "No test report was written. See $log"; exit 2 }
$result = Get-Content $json -Raw | ConvertFrom-Json
foreach ($test in $result.tests) {
    Write-Output ("{0,-8} {1}" -f $test.state, $test.fullTestPath)
    foreach ($entry in $test.entries) { Write-Output ("         [{0}] {1}" -f $entry.event.type, $entry.event.message) }
}
Write-Output ("succeeded={0} failed={1} notRun={2}" -f $result.succeeded, $result.failed, $result.notRun)
if ($result.failed -gt 0 -or $result.succeeded -eq 0 -or $result.notRun -gt 0) { exit 1 }
exit 0
