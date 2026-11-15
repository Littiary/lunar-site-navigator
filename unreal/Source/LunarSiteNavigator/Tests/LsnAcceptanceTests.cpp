// Stage 1 acceptance tests of the Unreal view scene.
//
// Acceptance criteria and tolerances. They were written before the first
// measurement and are not to be changed to make a test pass.
//
// A. Sun from the package.
//    At every tested timeline sample, the direction the scene's directional
//    light comes from, and the direction of the centre of the Sun disc seen
//    from the eye, are within 0.001 deg of the package's Sun azimuth and
//    elevation. The light's source angle and the disc's angular radius are
//    within 0.001 deg of the package's angular radius (the source angle is a
//    diameter). The same holds for the Earth disc.
//    When the Sun series of a package is replaced by another direction, the
//    scene follows it: the scene has no Sun of its own.
//
// B. Horizon silhouette.
//    For every observer height of the package and every azimuth sample, the
//    highest elevation angle at which scene geometry (site terrain and Moon
//    sphere, vertices rounded to 32-bit floats as on the GPU) is seen from the
//    eye is within 0.001 deg of the package's horizon elevation.
//    Halfway between two neighbouring samples the silhouette lies between the
//    two sample values, with the same 0.001 deg allowance. (The contract
//    prescribes linear interpolation between samples; the mesh edge is a
//    straight line in space, which differs from that only inside this band.)
//
//    Why 0.001 deg: it is about one part in 270 of the Sun's angular radius in
//    the sample, and it is far above what the representation can cost. A
//    32-bit vertex coordinate 300 km from the origin is exact to about 2 cm,
//    which is 0.000004 deg; the package's 32-bit elevation angles are exact to
//    about 0.0000003 deg at 3 deg.
//
// The package's horizon is the same array the Python panorama is drawn from,
// so criterion B is the numeric form of "the silhouette matches the panorama".

#include "Tests/LsnTestSupport.h"
#include "Package/LsnSha256.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnAcceptance
{
	constexpr double DirectionToleranceDeg = 0.001;
	constexpr double SilhouetteToleranceDeg = 0.001;

	/** A throw-away game world holding one scene actor. */
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

	/** Checks one disc against the package: where it is seen from the eye, and how large. */
	inline void CheckDisc(FAutomationTestBase& Test, const ALsnSiteScene& Scene, const UProceduralMeshComponent* Disc, const FLsnBodySeries& Series,
		int32 TimeIndex, const TCHAR* Name, double& WorstDirectionDeg, double& WorstRadiusDeg)
	{
		if (!Disc->IsVisible())
		{
			Test.AddError(FString::Printf(TEXT("%s disc is hidden at sample %d"), Name, TimeIndex));
			return;
		}
		const FVector FromEye = Disc->GetComponentLocation() - Scene.GetEyeUnreal();
		const FVector Expected = FLsnSiteFrame::AzElToUnrealDir(Series.AzimuthDeg[TimeIndex], Series.ElevationDeg[TimeIndex]);
		WorstDirectionDeg = FMath::Max(WorstDirectionDeg, LsnTest::AngleDeg(FromEye, Expected));
		// The disc mesh is a sphere of radius 1 cm scaled by the component.
		const double RadiusCm = Disc->GetComponentScale().X;
		const double AngularRadiusDeg = FMath::RadiansToDegrees(FMath::Asin(RadiusCm / FromEye.Size()));
		WorstRadiusDeg = FMath::Max(WorstRadiusDeg, FMath::Abs(AngularRadiusDeg - Series.AngularRadiusDeg[TimeIndex]));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnAcceptanceSunTest, "LunarSiteNavigator.Acceptance.SunAndEarthFromPackage", LsnTest::Flags)
bool FLsnAcceptanceSunTest::RunTest(const FString& Parameters)
{
	using namespace LsnAcceptance;

	FSceneFixture Fixture;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error),
		Fixture.Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		return false;
	}
	const ALsnSiteScene& Scene = *Fixture.Scene;
	const FLsnSitePackage& P = Scene.GetPackage();
	const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
	const FLsnBodySeries* Earth = P.FindSeries(TEXT("EARTH"));
	if (!TestTrue(TEXT("the sample has Sun and Earth series"), Sun && Earth))
	{
		return false;
	}

	double WorstLightDeg = 0.0, WorstSourceAngleDeg = 0.0;
	double WorstSunDiscDeg = 0.0, WorstSunRadiusDeg = 0.0, WorstEarthDiscDeg = 0.0, WorstEarthRadiusDeg = 0.0;
	int32 Tested = 0;
	for (int32 I = 0; I < P.Time.Count; I += (I + 13 < P.Time.Count ? 13 : 1))
	{
		if (!TestTrue(TEXT("the time index is accepted"), Fixture.Scene->SetTimeIndex(I)))
		{
			break;
		}
		const FVector Expected = FLsnSiteFrame::AzElToUnrealDir(Sun->AzimuthDeg[I], Sun->ElevationDeg[I]);
		WorstLightDeg = FMath::Max(WorstLightDeg, LsnTest::AngleDeg(Scene.GetSunDirectionFromLight(), Expected));
		// What the light component itself reports, not only what the scene says about it:
		// a directional light shines along its forward vector.
		WorstLightDeg = FMath::Max(WorstLightDeg, LsnTest::AngleDeg(-Scene.GetSunLight()->GetForwardVector(), Expected));
		WorstSourceAngleDeg = FMath::Max(WorstSourceAngleDeg, FMath::Abs(0.5 * Scene.GetSunLight()->LightSourceAngle - Sun->AngularRadiusDeg[I]));
		TestTrue(TEXT("the Sun light is switched on"), Scene.GetSunLight()->IsVisible());
		CheckDisc(*this, Scene, Scene.GetSunDisc(), *Sun, I, TEXT("Sun"), WorstSunDiscDeg, WorstSunRadiusDeg);
		CheckDisc(*this, Scene, Scene.GetEarthDisc(), *Earth, I, TEXT("Earth"), WorstEarthDiscDeg, WorstEarthRadiusDeg);
		++Tested;
	}
	AddInfo(FString::Printf(TEXT("%d samples: light direction %.3g deg, light half source angle %.3g deg, Sun disc %.3g / %.3g deg, Earth disc %.3g / %.3g deg (direction / radius); tolerance %.3f deg"),
		Tested, WorstLightDeg, WorstSourceAngleDeg, WorstSunDiscDeg, WorstSunRadiusDeg, WorstEarthDiscDeg, WorstEarthRadiusDeg, DirectionToleranceDeg));
	TestTrue(TEXT("samples were tested"), Tested > 50);
	TestTrue(TEXT("A: light direction equals the package's Sun direction"), WorstLightDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("A: light source angle equals the package's Sun angular diameter"), WorstSourceAngleDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("A: Sun disc is where the package says"), WorstSunDiscDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("A: Sun disc has the package's angular radius"), WorstSunRadiusDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("A: Earth disc is where the package says"), WorstEarthDiscDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("A: Earth disc has the package's angular radius"), WorstEarthRadiusDeg <= DirectionToleranceDeg);

	TestFalse(TEXT("a time index past the end is refused"), Fixture.Scene->SetTimeIndex(P.Time.Count));
	TestFalse(TEXT("a negative time index is refused"), Fixture.Scene->SetTimeIndex(-1));
	return true;
}

// The scene has no Sun of its own: change the package and the scene follows.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnAcceptanceSunFollowsTest, "LunarSiteNavigator.Acceptance.SunFollowsThePackage", LsnTest::Flags)
bool FLsnAcceptanceSunFollowsTest::RunTest(const FString& Parameters)
{
	using namespace LsnAcceptance;

	// A copy of the sample whose Sun series is overwritten with one known
	// direction: azimuth 90 (due east), elevation 5.
	const FString Dir = LsnTest::CopyPackageToScratch(LsnTest::FixturePackageDir(TEXT("site")), TEXT("sun-east"));
	FLsnSitePackage Original;
	FString Error;
	if (!TestTrue(TEXT("the copy loads"), LsnPackageIO::LoadSitePackage(Dir, Original, Error)))
	{
		return false;
	}
	TArray<float> Azimuth, Elevation;
	Azimuth.Init(90.0f, Original.Time.Count);
	Elevation.Init(5.0f, Original.Time.Count);
	const TArrayView<const uint8> AzBytes(reinterpret_cast<const uint8*>(Azimuth.GetData()), Azimuth.Num() * sizeof(float));
	const TArrayView<const uint8> ElBytes(reinterpret_cast<const uint8*>(Elevation.GetData()), Elevation.Num() * sizeof(float));
	// Since 15 November 2026 the reader checks every array against its SHA-256 (SPEC 3.1): the copy
	// states the digests of its new arrays, as a package written that way would.
	FString DigestManifest;
	FFileHelper::LoadFileToString(DigestManifest, *FPaths::Combine(Dir, TEXT("manifest.json")));
	auto Rewrite = [&](const TCHAR* File, const TArrayView<const uint8>& Bytes)
	{
		TArray<uint8> Old;
		FFileHelper::LoadFileToArray(Old, *FPaths::Combine(Dir, File));
		DigestManifest.ReplaceInline(*LsnSha256::HexOf(Old.GetData(), Old.Num()), *LsnSha256::HexOf(Bytes.GetData(), Bytes.Num()));
		return FFileHelper::SaveArrayToFile(Bytes, *FPaths::Combine(Dir, File));
	};
	TestTrue(TEXT("test set-up: azimuth series written"), Rewrite(TEXT("series_sun_azimuth_deg.f4"), AzBytes));
	TestTrue(TEXT("test set-up: elevation series written"), Rewrite(TEXT("series_sun_elevation_deg.f4"), ElBytes));
	FFileHelper::SaveStringToFile(DigestManifest, *FPaths::Combine(Dir, TEXT("manifest.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);

	FSceneFixture Fixture;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the altered package (%s)"), *Error), Fixture.Scene->LoadPackageDirectory(Dir, Error)))
	{
		return false;
	}
	Fixture.Scene->SetTimeIndex(Original.Time.Count / 2);
	const FVector ToSun = Fixture.Scene->GetSunDirectionFromLight();

	// Azimuth 90, elevation 5 by hand: (north, east, up) = (0, cos 5, sin 5).
	const FVector Expected(0.0, 0.9961946980917455, 0.08715574274765817);
	const double ErrorDeg = LsnTest::AngleDeg(ToSun, Expected);
	AddInfo(FString::Printf(TEXT("Sun at azimuth 90, elevation 5: scene light is %.3g deg off"), ErrorDeg));
	TestTrue(TEXT("the light comes from due east, 5 degrees up"), ErrorDeg <= DirectionToleranceDeg);

	// "Sun in the east": a camera looking north has it on its right, and the light travels towards the west.
	const FVector CameraRight = FRotationMatrix(FRotator(0.0, 0.0, 0.0)).GetUnitAxis(EAxis::Y);
	TestTrue(TEXT("a camera looking north has the Sun on its right"), FVector::DotProduct(ToSun, CameraRight) > 0.99);
	TestTrue(TEXT("the light travels towards -Y (west) and downwards"),
		Fixture.Scene->GetSunLight()->GetForwardVector().Y < -0.99 && Fixture.Scene->GetSunLight()->GetForwardVector().Z < 0.0);
	const FVector DiscFromEye = Fixture.Scene->GetSunDisc()->GetComponentLocation() - Fixture.Scene->GetEyeUnreal();
	TestTrue(TEXT("the Sun disc is due east, 5 degrees up"), LsnTest::AngleDeg(DiscFromEye, Expected) <= DirectionToleranceDeg);

	// A package without a timeline shows no Sun at all, rather than a default one.
	const FString NoTimelineDir = LsnTest::CopyPackageToScratch(LsnTest::FixturePackageDir(TEXT("site")), TEXT("scene-notimeline"));
	FString Manifest;
	FFileHelper::LoadFileToString(Manifest, *FPaths::Combine(NoTimelineDir, TEXT("manifest.json")));
	Manifest.ReplaceInline(TEXT("\"timeline\": {"), TEXT("\"timeline_removed_by_test\": {"));
	FFileHelper::SaveStringToFile(Manifest, *FPaths::Combine(NoTimelineDir, TEXT("manifest.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	FSceneFixture Bare;
	if (TestTrue(FString::Printf(TEXT("the scene loads a horizon-only package (%s)"), *Error), Bare.Scene->LoadPackageDirectory(NoTimelineDir, Error)))
	{
		TestFalse(TEXT("no timeline: the Sun light is off"), Bare.Scene->GetSunLight()->IsVisible());
		TestFalse(TEXT("no timeline: the Sun disc is hidden"), Bare.Scene->GetSunDisc()->IsVisible());
		TestFalse(TEXT("no timeline: the Earth disc is hidden"), Bare.Scene->GetEarthDisc()->IsVisible());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnAcceptanceHorizonTest, "LunarSiteNavigator.Acceptance.HorizonSilhouette", LsnTest::Flags)
bool FLsnAcceptanceHorizonTest::RunTest(const FString& Parameters)
{
	using namespace LsnAcceptance;

	FSceneFixture Fixture;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error),
		Fixture.Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		return false;
	}
	ALsnSiteScene& Scene = *Fixture.Scene;
	const FLsnSitePackage& P = Scene.GetPackage();

	for (int32 H = 0; H < P.NumHeights(); ++H)
	{
		if (!TestTrue(TEXT("the observer height is accepted"), Scene.SetHeightIndex(H)))
		{
			continue;
		}
		TestEqual(TEXT("horizon samples that could not be placed"), Scene.GetSkippedHorizonSamples(), 0);

		// The geometry exactly as the components hold it, at the components' world positions.
		FLsnPlacedMesh TerrainMesh, SphereMesh;
		TerrainMesh.Mesh = &Scene.GetTerrainMeshData();
		TerrainMesh.Origin = Scene.GetTerrainComponent()->GetComponentLocation();
		SphereMesh.Mesh = &Scene.GetMoonSphereMeshData();
		SphereMesh.Origin = Scene.GetMoonSphereComponent()->GetComponentLocation();
		TestEqual(TEXT("the terrain component holds the measured mesh"),
			Scene.GetTerrainComponent()->GetProcMeshSection(0)->ProcVertexBuffer.Num(), TerrainMesh.Mesh->Positions.Num());
		const FLsnSilhouette Silhouette({ TerrainMesh, SphereMesh }, Scene.GetEyeUnreal());

		double WorstAtSampleDeg = 0.0, WorstBetweenDeg = 0.0;
		int32 WorstAzimuthIndex = -1, Missing = 0;
		for (int32 A = 0; A < P.AzimuthCount; ++A)
		{
			const double Expected = P.HorizonElevationAt(H, A);
			double Measured = 0.0;
			if (!Silhouette.MaxElevationDeg(P.AzimuthDegAt(A), Measured))
			{
				++Missing;
				continue;
			}
			const double Difference = FMath::Abs(Measured - Expected);
			if (Difference > WorstAtSampleDeg)
			{
				WorstAtSampleDeg = Difference;
				WorstAzimuthIndex = A;
			}

			const double Next = P.HorizonElevationAt(H, (A + 1) % P.AzimuthCount);
			if (!Silhouette.MaxElevationDeg(P.AzimuthDegAt(A) + 0.5 * P.AzimuthStepDeg, Measured))
			{
				++Missing;
				continue;
			}
			const double Outside = FMath::Max3(0.0, FMath::Min(Expected, Next) - Measured, Measured - FMath::Max(Expected, Next));
			WorstBetweenDeg = FMath::Max(WorstBetweenDeg, Outside);
		}
		AddInfo(FString::Printf(TEXT("observer height %.1f m: silhouette minus package horizon, worst %.3g deg at azimuth index %d; between samples worst %.3g deg outside the neighbouring values; tolerance %.3f deg; %d azimuths"),
			P.ObserverHeightsM[H], WorstAtSampleDeg, WorstAzimuthIndex, WorstBetweenDeg, SilhouetteToleranceDeg, P.AzimuthCount));
		TestEqual(TEXT("azimuths at which no geometry was found"), Missing, 0);
		TestTrue(FString::Printf(TEXT("B: silhouette equals the package horizon at the samples (height index %d)"), H), WorstAtSampleDeg <= SilhouetteToleranceDeg);
		TestTrue(FString::Printf(TEXT("B: silhouette stays between neighbouring samples (height index %d)"), H), WorstBetweenDeg <= SilhouetteToleranceDeg);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
