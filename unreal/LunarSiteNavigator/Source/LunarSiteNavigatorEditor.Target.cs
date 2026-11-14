using UnrealBuildTool;

public class LunarSiteNavigatorEditorTarget : TargetRules
{
	public LunarSiteNavigatorEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("LunarSiteNavigator");
	}
}
