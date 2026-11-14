// "Show the obstacle" (contract 0.2, SPEC 5.3 and 5.5).
//
// Criteria and tolerances, written before the first run:
//
// I. Reader. A 0.2 package gives horizon.obstacle_id, horizon.obstacles, the series
//    channel blocker_azimuth_index and timeline.blockers. Every azimuth of an obstacle's
//    run carries that obstacle's id; a blocker names an existing obstacle of its own
//    observer height and repeats its peak; blockers of one body and height are sorted by
//    cost, and their shares add up to at most 1 (1e-6). A package without these fields
//    (0.1) still loads, and the view is hidden.
//
// J. The viewer recipe of SPEC 5.5, on a hand-made package (exact) and on the sample:
//    at a sample, the limiting azimuth index is the package's blocker_azimuth_index, the
//    obstacle is obstacle_id at that index, the cost is lost_s of the blocker record with
//    that body, height and obstacle, and there is no cost if there is no such record.
//    The scene decides nothing of this itself.
//
// K. Highlight in the scene. While a body is hidden or partly hidden, a highlight is
//    drawn along the run of the obstacle the package names: seen from the eye every
//    highlight vertex lies within the azimuths of the run (0.001 deg), and its lower
//    edge is the package horizon of those azimuths (0.001 deg). While the whole disc of
//    the Sun is visible (and while the Earth's centre is above the horizon) there is no
//    highlight for that body. Without the 0.2 fields there is never one.
//
// L. Wording. The sentence states the distance and azimuth of the limiting terrain point
//    and the hours the obstacle costs in the computed window compared with a smooth
//    sphere; it says so when the obstacle costs nothing, and it says "within 1 km:
//    depends on single pixels of the elevation model" for a near-field obstacle.

#include "Tests/LsnTestSupport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnHud.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnBlockerTest
{
	constexpr double ShareTolerance = 1e-6;
	constexpr double HighlightToleranceDeg = 0.001;

	struct FSceneFixture
	{
		UWorld* World = nullptr;
		ALsnSiteScene* Scene = nullptr;

		FSceneFixture()
		{
			World = UWorld::CreateWorld(EWorldType::Game, false);
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->BeginPlay();
			Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
		}

		~FSceneFixture()
		{
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
	};

	/**
	 * Hand-made package: 8 azimuths of 45 deg, one observer height, 4 time samples.
	 * Obstacle 0 covers azimuth indices 6, 7, 0, 1 (a run through north), obstacle 1 covers 2 .. 5.
	 */
	inline FLsnSitePackage HandMadePackage()
	{
		FLsnSitePackage P;
		P.ContractVersion = TEXT("0.2");
		P.ObserverHeightsM = { 2.0 };
		P.AzimuthStartDeg = 0.0;
		P.AzimuthStepDeg = 45.0;
		P.AzimuthCount = 8;
		P.HorizonElevationDeg = { 1.0f, 1.5f, 0.2f, 0.3f, 0.4f, 0.1f, 0.8f, 0.9f };
		P.HorizonDistanceM = { 5000.0f, 5100.0f, 300.0f, 310.0f, 320.0f, 330.0f, 4900.0f, 4950.0f };
		P.ObstacleId = { 0, 0, 1, 1, 1, 1, 0, 0 };
		FLsnObstacle Far;
		Far.Id = 0;
		Far.AzimuthStartIndex = 6;
		Far.AzimuthCount = 4;
		Far.AzimuthStartDeg = 270.0;
		Far.AzimuthEndDeg = 45.0;
		Far.PeakAzimuthDeg = 45.0;
		Far.PeakElevationDeg = 1.5;
		Far.PeakDistanceM = 5100.0;
		FLsnObstacle Near;
		Near.Id = 1;
		Near.AzimuthStartIndex = 2;
		Near.AzimuthCount = 4;
		Near.AzimuthStartDeg = 90.0;
		Near.AzimuthEndDeg = 225.0;
		Near.PeakAzimuthDeg = 180.0;
		Near.PeakElevationDeg = 0.4;
		Near.PeakDistanceM = 320.0;
		Near.bNearField = true;
		P.Obstacles = { Far, Near };

		P.bHasTimeline = true;
		P.Time.StartEtS = 0.0;
		P.Time.StepS = 3600.0;
		P.Time.Count = 4;
		P.Bodies = { TEXT("SUN") };
		FLsnBodySeries& Sun = P.Series.Add(TEXT("SUN"));
		Sun.AzimuthDeg = { 44.0f, 46.0f, 135.0f, 300.0f };
		Sun.ElevationDeg = { 1.0f, 1.2f, 0.0f, 5.0f };
		Sun.AngularRadiusDeg = { 0.27f, 0.27f, 0.27f, 0.27f };
		Sun.MarginDeg = { -0.5f, -0.3f, -0.3f, 4.2f };
		Sun.VisibleFraction = { 0.0f, 0.2f, 0.0f, 1.0f };
		Sun.BlockerAzimuthIndex = { 1, 1, 3, 7 };
		FLsnBlocker Cost;
		Cost.Body = TEXT("SUN");
		Cost.HeightIndex = 0;
		Cost.ObstacleId = 0;
		Cost.LostS = 36000.0;
		Cost.ShareOfLost = 1.0;
		Cost.Method = TEXT("timeline.blocking");
		P.Blockers = { Cost };
		return P;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnBlockerRecipeTest, "LunarSiteNavigator.Package.BlockerRecipe", LsnTest::Flags)
bool FLsnBlockerRecipeTest::RunTest(const FString& Parameters)
{
	using namespace LsnBlockerTest;
	const FLsnSitePackage P = HandMadePackage();

	FLsnBlocking B;
	TestTrue(TEXT("J: sample 0 has blocking information"), P.BlockingAt(TEXT("SUN"), 0, 0, B));
	TestEqual(TEXT("J: limiting azimuth index is the package's"), B.AzimuthIndex, 1);
	TestEqual(TEXT("J: limiting azimuth"), B.AzimuthDeg, 45.0, 1e-12);
	TestEqual(TEXT("J: limiting distance is horizon.distance_m there"), B.DistanceM, 5100.0, 1e-9);
	TestEqual(TEXT("J: obstacle is obstacle_id there"), B.ObstacleId, 0);
	TestTrue(TEXT("J: the obstacle record is found"), B.Obstacle != nullptr && B.Obstacle->AzimuthStartIndex == 6);
	TestTrue(TEXT("J: the blocker record of that obstacle is found"), B.Blocker != nullptr);
	TestEqual(TEXT("J: cost is lost_s of that record"), B.Blocker ? B.Blocker->LostS : -1.0, 36000.0, 1e-9);
	TestEqual(TEXT("J: visible fraction of the sample"), B.VisibleFraction, 0.0, 1e-12);
	TestTrue(TEXT("J: hidden"), B.bHiddenOrPartly);

	TestTrue(TEXT("J: sample 1"), P.BlockingAt(TEXT("SUN"), 0, 1, B));
	TestTrue(TEXT("J: a partly hidden disc counts as blocked"), B.bHiddenOrPartly);
	TestEqual(TEXT("J: visible fraction of a partly hidden disc"), B.VisibleFraction, 0.2, 1e-6);

	TestTrue(TEXT("J: sample 2"), P.BlockingAt(TEXT("SUN"), 0, 2, B));
	TestEqual(TEXT("J: obstacle of sample 2"), B.ObstacleId, 1);
	TestTrue(TEXT("J: an obstacle without a blocker record costs nothing"), B.Blocker == nullptr);
	TestTrue(TEXT("J: near-field flag comes from the obstacle record"), B.Obstacle && B.Obstacle->bNearField);

	TestTrue(TEXT("J: sample 3"), P.BlockingAt(TEXT("SUN"), 0, 3, B));
	TestFalse(TEXT("J: a fully visible disc is not blocked"), B.bHiddenOrPartly);

	TestFalse(TEXT("J: no information for a body without the channel"), P.BlockingAt(TEXT("EARTH"), 0, 0, B));
	TestFalse(TEXT("J: no information outside the time axis"), P.BlockingAt(TEXT("SUN"), 0, 4, B));

	// The run of an obstacle, through azimuth 0.
	TArray<int32> Run;
	P.ObstacleRun(P.Obstacles[0], Run);
	TestEqual(TEXT("run through north"), Run, TArray<int32>({ 6, 7, 0, 1 }));

	// L. Wording.
	P.BlockingAt(TEXT("SUN"), 0, 0, B);
	TArray<FString> Lines;
	LsnHudText::BlockerSentences(TEXT("SUN"), P, B, Lines);
	TestEqual(TEXT("L: two sentences"), Lines.Num(), 2);
	if (Lines.Num() == 2)
	{
		TestEqual(TEXT("L: what hides it"), Lines[0], FString(TEXT("SUN hidden by terrain 5.1 km away, azimuth 45.0 deg")));
		TestEqual(TEXT("L: what it costs"), Lines[1], FString(TEXT("this obstacle costs 10.0 h of SUN in the computed window (100 % of the time lost to terrain, against a smooth sphere)")));
	}
	P.BlockingAt(TEXT("SUN"), 0, 1, B);
	LsnHudText::BlockerSentences(TEXT("SUN"), P, B, Lines);
	TestTrue(TEXT("L: partly hidden is said with the visible share"), Lines.Num() > 0 && Lines[0].StartsWith(TEXT("SUN partly hidden (20 % visible) by terrain")));
	P.BlockingAt(TEXT("SUN"), 0, 2, B);
	LsnHudText::BlockerSentences(TEXT("SUN"), P, B, Lines);
	TestEqual(TEXT("L: three sentences for a near-field obstacle"), Lines.Num(), 3);
	if (Lines.Num() == 3)
	{
		TestEqual(TEXT("L: metres below one kilometre"), Lines[0], FString(TEXT("SUN hidden by terrain 310 m away, azimuth 135.0 deg")));
		TestTrue(TEXT("L: no cost is said"), Lines[1].Contains(TEXT("costs no SUN time against a smooth sphere")));
		TestTrue(TEXT("L: near field is said"), Lines[2].Contains(TEXT("within 1 km: depends on single pixels of the elevation model")));
	}
	P.BlockingAt(TEXT("SUN"), 0, 3, B);
	LsnHudText::BlockerSentences(TEXT("SUN"), P, B, Lines);
	TestEqual(TEXT("L: nothing is said while the disc is fully visible"), Lines.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnBlockerSampleTest, "LunarSiteNavigator.Package.ObstaclesOfTheSample", LsnTest::Flags)
bool FLsnBlockerSampleTest::RunTest(const FString& Parameters)
{
	using namespace LsnBlockerTest;
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	if (!TestTrue(TEXT("I: the pinned sample is a 0.2 package with obstacles"), P.HasObstacles()))
	{
		return false;
	}
	TestEqual(TEXT("I: obstacle_id has one value per height and azimuth"), P.ObstacleId.Num(), P.NumHeights() * P.AzimuthCount);
	int32 WrongId = 0, WrongHeight = 0;
	for (int32 K = 0; K < P.Obstacles.Num(); ++K)
	{
		const FLsnObstacle& O = P.Obstacles[K];
		WrongId += O.Id == K ? 0 : 1;
		TArray<int32> Run;
		P.ObstacleRun(O, Run);
		for (const int32 A : Run)
		{
			WrongId += P.ObstacleId[O.HeightIndex * P.AzimuthCount + A] == O.Id ? 0 : 1;
		}
		WrongHeight += P.ObserverHeightsM.IsValidIndex(O.HeightIndex) ? 0 : 1;
	}
	TestEqual(TEXT("I: every azimuth of a run carries the id of its obstacle"), WrongId, 0);
	TestEqual(TEXT("I: every obstacle belongs to an observer height"), WrongHeight, 0);

	TMap<FString, double> ShareSum, LastCost;
	int32 BadBlockers = 0, Unsorted = 0;
	for (const FLsnBlocker& B : P.Blockers)
	{
		const FString Key = FString::Printf(TEXT("%s/%d"), *B.Body, B.HeightIndex);
		ShareSum.FindOrAdd(Key) += B.ShareOfLost;
		if (const double* Previous = LastCost.Find(Key))
		{
			Unsorted += B.LostS <= *Previous + 1e-9 ? 0 : 1;
		}
		LastCost.Add(Key, B.LostS);
		if (B.ObstacleId >= 0)
		{
			const bool bOk = P.Obstacles.IsValidIndex(B.ObstacleId) && P.Obstacles[B.ObstacleId].HeightIndex == B.HeightIndex
				&& FMath::Abs(P.Obstacles[B.ObstacleId].PeakDistanceM - B.PeakDistanceM) < 1e-6;
			BadBlockers += bOk ? 0 : 1;
		}
	}
	TestTrue(TEXT("I: the sample has blockers"), P.Blockers.Num() > 0);
	TestEqual(TEXT("I: blockers name an obstacle of their own height and repeat its peak"), BadBlockers, 0);
	TestEqual(TEXT("I: blockers of a body and height are sorted by cost"), Unsorted, 0);
	for (const TPair<FString, double>& Pair : ShareSum)
	{
		TestTrue(FString::Printf(TEXT("I: shares of %s add up to at most 1"), *Pair.Key), Pair.Value <= 1.0 + ShareTolerance);
	}

	// J on the sample: the recipe gives, at every sample, what the package arrays say.
	int32 Mismatch = 0, Blocked = 0, WithCost = 0;
	for (const FString& Body : P.Bodies)
	{
		const FLsnBodySeries* S = P.FindSeries(Body);
		for (int32 H = 0; S && H < P.NumHeights(); ++H)
		{
			for (int32 T = 0; T < P.Time.Count; ++T)
			{
				FLsnBlocking B;
				if (!P.BlockingAt(Body, H, T, B))
				{
					++Mismatch;
					continue;
				}
				const int32 J = S->BlockerAzimuthIndex[H * P.Time.Count + T];
				Mismatch += (B.AzimuthIndex == J && B.ObstacleId == P.ObstacleId[H * P.AzimuthCount + J]) ? 0 : 1;
				Blocked += B.bHiddenOrPartly ? 1 : 0;
				WithCost += (B.bHiddenOrPartly && B.Blocker) ? 1 : 0;
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d obstacles, %d blockers; %d samples x heights x bodies hidden or partly hidden, %d of them behind an obstacle that costs time"), P.Obstacles.Num(), P.Blockers.Num(), Blocked, WithCost));
	TestEqual(TEXT("J: the recipe follows the package arrays at every sample"), Mismatch, 0);

	// A package without the 0.2 fields: the view is hidden.
	FLsnSitePackage Old = P;
	Old.ObstacleId.Reset();
	Old.Obstacles.Reset();
	Old.Blockers.Reset();
	for (TPair<FString, FLsnBodySeries>& Pair : Old.Series)
	{
		Pair.Value.BlockerAzimuthIndex.Reset();
	}
	FLsnBlocking None;
	TestFalse(TEXT("I: without the fields there is no blocking information"), Old.HasObstacles() || Old.BlockingAt(TEXT("SUN"), 0, 0, None));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnBlockerSceneTest, "LunarSiteNavigator.Acceptance.ObstacleHighlight", LsnTest::Flags)
bool FLsnBlockerSceneTest::RunTest(const FString& Parameters)
{
	using namespace LsnBlockerTest;
	FSceneFixture Fixture;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error),
		Fixture.Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		return false;
	}
	ALsnSiteScene& Scene = *Fixture.Scene;
	const FLsnSitePackage& P = Scene.GetPackage();
	const int32 H = Scene.GetHeightIndex();
	const FVector Eye = Scene.GetEyeUnreal();

	int32 CheckedBlocked = 0, CheckedClear = 0;
	double WorstAzimuthDeg = 0.0, WorstEdgeDeg = 0.0;
	for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
	{
		const bool bSun = FString(Body) == TEXT("SUN");
		for (int32 T = 0; T < P.Time.Count; T += 5)
		{
			Scene.SetTimeIndex(T);
			FLsnBlocking B;
			if (!TestTrue(TEXT("blocking information at the sample"), P.BlockingAt(Body, H, T, B)))
			{
				return false;
			}
			const UProceduralMeshComponent* Highlight = Scene.GetObstacleHighlight(Body);
			if (!B.bHiddenOrPartly)
			{
				TestFalse(FString::Printf(TEXT("K: no %s highlight at sample %d, where the body is clear"), Body, T), Highlight->IsVisible());
				++CheckedClear;
				continue;
			}
			if (!TestTrue(FString::Printf(TEXT("K: %s highlight shown at sample %d"), Body, T), Highlight->IsVisible()) || !B.Obstacle)
			{
				continue;
			}
			++CheckedBlocked;
			TArray<int32> Run;
			P.ObstacleRun(*B.Obstacle, Run);
			const FProcMeshSection* Section = const_cast<UProceduralMeshComponent*>(Highlight)->GetProcMeshSection(0);
			if (!TestNotNull(TEXT("K: the highlight has geometry"), Section) || !TestEqual(TEXT("K: two vertices per azimuth of the run"), Section->ProcVertexBuffer.Num(), 2 * Run.Num()))
			{
				continue;
			}
			for (int32 I = 0; I < Run.Num(); ++I)
			{
				// Vertex 2 I is the lower edge at azimuth Run[I], vertex 2 I + 1 the upper edge.
				for (int32 Edge = 0; Edge < 2; ++Edge)
				{
					const FVector World = Highlight->GetComponentTransform().TransformPosition(FVector(Section->ProcVertexBuffer[2 * I + Edge].Position));
					double Az = 0.0, El = 0.0;
					FLsnSiteFrame::UnrealDirToAzEl(World - Eye, Az, El);
					WorstAzimuthDeg = FMath::Max(WorstAzimuthDeg, FMath::Abs(FMath::Fmod(Az - P.AzimuthDegAt(Run[I]) + 540.0, 360.0) - 180.0));
					if (Edge == 0)
					{
						WorstEdgeDeg = FMath::Max(WorstEdgeDeg, FMath::Abs(El - P.HorizonElevationAt(H, Run[I])));
					}
				}
			}
		}
		// The colour of the highlight tells the bodies apart; that is all it means.
		(void)bSun;
	}
	AddInfo(FString::Printf(TEXT("%d blocked and %d clear samples checked; highlight vertices off their azimuth by at most %.3g deg, lower edge off the package horizon by at most %.3g deg (tolerance %.3f deg)"),
		CheckedBlocked, CheckedClear, WorstAzimuthDeg, WorstEdgeDeg, HighlightToleranceDeg));
	TestTrue(TEXT("blocked samples were checked"), CheckedBlocked > 0);
	TestTrue(TEXT("clear samples were checked"), CheckedClear > 0);
	TestTrue(TEXT("K: the highlight lies on the azimuths of the run"), WorstAzimuthDeg <= HighlightToleranceDeg);
	TestTrue(TEXT("K: the lower edge of the highlight is the package horizon"), WorstEdgeDeg <= HighlightToleranceDeg);

	// Switching the view off hides it; so does a time between samples that is clear on both sides.
	Scene.SetObstacleViewEnabled(false);
	Scene.SetTimeIndex(0);
	TestFalse(TEXT("K: no highlight when the view is switched off"), Scene.GetObstacleHighlight(TEXT("SUN"))->IsVisible() || Scene.GetObstacleHighlight(TEXT("EARTH"))->IsVisible());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
