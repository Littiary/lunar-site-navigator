// Star field.
//
// Criteria and tolerances, written before the first run:
//
// S. The stars stand where the catalogue and the Moon's orientation put them.
//    1. Hand-made orientation: with east, north, up equal to the J2000 X, Y, Z axes, a star
//       at J2000 +X is drawn towards Unreal +Y (east), +Y towards +X (north), +Z towards +Z
//       (up), within 1e-9. Half way between that orientation and one turned by 90 degrees
//       about "up" (in which J2000 +X is drawn south), the mesh is turned by 45 degrees:
//       J2000 +X is drawn 45 degrees from east and 45 degrees from south, within 1e-6 deg.
//    2. Catalogue: Sirius is its brightest star (magnitude below -1.4) and stands at right
//       ascension 101.29 deg, declination -16.72 deg within 0.01 deg; every direction is a
//       unit vector; every star mesh square has its four corners within twice its stated
//       angular half size of its star's direction.
//    3. Real packages (where Scripts/export_sky.py has been run for the published package):
//       the direction of the Sun that SPICE gives in J2000, turned by the exported
//       orientation with the very function the star mesh uses, equals the Sun direction of
//       the package series at the same samples within 0.01 deg. (Expected difference: the
//       parallax between the Moon's centre and the site, below 0.001 deg.) The stars
//       therefore stand in the same frame, at the same instant, as the package's Sun.
//       If no orientation was exported the test reports a warning instead of passing silently.

#include "Tests/LsnTestSupport.h"
#include "Planner/LsnPlanner.h"
#include "Sky/LsnSky.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnSkyOrientationTest, "LunarSiteNavigator.Sky.StarsWhereTheyStand", LsnTest::Flags)
bool FLsnSkyOrientationTest::RunTest(const FString& Parameters)
{
	// 1. Hand-made orientation.
	FLsnSkyOrientation Sky;
	Sky.StartEtS = 0.0;
	Sky.StepS = 100.0;
	Sky.East = { FVector(1, 0, 0), FVector(0, 1, 0) };    // second entry: turned by 90 degrees about "up"
	Sky.North = { FVector(0, 1, 0), FVector(-1, 0, 0) };
	Sky.Up = { FVector(0, 0, 1), FVector(0, 0, 1) };
	FQuat Rotation;
	TestTrue(TEXT("rotation at the first time"), Sky.MeshRotationAt(0.0, Rotation));
	TestTrue(TEXT("J2000 +X is drawn east"), LsnSky::MeshDirection(FVector(1, 0, 0), Rotation).Equals(FVector(0, 1, 0), 1e-9));
	TestTrue(TEXT("J2000 +Y is drawn north"), LsnSky::MeshDirection(FVector(0, 1, 0), Rotation).Equals(FVector(1, 0, 0), 1e-9));
	TestTrue(TEXT("J2000 +Z is drawn up"), LsnSky::MeshDirection(FVector(0, 0, 1), Rotation).Equals(FVector(0, 0, 1), 1e-9));
	TestTrue(TEXT("rotation half way"), Sky.MeshRotationAt(50.0, Rotation));
	const FVector Half = LsnSky::MeshDirection(FVector(1, 0, 0), Rotation);
	// At the second time J2000 +X has no east part and a north part of -1: it is south (Unreal -X).
	// Half way it is 45 degrees from east and from south.
	TestEqual(TEXT("half way: 45 degrees from east"), FMath::RadiansToDegrees(FMath::Acos(FVector::DotProduct(Half, FVector(0, 1, 0)))), 45.0, 1e-6);
	TestEqual(TEXT("half way: 45 degrees from south"), FMath::RadiansToDegrees(FMath::Acos(FVector::DotProduct(Half, FVector(-1, 0, 0)))), 45.0, 1e-6);
	TestFalse(TEXT("no rotation outside the listed range"), Sky.MeshRotationAt(101.0, Rotation));

	// 2. Catalogue.
	FLsnStarCatalogue Catalogue;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the star list loads (%s)"), *Error), FLsnStarCatalogue::Load(Catalogue, Error)))
	{
		return false;
	}
	int32 Brightest = 0;
	double WorstLength = 0.0;
	for (int32 I = 0; I < Catalogue.Stars.Num(); ++I)
	{
		WorstLength = FMath::Max(WorstLength, FMath::Abs(Catalogue.Stars[I].DirectionJ2000.Size() - 1.0));
		if (Catalogue.Stars[I].VisualMagnitude < Catalogue.Stars[Brightest].VisualMagnitude)
		{
			Brightest = I;
		}
	}
	TestTrue(TEXT("unit directions"), WorstLength < 1e-6);
	const FLsnStar& Sirius = Catalogue.Stars[Brightest];
	TestTrue(FString::Printf(TEXT("the brightest star has magnitude %.2f"), Sirius.VisualMagnitude), Sirius.VisualMagnitude < -1.4f);
	const double Ra = FMath::Fmod(FMath::RadiansToDegrees(FMath::Atan2(Sirius.DirectionJ2000.Y, Sirius.DirectionJ2000.X)) + 360.0, 360.0);
	const double Dec = FMath::RadiansToDegrees(FMath::Asin(Sirius.DirectionJ2000.Z));
	TestEqual(TEXT("right ascension of Sirius"), Ra, 101.29, 0.01);
	TestEqual(TEXT("declination of Sirius"), Dec, -16.72, 0.01);
	AddInfo(FString::Printf(TEXT("%d stars; %s"), Catalogue.Stars.Num(), *Catalogue.Source));

	FLsnMeshData Mesh;
	LsnSky::BuildStarMesh(Catalogue, 1.0e11, Mesh);
	TestEqual(TEXT("four corners per star"), Mesh.Positions.Num(), 4 * Catalogue.Stars.Num());
	double WorstCorner = 0.0;
	for (int32 I = 0; I < Catalogue.Stars.Num() && 4 * I + 3 < Mesh.Positions.Num(); ++I)
	{
		const FVector Direction(Catalogue.Stars[I].DirectionJ2000.X, Catalogue.Stars[I].DirectionJ2000.Y, -Catalogue.Stars[I].DirectionJ2000.Z);
		for (int32 C = 0; C < 4; ++C)
		{
			const double Angle = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Mesh.Positions[4 * I + C].GetSafeNormal(), Direction), -1.0, 1.0)));
			WorstCorner = FMath::Max(WorstCorner, Angle / LsnSky::DotHalfSizeDeg(Catalogue.Stars[I].VisualMagnitude));
		}
	}
	TestTrue(FString::Printf(TEXT("corners within twice the half size (worst %.2f)"), WorstCorner), WorstCorner <= 2.0);

	// 3. Real packages.
	FString Root = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Sites;
	int32 Checked = 0;
	double WorstDeg = 0.0;
	if (!Root.IsEmpty() && LsnPlanner::ListSites(Root, Sites, Error))
	{
		for (const FLsnIndexEntry& Entry : Sites)
		{
			FLsnSitePackage P;
			FLsnSkyOrientation Real;
			if (!LsnPackageIO::LoadSitePackage(FPaths::Combine(Root, Entry.Path), P, Error) || !P.bHasTimeline
				|| !FLsnSkyOrientation::LoadForSite(P.SiteId, Real, Error) || !Real.Matches(P, Error))
			{
				continue;
			}
			const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
			for (const FLsnSkyCheck& Check : Real.Checks)
			{
				FQuat Turn;
				if (!Sun || !Sun->AzimuthDeg.IsValidIndex(Check.Sample) || !Real.MeshRotationAt(Check.EtS, Turn))
				{
					continue;
				}
				const FVector Drawn = LsnSky::MeshDirection(Check.SunJ2000, Turn);
				const FVector Expected = FLsnSiteFrame::AzElToUnrealDir(Sun->AzimuthDeg[Check.Sample], Sun->ElevationDeg[Check.Sample]);
				WorstDeg = FMath::Max(WorstDeg, FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Drawn, Expected), -1.0, 1.0))));
				++Checked;
			}
		}
	}
	if (Checked == 0)
	{
		AddWarning(TEXT("No sky orientation exported for the published packages (Scripts/export_sky.py): the real-data check was not made."));
	}
	else
	{
		AddInfo(FString::Printf(TEXT("%d Sun directions of SPICE against the package series: worst %.5f deg"), Checked, WorstDeg));
		TestTrue(FString::Printf(TEXT("sky orientation agrees with the package's Sun within 0.01 deg (worst %.5f)"), WorstDeg), WorstDeg <= 0.01);
	}
	return true;
}

#endif
