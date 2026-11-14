# Runs the project's automation tests headless and prints a pass/fail summary.
# Exit code 0 only if every selected test passed.
param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Filter = "LunarSiteNavigator",
    # Tests that render need a real GPU device; pass -Rendered to run without -NullRHI.
    [switch]$Rendered
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root "LunarSiteNavigator.uproject"
$report = Join-Path $root "Saved\TestReport"
if (Test-Path $report) { Remove-Item -Recurse -Force $report }
$log = Join-Path $root "Saved\Logs\AutomationTests.log"
$editor = "$EngineRoot\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$args = @(
    "`"$project`"",
    "-ExecCmds=`"Automation RunTests $Filter; Quit`"",
    "-TestExit=`"Automation Test Queue Empty`"",
    "-ReportExportPath=`"$report`"",
    "-abslog=`"$log`"",
    "-unattended", "-nopause", "-nosplash", "-nosound"
)
if ($Rendered) { $args += @("-RenderOffscreen", "-ResX=1280", "-ResY=720") } else { $args += "-NullRHI" }
$proc = Start-Process -FilePath $editor -ArgumentList $args -NoNewWindow -Wait -PassThru -RedirectStandardOutput (Join-Path $env:TEMP "lsn_tests_stdout.txt")
$json = Join-Path $report "index.json"
if (-not (Test-Path $json)) { Write-Host "No test report was written (editor exit code $($proc.ExitCode)). Log: $log"; exit 2 }
$r = Get-Content $json -Raw | ConvertFrom-Json
foreach ($t in $r.tests) {
    Write-Host ("{0,-8} {1}" -f $t.state, $t.fullTestPath)
    foreach ($e in $t.entries) {
        if ($e.event.type -ne "Info") { Write-Host ("         [{0}] {1}" -f $e.event.type, $e.event.message) }
    }
}
Write-Host ("succeeded {0}, warnings {1}, failed {2}, not run {3}" -f $r.succeeded, $r.succeededWithWarnings, $r.failed, $r.notRun)
if ($r.failed -gt 0 -or $r.notRun -gt 0 -or ($r.succeeded + $r.succeededWithWarnings) -eq 0) { exit 1 }
exit 0
