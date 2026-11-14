# Opens the Unreal editor on this project with the engine's own "Unreal MCP" plugin
# (ModelContextProtocol, experimental, ships with Unreal Engine 5.8) and the editor toolset,
# so that a local assistant can reach the editor at http://127.0.0.1:8000/mcp.
#
# Both plugins are listed in the .uproject as optional and editor-only. In this engine
# version an optional plugin is not loaded by itself, so the project opens and builds the
# same without them; this script switches them on for one editor session. The server
# starts by itself (Config/DefaultEditorPerProjectUserSettings.ini). Nothing of this is in
# the packaged build.
param([string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8")
$project = Join-Path (Split-Path -Parent $PSScriptRoot) "LunarSiteNavigator.uproject"
$log = Join-Path (Split-Path -Parent $PSScriptRoot) "Saved\Logs\EditorMcp.log"
Start-Process -FilePath "$EngineRoot\Engine\Binaries\Win64\UnrealEditor.exe" -ArgumentList @("`"$project`"", "-EnablePlugins=ModelContextProtocol,EditorToolset", "-nosplash", "-abslog=`"$log`"")
Write-Host "Editor starting. MCP endpoint: http://127.0.0.1:8000/mcp (log: $log)"
