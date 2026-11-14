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
//    8. (Added on 2026-11-14, before its first run: the clean view became the default.)
//       Without "all controls" the window holds the three main actions and one button that
//       opens the rest, and nothing else (side by side also the right view's control);
//       criteria 1 to 7 hold for that layout too. The box of "look at the Sun", shown while
//       the Sun is outside the frame, lies in the window, in the left half side by side, and
//       overlaps no button and no time strip in either layout.
//    9. (Added on 2026-11-14, before its first run.) With all controls open there are also
//       buttons for the composed camera positions, for playing the first lunar day after
//       the planned landing, and for the arrival camera move.
//    The actions a planner needs first must have a button (with all controls open): play, a step and a day in both
//    directions, the next and previous rise or set of the Sun, the site list (it replaced
//    "next site" on 2026-11-14, when the list of sites grew), the three planner pages, the
//    observer height, the details and help.
//
// T2. (Revision of 14 November 2026 for the interface pass, written before its first run.
//    It replaces criteria T.1 to T.9 above: the brief of that pass replaced the three large
//    main buttons and the bar of grouped buttons by a control bar at the bottom left, one
//    time strip in a panel, and a drawer from the right. What a button must be able to do
//    did not change.)
//    For the windows 1280 x 720, 1920 x 1080 and 2560 x 1440, each as one view and side by
//    side, with the drawer closed, open on a page, and open on its tab of further controls:
//    1. every button lies inside the safe margin (48 px at a height of 1080, scaled with the
//       height) and is at least 22 px high and 44 px wide;
//    2. no two buttons overlap, and no button overlaps the panel of the time strip;
//    3. the panel of the time strip lies inside the safe margin and below the header, and the
//       strip lies inside its panel;
//    4. a point in the middle of a button gives that button's action, a point outside none;
//    5. every button names an action the observer knows, no action has two buttons, every
//       button has a label;
//    6. the control bar holds exactly play, next sunset, obstacle, compare, camera and the
//       button that opens the rest, all left of the strip's panel and in the bottom row;
//    7. "next site" exists for each half side by side, each in its half, and not in one view;
//    8. with the drawer closed there are no other buttons. The drawer lies inside the safe
//       margin, between the header and the bottom row; in one view it lies wholly right of
//       the middle of the window (the centre of the view stays free); its tabs and the
//       further controls lie inside it, and every further control belongs to a labelled group;
//    9. "look at the Sun" lies inside the safe margin, in the left half side by side, and
//       overlaps no button, not the strip's panel and not the drawer.
//    With the tab of further controls open, the actions a planner needs have a button: play,
//    a step and a day in both directions, the next and previous rise or set of the Sun, the
//    site list, the three pages, the observer height, the evidence (details), help, the
//    camera positions, the first lunar day and the arrival view.
//
// U. A button does what its key does.
//    With the sample package in a scene, the named actions move the time by one sample and
//    by one day exactly, land on the first and last sample, and go round the observer heights
//    of the package; the next sunset is the package's next "set" event of the Sun, exactly
//    (1e-6 s); the details open and close. An unknown name is refused.
//    (Added on 2026-11-14, before its first run.) "camera" goes round the observer's view,
//    the view near the lander and the wide view, and only the first is the observer's view.
//    "first_day" puts the time on the planned landing of the package (its slip report) and
//    plays one lunar day of the package's calendar from there: the time is the landing
//    within 1e-6 s, the timeline is playing, and it stops within one sample of the landing
//    plus the length of the first complete calendar period. Without a planned landing or a
//    calendar nothing happens. "arrival" starts the camera move and marks the view as not
//    the observer's.

#include "Tests/LsnTestSupport.h"
#include "Algo/AnyOf.h"
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
	const FVector2D Sizes[] = { { 1280, 720 }, { 1920, 1080 }, { 2560, 1440 } };
	for (const FVector2D& Size : Sizes)
	{
		for (int32 Variant = 0; Variant < 6; ++Variant)
		{
			const bool bComparing = (Variant & 1) != 0;
			const int32 Drawer = Variant / 2;   // 0 closed, 1 open on a page, 2 open on the further controls
			const FString Where = FString::Printf(TEXT("%.0f x %.0f%s%s"), Size.X, Size.Y, bComparing ? TEXT(" side by side") : TEXT(""), Drawer == 0 ? TEXT(", drawer closed") : Drawer == 1 ? TEXT(", drawer on a page") : TEXT(", further controls"));
			const FLsnToolbar Toolbar = FLsnToolbar::Make(Size.X, Size.Y, bComparing, Drawer > 0, Drawer == 2);
			const FLsnTimeStripLayout Strip = FLsnTimeStripLayout::Make(Size.X, Size.Y, P, bComparing);
			const double Safe = 48.0 * Size.Y / 1080.0, Middle = 0.5 * Size.X;
			// Half a pixel of slack for rounding.
			const FBox2D SafeArea(FVector2D(Safe - 0.5, Safe - 0.5), FVector2D(Size.X - Safe + 0.5, Size.Y - Safe + 0.5));
			const FBox2D DrawerBox = FLsnToolbar::DrawerBox(Size.X, Size.Y, bComparing);
			auto Inside = [](const FBox2D& Outer, const FBox2D& Inner) { return Outer.IsInside(Inner.Min) && Outer.IsInside(Inner.Max); };

			TestTrue(Where + TEXT(": the strip's panel lies inside the safe margin"), Inside(SafeArea, Strip.Panel));
			TestTrue(Where + TEXT(": the strip's panel lies below the header"), Strip.Panel.Min.Y > Toolbar.HeaderBottom);
			TestTrue(Where + TEXT(": the strip lies inside its panel"), Inside(Strip.Panel, Strip.Zoom));
			TestTrue(Where + TEXT(": the drawer lies inside the safe margin"), Inside(SafeArea, DrawerBox));
			TestTrue(Where + TEXT(": the drawer lies between the header and the bottom row"), DrawerBox.Min.Y > Toolbar.HeaderBottom && DrawerBox.Max.Y < Strip.Panel.Min.Y);
			TestTrue(Where + TEXT(": in one view the drawer leaves the middle of the window free"), bComparing || DrawerBox.Min.X > Middle);

			static const TCHAR* BarActions[] = { TEXT("play"), TEXT("next_sunset"), TEXT("obstacle"), TEXT("compare"), TEXT("camera"), TEXT("controls") };
			TSet<FName> Seen;
			int32 BarCount = 0;
			for (int32 I = 0; I < Toolbar.Buttons.Num(); ++I)
			{
				const FLsnButton& Button = Toolbar.Buttons[I];
				const FString Name = Where + TEXT(": ") + Button.Action.ToString();
				TestTrue(Name + TEXT(" lies inside the safe margin"), Inside(SafeArea, Button.Box));
				TestTrue(Name + TEXT(" is at least 22 px high"), Button.Box.Max.Y - Button.Box.Min.Y >= 22.0);
				TestTrue(Name + TEXT(" is at least 44 px wide"), Button.Box.Max.X - Button.Box.Min.X >= 44.0);
				TestFalse(Name + TEXT(" does not overlap the strip's panel"), Button.Box.ExpandBy(-0.5).Intersect(Strip.Panel));
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
				const bool bBar = Algo::AnyOf(BarActions, [&Button](const TCHAR* Action) { return Button.Action == Action; });
				const bool bNext = Button.Action == TEXT("next_site") || Button.Action == TEXT("next_right_site");
				if (bBar)
				{
					++BarCount;
					TestTrue(Name + TEXT(" (control bar) lies left of the strip's panel, in the bottom row"), Button.Box.Max.X < Strip.Panel.Min.X && Button.Box.Min.Y >= FLsnToolbar::BottomRowTop(Size.Y, bComparing) - 0.5);
				}
				else if (bNext)
				{
					TestTrue(Name + TEXT(" exists only side by side"), bComparing);
					TestTrue(Name + TEXT(" lies in its half"), Button.Action == TEXT("next_site") ? Button.Box.Max.X <= Middle : Button.Box.Min.X >= Middle);
				}
				else
				{
					TestTrue(Name + TEXT(" exists only with the drawer open"), Drawer > 0);
					TestTrue(Name + TEXT(" lies inside the drawer"), Inside(DrawerBox, Button.Box));
					if (Button.Style != ELsnButtonStyle::Tab)
					{
						TestTrue(Name + TEXT(" exists only on the tab of further controls"), Drawer == 2);
						TestFalse(Name + TEXT(" belongs to a labelled group"), Button.Group.IsEmpty());
					}
				}
			}
			TestEqual(Where + TEXT(": the control bar has six buttons"), BarCount, 6);
			TestEqual(Where + TEXT(": 'next site' for each half side by side"), Seen.Contains(TEXT("next_site")) && Seen.Contains(TEXT("next_right_site")), bComparing);
			TestTrue(Where + TEXT(": no action outside the buttons"), Toolbar.ActionAt(FVector2D(1.0, 0.5 * Size.Y)).IsNone() && Toolbar.ActionAt(Strip.Zoom.GetCenter()).IsNone());
			const FBox2D LookBox = FLsnToolbar::LookAtSunBox(Size.X, Size.Y, bComparing);
			TestTrue(Where + TEXT(": 'look at the Sun' lies inside the safe margin"), Inside(SafeArea, LookBox));
			TestTrue(Where + TEXT(": 'look at the Sun' lies in the left half side by side"), !bComparing || LookBox.Max.X <= Middle);
			TestFalse(Where + TEXT(": 'look at the Sun' does not overlap the strip's panel"), LookBox.Intersect(Strip.Panel));
			TestFalse(Where + TEXT(": 'look at the Sun' does not overlap the drawer"), LookBox.Intersect(DrawerBox));
			for (const FLsnButton& Button : Toolbar.Buttons)
			{
				TestFalse(Where + TEXT(": 'look at the Sun' overlaps no button"), LookBox.Intersect(Button.Box));
			}
			for (const TCHAR* Needed : { TEXT("play"), TEXT("sample_back"), TEXT("sample_forward"), TEXT("day_back"), TEXT("day_forward"), TEXT("sun_event_back"), TEXT("sun_event_forward"),
				TEXT("page_sites"), TEXT("page_calendar"), TEXT("page_uncertainty"), TEXT("page_trade"), TEXT("height_next"), TEXT("details"), TEXT("help"),
				TEXT("camera"), TEXT("first_day"), TEXT("arrival") })
			{
				TestTrue(Where + TEXT(": there is a button for ") + Needed, Drawer != 2 || Seen.Contains(Needed));
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
		// Composed cameras.
		TestTrue(TEXT("the observer's view at first"), Pawn->GetCameraView() == ELsnCameraView::Observer && !Pawn->IsOverview());
		Pawn->DoAction(TEXT("camera"));
		TestTrue(TEXT("camera: the view near the lander, not the observer's"), Pawn->GetCameraView() == ELsnCameraView::Hero && Pawn->IsOverview());
		Pawn->DoAction(TEXT("camera"));
		TestTrue(TEXT("camera: the wide view"), Pawn->GetCameraView() == ELsnCameraView::Wide && Pawn->IsOverview());
		Pawn->DoAction(TEXT("camera"));
		TestTrue(TEXT("camera: back to the observer"), Pawn->GetCameraView() == ELsnCameraView::Observer && !Pawn->IsOverview());
		Pawn->DoAction(TEXT("arrival"));
		TestTrue(TEXT("arrival: a camera move, not the observer's view"), Pawn->IsArrivalRunning() && Pawn->IsOverview());
		Pawn->DoAction(TEXT("camera"));
		TestFalse(TEXT("choosing a camera ends the move"), Pawn->IsArrivalRunning());
		while (Pawn->GetCameraView() != ELsnCameraView::Observer)
		{
			Pawn->DoAction(TEXT("camera"));
		}
		// The first lunar day after the planned landing.
		const FLsnOpportunity* WithLanding = P.Opportunities.FindByPredicate([](const FLsnOpportunity& O) { return O.Planned.bPresent; });
		const FLsnCalendarPeriod* FullDay = P.Calendar.Periods.FindByPredicate([](const FLsnCalendarPeriod& Day) { return Day.bComplete; });
		Scene->SetTimeIndex(3);
		Pawn->DoAction(TEXT("first_day"));
		if (WithLanding && FullDay && P.Calendar.bPresent)
		{
			TestEqual(TEXT("first day: the time is the planned landing of the package"), P.EtOfPosition(Scene->GetTimePosition()), FMath::Clamp(WithLanding->Planned.EtS, P.Time.StartEtS, P.EtOfPosition(P.Time.Count - 1)), 1e-6);
			TestTrue(TEXT("first day: the timeline plays"), Pawn->IsPlaying() && Pawn->IsFirstDayPlaying());
			const double EndEtS = FMath::Min(WithLanding->Planned.EtS + (FullDay->EndEtS - FullDay->StartEtS), P.EtOfPosition(P.Time.Count - 1));
			TestEqual(TEXT("first day: it stops one lunar day of the calendar later"), P.EtOfPosition(Pawn->GetPlayToPosition()), EndEtS, P.Time.StepS);
		}
		else
		{
			TestFalse(TEXT("no planned landing or calendar: nothing plays"), Pawn->IsPlaying());
			TestEqual(TEXT("no planned landing or calendar: the time stays"), Scene->GetTimeIndex(), 3);
		}
		Pawn->DoAction(TEXT("sample_forward"));
		TestFalse(TEXT("a step ends the first-day play"), Pawn->IsFirstDayPlaying());
		TestFalse(TEXT("the clean view at first"), Pawn->AreControlsShown());
		Pawn->DoAction(TEXT("controls"));
		TestTrue(TEXT("all controls open"), Pawn->AreControlsShown());
		Pawn->DoAction(TEXT("follow_sun"));
		const bool bFollowed = Pawn->IsFollowingSun();
		Pawn->DoAction(TEXT("look_at_sun"));
		TestTrue(TEXT("'look at the Sun' keeps the view on the Sun"), Pawn->IsFollowingSun());
		TestEqual(TEXT("'look at the Sun' turns the view straight to it"), Pawn->GetFollowOffsetDeg(), 0.0);
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
