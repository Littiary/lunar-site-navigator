using UnrealBuildTool;

public class LunarSiteNavigatorTarget : TargetRules
{
	public LunarSiteNavigatorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("LunarSiteNavigator");
	}
}
