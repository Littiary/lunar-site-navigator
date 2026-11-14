// Buttons on screen.
//
// Criteria, written before the first run:
//
// T. The main actions can be reached with the mouse alone, and the three main ones stand out.
//    (Revised on 2026-11-14 for the product-screen layout, before its first run: the buttons
//    are laid out in window coordinates, in labelled groups, with three main actions.)
//    For the window sizes 1280 x 720, 1920 x 1080, 2560 x 1440 and 3840 x 2160, each as one
//    view and as two views side by side:
//    1. every button lies wholly in the window and is at least 22 px high and 60 px wide;
//    2. no two buttons overlap, and no button overlaps a time strip of a view;
//    3. the time strips of a view lie below the header and above the bar of grouped buttons;
//    4. a point in the middle of a button gives that button's action, and a point outside
//       all buttons gives none;
//    5. every button names an action the observer knows, no action has two buttons, every
//       button has a label, and every button of the bar belongs to a labelled group;
//    6. the three main actions (two sites side by side, jump to the next sunset, show what
//       blocks the Sun) are marked as main and each covers at least twice the area of the
//       largest other button;
//    7. side by side: no button lies across the middle of the window; the control of the
//       right view (its next site) lies wholly in the right half and exists only side by
//       side; the main actions lie in the left half.
//    The actions a planner needs first must have a button: play, a step and a day in both
//    directions, the next and previous rise or set of the Sun, the site list (it replaced
//    "next site" on 2026-11-14, when the list of sites grew), the three planner pages, the
//    observer height, the details and help.
//
// U. A button does what its key does.
//    With the sample package in a scene, the named actions move the time by one sample and
//    by one day exactly, land on the first and last sample, and go round the observer heights
//    of the package; the next sunset is the package's next "set" event of the Sun, exactly
//    (1e-6 s); the details open and close. An unknown name is refused.

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
	const FVector2D Sizes[] = { { 1280, 720 }, { 1920, 1080 }, { 2560, 1440 }, { 3840, 2160 } };
	for (const FVector2D& Size : Sizes)
	{
		for (const bool bComparing : { false, true })
		{
			const FString Where = FString::Printf(TEXT("%.0f x %.0f%s"), Size.X, Size.Y, bComparing ? TEXT(" side by side") : TEXT(""));
			const FLsnToolbar Toolbar = FLsnToolbar::Make(Size.X, Size.Y, bComparing);
			const FBox2D Window(FVector2D(0.0, 0.0), Size);
			const double Middle = 0.5 * Size.X;
			// The strips of each view, moved to window coordinates.
			const int32 Views = bComparing ? 2 : 1;
			const double ViewWidth = Size.X / Views;
			TArray<FBox2D> Strips;
			for (int32 View = 0; View < Views; ++View)
			{
				const FLsnTimeStripLayout Layout = FLsnTimeStripLayout::Make(ViewWidth, Size.Y, P);
				const FVector2D Shift(View * ViewWidth, 0.0);
				Strips.Add(FBox2D(Layout.Zoom.Min + Shift, Layout.Zoom.Max + Shift));
				Strips.Add(FBox2D(Layout.WholeRange.Min + Shift, Layout.WholeRange.Max + Shift));
				TestTrue(Where + TEXT(": the strips lie below the header"), Layout.Zoom.Min.Y > Toolbar.HeaderBottom);
				TestTrue(Where + TEXT(": the strips lie above the bar"), Layout.Zoom.Max.Y < Layout.WholeRange.Min.Y && Layout.WholeRange.Max.Y < Toolbar.Top);
			}
			TestTrue(Where + TEXT(": there are buttons"), Toolbar.Buttons.Num() > 0);
			TSet<FName> Seen;
			double LargestOther = 0.0, SmallestMain = TNumericLimits<double>::Max();
			int32 MainCount = 0;
			for (int32 I = 0; I < Toolbar.Buttons.Num(); ++I)
			{
				const FLsnButton& Button = Toolbar.Buttons[I];
				const FString Name = Where + TEXT(": ") + Button.Action.ToString();
				TestTrue(Name + TEXT(" lies in the window"), Window.IsInside(Button.Box.Min) && Window.IsInside(Button.Box.Max));
				TestTrue(Name + TEXT(" is at least 22 px high"), Button.Box.Max.Y - Button.Box.Min.Y >= 22.0);
				TestTrue(Name + TEXT(" is at least 60 px wide"), Button.Box.Max.X - Button.Box.Min.X >= 60.0);
				for (const FBox2D& Strip : Strips)
				{
					TestFalse(Name + TEXT(" does not overlap a time strip"), Button.Box.Intersect(Strip));
				}
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
				const double Area = (Button.Box.Max.X - Button.Box.Min.X) * (Button.Box.Max.Y - Button.Box.Min.Y);
				if (Button.Style == ELsnButtonStyle::Main)
				{
					++MainCount;
					SmallestMain = FMath::Min(SmallestMain, Area);
					TestTrue(Name + TEXT(" (main) lies in the left half when side by side"), !bComparing || Button.Box.Max.X <= Middle);
				}
				else
				{
					LargestOther = FMath::Max(LargestOther, Area);
				}
				if (Button.Style == ELsnButtonStyle::Bar)
				{
					TestFalse(Name + TEXT(" belongs to a labelled group"), Button.Group.IsEmpty());
				}
				if (bComparing)
				{
					TestTrue(Name + TEXT(" does not lie across the middle"), Button.Box.Max.X <= Middle + 0.5 || Button.Box.Min.X >= Middle - 0.5);
				}
			}
			TestEqual(Where + TEXT(": three main actions"), MainCount, 3);
			for (const TCHAR* Main : { TEXT("compare"), TEXT("next_sunset"), TEXT("obstacle") })
			{
				const FLsnButton* Button = Toolbar.Buttons.FindByPredicate([Main](const FLsnButton& B) { return B.Action == Main; });
				TestTrue(Where + TEXT(": ") + Main + TEXT(" is a main action"), Button && Button->Style == ELsnButtonStyle::Main);
			}
			TestTrue(Where + FString::Printf(TEXT(": the main actions are at least twice as large as any other button (%.0f against %.0f px2)"), SmallestMain, LargestOther), SmallestMain >= 2.0 * LargestOther);
			const FLsnButton* RightSite = Toolbar.Buttons.FindByPredicate([](const FLsnButton& B) { return B.Action == TEXT("next_right_site"); });
			TestEqual(Where + TEXT(": the right view's control exists only side by side"), RightSite != nullptr, bComparing);
			if (RightSite)
			{
				TestTrue(Where + TEXT(": the right view's control lies in the right half"), RightSite->Box.Min.X >= Middle);
			}
			TestTrue(Where + TEXT(": no action outside the buttons"), Toolbar.ActionAt(FVector2D(1.0, 0.5 * Size.Y)).IsNone() && Toolbar.ActionAt(Strips[0].GetCenter()).IsNone());
			for (const TCHAR* Needed : { TEXT("play"), TEXT("sample_back"), TEXT("sample_forward"), TEXT("day_back"), TEXT("day_forward"), TEXT("sun_event_back"), TEXT("sun_event_forward"),
				TEXT("page_sites"), TEXT("page_calendar"), TEXT("page_uncertainty"), TEXT("page_trade"), TEXT("height_next"), TEXT("details"), TEXT("help") })
			{
				TestTrue(Where + TEXT(": there is a button for ") + Needed, Seen.Contains(Needed));
			}
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
		// The next sunset is the package's next event of type "set" of the Sun for this height.
		Scene->SetTimeIndex(0);
		const int32 H = Scene->GetHeightIndex();
		double NextSetEtS = TNumericLimits<double>::Max();
		for (const FLsnEvent& Event : P.Events)
		{
			if (Event.Body == TEXT("SUN") && Event.Type == TEXT("set") && Event.HeightIndex == H && Event.EtS > P.Time.StartEtS)
			{
				NextSetEtS = FMath::Min(NextSetEtS, Event.EtS);
			}
		}
		Pawn->DoAction(TEXT("next_sunset"));
		if (NextSetEtS < TNumericLimits<double>::Max())
		{
			TestEqual(TEXT("next sunset: the time of the package's next set event of the Sun"), P.EtOfPosition(Scene->GetTimePosition()), NextSetEtS, 1e-6);
		}
		else
		{
			TestEqual(TEXT("no set event in the package: the time stays"), Scene->GetTimePosition(), 0.0);
		}
		TestFalse(TEXT("details closed at first"), Pawn->AreDetailsShown());
		Pawn->DoAction(TEXT("details"));
		TestTrue(TEXT("details open"), Pawn->AreDetailsShown());
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
