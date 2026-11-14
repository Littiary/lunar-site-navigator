// Orientation of the Earth (SPEC 6.1, since contract 0.8).
//
// Criteria and tolerances, written before the first run:
//
// Y. The Earth's axes follow from the three angles of the table as the contract says.
//    1. Hand-made: with the Earth in direction +X of the table frame, sub-lunar latitude 0,
//       longitude 0, pole angle 0 and no flattening, the north pole is +Z, the point of
//       latitude 0 and longitude 0 faces the Moon (x axis = -X), and the y axis is -Y,
//       within 1e-12.
//    2. Hand-made, general values (Earth in an oblique direction, latitude 20 deg, longitude
//       -75 deg, pole angle 15 deg, flattening 1/298.257): the three axes are unit vectors at
//       right angles (1e-12); the centre of the disc, seen from the Earth's centre in
//       direction -g, has longitude -75 deg and the geocentric latitude
//       atan(tan(20 deg) (1 - f)^2), within 1e-9 deg; the pole lies 15 deg from the projected
//       +Z of the frame towards east = Z x g, within 1e-9 deg.
//    3. Between two records the longitude goes the short way round: from 179 to -179 deg the
//       half-way value is 180 deg (or -180), not 0, within 1e-9 deg.
//    4. Published table (if it carries earth_view): at 60 records spread over the table the
//       same two identities hold within 1e-4 deg (the angles are stored as 32-bit numbers),
//       and the records are complete (no NaN). If the published table has no earth_view the
//       test says so and checks nothing there.

#include "Tests/LsnTestSupport.h"
#include "Planner/LsnPlanner.h"
#include "Sky/LsnEarthView.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnEarthTest
{
	/** Latitude and longitude, degrees, of a direction given from the Earth's centre, in the Earth's axes. */
	inline void LatLonOf(const FLsnEarthAxes& Axes, const FVector& FromCentre, double& OutLatDeg, double& OutLonDeg)
	{
		OutLatDeg = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(FVector::DotProduct(FromCentre, Axes.Pole), -1.0, 1.0)));
		OutLonDeg = FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(FromCentre, Axes.Y), FVector::DotProduct(FromCentre, Axes.X)));
	}

	inline double GeocentricDeg(double LatDeg, double Flattening)
	{
		return FMath::RadiansToDegrees(FMath::Atan(FMath::Tan(FMath::DegreesToRadians(LatDeg)) * FMath::Square(1.0 - Flattening)));
	}

	/** Position angle of the pole from the projected +Z of the frame towards east = Z x g, degrees. */
	inline double PoleAngleDeg(const FLsnEarthAxes& Axes, const FVector& G)
	{
		const FVector East = FVector::CrossProduct(FVector(0, 0, 1), G).GetSafeNormal();
		const FVector North = FVector::CrossProduct(G, East);
		return FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(Axes.Pole, East), FVector::DotProduct(Axes.Pole, North)));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnEarthAxesTest, "LunarSiteNavigator.Sky.EarthTurnedAsTheTableSays", LsnTest::Flags)
bool FLsnEarthAxesTest::RunTest(const FString& Parameters)
{
	using namespace LsnEarthTest;
	// 1.
	FLsnEarthAxes Axes = LsnEarth::Axes(FVector(1, 0, 0), 0.0, 0.0, 0.0, 0.0);
	TestTrue(TEXT("Y1: the pole is +Z"), Axes.Pole.Equals(FVector(0, 0, 1), 1e-12));
	TestTrue(TEXT("Y1: latitude 0, longitude 0 faces the Moon"), Axes.X.Equals(FVector(-1, 0, 0), 1e-12));
	TestTrue(TEXT("Y1: the y axis is -Y"), Axes.Y.Equals(FVector(0, -1, 0), 1e-12));

	// 2.
	const FVector G = FVector(0.6, -0.5, 0.2).GetSafeNormal();
	const double F = 1.0 / 298.257;
	Axes = LsnEarth::Axes(G, 20.0, -75.0, 15.0, F);
	TestEqual(TEXT("Y2: unit pole"), Axes.Pole.Size(), 1.0, 1e-12);
	TestEqual(TEXT("Y2: unit x"), Axes.X.Size(), 1.0, 1e-12);
	TestEqual(TEXT("Y2: unit y"), Axes.Y.Size(), 1.0, 1e-12);
	TestEqual(TEXT("Y2: pole at right angles to x"), FVector::DotProduct(Axes.Pole, Axes.X), 0.0, 1e-12);
	TestEqual(TEXT("Y2: pole at right angles to y"), FVector::DotProduct(Axes.Pole, Axes.Y), 0.0, 1e-12);
	TestEqual(TEXT("Y2: x at right angles to y"), FVector::DotProduct(Axes.X, Axes.Y), 0.0, 1e-12);
	double Lat = 0.0, Lon = 0.0;
	LatLonOf(Axes, -G, Lat, Lon);
	TestEqual(TEXT("Y2: longitude of the centre of the disc"), Lon, -75.0, 1e-9);
	TestEqual(TEXT("Y2: geocentric latitude of the centre of the disc"), Lat, GeocentricDeg(20.0, F), 1e-9);
	TestEqual(TEXT("Y2: position angle of the pole"), PoleAngleDeg(Axes, G), 15.0, 1e-9);

	// 3.
	TestEqual(TEXT("Y3: the longitude goes the short way round"), FMath::Abs(LsnEarth::LerpLongitudeDeg(179.0, -179.0, 0.5)), 180.0, 1e-9);
	TestEqual(TEXT("Y3: an ordinary step"), LsnEarth::LerpLongitudeDeg(10.0, -4.5, 0.5), 2.75, 1e-9);

	// 4.
	const FString Root = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Entries;
	FString Error;
	FLsnDirectionTable Table;
	bool bLoaded = false;
	if (!Root.IsEmpty() && LsnPackageIO::LoadIndex(Root, Entries, Error))
	{
		for (const FLsnIndexEntry& Entry : Entries)
		{
			if (Entry.Kind == TEXT("direction_table"))
			{
				bLoaded = LsnPackageIO::LoadDirectionTable(FPaths::Combine(Root, Entry.Path), Table, Error);
				break;
			}
		}
	}
	if (!bLoaded || !Table.bHasEarthView)
	{
		AddInfo(FString::Printf(TEXT("The published direction table carries no earth_view (%s): nothing checked on real data."), bLoaded ? *Table.PackageId : *Error));
		return true;
	}
	double WorstLonDeg = 0.0, WorstLatDeg = 0.0, WorstAngleDeg = 0.0;
	int32 Checked = 0;
	for (int32 K = 0; K < 60; ++K)
	{
		const int32 Record = K * (Table.Time.Count - 1) / 59;
		FVector EarthKm;
		if (!TestTrue(TEXT("Y4: the Earth is in the table"), Table.PositionKm(TEXT("EARTH"), Record, EarthKm)))
		{
			break;
		}
		const float SubLat = Table.EarthSubLunarLatDeg[Record], SubLon = Table.EarthSubLunarLonDeg[Record], Angle = Table.EarthNorthPoleAngleDeg[Record];
		if (!TestFalse(TEXT("Y4: complete record"), FMath::IsNaN(SubLat) || FMath::IsNaN(SubLon) || FMath::IsNaN(Angle)))
		{
			continue;
		}
		const FVector Dir = EarthKm.GetSafeNormal();
		const FLsnEarthAxes Real = LsnEarth::Axes(Dir, SubLat, SubLon, Angle, Table.EarthFlattening);
		LatLonOf(Real, -Dir, Lat, Lon);
		WorstLonDeg = FMath::Max(WorstLonDeg, FMath::Abs(FMath::Fmod(Lon - SubLon + 540.0, 360.0) - 180.0));
		WorstLatDeg = FMath::Max(WorstLatDeg, FMath::Abs(Lat - GeocentricDeg(SubLat, Table.EarthFlattening)));
		WorstAngleDeg = FMath::Max(WorstAngleDeg, FMath::Abs(FMath::Fmod(PoleAngleDeg(Real, Dir) - Angle + 540.0, 360.0) - 180.0));
		++Checked;
	}
	AddInfo(FString::Printf(TEXT("%s: %d records; worst longitude %.2g deg, latitude %.2g deg, pole angle %.2g deg; flattening %.6f"), *Table.PackageId, Checked, WorstLonDeg, WorstLatDeg, WorstAngleDeg, Table.EarthFlattening));
	TestTrue(TEXT("Y4: longitude of the centre of the disc as the table says"), WorstLonDeg <= 1e-4);
	TestTrue(TEXT("Y4: latitude of the centre of the disc as the table says"), WorstLatDeg <= 1e-4);
	TestTrue(TEXT("Y4: pole angle as the table says"), WorstAngleDeg <= 1e-4);
	return true;
}

#endif
