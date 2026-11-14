// Mesh generator tests. The test radius is a round number chosen for the
// test, not a physical constant.

#include "Tests/LsnTestSupport.h"
#include "Planner/LsnPlanner.h"
#include "Package/LsnTerrainPatches.h"
#include "Frame/LsnSiteFrame.h"
#include "KismetProceduralMeshLibrary.h"
#include "Mesh/LsnMesh.h"
#include "ProceduralMeshComponent.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnMeshTest
{
	constexpr double TestRadiusM = 1000000.0;
}

// The winding rule this project uses is the engine's: checked against a box the engine itself generates.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnMeshWindingTest, "LunarSiteNavigator.Mesh.WindingMatchesEngine", LsnTest::Flags)
bool FLsnMeshWindingTest::RunTest(const FString& Parameters)
{
	FLsnMeshData Box;
	TArray<FVector2D> UVs;
	TArray<FProcMeshTangent> Tangents;
	UKismetProceduralMeshLibrary::GenerateBoxMesh(FVector(50, 50, 50), Box.Positions, Box.Triangles, Box.Normals, UVs, Tangents);
	int32 Wrong = 0;
	for (int32 T = 0; T < Box.NumTriangles(); ++T)
	{
		// Every face of the engine's box faces along the normal the engine gave its vertices.
		if (FVector::DotProduct(Box.TriangleFacing(T), Box.Normals[Box.Triangles[T * 3]]) <= 0.0)
		{
			++Wrong;
		}
	}
	TestEqual(TEXT("engine box triangles that TriangleFacing puts on the wrong side"), Wrong, 0);

	FLsnMeshData Mesh;
	Mesh.Positions = { FVector(0, 0, 0), FVector(100, 0, 0), FVector(0, 100, 0) };
	Mesh.AddTriangleFacing(0, 1, 2, FVector(0, 0, 1));
	Mesh.AddTriangleFacing(0, 1, 2, FVector(0, 0, -1));
	TestTrue(TEXT("AddTriangleFacing up faces up"), Mesh.TriangleFacing(0).Z > 0.0);
	TestTrue(TEXT("AddTriangleFacing down faces down"), Mesh.TriangleFacing(1).Z < 0.0);
	return true;
}

// The point that sets the horizon, placed from elevation angle and arc distance.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnMeshHorizonPointTest, "LunarSiteNavigator.Mesh.HorizonPoint", LsnTest::Flags)
bool FLsnMeshHorizonPointTest::RunTest(const FString& Parameters)
{
	using namespace LsnMeshTest;
	const double R = TestRadiusM;

	// Hand case: eye on the ground of a bare sphere, elevation 0, arc 0.1 rad due north.
	// The point lies in the horizontal plane of the site, R tan(0.1) away:
	//   tan(0.1) = 0.10033467208545055.
	{
		const FLsnSiteFrame F = FLsnSiteFrame::Make(-80.0, 10.0, R, 0.0);
		FVector P;
		TestTrue(TEXT("level sight line meets the radial"), LsnMesh::HorizonPointUnreal(F, 0.0, 0.0, 0.0, 0.1 * R, P));
		TestTrue(TEXT("level sight line: point is R tan(0.1) north, at eye level"),
			(P - FVector(R * 100.0 * 0.10033467208545055, 0.0, 0.0)).GetAbsMax() < 1e-3);
	}

	// Property: seen from the eye the point is at the stated azimuth and elevation,
	// and seen from the Moon's centre it is the stated arc away from the site.
	const FLsnSiteFrame F = FLsnSiteFrame::Make(-88.0, 45.0, R, -500.0);
	const FVector Centre = F.MoonCentreUnreal();
	double WorstAngleDeg = 0.0, WorstArcM = 0.0;
	for (double EyeHeightM : { 0.0, 2.0, 20.0 })
	{
		const FVector Eye(0, 0, EyeHeightM * 100.0);
		for (double Az : { 0.0, 33.25, 90.0, 201.5, 359.75 })
		{
			for (double El : { -1.5, -0.01, 0.0, 0.3, 3.0, 12.0 })
			{
				for (double ArcM : { 50.0, 2000.0, 42000.0, 300000.0 })
				{
					FVector P;
					if (!LsnMesh::HorizonPointUnreal(F, EyeHeightM, Az, El, ArcM, P))
					{
						AddError(FString::Printf(TEXT("no point for az %.2f el %.2f arc %.0f"), Az, El, ArcM));
						continue;
					}
					WorstAngleDeg = FMath::Max(WorstAngleDeg, LsnTest::AngleDeg(P - Eye, FLsnSiteFrame::AzElToUnrealDir(Az, El)));
					const double ArcBackM = FMath::DegreesToRadians(LsnTest::AngleDeg(P - Centre, FVector(0, 0, 1))) * R;
					WorstArcM = FMath::Max(WorstArcM, FMath::Abs(ArcBackM - ArcM));
				}
			}
		}
	}
	AddInfo(FString::Printf(TEXT("worst direction error %.3g deg, worst arc error %.3g m"), WorstAngleDeg, WorstArcM));
	TestTrue(TEXT("the point is seen at the stated azimuth and elevation (1e-9 deg)"), WorstAngleDeg < 1e-9);
	TestTrue(TEXT("the point is the stated arc away (1e-6 m)"), WorstArcM < 1e-6);

	// Values that cannot describe a point are refused, not drawn.
	FVector Unused;
	TestFalse(TEXT("NaN elevation"), LsnMesh::HorizonPointUnreal(F, 2.0, 0.0, NAN, 1000.0, Unused));
	TestFalse(TEXT("zero distance"), LsnMesh::HorizonPointUnreal(F, 2.0, 0.0, 1.0, 0.0, Unused));
	TestFalse(TEXT("sight line that never meets the radial"), LsnMesh::HorizonPointUnreal(F, 2.0, 0.0, 89.0, 300000.0, Unused));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnMeshSphereTest, "LunarSiteNavigator.Mesh.MoonSphere", LsnTest::Flags)
bool FLsnMeshSphereTest::RunTest(const FString& Parameters)
{
	using namespace LsnMeshTest;
	const double R = TestRadiusM;
	const FLsnSiteFrame F = FLsnSiteFrame::Make(-88.0, 45.0, R, 300.0);

	// Flat sphere: every vertex is R from the mesh origin (the Moon's centre).
	FLsnMeshData Sphere;
	LsnMesh::BuildMoonSphere(F, 5.0, [R](double) { return R; }, 0.13f, Sphere);
	double WorstCm = 0.0;
	for (const FVector& P : Sphere.Positions)
	{
		WorstCm = FMath::Max(WorstCm, FMath::Abs(P.Size() - R * 100.0));
	}
	TestTrue(TEXT("flat sphere vertices are at the sphere radius (1e-4 cm)"), WorstCm < 1e-4);
	int32 Inward = 0;
	for (int32 T = 0; T < Sphere.NumTriangles(); ++T)
	{
		const FVector Centroid = Sphere.Positions[Sphere.Triangles[T * 3]] + Sphere.Positions[Sphere.Triangles[T * 3 + 1]] + Sphere.Positions[Sphere.Triangles[T * 3 + 2]];
		if (FVector::DotProduct(Sphere.TriangleFacing(T), Centroid) <= 0.0)
		{
			++Inward;
		}
	}
	TestEqual(TEXT("sphere triangles facing inward"), Inward, 0);
	TestTrue(TEXT("sphere has triangles"), Sphere.NumTriangles() > 1000);

	// The frame's surface points lie on the same sphere, and the site direction is straight up from the centre.
	const FVector Centre = F.MoonCentreUnreal();
	for (double Az : { 0.0, 120.0, 250.0 })
	{
		for (double ArcM : { 10.0, 5000.0, 250000.0 })
		{
			TestTrue(TEXT("surface point is on the sphere (1e-4 cm)"), FMath::Abs((F.SurfacePointUnreal(Az, ArcM, 0.0) - Centre).Size() - R * 100.0) < 1e-4);
		}
	}

	// Sunk sphere: seen from the eye, no point of it rises above the cap; it is never
	// outside the reference sphere; and under the site it is the sink depth below the eye.
	const double EyeHeightM = 2.0, CapDeg = -2.0, SinkM = 500.0;
	const FVector Eye(0, 0, EyeHeightM * 100.0);
	double WorstOverCapDeg = -1000.0;
	for (int32 I = 0; I <= 1800; ++I)
	{
		const double Angle = UE_DOUBLE_PI * I / 1800.0;
		const double Radius = LsnMesh::SunkSphereRadiusM(F, EyeHeightM, CapDeg, SinkM, Angle);
		TestTrue(TEXT("sunk sphere stays inside the reference sphere"), Radius <= R + 1e-9);
		const FVector P = Centre + FVector(FMath::Sin(Angle), 0.0, FMath::Cos(Angle)) * (Radius * 100.0);
		double Az = 0.0, El = 0.0;
		FLsnSiteFrame::UnrealDirToAzEl(P - Eye, Az, El);
		WorstOverCapDeg = FMath::Max(WorstOverCapDeg, El - CapDeg);
	}
	TestTrue(TEXT("sunk sphere never rises above the cap elevation"), WorstOverCapDeg <= 1e-9);
	const double UnderSite = LsnMesh::SunkSphereRadiusM(F, EyeHeightM, CapDeg, SinkM, 0.0);
	TestTrue(TEXT("under the site the sphere is the sink depth below the eye"), FMath::Abs(UnderSite - (F.OriginRadiusM() + EyeHeightM - SinkM)) < 1e-6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnMeshCraterTest, "LunarSiteNavigator.Mesh.CratersOnlyLower", LsnTest::Flags)
bool FLsnMeshCraterTest::RunTest(const FString& Parameters)
{
	double Lowest = 0.0, Deepest = 0.0;
	int32 NonZero = 0;
	for (int32 I = 0; I < 200; ++I)
	{
		for (int32 J = 0; J < 200; ++J)
		{
			const double Depth = LsnMesh::CraterDepthM(-9000.0 + 91.7 * I, -7000.0 + 73.3 * J, 12345u);
			Lowest = FMath::Min(Lowest, Depth);
			Deepest = FMath::Max(Deepest, Depth);
			NonZero += Depth > 0.0 ? 1 : 0;
		}
	}
	TestTrue(TEXT("crater depth is never negative (the surface is only ever lowered)"), Lowest >= 0.0);
	TestTrue(TEXT("crater depth stays below the depth the sphere is sunk by"), Deepest < 400.0);
	TestTrue(TEXT("there are craters"), NonZero > 1000);
	TestEqual(TEXT("the formula is deterministic"), LsnMesh::CraterDepthM(123.0, 456.0, 7u), LsnMesh::CraterDepthM(123.0, 456.0, 7u));
	return true;
}

// The silhouette measurement on a mesh small enough to work out by hand.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnMeshSilhouetteTest, "LunarSiteNavigator.Mesh.SilhouetteMeasurement", LsnTest::Flags)
bool FLsnMeshSilhouetteTest::RunTest(const FString& Parameters)
{
	// One triangle seen from an eye 1 m above the origin. Its top edge runs from
	//   A: azimuth -1 deg, 1000 m away horizontally, elevation 10 deg, to
	//   B: azimuth +1 deg, 3000 m away horizontally, elevation 20 deg.
	// Where that edge crosses azimuth 0, tan(elevation) = (tan 10 + tan 20) / (2 cos 1 deg).
	const FVector Eye(0, 0, 100.0);
	auto PointAt = [&Eye](double AzDeg, double HorizontalM, double ElDeg)
	{
		const double Az = FMath::DegreesToRadians(AzDeg);
		return Eye + FVector(FMath::Cos(Az), FMath::Sin(Az), FMath::Tan(FMath::DegreesToRadians(ElDeg))) * (HorizontalM * 100.0);
	};
	FLsnMeshData Mesh;
	Mesh.Positions = { PointAt(-1.0, 1000.0, 10.0), PointAt(1.0, 3000.0, 20.0), PointAt(0.0, 500.0, -30.0) };
	Mesh.AddTriangleFacing(0, 1, 2, FVector(-1, 0, 0));

	FLsnPlacedMesh Placed;
	Placed.Mesh = &Mesh;
	const FLsnSilhouette Silhouette({ Placed }, Eye);

	double El = 0.0;
	const double ExpectedMid = FMath::RadiansToDegrees(FMath::Atan(
		(FMath::Tan(FMath::DegreesToRadians(10.0)) + FMath::Tan(FMath::DegreesToRadians(20.0))) / (2.0 * FMath::Cos(FMath::DegreesToRadians(1.0)))));
	TestTrue(TEXT("azimuth 0 meets the triangle"), Silhouette.MaxElevationDeg(0.0, El));
	TestTrue(TEXT("elevation at azimuth 0 is the hand value"), FMath::Abs(El - ExpectedMid) < 1e-9);
	TestTrue(TEXT("azimuth 360 is azimuth 0"), Silhouette.MaxElevationDeg(360.0, El) && FMath::Abs(El - ExpectedMid) < 1e-9);
	TestTrue(TEXT("azimuth -1 meets vertex A"), Silhouette.MaxElevationDeg(-1.0, El) && FMath::Abs(El - 10.0) < 1e-6);
	TestTrue(TEXT("azimuth +1 meets vertex B"), Silhouette.MaxElevationDeg(1.0, El) && FMath::Abs(El - 20.0) < 1e-6);
	TestFalse(TEXT("azimuth 5 misses the triangle"), Silhouette.MaxElevationDeg(5.0, El));
	TestFalse(TEXT("azimuth 180 misses the triangle (it is behind the eye)"), Silhouette.MaxElevationDeg(180.0, El));

	// A mesh origin offset moves the measurement with it.
	FLsnPlacedMesh Raised = Placed;
	Raised.Origin = FVector(0, 0, 100000.0 * FMath::Tan(FMath::DegreesToRadians(1.0))); // lifts vertex A (1000 m away) by 1000 m * tan 1
	const FLsnSilhouette RaisedSilhouette({ Raised }, Eye);
	const double ExpectedRaisedA = FMath::RadiansToDegrees(FMath::Atan(FMath::Tan(FMath::DegreesToRadians(10.0)) + FMath::Tan(FMath::DegreesToRadians(1.0))));
	TestTrue(TEXT("a raised mesh is measured where it is"), RaisedSilhouette.MaxElevationDeg(-1.0, El) && FMath::Abs(El - ExpectedRaisedA) < 1e-6);
	return true;
}

// P. The ground from the terrain patches of a package (SPEC 5.9). Criteria, written before the first run
//    (14 November 2026):
//    1. every node of a patch is a vertex at its (east, north, up), to 1e-6 m;
//    2. a coarser patch has no triangle inside the square of a finer one, and outside it every cell with
//       data has two triangles facing up: with a 5 x 5 patch of 5 m spacing inside a 5 x 5 patch of 10 m
//       spacing that is 16 * 2 + (16 - 4) * 2 = 56 triangles (the first draft of this test gave both
//       patches the same spacing, so that neither was the finer one; corrected before a valid run);
//    3. the patches are taken by spacing: the same list in another order gives the same number of
//       vertices and triangles;
//    4. a node without data leaves out the cells it belongs to (four for a node in the middle), and they
//       are counted;
//    5. the height read at a point is linear between the nodes, and there is none outside the patch;
//    6. on a published package with patches (if one is there): the patches load with the counts their
//       manifest states, and the mesh has the triangles of all cells outside the next finer patch.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPatchTerrainTest, "LunarSiteNavigator.Terrain.PatchMesh", LsnTest::Flags)
bool FLsnPatchTerrainTest::RunTest(const FString& Parameters)
{
	auto MakePatch = [](const TCHAR* Id, double Spacing, int32 Count)
	{
		FLsnTerrainPatch Patch;
		Patch.Id = Id;
		Patch.SpacingM = Spacing;
		Patch.CountEast = Patch.CountNorth = Count;
		Patch.HalfWidthM = 0.5 * Spacing * (Count - 1);
		Patch.EastMinM = Patch.NorthMinM = -Patch.HalfWidthM;
		for (int32 I = 0; I < Count; ++I)
		{
			for (int32 J = 0; J < Count; ++J)
			{
				// A tilted plane with a little curvature: up = 0.1 east - 0.05 north - 0.001 (east^2 + north^2).
				const double East = Patch.EastMinM + J * Spacing, North = Patch.NorthMinM + I * Spacing;
				Patch.UpM.Add(static_cast<float>(0.1 * East - 0.05 * North - 0.001 * (East * East + North * North)));
			}
		}
		return Patch;
	};
	const FLsnTerrainPatch Fine = MakePatch(TEXT("site"), 5.0, 5), Coarse = MakePatch(TEXT("wide"), 10.0, 5);
	FLsnMeshData Mesh, Swapped;
	int32 Missing = -1;
	LsnMesh::BuildPatchTerrain({ Fine, Coarse }, 0.13f, Mesh, Missing);
	TestEqual(TEXT("P1: every node is a vertex"), Mesh.Positions.Num(), 25 + 25);
	double Worst = 0.0;
	for (int32 I = 0; I < 5; ++I)
	{
		for (int32 J = 0; J < 5; ++J)
		{
			const FVector Expected = FLsnSiteFrame::EnuMToUnreal(FVector(-10.0 + 5.0 * J, -10.0 + 5.0 * I, Fine.UpM[I * 5 + J]));
			Worst = FMath::Max(Worst, FVector::Distance(Mesh.Positions[I * 5 + J], Expected) / FLsnSiteFrame::CmPerM);
		}
	}
	TestTrue(FString::Printf(TEXT("P1: vertices at (east, north, up), worst %.2e m"), Worst), Worst <= 1e-6);
	TestEqual(TEXT("P2: 32 triangles of the fine patch and 24 of the coarse one outside it"), Mesh.NumTriangles(), 56);
	TestEqual(TEXT("P2: no cell without data"), Missing, 0);
	int32 FacingDown = 0, CoarseInside = 0;
	for (int32 T = 0; T < Mesh.NumTriangles(); ++T)
	{
		FacingDown += Mesh.TriangleFacing(T).Z <= 0.0 ? 1 : 0;
		if (Mesh.Triangles[T * 3] >= 25)
		{
			const FVector Centre = (Mesh.Positions[Mesh.Triangles[T * 3]] + Mesh.Positions[Mesh.Triangles[T * 3 + 1]] + Mesh.Positions[Mesh.Triangles[T * 3 + 2]]) / 3.0;
			const FVector Enu = FLsnSiteFrame::UnrealToEnuM(Centre);
			CoarseInside += (FMath::Abs(Enu.X) < 10.0 && FMath::Abs(Enu.Y) < 10.0) ? 1 : 0;
		}
	}
	TestEqual(TEXT("P2: every triangle faces up"), FacingDown, 0);
	TestEqual(TEXT("P2: no triangle of the coarse patch inside the fine one"), CoarseInside, 0);
	LsnMesh::BuildPatchTerrain({ Coarse, Fine }, 0.13f, Swapped, Missing);
	TestEqual(TEXT("P3: the order of the list does not matter (vertices)"), Swapped.Positions.Num(), Mesh.Positions.Num());
	TestEqual(TEXT("P3: the order of the list does not matter (triangles)"), Swapped.NumTriangles(), Mesh.NumTriangles());

	FLsnTerrainPatch Holed = MakePatch(TEXT("near"), 10.0, 5);
	Holed.UpM[2 * 5 + 2] = std::numeric_limits<float>::quiet_NaN();
	LsnMesh::BuildPatchTerrain({ Holed }, 0.13f, Mesh, Missing);
	TestEqual(TEXT("P4: four cells left out around a node without data"), Missing, 4);
	TestEqual(TEXT("P4: the other twelve cells are drawn"), Mesh.NumTriangles(), 24);

	double Up = 0.0;
	TestTrue(TEXT("P5: a height inside the patch"), Coarse.UpAt(5.0, 0.0, Up));
	TestEqual(TEXT("P5: linear between two nodes"), Up, 0.5 * (static_cast<double>(Coarse.UpM[2 * 5 + 2]) + Coarse.UpM[2 * 5 + 3]), 1e-9);
	TestFalse(TEXT("P5: none outside the patch"), Coarse.UpAt(25.0, 0.0, Up));

	// On a published package.
	const FString Root = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Entries;
	FString Error;
	if (!LsnPackageIO::LoadIndex(Root, Entries, Error))
	{
		AddWarning(TEXT("NOT RUN on published packages: none found."));
		return true;
	}
	int32 Checked = 0;
	for (const FLsnIndexEntry& Entry : Entries)
	{
		TArray<FLsnTerrainPatch> Patches;
		if (Entry.Kind != TEXT("site") || !LsnPackageIO::LoadTerrainPatches(FPaths::Combine(Root, Entry.Path), Patches, Error))
		{
			continue;
		}
		++Checked;
		Patches.Sort([](const FLsnTerrainPatch& A, const FLsnTerrainPatch& B) { return A.SpacingM < B.SpacingM; });
		int32 ExpectedTriangles = 0, WithoutData = 0;
		double Inner = -1.0;
		for (const FLsnTerrainPatch& Patch : Patches)
		{
			TestEqual(Entry.SiteId + TEXT(": P6: a patch holds count_north x count_east values"), Patch.UpM.Num(), Patch.CountEast * Patch.CountNorth);
			for (int32 I = 0; I + 1 < Patch.CountNorth; ++I)
			{
				for (int32 J = 0; J + 1 < Patch.CountEast; ++J)
				{
					const double E0 = Patch.EastMinM + J * Patch.SpacingM, N0 = Patch.NorthMinM + I * Patch.SpacingM;
					const bool bInside = FMath::Max(FMath::Abs(E0), FMath::Abs(E0 + Patch.SpacingM)) <= Inner + 5.0e-4 && FMath::Max(FMath::Abs(N0), FMath::Abs(N0 + Patch.SpacingM)) <= Inner + 5.0e-4;
					const bool bData = !FMath::IsNaN(Patch.UpM[I * Patch.CountEast + J]) && !FMath::IsNaN(Patch.UpM[I * Patch.CountEast + J + 1])
						&& !FMath::IsNaN(Patch.UpM[(I + 1) * Patch.CountEast + J]) && !FMath::IsNaN(Patch.UpM[(I + 1) * Patch.CountEast + J + 1]);
					ExpectedTriangles += (!bInside && bData) ? 2 : 0;
					WithoutData += (!bInside && !bData) ? 1 : 0;
				}
			}
			Inner = FMath::Max(Inner, Patch.HalfWidthM);
		}
		LsnMesh::BuildPatchTerrain(Patches, 0.13f, Mesh, Missing);
		TestEqual(Entry.SiteId + TEXT(": P6: triangles of all cells outside the next finer patch"), Mesh.NumTriangles(), ExpectedTriangles);
		TestEqual(Entry.SiteId + TEXT(": P6: cells without data"), Missing, WithoutData);
	}
	AddInfo(FString::Printf(TEXT("terrain patches read and meshed for %d published site packages"), Checked));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
