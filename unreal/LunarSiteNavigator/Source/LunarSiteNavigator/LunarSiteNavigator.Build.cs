using UnrealBuildTool;

public class LunarSiteNavigator : ModuleRules
{
	public LunarSiteNavigator(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core", "CoreUObject", "Engine", "InputCore", "Json", "ProceduralMeshComponent"
		});
	}
}
