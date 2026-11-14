#include "CoreMinimal.h"
#include "HAL/FileManager.h"
#include "LsnFrame.h"
#include "LsnPackage.h"
#include "LsnTerrain.h"
#include "LsnTolerances.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags LsnTestFlags = EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter;

	bool Near(FAutomationTestBase& Test, const TCHAR* What, const FVector& Actual, const FVector& Expected, double Tolerance)
	{
		const double Error = (Actual - Expected).GetAbsMax();
		if (Error > Tolerance)
		{
			Test.AddError(FString::Printf(TEXT("%s: got (%.12g, %.12g, %.12g), expected (%.12g, %.12g, %.12g), error %.3g > %.3g"),
				What, Actual.X, Actual.Y, Actual.Z, Expected.X, Expected.Y, Expected.Z, Error, Tolerance));
			return false;
		}
		return true;
	}

	double AngleDifferenceDeg(double A, double B)
	{
		return FMath::Abs(FMath::Fmod(A - B + 540.0, 360.0) - 180.0);
	}

	/** Loads the first site package and its direction table from the package root. A missing sample is a failure, not a skip. */
	bool LoadSample(FAutomationTestBase& Test, FLsnSitePackage& Site, FLsnDirectionTable* Table = nullptr)
	{
		const FString Root = LsnContract::FindPackageRoot();
		if (Root.IsEmpty())
		{
			Test.AddError(TEXT("No package root found. Run unreal/LunarSiteNavigator/Scripts/sync_contract_sample.ps1 or pass -LsnPackageRoot=<dir>."));
			return false;
		}
		FString Error;
		FLsnIndex Index;
		if (!Index.Load(Root, Error) || !Site.Load(Index.FindPackageDir(TEXT("site")), Error))
		{
			Test.AddError(Error);
			return false;
		}
		if (Table != nullptr && !Table->Load(Index.FindPackageDirById(Site.DirectionTableId), Error))
		{
			Test.AddError(Error);
			return false;
		}
		Test.AddInfo(FString::Printf(TEXT("Package %s from %s (synthetic: %s)"), *Site.Header.PackageId, *Root, Site.Header.bSynthetic ? TEXT("yes") : TEXT("no")));
		return true;
	}
}

// ---------------------------------------------------------------------------------------
// Frame mapping. Expected values are written out by hand, not computed with the code under test.
// ---------------------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFrameAxesTest, "Lsn.Frame.Axes", LsnTestFlags)
bool FLsnFrameAxesTest::RunTest(const FString&)
{
	using namespace LsnFrame;
	const double Tol = LsnTolerances::FrameUnitVector;
	const double H = 0.70710678118654752;  // sqrt(1/2)

	// Site frame: azimuth clockwise from north, elevation above the horizontal.
	Near(*this, TEXT("ENU north"), AzElToEnu(0.0, 0.0), FVector(0.0, 1.0, 0.0), Tol);
	Near(*this, TEXT("ENU east"), AzElToEnu(90.0, 0.0), FVector(1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("ENU south"), AzElToEnu(180.0, 0.0), FVector(0.0, -1.0, 0.0), Tol);
	Near(*this, TEXT("ENU west"), AzElToEnu(270.0, 0.0), FVector(-1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("ENU zenith"), AzElToEnu(123.0, 90.0), FVector(0.0, 0.0, 1.0), Tol);

	// Unreal world: +X east, +Y south, +Z up.
	Near(*this, TEXT("world north"), AzElToWorldDir(0.0, 0.0), FVector(0.0, -1.0, 0.0), Tol);
	Near(*this, TEXT("world east"), AzElToWorldDir(90.0, 0.0), FVector(1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("world south"), AzElToWorldDir(180.0, 0.0), FVector(0.0, 1.0, 0.0), Tol);
	Near(*this, TEXT("world west"), AzElToWorldDir(270.0, 0.0), FVector(-1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("world zenith"), AzElToWorldDir(0.0, 90.0), FVector(0.0, 0.0, 1.0), Tol);
	Near(*this, TEXT("world south-east, 45 up"), AzElToWorldDir(135.0, 45.0), FVector(0.5, 0.5, H), Tol);
	Near(*this, TEXT("world north-west, 45 down"), AzElToWorldDir(315.0, -45.0), FVector(-0.5, -0.5, -H), Tol);

	// The rotator a camera or a light is given must look along the same direction.
	// FRotator works in single-precision trigonometry tables in places, hence the looser bound.
	Near(*this, TEXT("rotator east"), AzElToRotator(90.0, 0.0).Vector(), FVector(1.0, 0.0, 0.0), 1e-6);
	Near(*this, TEXT("rotator north"), AzElToRotator(0.0, 0.0).Vector(), FVector(0.0, -1.0, 0.0), 1e-6);
	Near(*this, TEXT("rotator south-east, 45 up"), AzElToRotator(135.0, 45.0).Vector(), FVector(0.5, 0.5, H), 1e-6);

	// Turning right (positive yaw) from north must lead to east: azimuth and yaw grow the same way.
	TestTrue(TEXT("yaw grows with azimuth"), AzElToRotator(10.0, 0.0).Yaw > AzElToRotator(0.0, 0.0).Yaw);

	// The site frame is right-handed, the Unreal world is its mirror image.
	const FVector E = AzElToEnu(90.0, 0.0), N = AzElToEnu(0.0, 0.0), U = AzElToEnu(0.0, 90.0);
	TestTrue(TEXT("ENU right-handed"), FVector::DotProduct(FVector::CrossProduct(E, N), U) > 0.999999);
	TestTrue(TEXT("world mirrored"), FVector::DotProduct(FVector::CrossProduct(EnuToWorld(E), EnuToWorld(N)), EnuToWorld(U)) < -0.999999);

	// Round trip of azimuth and elevation.
	double Az = 0.0, El = 0.0;
	EnuToAzEl(WorldToEnu(AzElToWorldDir(217.25, -3.5)), Az, El);
	TestTrue(TEXT("azimuth round trip"), FMath::Abs(Az - 217.25) < 1e-10);
	TestTrue(TEXT("elevation round trip"), FMath::Abs(El + 3.5) < 1e-10);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFrameKnownPointTest, "Lsn.Frame.KnownPoint", LsnTestFlags)
bool FLsnFrameKnownPointTest::RunTest(const FString&)
{
	const double Tol = LsnTolerances::FrameUnitVector;

	// Site on the equator at longitude 0, 1000 km from the centre: up is +X of the body-fixed
	// frame, east is +Y, north is +Z.
	const FLsnSiteFrame Equator = FLsnSiteFrame::FromLatLon(0.0, 0.0, 1.0e6);
	Near(*this, TEXT("equator east"), Equator.East, FVector(0.0, 1.0, 0.0), Tol);
	Near(*this, TEXT("equator north"), Equator.North, FVector(0.0, 0.0, 1.0), Tol);
	Near(*this, TEXT("equator up"), Equator.Up, FVector(1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("equator position"), Equator.PositionKm, FVector(1000.0, 0.0, 0.0), 1e-9);

	// A point 1 km above, 2 km east and 3 km north of that site.
	const FVector Enu = Equator.BodyFixedKmToEnuM(FVector(1001.0, 2.0, 3.0));
	Near(*this, TEXT("point in site frame, m"), Enu, FVector(2000.0, 3000.0, 1000.0), 1e-8);
	Near(*this, TEXT("point in world, cm"), LsnFrame::EnuMToWorldCm(Enu), FVector(200000.0, -300000.0, 100000.0), LsnTolerances::FramePointCm);

	// The centre of the Moon lies one site radius straight below the world origin.
	Near(*this, TEXT("Moon centre in world, cm"), LsnFrame::EnuMToWorldCm(Equator.BodyFixedKmToEnuM(FVector::ZeroVector)), FVector(0.0, 0.0, -1.0e8), LsnTolerances::FramePointCm);

	// Site at longitude 90 east on the equator: up is +Y, east is -X.
	const FLsnSiteFrame East90 = FLsnSiteFrame::FromLatLon(0.0, 90.0, 1.0e6);
	Near(*this, TEXT("lon 90 east"), East90.East, FVector(-1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("lon 90 up"), East90.Up, FVector(0.0, 1.0, 0.0), Tol);

	// South pole, approached along longitude 0: up is -Z, north points back along +X.
	const FLsnSiteFrame SouthPole = FLsnSiteFrame::FromLatLon(-90.0, 0.0, 1.0e6);
	Near(*this, TEXT("south pole up"), SouthPole.Up, FVector(0.0, 0.0, -1.0), Tol);
	Near(*this, TEXT("south pole north"), SouthPole.North, FVector(1.0, 0.0, 0.0), Tol);
	Near(*this, TEXT("south pole east"), SouthPole.East, FVector(0.0, 1.0, 0.0), Tol);

	// A body straight above the equator site is at the zenith; one far along +Z of the
	// body-fixed frame is due north on the horizon.
	double Az = 0.0, El = 0.0;
	LsnFrame::EnuToAzEl(Equator.BodyFixedDirToEnu(FVector(1.0, 0.0, 0.0)), Az, El);
	TestTrue(TEXT("zenith elevation"), FMath::Abs(El - 90.0) < 1e-9);
	LsnFrame::EnuToAzEl(Equator.BodyFixedDirToEnu(FVector(0.0, 0.0, 1.0)), Az, El);
	TestTrue(TEXT("north azimuth"), FMath::Abs(Az) < 1e-9 && FMath::Abs(El) < 1e-9);
	LsnFrame::EnuToAzEl(Equator.BodyFixedDirToEnu(FVector(0.0, 1.0, 0.0)), Az, El);
	TestTrue(TEXT("east azimuth"), FMath::Abs(Az - 90.0) < 1e-9 && FMath::Abs(El) < 1e-9);
	return true;
}

// ---------------------------------------------------------------------------------------
// Package reader
// ---------------------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageReadTest, "Lsn.Package.Read", LsnTestFlags)
bool FLsnPackageReadTest::RunTest(const FString&)
{
	TestTrue(TEXT("0.1 supported"), LsnContract::IsSupportedVersion(TEXT("0.1")));
	TestTrue(TEXT("0.7 supported"), LsnContract::IsSupportedVersion(TEXT("0.7")));
	TestFalse(TEXT("1.0 refused"), LsnContract::IsSupportedVersion(TEXT("1.0")));
	TestFalse(TEXT("garbage refused"), LsnContract::IsSupportedVersion(TEXT("abc")));

	FLsnSitePackage Site;
	FLsnDirectionTable Table;
	if (!LoadSample(*this, Site, &Table))
	{
		return false;
	}
	const int32 H = Site.NumHeights(), A = Site.AzimuthCount;
	TestTrue(TEXT("heights present"), H > 0);
	TestEqual(TEXT("azimuth samples cover the circle"), A * Site.AzimuthStepDeg, 360.0, 1e-9);
	TestEqual(TEXT("elevation array size"), Site.HorizonElevationDeg.Num(), H * A);
	TestEqual(TEXT("distance array size"), Site.HorizonDistanceM.Num(), H * A);
	TestTrue(TEXT("radius = reference + height"), FMath::Abs(Site.RadiusM - Site.ReferenceRadiusM - Site.SurfaceHeightM) < 1e-6);
	for (int32 I = 1; I < H; ++I)
	{
		TestTrue(TEXT("heights strictly increasing"), Site.ObserverHeightsM[I] > Site.ObserverHeightsM[I - 1]);
	}
	if (Site.Header.bSynthetic)
	{
		TestFalse(TEXT("synthetic package carries a notice"), Site.Header.SyntheticNotice.IsEmpty());
	}

	// Interpolation: exact at samples, mean of the neighbours half-way, periodic at 360.
	const float* Row = Site.HorizonElevationDeg.GetData() + Site.DefaultHeightIndex * A;
	TestEqual(TEXT("at sample"), Site.InterpolatedHorizonElevationDeg(Site.DefaultHeightIndex, 7 * Site.AzimuthStepDeg), static_cast<double>(Row[7]), 1e-9);
	TestEqual(TEXT("half-way"), Site.InterpolatedHorizonElevationDeg(Site.DefaultHeightIndex, 7.5 * Site.AzimuthStepDeg), 0.5 * (static_cast<double>(Row[7]) + static_cast<double>(Row[8])), 1e-9);
	TestEqual(TEXT("wraps"), Site.InterpolatedHorizonElevationDeg(Site.DefaultHeightIndex, 360.0 - 0.5 * Site.AzimuthStepDeg), 0.5 * (static_cast<double>(Row[A - 1]) + static_cast<double>(Row[0])), 1e-9);
	TestEqual(TEXT("nearest wraps"), Site.NearestAzimuthIndex(359.99), 0);

	if (Site.bHasTimeline)
	{
		TestTrue(TEXT("time samples"), Site.Time.Count > 0);
		for (const FString& Body : Site.Bodies)
		{
			const FLsnBodySeries* Series = Site.Series.Find(Body);
			if (TestNotNull(TEXT("series of body"), Series))
			{
				TestEqual(TEXT("azimuth series size"), Series->AzimuthDeg.Num(), Site.Time.Count);
				TestEqual(TEXT("margin series size"), Series->MarginDeg.Num(), H * Site.Time.Count);
			}
		}
		TestEqual(TEXT("table frame equals site frame"), Table.FrameName, Site.FrameName);
		TestEqual(TEXT("table positions size"), Table.PositionsKm.Num(), Table.Time.Count * Table.Bodies.Num() * 3);
		for (int32 I = 1; I < Site.Events.Num(); ++I)
		{
			TestTrue(TEXT("events sorted"), Site.Events[I].EtS >= Site.Events[I - 1].EtS);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageSiteFrameTest, "Lsn.Package.SiteFrameAgainstLatLon", LsnTestFlags)
bool FLsnPackageSiteFrameTest::RunTest(const FString&)
{
	FLsnSitePackage Site;
	if (!LoadSample(*this, Site))
	{
		return false;
	}
	// site.enu and site.position_km as the core wrote them, against the same frame derived
	// here from the latitude and longitude alone.
	const FLsnSiteFrame Expected = FLsnSiteFrame::FromLatLon(Site.LatDeg, Site.LonDeg, Site.RadiusM);
	Near(*this, TEXT("east"), Site.Frame.East, Expected.East, LsnTolerances::SiteFrameAgainstLatLon);
	Near(*this, TEXT("north"), Site.Frame.North, Expected.North, LsnTolerances::SiteFrameAgainstLatLon);
	Near(*this, TEXT("up"), Site.Frame.Up, Expected.Up, LsnTolerances::SiteFrameAgainstLatLon);
	Near(*this, TEXT("position_km"), Site.Frame.PositionKm, Expected.PositionKm, LsnTolerances::SitePositionKm);
	return true;
}

// ---------------------------------------------------------------------------------------
// Scene acceptance
// ---------------------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnSceneBodyDirectionTest, "Lsn.Scene.BodyDirectionFromPackage", LsnTestFlags)
bool FLsnSceneBodyDirectionTest::RunTest(const FString&)
{
	FLsnSitePackage Site;
	FLsnDirectionTable Table;
	if (!LoadSample(*this, Site, &Table))
	{
		return false;
	}
	if (!Site.bHasTimeline)
	{
		AddError(TEXT("The package has no timeline; the Sun direction cannot be checked."));
		return false;
	}
	// Two routes to the same direction in the Unreal world:
	//  (a) what the scene uses: azimuth and elevation series of the site package;
	//  (b) the direction-table position through body-fixed frame -> site frame -> world (SPEC 6).
	// The scene never uses (b) for drawing; it is here to catch a frame or sign mistake.
	const int32 Offset = FMath::RoundToInt32((Site.Time.StartEtS - Table.Time.StartEtS) / Table.Time.StepS);
	const int32 Stride = FMath::RoundToInt32(Site.Time.StepS / Table.Time.StepS);
	if (!FMath::IsNearlyEqual(Table.Time.StartEtS + Offset * Table.Time.StepS, Site.Time.StartEtS, 1e-6) || Stride < 1
		|| !FMath::IsNearlyEqual(Stride * Table.Time.StepS, Site.Time.StepS, 1e-6))
	{
		AddError(TEXT("The time grids of the site package and the direction table do not share samples; this test needs them to."));
		return false;
	}
	for (const FString& Body : Site.Bodies)
	{
		const int32 BodyIndex = Table.Bodies.IndexOfByKey(Body);
		if (!TestTrue(TEXT("body in table"), BodyIndex != INDEX_NONE))
		{
			continue;
		}
		double WorstDeg = 0.0;
		int32 WorstIndex = 0;
		for (int32 I = 0; I < Site.Time.Count; ++I)
		{
			FLsnBodySky Sky;
			if (!Site.GetBodySky(Body, I, Site.DefaultHeightIndex, Sky))
			{
				AddError(TEXT("GetBodySky failed"));
				return false;
			}
			const FVector FromTable = LsnFrame::EnuToWorld(Site.Frame.BodyFixedKmToEnuM(Table.PositionKm(Offset + I * Stride, BodyIndex))).GetSafeNormal();
			const double AngleDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(FromTable, Sky.WorldDir), -1.0, 1.0)));
			if (AngleDeg > WorstDeg)
			{
				WorstDeg = AngleDeg;
				WorstIndex = I;
			}
		}
		AddInfo(FString::Printf(TEXT("%s: largest angle between series direction and table direction %.3g deg at sample %d (tolerance %.3g deg, %d samples)"),
			*Body, WorstDeg, WorstIndex, LsnTolerances::BodyDirectionDeg, Site.Time.Count));
		TestTrue(*FString::Printf(TEXT("%s direction within tolerance"), *Body), WorstDeg <= LsnTolerances::BodyDirectionDeg);
	}

	// The light must shine along the opposite of the Sun direction at the same sample.
	FLsnBodySky Sun;
	if (Site.GetBodySky(TEXT("SUN"), 0, Site.DefaultHeightIndex, Sun))
	{
		const FVector LightForward = LsnFrame::AzElToRotator(Sun.AzimuthDeg + 180.0, -Sun.ElevationDeg).Vector();
		Near(*this, TEXT("light forward = -sun direction"), LightForward, -Sun.WorldDir, 1e-6);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnSceneHorizonTest, "Lsn.Scene.HorizonSilhouette", LsnTestFlags)
bool FLsnSceneHorizonTest::RunTest(const FString&)
{
	FLsnSitePackage Site;
	if (!LoadSample(*this, Site))
	{
		return false;
	}
	if (!Site.bHasObstaclePoints)
	{
		AddError(TEXT("The package has no obstacle points; the stand-in patch cannot be built."));
		return false;
	}
	const int32 A = Site.AzimuthCount;
	TArray<FString> Csv;
	Csv.Add(TEXT("height_index,azimuth_deg,scene_elevation_deg"));
	double WorstSample = 0.0, WorstMid = 0.0, WorstAz = 0.0;

	for (int32 H = 0; H < Site.NumHeights(); ++H)
	{
		// The mesh exactly as the scene builds it for this observer height, in the precision
		// in which the engine stores it.
		FLsnMeshData Mesh;
		if (!LsnTerrain::BuildHorizonPatch(Site, H, Mesh))
		{
			AddError(TEXT("BuildHorizonPatch failed"));
			return false;
		}
		Mesh.QuantizeToFloat();
		const FVector Observer = Site.ObserverWorldCm(H);

		for (int32 I = 0; I < A; ++I)
		{
			const double Az = I * Site.AzimuthStepDeg;

			// The obstacle point must lie in the azimuth of its sample.
			double ObstacleAz = 0.0, ObstacleEl = 0.0;
			LsnFrame::EnuToAzEl(LsnTerrain::ObstacleEnuM(Site, H, I), ObstacleAz, ObstacleEl);
			WorstAz = FMath::Max(WorstAz, AngleDifferenceDeg(ObstacleAz, Az));

			const double AtSample = LsnTerrain::SilhouetteElevationDeg(Mesh, Observer, Az);
			WorstSample = FMath::Max(WorstSample, FMath::Abs(AtSample - Site.HorizonElevationDeg[H * A + I]));
			Csv.Add(FString::Printf(TEXT("%d,%.6f,%.9f"), H, Az, AtSample));

			const double MidAz = Az + 0.5 * Site.AzimuthStepDeg;
			const double AtMid = LsnTerrain::SilhouetteElevationDeg(Mesh, Observer, MidAz);
			WorstMid = FMath::Max(WorstMid, FMath::Abs(AtMid - Site.InterpolatedHorizonElevationDeg(H, MidAz)));
			Csv.Add(FString::Printf(TEXT("%d,%.6f,%.9f"), H, MidAz, AtMid));
		}
	}

	AddInfo(FString::Printf(TEXT("Horizon silhouette, %d heights x %d azimuths: largest difference at samples %.5f deg (tolerance %.5f), between samples %.5f deg (tolerance %.5f); largest obstacle azimuth offset %.3g deg (tolerance %.3g)"),
		Site.NumHeights(), A, WorstSample, LsnTolerances::HorizonSilhouetteDeg, WorstMid, LsnTolerances::HorizonSilhouetteMidSampleDeg, WorstAz, LsnTolerances::ObstacleAzimuthDeg));
	TestTrue(TEXT("silhouette at azimuth samples within tolerance"), WorstSample <= LsnTolerances::HorizonSilhouetteDeg);
	TestTrue(TEXT("silhouette between azimuth samples within tolerance"), WorstMid <= LsnTolerances::HorizonSilhouetteMidSampleDeg);
	TestTrue(TEXT("obstacle points lie in their azimuth"), WorstAz <= LsnTolerances::ObstacleAzimuthDeg);

	// Written for Scripts/compare_horizon.py, which reads the package with Python and
	// repeats the comparison independently of this reader.
	const FString CsvPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Lsn"), FString::Printf(TEXT("horizon_silhouette_%s.csv"), *Site.Header.PackageId));
	FFileHelper::SaveStringArrayToFile(Csv, *CsvPath);
	AddInfo(FString::Printf(TEXT("Silhouette written to %s"), *FPaths::ConvertRelativePathToFull(CsvPath)));
	return true;
}

#endif  // WITH_DEV_AUTOMATION_TESTS
