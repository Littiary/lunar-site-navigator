#include "CoreMinimal.h"
#include "Frame/LsnSiteFrame.h"
#include "Mesh/LsnMesh.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Package/LsnPackage.h"
#include "Tests/LsnTestSupport.h"

#if WITH_DEV_AUTOMATION_TESTS

// Tolerances, fixed before the first run:
//
//  ObstacleElevationToleranceDeg  0.05 deg. The horizon elevation recomputed from the
//      obstacle point (arc distance and obstacle height, placed through the site frame)
//      against horizon.elevation_deg. Unlike the scene mesh, which is built from the
//      elevation itself, this uses fields that are independent of the elevation, so it
//      checks the package against itself through this project's frame code. 0.05 deg is
//      less than a fifth of the angular radius of the Sun. The synthetic sample writes
//      its obstacle heights with small-angle formulas, expected to cost about 0.02 deg
//      at its farthest obstacles; a package computed from terrain should be far closer.
//  ObstacleAzimuthToleranceDeg    1e-4 deg. The obstacle point must lie in the azimuth
//      of its sample.
namespace LsnObstacleTest
{
	constexpr double ObstacleElevationToleranceDeg = 0.05;
	constexpr double ObstacleAzimuthToleranceDeg = 1e-4;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageObstacleTest, "LunarSiteNavigator.Package.ObstaclePointsReproduceHorizon", LsnTest::Flags)
bool FLsnPackageObstacleTest::RunTest(const FString& Parameters)
{
	using namespace LsnObstacleTest;

	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	if (!TestEqual(TEXT("the sample carries obstacle heights"), P.ObstacleHeightM.Num(), P.NumHeights() * P.AzimuthCount))
	{
		return false;
	}
	const FLsnSiteFrame Frame = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);

	double WorstElevationDeg = 0.0, WorstAzimuthDeg = 0.0;
	int32 WorstHeight = -1, WorstAzimuthIndex = -1, Compared = 0, Unknown = 0;
	for (int32 H = 0; H < P.NumHeights(); ++H)
	{
		const FVector Eye(0.0, 0.0, P.ObserverHeightsM[H] * FLsnSiteFrame::CmPerM);
		for (int32 A = 0; A < P.AzimuthCount; ++A)
		{
			const int32 Flat = H * P.AzimuthCount + A;
			const double Expected = P.HorizonElevationAt(H, A);
			const double DistanceM = P.HorizonDistanceAt(H, A);
			const double ObstacleHeightM = P.ObstacleHeightM[Flat];
			if (FMath::IsNaN(Expected) || FMath::IsNaN(DistanceM) || FMath::IsNaN(ObstacleHeightM))
			{
				++Unknown;
				continue;
			}
			const FVector Obstacle = Frame.SurfacePointUnreal(P.AzimuthDegAt(A), DistanceM, ObstacleHeightM);
			double Az = 0.0, El = 0.0;
			FLsnSiteFrame::UnrealDirToAzEl(Obstacle - Eye, Az, El);
			const double ElevationError = FMath::Abs(El - Expected);
			if (ElevationError > WorstElevationDeg)
			{
				WorstElevationDeg = ElevationError;
				WorstHeight = H;
				WorstAzimuthIndex = A;
			}
			WorstAzimuthDeg = FMath::Max(WorstAzimuthDeg, FMath::Abs(FMath::Fmod(Az - P.AzimuthDegAt(A) + 540.0, 360.0) - 180.0));
			++Compared;
		}
	}
	AddInfo(FString::Printf(TEXT("elevation of the obstacle points minus horizon.elevation_deg: worst %.5f deg at height index %d, azimuth index %d (tolerance %.3f); worst azimuth offset %.3g deg (tolerance %.0e); %d samples compared, %d unknown"),
		WorstElevationDeg, WorstHeight, WorstAzimuthIndex, ObstacleElevationToleranceDeg, WorstAzimuthDeg, ObstacleAzimuthToleranceDeg, Compared, Unknown));
	TestTrue(TEXT("samples were compared"), Compared > 0);
	TestTrue(TEXT("obstacle points reproduce the horizon elevation"), WorstElevationDeg <= ObstacleElevationToleranceDeg);
	TestTrue(TEXT("obstacle points lie in the azimuth of their sample"), WorstAzimuthDeg <= ObstacleAzimuthToleranceDeg);
	return true;
}

/**
 * Writes the silhouette of the terrain mesh, as the scene builds it, for every observer
 * height and azimuth sample. Scripts/compare_horizon.py reads the package with Python
 * alone and repeats the comparison, so the result does not rest on this C++ reader.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnAcceptanceHorizonExportTest, "LunarSiteNavigator.Acceptance.HorizonExportForPython", LsnTest::Flags)
bool FLsnAcceptanceHorizonExportTest::RunTest(const FString& Parameters)
{
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const FLsnSiteFrame Frame = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);

	TArray<FString> Csv;
	Csv.Add(TEXT("height_index,azimuth_deg,scene_elevation_deg"));
	int32 Missing = 0;
	for (int32 H = 0; H < P.NumHeights(); ++H)
	{
		FLsnMeshData Terrain;
		int32 Skipped = 0;
		LsnMesh::BuildHorizonTerrain(Frame, P, H, FLsnHorizonTerrainParams(), Terrain, Skipped);
		Terrain.RoundPositionsToFloat();
		TestEqual(TEXT("horizon samples that could not be placed"), Skipped, 0);

		FLsnPlacedMesh Placed;
		Placed.Mesh = &Terrain;
		const FLsnSilhouette Silhouette({ Placed }, FVector(0.0, 0.0, P.ObserverHeightsM[H] * FLsnSiteFrame::CmPerM));
		for (int32 A = 0; A < P.AzimuthCount; ++A)
		{
			double Measured = 0.0;
			if (!Silhouette.MaxElevationDeg(P.AzimuthDegAt(A), Measured))
			{
				++Missing;
				continue;
			}
			Csv.Add(FString::Printf(TEXT("%d,%.6f,%.9f"), H, P.AzimuthDegAt(A), Measured));
		}
	}
	TestEqual(TEXT("azimuths at which no geometry was found"), Missing, 0);

	const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Lsn"), TEXT("horizon_silhouette.csv")));
	TestTrue(TEXT("the silhouette file is written"), FFileHelper::SaveStringArrayToFile(Csv, *Path));
	AddInfo(FString::Printf(TEXT("%d rows written to %s"), Csv.Num() - 1, *Path));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
