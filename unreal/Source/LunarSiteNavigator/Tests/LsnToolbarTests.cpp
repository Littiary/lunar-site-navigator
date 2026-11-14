// Buttons on screen.
//
// Criteria, written before the first run:
//
// T. The main actions can be reached with the mouse alone.
//    For every screen size the planner is used at (1280 x 720, 1920 x 1080, 2560 x 1440,
//    3840 x 2160) and for the half-width views of a comparison (640 x 720, 960 x 1080):
//    1. every button lies wholly on the screen and is at least 22 px high and 60 px wide;
//    2. no two buttons overlap, and no button overlaps a time strip;
//    3. the time strips lie wholly on the screen, above the buttons;
//    4. a point in the middle of a button gives that button's action, and a point
//       outside all buttons gives none;
//    5. every button names an action the observer knows, and no action has two buttons.
//    The actions a planner needs first must have a button: play, a step and a day in both
//    directions, the next and previous rise or set of the Sun, the next site, two sites
//    side by side, the three planner pages, the obstacle view, the observer height, and help.
//
// U. A button does what its key does.
//    With the sample package in a scene, the named actions move the time by one sample and
//    by one day exactly, land on the first and last sample, and go round the observer heights
//    of the package. An unknown name is refused.

#include "Tests/LsnTestSupport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Scene/LsnHud.h"
#include "Scene/LsnObserverPawn.h"
#include "Scene/LsnSiteScene.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnToolbarLayoutTest, "LunarSiteNavigator.Planner.ButtonsOnScreen", LsnTest::Flags)
bool FLsnToolbarLayoutTest::RunTest(const FString& Parameters)
{
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const FVector2D Sizes[] = { { 1280, 720 }, { 1920, 1080 }, { 2560, 1440 }, { 3840, 2160 }, { 640, 720 }, { 960, 1080 } };
	for (const FVector2D& Size : Sizes)
	{
		const FString Where = FString::Printf(TEXT("%.0f x %.0f"), Size.X, Size.Y);
		const FLsnToolbar Toolbar = FLsnToolbar::Make(Size.X, Size.Y);
		const FLsnTimeStripLayout Strips = FLsnTimeStripLayout::Make(Size.X, Size.Y, P);
		const FBox2D Screen(FVector2D(0.0, 0.0), Size);
		TestTrue(Where + TEXT(": there are buttons"), Toolbar.Buttons.Num() > 0);
		TSet<FName> Seen;
		for (int32 I = 0; I < Toolbar.Buttons.Num(); ++I)
		{
			const FLsnButton& Button = Toolbar.Buttons[I];
			const FString Name = Where + TEXT(": ") + Button.Action.ToString();
			TestTrue(Name + TEXT(" lies on the screen"), Screen.IsInside(Button.Box.Min) && Screen.IsInside(Button.Box.Max));
			TestTrue(Name + TEXT(" is at least 22 px high"), Button.Box.Max.Y - Button.Box.Min.Y >= 22.0);
			TestTrue(Name + TEXT(" is at least 60 px wide"), Button.Box.Max.X - Button.Box.Min.X >= 60.0);
			TestFalse(Name + TEXT(" does not overlap the zoom strip"), Button.Box.Intersect(Strips.Zoom));
			TestFalse(Name + TEXT(" does not overlap the whole-range strip"), Button.Box.Intersect(Strips.WholeRange));
			for (int32 J = I + 1; J < Toolbar.Buttons.Num(); ++J)
			{
				// Shrunk by half a pixel: touching edges are not an overlap.
				TestFalse(Name + TEXT(" does not overlap ") + Toolbar.Buttons[J].Action.ToString(), Button.Box.ExpandBy(-0.5).Intersect(Toolbar.Buttons[J].Box.ExpandBy(-0.5)));
			}
			TestEqual(Name + TEXT(" is found at its middle"), Toolbar.ActionAt(Button.Box.GetCenter()), Button.Action);
			TestTrue(Name + TEXT(" is an action the observer knows"), ALsnObserverPawn::KnownActions().Contains(Button.Action));
			TestFalse(Name + TEXT(" has one button only"), Seen.Contains(Button.Action));
			Seen.Add(Button.Action);
			TestFalse(Name + TEXT(" has a label"), Button.Label.IsEmpty());
		}
		TestTrue(Where + TEXT(": the strips lie on the screen"), Screen.IsInside(Strips.Zoom.Min) && Screen.IsInside(Strips.Zoom.Max) && Screen.IsInside(Strips.WholeRange.Min) && Screen.IsInside(Strips.WholeRange.Max));
		TestTrue(Where + TEXT(": the strips are above the buttons"), Strips.Zoom.Max.Y < Strips.WholeRange.Min.Y && Strips.WholeRange.Max.Y < Toolbar.Top);
		TestTrue(Where + TEXT(": no action outside the buttons"), Toolbar.ActionAt(FVector2D(1.0, 1.0)).IsNone() && Toolbar.ActionAt(Strips.Zoom.GetCenter()).IsNone());
		for (const TCHAR* Needed : { TEXT("play"), TEXT("sample_back"), TEXT("sample_forward"), TEXT("day_back"), TEXT("day_forward"), TEXT("sun_event_back"), TEXT("sun_event_forward"),
			TEXT("next_site"), TEXT("compare"), TEXT("page_calendar"), TEXT("page_uncertainty"), TEXT("page_trade"), TEXT("obstacle"), TEXT("height_next"), TEXT("help") })
		{
			TestTrue(Where + TEXT(": there is a button for ") + Needed, Seen.Contains(Needed));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnNamedActionsTest, "LunarSiteNavigator.Planner.ButtonsDoWhatKeysDo", LsnTest::Flags)
bool FLsnNamedActionsTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->BeginPlay();
	ALsnSiteScene* Scene = World->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);
	ALsnObserverPawn* Pawn = World->SpawnActor<ALsnObserverPawn>(ALsnObserverPawn::StaticClass(), FTransform::Identity);
	FString Error;
	if (TestTrue(FString::Printf(TEXT("the scene loads the sample package (%s)"), *Error), Scene->LoadPackageDirectory(LsnTest::FixturePackageDir(TEXT("site")), Error)))
	{
		const FLsnSitePackage& P = Scene->GetPackage();
		const int32 Last = P.Time.Count - 1;
		const int32 PerDay = FMath::RoundToInt32(86400.0 / P.Time.StepS);
		Scene->SetTimeIndex(10);
		TestTrue(TEXT("sample_forward is known"), Pawn->DoAction(TEXT("sample_forward")));
		TestEqual(TEXT("one sample forward"), Scene->GetTimeIndex(), 11);
		Pawn->DoAction(TEXT("sample_back"));
		Pawn->DoAction(TEXT("sample_back"));
		TestEqual(TEXT("two samples back"), Scene->GetTimeIndex(), 9);
		if (9 + PerDay <= Last)
		{
			Pawn->DoAction(TEXT("day_forward"));
			TestEqual(TEXT("one day forward"), Scene->GetTimeIndex(), 9 + PerDay);
			Pawn->DoAction(TEXT("day_back"));
			TestEqual(TEXT("one day back"), Scene->GetTimeIndex(), 9);
		}
		Pawn->DoAction(TEXT("last_sample"));
		TestEqual(TEXT("last sample"), Scene->GetTimeIndex(), Last);
		Pawn->DoAction(TEXT("sample_forward"));
		TestEqual(TEXT("no step past the last sample"), Scene->GetTimeIndex(), Last);
		Pawn->DoAction(TEXT("first_sample"));
		TestEqual(TEXT("first sample"), Scene->GetTimeIndex(), 0);
		Pawn->DoAction(TEXT("sample_back"));
		TestEqual(TEXT("no step before the first sample"), Scene->GetTimeIndex(), 0);

		const int32 Heights = P.NumHeights();
		const int32 Start = Scene->GetHeightIndex();
		for (int32 I = 1; I <= Heights; ++I)
		{
			Pawn->DoAction(TEXT("height_next"));
			TestEqual(TEXT("the observer heights go round"), Scene->GetHeightIndex(), (Start + I) % Heights);
		}
		TestFalse(TEXT("not playing at first"), Pawn->IsPlaying());
		Pawn->DoAction(TEXT("play"));
		TestTrue(TEXT("play starts the timeline"), Pawn->IsPlaying());
		Pawn->DoAction(TEXT("sample_forward"));
		TestFalse(TEXT("a step stops the playing"), Pawn->IsPlaying());
		const bool bObstacle = Scene->IsObstacleViewEnabled();
		Pawn->DoAction(TEXT("obstacle"));
		TestEqual(TEXT("the obstacle view switches"), Scene->IsObstacleViewEnabled(), !bObstacle);
		TestFalse(TEXT("an unknown name is refused"), Pawn->DoAction(TEXT("no_such_action")));
		for (const FName& Action : ALsnObserverPawn::KnownActions())
		{
			if (Action != TEXT("quit"))
			{
				TestTrue(FString::Printf(TEXT("%s is carried out without a game mode"), *Action.ToString()), Pawn->DoAction(Action));
			}
		}
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
