#include "Scene/LsnHud.h"

#include "Engine/Canvas.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Planner/LsnPlanner.h"
#include "Scene/LsnObserverPawn.h"
#include "Scene/LsnSiteScene.h"
#include "Scene/LsnUi.h"
#include "Scene/LsnViewGameMode.h"

namespace
{
	// The colours of the design system (Scene/LsnUi.h): colour carries state only.
	const FLinearColor White = FLsnUi::Ink();
	const FLinearColor Dim = FLsnUi::InkDim();
	const FLinearColor Alert = FLsnUi::Red();
	const FLinearColor SunColor = FLsnUi::Amber();
	const FLinearColor EarthColor = FLsnUi::Blue();
	const FLinearColor Good = FLsnUi::Green();
	const FLinearColor Lost = FLsnUi::Red();
}

FString LsnHudText::FormatDuration(double Seconds)
{
	const int64 Total = static_cast<int64>(FMath::FloorToDouble(FMath::Max(Seconds, 0.0)));
	const int64 Days = Total / 86400, Hours = (Total % 86400) / 3600, Minutes = (Total % 3600) / 60, Secs = Total % 60;
	if (Days > 0)
	{
		return FString::Printf(TEXT("%lld d %02lld h %02lld min"), Days, Hours, Minutes);
	}
	if (Hours > 0)
	{
		return FString::Printf(TEXT("%lld h %02lld min"), Hours, Minutes);
	}
	return FString::Printf(TEXT("%lld min %02lld s"), Minutes, Secs);
}

FString LsnHudText::UtcLabelOfPosition(const FLsnSitePackage& Package, double SamplePosition)
{
	// SPEC 3.5: start_utc + i * step_s is a valid label only without a leap second in the range.
	FDateTime Start;
	if (!Package.bHasTimeline || Package.Time.LeapSecondsInRange != 0 || !FDateTime::ParseIso8601(*Package.Time.StartUtc, Start))
	{
		return FString();
	}
	const FDateTime When = Start + FTimespan::FromSeconds(Package.Time.StepS * SamplePosition);
	return FString::Printf(TEXT("%04d-%02d-%02d %02d:%02d UTC"), When.GetYear(), When.GetMonth(), When.GetDay(), When.GetHour(), When.GetMinute());
}

FString LsnHudText::CountdownSentence(const TCHAR* BodyLabel, const FLsnCountdown& Countdown)
{
	if (!Countdown.bAvailable)
	{
		return FString();
	}
	const FString Duration = FormatDuration(Countdown.SecondsToChange);
	if (Countdown.bVisibleNow)
	{
		return Countdown.bLowerBound
			? FString::Printf(TEXT("%s visible - sets in at least %s (no set in the computed range)"), BodyLabel, *Duration)
			: FString::Printf(TEXT("%s visible - sets in %s"), BodyLabel, *Duration);
	}
	return Countdown.bLowerBound
		? FString::Printf(TEXT("%s not visible - rises in at least %s (no rise in the computed range)"), BodyLabel, *Duration)
		: FString::Printf(TEXT("%s not visible - rises in %s"), BodyLabel, *Duration);
}

void LsnHudText::BlockerSentences(const TCHAR* BodyLabel, const FLsnSitePackage& Package, const FLsnBlocking& Blocking, TArray<FString>& OutLines)
{
	OutLines.Reset();
	if (!Blocking.bHiddenOrPartly || Blocking.AzimuthIndex < 0)
	{
		return;
	}
	const FString Distance = Blocking.DistanceM < 1000.0 ? FString::Printf(TEXT("%.0f m"), Blocking.DistanceM) : FString::Printf(TEXT("%.1f km"), Blocking.DistanceM / 1000.0);
	const FString State = Blocking.VisibleFraction > 0.0 ? FString::Printf(TEXT("partly hidden (%.0f %% visible)"), 100.0 * Blocking.VisibleFraction) : FString(TEXT("hidden"));
	OutLines.Add(FString::Printf(TEXT("%s %s by terrain %s away, azimuth %.1f deg"), BodyLabel, *State, *Distance, Blocking.AzimuthDeg));
	if (Blocking.Blocker)
	{
		OutLines.Add(FString::Printf(TEXT("this obstacle costs %.1f h of %s in the computed window (%.0f %% of the time lost to terrain, against a smooth sphere)"),
			Blocking.Blocker->LostS / 3600.0, BodyLabel, 100.0 * Blocking.Blocker->ShareOfLost));
	}
	else
	{
		OutLines.Add(FString::Printf(TEXT("this obstacle costs no %s time against a smooth sphere in the computed window"), BodyLabel));
	}
	if (Blocking.Obstacle && Blocking.Obstacle->bNearField)
	{
		OutLines.Add(TEXT("within 1 km: depends on single pixels of the elevation model"));
	}
}

FString LsnHudText::LandingSentence(const FLsnLandingCheck& Check)
{
	if (!Check.bJudgeable)
	{
		return TEXT("landing now cannot be judged: the stay would run past the end of the computed range");
	}
	if (Check.bFeasible)
	{
		return FString::Printf(TEXT("landing now meets the requirement; it can slip by %s%s (earlier: %s)"), Check.bSlipIsLowerBound ? TEXT("at least ") : TEXT(""),
			*FormatDuration(Check.SlipS), *FormatDuration(Check.EarlyS));
	}
	if (Check.bHasNextWindow)
	{
		return FString::Printf(TEXT("landing now does not meet the requirement; next landing window in %s (%s long)"), *FormatDuration(Check.WaitS), *FormatDuration(Check.NextWindowLengthS));
	}
	return TEXT("landing now does not meet the requirement; no further landing window in the computed range");
}

FString LsnHudText::CountdownBandSentence(const FLsnSitePackage& Package, double EtS, const FLsnEvent& Event)
{
	return FString::Printf(TEXT("for a stated horizon error of %.2f deg: %s to %s"), Package.Uncertainty.HorizonErrorDeg,
		*FormatDuration(Event.EarliestEtS - EtS), *FormatDuration(Event.LatestEtS - EtS));
}

void LsnHudText::BuildStatusLines(const FLsnSitePackage& P, int32 H, double TimePosition, TArray<FLsnHudLine>& OutLines, const FString& GroundNote)
{
	OutLines.Reset();
	auto Line = [&OutLines](const FString& Text, const FLinearColor& Color, float Size = 1.0f) { OutLines.Add({ Text, Color, Size }); };

	if (P.bSynthetic)
	{
		Line(FString::Printf(TEXT("%s - invented values for interface testing, not results"), SyntheticMarker()), Alert, 1.4f);
	}
	Line(FString::Printf(TEXT("%s   lat %.4f  lon %.4f (east +)   frame %s"), *P.SiteName, P.LatDeg, P.LonDeg, *P.Frame), White, 1.2f);
	Line(FString::Printf(TEXT("package %s   contract %s   status %s"), *P.PackageId, *P.ContractVersion, *P.Status), Dim);
	if (P.ObserverHeightsM.IsValidIndex(H))
	{
		Line(FString::Printf(TEXT("observer height %.1f m above the surface (%d of %d)"), P.ObserverHeightsM[H], H + 1, P.NumHeights()), White);
	}

	if (P.bHasTimeline)
	{
		const int32 T = FMath::Clamp(static_cast<int32>(FMath::FloorToDouble(TimePosition)), 0, P.Time.Count - 1);
		const bool bBetween = TimePosition > T;
		for (const FString& Body : P.Bodies)
		{
			const FLsnBodySeries* S = P.FindSeries(Body);
			if (!S || !S->AzimuthDeg.IsValidIndex(T))
			{
				continue;
			}
			const int32 Flat = H * P.Time.Count + T;
			const FString Margin = S->MarginDeg.IsValidIndex(Flat) ? FString::Printf(TEXT("%.3f deg"), S->MarginDeg[Flat]) : FString(TEXT("n/a"));
			const FString Visible = S->VisibleFraction.IsValidIndex(Flat) ? FString::Printf(TEXT("%.1f %%"), 100.0f * S->VisibleFraction[Flat]) : FString(TEXT("n/a"));
			Line(FString::Printf(TEXT("%s  az %.3f  el %.3f  margin over terrain %s  visible %s   [%s]%s"), *Body,
				S->AzimuthDeg[T], S->ElevationDeg[T], *Margin, *Visible, *P.ValidationStatusOf(P.DirectionMethod),
				bBetween ? *FString::Printf(TEXT("   (values of sample %d)"), T) : TEXT("")), White);
			// The terrain that stands in that direction: read at the nearest azimuth sample, never interpolated.
			const int32 Nearest = FMath::RoundToInt32((S->AzimuthDeg[T] - P.AzimuthStartDeg) / P.AzimuthStepDeg);
			const int32 A = ((Nearest % P.AzimuthCount) + P.AzimuthCount) % P.AzimuthCount;
			Line(FString::Printf(TEXT("      terrain there: horizon %.3f deg, set by a point %.1f km away   [%s]"),
				P.HorizonElevationAt(H, A), P.HorizonDistanceAt(H, A) / 1000.0f, *P.ValidationStatusOf(P.HorizonElevationMethod)), Dim);
		}
	}
	else
	{
		Line(TEXT("This package has no timeline: no Sun or Earth is shown."), Dim);
	}
	if (!GroundNote.IsEmpty())
	{
		Line(GroundNote, Dim);
	}
	for (const FString& Warning : P.Warnings)
	{
		Line(FString::Printf(TEXT("warning: %s"), *Warning), Alert);
	}
}

float FLsnToolbar::TextScale(float SizeX, float SizeY)
{
	// Sized for the height of the view, and smaller where the view is narrow (the two halves of a comparison).
	// By the height of the window alone: the type has four sizes and does not shrink in a narrow view.
	return FMath::Clamp(SizeY / 720.0f, 0.55f, 4.0f);
}

float FLsnToolbar::HeaderBottomOf(float SizeY, bool bComparing)
{
	// One view: name on the left, chips on the right, in one band. Side by side: the chips under the name.
	return (bComparing ? 360.0f : 244.0f) * SizeY / 1080.0f;
}

float FLsnToolbar::BottomRowTop(float SizeY, bool bComparing)
{
	// The bottom row holds the control bar and the time strip; side by side the strip has the rows of two sites.
	return SizeY - (48.0f + (bComparing ? 140.0f : 96.0f)) * SizeY / 1080.0f;
}

float FLsnToolbar::BarTop(float SizeY)
{
	return BottomRowTop(SizeY, false);
}

FBox2D FLsnToolbar::DrawerBox(float WindowSizeX, float SizeY, bool bComparing)
{
	// From the right edge, between the header and the bottom row: the centre of the view stays free.
	const float U = SizeY / 1080.0f;
	return FBox2D(FVector2D(WindowSizeX - 808.0f * U, HeaderBottomOf(SizeY, bComparing) + 16.0f * U), FVector2D(WindowSizeX - 48.0f * U, BottomRowTop(SizeY, bComparing) - 52.0f * U));
}

FBox2D FLsnToolbar::DrawerContent(float WindowSizeX, float SizeY, bool bComparing)
{
	const float U = SizeY / 1080.0f;
	const FBox2D Drawer = DrawerBox(WindowSizeX, SizeY, bComparing);
	return FBox2D(FVector2D(Drawer.Min.X + 16.0f * U, Drawer.Min.Y + 68.0f * U), FVector2D(Drawer.Max.X - 16.0f * U, Drawer.Max.Y - 12.0f * U));
}

FBox2D FLsnToolbar::LookAtSunBox(float WindowSizeX, float SizeY, bool bComparing)
{
	// On the left, above the hint line over the control bar.
	const float U = SizeY / 1080.0f, Top = BottomRowTop(SizeY, bComparing) - 106.0f * U;
	return FBox2D(FVector2D(48.0f * U, Top), FVector2D(48.0f * U + 380.0f * U, Top + 44.0f * U));
}

FLsnToolbar FLsnToolbar::Make(float WindowSizeX, float SizeY, bool bComparing, bool bDrawerOpen, bool bControlsTab)
{
	FLsnToolbar Toolbar;
	const float W = WindowSizeX, H = SizeY, U = H / 1080.0f, M = 48.0f * U;
	Toolbar.HeaderBottom = HeaderBottomOf(H, bComparing);
	Toolbar.Top = BottomRowTop(H, bComparing);

	// The control bar, bottom left: two rows of three quiet buttons.
	static const TPair<const TCHAR*, const TCHAR*> Bar[] = {
		{ TEXT("play"), TEXT("Play") }, { TEXT("next_sunset"), TEXT("Next sunset") }, { TEXT("obstacle"), TEXT("Obstacle") },
		{ TEXT("compare"), TEXT("Compare") }, { TEXT("camera"), TEXT("Camera") }, { TEXT("controls"), TEXT("More") },
	};
	const float ButtonWidth = 148.0f * U, ButtonHeight = 44.0f * U, Gap = 8.0f * U;
	const float BarY0 = H - M - 2.0f * ButtonHeight - Gap;
	for (int32 I = 0; I < UE_ARRAY_COUNT(Bar); ++I)
	{
		const float X0 = M + (I % 3) * (ButtonWidth + Gap), Y0 = BarY0 + (I / 3) * (ButtonHeight + Gap);
		Toolbar.Buttons.Add({ Bar[I].Key, Bar[I].Value, FBox2D(FVector2D(X0, Y0), FVector2D(X0 + ButtonWidth, Y0 + ButtonHeight)), ELsnButtonStyle::Bar, FString() });
	}

	// Side by side: "Next site" in the header of each half.
	if (bComparing)
	{
		const float NextWidth = 150.0f * U, NextHeight = 40.0f * U;
		Toolbar.Buttons.Add({ TEXT("next_site"), TEXT("Next site"), FBox2D(FVector2D(0.5f * W - M - NextWidth, M), FVector2D(0.5f * W - M, M + NextHeight)), ELsnButtonStyle::RightView, FString() });
		Toolbar.Buttons.Add({ TEXT("next_right_site"), TEXT("Next site"), FBox2D(FVector2D(W - M - NextWidth, M), FVector2D(W - M, M + NextHeight)), ELsnButtonStyle::RightView, FString() });
	}

	// The drawer: its tabs, and on the tab of the further controls their buttons in labelled groups.
	if (bDrawerOpen)
	{
		const FBox2D Drawer = DrawerBox(W, H, bComparing);
		static const TPair<const TCHAR*, const TCHAR*> Tabs[] = {
			{ TEXT("page_calendar"), TEXT("Calendar") }, { TEXT("page_uncertainty"), TEXT("Uncertainty") }, { TEXT("page_trade"), TEXT("Mast height") },
			{ TEXT("page_sites"), TEXT("Sites") }, { TEXT("details"), TEXT("Evidence") }, { TEXT("controls_tab"), TEXT("Controls") },
		};
		const int32 NumTabs = UE_ARRAY_COUNT(Tabs);
		const float TabX0 = Drawer.Min.X + 16.0f * U, TabWidth = (Drawer.Max.X - Drawer.Min.X - 32.0f * U - (NumTabs - 1) * Gap) / NumTabs;
		for (int32 I = 0; I < NumTabs; ++I)
		{
			const float X0 = TabX0 + I * (TabWidth + Gap);
			Toolbar.Buttons.Add({ Tabs[I].Key, Tabs[I].Value, FBox2D(FVector2D(X0, Drawer.Min.Y + 12.0f * U), FVector2D(X0 + TabWidth, Drawer.Min.Y + 52.0f * U)), ELsnButtonStyle::Tab, FString() });
		}
		if (bControlsTab)
		{
			struct FEntry { const TCHAR* Action; const TCHAR* Label; const TCHAR* Group; };
			static const FEntry Entries[] = {
				{ TEXT("slower"), TEXT("Slower"), TEXT("TIME") }, { TEXT("faster"), TEXT("Faster"), TEXT("TIME") }, { TEXT("sample_back"), TEXT("Step back"), TEXT("TIME") },
				{ TEXT("sample_forward"), TEXT("Step forward"), TEXT("TIME") }, { TEXT("day_back"), TEXT("Day back"), TEXT("TIME") }, { TEXT("day_forward"), TEXT("Day forward"), TEXT("TIME") },
				{ TEXT("sun_event_back"), TEXT("Previous sunrise / set"), TEXT("TIME") }, { TEXT("sun_event_forward"), TEXT("Next sunrise / set"), TEXT("TIME") },
				{ TEXT("first_day"), TEXT("First lunar day"), TEXT("MISSION AND OBSERVER") }, { TEXT("arrival"), TEXT("Arrival view"), TEXT("MISSION AND OBSERVER") }, { TEXT("height_next"), TEXT("Observer height"), TEXT("MISSION AND OBSERVER") },
				{ TEXT("follow_sun"), TEXT("Follow Sun"), TEXT("VIEW") }, { TEXT("scale_objects"), TEXT("Scale objects"), TEXT("VIEW") }, { TEXT("fill_light"), TEXT("Night fill light"), TEXT("VIEW") },
				{ TEXT("quality"), TEXT("Low quality"), TEXT("VIEW") }, { TEXT("help"), TEXT("Help (F1)"), TEXT("VIEW") },
			};
			const FBox2D Content = DrawerContent(W, H, bComparing);
			const float CellWidth = (Content.Max.X - Content.Min.X - 2.0f * Gap) / 3.0f, CellHeight = 40.0f * U, LabelHeight = 28.0f * U;
			float Y = Content.Min.Y;
			int32 Column = 0;
			for (int32 I = 0; I < UE_ARRAY_COUNT(Entries); ++I)
			{
				const FEntry& Entry = Entries[I];
				if (I == 0 || FCString::Strcmp(Entries[I - 1].Group, Entry.Group) != 0)
				{
					if (Column != 0) { Y += CellHeight + Gap; }
					Column = 0;
					Toolbar.GroupLabels.Add({ Entry.Group, FVector2D(Content.Min.X, Y) });
					Y += LabelHeight;
				}
				const float X0 = Content.Min.X + Column * (CellWidth + Gap);
				Toolbar.Buttons.Add({ Entry.Action, Entry.Label, FBox2D(FVector2D(X0, Y), FVector2D(X0 + CellWidth, Y + CellHeight)), ELsnButtonStyle::Bar, Entry.Group });
				if (++Column == 3)
				{
					Column = 0;
					Y += CellHeight + Gap;
				}
			}
		}
	}
	return Toolbar;
}

FName FLsnToolbar::ActionAt(const FVector2D& Point) const
{
	for (const FLsnButton& Button : Buttons)
	{
		if (Button.Box.IsInside(Point))
		{
			return Button.Action;
		}
	}
	return NAME_None;
}

FLsnSitePicker FLsnSitePicker::Make(float WindowSizeX, float SizeY, bool bComparing, const TArray<FString>& GroupOfSite, const TArray<bool>* Hidden, int32 FirstRow)
{
	FLsnSitePicker Picker;
	const float U = SizeY / 1080.0f;
	// In the drawer, on the tab of the sites: a search field, the list in one column, the custom coordinates.
	Picker.Sheet = FLsnToolbar::DrawerContent(WindowSizeX, SizeY, bComparing);
	const float X0 = Picker.Sheet.Min.X, X1 = Picker.Sheet.Max.X;
	Picker.TitlePosition = FVector2D(X0, Picker.Sheet.Min.Y);
	const float SearchTop = Picker.Sheet.Min.Y + 30.0f * U, FieldHeight = 36.0f * U;
	Picker.SearchField = FBox2D(FVector2D(X0, SearchTop), FVector2D(X1, SearchTop + FieldHeight));

	// The rows: a header where a group first appears, then its sites in the order of the list.
	// A group none of whose sites is shown has no header, so no header stands alone.
	TArray<FString> Groups;
	for (const FString& Group : GroupOfSite)
	{
		Groups.AddUnique(Group);
	}
	struct FItem { int32 Site; FString Group; };
	TArray<FItem> Items;
	for (const FString& Group : Groups)
	{
		const int32 HeaderAt = Items.Num();
		for (int32 I = 0; I < GroupOfSite.Num(); ++I)
		{
			if (GroupOfSite[I] == Group && !(Hidden && Hidden->IsValidIndex(I) && (*Hidden)[I]))
			{
				Items.Add({ I, Group });
			}
		}
		if (Items.Num() > HeaderAt)
		{
			Items.Insert({ -1, Group }, HeaderAt);
		}
	}
	const float FooterHeight = 150.0f * U, RowHeight = 32.0f * U;
	const float RowsTop = SearchTop + FieldHeight + 10.0f * U, RowsBottom = Picker.Sheet.Max.Y - FooterHeight;
	Picker.RowsPerPage = FMath::Max(FMath::FloorToInt32((RowsBottom - RowsTop) / RowHeight), 1);
	Picker.NumRows = Items.Num();
	Picker.FirstRow = FMath::Clamp(FirstRow, 0, FMath::Max(Items.Num() - 2, 0));
	// A list that begins in the middle of a group begins with that group's header, and the
	// last row shown is never a header: no header stands alone.
	TArray<FItem> Page;
	if (Items.IsValidIndex(Picker.FirstRow) && Items[Picker.FirstRow].Site >= 0)
	{
		Page.Add({ -1, Items[Picker.FirstRow].Group });
	}
	for (int32 I = Picker.FirstRow; I < Items.Num() && Page.Num() < Picker.RowsPerPage; ++I)
	{
		Page.Add(Items[I]);
	}
	while (Page.Num() > 0 && Page.Last().Site < 0)
	{
		Page.Pop();
	}
	for (int32 Slot = 0; Slot < Page.Num(); ++Slot)
	{
		const FItem& Item = Page[Slot];
		const float Y0 = RowsTop + RowHeight * Slot;
		FLsnPickerRow Row;
		Row.SiteIndex = Item.Site;
		Row.Group = Item.Group;
		Row.Row = FBox2D(FVector2D(X0, Y0), FVector2D(X1, Y0 + RowHeight));
		if (Row.SiteIndex >= 0)
		{
			// The name is the "show" box; at the right end two small boxes pin the site for a view.
			const float PinWidth = 56.0f * U;
			Row.PinRight = FBox2D(FVector2D(X1 - PinWidth, Y0 + 2.0f * U), FVector2D(X1, Y0 + RowHeight - 2.0f * U));
			Row.PinLeft = FBox2D(FVector2D(X1 - 2.0f * PinWidth - 6.0f * U, Y0 + 2.0f * U), FVector2D(X1 - PinWidth - 6.0f * U, Y0 + RowHeight - 2.0f * U));
			Row.Show = FBox2D(FVector2D(X0, Y0 + 1.0f), FVector2D(X1 - 2.0f * PinWidth - 14.0f * U, Y0 + RowHeight - 1.0f));
		}
		Picker.Rows.Add(Row);
	}

	// Custom coordinates at the foot: a label, two fields and a button, and lines for the message.
	const float EntryTop = Picker.Sheet.Max.Y - FooterHeight + 12.0f * U, FieldTop = EntryTop + 30.0f * U;
	const float Width = X1 - X0;
	Picker.EntryLabelPosition = FVector2D(X0, EntryTop);
	Picker.LatField = FBox2D(FVector2D(X0 + 0.11f * Width, FieldTop), FVector2D(X0 + 0.30f * Width, FieldTop + FieldHeight));
	Picker.LonField = FBox2D(FVector2D(X0 + 0.50f * Width, FieldTop), FVector2D(X0 + 0.69f * Width, FieldTop + FieldHeight));
	Picker.Compute = FBox2D(FVector2D(X0 + 0.73f * Width, FieldTop), FVector2D(X1, FieldTop + FieldHeight));
	Picker.MessagePosition = FVector2D(X0, FieldTop + FieldHeight + 8.0f * U);
	return Picker;
}

ELsnPickerHit FLsnSitePicker::HitAt(const FVector2D& Point, int32& OutSiteIndex) const
{
	OutSiteIndex = -1;
	if (!Sheet.IsInside(Point))
	{
		return ELsnPickerHit::None;
	}
	if (SearchField.IsInside(Point)) { return ELsnPickerHit::SearchField; }
	if (LatField.IsInside(Point)) { return ELsnPickerHit::LatField; }
	if (LonField.IsInside(Point)) { return ELsnPickerHit::LonField; }
	if (Compute.IsInside(Point)) { return ELsnPickerHit::Compute; }
	for (const FLsnPickerRow& Row : Rows)
	{
		if (Row.SiteIndex < 0 || !Row.Row.IsInside(Point))
		{
			continue;
		}
		OutSiteIndex = Row.SiteIndex;
		return Row.PinLeft.IsInside(Point) ? ELsnPickerHit::PinLeft : Row.PinRight.IsInside(Point) ? ELsnPickerHit::PinRight : Row.Show.IsInside(Point) ? ELsnPickerHit::Show : ELsnPickerHit::None;
	}
	return ELsnPickerHit::None;
}

FLsnTimeStripLayout FLsnTimeStripLayout::Make(float WindowSizeX, float SizeY, const FLsnSitePackage& Package, bool bComparing, bool bWithControlBar)
{
	FLsnTimeStripLayout Layout;
	const float U = SizeY / 1080.0f, M = 48.0f * U;
	// One strip in a panel along the bottom, right of the control bar; side by side it is shared and has the rows of both sites.
	const float Left = bWithControlBar ? M + 476.0f * U : M, Right = WindowSizeX - M, Top = FLsnToolbar::BottomRowTop(SizeY, bComparing);
	Layout.Panel = FBox2D(FVector2D(Left, Top), FVector2D(Right, SizeY - M));
	// Side by side the names of the two sites stand left of their rows.
	Layout.Zoom = FBox2D(FVector2D(Left + (bComparing ? 236.0f : 16.0f) * U, Top + 14.0f * U), FVector2D(Right - 16.0f * U, Top + (bComparing ? 94.0f : 50.0f) * U));
	// The strip of the whole range is gone from the screen: the calendar of the drawer shows the whole range.
	Layout.WholeRange = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);
	// The strip shows six days around the selected time, or the whole axis if that is shorter.
	const double SixDays = Package.Time.StepS > 0.0 ? 6.0 * 86400.0 / Package.Time.StepS : 0.0;
	Layout.ZoomHalfWidthSamples = FMath::Min(0.5 * SixDays, 0.5 * FMath::Max(Package.Time.Count - 1, 1));
	return Layout;
}

bool FLsnTimeStripLayout::PositionAt(const FVector2D& Point, const FLsnSitePackage& Package, double CurrentPosition, double& OutPosition) const
{
	const double Last = FMath::Max(Package.Time.Count - 1, 0);
	if (Zoom.IsInside(Point))
	{
		const double Fraction = (Point.X - Zoom.Min.X) / (Zoom.Max.X - Zoom.Min.X);
		OutPosition = FMath::Clamp(CurrentPosition + (2.0 * Fraction - 1.0) * ZoomHalfWidthSamples, 0.0, Last);
		return true;
	}
	return false;
}

void ALsnHud::DrawStrip(const FBox2D& Box, const FLsnSitePackage& P, int32 H, double FromPosition, double ToPosition, double CurrentPosition, float Scale)
{
	const float Width = Box.Max.X - Box.Min.X, Height = Box.Max.Y - Box.Min.Y;
	const double FromEt = P.EtOfPosition(FromPosition), ToEt = P.EtOfPosition(ToPosition);
	const double AxisStartEt = P.EtOfPosition(0.0), AxisEndEt = P.EtOfPosition(P.Time.Count - 1);
	auto X = [&](double EtS) { return Box.Min.X + Width * static_cast<float>(FMath::Clamp((EtS - FromEt) / (ToEt - FromEt), 0.0, 1.0)); };

	// Two rows: Sun visible above, Earth visible below. Both are the package's windows.
	struct FRow { const TCHAR* WindowId; FLinearColor Color; float Top; };
	const FRow Rows[] = { { TEXT("sun_visible"), FLsnUi::Amber(), 0.0f }, { TEXT("earth_visible"), FLsnUi::Blue(), 0.56f } };
	for (const FRow& Row : Rows)
	{
		const FBox2D Track(FVector2D(Box.Min.X, Box.Min.Y + Row.Top * Height), FVector2D(Box.Max.X, Box.Min.Y + (Row.Top + 0.44f) * Height));
		DrawRounded(Track, FLinearColor(1.0f, 1.0f, 1.0f, 0.07f), 2.0f);
		// Outside the package's time axis there is nothing to show.
		if (FromEt < AxisStartEt)
		{
			DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), Box.Min.X, Track.Min.Y, X(AxisStartEt) - Box.Min.X, Track.Max.Y - Track.Min.Y);
		}
		if (ToEt > AxisEndEt)
		{
			DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), X(AxisEndEt), Track.Min.Y, Box.Max.X - X(AxisEndEt), Track.Max.Y - Track.Min.Y);
		}
		// With a stated horizon error (SPEC 5.7) the edges are bands, not lines: pale where the
		// body is visible only if the horizon is lower than computed, full where it is visible
		// even if the horizon is higher.
		const FLsnWindow* Possible = P.FindWindow(FString(Row.WindowId) + TEXT("_possible"), H);
		const FLsnWindow* Certain = P.FindWindow(FString(Row.WindowId) + TEXT("_certain"), H);
		const bool bBand = Possible && Certain;
		struct FTone { const FLsnWindow* Window; float Alpha; };
		const FTone Tones[] = { { bBand ? Possible : nullptr, 0.30f }, { P.FindWindow(Row.WindowId, H), bBand ? 0.55f : 1.0f }, { bBand ? Certain : nullptr, 1.0f } };
		for (const FTone& Tone : Tones)
		{
			for (int32 I = 0; Tone.Window && I < Tone.Window->StartsEtS.Num(); ++I)
			{
				if (Tone.Window->EndsEtS[I] < FromEt || Tone.Window->StartsEtS[I] > ToEt)
				{
					continue;
				}
				const float X0 = X(Tone.Window->StartsEtS[I]), X1 = X(Tone.Window->EndsEtS[I]);
				// Opaque tones, so that a pale band does not add up with what lies on it.
				const FLinearColor Color(Row.Color.R * Tone.Alpha, Row.Color.G * Tone.Alpha, Row.Color.B * Tone.Alpha, 1.0f);
				DrawRect(Color, X0, Track.Min.Y, FMath::Max(X1 - X0, 1.0f), Track.Max.Y - Track.Min.Y);
			}
		}
	}
}

void ALsnHud::DrawPanorama(const FLsnPanorama& Pano, const ALsnSiteScene& Scene, const ALsnObserverPawn* Pawn, float Scale)
{
	const FLsnSitePackage& P = Scene.GetPackage();
	const int32 H = Scene.GetHeightIndex();
	UFont* Font = GEngine->GetMediumFont();
	const float Width = Pano.Box.Max.X - Pano.Box.Min.X, Height = Pano.Box.Max.Y - Pano.Box.Min.Y;
	DrawRect(FLinearColor(0.02f, 0.02f, 0.03f, 0.85f), Pano.Box.Min.X, Pano.Box.Min.Y, Width, Height);

	// Terrain below the package horizon, one column per degree of azimuth.
	const int32 Columns = 360;
	for (int32 C = 0; C < Columns; ++C)
	{
		const double El = P.HorizonElevationInterpolated(H, C + 0.5);
		if (FMath::IsNaN(El))
		{
			continue;
		}
		const FVector2D Top = Pano.Point(C + 0.5, El);
		DrawRect(FLinearColor(0.22f, 0.22f, 0.24f, 1.0f), Pano.Box.Min.X + Width * C / Columns, Top.Y, Width / Columns + 1.0f, Pano.Box.Max.Y - Top.Y);
	}
	// The horizontal of the site.
	const float ZeroY = Pano.Point(0.0, 0.0).Y;
	DrawLine(Pano.Box.Min.X, ZeroY, Pano.Box.Max.X, ZeroY, FLinearColor(0.45f, 0.45f, 0.45f, 0.8f), 1.0f);

	// The obstacle that hides a body at the selected sample: its run, in the colour of the highlight in the view.
	const int32 Sample = Scene.GetTimeIndex();
	for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
	{
		const bool bSun = FCString::Stricmp(Body, TEXT("SUN")) == 0;
		FLsnBlocking Blocking;
		if (Scene.IsObstacleViewEnabled() && P.BlockingAt(Body, H, Sample, Blocking) && Blocking.bHiddenOrPartly && Blocking.Obstacle)
		{
			TArray<int32> Run;
			P.ObstacleRun(*Blocking.Obstacle, Run);
			for (int32 I = 0; I + 1 < Run.Num(); ++I)
			{
				const FVector2D A = Pano.Point(P.AzimuthDegAt(Run[I]), P.HorizonElevationAt(H, Run[I]));
				const FVector2D B = Pano.Point(P.AzimuthDegAt(Run[I + 1]), P.HorizonElevationAt(H, Run[I + 1]));
				if (FMath::Abs(B.X - A.X) < 0.5f * Width)
				{
					DrawLine(A.X, A.Y, B.X, B.Y, bSun ? FLinearColor(1.0f, 0.3f, 0.05f) : FLinearColor(0.1f, 0.8f, 1.0f), 2.5f * Scale);
				}
			}
		}
		// The body itself, at the direction the package gives for the selected time.
		FLsnBodyAtTime At;
		if (Scene.SampleBody(Body, Scene.GetTimePosition(), At))
		{
			const FVector2D Point = Pano.Point(At.AzimuthDeg, At.ElevationDeg);
			const float Half = 3.5f * Scale;
			DrawRect(bSun ? SunColor : EarthColor, Point.X - Half, Point.Y - Half, 2.0f * Half, 2.0f * Half);
			DrawText(bSun ? TEXT("Sun") : TEXT("Earth"), bSun ? SunColor : EarthColor, Point.X + Half + 2.0f * Scale, Point.Y - 8.0f * Scale, Font, Scale * 0.85f);
		}
	}
	// What the camera sees: the two edges of the field of view.
	if (Pawn)
	{
		for (const double Edge : { -0.5, 0.5 })
		{
			const float X = Pano.Point(Pawn->GetAzimuthDeg() + Edge * Pawn->GetFovDeg(), 0.0).X;
			DrawLine(X, Pano.Box.Min.Y, X, Pano.Box.Max.Y, FLinearColor(1.0f, 1.0f, 1.0f, 0.55f), 1.0f);
		}
	}
	const TCHAR* Compass[] = { TEXT("N"), TEXT("E"), TEXT("S"), TEXT("W") };
	for (int32 I = 0; I < 4; ++I)
	{
		DrawText(Compass[I], Dim, Pano.Point(90.0 * I, 0.0).X + 2.0f * Scale, Pano.Box.Max.Y - 15.0f * Scale, Font, Scale * 0.85f);
	}
	DrawFit(FString::Printf(TEXT("horizon all round, %+.0f to %+.0f deg; white lines: this view"), Pano.MinElevationDeg, Pano.MaxElevationDeg),
		Dim, Pano.Box.Min.X, Pano.Box.Max.Y + 1.0f * Scale, Width, Scale * 0.85f);
}

float ALsnHud::DrawFit(const FString& Text, const FLinearColor& Color, float X, float Y, float MaxWidth, float TextScale)
{
	UFont* Font = GEngine->GetMediumFont();
	float Width = 0.0f, Height = 0.0f;
	GetTextSize(Text, Width, Height, Font, TextScale);
	// The type has four sizes: a text that is too wide is cut and ends in three dots, it is not made smaller.
	FString Shown = Text;
	while (Width > MaxWidth && Shown.Len() > 4)
	{
		Shown = Shown.LeftChop(5).TrimEnd() + TEXT("...");
		GetTextSize(Shown, Width, Height, Font, TextScale);
	}
	DrawText(Shown, Color, X, Y, Font, TextScale);
	return Width;
}

void ALsnHud::EndPlay(const EEndPlayReason::Type Reason)
{
	FLsnUi::Get().RemoveWidget();
	Super::EndPlay(Reason);
}

float ALsnHud::SizeOfScale(float Scale) const
{
	// The old calls gave a scale of the engine's font: 0.9 small, 1.12 text, 1.45 large, 2 extra large at a height of 720.
	const float Ratio = Scale / FLsnToolbar::TextScale(1.0f, UiHeight);
	const float At1080 = Ratio < 1.0f ? FLsnUi::Footnote : Ratio < 1.3f ? FLsnUi::Body : Ratio < 1.9f ? FLsnUi::Title : FLsnUi::Display;
	return U(At1080);
}

void ALsnHud::DrawRect(FLinearColor Color, float X, float Y, float Width, float Height)
{
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Box;
	Item.Box = FBox2D(UiOrigin + FVector2D(X, Y), UiOrigin + FVector2D(X + Width, Y + Height));
	Item.Color = Color;
	FLsnUi::Get().Add(Item);
}

void ALsnHud::DrawRounded(const FBox2D& Box, const FLinearColor& Fill, float RadiusAt1080, const FLinearColor& Border)
{
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Box;
	Item.Box = FBox2D(UiOrigin + Box.Min, UiOrigin + Box.Max);
	Item.Color = Fill;
	Item.Radius = U(RadiusAt1080);
	Item.Border = Border;
	Item.BorderPx = Border.A > 0.0f ? FMath::Max(U(1.0f), 1.0f) : 0.0f;
	FLsnUi::Get().Add(Item);
}

void ALsnHud::DrawPanel(const FBox2D& Box, bool bBlur)
{
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Box;
	Item.Box = FBox2D(UiOrigin + Box.Min, UiOrigin + Box.Max);
	Item.Color = FLsnUi::PanelFill();
	Item.Radius = U(FLsnUi::PanelRadius);
	Item.Border = FLsnUi::Hairline();
	Item.BorderPx = FMath::Max(U(1.0f), 1.0f);
	Item.bBlur = bBlur;
	FLsnUi::Get().Add(Item);
}

void ALsnHud::DrawText(const FString& Text, FLinearColor Color, float X, float Y, UFont*, float Scale, bool)
{
	if (Text.IsEmpty())
	{
		return;
	}
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Text;
	Item.Box = FBox2D(UiOrigin + FVector2D(X, Y), UiOrigin + FVector2D(X, Y));
	Item.Color = Color;
	Item.Text = Text;
	Item.SizePx = SizeOfScale(Scale);
	FLsnUi::Get().Add(Item);
}

void ALsnHud::DrawType(const FString& Text, const FLinearColor& Color, float X, float Y, float SizeAt1080, bool bMedium)
{
	if (Text.IsEmpty())
	{
		return;
	}
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Text;
	Item.Box = FBox2D(UiOrigin + FVector2D(X, Y), UiOrigin + FVector2D(X, Y));
	Item.Color = Color;
	Item.Text = Text;
	Item.SizePx = U(SizeAt1080);
	Item.bMedium = bMedium;
	FLsnUi::Get().Add(Item);
}

float ALsnHud::TypeWidth(const FString& Text, float SizeAt1080, bool bMedium) const
{
	return static_cast<float>(FLsnUi::Measure(Text, U(SizeAt1080), bMedium).X);
}

float ALsnHud::DrawDuration(const FString& Text, const FLinearColor& Color, float X, float Y, float SizeAt1080, bool bDraw)
{
	// Runs of digits at the size; everything else (units, words) one size smaller, on the same baseline.
	const float Smaller = SizeAt1080 >= FLsnUi::Display ? FLsnUi::Title : SizeAt1080 >= FLsnUi::Title ? FLsnUi::Body : FLsnUi::Footnote;
	// The baseline of this family lies about 0.93 of the size below the top of a line.
	const float Drop = 0.93f * U(SizeAt1080 - Smaller);
	float Pen = X;
	int32 Start = 0;
	while (Start < Text.Len())
	{
		const bool bDigits = FChar::IsDigit(Text[Start]);
		int32 End = Start;
		while (End < Text.Len() && FChar::IsDigit(Text[End]) == bDigits)
		{
			++End;
		}
		const FString Run = Text.Mid(Start, End - Start);
		if (bDraw)
		{
			DrawType(Run, Color, Pen, bDigits ? Y : Y + Drop, bDigits ? SizeAt1080 : Smaller, bDigits);
		}
		Pen += TypeWidth(Run, bDigits ? SizeAt1080 : Smaller, bDigits);
		Start = End;
	}
	return Pen - X;
}

void ALsnHud::GetTextSize(const FString& Text, float& OutWidth, float& OutHeight, UFont*, float Scale) const
{
	const FVector2D Size = FLsnUi::Measure(Text, SizeOfScale(Scale));
	OutWidth = static_cast<float>(Size.X);
	OutHeight = static_cast<float>(Size.Y);
}

void ALsnHud::DrawLine(float X0, float Y0, float X1, float Y1, FLinearColor Color, float Thickness)
{
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Line;
	Item.A = UiOrigin + FVector2D(X0, Y0);
	Item.B = UiOrigin + FVector2D(X1, Y1);
	Item.Color = Color;
	Item.Thickness = FMath::Max(Thickness, 1.0f);
	FLsnUi::Get().Add(Item);
}

TArray<FString> ALsnHud::WrapLines(const FString& Text, float SizeAt1080, float MaxWidth) const
{
	TArray<FString> Lines;
	FString Rest = Text;
	while (!Rest.IsEmpty())
	{
		FString Part = Rest;
		while (TypeWidth(Part, SizeAt1080) > MaxWidth)
		{
			int32 Space = INDEX_NONE;
			if (!Part.FindLastChar(TEXT(' '), Space) || Space <= 0)
			{
				break;
			}
			Part.LeftInline(Space);
		}
		Lines.Add(Part);
		Rest = Part.Len() < Rest.Len() ? Rest.Mid(Part.Len()).TrimStart() : FString();
	}
	return Lines;
}

float ALsnHud::DrawCard(const TArray<FLsnHudLine>& Lines, float X, float Y, float Width)
{
	// Measured first, so that the panel is as high as its text. FLsnHudLine::Size is one of the four sizes.
	const float Pad = U(12.0f);
	struct FRun { FString Text; FLinearColor Color; float Size; };
	TArray<FRun> Runs;
	float Height = 2.0f * Pad;
	for (const FLsnHudLine& Line : Lines)
	{
		for (const FString& Part : WrapLines(Line.Text, Line.Size, Width - 2.0f * Pad))
		{
			Runs.Add({ Part, Line.Color, Line.Size });
			Height += U(1.35f * Line.Size);
		}
	}
	if (Runs.Num() == 0)
	{
		return Y;
	}
	DrawPanel(FBox2D(FVector2D(X, Y), FVector2D(X + Width, Y + Height)));
	float LineY = Y + Pad;
	for (const FRun& Run : Runs)
	{
		DrawType(Run.Text, Run.Color, X + Pad, LineY, Run.Size);
		LineY += U(1.35f * Run.Size);
	}
	return Y + Height + U(FLsnUi::Grid);
}

void ALsnHud::DrawDisc(const FVector2D& Centre, float RadiusPx, const FLinearColor& Color)
{
	FLsnUiItem Item;
	Item.Kind = FLsnUiItem::EKind::Box;
	Item.Box = FBox2D(UiOrigin + Centre - FVector2D(RadiusPx, RadiusPx), UiOrigin + Centre + FVector2D(RadiusPx, RadiusPx));
	Item.Color = Color;
	Item.Radius = RadiusPx;
	FLsnUi::Get().Add(Item);
}

void ALsnHud::DrawIcon(FName Icon, const FVector2D& C, const FLinearColor& Color, bool bOn)
{
	const float S = U(8.0f), T = FMath::Max(U(1.6f), 1.0f);
	if (Icon == TEXT("sun"))
	{
		DrawDisc(C, S, Color);
	}
	else if (Icon == TEXT("earth"))
	{
		DrawDisc(C, S, Color);
		DrawDisc(C + FVector2D(0.35f * S, -0.3f * S), 0.45f * S, FLinearColor(0.02f, 0.03f, 0.05f, 0.55f));
	}
	else if (Icon == TEXT("lander"))
	{
		DrawRect(Color, C.X - 0.6f * S, C.Y - 0.7f * S, 1.2f * S, 0.9f * S);
		DrawLine(C.X - 0.6f * S, C.Y + 0.2f * S, C.X - 1.1f * S, C.Y + S, Color, T);
		DrawLine(C.X + 0.6f * S, C.Y + 0.2f * S, C.X + 1.1f * S, C.Y + S, Color, T);
	}
	else if (Icon == TEXT("play"))
	{
		if (bOn)
		{
			DrawRect(Color, C.X - 0.7f * S, C.Y - 0.8f * S, 0.5f * S, 1.6f * S);
			DrawRect(Color, C.X + 0.2f * S, C.Y - 0.8f * S, 0.5f * S, 1.6f * S);
		}
		else
		{
			DrawLine(C.X - 0.6f * S, C.Y - 0.9f * S, C.X - 0.6f * S, C.Y + 0.9f * S, Color, T);
			DrawLine(C.X - 0.6f * S, C.Y - 0.9f * S, C.X + 0.9f * S, C.Y, Color, T);
			DrawLine(C.X - 0.6f * S, C.Y + 0.9f * S, C.X + 0.9f * S, C.Y, Color, T);
		}
	}
	else if (Icon == TEXT("next_sunset"))
	{
		DrawDisc(C + FVector2D(0.0f, -0.1f * S), 0.6f * S, Color);
		DrawRect(FLinearColor(0.05f, 0.06f, 0.07f, 1.0f), C.X - S, C.Y + 0.25f * S, 2.0f * S, 0.6f * S);
		DrawLine(C.X - S, C.Y + 0.25f * S, C.X + S, C.Y + 0.25f * S, Color, T);
	}
	else if (Icon == TEXT("obstacle"))
	{
		DrawLine(C.X - S, C.Y + 0.7f * S, C.X - 0.3f * S, C.Y - 0.7f * S, Color, T);
		DrawLine(C.X - 0.3f * S, C.Y - 0.7f * S, C.X + 0.2f * S, C.Y + 0.1f * S, Color, T);
		DrawLine(C.X + 0.2f * S, C.Y + 0.1f * S, C.X + 0.5f * S, C.Y - 0.3f * S, Color, T);
		DrawLine(C.X + 0.5f * S, C.Y - 0.3f * S, C.X + S, C.Y + 0.7f * S, Color, T);
	}
	else if (Icon == TEXT("compare"))
	{
		DrawRect(Color, C.X - S, C.Y - 0.7f * S, 0.85f * S, 1.4f * S);
		DrawRect(FLinearColor(Color.R, Color.G, Color.B, 0.5f * Color.A), C.X + 0.15f * S, C.Y - 0.7f * S, 0.85f * S, 1.4f * S);
	}
	else if (Icon == TEXT("camera"))
	{
		DrawRect(Color, C.X - S, C.Y - 0.5f * S, 1.4f * S, 1.1f * S);
		DrawLine(C.X + 0.4f * S, C.Y, C.X + S, C.Y - 0.5f * S, Color, T);
		DrawLine(C.X + 0.4f * S, C.Y, C.X + S, C.Y + 0.6f * S, Color, T);
		DrawLine(C.X + S, C.Y - 0.5f * S, C.X + S, C.Y + 0.6f * S, Color, T);
	}
	else if (Icon == TEXT("controls"))
	{
		for (int32 I = -1; I <= 1; ++I)
		{
			DrawDisc(C + FVector2D(I * 0.7f * S, 0.0f), 0.22f * S, Color);
		}
	}
	else if (Icon == TEXT("next_site") || Icon == TEXT("next_right_site"))
	{
		DrawLine(C.X - 0.4f * S, C.Y - 0.7f * S, C.X + 0.4f * S, C.Y, Color, T);
		DrawLine(C.X - 0.4f * S, C.Y + 0.7f * S, C.X + 0.4f * S, C.Y, Color, T);
	}
}

void ALsnHud::DrawButton(const FBox2D& Box, const FString& Label, FName Icon, bool bOn, bool bEnabled, bool bAccent, FName HoverKey)
{
	// One quiet style: dark, hairline border, icon and label. Hover and pressed lighten it; a switch that is on has a brighter edge.
	const bool bInside = bEnabled && Box.IsInside(UiMouse - UiOrigin);
	float& Hover = HoverOf.FindOrAdd(HoverKey);
	// 150 ms from one state to the other.
	Hover = FMath::Clamp(Hover + (bInside ? 1.0f : -1.0f) * UiDelta / 0.15f, 0.0f, 1.0f);
	const float Lift = 0.10f * Hover + ((bInside && bUiPressed) ? 0.10f : 0.0f);
	FLinearColor Fill = bAccent ? FLinearColor(FLsnUi::Amber().R * 0.9f, FLsnUi::Amber().G * 0.9f, FLsnUi::Amber().B * 0.9f, 1.0f) : bOn ? FLinearColor(0.16f, 0.19f, 0.24f, 0.92f) : FLinearColor(0.05f, 0.06f, 0.07f, 0.80f);
	Fill = FLinearColor(Fill.R + Lift, Fill.G + Lift, Fill.B + Lift, Fill.A);
	const FLinearColor Edge = bOn ? FLinearColor(1.0f, 1.0f, 1.0f, 0.55f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.16f + 0.25f * Hover);
	DrawRounded(Box, Fill, 6.0f, Edge);
	const FLinearColor Ink = bAccent ? FLinearColor(0.04f, 0.03f, 0.0f) : bEnabled ? FLsnUi::Ink() : FLinearColor(0.42f, 0.44f, 0.48f);
	const float LabelWidth = TypeWidth(Label, FLsnUi::Body), IconWidth = Icon.IsNone() ? 0.0f : U(28.0f);
	const float X0 = Box.Min.X + FMath::Max(0.5f * (Box.Max.X - Box.Min.X - LabelWidth - IconWidth), U(6.0f));
	const float CentreY = 0.5f * (Box.Min.Y + Box.Max.Y);
	if (!Icon.IsNone())
	{
		DrawIcon(Icon, FVector2D(X0 + U(10.0f), CentreY), Ink, bOn);
	}
	DrawType(Label, Ink, X0 + IconWidth, CentreY - U(0.62f * FLsnUi::Body), FLsnUi::Body);
}

void ALsnHud::DrawChip(const FBox2D& Box, const FLinearColor& Accent, FName Icon, const FString& Label, const FString& State, const FString& LeadIn, const FString& Duration, const TArray<FString>& Detail)
{
	// A dark panel with a bar of the state colour on the left, an icon, the state word, and the countdown as the largest thing.
	DrawPanel(Box);
	DrawRounded(FBox2D(FVector2D(Box.Min.X + U(1.0f), Box.Min.Y + U(8.0f)), FVector2D(Box.Min.X + U(5.0f), Box.Max.Y - U(8.0f))), Accent, 2.0f);
	const float X = Box.Min.X + U(20.0f), Width = Box.Max.X - X - U(12.0f);
	float Y = Box.Min.Y + U(12.0f);
	DrawIcon(Icon, FVector2D(X + U(9.0f), Y + U(15.0f)), Accent, false);
	const float LabelX = X + U(28.0f), LabelWidth = TypeWidth(Label, FLsnUi::Title, true);
	DrawType(Label, Accent, LabelX, Y, FLsnUi::Title, true);
	// The state word beside the label where it fits, under it where it does not.
	if (LabelX + LabelWidth + U(10.0f) + TypeWidth(State, FLsnUi::Title) <= Box.Max.X - U(12.0f))
	{
		DrawType(State, FLsnUi::Ink(), LabelX + LabelWidth + U(10.0f), Y, FLsnUi::Title);
		Y += U(32.0f);
	}
	else
	{
		Y += U(30.0f);
		for (const FString& Part : WrapLines(State, FLsnUi::Body, Width))
		{
			DrawType(Part, FLsnUi::Ink(), X, Y, FLsnUi::Body);
			Y += U(24.0f);
		}
	}
	if (!LeadIn.IsEmpty())
	{
		DrawType(LeadIn, FLsnUi::InkDim(), X, Y, FLsnUi::Body);
		Y += U(22.0f);
	}
	if (!Duration.IsEmpty())
	{
		// A countdown too long for a narrow chip is set one size smaller, so that it does not touch the edge.
		const bool bFits = DrawDuration(Duration, FLsnUi::Ink(), X, Y, FLsnUi::Display, false) <= Width;
		DrawDuration(Duration, FLsnUi::Ink(), X, Y + (bFits ? 0.0f : U(8.0f)), bFits ? FLsnUi::Display : FLsnUi::Title);
		Y += U(50.0f);
	}
	for (const FString& Line : Detail)
	{
		for (const FString& Part : WrapLines(Line, FLsnUi::Body, Width))
		{
			if (Y + U(22.0f) <= Box.Max.Y)
			{
				DrawType(Part, FLsnUi::InkDim(), X, Y, FLsnUi::Body);
			}
			Y += U(23.0f);
		}
	}
}

void ALsnHud::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas || !GEngine)
	{
		return;
	}
	// What this view draws goes to the interface's list of the frame; a widget over the game view paints it.
	FLsnUi::Get().BeginView(GFrameCounter);
	FLsnUi::Get().EnsureWidget(GetWorld());
	UiOrigin = FVector2D::ZeroVector;
	UiHeight = Canvas->SizeY;
	UFont* Font = nullptr;
	const ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>();
	const APlayerController* Player = GetOwningPlayerController();
	const bool bComparing = GameMode && GameMode->IsComparing();
	const int32 View = GameMode ? GameMode->GetViewIndexOf(Player) : 0;
	const float SizeX = Canvas->SizeX, SizeY = Canvas->SizeY;
	const float Scale = FLsnToolbar::TextScale(SizeX, SizeY);
	// Shared things (control bar, time strip, drawer) are laid out in the whole window and drawn by the left view.
	const float WindowX = bComparing ? 2.0f * SizeX : SizeX;
	const float ViewX0 = bComparing ? View * SizeX : 0.0f;
	// What a view draws is given in its own pixels; the list of the frame is in pixels of the window.
	UiOrigin = FVector2D(ViewX0, 0.0f);
	const float Margin = U(FLsnUi::SafeMargin);
	const float TypeL = 1.45f * Scale, TypeM = 1.12f * Scale, TypeS = 0.9f * Scale;

	// The pointer belongs to the left player; its position is in window pixels.
	const APlayerController* FirstPlayer = GetWorld()->GetFirstPlayerController();
	const double NowS = GetWorld()->GetRealTimeSeconds();
	UiDelta = FMath::Clamp(static_cast<float>(NowS - UiLastS), 0.0f, 0.1f);
	UiLastS = NowS;
	float MouseX = 0.0f, MouseY = 0.0f;
	UiMouse = FVector2D(-1.0e6, -1.0e6);
	if (FirstPlayer && FirstPlayer->bShowMouseCursor && FirstPlayer->GetMousePosition(MouseX, MouseY))
	{
		UiMouse = FVector2D(MouseX, MouseY);
		if (!UiMouse.Equals(UiMouseBefore, 0.5))
		{
			UiMouseMovedS = NowS;
			UiMouseBefore = UiMouse;
		}
	}
	bUiPressed = FirstPlayer && FirstPlayer->IsInputKeyDown(EKeys::LeftMouseButton);

	const ALsnSiteScene* Scene = GameMode ? GameMode->GetSceneOf(Player) : nullptr;
	if (!Scene)
	{
		for (TActorIterator<ALsnSiteScene> It(GetWorld()); It; ++It)
		{
			Scene = *It;
			break;
		}
	}
	if (!Scene || !Scene->HasPackage())
	{
		TArray<FLsnHudLine> Lines;
		Lines.Add({ TEXT("No package loaded."), Alert, FLsnUi::Title });
		if (GameMode)
		{
			Lines.Add({ GameMode->GetLoadError(), White, FLsnUi::Body });
		}
		DrawCard(Lines, Margin, Margin, SizeX - 2.0f * Margin);
		return;
	}
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();
	const double Position = Scene->GetTimePosition();
	const ALsnObserverPawn* Pawn = Cast<ALsnObserverPawn>(GetOwningPawn());
	// The left observer holds what both views share (drawer, help).
	const ALsnObserverPawn* LeftPawn = FirstPlayer ? Cast<ALsnObserverPawn>(FirstPlayer->GetPawn()) : Pawn;

	// For stills: no panels. A synthetic package keeps its marker; every still keeps a caption
	// that says which package, site and time it shows.
	if (FParse::Param(FCommandLine::Get(), TEXT("LsnNoHud")))
	{
		if (P.bSynthetic)
		{
			DrawType(FString::Printf(TEXT("%s - invented values for interface testing, not results"), LsnHudText::SyntheticMarker()), Alert, Margin, Margin, FLsnUi::Title);
		}
		const FString Viewpoint = (Pawn && Pawn->IsOverview()) ? (Pawn->GetCameraUpM() >= 1000.0 ? FString::Printf(TEXT("overview from %.0f km above the site, not the observer's view"), Pawn->GetCameraUpM() / 1000.0)
			: Pawn->IsArrivalRunning() ? FString(TEXT("camera move from high above down to the site; a camera move only, no descent is simulated"))
			: Pawn->GetCameraView() == ELsnCameraView::HeroLit ? FString(TEXT("camera on the lander's sunlit side, not the observer's view"))
			: Pawn->GetCameraView() == ELsnCameraView::Hero ? FString(TEXT("camera near the lander, not the observer's view")) : Pawn->GetCameraView() == ELsnCameraView::Wide ? FString(TEXT("wide view of the site, Sun outside the picture to the right; not the observer's view"))
			: FString::Printf(TEXT("camera %.0f m above and behind the observer, not the observer's view"), Pawn->GetCameraUpM()))
			: FString::Printf(TEXT("observer %.1f m"), P.ObserverHeightsM[H]);
		DrawType(FString::Printf(TEXT("%s   %s   %s   package %s (contract %s)"), *P.SiteName, *LsnHudText::UtcLabelOfPosition(P, Position), *Viewpoint, *P.PackageId, *P.ContractVersion)
			+ (Scene->IsFillForced() ? TEXT("   weak fill light on as a viewing aid: shadows are black without it") : TEXT("")),
			Dim, Margin, SizeY - Margin - U(20.0f), FLsnUi::Footnote);
		return;
	}

	// For the pitch clip: the view without its controls, with a caption that says what is shown.
	const bool bPresentation = FParse::Param(FCommandLine::Get(), TEXT("LsnPresentation"));
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	const bool bDetails = LeftPawn && LeftPawn->AreDetailsShown() && Page == ELsnPlannerPage::Summary;
	// The drawer is open while further controls, a page or the evidence is asked for.
	const bool bDrawer = !bPresentation && LeftPawn && (LeftPawn->AreControlsShown() || Page != ELsnPlannerPage::Summary || bDetails);
	const bool bControlsTab = bDrawer && Page == ELsnPlannerPage::Summary && !bDetails;
	const FLsnToolbar Toolbar = FLsnToolbar::Make(WindowX, SizeY, bComparing, bDrawer, bControlsTab);
	const bool bOverview = Pawn && Pawn->IsOverview();
	const double EtS = P.bHasTimeline ? P.EtOfPosition(Position) : 0.0;
	const int32 Sample = Scene->GetTimeIndex();

	// Side by side: a thin divider between the halves.
	if (bComparing && View == 0)
	{
		DrawRect(FLsnUi::Hairline(), SizeX - U(0.5f), 0.0f, FMath::Max(U(1.0f), 1.0f), SizeY);
	}

	// --- top left: site name, time, one line of coordinates and observer height -------------
	float NameY = Margin - U(8.0f);
	if (P.bSynthetic)
	{
		// The marker a synthetic package carries at all times (SPEC 3.3).
		DrawType(FString::Printf(TEXT("%s - invented values for interface testing, not results"), LsnHudText::SyntheticMarker()), Alert, Margin, NameY + U(6.0f), FLsnUi::Body, true);
		NameY += U(28.0f);
	}
	const float ChipGap = U(16.0f);
	const float ChipWidth = bComparing ? (SizeX - 2.0f * Margin - 2.0f * U(12.0f)) / 3.0f : U(392.0f), ChipHeight = U(196.0f);
	const float ChipsX0 = bComparing ? Margin : SizeX - Margin - 3.0f * ChipWidth - 2.0f * ChipGap;
	const float ChipsY0 = bComparing ? Margin + U(116.0f) : Margin;
	const float NameWidth = bComparing ? SizeX - 2.0f * Margin - U(166.0f) : ChipsX0 - Margin - U(24.0f);
	const TArray<FString> NameLines = WrapLines(P.SiteName, FLsnUi::Display, NameWidth);
	for (int32 I = 0; I < NameLines.Num() && I < (bComparing ? 1 : 2); ++I)
	{
		FString Line = NameLines[I];
		if (I == (bComparing ? 0 : 1) && NameLines.Num() > I + 1)
		{
			Line += TEXT("...");
		}
		DrawType(Line, White, Margin, NameY, FLsnUi::Display);
		NameY += U(46.0f);
	}
	const FString Utc = P.bHasTimeline ? LsnHudText::UtcLabelOfPosition(P, Position) : FString();
	const FString TimeText = !P.bHasTimeline ? FString(TEXT("terrain horizon only: no Sun or Earth timeline")) : Utc.IsEmpty() ? FString(TEXT("UTC label not available")) : Utc;
	DrawType(TimeText, White, Margin, NameY + U(2.0f), FLsnUi::Title);
	if (P.TerrainSource.bPresent)
	{
		// What elevation data the result rests on (since contract 0.9), as a small badge beside the time.
		const FString Badge = P.TerrainSource.PixelM > 0.0 ? FString::Printf(TEXT("%s terrain, %.0f m"), *P.TerrainSource.ResolutionClass, P.TerrainSource.PixelM) : P.TerrainSource.ResolutionClass + TEXT(" terrain");
		const float BadgeX = Margin + TypeWidth(TimeText, FLsnUi::Title) + U(16.0f), BadgeWidth = TypeWidth(Badge, FLsnUi::Body) + U(20.0f);
		if (BadgeX + BadgeWidth <= Margin + NameWidth + U(160.0f))
		{
			DrawRounded(FBox2D(FVector2D(BadgeX, NameY + U(2.0f)), FVector2D(BadgeX + BadgeWidth, NameY + U(32.0f))), FLinearColor(0.05f, 0.06f, 0.07f, 0.70f), 6.0f, FLsnUi::Hairline());
			DrawType(Badge, Dim, BadgeX + U(10.0f), NameY + U(5.0f), FLsnUi::Body);
		}
	}
	DrawType(FString::Printf(TEXT("lat %.4f   lon %.4f (east +)   observer %.1f m above the surface"), P.LatDeg, P.LonDeg, P.ObserverHeightsM[H]), Dim, Margin, NameY + U(38.0f), FLsnUi::Body);

	// --- top right: three state chips ---------------------------------------------------------
	const FLsnCountdown SunCountdown = P.bHasTimeline ? P.CountdownAt(TEXT("SUN"), H, EtS) : FLsnCountdown();
	const FLsnCountdown EarthCountdown = P.bHasTimeline ? P.CountdownAt(TEXT("EARTH"), H, EtS) : FLsnCountdown();
	int32 ChipIndex = 0;
	auto ChipBox = [&]()
	{
		const float X0 = ChipsX0 + ChipIndex * (ChipWidth + (bComparing ? U(12.0f) : ChipGap));
		++ChipIndex;
		return FBox2D(FVector2D(X0, ChipsY0), FVector2D(X0 + ChipWidth, ChipsY0 + ChipHeight));
	};
	auto BodyChip = [&](const TCHAR* Body, const TCHAR* Name, FName Icon, const FLsnCountdown& Countdown, const FLinearColor& Color)
	{
		if (!Countdown.bAvailable)
		{
			return;
		}
		FLsnBlocking Blocking;
		const bool bBlocked = P.BlockingAt(Body, H, Sample, Blocking) && Blocking.bHiddenOrPartly;
		const bool bPartly = bBlocked && Blocking.VisibleFraction > 0.0;
		const FString State = bPartly ? (100.0 * Blocking.VisibleFraction < 0.5 ? FString(TEXT("partly hidden, under 1 % visible")) : FString::Printf(TEXT("partly hidden, %.0f %% visible"), 100.0 * Blocking.VisibleFraction)) : Countdown.bVisibleNow ? FString(TEXT("visible")) : FString(TEXT("hidden"));
		const FString LeadIn = FString::Printf(TEXT("%s in%s"), Countdown.bVisibleNow ? TEXT("sets") : TEXT("rises"), Countdown.bLowerBound ? TEXT(" at least") : TEXT(""));
		TArray<FString> Detail;
		// With a stated error the event is a range, not an instant.
		const FLsnEvent* Event = LsnPlanner::EventEndingCountdown(P, Body, H, EtS, Countdown);
		if (Event && Event->bHasBand && Event->LatestEtS > Event->EarliestEtS && Event->bHasTerrainQuality && FMath::IsFinite(Event->QualityHeightErrorM))
		{
			// Since 0.10: the band of the event for the height error of the terrain pixel it rests on.
			const double Error = Event->QualityHeightErrorM;
			Detail.Add(FString::Printf(TEXT("uncertainty: %s to %s (%s m terrain)"), *LsnHudText::FormatDuration(Event->EarliestEtS - EtS), *LsnHudText::FormatDuration(Event->LatestEtS - EtS),
				FMath::IsNearlyEqual(Error, FMath::RoundToDouble(Error), 0.05) ? *FString::Printf(TEXT("%.0f"), Error) : *FString::Printf(TEXT("%.1f"), Error)));
		}
		else if (Event && Event->bHasBand && Event->LatestEtS > Event->EarliestEtS && P.Uncertainty.bHasHorizonError)
		{
			Detail.Add(FString::Printf(TEXT("uncertainty: %s to %s (horizon +/- %.2f deg)"), *LsnHudText::FormatDuration(Event->EarliestEtS - EtS), *LsnHudText::FormatDuration(Event->LatestEtS - EtS), P.Uncertainty.HorizonErrorDeg));
		}
		else if (Countdown.bLowerBound)
		{
			Detail.Add(TEXT("no such event in the computed range"));
		}
		// The bar carries the body's colour while the body is visible.
		DrawChip(ChipBox(), Countdown.bVisibleNow ? Color : FLinearColor(0.45f, 0.47f, 0.50f), Icon, Name, State, LeadIn, LsnHudText::FormatDuration(Countdown.SecondsToChange), Detail);
	};
	BodyChip(TEXT("SUN"), TEXT("SUN"), TEXT("sun"), SunCountdown, SunColor);
	BodyChip(TEXT("EARTH"), TEXT("EARTH"), TEXT("earth"), EarthCountdown, EarthColor);
	const FLsnRequirement* Requirement = P.Requirements.Num() > 0 ? &P.Requirements[(GameMode ? GameMode->GetRequirementIndex() : 0) % P.Requirements.Num()] : nullptr;
	const FLsnOpportunity* Opportunity = (Requirement && P.bHasTimeline) ? P.FindOpportunity(Requirement->Id, H) : nullptr;
	if (Opportunity)
	{
		const FLsnLandingCheck Check = LsnPlanner::LandingAt(*Opportunity, EtS);
		const bool bMet = Check.bJudgeable && Check.bFeasible;
		const FString State = !Check.bJudgeable ? FString(TEXT("cannot be judged")) : bMet ? FString(TEXT("requirement met")) : FString(TEXT("requirement not met"));
		const FString LeadIn = !Check.bJudgeable ? FString(TEXT("the stay runs past the computed range")) : bMet ? FString::Printf(TEXT("can slip%s"), Check.bSlipIsLowerBound ? TEXT(" at least") : TEXT(""))
			: Check.bHasNextWindow ? FString(TEXT("next window in")) : FString(TEXT("no window left in the computed range"));
		const FString Duration = !Check.bJudgeable ? FString() : bMet ? LsnHudText::FormatDuration(Check.SlipS) : Check.bHasNextWindow ? LsnHudText::FormatDuration(Check.WaitS) : FString();
		DrawChip(ChipBox(), bMet ? Good : Alert, TEXT("lander"), TEXT("LANDING NOW:"), State, LeadIn, Duration, { TEXT("Example requirement (team's choice)") });
	}

	// --- buttons -----------------------------------------------------------------------------
	if (!bPresentation)
	{
		DrawToolbar(Toolbar, ViewX0, *Scene, LeftPawn, GameMode, Scale);
	}

	// --- left column under the header: notices, what blocks the Sun or the Earth ---------------
	const float ColumnWidth = bComparing ? SizeX - 2.0f * Margin : U(640.0f);
	float Y = Toolbar.HeaderBottom + U(16.0f);
	TArray<FLsnHudLine> Notices;
	if (Pawn && !Pawn->GetCameraNote().IsEmpty())
	{
		Notices.Add({ Pawn->GetCameraNote(), White, FLsnUi::Body });
	}
	if (Scene->GetSkippedHorizonSamples() > 0)
	{
		Notices.Add({ FString::Printf(TEXT("%d horizon samples are unknown in the package and are not drawn."), Scene->GetSkippedHorizonSamples()), Alert, FLsnUi::Body });
	}
	if (bComparing && View == 1 && GameMode && !GameMode->IsRightViewInRange())
	{
		Notices.Add({ TEXT("The selected instant is outside this package's time range: this half shows its nearest sample."), Alert, FLsnUi::Body });
	}
	if (View == 0 && LeftPawn && LeftPawn->IsFirstDayPlaying() && P.Calendar.bPresent)
	{
		// What is being played, in one line: the dates and lengths are the package's.
		const FLsnOpportunity* WithLanding = P.Opportunities.FindByPredicate([](const FLsnOpportunity& O) { return O.Planned.bPresent; });
		const FLsnCalendarPeriod* FullDay = P.Calendar.Periods.FindByPredicate([](const FLsnCalendarPeriod& Day) { return Day.bComplete; });
		if (WithLanding && FullDay)
		{
			Notices.Add({ FString::Printf(TEXT("The first lunar day after the planned landing of %s UTC, played fast: %.1f days of what this site gives the mission."), *WithLanding->Planned.Utc.Left(16).Replace(TEXT("T"), TEXT(" ")),
				(FullDay->EndEtS - FullDay->StartEtS) / 86400.0), SunColor, FLsnUi::Body });
		}
	}
	for (const FString& Warning : P.Warnings)
	{
		Notices.Add({ FString::Printf(TEXT("Warning of the package: %s"), *Warning), Dim, FLsnUi::Body });
	}
	if (Scene->GetNearGroundShadeShare() >= 0.3 && !bOverview && !bPresentation)
	{
		// One short line: the chip says "visible" while the ground in the picture is dark.
		FLsnBodyAtTime SunLow;
		Scene->SampleBody(TEXT("SUN"), Position, SunLow);
		Notices.Add({ FString::Printf(TEXT("You are in sunlight; %.0f %% of the ground around you is not: the Sun is only %.1f deg high."), 100.0 * Scene->GetNearGroundShadeShare(), FMath::Abs(SunLow.ElevationDeg) < 0.05 ? 0.0 : SunLow.ElevationDeg), White, FLsnUi::Body });
	}
	const int32 SiteCount = GameMode ? GameMode->GetSites().Num() : 0;
	const int32 SiteIndex = GameMode ? GameMode->GetSelectedSite(View) : -1;
	bool bCustomProgress = false;
	float CustomShare = 0.0f;
	if (GameMode && View == 0 && SiteIndex >= 0 && GameMode->GetSites()[SiteIndex].Programme.StartsWith(TEXT("Custom")))
	{
		// Custom coordinates: what the two steps of the science core said, and how far the running one is.
		const FLsnCustomEntry& Entry = GameMode->GetCustomEntry();
		if (!Entry.HorizonLine.IsEmpty())
		{
			Notices.Add({ Entry.HorizonLine, Good, FLsnUi::Body });
		}
		if (Entry.bRunning && Entry.Step == 2)
		{
			Notices.Add({ Entry.Message, SunColor, FLsnUi::Body });
			bCustomProgress = true;
			CustomShare = static_cast<float>(LsnPlanner::StepShare(FPlatformTime::Seconds() - Entry.StartedS, Entry.StatedS));
		}
		else if (!Entry.TimelineLine.IsEmpty())
		{
			Notices.Add({ Entry.TimelineLine, Entry.bFailed ? Alert : P.bHasTimeline ? Good : Dim, FLsnUi::Body });
		}
	}
	if (!P.bHasTimeline)
	{
		Notices.Add({ TEXT("This package has no timeline: no Sun or Earth is shown."), Dim, FLsnUi::Body });
	}
	if (!bPresentation && Notices.Num() > 0)
	{
		Y = DrawCard(Notices, Margin, Y, ColumnWidth);
		if (bCustomProgress)
		{
			DrawRounded(FBox2D(FVector2D(Margin, Y), FVector2D(Margin + ColumnWidth, Y + U(8.0f))), FLinearColor(1.0f, 1.0f, 1.0f, 0.12f), 4.0f);
			DrawRounded(FBox2D(FVector2D(Margin, Y), FVector2D(Margin + ColumnWidth * CustomShare, Y + U(8.0f))), SunColor, 4.0f);
			Y += U(16.0f);
		}
	}
	const FLsnTimeStripLayout Layout = FLsnTimeStripLayout::Make(WindowX, SizeY, P, bComparing, !bPresentation);
	// --- the drawer, from the right: pages, sites, evidence, further controls ---------------
	if (View == 0)
	{
		DrawerAnim = FMath::Clamp(DrawerAnim + (bDrawer ? 1.0f : -1.0f) * UiDelta / 0.18f, 0.0f, 1.0f);
	}
	if (View == 0 && bDrawer && GameMode)
	{
		const FBox2D Drawer = FLsnToolbar::DrawerBox(WindowX, SizeY, bComparing);
		const FBox2D Content = FLsnToolbar::DrawerContent(WindowX, SizeY, bComparing);
		const float InnerX = Content.Min.X, InnerWidth = Content.Max.X - Content.Min.X;
		float InnerY = Content.Min.Y;
		if (Page == ELsnPlannerPage::Sites)
		{
			DrawSitePicker(WindowX, ViewX0, *GameMode, Scale);
		}
		else if (Page == ELsnPlannerPage::Calendar)
		{
			// Side by side the chart has a row for each site on one time axis.
			TArray<const ALsnSiteScene*> Rows = { Scene };
			if (bComparing && GameMode->GetSceneOfView(1) && GameMode->GetSceneOfView(1)->HasPackage())
			{
				Rows.Add(GameMode->GetSceneOfView(1));
			}
			DrawCalendar(Content, Rows, GameMode->GetRequirementIndex(), Scale);
		}
		else if (Page == ELsnPlannerPage::Uncertainty)
		{
			DrawUncertainty(*Scene, InnerX, InnerY, InnerWidth, Scale);
		}
		else if (Page == ELsnPlannerPage::Trade)
		{
			DrawTrade(*Scene, *GameMode, InnerX, InnerY, InnerWidth, Scale);
		}
		else if (bDetails)
		{
			// Evidence: where every number comes from, and how far it has been checked. Complete and unchanged.
			TArray<FLsnHudLine> Lines;
			LsnHudText::BuildStatusLines(P, H, Position, Lines, Scene->GetGroundNote());
			if (SiteIndex >= 0 && SiteCount > 0)
			{
				Lines.Add({ FString::Printf(TEXT("site %d of %d in the package root"), SiteIndex + 1, SiteCount), Dim, 1.0f });
			}
			if (Pawn)
			{
				Lines.Add({ FString::Printf(TEXT("looking az %.2f  el %.2f   field of view %.1f deg%s"), Pawn->GetAzimuthDeg(), Pawn->GetElevationDeg(), Pawn->GetFovDeg(),
					Pawn->IsFollowingSun() ? TEXT("   view follows the Sun's azimuth") : TEXT("")), Dim, 1.0f });
			}
			if (SunCountdown.bAvailable || EarthCountdown.bAvailable)
			{
				const FString Method = SunCountdown.bAvailable ? SunCountdown.Method : EarthCountdown.Method;
				Lines.Add({ FString::Printf(TEXT("countdowns: package windows sun_visible / earth_visible, TDB   [%s: %s]"), *Method, *P.ValidationStatusOf(Method)), Dim, 1.0f });
			}
			for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
			{
				const FLsnCountdown& Countdown = FCString::Stricmp(Body, TEXT("SUN")) == 0 ? SunCountdown : EarthCountdown;
				const FLsnEvent* Event = Countdown.bAvailable ? LsnPlanner::EventEndingCountdown(P, Body, H, EtS, Countdown) : nullptr;
				const FString Quality = Event ? LsnPlanner::TerrainQualityPhrase(*Event) : FString();
				if (!Quality.IsEmpty())
				{
					Lines.Add({ FString::Printf(TEXT("the next %s event rests on a %s%s"), Body, *Quality, Event->QualityProductId.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Event->QualityProductId)), Dim, 1.0f });
				}
			}
			// What hides a body now, and what that obstacle costs, in full: the package's own blocker (SPEC 5.5).
			for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
			{
				FLsnBlocking Blocking;
				TArray<FString> Sentences;
				if (P.bHasTimeline && P.BlockingAt(Body, H, Sample, Blocking))
				{
					LsnHudText::BlockerSentences(Body, P, Blocking, Sentences);
					for (int32 I = 0; I < Sentences.Num(); ++I)
					{
						Lines.Add({ Sentences[I], I == 2 ? Alert : White, 1.0f });
					}
				}
			}
			if (!P.BlockingMethod.IsEmpty())
			{
				Lines.Add({ FString::Printf(TEXT("what blocks a body and its cost: package blockers   [%s: %s]"), *P.BlockingMethod, *P.ValidationStatusOf(P.BlockingMethod)), Dim, 1.0f });
			}
			if (P.Uncertainty.bHasHorizonError)
			{
				Lines.Add({ FString::Printf(TEXT("ranges for the stated horizon error of %.2f deg   [%s]"), P.Uncertainty.HorizonErrorDeg, *P.ValidationStatusOf(P.Uncertainty.HorizonMethod)), Dim, 1.0f });
			}
			if (P.Calendar.bPresent)
			{
				Lines.Add({ FString::Printf(TEXT("lunar-day calendar, %s to %s: share of each lunar day with the Sun and with the Earth visible   [%s]"), *P.Time.StartUtc.Left(10), *P.Time.EndUtc.Left(10), *P.ValidationStatusOf(P.Calendar.Method)), Dim, 1.0f });
			}
			if (P.Uncertainty.bHasEllipse)
			{
				Lines.Add({ FString::Printf(TEXT("survey of the stated landing ellipse   [%s]"), *P.ValidationStatusOf(P.Uncertainty.EllipseMethod)), Dim, 1.0f });
			}
			if (const FLsnHeightTradeQuantity* TradeSun = P.HeightTrade.bPresent ? P.HeightTrade.Find(TEXT("sun_visible_s")) : nullptr)
			{
				Lines.Add({ FString::Printf(TEXT("mast-height trade   [%s]"), *P.ValidationStatusOf(TradeSun->Method)), Dim, 1.0f });
			}
			if (Opportunity)
			{
				FString Summary = FString::Printf(TEXT("landing possible in %.1f %% of the range that can be judged (%d windows, longest %s)"), 100.0 * Opportunity->FeasibleFraction,
					Opportunity->WindowCount, *LsnHudText::FormatDuration(Opportunity->LongestWindowS));
				if (Opportunity->Planned.bPresent)
				{
					// The slip report of the scenario's planned landing, as the package gives it.
					const FLsnSlipReport& Planned = Opportunity->Planned;
					Summary += FString::Printf(TEXT("; planned landing %s (green line of the calendar): %s"), *Planned.Utc.Left(16).Replace(TEXT("T"), TEXT(" ")),
						Planned.bFeasible ? *FString::Printf(TEXT("meets it, can slip %s%s"), Planned.bSlipIsLowerBound ? TEXT("at least ") : TEXT(""), *LsnHudText::FormatDuration(Planned.SlipToleranceS))
						: Planned.bHasWait ? *FString::Printf(TEXT("does not meet it, next window after %s"), *LsnHudText::FormatDuration(Planned.WaitS)) : TEXT("does not meet it, no window left"));
				}
				Lines.Add({ Summary, Dim, 1.0f });
				Lines.Add({ FString::Printf(TEXT("landing windows of the example requirement '%s': %s   [%s]"), *Requirement->Id, *Requirement->Label, *P.ValidationStatusOf(Opportunity->Method)), Dim, 1.0f });
				Lines.Add({ TEXT("The example requirement is the team's choice for showing the tool. It is not a requirement of NASA or of any mission."), White, 1.0f });
			}
			DrawType(TEXT("Evidence"), White, InnerX, InnerY, FLsnUi::Title, true);
			InnerY += U(36.0f);
			for (const FLsnHudLine& Line : Lines)
			{
				for (const FString& Part : WrapLines(Line.Text, FLsnUi::Footnote, InnerWidth))
				{
					if (InnerY + U(19.0f) > Content.Max.Y)
					{
						break;
					}
					DrawType(Part, Line.Color == FLinearColor::White ? White : Line.Color, InnerX, InnerY, FLsnUi::Footnote);
					InnerY += U(19.0f);
				}
				InnerY += U(3.0f);
			}
		}
		else if (!bComparing && P.bHasTimeline)
		{
			// Under the further controls: the horizon all round and the numbers of the whole computed window.
			float Lowest = Content.Min.Y;
			for (const FLsnButton& Button : Toolbar.Buttons)
			{
				if (Button.Style == ELsnButtonStyle::Bar && Button.Box.Min.X >= Drawer.Min.X)
				{
					Lowest = FMath::Max(Lowest, static_cast<float>(Button.Box.Max.Y));
				}
			}
			FLsnPanorama Pano;
			LsnPlanner::PanoramaRange(P, H, Pano.MinElevationDeg, Pano.MaxElevationDeg);
			Pano.Box = FBox2D(FVector2D(InnerX, Lowest + U(40.0f)), FVector2D(InnerX + InnerWidth, Lowest + U(112.0f)));
			if (Pano.Box.Max.Y + U(60.0f) <= Content.Max.Y)
			{
				DrawType(TEXT("HORIZON ALL ROUND"), Dim, InnerX, Lowest + U(14.0f), FLsnUi::Footnote);
				DrawPanorama(Pano, *Scene, Pawn, Scale);
				TArray<FString> Metrics;
				LsnPlanner::BuildMetricLines(P, H, Metrics);
				float MetricY = Pano.Box.Max.Y + U(28.0f);
				DrawType(FString::Printf(TEXT("WHOLE COMPUTED WINDOW   %s to %s"), *P.Time.StartUtc.Left(10), *P.Time.EndUtc.Left(10)), Dim, InnerX, MetricY, FLsnUi::Footnote);
				MetricY += U(22.0f);
				for (const FString& Metric : Metrics)
				{
					for (const FString& Part : WrapLines(Metric, FLsnUi::Body, InnerWidth))
					{
						if (MetricY + U(24.0f) <= Content.Max.Y)
						{
							DrawType(Part, White, InnerX, MetricY, FLsnUi::Body);
						}
						MetricY += U(24.0f);
					}
				}
			}
		}
	}
	if (!P.bHasTimeline)
	{
		if (View == 0 && LeftPawn && LeftPawn->IsHelpShown())
		{
			DrawHelp(SizeX, SizeY, Scale);
		}
		return;
	}

	// --- the Sun outside the picture: one click turns the view to it ---------------------------
	if (View == 0 && LeftPawn && LeftPawn->IsSunOutOfView() && !bOverview && !bPresentation)
	{
		DrawButton(FLsnToolbar::LookAtSunBox(WindowX, SizeY, bComparing), TEXT("The Sun is outside the picture: look at it"), TEXT("sun"), false, true, false, TEXT("look_at_sun"));
	}

	// A label card at the peak of each highlighted obstacle, and an outline where the hidden body stands.
	for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
	{
		FLsnBlocking Blocking;
		if (bOverview || !Scene->IsObstacleViewEnabled() || !P.BlockingAt(Body, H, Sample, Blocking) || !Blocking.bHiddenOrPartly || !Blocking.Obstacle)
		{
			continue;
		}
		const bool bSun = FCString::Stricmp(Body, TEXT("SUN")) == 0;
		const FLinearColor Outline = bSun ? SunColor : EarthColor;
		FLsnBodyAtTime At;
		if (Scene->SampleBody(Body, Position, At) && At.bHasAngularRadius)
		{
			const FVector Centre = Project(Scene->GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(At.AzimuthDeg, At.ElevationDeg) * 1.0e6, false);
			const FVector Rim = Project(Scene->GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(At.AzimuthDeg, At.ElevationDeg + At.AngularRadiusDeg) * 1.0e6, false);
			if (Centre.Z > 0.0 && Rim.Z > 0.0)
			{
				const float Radius = FMath::Max(static_cast<float>(FVector2D::Distance(FVector2D(Centre.X, Centre.Y), FVector2D(Rim.X, Rim.Y))), U(4.0f));
				const int32 Segments = 48;
				for (int32 I = 0; I < Segments; I += 2)  // dashed
				{
					const float A0 = 2.0f * UE_PI * I / Segments, A1 = 2.0f * UE_PI * (I + 1) / Segments;
					DrawLine(Centre.X + Radius * FMath::Cos(A0), Centre.Y + Radius * FMath::Sin(A0), Centre.X + Radius * FMath::Cos(A1), Centre.Y + Radius * FMath::Sin(A1), Outline, U(1.5f));
				}
				// The label stays out of the open drawer.
				const FString Behind = FString::Printf(TEXT("%s (behind terrain)"), bSun ? TEXT("Sun") : TEXT("Earth"));
				const float LabelRight = (bDrawer && View == (bComparing ? 1 : 0)) ? static_cast<float>(FLsnToolbar::DrawerBox(WindowX, SizeY, bComparing).Min.X) - ViewX0 - U(8.0f) : SizeX - Margin;
				const float LabelX = Centre.X + Radius + U(8.0f) + TypeWidth(Behind, FLsnUi::Body) <= LabelRight ? Centre.X + Radius + U(8.0f) : Centre.X - Radius - U(8.0f) - TypeWidth(Behind, FLsnUi::Body);
				DrawType(Behind, Outline, LabelX, Centre.Y - U(11.0f), FLsnUi::Body);
			}
		}
		const FVector Peak = Project(Scene->GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(Blocking.Obstacle->PeakAzimuthDeg, Blocking.Obstacle->PeakElevationDeg) * 1.0e6, false);
		if (Peak.Z <= 0.0 || Peak.X < 0.0 || Peak.X > SizeX || Peak.Y < 0.0 || Peak.Y > SizeY)
		{
			continue;
		}
		// The cost in hours is the large thing; distance and azimuth stand under it. A leader line runs to the ridge.
		const FString Distance = Blocking.Obstacle->PeakDistanceM < 1000.0 ? FString::Printf(TEXT("%.0f m"), Blocking.Obstacle->PeakDistanceM) : FString::Printf(TEXT("%.1f km"), Blocking.Obstacle->PeakDistanceM / 1000.0);
		const FString Head = Blocking.Blocker ? FString(TEXT("this ridge costs")) : FString::Printf(TEXT("this ridge hides the %s now"), bSun ? TEXT("Sun") : TEXT("Earth"));
		const FString Cost = Blocking.Blocker ? FString::Printf(TEXT("%.0f h of %s"), Blocking.Blocker->LostS / 3600.0, bSun ? TEXT("Sun") : TEXT("Earth")) : FString();
		const FString Detail = FString::Printf(TEXT("%s away, azimuth %.1f deg"), *Distance, Blocking.Obstacle->PeakAzimuthDeg);
		const float CardWidth = FMath::Max3(TypeWidth(Head, FLsnUi::Body), TypeWidth(Detail, FLsnUi::Body), TypeWidth(Cost, FLsnUi::Display)) + U(28.0f);
		const float CardHeight = U(Cost.IsEmpty() ? 68.0f : 116.0f);
		// Above the ridge, centred over its peak, never on the outline (the peak is the highest point of
		// it); clear of the drawer and of the cards of the left column.
		const float RightLimit = (bDrawer && !bComparing ? static_cast<float>(FLsnToolbar::DrawerBox(WindowX, SizeY, bComparing).Min.X) - U(16.0f) : SizeX - Margin) - CardWidth;
		const float CardX = FMath::Clamp(Peak.X - 0.5f * CardWidth, Margin, FMath::Max(RightLimit, Margin));
		const float TopLimit = CardX < Margin + ColumnWidth + U(8.0f) ? FMath::Max(Y, Toolbar.HeaderBottom + U(16.0f)) : Toolbar.HeaderBottom + U(16.0f);
		const float CardY = FMath::Max(Peak.Y - U(56.0f) - CardHeight, TopLimit);
		if (CardY + CardHeight > Peak.Y - U(10.0f))
		{
			// No room above the ridge in this picture: no card rather than one on the outline.
			continue;
		}
		DrawLine(Peak.X, Peak.Y - U(4.0f), FMath::Clamp(Peak.X, CardX + U(12.0f), CardX + CardWidth - U(12.0f)), CardY + CardHeight, FLinearColor(Outline.R, Outline.G, Outline.B, 0.85f), U(1.5f));
		DrawDisc(FVector2D(Peak.X, Peak.Y - U(4.0f)), U(3.5f), Outline);
		DrawPanel(FBox2D(FVector2D(CardX, CardY), FVector2D(CardX + CardWidth, CardY + CardHeight)));
		DrawRounded(FBox2D(FVector2D(CardX + U(1.0f), CardY + U(8.0f)), FVector2D(CardX + U(5.0f), CardY + CardHeight - U(8.0f))), Outline, 2.0f);
		float LineY = CardY + U(10.0f);
		DrawType(Head, Dim, CardX + U(16.0f), LineY, FLsnUi::Body);
		LineY += U(24.0f);
		if (!Cost.IsEmpty())
		{
			DrawDuration(Cost, White, CardX + U(16.0f), LineY, FLsnUi::Display);
			LineY += U(50.0f);
		}
		DrawType(Detail, White, CardX + U(16.0f), LineY, FLsnUi::Body);
	}

	// --- bottom: the time strip in its panel ---------------------------------------------------
	const float RowHeight = U(36.0f);
	const FBox2D Rows(FVector2D(Layout.Zoom.Min.X, Layout.Zoom.Min.Y + (bComparing ? View * U(44.0f) : 0.0f)), FVector2D(Layout.Zoom.Max.X, Layout.Zoom.Min.Y + (bComparing ? View * U(44.0f) : 0.0f) + RowHeight));
	if (View == 0)
	{
		DrawPanel(Layout.Panel);
	}
	// Shared things are laid out in window pixels: taken back by the origin of this view.
	const FBox2D RowsHere(Rows.Min - FVector2D(ViewX0, 0.0f), Rows.Max - FVector2D(ViewX0, 0.0f));
	DrawStrip(RowsHere, P, H, Position - Layout.ZoomHalfWidthSamples, Position + Layout.ZoomHalfWidthSamples, Position, Scale);
	if (View == 0)
	{
		// Tick marks at every UTC midnight with the date; the playhead carries its own time.
		const float StripWidth = Layout.Zoom.Max.X - Layout.Zoom.Min.X;
		const float TickY = Layout.Zoom.Max.Y + U(4.0f);
		FDateTime Start;
		if (P.Time.LeapSecondsInRange == 0 && P.Time.StepS > 0.0 && FDateTime::ParseIso8601(*P.Time.StartUtc, Start))
		{
			static const TCHAR* Months[] = { TEXT("Jan"), TEXT("Feb"), TEXT("Mar"), TEXT("Apr"), TEXT("May"), TEXT("Jun"), TEXT("Jul"), TEXT("Aug"), TEXT("Sep"), TEXT("Oct"), TEXT("Nov"), TEXT("Dec") };
			const double From = Position - Layout.ZoomHalfWidthSamples, To = Position + Layout.ZoomHalfWidthSamples;
			const FDateTime FromTime = Start + FTimespan::FromSeconds(P.Time.StepS * From);
			FDateTime Midnight(FromTime.GetYear(), FromTime.GetMonth(), FromTime.GetDay());
			for (int32 Day = 0; Day < 40; ++Day)
			{
				Midnight += FTimespan::FromDays(1.0);
				const double At = (Midnight - Start).GetTotalSeconds() / P.Time.StepS;
				if (At > To)
				{
					break;
				}
				if (At < 0.0 || At > P.Time.Count - 1)
				{
					continue;
				}
				const float X = Layout.Zoom.Min.X + StripWidth * static_cast<float>((At - From) / (To - From));
				DrawLine(X, Layout.Zoom.Min.Y - U(4.0f), X, TickY + U(6.0f), FLinearColor(1.0f, 1.0f, 1.0f, 0.35f), U(1.0f));
				const FString Label = FString::Printf(TEXT("%d %s"), Midnight.GetDay(), Months[Midnight.GetMonth() - 1]);
				if (X + TypeWidth(Label, FLsnUi::Body) + U(6.0f) < Layout.Zoom.Max.X)
				{
					DrawType(Label, Dim, X + U(6.0f), TickY + U(2.0f), FLsnUi::Body);
				}
			}
		}
		if (bComparing && GameMode)
		{
			// Which pair of rows is which site.
			for (int32 Half = 0; Half < 2; ++Half)
			{
				const ALsnSiteScene* Other = GameMode->GetSceneOfView(Half);
				if (Other && Other->HasPackage())
				{
					FString Name = Other->GetPackage().SiteName;
					while (TypeWidth(Name, FLsnUi::Footnote) > U(208.0f) && Name.Len() > 4)
					{
						Name = Name.LeftChop(5).TrimEnd() + TEXT("...");
					}
					DrawType(Name, White, Layout.Panel.Min.X + U(16.0f), Layout.Zoom.Min.Y + Half * U(44.0f) + U(8.0f), FLsnUi::Footnote);
				}
			}
		}
		const float Cursor = 0.5f * (Layout.Zoom.Min.X + Layout.Zoom.Max.X);
		DrawRect(White, Cursor - U(1.0f), Layout.Panel.Min.Y - U(6.0f), U(2.0f), Layout.Zoom.Max.Y - Layout.Panel.Min.Y + U(12.0f));
		const FString Now = LsnHudText::UtcLabelOfPosition(P, Position);
		if (!Now.IsEmpty())
		{
			const float LabelWidth = TypeWidth(Now, FLsnUi::Body) + U(24.0f);
			const FBox2D Label(FVector2D(Cursor - 0.5f * LabelWidth, Layout.Panel.Min.Y - U(42.0f)), FVector2D(Cursor + 0.5f * LabelWidth, Layout.Panel.Min.Y - U(8.0f)));
			DrawPanel(Label);
			DrawType(Now, White, Label.Min.X + U(12.0f), Label.Min.Y + U(5.0f), FLsnUi::Body);
		}
	}
	if (bPresentation)
	{
		// A caption across the window says what is shown.
		FString Caption;
		if (View == 0 && FParse::Value(FCommandLine::Get(), TEXT("LsnCaption="), Caption, false) && GameMode)
		{
			// "first|second": the second text from the moment the package gives the Sun of the left site as hidden.
			FString First = Caption, Second;
			Caption.Split(TEXT("|"), &First, &Second);
			const ALsnSiteScene* LeftScene = GameMode->GetSceneOfView(0);
			const bool bLeftSunDown = LeftScene && LeftScene->HasPackage() && LeftScene->GetSunVisibleFraction() <= 0.0;
			const FString Text = (bLeftSunDown && !Second.IsEmpty()) ? Second : First;
			const TArray<FString> Parts = WrapLines(Text, FLsnUi::Title, WindowX - 2.0f * Margin - U(48.0f));
			const float BandHeight = U(24.0f + 34.0f * Parts.Num());
			const float BandTop = Layout.Panel.Min.Y - U(64.0f) - BandHeight;
			float Widest = 0.0f;
			for (const FString& Part : Parts)
			{
				Widest = FMath::Max(Widest, TypeWidth(Part, FLsnUi::Title));
			}
			DrawPanel(FBox2D(FVector2D(0.5f * (WindowX - Widest) - U(24.0f), BandTop), FVector2D(0.5f * (WindowX + Widest) + U(24.0f), BandTop + BandHeight)));
			for (int32 I = 0; I < Parts.Num(); ++I)
			{
				DrawType(Parts[I], White, 0.5f * (WindowX - TypeWidth(Parts[I], FLsnUi::Title)), BandTop + U(12.0f + 34.0f * I), FLsnUi::Title);
			}
		}
		return;
	}
	if (View == 0)
	{
		// One line that says how to use the view: it fades out five seconds after the pointer last moved.
		const bool bPlayingNow = LeftPawn && LeftPawn->IsPlaying();
		const FString Hint = bPlayingNow ? FString::Printf(TEXT("Playing: %.1f h of site time per second"), LeftPawn->GetPlayRateSamplesPerSecond() * P.Time.StepS / 3600.0)
			: FString(TEXT("Drag the strip to change the time. Right mouse button: look round."));
		const float Target = (bPlayingNow || NowS - UiMouseMovedS < 5.0) ? 1.0f : 0.0f;
		HintAlpha = FMath::Clamp(HintAlpha + (Target > HintAlpha ? 1.0f : -1.0f) * UiDelta / 0.2f, 0.0f, 1.0f);
		if (HintAlpha > 0.0f)
		{
			DrawType(Hint, FLinearColor(Dim.R, Dim.G, Dim.B, HintAlpha), Margin, Toolbar.Top - U(46.0f), FLsnUi::Body);
		}
		if (LeftPawn && LeftPawn->IsHelpShown())
		{
			DrawHelp(SizeX, SizeY, Scale);
		}
	}
}

void ALsnHud::DrawToolbar(const FLsnToolbar& Toolbar, float ViewX0, const ALsnSiteScene& Scene, const ALsnObserverPawn* Pawn, const ALsnViewGameMode* GameMode, float Scale)
{
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	const bool bComparing = GameMode && GameMode->IsComparing();
	const int32 View = ViewX0 > 0.0f ? 1 : 0;
	const bool bDetails = Pawn && Pawn->AreDetailsShown() && Page == ELsnPlannerPage::Summary;
	const bool bDrawer = Pawn && (Pawn->AreControlsShown() || Page != ELsnPlannerPage::Summary || bDetails);
	if (View == 0 && bDrawer)
	{
		// The drawer slides in from the right; its buttons are where they will be clicked.
		const FBox2D Drawer = FLsnToolbar::DrawerBox(bComparing ? 2.0f * Canvas->SizeX : Canvas->SizeX, Canvas->SizeY, bComparing);
		const float Slide = (1.0f - DrawerAnim) * U(120.0f);
		DrawPanel(FBox2D(Drawer.Min + FVector2D(Slide, 0.0f), Drawer.Max + FVector2D(Slide, 0.0f)));
		for (const FLsnButtonGroupLabel& Label : Toolbar.GroupLabels)
		{
			DrawType(Label.Text, FLsnUi::InkDim(), Label.Position.X, Label.Position.Y + U(4.0f), FLsnUi::Footnote);
		}
	}
	const bool bHasTimeline = Scene.GetPackage().bHasTimeline;
	for (const FLsnButton& Button : Toolbar.Buttons)
	{
		// The left view draws everything that is shared; the right view its own control.
		const FName A = Button.Action;
		if ((A == TEXT("next_right_site")) != (View == 1))
		{
			continue;
		}
		// A button that is a switch is drawn with a brighter edge while it is on.
		const bool bOn = (A == TEXT("play") && Pawn && Pawn->IsPlaying()) || (A == TEXT("compare") && bComparing)
			|| (A == TEXT("page_calendar") && Page == ELsnPlannerPage::Calendar) || (A == TEXT("page_uncertainty") && Page == ELsnPlannerPage::Uncertainty)
			|| (A == TEXT("page_trade") && Page == ELsnPlannerPage::Trade) || (A == TEXT("page_sites") && Page == ELsnPlannerPage::Sites) || (A == TEXT("obstacle") && Scene.IsObstacleViewEnabled())
			|| (A == TEXT("follow_sun") && Pawn && Pawn->IsFollowingSun()) || (A == TEXT("quality") && GameMode && GameMode->IsLowQuality())
			|| (A == TEXT("scale_objects") && Scene.AreScaleObjectsVisible()) || (A == TEXT("fill_light") && Scene.IsFillLightVisible())
			|| (A == TEXT("details") && bDetails) || (A == TEXT("help") && Pawn && Pawn->IsHelpShown())
			|| (A == TEXT("controls_tab") && bDrawer && Page == ELsnPlannerPage::Summary && !bDetails) || (A == TEXT("controls") && bDrawer)
			|| (A == TEXT("camera") && Pawn && Pawn->GetCameraView() != ELsnCameraView::Observer) || (A == TEXT("arrival") && Pawn && Pawn->IsArrivalRunning())
			|| (A == TEXT("first_day") && Pawn && Pawn->IsFirstDayPlaying());
		// What needs the timeline of the package is shown as not available without one.
		const bool bNeedsTimeline = A == TEXT("play") || A == TEXT("next_sunset") || A == TEXT("slower") || A == TEXT("faster") || A == TEXT("sample_back") || A == TEXT("sample_forward") || A == TEXT("day_back")
			|| A == TEXT("day_forward") || A == TEXT("sun_event_back") || A == TEXT("sun_event_forward") || A == TEXT("first_day");
		FString Label = Button.Label;
		if (A == TEXT("play") && bOn) { Label = TEXT("Pause"); }
		if (A == TEXT("compare") && bComparing) { Label = TEXT("One site"); }
		if (A == TEXT("controls") && bDrawer) { Label = TEXT("Less"); }
		const FBox2D Box(Button.Box.Min - FVector2D(ViewX0, 0.0f), Button.Box.Max - FVector2D(ViewX0, 0.0f));
		const bool bIcon = Button.Style != ELsnButtonStyle::Tab && Button.Group.IsEmpty();
		DrawButton(Box, Label, bIcon ? A : NAME_None, bOn, bHasTimeline || !bNeedsTimeline, false, A);
	}
}

void ALsnHud::DrawSitePicker(float WindowSizeX, float ViewX0, const ALsnViewGameMode& GameMode, float Scale)
{
	TArray<FString> Groups;
	for (const FLsnSiteInfo& Info : GameMode.GetSiteInfos())
	{
		Groups.Add(Info.Group);
	}
	const bool bComparing = GameMode.IsComparing();
	const TArray<bool> Hidden = GameMode.GetSitesHiddenBySearch();
	const FLsnSitePicker Picker = FLsnSitePicker::Make(WindowSizeX, Canvas->SizeY, bComparing, Groups, &Hidden, GameMode.GetPickerFirstRow());
	const FLsnCustomEntry& Entry = GameMode.GetCustomEntry();
	const FVector2D Mouse = UiMouse;
	DrawType(TEXT("Sites"), White, Picker.TitlePosition.X, Picker.TitlePosition.Y - U(4.0f), FLsnUi::Title, true);
	const FString Count = FString::Printf(TEXT("%d of %d rows; the wheel scrolls"), FMath::Min(Picker.FirstRow + Picker.Rows.Num(), Picker.NumRows), Picker.NumRows);
	DrawType(Count, Dim, Picker.Sheet.Max.X - TypeWidth(Count, FLsnUi::Footnote), Picker.TitlePosition.Y + U(4.0f), FLsnUi::Footnote);

	// The search field: what is typed narrows the list by name, programme and category.
	const bool bSearchFocus = Entry.Focus == 2;
	DrawRounded(Picker.SearchField, FLinearColor(0.02f, 0.02f, 0.03f, 0.85f), 6.0f, bSearchFocus ? FLinearColor(1.0f, 1.0f, 1.0f, 0.6f) : FLsnUi::Hairline());
	const bool bCaretOn = FMath::Fmod(GetWorld()->GetRealTimeSeconds(), 1.0) < 0.5;
	const FString& Search = GameMode.GetSiteSearch();
	DrawType(Search.IsEmpty() && !bSearchFocus ? FString(TEXT("Search: click here and type a name, a programme or a category")) : Search + ((bSearchFocus && bCaretOn) ? TEXT("_") : TEXT("")),
		Search.IsEmpty() && !bSearchFocus ? Dim : White, Picker.SearchField.Min.X + U(12.0f), Picker.SearchField.Min.Y + U(6.0f), FLsnUi::Body);

	const int32 LeftSite = GameMode.GetSelectedSite(0), RightSite = bComparing ? GameMode.GetSelectedSite(1) : -1;
	for (const FLsnPickerRow& Row : Picker.Rows)
	{
		const float X0 = Row.Row.Min.X, TextY = Row.Row.Min.Y + U(4.0f);
		if (Row.SiteIndex < 0)
		{
			DrawType(Row.Group.ToUpper(), Dim, X0, TextY + U(6.0f), FLsnUi::Footnote, true);
			DrawLine(X0 + TypeWidth(Row.Group.ToUpper(), FLsnUi::Footnote, true) + U(10.0f), Row.Row.Min.Y + U(20.0f), Row.Row.Max.X, Row.Row.Min.Y + U(20.0f), FLsnUi::Hairline(), U(1.0f));
			continue;
		}
		const bool bLeft = Row.SiteIndex == LeftSite, bRight = Row.SiteIndex == RightSite;
		if (Row.Row.IsInside(Mouse) || bLeft || bRight)
		{
			DrawRounded(Row.Show, Row.Row.IsInside(Mouse) ? FLinearColor(1.0f, 1.0f, 1.0f, 0.10f) : FLinearColor(1.0f, 1.0f, 1.0f, 0.05f), 4.0f);
		}
		// The name; the category; the resolution class of the terrain behind the result as a small badge (since contract 0.9).
		const FLsnSiteInfo& Info = GameMode.GetSiteInfos()[Row.SiteIndex];
		const FLsnIndexEntry& Site = GameMode.GetSites()[Row.SiteIndex];
		const FString Class = Info.TerrainSource.bPresent ? FString::Printf(TEXT("%s %.0f m"), *Info.TerrainSource.ResolutionClass, Info.TerrainSource.PixelM) : FString();
		const float BadgeWidth = Class.IsEmpty() ? 0.0f : TypeWidth(Class, FLsnUi::Footnote) + U(16.0f);
		const float CategoryWidth = Site.Category.IsEmpty() ? 0.0f : TypeWidth(Site.Category, FLsnUi::Footnote) + U(16.0f);
		const float NameRight = Row.Show.Max.X - BadgeWidth - CategoryWidth - U(12.0f);
		FString Name = Site.Name;
		while (TypeWidth(Name, FLsnUi::Body) > NameRight - X0 - U(8.0f) && Name.Len() > 4)
		{
			Name = Name.LeftChop(5).TrimEnd() + TEXT("...");
		}
		DrawType(Name, White, X0 + U(8.0f), TextY, FLsnUi::Body);
		float BadgeX = Row.Show.Max.X - BadgeWidth - U(4.0f);
		if (!Class.IsEmpty())
		{
			DrawRounded(FBox2D(FVector2D(BadgeX, Row.Row.Min.Y + U(5.0f)), FVector2D(BadgeX + BadgeWidth, Row.Row.Max.Y - U(5.0f))), FLinearColor(0.0f, 0.0f, 0.0f, 0.0f), 5.0f, FLinearColor(1.0f, 1.0f, 1.0f, 0.30f));
			DrawType(Class, White, BadgeX + U(8.0f), Row.Row.Min.Y + U(8.0f), FLsnUi::Footnote);
		}
		if (!Site.Category.IsEmpty())
		{
			BadgeX -= CategoryWidth;
			DrawType(Site.Category, Dim, BadgeX + U(4.0f), Row.Row.Min.Y + U(8.0f), FLsnUi::Footnote);
		}
		DrawButton(Row.PinLeft, TEXT("Left"), NAME_None, bLeft, true, false, FName(*FString::Printf(TEXT("pin_left_%d"), Row.SiteIndex)));
		DrawButton(Row.PinRight, TEXT("Right"), NAME_None, bRight, true, false, FName(*FString::Printf(TEXT("pin_right_%d"), Row.SiteIndex)));
	}

	// Custom coordinates: handed to the science core, which must be on this machine.
	DrawLine(Picker.Sheet.Min.X, Picker.EntryLabelPosition.Y - U(8.0f), Picker.Sheet.Max.X, Picker.EntryLabelPosition.Y - U(8.0f), FLsnUi::Hairline(), U(1.0f));
	DrawType(TEXT("Custom coordinates"), White, Picker.EntryLabelPosition.X, Picker.EntryLabelPosition.Y - U(2.0f), FLsnUi::Body, true);
	DrawType(TEXT("computed by the science core on this machine; Tab changes the field, Enter computes"), Dim, Picker.EntryLabelPosition.X + TypeWidth(TEXT("Custom coordinates"), FLsnUi::Body, true) + U(12.0f),
		Picker.EntryLabelPosition.Y + U(2.0f), FLsnUi::Footnote);
	const TPair<const FBox2D*, const TCHAR*> Fields[] = { { &Picker.LatField, TEXT("latitude") }, { &Picker.LonField, TEXT("longitude E") } };
	for (int32 I = 0; I < 2; ++I)
	{
		const FBox2D& Box = *Fields[I].Key;
		const bool bFocus = Entry.Focus == I;
		DrawType(Fields[I].Value, Dim, Box.Min.X - TypeWidth(Fields[I].Value, FLsnUi::Footnote) - U(8.0f), Box.Min.Y + U(9.0f), FLsnUi::Footnote);
		DrawRounded(Box, FLinearColor(0.02f, 0.02f, 0.03f, 0.85f), 6.0f, bFocus ? FLinearColor(1.0f, 1.0f, 1.0f, 0.6f) : FLsnUi::Hairline());
		const FString& Value = I == 0 ? Entry.Latitude : Entry.Longitude;
		DrawType(Value + ((bFocus && bCaretOn) ? TEXT("_") : TEXT("")), White, Box.Min.X + U(10.0f), Box.Min.Y + U(6.0f), FLsnUi::Body);
	}
	// The one accent button of the screen.
	DrawButton(Picker.Compute, Entry.bRunning ? TEXT("Computing ...") : TEXT("Compute and show"), NAME_None, false, !Entry.bRunning, true, TEXT("custom_compute"));
	float MessageY = Picker.MessagePosition.Y;
	for (const FString& Part : WrapLines(Entry.Message, FLsnUi::Footnote, Picker.Sheet.Max.X - Picker.Sheet.Min.X))
	{
		if (MessageY + U(18.0f) <= Picker.Sheet.Max.Y + U(8.0f))
		{
			DrawType(Part, Entry.bFailed ? FLsnUi::Red() : Entry.bRunning ? FLsnUi::Amber() : FLsnUi::Green(), Picker.MessagePosition.X, MessageY, FLsnUi::Footnote);
		}
		MessageY += U(18.0f);
	}
}

void ALsnHud::DrawHelp(float SizeX, float SizeY, float Scale)
{
	static const TCHAR* Lines[] = {
		TEXT("Mouse"),
		TEXT("  click a button; a lit button is switched on"),
		TEXT("  drag on a time strip: choose the time"),
		TEXT("  hold the right button and move: look round      wheel: zoom"),
		TEXT("Keys"),
		TEXT("  arrow keys  look          Z / X  zoom          Tab  hide the cursor, look with the mouse alone"),
		TEXT("  Space  play and pause      [ / ]  slower / faster"),
		TEXT("  Q / E  one step back / forward (Shift: 24 steps)      , / .  one day back / forward"),
		TEXT("  B / N  previous / next rise or set of the Sun (Shift: of the Earth)      Home / End  first / last sample"),
		TEXT("  1 .. 9  show that site (Shift: on the right, side by side)      C  two sites side by side"),
		TEXT("  K  calendar and landing windows      U  uncertainty      M  mast-height trade and site pairs      R  next requirement"),
		TEXT("  O  obstacle view      F  keep the view on the Sun      PageUp / PageDown  observer height"),
		TEXT("  H  horizon line of the package      L  fill light while the Sun is down (a display aid)      G  lower drawing quality"),
		TEXT("  V  camera: observer, near the lander, wide      A  arrival camera move      D  play the first lunar day after the planned landing"),
		TEXT("  T  all controls on and off      I  details: package, frame, contract, test status      P  scale objects (lander, boulders)"),
		TEXT("  S  site list, pinning two sites, custom coordinates"),
		TEXT("  F1  this list      Esc  quit"),
	};
	UFont* Font = GEngine->GetMediumFont();
	const float TextSize = Scale * 1.05f, LineHeight = 21.0f * Scale;
	float Width = 0.0f;
	for (const TCHAR* Text : Lines)
	{
		float W = 0.0f, H = 0.0f;
		GetTextSize(Text, W, H, Font, TextSize);
		Width = FMath::Max(Width, W);
	}
	// Made smaller where the list is wider than the view.
	const float Fit = FMath::Min(1.0f, (SizeX - 60.0f * Scale) / FMath::Max(Width, 1.0f));
	Width *= Fit;
	const float Height = UE_ARRAY_COUNT(Lines) * LineHeight * Fit;
	const float X = 0.5f * (SizeX - Width), Y0 = 0.5f * (SizeY - Height);
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.97f), X - 16.0f * Scale, Y0 - 14.0f * Scale, Width + 32.0f * Scale, Height + 28.0f * Scale);
	float Y = Y0;
	for (const TCHAR* Text : Lines)
	{
		DrawText(Text, Text[0] == TEXT(' ') ? White : SunColor, X, Y, Font, TextSize * Fit);
		Y += LineHeight * Fit;
	}
}

float ALsnHud::DrawWrapped(const FString& Text, const FLinearColor& Color, float X, float Y, float MaxWidth, float TextScale)
{
	UFont* Font = GEngine->GetMediumFont();
	FString Rest = Text;
	while (!Rest.IsEmpty())
	{
		FString Part = Rest;
		float Width = 0.0f, Height = 0.0f;
		GetTextSize(Part, Width, Height, Font, TextScale);
		while (Width > MaxWidth)
		{
			int32 Space = INDEX_NONE;
			if (!Part.FindLastChar(TEXT(' '), Space) || Space <= 0)
			{
				break;
			}
			Part.LeftInline(Space);
			GetTextSize(Part, Width, Height, Font, TextScale);
		}
		DrawText(Part, Color, X, Y, Font, TextScale);
		Y += 1.35f * SizeOfScale(TextScale);
		Rest = Part.Len() < Rest.Len() ? Rest.Mid(Part.Len()).TrimStart() : FString();
	}
	return Y;
}

void ALsnHud::DrawCalendar(const FBox2D& Box, const TArray<const ALsnSiteScene*>& Rows, int32 RequirementIndex, float Scale)
{
	UFont* Font = nullptr;
	// The scale of the old calls that gives the text size of the design system.
	const float TextM = 1.12f * Scale;
	const float Width = Box.Max.X - Box.Min.X;
	if (Rows.Num() == 0 || Box.Max.Y - Box.Min.Y < 60.0f * Scale)
	{
		return;
	}
	const FLsnSitePackage& First = Rows[0]->GetPackage();
	float Y = Box.Min.Y;
	if (!First.Calendar.bPresent)
	{
		// The field is absent: say so once instead of drawing an empty chart.
		DrawWrapped(FString::Printf(TEXT("The package of this site (contract %s) has no lunar-day calendar; there is nothing to show here."), *First.ContractVersion), Dim, Box.Min.X, Y, Width, Scale * 1.1f);
		return;
	}
	// One time axis for all rows: that of the first package. The lunar days do not depend on the site.
	const double AxisStart = First.EtOfPosition(0.0), AxisEnd = First.EtOfPosition(First.Time.Count - 1);
	auto X = [&](double EtS) { return Box.Min.X + Width * static_cast<float>(FMath::Clamp((EtS - AxisStart) / (AxisEnd - AxisStart), 0.0, 1.0)); };

	const FLsnRequirement* Requirement = First.Requirements.Num() > 0 ? &First.Requirements[RequirementIndex % First.Requirements.Num()] : nullptr;
	DrawType(TEXT("Calendar"), White, Box.Min.X, Y - U(4.0f), FLsnUi::Title, true);
	const FString Range = FString::Printf(TEXT("lunar days, %s to %s"), *First.Time.StartUtc.Left(10), *First.Time.EndUtc.Left(10));
	DrawType(Range, Dim, Box.Max.X - TypeWidth(Range, FLsnUi::Body), Y + U(2.0f), FLsnUi::Body);
	Y += U(40.0f);
	// One row of legend: what each mark of the chart is.
	{
		float LegendX = Box.Min.X;
		const float MarkY = Y + U(11.0f);
		DrawRect(SunColor, LegendX, MarkY - U(7.0f), U(14.0f), U(14.0f));
		LegendX += U(22.0f);
		DrawType(TEXT("Sun share"), White, LegendX, Y, FLsnUi::Body);
		LegendX += TypeWidth(TEXT("Sun share"), FLsnUi::Body) + U(24.0f);
		DrawRect(EarthColor, LegendX, MarkY - U(1.5f), U(18.0f), U(3.0f));
		LegendX += U(26.0f);
		DrawType(TEXT("Earth share"), White, LegendX, Y, FLsnUi::Body);
		LegendX += TypeWidth(TEXT("Earth share"), FLsnUi::Body) + U(24.0f);
		DrawRect(Good, LegendX, MarkY - U(3.0f), U(18.0f), U(6.0f));
		LegendX += U(26.0f);
		DrawType(TEXT("landing windows"), White, LegendX, Y, FLsnUi::Body);
		LegendX += TypeWidth(TEXT("landing windows"), FLsnUi::Body) + U(24.0f);
		DrawRect(White, LegendX, MarkY - U(9.0f), U(2.0f), U(18.0f));
		LegendX += U(10.0f);
		DrawType(TEXT("selected instant"), White, LegendX, Y, FLsnUi::Body);
	}
	Y += U(36.0f);
	(void)Requirement;

	const float TextBlock = U(104.0f);
	const float RowHeight = FMath::Clamp((Box.Max.Y - Y) / Rows.Num() - TextBlock, U(60.0f), U(260.0f));
	for (const ALsnSiteScene* Row : Rows)
	{
		const FLsnSitePackage& P = Row->GetPackage();
		const int32 H = Row->GetHeightIndex();
		DrawFit(FString::Printf(TEXT("%s, observer %.1f m"), *P.SiteName, P.ObserverHeightsM[H]), White, Box.Min.X, Y, Width, TextM);
		Y += U(28.0f);
		const FLsnCalendarQuantity* SunQ = P.Calendar.bPresent ? P.Calendar.Find(TEXT("sun_visible_s")) : nullptr;
		const FLsnCalendarQuantity* EarthQ = P.Calendar.bPresent ? P.Calendar.Find(TEXT("earth_visible_s")) : nullptr;
		if (!SunQ)
		{
			DrawText(TEXT("no calendar in this package"), Dim, Box.Min.X, Y, Font, TextM);
			Y += RowHeight + TextBlock - U(28.0f);
			continue;
		}
		const float BarTop = Y, BarBottom = Y + RowHeight;
		for (int32 Period = 0; Period < P.Calendar.Periods.Num(); ++Period)
		{
			const FLsnCalendarPeriod& Day = P.Calendar.Periods[Period];
			const double Length = Day.EndEtS - Day.StartEtS;
			if (!(Length > 0.0))
			{
				continue;
			}
			const float X0 = X(Day.StartEtS), X1 = FMath::Max(X(Day.EndEtS) - 1.0f, X0 + 1.0f);
			// A lunar day cut by the ends of the range is drawn dimmer: its total is not that of a full day.
			const float Tone = Day.bComplete ? 1.0f : 0.45f;
			DrawRect(FLinearColor(0.10f, 0.10f, 0.12f, 1.0f), X0, BarTop, X1 - X0, RowHeight);
			const double SunShare = FMath::Clamp(P.Calendar.Value(*SunQ, H, Period) / Length, 0.0, 1.0);
			DrawRect(FLinearColor(SunColor.R * Tone, SunColor.G * Tone, SunColor.B * Tone, 1.0f), X0, BarBottom - RowHeight * static_cast<float>(SunShare), X1 - X0, RowHeight * static_cast<float>(SunShare));
			if (EarthQ)
			{
				const double EarthShare = FMath::Clamp(P.Calendar.Value(*EarthQ, H, Period) / Length, 0.0, 1.0);
				DrawRect(FLinearColor(EarthColor.R * Tone, EarthColor.G * Tone, EarthColor.B * Tone, 1.0f), X0, BarBottom - RowHeight * static_cast<float>(EarthShare) - 1.5f * Scale, X1 - X0, 3.0f * Scale);
			}
			if (Period % 4 == 0 && Row == Rows[0] && X0 + U(76.0f) <= Box.Max.X)
			{
				// Axis labels at the size of the text.
				DrawText(Day.StartUtc.Left(7), Dim, X0, BarBottom + U(12.0f), Font, TextM);
			}
		}
		// Landing windows of the requirement, the planned landing and the selected time, on the same axis.
		const FLsnRequirement* Mine = P.Requirements.Num() > 0 ? &P.Requirements[RequirementIndex % P.Requirements.Num()] : nullptr;
		const FLsnOpportunity* Opportunity = Mine ? P.FindOpportunity(Mine->Id, H) : nullptr;
		const double NowEt = P.EtOfPosition(Row->GetTimePosition());
		if (Opportunity)
		{
			for (int32 I = 0; I < Opportunity->StartsEtS.Num(); ++I)
			{
				const float X0 = X(Opportunity->StartsEtS[I]), X1 = X(Opportunity->EndsEtS[I]);
				DrawRect(Good, X0, BarBottom + 2.0f * Scale, FMath::Max(X1 - X0, 2.0f), 6.0f * Scale);
			}
			// Beyond latest_landing nothing can be judged.
			DrawRect(FLinearColor(0.3f, 0.3f, 0.3f, 0.6f), X(Opportunity->LatestLandingEtS), BarBottom + 2.0f * Scale, Box.Max.X - X(Opportunity->LatestLandingEtS), 6.0f * Scale);
			if (Opportunity->Planned.bPresent)
			{
				const float PlannedX = X(Opportunity->Planned.EtS);
				DrawLine(PlannedX, BarTop - 4.0f * Scale, PlannedX, BarBottom + 9.0f * Scale, FLinearColor(0.3f, 1.0f, 0.5f), 2.0f * Scale);
			}
		}
		const float NowX = X(NowEt);
		DrawRect(FLinearColor::White, NowX - Scale, BarTop - 4.0f * Scale, 2.0f * Scale, RowHeight + 14.0f * Scale);
		Y = BarBottom + U(Row == Rows[0] ? 40.0f : 14.0f);
		if (Opportunity)
		{
			const FLsnLandingCheck Check = LsnPlanner::LandingAt(*Opportunity, NowEt);
			// The result sentence, one line. The numbers behind it are in the evidence of the drawer.
			const FString Result = !Check.bJudgeable ? FString(TEXT("Landing now cannot be judged: the stay runs past the computed range"))
				: Check.bFeasible ? FString::Printf(TEXT("Landing now: requirement met; it can slip %s%s"), Check.bSlipIsLowerBound ? TEXT("at least ") : TEXT(""), *LsnHudText::FormatDuration(Check.SlipS))
				: Check.bHasNextWindow ? FString::Printf(TEXT("Landing now: requirement not met; next window in %s"), *LsnHudText::FormatDuration(Check.WaitS)) : FString(TEXT("Landing now: requirement not met; no window left in the range"));
			DrawFit(Result, !Check.bJudgeable ? Dim : Check.bFeasible ? Good : Lost, Box.Min.X, Y, Width, TextM);
			Y += U(34.0f);
		}
		else
		{
			DrawText(TEXT("this package states no requirement: no landing windows"), Dim, Box.Min.X, Y, Font, TextM);
			Y += U(34.0f);
		}
	}
}

float ALsnHud::DrawUncertainty(const ALsnSiteScene& Scene, float X, float Y, float Width, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	const FLsnSitePackage& P = Scene.GetPackage();
	const FLsnUncertainty& U = P.Uncertainty;
	if (!U.bHasHorizonError && !U.bHasEllipse)
	{
		return DrawWrapped(FString::Printf(TEXT("The package of this site (contract %s) states no horizon error and no landing ellipse; there is no band to show."), *P.ContractVersion), Dim, X, Y, Width, Scale);
	}
	if (U.bHasHorizonError)
	{
		Y = DrawWrapped(FString::Printf(TEXT("Stated horizon error %.2f deg: the pale edges of the time strips and the ranges under the countdowns"), U.HorizonErrorDeg), White, X, Y, Width, Scale * 1.1f);
		Y = DrawWrapped(U.HorizonAssumption, Dim, X, Y, Width, Scale * 0.85f);
		Y += 8.0f * Scale;
	}
	if (U.bHasEllipse)
	{
		const FLsnEllipseStats* Stats = U.EllipseStats.Find(TEXT("SUN"));
		Y = DrawWrapped(FString::Printf(TEXT("Stated landing ellipse %.1f x %.1f km, major axis towards azimuth %.0f deg, %d sample points, observer %.1f m"), 2.0 * U.SemiMajorM / 1000.0, 2.0 * U.SemiMinorM / 1000.0,
			U.AzimuthDeg, U.Points.Num(), P.ObserverHeightsM.IsValidIndex(U.EllipseHeightIndex) ? P.ObserverHeightsM[U.EllipseHeightIndex] : 0.0), White, X, Y, Width, Scale * 1.1f);
		// Small map: the sample points east and north of the site, coloured by their Sun-visible time.
		const float Side = FMath::Min(Width * 0.42f, 190.0f * Scale);
		const FVector2D Centre(X + 0.5f * Side, Y + 0.5f * Side + 4.0f * Scale);
		DrawRect(FLinearColor(0.03f, 0.03f, 0.04f, 0.9f), Centre.X - 0.5f * Side, Centre.Y - 0.5f * Side, Side, Side);
		const FLsnSiteFrame& Frame = Scene.GetFrame();
		const float MetresToPixels = U.SemiMajorM > 0.0 ? 0.44f * Side / static_cast<float>(U.SemiMajorM) : 0.0f;
		for (const FLsnEllipsePoint& Point : U.Points)
		{
			const FVector2D EastNorth = LsnPlanner::EllipsePointEastNorthM(Frame, Point);
			const double* Seconds = Point.VisibleS.Find(TEXT("SUN"));
			FLinearColor Color(0.35f, 0.35f, 0.35f);  // a point without a complete horizon has no value
			if (Seconds && Stats && Stats->MaxS > Stats->MinS)
			{
				const float T = static_cast<float>((*Seconds - Stats->MinS) / (Stats->MaxS - Stats->MinS));
				Color = FLinearColor(0.25f + 0.75f * T, 0.2f + 0.62f * T, 0.45f - 0.2f * T);
			}
			else if (Seconds)
			{
				Color = SunColor;
			}
			const float Half = 4.0f * Scale;
			DrawRect(Color, Centre.X + static_cast<float>(EastNorth.X) * MetresToPixels - Half, Centre.Y - static_cast<float>(EastNorth.Y) * MetresToPixels - Half, 2.0f * Half, 2.0f * Half);
		}
		DrawText(TEXT("N"), Dim, Centre.X - 4.0f * Scale, Centre.Y - 0.5f * Side + 1.0f * Scale, Font, Scale * 0.8f);
		float TextY = Centre.Y - 0.5f * Side;
		const float TextX = X + Side + 10.0f * Scale, TextWidth = Width - Side - 10.0f * Scale;
		if (Stats)
		{
			TextY = DrawWrapped(TEXT("Sun-visible time over the computed window at the sample points (dark: least, bright: most):"), Dim, TextX, TextY, TextWidth, Scale * 0.9f);
			TextY = DrawWrapped(FString::Printf(TEXT("site %.0f h"), Stats->CentreS / 3600.0), White, TextX, TextY, TextWidth, Scale * 1.2f);
			TextY = DrawWrapped(FString::Printf(TEXT("least %.0f h   median %.0f h   most %.0f h"), Stats->MinS / 3600.0, Stats->MedianS / 3600.0, Stats->MaxS / 3600.0), White, TextX, TextY, TextWidth, Scale * 1.2f);
		}
		const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
		if (Sun && Sun->EllipseVisibleShare.IsValidIndex(Scene.GetTimeIndex()))
		{
			TextY = DrawWrapped(FString::Printf(TEXT("at sample %d the Sun is visible at %.0f %% of the points"), Scene.GetTimeIndex(), 100.0f * Sun->EllipseVisibleShare[Scene.GetTimeIndex()]), SunColor, TextX, TextY, TextWidth, Scale * 1.1f);
		}
		TextY = DrawWrapped(TEXT("A survey of the ellipse, not a probability."), Dim, TextX, TextY, TextWidth, Scale * 0.9f);
		Y = FMath::Max(TextY, Centre.Y + 0.5f * Side) + 6.0f * Scale;
		Y = DrawWrapped(U.EllipseAssumption, Dim, X, Y, Width, Scale * 0.85f);
	}
	return Y;
}

float ALsnHud::DrawTrade(const ALsnSiteScene& Scene, const ALsnViewGameMode& GameMode, float X, float Y, float Width, float Scale)
{
	const FLsnSitePackage& P = Scene.GetPackage();
	TArray<FString> Lines;
	LsnPlanner::BuildHeightTradeLines(P, Lines);
	if (Lines.Num() > 0)
	{
		Y = DrawWrapped(Lines[0], Dim, X, Y, Width, Scale * 0.9f);
		for (int32 I = 1; I < Lines.Num(); ++I)
		{
			// The height the view is drawn for is marked.
			const bool bShown = I - 1 == Scene.GetHeightIndex();
			Y = DrawWrapped((bShown ? TEXT("> ") : TEXT("   ")) + Lines[I].TrimStart(), bShown ? White : FLinearColor(0.8f, 0.8f, 0.8f), X, Y, Width, Scale * 1.1f);
		}
		Y = DrawWrapped(TEXT("Sun-visible time and longest time without Sun over the computed window; in brackets the change against the lowest height, hours."), Dim, X, Y, Width, Scale * 0.85f);
	}
	else
	{
		Y = DrawWrapped(FString::Printf(TEXT("The package of this site (contract %s) has no mast-height trade."), *P.ContractVersion), Dim, X, Y, Width, Scale);
	}
	Y += 10.0f * Scale;

	const FLsnSitePairs* Pairs = GameMode.GetSitePairs();
	if (!Pairs)
	{
		return DrawWrapped(TEXT("The package root has no site-pairs package."), Dim, X, Y, Width, Scale);
	}
	// Pairs are shown only for the very site packages they were computed from.
	const FString* Mine = Pairs->SitePackageIds.Find(P.SiteId);
	if (!Mine || *Mine != P.PackageId)
	{
		return DrawWrapped(TEXT("The site-pairs package of the root was computed from another package of this site; it is not shown."), Alert, X, Y, Width, Scale);
	}
	const FString* Status = Pairs->MethodStatus.Find(TEXT("pairs.complementarity"));
	Y = DrawWrapped(FString::Printf(TEXT("site pairs: when at least one of two sites sees the body (not: that power or data can be moved between them)   [%s]"), Status ? **Status : TEXT("unknown")), Dim, X, Y, Width, Scale * 0.9f);
	const ALsnSiteScene* Other = GameMode.IsComparing() ? GameMode.GetSceneOfView(1 - Scene.GetSceneSlot()) : nullptr;
	for (const FLsnSitePair& Pair : Pairs->Pairs)
	{
		if (Pair.SiteA != P.SiteId && Pair.SiteB != P.SiteId)
		{
			continue;
		}
		const FString& Partner = Pair.SiteA == P.SiteId ? Pair.SiteB : Pair.SiteA;
		// Side by side, only the pair on screen; alone, every pair of this site.
		if (Other && Other->HasPackage() && Other->GetPackage().SiteId != Partner)
		{
			continue;
		}
		LsnPlanner::BuildPairLines(Pair, Lines);
		Y = DrawWrapped(FString::Printf(TEXT("with %s, %s"), *Partner, Lines.Num() > 0 ? *Lines[0] : TEXT("")), White, X, Y, Width, Scale * 1.1f);
		for (int32 I = 1; I < Lines.Num(); ++I)
		{
			Y = DrawWrapped(TEXT("   ") + Lines[I], FLinearColor(0.85f, 0.85f, 0.85f), X, Y, Width, Scale);
		}
	}
	return Y;
}
