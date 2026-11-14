// Scale objects (lander, mast, boulders).
//
// Criteria, written before the first run:
//
// P. The objects have the sizes they claim and stand on the ground.
//    Every model file of Content/LsnModels loads, has unit normals, and its lowest point is
//    on the ground within 0.15 m (boulders sit a little into it). The lander is between
//    3.5 and 4.2 m high and between 3.5 and 5 m across. For every observer height of the
//    sample package the sensor head of the mast is at that height: the box of the head
//    (0.16 m high) is centred on it within 0.01 m. Tested on the pole: its top is at the
//    height within 0.01 m for heights of 1 m and more.
//
// Q. The objects do not touch what is measured.
//    With the objects shown or hidden, the terrain mesh of the scene is the same mesh
//    (same vertex count, same positions): the horizon comparison cannot see them.

#include "Tests/LsnTestSupport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mesh/LsnProps.h"
#include "Misc/Paths.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnPropsTest
{
	inline FBox BoundsM(const FLsnMeshData& Mesh)
	{
		FBox Box(ForceInit);
		for (const FVector& P : Mesh.Positions)
		{
			Box += P / 100.0;
		}
		return Box;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPropsModelsTest, "LunarSiteNavigator.Props.ModelsHaveTheirSizes", LsnTest::Flags)
bool FLsnPropsModelsTest::RunTest(const FString& Parameters)
{
	using namespace LsnPropsTest;
	for (const TCHAR* Name : { TEXT("lander"), TEXT("mast_base"), TEXT("mast_pole"), TEXT("boulder_1"), TEXT("boulder_2"), TEXT("boulder_3") })
	{
		FLsnMeshData Mesh;
		FString Error;
		if (!TestTrue(FString::Printf(TEXT("%s loads (%s)"), Name, *Error), LsnProps::LoadObj(FPaths::Combine(LsnProps::ModelDirectory(), FString(Name) + TEXT(".obj")), Mesh, Error)))
		{
			continue;
		}
		double WorstNormal = 0.0;
		for (const FVector& N : Mesh.Normals)
		{
			WorstNormal = FMath::Max(WorstNormal, FMath::Abs(N.Size() - 1.0));
		}
		TestTrue(FString::Printf(TEXT("%s: unit normals (worst %.2g)"), Name, WorstNormal), WorstNormal < 1e-3);
		const FBox Box = BoundsM(Mesh);
		TestTrue(FString::Printf(TEXT("%s: lowest point %.3f m is on the ground"), Name, Box.Min.Z), FMath::Abs(Box.Min.Z) <= 0.15);
		if (FCString::Strcmp(Name, TEXT("lander")) == 0)
		{
			TestTrue(FString::Printf(TEXT("lander height %.2f m"), Box.Max.Z), Box.Max.Z >= 3.5 && Box.Max.Z <= 4.2);
			TestTrue(FString::Printf(TEXT("lander width %.2f m"), Box.GetSize().X), Box.GetSize().X >= 3.5 && Box.GetSize().X <= 5.0);
		}
	}
	FLsnSitePackage P;
	FString Error;
	if (TestTrue(TEXT("the sample package loads"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		for (const float HeightM : P.ObserverHeightsM)
		{
			FLsnMeshData Mast, Pole;
			if (!TestTrue(FString::Printf(TEXT("mast for %.1f m builds (%s)"), HeightM, *Error), LsnProps::BuildMast(HeightM, Mast, Error)))
			{
				continue;
			}
			if (HeightM >= 1.0)
			{
				// The pole alone, as BuildMast stretches it.
				FLsnMeshData Unit;
				LsnProps::LoadObj(FPaths::Combine(LsnProps::ModelDirectory(), TEXT("mast_pole.obj")), Unit, Error);
				LsnProps::Append(Unit, FVector(1.0, 1.0, HeightM - 0.70), 0.0, FVector(0.0, 0.0, 70.0), Pole);
				TestEqual(FString::Printf(TEXT("pole top for %.1f m"), HeightM), BoundsM(Pole).Max.Z, static_cast<double>(HeightM), 0.01);
				TestTrue(FString::Printf(TEXT("mast for %.1f m reaches the height"), HeightM), BoundsM(Mast).Max.Z >= HeightM);
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPropsSceneTest, "LunarSiteNavigator.Props.TerrainUntouched", LsnTest::Flags)
bool FLsnPropsSceneTest::RunTest(const FString& Parameters)
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
		Scene->SetScaleObjectsVisible(true);
		const TArray<FVector> Shown = Scene->GetTerrainMeshData().Positions;
		Scene->SetScaleObjectsVisible(false);
		const TArray<FVector> Hidden = Scene->GetTerrainMeshData().Positions;
		TestEqual(TEXT("same number of terrain vertices"), Shown.Num(), Hidden.Num());
		TestTrue(TEXT("same terrain positions"), Shown == Hidden);
		TestFalse(TEXT("hidden when switched off"), Scene->AreScaleObjectsVisible());
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
