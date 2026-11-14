// Origin and frame tests. Every expected value below is worked out by hand
// from the frame definitions in unreal/FRAMES.md, not produced by the code
// under test. The test radius is a round number chosen for the test; it is
// not a physical constant.

#include "Frame/LsnSiteFrame.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnFrameTest
{
	constexpr double TestRadiusM = 1000000.0;
	constexpr double DirTol = 1e-12;
	/** Position tolerance in centimetres; double precision at 1e8 cm resolves about 1e-8 cm. */
	constexpr double PosTolCm = 1e-5;
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter;

	inline bool Near(const FVector& A, const FVector& B, double Tol)
	{
		return FMath::Abs(A.X - B.X) <= Tol && FMath::Abs(A.Y - B.Y) <= Tol && FMath::Abs(A.Z - B.Z) <= Tol;
	}
}

#define LSN_EXPECT_VEC(What, Actual, Expected, Tol) \
	if (!LsnFrameTest::Near((Actual), (Expected), (Tol))) \
	{ \
		AddError(FString::Printf(TEXT("%s: got (%.15g, %.15g, %.15g), expected (%.15g, %.15g, %.15g)"), TEXT(What), \
			(Actual).X, (Actual).Y, (Actual).Z, (Expected).X, (Expected).Y, (Expected).Z)); \
	}

// ---------------------------------------------------------------------------
// Local frame: azimuth and elevation land on the right Unreal axes.
// ---------------------------------------------------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFrameAzElTest, "LunarSiteNavigator.Frame.AzElToUnreal", LsnFrameTest::Flags)
bool FLsnFrameAzElTest::RunTest(const FString& Parameters)
{
	using namespace LsnFrameTest;

	// North on the horizon is Unreal +X, east is +Y, the zenith is +Z.
	LSN_EXPECT_VEC("north", FLsnSiteFrame::AzElToUnrealDir(0.0, 0.0), FVector(1, 0, 0), DirTol);
	LSN_EXPECT_VEC("east", FLsnSiteFrame::AzElToUnrealDir(90.0, 0.0), FVector(0, 1, 0), DirTol);
	LSN_EXPECT_VEC("south", FLsnSiteFrame::AzElToUnrealDir(180.0, 0.0), FVector(-1, 0, 0), DirTol);
	LSN_EXPECT_VEC("west", FLsnSiteFrame::AzElToUnrealDir(270.0, 0.0), FVector(0, -1, 0), DirTol);
	LSN_EXPECT_VEC("zenith", FLsnSiteFrame::AzElToUnrealDir(123.0, 90.0), FVector(0, 0, 1), DirTol);

	// Azimuth 90, elevation 30: cos 30 towards east, sin 30 up.
	LSN_EXPECT_VEC("east 30 up", FLsnSiteFrame::AzElToUnrealDir(90.0, 30.0), FVector(0.0, 0.8660254037844387, 0.5), DirTol);
	// Azimuth 225 (south-west), elevation -45.
	LSN_EXPECT_VEC("south-west 45 down", FLsnSiteFrame::AzElToUnrealDir(225.0, -45.0), FVector(-0.5, -0.5, -0.7071067811865476), DirTol);

	// The engine's own yaw and pitch agree with azimuth and elevation:
	// a rotator with Yaw = azimuth and Pitch = elevation looks along the same direction.
	for (double Az : { 0.0, 37.0, 90.0, 181.5, 300.0 })
	{
		for (double El : { -20.0, 0.0, 1.5, 60.0 })
		{
			const FVector FromRotator = FRotator(El, Az, 0.0).Vector();
			if (!Near(FLsnSiteFrame::AzElToUnrealDir(Az, El), FromRotator, 1e-9))
			{
				AddError(FString::Printf(TEXT("FRotator(pitch %.1f, yaw %.1f) disagrees with azimuth/elevation"), El, Az));
			}
		}
	}

	// "Sun in the east": a camera that looks north has an azimuth-90 Sun on its right.
	const FRotator LookNorth(0.0, 0.0, 0.0);
	const FVector CameraRight = FRotationMatrix(LookNorth).GetUnitAxis(EAxis::Y);
	const FVector CameraForward = FRotationMatrix(LookNorth).GetUnitAxis(EAxis::X);
	const FVector SunEast = FLsnSiteFrame::AzElToUnrealDir(90.0, 5.0);
	TestTrue(TEXT("camera looking north looks along +X"), Near(CameraForward, FVector(1, 0, 0), 1e-9));
	TestTrue(TEXT("Sun at azimuth 90 is on the right of a camera looking north"), FVector::DotProduct(SunEast, CameraRight) > 0.99);

	// Inverse.
	for (double Az : { 0.0, 0.25, 89.75, 90.0, 179.0, 270.0, 359.75 })
	{
		for (double El : { -89.0, -3.0, 0.0, 0.01, 45.0, 89.0 })
		{
			double AzBack = 0.0, ElBack = 0.0;
			FLsnSiteFrame::UnrealDirToAzEl(FLsnSiteFrame::AzElToUnrealDir(Az, El) * 12345.0, AzBack, ElBack);
			if (FMath::Abs(AzBack - Az) > 1e-9 || FMath::Abs(ElBack - El) > 1e-9)
			{
				AddError(FString::Printf(TEXT("az/el round trip: in (%.6f, %.6f), out (%.12f, %.12f)"), Az, El, AzBack, ElBack));
			}
		}
	}
	double AzOut = -1.0, ElOut = 0.0;
	FLsnSiteFrame::UnrealDirToAzEl(FVector(0, -1, 0), AzOut, ElOut);
	TestTrue(TEXT("west is azimuth 270, not -90"), FMath::Abs(AzOut - 270.0) < 1e-9 && FMath::Abs(ElOut) < 1e-9);

	// ENU metres -> Unreal centimetres: (east 1, north 2, up 3) m.
	LSN_EXPECT_VEC("enu to unreal", FLsnSiteFrame::EnuMToUnreal(FVector(1, 2, 3)), FVector(200, 100, 300), 1e-12);
	LSN_EXPECT_VEC("unreal to enu", FLsnSiteFrame::UnrealToEnuM(FVector(200, 100, 300)), FVector(1, 2, 3), 1e-12);
	return true;
}

// ---------------------------------------------------------------------------
// Body frame: known directions at hand-checkable sites.
// ---------------------------------------------------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFrameBodyDirTest, "LunarSiteNavigator.Frame.BodyDirections", LsnFrameTest::Flags)
bool FLsnFrameBodyDirTest::RunTest(const FString& Parameters)
{
	using namespace LsnFrameTest;
	const double S = 0.7071067811865476;

	// Site A: latitude 0, longitude 0. Up is body +X, east is body +Y, north is body +Z.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(0.0, 0.0, TestRadiusM, 0.0);
		LSN_EXPECT_VEC("A: body +X is up", F.BodyDirToUnreal(FVector(1, 0, 0)), FVector(0, 0, 1), DirTol);
		LSN_EXPECT_VEC("A: body +Y is east", F.BodyDirToUnreal(FVector(0, 1, 0)), FVector(0, 1, 0), DirTol);
		LSN_EXPECT_VEC("A: body +Z is north", F.BodyDirToUnreal(FVector(0, 0, 1)), FVector(1, 0, 0), DirTol);
	}

	// Site B: latitude 0, longitude 90 E. Up is body +Y; east is body -X
	// (east longitude increases towards -X there); north is body +Z.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(0.0, 90.0, TestRadiusM, 0.0);
		LSN_EXPECT_VEC("B: body +Y is up", F.BodyDirToUnreal(FVector(0, 1, 0)), FVector(0, 0, 1), DirTol);
		LSN_EXPECT_VEC("B: body -X is east", F.BodyDirToUnreal(FVector(-1, 0, 0)), FVector(0, 1, 0), DirTol);
		LSN_EXPECT_VEC("B: body +Z is north", F.BodyDirToUnreal(FVector(0, 0, 1)), FVector(1, 0, 0), DirTol);

		// East longitude is positive: a surface point at longitude 100 E lies east of the site.
		const FVector ToEast = FLsnSiteFrame::LatLonToBodyDir(0.0, 100.0) - FLsnSiteFrame::LatLonToBodyDir(0.0, 90.0);
		TestTrue(TEXT("B: longitude 100 E is east (+Y) of longitude 90 E"), F.BodyDirToUnreal(ToEast).Y > 0.0);
		// And a point at latitude +10 lies north of the site.
		const FVector ToNorth = FLsnSiteFrame::LatLonToBodyDir(10.0, 90.0) - FLsnSiteFrame::LatLonToBodyDir(0.0, 90.0);
		TestTrue(TEXT("B: latitude +10 is north (+X) of latitude 0"), F.BodyDirToUnreal(ToNorth).X > 0.0);
	}

	// Site C: latitude -45, longitude 90 E. The Moon's north pole direction
	// (body +Z) is seen due north, 45 degrees below the horizontal.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-45.0, 90.0, TestRadiusM, 0.0);
		LSN_EXPECT_VEC("C: north pole direction", F.BodyDirToUnreal(FVector(0, 0, 1)), FVector(S, 0, -S), DirTol);
		LSN_EXPECT_VEC("C: body -X is east", F.BodyDirToUnreal(FVector(-1, 0, 0)), FVector(0, 1, 0), DirTol);
		LSN_EXPECT_VEC("C: up", F.BodyDirToUnreal(FVector(0, S, -S)), FVector(0, 0, 1), DirTol);
		double Az = 0.0, El = 0.0;
		FLsnSiteFrame::UnrealDirToAzEl(F.BodyDirToUnreal(FVector(0, 0, 1)), Az, El);
		TestTrue(TEXT("C: pole direction is azimuth 0, elevation -45"), FMath::Abs(Az) < 1e-9 && FMath::Abs(El + 45.0) < 1e-9);
	}

	// Site D: the south pole itself, longitude given as 0. Up is body -Z.
	// North is the direction of the longitude-0 meridian (body +X), east is body +Y.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-90.0, 0.0, TestRadiusM, 0.0);
		LSN_EXPECT_VEC("D: body -Z is up", F.BodyDirToUnreal(FVector(0, 0, -1)), FVector(0, 0, 1), DirTol);
		LSN_EXPECT_VEC("D: body +X is north", F.BodyDirToUnreal(FVector(1, 0, 0)), FVector(1, 0, 0), DirTol);
		LSN_EXPECT_VEC("D: body +Y is east", F.BodyDirToUnreal(FVector(0, 1, 0)), FVector(0, 1, 0), DirTol);
	}

	// Site E: near the south pole, latitude -89, longitude 180. There "north" is
	// away from the pole along the longitude-180 meridian, which is body -X, and
	// up is body -Z tilted 1 degree towards -X. So body -X is seen due north,
	// 1 degree above the horizontal, and body +X due south, 1 degree below it.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-89.0, 180.0, TestRadiusM, 0.0);
		double Az = 0.0, El = 0.0;
		FLsnSiteFrame::UnrealDirToAzEl(F.BodyDirToUnreal(FVector(-1, 0, 0)), Az, El);
		TestTrue(TEXT("E: body -X is azimuth 0, elevation +1"), (Az < 1e-9 || Az > 360.0 - 1e-9) && FMath::Abs(El - 1.0) < 1e-9);
		FLsnSiteFrame::UnrealDirToAzEl(F.BodyDirToUnreal(FVector(1, 0, 0)), Az, El);
		TestTrue(TEXT("E: body +X is azimuth 180, elevation -1"), FMath::Abs(Az - 180.0) < 1e-9 && FMath::Abs(El + 1.0) < 1e-9);
		// Body +Y (longitude 90 E) is due west there, on the horizontal.
		FLsnSiteFrame::UnrealDirToAzEl(F.BodyDirToUnreal(FVector(0, 1, 0)), Az, El);
		TestTrue(TEXT("E: body +Y is azimuth 270, elevation 0"), FMath::Abs(Az - 270.0) < 1e-9 && FMath::Abs(El) < 1e-9);
	}

	// The map is a reflection: a right-handed body triad becomes a left-handed
	// Unreal triad. (If this ever becomes +1 someone replaced it by a rotation.)
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-83.25, 41.5, TestRadiusM, 0.0);
		const FVector X = F.BodyDirToUnreal(FVector(1, 0, 0));
		const FVector Y = F.BodyDirToUnreal(FVector(0, 1, 0));
		const FVector Z = F.BodyDirToUnreal(FVector(0, 0, 1));
		const double Det = FVector::DotProduct(FVector::CrossProduct(X, Y), Z);
		TestTrue(TEXT("body -> Unreal has determinant -1"), FMath::Abs(Det + 1.0) < 1e-12);

		// Round trip.
		const FVector D(0.3, -0.4, 0.8660254037844386);
		LSN_EXPECT_VEC("direction round trip", F.UnrealDirToBody(F.BodyDirToUnreal(D)), D, DirTol);
	}
	return true;
}

// ---------------------------------------------------------------------------
// Origin: where points land, in centimetres.
// ---------------------------------------------------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFrameOriginTest, "LunarSiteNavigator.Frame.OriginAndPoints", LsnFrameTest::Flags)
bool FLsnFrameOriginTest::RunTest(const FString& Parameters)
{
	using namespace LsnFrameTest;
	const double R = TestRadiusM;

	// Site at latitude 0, longitude 0, 500 m above the sphere.
	{
		const double H = 500.0;
		const FLsnSiteFrame F = FLsnSiteFrame::Make(0.0, 0.0, R, H);
		TestTrue(TEXT("origin radius"), FMath::Abs(F.OriginRadiusM() - (R + H)) < 1e-9);

		// The site's ground point is the Unreal origin.
		LSN_EXPECT_VEC("site ground point", F.BodyPointMToUnreal(FVector(R + H, 0, 0)), FVector(0, 0, 0), PosTolCm);
		// The Moon's centre is straight down by the origin radius.
		LSN_EXPECT_VEC("moon centre", F.BodyPointMToUnreal(FVector(0, 0, 0)), FVector(0, 0, -(R + H) * 100.0), PosTolCm);
		LSN_EXPECT_VEC("moon centre accessor", F.MoonCentreUnreal(), FVector(0, 0, -(R + H) * 100.0), PosTolCm);
		// The north pole of the sphere: R north of the centre.
		LSN_EXPECT_VEC("north pole point", F.BodyPointMToUnreal(FVector(0, 0, R)), FVector(R * 100.0, 0, -(R + H) * 100.0), PosTolCm);
		// The point at longitude 90 E on the equator: R east of the centre.
		LSN_EXPECT_VEC("lon 90E point", F.BodyPointMToUnreal(FVector(0, R, 0)), FVector(0, R * 100.0, -(R + H) * 100.0), PosTolCm);
		// Round trip.
		const FVector P(123456.0, -654321.0, 111111.0);
		LSN_EXPECT_VEC("point round trip", F.UnrealToBodyPointM(F.BodyPointMToUnreal(P)), P, 1e-6);
	}

	// Surface points on the bare sphere (site height 0).
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-45.0, 90.0, R, 0.0);
		// Zero distance, zero height: the origin.
		LSN_EXPECT_VEC("surface point at the site", F.SurfacePointUnreal(77.0, 0.0, 0.0), FVector(0, 0, 0), PosTolCm);
		// Straight up by 10 m.
		LSN_EXPECT_VEC("10 m above the site", F.SurfacePointUnreal(77.0, 0.0, 10.0), FVector(0, 0, 1000.0), PosTolCm);
		// A quarter of the way round the sphere, due north: R north, R down.
		const double Quarter = R * UE_DOUBLE_PI / 2.0;
		LSN_EXPECT_VEC("quarter circle north", F.SurfacePointUnreal(0.0, Quarter, 0.0), FVector(R * 100.0, 0, -R * 100.0), 1e-4);
		// A quarter of the way round, due east: R east, R down.
		LSN_EXPECT_VEC("quarter circle east", F.SurfacePointUnreal(90.0, Quarter, 0.0), FVector(0, R * 100.0, -R * 100.0), 1e-4);
		// Curvature: at arc distance s the sphere drops by R (1 - cos(s / R)) and
		// the horizontal offset is R sin(s / R). For s = R / 10 (0.1 rad):
		//   horizontal = R * 0.09983341664682815, drop = R * 0.004995834721974179.
		LSN_EXPECT_VEC("curvature drop", F.SurfacePointUnreal(180.0, R / 10.0, 0.0),
			FVector(-R * 100.0 * 0.09983341664682815, 0, -R * 100.0 * 0.004995834721974179), 1e-4);
		// The same route must agree with the body-frame route: walking north from
		// latitude -45 by 45 degrees of arc reaches the equator at longitude 90 E.
		LSN_EXPECT_VEC("great circle north reaches the equator",
			F.SurfacePointUnreal(0.0, R * UE_DOUBLE_PI / 4.0, 0.0),
			F.BodyPointMToUnreal(FLsnSiteFrame::LatLonToBodyDir(0.0, 90.0) * R), 1e-4);
		// Walking east from the equator by 10 degrees of arc increases east longitude by 10 degrees.
		const FLsnSiteFrame G = FLsnSiteFrame::Make(0.0, 20.0, R, 0.0);
		LSN_EXPECT_VEC("great circle east increases east longitude",
			G.SurfacePointUnreal(90.0, R * UE_DOUBLE_PI / 18.0, 0.0),
			G.BodyPointMToUnreal(FLsnSiteFrame::LatLonToBodyDir(0.0, 30.0) * R), 1e-4);
	}

	// A point on the eye's line of sight.
	{
		// Eye 2 m up, looking east, level, 1000 m away: 1000 m east, 2 m up.
		LSN_EXPECT_VEC("sight point level east", FLsnSiteFrame::SightPointUnreal(2.0, 90.0, 0.0, 1000.0), FVector(0, 100000.0, 200.0), PosTolCm);
		// Looking north, 30 degrees up, 2000 m away: 1732.05 m north, 1000 m + 2 m up.
		LSN_EXPECT_VEC("sight point north 30 up", FLsnSiteFrame::SightPointUnreal(2.0, 0.0, 30.0, 2000.0),
			FVector(173205.0807568877, 0, 100200.0), 1e-6);
	}
	return true;
}

#undef LSN_EXPECT_VEC

#endif // WITH_DEV_AUTOMATION_TESTS
