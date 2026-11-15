// The zenith fill comes and goes softly.
//
// Criteria, written on 15 November 2026 before the change (the fill went from 0 to lsn.Look.FillLux in one
// frame when the package's Sun went hidden, and back in one frame when it rose; it looked like a fault):
//
// F1. When the target changes (a time jump to a sample with the Sun hidden), the fill's intensity does not
//     jump: right after the change it is still within 2 % of lsn.Look.FillLux of where it was; at 60
//     frames a second no frame changes it by more than 2.5 % of FillLux; after 0.75 s it is between 40 and
//     60 %, after 1.5 s it is at FillLux (within 0.5 %): an ease-in-out over about 1.5 s of real time.
// F2. The same at 20 frames a second: after 0.75 s within 2 % of FillLux of the 60 frames a second value
//     (independent of the frame rate).
// F3. Going out (a time jump to a sample with the Sun visible) is as soft; after 1.5 s the fill is off.
// F4. With the transition instant (as for -LsnShot, -LsnBench and the automation tests), the fill is at
//     its target at once: FillLux on a sample with the Sun hidden, off on one with the Sun visible.
// The rule, the level and the colour of the fill stay those of 0b1cb68 (LsnEarthshineTests.cpp, N3).

#include "Tests/LsnTestSupport.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Scene/LsnLook.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnFillTest
{
	/** Runs the fill transition for Seconds at Fps frames a second; returns the largest change in one frame. */
	float Run(ALsnSiteScene* Scene, double Seconds, double Fps)
	{
		float Largest = 0.0f;
		const int32 Frames = FMath::RoundToInt(Seconds * Fps);
		for (int32 Frame = 0; Frame < Frames; ++Frame)
		{
			const float Before = Scene->GetFillLight()->Intensity;
			Scene->AdvanceFillTransition(static_cast<float>(1.0 / Fps));
			Largest = FMath::Max(Largest, FMath::Abs(Scene->GetFillLight()->Intensity - Before));
		}
		return Largest;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFillTransitionTest, "LunarSiteNavigator.FillLight.SoftTransition", LsnTest::Flags)
bool FLsnFillTransitionTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->BeginPlay();
	ALsnSiteScene* Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
	FString Error;
	if (TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error), Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		int32 Hidden = INDEX_NONE, Visible = INDEX_NONE;
		for (int32 Index = 0; Index < Scene->GetPackage().Time.Count; ++Index)
		{
			Scene->SetTimeIndex(Index);
			const double Share = Scene->GetSunVisibleFraction();
			if (Share <= 0.0 && Hidden == INDEX_NONE) { Hidden = Index; }
			if (Share > 0.0 && Visible == INDEX_NONE) { Visible = Index; }
		}
		if (TestTrue(FString::Printf(TEXT("the sample package has samples with the Sun hidden (%d) and visible (%d)"), Hidden, Visible), Hidden != INDEX_NONE && Visible != INDEX_NONE))
		{
			const float Lux = LsnLook::FillLux.GetValueOnGameThread();
			UDirectionalLightComponent* Fill = Scene->GetFillLight();
			float Level[2] = { 0.0f, 0.0f };
			for (int32 Pass = 0; Pass < 2; ++Pass)
			{
				const double Fps = Pass == 0 ? 60.0 : 20.0;
				Scene->SetFillTransitionInstant(false);
				Scene->SetTimeIndex(Visible);
				LsnFillTest::Run(Scene, 2.0, Fps);
				const float Start = Fill->IsVisible() ? Fill->Intensity : 0.0f;
				Scene->SetTimeIndex(Hidden);
				const float AfterJump = Fill->IsVisible() ? Fill->Intensity : 0.0f;
				TestTrue(FString::Printf(TEXT("F1 (%.0f fps): no jump at the change (%.3f -> %.3f of %.3f)"), Fps, Start, AfterJump, Lux), FMath::Abs(AfterJump - Start) <= 0.02f * Lux);
				const float StepIn = LsnFillTest::Run(Scene, 0.75, Fps);
				Level[Pass] = Fill->Intensity;
				if (Pass == 0)
				{
					TestTrue(FString::Printf(TEXT("F1: no frame changes the fill by more than 2.5 %% (largest %.2f %%)"), 100.0f * StepIn / Lux), StepIn <= 0.025f * Lux);
					TestTrue(FString::Printf(TEXT("F1: between 40 and 60 %% after 0.75 s (%.1f %%)"), 100.0f * Level[0] / Lux), Level[0] >= 0.4f * Lux && Level[0] <= 0.6f * Lux);
				}
				LsnFillTest::Run(Scene, 0.75, Fps);
				TestTrue(FString::Printf(TEXT("F1 (%.0f fps): at FillLux after 1.5 s (%.3f of %.3f)"), Fps, Fill->Intensity, Lux), Fill->IsVisible() && FMath::Abs(Fill->Intensity - Lux) <= 0.005f * Lux);
				// F3: out again.
				Scene->SetTimeIndex(Visible);
				TestTrue(FString::Printf(TEXT("F3 (%.0f fps): no drop at the change (%.3f)"), Fps, Fill->Intensity), Fill->IsVisible() && Fill->Intensity >= 0.98f * Lux);
				const float StepOut = LsnFillTest::Run(Scene, 1.5, Fps);
				if (Pass == 0)
				{
					TestTrue(FString::Printf(TEXT("F3: no frame changes the fill by more than 2.5 %% going out (largest %.2f %%)"), 100.0f * StepOut / Lux), StepOut <= 0.025f * Lux);
				}
				LsnFillTest::Run(Scene, 1.0 / Fps, Fps);
				TestFalse(FString::Printf(TEXT("F3 (%.0f fps): off after 1.5 s"), Fps), Fill->IsVisible());
			}
			TestTrue(FString::Printf(TEXT("F2: 20 fps within 2 %% of 60 fps after 0.75 s (%.3f, %.3f)"), Level[1], Level[0]), FMath::Abs(Level[1] - Level[0]) <= 0.02f * Lux);

			Scene->SetFillTransitionInstant(true);
			Scene->SetTimeIndex(Hidden);
			TestTrue(TEXT("F4: instant, at FillLux at once"), Fill->IsVisible() && FMath::Abs(Fill->Intensity - Lux) <= 0.005f * Lux);
			Scene->SetTimeIndex(Visible);
			TestFalse(TEXT("F4: instant, off at once"), Fill->IsVisible());
		}
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
