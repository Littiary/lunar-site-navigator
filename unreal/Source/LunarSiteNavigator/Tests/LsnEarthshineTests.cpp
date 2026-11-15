// Earthshine as shown.
//
// Criteria, written on 15 November 2026 before the change (viewers took the earthshine at 10 % of the
// Sun's display intensity for sunlight, against a card that said "Sun hidden"):
//
// E1. The earthshine is shown at 4 % of the Sun's display intensity for a full Earth
//     (lsn.Look.EarthshineShare = 0.04).
// E2. Its colour is clearly cold, apart from the warm white of the Sun: blue at least 1.5 times red,
//     green between the two.
// E3. While the earthshine is on (the package gives the Sun as hidden and the Earth as visible) the
//     view says so: "Lit by earthshine, shown brighter than real"; otherwise nothing.

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Scene/LsnHud.h"
#include "Scene/LsnLook.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnEarthshineShownTest, "LunarSiteNavigator.Earthshine.ShownFaintAndCold", LsnTest::Flags)
bool FLsnEarthshineShownTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("E1: earthshine at 4 % of the Sun's display intensity"), LsnLook::EarthshineShare.GetValueOnGameThread(), 0.04f);

	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->BeginPlay();
	const ALsnSiteScene* Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
	const FLinearColor Colour = Scene->GetEarthLight()->GetLightColor();
	TestTrue(FString::Printf(TEXT("E2: blue at least 1.5 times red (%.2f, %.2f, %.2f)"), Colour.R, Colour.G, Colour.B), Colour.B >= 1.5f * Colour.R);
	TestTrue(FString::Printf(TEXT("E2: green between red and blue (%.2f, %.2f, %.2f)"), Colour.R, Colour.G, Colour.B), Colour.G > Colour.R && Colour.G < Colour.B);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);

	TestEqual(TEXT("E3: the label while the earthshine is on"), LsnHudText::EarthshineLabel(true), FString(TEXT("Lit by earthshine, shown brighter than real")));
	TestTrue(TEXT("E3: no label otherwise"), LsnHudText::EarthshineLabel(false).IsEmpty());
	return true;
}

#endif
