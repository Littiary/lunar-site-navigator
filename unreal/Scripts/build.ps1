# Builds the editor target from the command line.
# Only one session compiles this project at a time.
param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Configuration = "Development",
    [string]$Target = "LunarSiteNavigatorEditor"
)
$ErrorActionPreference = "Stop"
$project = Join-Path (Split-Path -Parent $PSScriptRoot) "LunarSiteNavigator.uproject"
& "$EngineRoot\Engine\Build\BatchFiles\Build.bat" $Target Win64 $Configuration "-Project=$project" -WaitMutex -NoHotReloadFromIDE
exit $LASTEXITCODE
