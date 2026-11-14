// Planner interface: two sites side by side.
//
// Criteria and tolerances, written before the first run:
//
// M. A scene placed away from the world origin (as the second site of a comparison is)
//    is the same scene: its eye is its own origin plus the observer height, the Sun disc
//    is where the package says within 0.001 deg, and the silhouette of its terrain equals
//    the package horizon within 0.001 deg at every azimuth sample. The offset used in
//    the test is the one the comparison uses.
//    Amendment (2026-11-14). The comparison no longer places its second scene 20 000 km
//    away: that distance was measured to break the shadows of both scenes in the
//    side-by-side view (see LsnPlanner::SecondSceneOffsetCm). Both scenes now stand at the
//    same place and are kept apart by the views and the lighting channels (criterion N).
//    The property of this criterion is still tested 20 000 km from the origin, with the
//    same tolerances; the statement "the offset keeps the two scenes far apart" is
//    withdrawn, because the comparison does not rely on distance any more.
//
// N. Two scenes do not light each other: scene slot 0 has its Sun light, fill light and
//    lit meshes on lighting channel 0 only, slot 1 on channel 1 only.
//
// O. Linked time: both halves of a comparison show the same instant. The position on
//    the second package's time axis is found from the TDB time of the first (exact to
//    1e-9 samples); an instant outside the second package's axis is reported as such
//    and not replaced by a value.
//
// P. Jumping between events uses the package's events of the body and observer height,
//    strictly after or strictly before the selected time; none is invented.
//
// Q. The comparison numbers are the package's metrics, with their units converted
//    (seconds to hours, fraction to per cent) and nothing else; a metric the package
//    does not have gives no line.

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mesh/LsnMesh.h"
#include "Planner/LsnPlanner.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnPlannerTest
{
	constexpr double DirectionToleranceDeg = 0.001;
	constexpr double SilhouetteToleranceDeg = 0.001;

	struct FWorldFixture
	{
		UWorld* World = nullptr;

		FWorldFixture()
		{
			World = UWorld::CreateWorld(EWorldType::Game, false);
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->BeginPlay();
		}

		~FWorldFixture()
		{
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}

		ALsnSiteScene* Spawn(const FVector& Location)
		{
			return World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform(Location));
		}
	};

	inline bool OnlyChannel(const FLightingChannels& Channels, int32 Slot)
	{
		return Channels.bChannel0 == (Slot == 0) && Channels.bChannel1 == (Slot == 1) && Channels.bChannel2 == (Slot == 2);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPlannerOffsetSceneTest, "LunarSiteNavigator.Acceptance.SecondSceneAwayFromOrigin", LsnTest::Flags)
bool FLsnPlannerOffsetSceneTest::RunTest(const FString& Parameters)
{
	using namespace LsnPlannerTest;
	FWorldFixture Fixture;
	const FVector Offset(2.0e9, 0.0, 0.0);
	ALsnSiteScene* Scene = Fixture.Spawn(Offset);
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error), Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		return false;
	}
	Scene->SetSceneSlot(1);
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();

	TestTrue(TEXT("the test offset is far from the origin"), Offset.Size() > 2.0 * P.MaxRangeM * FLsnSiteFrame::CmPerM);
	const FVector ExpectedEye = Offset + FVector(0.0, 0.0, P.ObserverHeightsM[H] * FLsnSiteFrame::CmPerM);
	TestTrue(TEXT("M: the eye is the scene's origin plus the observer height"), FVector::Dist(Scene->GetEyeUnreal(), ExpectedEye) < 1e-6);

	// Sun disc and light.
	const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
	double WorstDiscDeg = 0.0, WorstLightDeg = 0.0;
	for (int32 T = 0; Sun && T < P.Time.Count; T += 11)
	{
		Scene->SetTimeIndex(T);
		const FVector Expected = FLsnSiteFrame::AzElToUnrealDir(Sun->AzimuthDeg[T], Sun->ElevationDeg[T]);
		WorstDiscDeg = FMath::Max(WorstDiscDeg, LsnTest::AngleDeg(Scene->GetSunDisc()->GetComponentLocation() - Scene->GetEyeUnreal(), Expected));
		WorstLightDeg = FMath::Max(WorstLightDeg, LsnTest::AngleDeg(Scene->GetSunDirectionFromLight(), Expected));
	}
	TestTrue(TEXT("M: Sun disc where the package says"), WorstDiscDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("M: light direction as the package says"), WorstLightDeg <= DirectionToleranceDeg);

	// Silhouette, with the meshes at the components' world positions.
	FLsnPlacedMesh TerrainMesh, SphereMesh;
	TerrainMesh.Mesh = &Scene->GetTerrainMeshData();
	TerrainMesh.Origin = Scene->GetTerrainComponent()->GetComponentLocation();
	SphereMesh.Mesh = &Scene->GetMoonSphereMeshData();
	SphereMesh.Origin = Scene->GetMoonSphereComponent()->GetComponentLocation();
	TestTrue(TEXT("M: the terrain component sits at the scene's origin"), FVector::Dist(TerrainMesh.Origin, Offset) < 1e-6);
	const FLsnSilhouette Silhouette({ TerrainMesh, SphereMesh }, Scene->GetEyeUnreal());
	double WorstSilhouetteDeg = 0.0;
	int32 Missing = 0;
	for (int32 A = 0; A < P.AzimuthCount; ++A)
	{
		double Measured = 0.0;
		if (!Silhouette.MaxElevationDeg(P.AzimuthDegAt(A), Measured))
		{
			++Missing;
			continue;
		}
		WorstSilhouetteDeg = FMath::Max(WorstSilhouetteDeg, FMath::Abs(Measured - P.HorizonElevationAt(H, A)));
	}
	AddInfo(FString::Printf(TEXT("scene %.0f km from the world origin: Sun disc %.3g deg, light %.3g deg, silhouette %.3g deg from the package (tolerance %.3f deg)"),
		Offset.Size() / 1.0e5, WorstDiscDeg, WorstLightDeg, WorstSilhouetteDeg, SilhouetteToleranceDeg));
	TestEqual(TEXT("azimuths at which no geometry was found"), Missing, 0);
	TestTrue(TEXT("M: silhouette equals the package horizon"), WorstSilhouetteDeg <= SilhouetteToleranceDeg);

	// N. Lighting channels of the two slots.
	ALsnSiteScene* First = Fixture.Spawn(FVector::ZeroVector);
	if (TestTrue(TEXT("a second scene loads"), First->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		First->SetSceneSlot(0);
		for (int32 Slot = 0; Slot < 2; ++Slot)
		{
			const ALsnSiteScene* S = Slot == 0 ? First : Scene;
			TestTrue(FString::Printf(TEXT("N: slot %d Sun light on its channel only"), Slot), OnlyChannel(S->GetSunLight()->LightingChannels, Slot));
			TestTrue(FString::Printf(TEXT("N: slot %d fill light on its channel only"), Slot), OnlyChannel(S->GetFillLight()->LightingChannels, Slot));
			TestTrue(FString::Printf(TEXT("N: slot %d terrain on its channel only"), Slot), OnlyChannel(S->GetTerrainComponent()->LightingChannels, Slot));
			TestTrue(FString::Printf(TEXT("N: slot %d Moon sphere on its channel only"), Slot), OnlyChannel(S->GetMoonSphereComponent()->LightingChannels, Slot));
			TestTrue(FString::Printf(TEXT("N: slot %d Earth disc on its channel only"), Slot), OnlyChannel(S->GetEarthDisc()->LightingChannels, Slot));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPlannerLogicTest, "LunarSiteNavigator.Planner.LinkedTimeEventsAndMetrics", LsnTest::Flags)
bool FLsnPlannerLogicTest::RunTest(const FString& Parameters)
{
	// O. Linked time.
	FLsnSitePackage A, B;
	A.bHasTimeline = B.bHasTimeline = true;
	A.Time.StartEtS = 0.0;
	A.Time.StepS = 10.0;
	A.Time.Count = 11;  // 0 .. 100 s
	B.Time.StartEtS = 20.0;
	B.Time.StepS = 5.0;
	B.Time.Count = 9;   // 20 .. 60 s
	double PosB = -1.0;
	TestTrue(TEXT("O: 30 s is on both axes"), LsnPlanner::LinkedPosition(A, 3.0, B, PosB));
	TestEqual(TEXT("O: 30 s is position 2 of the second package"), PosB, 2.0, 1e-9);
	TestTrue(TEXT("O: 60 s, the last sample of the second package"), LsnPlanner::LinkedPosition(A, 6.0, B, PosB));
	TestEqual(TEXT("O: position 8"), PosB, 8.0, 1e-9);
	TestTrue(TEXT("O: between samples"), LsnPlanner::LinkedPosition(A, 2.25, B, PosB));
	TestEqual(TEXT("O: 22.5 s is position 0.5"), PosB, 0.5, 1e-9);
	TestFalse(TEXT("O: 0 s is before the second package"), LsnPlanner::LinkedPosition(A, 0.0, B, PosB));
	TestFalse(TEXT("O: 65 s is after the second package"), LsnPlanner::LinkedPosition(A, 6.5, B, PosB));
	B.bHasTimeline = false;
	TestFalse(TEXT("O: no timeline, no linked time"), LsnPlanner::LinkedPosition(A, 3.0, B, PosB));

	// P. Events.
	FLsnSitePackage P;
	P.bHasTimeline = true;
	auto AddEvent = [&P](const TCHAR* Body, const TCHAR* Type, int32 H, double EtS)
	{
		FLsnEvent E;
		E.Body = Body;
		E.Type = Type;
		E.HeightIndex = H;
		E.EtS = EtS;
		P.Events.Add(E);
	};
	AddEvent(TEXT("SUN"), TEXT("set"), 0, 100.0);
	AddEvent(TEXT("EARTH"), TEXT("rise"), 0, 150.0);
	AddEvent(TEXT("SUN"), TEXT("rise"), 0, 200.0);
	AddEvent(TEXT("SUN"), TEXT("set"), 1, 250.0);
	const FLsnEvent* E = LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 0, 120.0, +1);
	TestTrue(TEXT("P: next Sun event after 120 s is the rise at 200 s"), E && E->EtS == 200.0 && E->Type == TEXT("rise"));
	E = LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 0, 120.0, -1);
	TestTrue(TEXT("P: previous Sun event before 120 s is the set at 100 s"), E && E->EtS == 100.0);
	E = LsnPlanner::AdjacentEvent(P, FString(), 0, 120.0, +1);
	TestTrue(TEXT("P: next event of any body is the Earth rise at 150 s"), E && E->EtS == 150.0 && E->Body == TEXT("EARTH"));
	E = LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 0, 100.0, +1);
	TestTrue(TEXT("P: strictly after: from the event at 100 s the next is at 200 s"), E && E->EtS == 200.0);
	TestTrue(TEXT("P: no Sun event of height 0 after 200 s"), LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 0, 200.0, +1) == nullptr);
	TestTrue(TEXT("P: no event before the first"), LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 0, 100.0, -1) == nullptr);
	E = LsnPlanner::AdjacentEvent(P, TEXT("SUN"), 1, 0.0, +1);
	TestTrue(TEXT("P: events of another height are kept apart"), E && E->EtS == 250.0);

	// Q. Metrics.
	FLsnSitePackage M;
	auto AddMetric = [&M](const TCHAR* Id, int32 H, double Value)
	{
		FLsnMetric Metric;
		Metric.Id = Id;
		Metric.HeightIndex = H;
		Metric.bHasValue = true;
		Metric.Value = Value;
		M.Metrics.Add(Metric);
	};
	AddMetric(TEXT("sun_visible_fraction_of_time"), 2, 0.779);
	AddMetric(TEXT("sun_longest_outage_s"), 2, 188.1 * 3600.0);
	AddMetric(TEXT("earth_visible_fraction_of_time"), 2, 0.509);
	AddMetric(TEXT("sun_lost_to_terrain_s"), 2, 545.2 * 3600.0);
	AddMetric(TEXT("sun_gained_from_terrain_s"), 2, 2369.2 * 3600.0);
	AddMetric(TEXT("sun_visible_fraction_of_time"), 0, 0.5);
	TArray<FString> Lines;
	LsnPlanner::BuildMetricLines(M, 2, Lines);
	TestEqual(TEXT("Q: one line per metric group the package has"), Lines.Num(), 4);
	if (Lines.Num() == 4)
	{
		TestEqual(TEXT("Q: share of Sun"), Lines[0], FString(TEXT("Sun visible 77.9 % of the window")));
		TestEqual(TEXT("Q: longest outage"), Lines[1], FString(TEXT("longest time without Sun 188.1 h")));
		TestEqual(TEXT("Q: share of Earth"), Lines[2], FString(TEXT("Earth visible 50.9 % of the window")));
		// One plain sentence (wording changed on 2026-11-14 at the team lead's request; the numbers are the package metrics in whole hours).
		TestEqual(TEXT("Q: terrain"), Lines[3], FString(TEXT("Terrain here costs 545 h of Sun and gives 2369 h that a smooth sphere would not have")));
	}
	LsnPlanner::BuildMetricLines(M, 1, Lines);
	TestEqual(TEXT("Q: a height without metrics gives no lines"), Lines.Num(), 0);

	// Site list of a package root.
	TArray<FLsnIndexEntry> Sites;
	FString Error;
	TestTrue(FString::Printf(TEXT("the sites of the pinned sample are listed (%s)"), *Error), LsnPlanner::ListSites(LsnTest::FixtureRoot(), Sites, Error));
	TestTrue(TEXT("the sample has at least one site"), Sites.Num() >= 1);
	for (const FLsnIndexEntry& Site : Sites)
	{
		// Direction tables and, since 0.5, site-pairs packages are in the index too and must be left out.
		TestTrue(TEXT("only site packages are listed"), Site.Kind == TEXT("site") && !Site.SiteId.IsEmpty());
	}
	TestFalse(TEXT("a folder without index.json has no site list"), LsnPlanner::ListSites(LsnTest::FixtureRoot() / TEXT("site"), Sites, Error));

	// A time given by UTC: only on the package's axis and only without a leap second in the range.
	FLsnSitePackage Clock;
	Clock.bHasTimeline = true;
	Clock.Time.StartUtc = TEXT("2026-11-14T00:00:00.000Z");
	Clock.Time.StepS = 3600.0;
	Clock.Time.Count = 49;
	double ClockPosition = -1.0;
	TestTrue(TEXT("a UTC time on the axis is found"), LsnPlanner::PositionOfUtc(Clock, TEXT("2026-11-14T12:30:00Z"), ClockPosition));
	TestEqual(TEXT("12:30 is position 12.5"), ClockPosition, 12.5, 1e-9);
	TestTrue(TEXT("the last sample"), LsnPlanner::PositionOfUtc(Clock, TEXT("2026-11-16T00:00:00Z"), ClockPosition) && FMath::Abs(ClockPosition - 48.0) < 1e-9);
	TestFalse(TEXT("a time before the axis is refused"), LsnPlanner::PositionOfUtc(Clock, TEXT("2026-11-13T23:00:00Z"), ClockPosition));
	TestFalse(TEXT("a time after the axis is refused"), LsnPlanner::PositionOfUtc(Clock, TEXT("2026-11-16T00:30:00Z"), ClockPosition));
	Clock.Time.LeapSecondsInRange = 1;
	TestFalse(TEXT("with a leap second in the range a UTC time is not converted"), LsnPlanner::PositionOfUtc(Clock, TEXT("2026-11-14T12:30:00Z"), ClockPosition));

	// Panorama: azimuth 0 at the left edge, 360 wraps to it; elevation range clamps.
	FLsnPanorama Pano;
	Pano.Box = FBox2D(FVector2D(100.0, 50.0), FVector2D(460.0, 150.0));
	Pano.MinElevationDeg = -5.0;
	Pano.MaxElevationDeg = 5.0;
	TestTrue(TEXT("north, on the horizontal"), Pano.Point(0.0, 0.0).Equals(FVector2D(100.0, 100.0), 1e-9));
	TestTrue(TEXT("east, top of the range"), Pano.Point(90.0, 5.0).Equals(FVector2D(190.0, 50.0), 1e-9));
	TestTrue(TEXT("azimuth wraps"), Pano.Point(450.0, 0.0).Equals(Pano.Point(90.0, 0.0), 1e-9));
	TestTrue(TEXT("elevation clamps"), Pano.Point(180.0, -40.0).Equals(FVector2D(280.0, 150.0), 1e-9));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
