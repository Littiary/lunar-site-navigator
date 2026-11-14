// Time slider and countdowns.
//
// Criteria and tolerances, written before the first run:
//
// C. Countdowns come from the package.
//    The time to the next set (or rise) of a body is the difference between the
//    selected time and an interval boundary of the package window "<body>_visible"
//    for the selected observer height. The scene finds no rise or set of its own.
//    On a hand-made window the countdown is exact (1e-9 s). A countdown is marked
//    as a lower bound when the package has no such event inside its computed range.
//    Where a package carries the metric "<body>_time_to_set_s" (counted from the
//    start of the range), the countdown at the first sample equals it within 1e-3 s.
//
// D. The slider follows the package.
//    At a whole sample position the scene is identical to SetTimeIndex (0 deg).
//    Between two samples the light and the discs show the linear interpolation of
//    the package's azimuth, elevation and angular radius series (the azimuth along
//    the shorter way round), within 0.001 deg. This is display interpolation of
//    package values over one time step, not an ephemeris.

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnSliderTest
{
	constexpr double CountdownToleranceS = 1e-9;
	constexpr double MetricToleranceS = 1e-3;
	constexpr double DirectionToleranceDeg = 0.001;

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

	/** A package with one hand-made visibility window: time axis 0 .. 500 s in steps of 10 s. */
	inline FLsnSitePackage HandMadePackage(bool bClippedEnd)
	{
		FLsnSitePackage P;
		P.bHasTimeline = true;
		P.ObserverHeightsM = { 0.0, 2.0 };
		P.Time.StartEtS = 0.0;
		P.Time.StepS = 10.0;
		P.Time.Count = 51;
		FLsnWindow W;
		W.Id = TEXT("sun_visible");
		W.Subject = TEXT("SUN");
		W.HeightIndex = 1;
		W.Method = TEXT("timeline.windows");
		W.StartsEtS = { 100.0, 300.0 };
		W.EndsEtS = { 200.0, bClippedEnd ? 500.0 : 400.0 };
		W.StartsUtc = { TEXT("start-1"), TEXT("start-2") };
		W.EndsUtc = { TEXT("end-1"), TEXT("end-2") };
		W.bClippedEnd = bClippedEnd;
		P.Windows.Add(W);
		return P;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnCountdownHandMadeTest, "LunarSiteNavigator.Package.CountdownFromWindows", LsnTest::Flags)
bool FLsnCountdownHandMadeTest::RunTest(const FString& Parameters)
{
	using namespace LsnSliderTest;
	const FLsnSitePackage P = HandMadePackage(false);

	FLsnCountdown C = P.CountdownAt(TEXT("SUN"), 1, 150.0);
	TestTrue(TEXT("150 s: available"), C.bAvailable);
	TestTrue(TEXT("150 s: visible"), C.bVisibleNow);
	TestEqual(TEXT("150 s: sets in 50 s"), C.SecondsToChange, 50.0, CountdownToleranceS);
	TestFalse(TEXT("150 s: not a lower bound"), C.bLowerBound);
	TestEqual(TEXT("150 s: UTC of the set is the package string"), C.ChangeUtc, FString(TEXT("end-1")));
	TestEqual(TEXT("150 s: method of the window"), C.Method, FString(TEXT("timeline.windows")));

	C = P.CountdownAt(TEXT("SUN"), 1, 250.0);
	TestFalse(TEXT("250 s: not visible"), C.bVisibleNow);
	TestEqual(TEXT("250 s: rises in 50 s"), C.SecondsToChange, 50.0, CountdownToleranceS);
	TestFalse(TEXT("250 s: not a lower bound"), C.bLowerBound);
	TestEqual(TEXT("250 s: UTC of the rise"), C.ChangeUtc, FString(TEXT("start-2")));

	// An interval is closed at its start and open at its end.
	TestTrue(TEXT("100 s: visible from the first instant"), P.CountdownAt(TEXT("SUN"), 1, 100.0).bVisibleNow);
	TestFalse(TEXT("200 s: no longer visible at the end"), P.CountdownAt(TEXT("SUN"), 1, 200.0).bVisibleNow);

	C = P.CountdownAt(TEXT("SUN"), 1, 450.0);
	TestFalse(TEXT("450 s: not visible"), C.bVisibleNow);
	TestTrue(TEXT("450 s: no rise in the range, lower bound"), C.bLowerBound);
	TestEqual(TEXT("450 s: at least to the end of the range"), C.SecondsToChange, 50.0, CountdownToleranceS);

	C = P.CountdownAt(TEXT("SUN"), 1, 50.0);
	TestFalse(TEXT("50 s: not visible before the first interval"), C.bVisibleNow);
	TestEqual(TEXT("50 s: rises in 50 s"), C.SecondsToChange, 50.0, CountdownToleranceS);

	const FLsnSitePackage Clipped = HandMadePackage(true);
	C = Clipped.CountdownAt(TEXT("SUN"), 1, 350.0);
	TestTrue(TEXT("clipped: visible"), C.bVisibleNow);
	TestTrue(TEXT("clipped: the set lies beyond the range, lower bound"), C.bLowerBound);
	TestEqual(TEXT("clipped: at least 150 s"), C.SecondsToChange, 150.0, CountdownToleranceS);

	TestFalse(TEXT("another height has no window: not available"), P.CountdownAt(TEXT("SUN"), 0, 150.0).bAvailable);
	TestFalse(TEXT("another body has no window: not available"), P.CountdownAt(TEXT("EARTH"), 1, 150.0).bAvailable);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnCountdownSampleTest, "LunarSiteNavigator.Package.WindowsOfTheSample", LsnTest::Flags)
bool FLsnCountdownSampleTest::RunTest(const FString& Parameters)
{
	using namespace LsnSliderTest;
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const double EndEtS = P.Time.StartEtS + P.Time.StepS * (P.Time.Count - 1);
	for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
	{
		for (int32 H = 0; H < P.NumHeights(); ++H)
		{
			const FLsnWindow* W = P.FindWindow(FString(Body).ToLower() + TEXT("_visible"), H);
			if (!TestNotNull(*FString::Printf(TEXT("%s_visible window of height %d"), Body, H), W))
			{
				continue;
			}
			TestEqual(TEXT("as many starts as ends"), W->StartsEtS.Num(), W->EndsEtS.Num());
			TestEqual(TEXT("a UTC string per start"), W->StartsUtc.Num(), W->StartsEtS.Num());
			for (int32 I = 0; I < W->StartsEtS.Num(); ++I)
			{
				TestTrue(TEXT("interval has positive length"), W->EndsEtS[I] > W->StartsEtS[I]);
				TestTrue(TEXT("interval inside the time axis"), W->StartsEtS[I] >= P.Time.StartEtS - 1e-6 && W->EndsEtS[I] <= EndEtS + 1e-6);
				if (I > 0)
				{
					TestTrue(TEXT("intervals sorted and disjoint"), W->StartsEtS[I] > W->EndsEtS[I - 1]);
				}
			}
			// The window and the series are two fields of the package for the same thing:
			// away from an event, a sample is inside the window exactly when the series says visible.
			// The threshold of the Sun is "any part visible", of the Earth "centre above the horizon".
			const FLsnBodySeries* S = P.FindSeries(Body);
			int32 Disagreements = 0;
			for (int32 T = 0; S && T < P.Time.Count; ++T)
			{
				const int32 Flat = H * P.Time.Count + T;
				const bool bSeriesVisible = FString(Body) == TEXT("SUN") ? S->VisibleFraction[Flat] > 0.0f : S->MarginDeg[Flat] > 0.0f;
				const FLsnCountdown C = P.CountdownAt(Body, H, P.Time.StartEtS + P.Time.StepS * T);
				if (C.bAvailable && C.bVisibleNow != bSeriesVisible)
				{
					++Disagreements;
				}
			}
			TestEqual(*FString::Printf(TEXT("%s height %d: samples where the window and the series disagree"), Body, H), Disagreements, 0);

			// Where the package carries the countdown metric, the countdown at the start equals it.
			const FLsnMetric* ToSet = P.FindMetric(FString(Body).ToLower() + TEXT("_time_to_set_s"), H);
			if (ToSet && ToSet->bHasValue)
			{
				const FLsnCountdown C = P.CountdownAt(Body, H, P.Time.StartEtS);
				if (C.bVisibleNow)
				{
					TestEqual(*FString::Printf(TEXT("%s height %d: countdown at the start equals the package metric"), Body, H), C.SecondsToChange, ToSet->Value, MetricToleranceS);
				}
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnSliderSceneTest, "LunarSiteNavigator.Acceptance.SliderFollowsThePackage", LsnTest::Flags)
bool FLsnSliderSceneTest::RunTest(const FString& Parameters)
{
	using namespace LsnSliderTest;
	FSceneFixture Fixture;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error),
		Fixture.Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		return false;
	}
	ALsnSiteScene& Scene = *Fixture.Scene;
	const FLsnSitePackage& P = Scene.GetPackage();
	const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
	const FLsnBodySeries* Earth = P.FindSeries(TEXT("EARTH"));
	if (!TestNotNull(TEXT("Sun series"), Sun) || !TestNotNull(TEXT("Earth series"), Earth))
	{
		return false;
	}

	auto Lerp = [](const FLsnBodySeries& S, int32 T, double F, double& Az, double& El, double& Radius)
	{
		const double DeltaAz = FMath::Fmod(static_cast<double>(S.AzimuthDeg[T + 1]) - S.AzimuthDeg[T] + 540.0, 360.0) - 180.0;
		Az = S.AzimuthDeg[T] + F * DeltaAz;
		El = (1.0 - F) * S.ElevationDeg[T] + F * S.ElevationDeg[T + 1];
		Radius = (1.0 - F) * S.AngularRadiusDeg[T] + F * S.AngularRadiusDeg[T + 1];
	};
	auto DiscDirection = [&Scene](const UProceduralMeshComponent* Disc) { return Disc->GetComponentLocation() - Scene.GetEyeUnreal(); };
	auto DiscRadiusDeg = [&](const UProceduralMeshComponent* Disc)
	{
		return FMath::RadiansToDegrees(FMath::Asin(Disc->GetComponentScale().X / DiscDirection(Disc).Size()));
	};

	double WorstWholeDeg = 0.0, WorstLightDeg = 0.0, WorstSunDeg = 0.0, WorstEarthDeg = 0.0, WorstRadiusDeg = 0.0;
	int32 Tested = 0;
	for (int32 T = 0; T + 1 < P.Time.Count; T += 7)
	{
		// Whole position: the same as SetTimeIndex.
		TestTrue(TEXT("index accepted"), Scene.SetTimeIndex(T));
		const FVector LightAtIndex = Scene.GetSunDirectionFromLight();
		const FVector SunAtIndex = DiscDirection(Scene.GetSunDisc());
		TestTrue(TEXT("position accepted"), Scene.SetTimePosition(static_cast<double>(T)));
		WorstWholeDeg = FMath::Max3(WorstWholeDeg, LsnTest::AngleDeg(LightAtIndex, Scene.GetSunDirectionFromLight()), LsnTest::AngleDeg(SunAtIndex, DiscDirection(Scene.GetSunDisc())));
		TestEqual(TEXT("whole position reports its sample"), Scene.GetTimeIndex(), T);

		for (const double F : { 0.25, 0.5, 0.9 })
		{
			TestTrue(TEXT("fractional position accepted"), Scene.SetTimePosition(T + F));
			double Az = 0.0, El = 0.0, Radius = 0.0;
			Lerp(*Sun, T, F, Az, El, Radius);
			const FVector ExpectedSun = FLsnSiteFrame::AzElToUnrealDir(Az, El);
			WorstLightDeg = FMath::Max(WorstLightDeg, LsnTest::AngleDeg(Scene.GetSunDirectionFromLight(), ExpectedSun));
			WorstSunDeg = FMath::Max(WorstSunDeg, LsnTest::AngleDeg(DiscDirection(Scene.GetSunDisc()), ExpectedSun));
			WorstRadiusDeg = FMath::Max3(WorstRadiusDeg, FMath::Abs(DiscRadiusDeg(Scene.GetSunDisc()) - Radius), FMath::Abs(0.5 * Scene.GetSunLight()->LightSourceAngle - Radius));
			Lerp(*Earth, T, F, Az, El, Radius);
			WorstEarthDeg = FMath::Max(WorstEarthDeg, LsnTest::AngleDeg(DiscDirection(Scene.GetEarthDisc()), FLsnSiteFrame::AzElToUnrealDir(Az, El)));
			WorstRadiusDeg = FMath::Max(WorstRadiusDeg, FMath::Abs(DiscRadiusDeg(Scene.GetEarthDisc()) - Radius));
			TestEqual(TEXT("time position is kept"), Scene.GetTimePosition(), T + F, 1e-12);
			++Tested;
		}
	}
	AddInfo(FString::Printf(TEXT("%d positions between samples: light %.3g deg, Sun disc %.3g deg, Earth disc %.3g deg, angular radii %.3g deg from the interpolated package series; whole positions %.3g deg from SetTimeIndex (tolerance %.3f deg)"),
		Tested, WorstLightDeg, WorstSunDeg, WorstEarthDeg, WorstRadiusDeg, WorstWholeDeg, DirectionToleranceDeg));
	TestTrue(TEXT("D: whole positions equal SetTimeIndex"), WorstWholeDeg <= 1e-9);
	TestTrue(TEXT("D: light follows the interpolated series"), WorstLightDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("D: Sun disc follows the interpolated series"), WorstSunDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("D: Earth disc follows the interpolated series"), WorstEarthDeg <= DirectionToleranceDeg);
	TestTrue(TEXT("D: angular radii follow the interpolated series"), WorstRadiusDeg <= DirectionToleranceDeg);

	// Outside the time axis nothing is shown that the package does not have.
	TestFalse(TEXT("a position before the first sample is refused"), Scene.SetTimePosition(-0.5));
	TestFalse(TEXT("a position after the last sample is refused"), Scene.SetTimePosition(P.Time.Count - 1 + 0.5));
	TestTrue(TEXT("the last sample itself is accepted"), Scene.SetTimePosition(static_cast<double>(P.Time.Count - 1)));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
