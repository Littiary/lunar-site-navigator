// Layered regolith material and ambient occlusion.
//
// Criteria, written on 15 November 2026 before the first run:
//
// R1. Ambient occlusion never darkens the Sun's light.
//     After a package is loaded, the Sun's light has no light function. The earthshine and the
//     zenith fill (light that is not the Sun's) carry the light function made from M_LsnLightAO,
//     and where that function is not evaluated they keep their full brightness (disabled
//     brightness 1), so that the light function can only take light away in the hollows.
// R2. The detail textures are fit for close views.
//     T_LsnRegolithMacro and T_LsnRegolithMicro load, are at least 2048 x 2048, hold data (no sRGB
//     curve) and wrap at their edges (tileable); M_LsnLightAO is a light function material.
// R3. Far ridges keep their light under a grazing Sun (written on 15 November 2026 after the
//     regression of f69e0ae, before the fix): the Sun's light and the earthshine have no contact
//     shadows (screen-space shadows whose length grows with the distance darkened the sunlit
//     ridges of distant terrain at a Sun elevation of 1 to 2 degrees), as in 0b1cb68.
//
// Amended on 15 November 2026, before the change, when the earthshine light was removed (see
// LsnEarthshineTests.cpp): in R1 the zenith fill is the only light that is not the Sun's, and in R3 only
// the Sun's light is left to check.

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnRegolithTest
{
	bool MadeFrom(const UMaterialInterface* Material, const TCHAR* Name)
	{
		const UMaterial* Base = Material ? Material->GetMaterial_Concurrent() : nullptr;
		return Base && Base->GetName() == Name;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnRegolithSunTest, "LunarSiteNavigator.Regolith.OcclusionNeverOnTheSun", LsnTest::Flags)
bool FLsnRegolithSunTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->BeginPlay();
	ALsnSiteScene* Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
	FString Error;
	if (TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error), Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		TestNull(TEXT("the Sun's light has no light function"), Scene->GetSunLight()->LightFunctionMaterial.Get());
		const UDirectionalLightComponent* Fill = Scene->GetFillLight();
		TestTrue(TEXT("the fill carries the occlusion light function"), LsnRegolithTest::MadeFrom(Fill->LightFunctionMaterial, TEXT("M_LsnLightAO")));
		TestEqual(TEXT("the fill keeps its full brightness where the function is not evaluated"), Fill->DisabledBrightness, 1.0f);
		TestEqual(TEXT("the Sun's light has no contact shadows (R3)"), Scene->GetSunLight()->ContactShadowLength, 0.0f);
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnRegolithTexturesTest, "LunarSiteNavigator.Regolith.DetailTextures", LsnTest::Flags)
bool FLsnRegolithTexturesTest::RunTest(const FString& Parameters)
{
	for (const TCHAR* Name : { TEXT("T_LsnRegolithMacro"), TEXT("T_LsnRegolithMicro") })
	{
		const UTexture2D* Texture = LoadObject<UTexture2D>(nullptr, *FString::Printf(TEXT("/Game/Lsn/%s.%s"), Name, Name));
		if (!TestNotNull(FString::Printf(TEXT("%s loads"), Name), Texture))
		{
			continue;
		}
		// The size of the imported image (the editor's source data: no GPU resource is made under the test commandlet).
#if WITH_EDITORONLY_DATA
		const int64 Width = Texture->Source.GetSizeX(), Height = Texture->Source.GetSizeY();
#else
		const int64 Width = Texture->GetSizeX(), Height = Texture->GetSizeY();
#endif
		TestTrue(FString::Printf(TEXT("%s is at least 2048 x 2048 (%lld x %lld)"), Name, Width, Height), Width >= 2048 && Height >= 2048);
		TestFalse(FString::Printf(TEXT("%s holds data, not colours"), Name), Texture->SRGB);
		TestTrue(FString::Printf(TEXT("%s wraps at its edges"), Name), Texture->AddressX == TA_Wrap && Texture->AddressY == TA_Wrap);
	}
	const UMaterial* LightAO = LoadObject<UMaterial>(nullptr, TEXT("/Game/Lsn/M_LsnLightAO.M_LsnLightAO"));
	if (TestNotNull(TEXT("M_LsnLightAO loads"), LightAO))
	{
		TestTrue(TEXT("M_LsnLightAO is a light function"), LightAO->MaterialDomain == MD_LightFunction);
	}
	return true;
}

#endif
