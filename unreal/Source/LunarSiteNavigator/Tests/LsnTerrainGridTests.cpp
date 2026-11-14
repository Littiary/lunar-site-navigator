// Real terrain around the site.
//
// Criteria and tolerances, written before the first run on real data:
//
// G. Terrain grid (Scripts/export_terrain.py; a viewer-side cache of the data stream's
//    heights, not part of the package contract).
//    - A grid is refused when it was sampled for another package, another sphere or
//      another azimuth layout than the package in the scene.
//    - A mesh vertex of ring r and azimuth a is the point at arc distance ring r along
//      azimuth a with the grid's height above the reference sphere, to 0.01 cm before
//      rounding to 32-bit.
//
// H. Real terrain against the package horizon (needs Content/LsnTerrain; warns if absent).
//    The package horizon is the highest elevation of the terrain along each azimuth out
//    to the search radius. Every exported terrain sample lies on that azimuth, so seen
//    from the eye none may stand above the package horizon of its azimuth by more than
//    0.001 deg. This compares the science core's horizon with heights read here through
//    the data stream's reader and placed with this project's frame code; a failure is a
//    finding to report, not a threshold to move.
//
//    Amendment after the first run on real packages (14 November 2026), stated here
//    instead of changing the tolerance: the first run found samples above the horizon,
//    all of them for the 0 m observer and nearer than 20 m (up to 4.82 deg at the
//    de Gerlache site). The horizon method card of the package states that its search
//    starts at parameter first_point_m = 20 m, so terrain nearer than that is by the
//    package's own statement not part of horizon.elevation_deg. Criterion H therefore
//    applies to samples from first_point_m outwards (all samples if a package does not
//    state it). The 0.001 deg tolerance is unchanged. What the samples nearer than
//    first_point_m do is measured and reported with every run, without a verdict; it
//    is a limit of the 0 m horizon that the core stream has been told about.
//
//    The crest vertex of each azimuth is the package's horizon point, so the silhouette
//    of the real-terrain mesh equals the package horizon within 0.001 deg at every
//    azimuth sample, as for the placeholder terrain.

#include "Tests/LsnTestSupport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mesh/LsnMesh.h"
#include "Planner/LsnPlanner.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnSiteScene.h"
#include "Terrain/LsnTerrainGrid.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnTerrainTest
{
	constexpr double VertexToleranceCm = 0.01;
	constexpr double AboveHorizonToleranceDeg = 0.001;
	constexpr double SilhouetteToleranceDeg = 0.001;

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
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnTerrainGridMeshTest, "LunarSiteNavigator.Terrain.GridMesh", LsnTest::Flags)
bool FLsnTerrainGridMeshTest::RunTest(const FString& Parameters)
{
	using namespace LsnTerrainTest;

	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const FLsnSiteFrame Frame = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);

	// A hand-made grid for the sample's layout: three rings, heights that differ per azimuth and ring.
	FLsnTerrainGrid Grid;
	Grid.SiteId = P.SiteId;
	Grid.PackageId = P.PackageId;
	Grid.ReferenceRadiusM = P.ReferenceRadiusM;
	Grid.AzimuthStartDeg = P.AzimuthStartDeg;
	Grid.AzimuthStepDeg = P.AzimuthStepDeg;
	Grid.AzimuthCount = P.AzimuthCount;
	Grid.RingDistanceM = { 10.0, 1000.0, 250000.0 };
	Grid.HeightsM.SetNumUninitialized(P.AzimuthCount * 3);
	for (int32 A = 0; A < P.AzimuthCount; ++A)
	{
		for (int32 R = 0; R < 3; ++R)
		{
			// Far below any horizon of the sample, so the package horizon points stay the crest.
			Grid.HeightsM[A * 3 + R] = static_cast<float>(P.SurfaceHeightM - 20000.0 - 3.0 * R - 0.01 * A);
		}
	}
	TestTrue(TEXT("G: a grid for this package is accepted"), Grid.Matches(P, Error));

	FLsnTerrainGrid Other = Grid;
	Other.PackageId = TEXT("site-0000000000000000");
	TestFalse(TEXT("G: a grid sampled for another package is refused"), Other.Matches(P, Error));
	TestTrue(TEXT("G: the refusal names the package"), Error.Contains(TEXT("package")));
	Other = Grid;
	Other.ReferenceRadiusM += 1.0;
	TestFalse(TEXT("G: a grid on another sphere is refused"), Other.Matches(P, Error));
	Other = Grid;
	Other.AzimuthStepDeg *= 2.0;
	Other.AzimuthCount /= 2;
	TestFalse(TEXT("G: a grid with another azimuth layout is refused"), Other.Matches(P, Error));

	FLsnMeshData Mesh;
	int32 Skipped = -1, Unknown = -1;
	LsnMesh::BuildGridTerrain(Frame, P, P.DefaultHeightIndex, Grid, 0.13f, Mesh, Skipped, Unknown);
	TestEqual(TEXT("horizon samples that could not be placed"), Skipped, 0);
	TestEqual(TEXT("grid samples without data"), Unknown, 0);
	TestEqual(TEXT("one centre vertex, and per azimuth one vertex per ring plus the horizon point"), Mesh.Positions.Num(), 1 + P.AzimuthCount * 4);

	// Every grid sample is a vertex at its place, and so is every horizon point.
	double WorstCm = 0.0;
	int32 Found = 0;
	const double EyeHeightM = P.ObserverHeightsM[P.DefaultHeightIndex];
	for (int32 A = 0; A < P.AzimuthCount; A += 37)
	{
		TArray<FVector> Expected;
		for (int32 R = 0; R < 3; ++R)
		{
			Expected.Add(Frame.SurfacePointUnreal(P.AzimuthDegAt(A), Grid.RingDistanceM[R], Grid.HeightsM[A * 3 + R]));
		}
		FVector HorizonPoint;
		TestTrue(TEXT("horizon point exists"), LsnMesh::HorizonPointUnreal(Frame, EyeHeightM, P.AzimuthDegAt(A), P.HorizonElevationAt(P.DefaultHeightIndex, A), P.HorizonDistanceAt(P.DefaultHeightIndex, A), HorizonPoint));
		Expected.Add(HorizonPoint);
		for (const FVector& Point : Expected)
		{
			double Nearest = TNumericLimits<double>::Max();
			for (int32 K = 0; K < 4; ++K)
			{
				Nearest = FMath::Min(Nearest, FVector::Dist(Mesh.Positions[1 + A * 4 + K], Point));
			}
			WorstCm = FMath::Max(WorstCm, Nearest);
			++Found;
		}
	}
	AddInfo(FString::Printf(TEXT("%d expected vertices, worst distance to the mesh vertex %.3g cm (tolerance %.2f cm)"), Found, WorstCm, VertexToleranceCm));
	TestTrue(TEXT("G: vertices lie at ring distance, azimuth and height of the grid"), WorstCm <= VertexToleranceCm);

	// Within one azimuth the vertices are ordered outwards, wherever the horizon point falls.
	bool bOrdered = true;
	for (int32 A = 0; A < P.AzimuthCount && bOrdered; ++A)
	{
		for (int32 K = 1; K < 4; ++K)
		{
			bOrdered &= Mesh.Positions[1 + A * 4 + K].Size2D() >= Mesh.Positions[1 + A * 4 + K - 1].Size2D();
		}
	}
	TestTrue(TEXT("vertices of an azimuth are ordered outwards"), bOrdered);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnTerrainRealTest, "LunarSiteNavigator.Real.TerrainAgainstHorizon", LsnTest::Flags)
bool FLsnTerrainRealTest::RunTest(const FString& Parameters)
{
	using namespace LsnTerrainTest;

	const FString PackageRoot = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Entries;
	FString Error;
	if (!LsnPackageIO::LoadIndex(PackageRoot, Entries, Error))
	{
		AddWarning(TEXT("NOT RUN: no published packages found (packages/ at the root of the repository)."));
		return true;
	}
	int32 SitesWithTerrain = 0;
	for (const FLsnIndexEntry& Entry : Entries)
	{
		if (Entry.Kind != TEXT("site"))
		{
			continue;
		}
		const FString Dir = FPaths::Combine(PackageRoot, Entry.Path);
		FLsnSitePackage P;
		if (!TestTrue(FString::Printf(TEXT("%s loads (%s)"), *Entry.SiteId, *Error), LsnPackageIO::LoadSitePackage(Dir, P, Error)))
		{
			continue;
		}
		FLsnTerrainGrid Grid;
		if (!FLsnTerrainGrid::LoadForSite(P.SiteId, Grid, Error))
		{
			AddWarning(FString::Printf(TEXT("NOT RUN for %s: no terrain grid (%s). Run Scripts/export_terrain.py."), *P.SiteId, *Error));
			continue;
		}
		if (!TestTrue(FString::Printf(TEXT("%s: the grid belongs to the imported package (%s)"), *P.SiteId, *Error), Grid.Matches(P, Error)))
		{
			continue;
		}
		++SitesWithTerrain;
		const FLsnSiteFrame Frame = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);
		const int32 NumRings = Grid.RingDistanceM.Num();

		// H: no terrain sample above the package horizon of its azimuth, for every observer height.
		const double SearchStartM = P.HorizonSearchStartM();
		double WorstExcessDeg = -TNumericLimits<double>::Max();
		double ClosestBelowDeg = TNumericLimits<double>::Max();
		int32 Above = 0, Compared = 0, WorstH = -1, WorstA = -1, WorstR = -1;
		// Samples nearer than the start of the package's horizon search: reported, not judged.
		TArray<int32> NearAbove;
		TArray<double> NearWorstExcessDeg;
		NearAbove.Init(0, P.NumHeights());
		NearWorstExcessDeg.Init(-TNumericLimits<double>::Max(), P.NumHeights());
		for (int32 H = 0; H < P.NumHeights(); ++H)
		{
			const FVector Eye(0.0, 0.0, P.ObserverHeightsM[H] * FLsnSiteFrame::CmPerM);
			for (int32 A = 0; A < P.AzimuthCount; ++A)
			{
				const double HorizonDeg = P.HorizonElevationAt(H, A);
				if (FMath::IsNaN(HorizonDeg))
				{
					continue;
				}
				double HighestDeg = -90.0;
				for (int32 R = 0; R < NumRings; ++R)
				{
					const float HeightM = Grid.HeightsM[A * NumRings + R];
					if (FMath::IsNaN(HeightM) || Grid.RingDistanceM[R] > P.MaxRangeM)
					{
						continue;
					}
					double Az = 0.0, El = 0.0;
					FLsnSiteFrame::UnrealDirToAzEl(Frame.SurfacePointUnreal(Grid.AzimuthDegAt(A), Grid.RingDistanceM[R], HeightM) - Eye, Az, El);
					const double Excess = El - HorizonDeg;
					if (Grid.RingDistanceM[R] < SearchStartM)
					{
						NearAbove[H] += Excess > AboveHorizonToleranceDeg ? 1 : 0;
						NearWorstExcessDeg[H] = FMath::Max(NearWorstExcessDeg[H], Excess);
						continue;
					}
					HighestDeg = FMath::Max(HighestDeg, El);
					++Compared;
					if (Excess > AboveHorizonToleranceDeg)
					{
						++Above;
					}
					if (Excess > WorstExcessDeg)
					{
						WorstExcessDeg = Excess;
						WorstH = H;
						WorstA = A;
						WorstR = R;
					}
				}
				ClosestBelowDeg = FMath::Min(ClosestBelowDeg, HorizonDeg - HighestDeg);
			}
		}
		TestEqual(FString::Printf(TEXT("%s: H: terrain samples standing above the package horizon"), *P.SiteId), Above, 0);

		// The scene with this terrain: the silhouette is still the package horizon.
		FSceneFixture Fixture;
		double WorstSilhouetteDeg = 0.0;
		if (TestTrue(FString::Printf(TEXT("%s: the scene loads the package (%s)"), *P.SiteId, *Error), Fixture.Scene->LoadPackageDirectory(Dir, Error)))
		{
			ALsnSiteScene& Scene = *Fixture.Scene;
			TestTrue(FString::Printf(TEXT("%s: the scene uses the real terrain"), *P.SiteId), Scene.HasRealTerrain());
			FLsnPlacedMesh TerrainMesh, SphereMesh;
			TerrainMesh.Mesh = &Scene.GetTerrainMeshData();
			TerrainMesh.Origin = Scene.GetTerrainComponent()->GetComponentLocation();
			SphereMesh.Mesh = &Scene.GetMoonSphereMeshData();
			SphereMesh.Origin = Scene.GetMoonSphereComponent()->GetComponentLocation();
			const FLsnSilhouette Silhouette({ TerrainMesh, SphereMesh }, Scene.GetEyeUnreal());
			int32 Missing = 0;
			for (int32 A = 0; A < P.AzimuthCount; ++A)
			{
				double Measured = 0.0;
				if (!Silhouette.MaxElevationDeg(P.AzimuthDegAt(A), Measured))
				{
					++Missing;
					continue;
				}
				WorstSilhouetteDeg = FMath::Max(WorstSilhouetteDeg, FMath::Abs(Measured - P.HorizonElevationAt(Scene.GetHeightIndex(), A)));
			}
			TestEqual(FString::Printf(TEXT("%s: azimuths at which no geometry was found"), *P.SiteId), Missing, 0);
			TestTrue(FString::Printf(TEXT("%s: silhouette of the real-terrain mesh equals the package horizon"), *P.SiteId), WorstSilhouetteDeg <= SilhouetteToleranceDeg);
		}

		FString NearReport;
		for (int32 H = 0; H < P.NumHeights(); ++H)
		{
			if (NearWorstExcessDeg[H] > -TNumericLimits<double>::Max())
			{
				NearReport += FString::Printf(TEXT(" %.0f m: %d above, highest %+.4f deg;"), P.ObserverHeightsM[H], NearAbove[H], NearWorstExcessDeg[H]);
			}
		}
		AddInfo(FString::Printf(TEXT("%s: terrain nearer than the start of the package's horizon search (%.1f m), per observer height, not judged:%s"),
			*P.SiteId, SearchStartM, NearReport.IsEmpty() ? TEXT(" no such samples") : *NearReport));
		AddInfo(FString::Printf(TEXT("%s: %d terrain samples x heights compared; highest excess over the package horizon %.6f deg (height index %d, azimuth index %d, ring %d at %.0f m; tolerance %.3f); the nearest any azimuth's samples come to its horizon from below: %.6f deg; mesh silhouette vs horizon worst %.3g deg (tolerance %.3f)"),
			*P.SiteId, Compared, WorstExcessDeg, WorstH, WorstA, WorstR, Grid.RingDistanceM.IsValidIndex(WorstR) ? Grid.RingDistanceM[WorstR] : 0.0, AboveHorizonToleranceDeg,
			ClosestBelowDeg, WorstSilhouetteDeg, SilhouetteToleranceDeg));
	}
	if (SitesWithTerrain == 0)
	{
		AddWarning(TEXT("NOT RUN: no real package has a terrain grid."));
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
