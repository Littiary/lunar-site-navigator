// No earthshine light.
//
// Criteria, written on 15 November 2026 before the change (the earthshine of f69e0ae to 394a738, even at
// 4 % of the Sun's display intensity in a cold blue-grey with a note, lit a hillside the package gives as
// "Sun hidden"; the night light goes back to what 0b1cb68 shows):
//
// N1. There is no setting for an earthshine: the console variable lsn.Look.EarthshineShare does not exist.
// N2. After a package is loaded the scene has exactly two directional lights, the Sun and the zenith fill,
//     as in 0b1cb68: no light from the Earth's direction and no blue light.
// N3. The zenith fill is as in 0b1cb68: white, at lsn.Look.FillLux, without shadows.
//
// The note "Lit by earthshine, shown brighter than real" goes with the light; that it is gone is shown in
// the before and after pictures (docs/unreal/before_after).

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Scene/LsnLook.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnEarthshineRemovedTest, "LunarSiteNavigator.Earthshine.Removed", LsnTest::Flags)
bool FLsnEarthshineRemovedTest::RunTest(const FString& Parameters)
{
	TestNull(TEXT("N1: no lsn.Look.EarthshineShare"), IConsoleManager::Get().FindConsoleVariable(TEXT("lsn.Look.EarthshineShare")));

	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->BeginPlay();
	ALsnSiteScene* Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
	FString Error;
	if (TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error), Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		TArray<UDirectionalLightComponent*> Lights;
		Scene->GetComponents<UDirectionalLightComponent>(Lights);
		TestEqual(TEXT("N2: two directional lights"), Lights.Num(), 2);
		for (const UDirectionalLightComponent* Light : Lights)
		{
			TestTrue(FString::Printf(TEXT("N2: %s is the Sun or the fill"), *Light->GetName()), Light == Scene->GetSunLight() || Light == Scene->GetFillLight());
		}
		const UDirectionalLightComponent* Fill = Scene->GetFillLight();
		TestTrue(TEXT("N3: the fill is white"), Fill->GetLightColor().Equals(FLinearColor::White));
		TestEqual(TEXT("N3: the fill at lsn.Look.FillLux"), Fill->Intensity, LsnLook::FillLux.GetValueOnGameThread());
		TestFalse(TEXT("N3: the fill casts no shadows"), Fill->CastShadows);
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
