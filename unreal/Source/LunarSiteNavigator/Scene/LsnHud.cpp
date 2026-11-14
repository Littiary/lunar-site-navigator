#include "Scene/LsnHud.h"

#include "Engine/Canvas.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Planner/LsnPlanner.h"
#include "Scene/LsnObserverPawn.h"
#include "Scene/LsnSiteScene.h"
#include "Scene/LsnViewGameMode.h"

namespace
{
	const FLinearColor White(0.92f, 0.92f, 0.92f);
	const FLinearColor Dim(0.6f, 0.6f, 0.6f);
	const FLinearColor Alert(1.0f, 0.35f, 0.2f);
	const FLinearColor SunColor(1.0f, 0.82f, 0.25f);
	const FLinearColor EarthColor(0.35f, 0.65f, 1.0f);
	const FLinearColor Good(0.55f, 1.0f, 0.6f);
	const FLinearColor Lost(1.0f, 0.55f, 0.25f);
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
	return FMath::Clamp(FMath::Min(SizeY / 720.0f, SizeX / 1000.0f), 0.55f, 4.0f);
}

float FLsnToolbar::BarTop(float SizeY)
{
	const float ButtonHeight = FMath::Max(0.036f * SizeY, 23.0f), LabelHeight = 0.021f * SizeY, Gap = 0.004f * SizeY;
	return 0.992f * SizeY - 2.0f * (ButtonHeight + LabelHeight) - Gap;
}

FLsnToolbar FLsnToolbar::Make(float WindowSizeX, float SizeY, bool bComparing)
{
	FLsnToolbar Toolbar;
	const float W = WindowSizeX, H = SizeY;
	// The header holds the site name, the time and the state chips: one line of chips beside
	// the name in a wide view, a line of their own in the half views.
	Toolbar.HeaderBottom = (bComparing ? 0.190f : 0.122f) * H;
	Toolbar.Top = BarTop(H);

	// The three main actions, under the header on the left.
	static const TPair<const TCHAR*, const TCHAR*> Main[] = {
		{ TEXT("compare"), TEXT("Compare two sites") }, { TEXT("next_sunset"), TEXT("Jump to next sunset") }, { TEXT("obstacle"), TEXT("What blocks the Sun?") },
	};
	const float MainTop = Toolbar.HeaderBottom + 0.012f * H, MainHeight = 0.062f * H, MainWidth = 0.150f * W, MainGap = 0.006f * W;
	for (int32 I = 0; I < UE_ARRAY_COUNT(Main); ++I)
	{
		const float X0 = 0.012f * W + I * (MainWidth + MainGap);
		Toolbar.Buttons.Add({ Main[I].Key, Main[I].Value, FBox2D(FVector2D(X0, MainTop), FVector2D(X0 + MainWidth, MainTop + MainHeight)), ELsnButtonStyle::Main, FString() });
	}

	// The bar: two rows of ten, each under a line of group labels. Ten cells between 6 % and
	// 94 % of the window, so that no button lies across the middle of a side-by-side window.
	struct FEntry { const TCHAR* Action; const TCHAR* Label; const TCHAR* Group; };
	static const FEntry Rows[2][10] = {
		{ { TEXT("play"), TEXT("Play / pause"), TEXT("TIME") }, { TEXT("slower"), TEXT("Slower"), TEXT("TIME") }, { TEXT("faster"), TEXT("Faster"), TEXT("TIME") },
		  { TEXT("sample_back"), TEXT("< Step"), TEXT("TIME") }, { TEXT("sample_forward"), TEXT("Step >"), TEXT("TIME") }, { TEXT("day_back"), TEXT("< Day"), TEXT("TIME") },
		  { TEXT("day_forward"), TEXT("Day >"), TEXT("TIME") }, { TEXT("sun_event_back"), TEXT("< Sunrise / set"), TEXT("TIME") }, { TEXT("sun_event_forward"), TEXT("Sunrise / set >"), TEXT("TIME") },
		  { TEXT("height_next"), TEXT("Observer height"), TEXT("OBSERVER") } },
		{ { TEXT("page_sites"), TEXT("Sites ..."), TEXT("SITE") }, { TEXT("page_calendar"), TEXT("Calendar"), TEXT("PLAN") }, { TEXT("page_uncertainty"), TEXT("Uncertainty"), TEXT("PLAN") },
		  { TEXT("page_trade"), TEXT("Mast / pairs"), TEXT("PLAN") }, { TEXT("follow_sun"), TEXT("Follow Sun"), TEXT("VIEW") }, { TEXT("scale_objects"), TEXT("Scale objects"), TEXT("VIEW") },
		  { TEXT("fill_light"), TEXT("Night fill light"), TEXT("VIEW") }, { TEXT("quality"), TEXT("Low quality"), TEXT("VIEW") }, { TEXT("details"), TEXT("Details"), TEXT("INFO") },
		  { TEXT("help"), TEXT("Help (F1)"), TEXT("INFO") } },
	};
	const float ButtonHeight = FMath::Max(0.036f * H, 23.0f), LabelHeight = 0.021f * H, Gap = 0.004f * H;
	const float Left = 0.06f * W, Cell = 0.088f * W, Pad = 0.0025f * W;
	for (int32 Row = 0; Row < 2; ++Row)
	{
		const float RowTop = Toolbar.Top + LabelHeight + Row * (ButtonHeight + LabelHeight + Gap);
		for (int32 Column = 0; Column < 10; ++Column)
		{
			const FEntry& Entry = Rows[Row][Column];
			const float X0 = Left + Cell * Column;
			Toolbar.Buttons.Add({ Entry.Action, Entry.Label, FBox2D(FVector2D(X0 + Pad, RowTop), FVector2D(X0 + Cell - Pad, RowTop + ButtonHeight)), ELsnButtonStyle::Bar, Entry.Group });
			if (Column == 0 || FCString::Strcmp(Rows[Row][Column - 1].Group, Entry.Group) != 0)
			{
				Toolbar.GroupLabels.Add({ Entry.Group, FVector2D(X0 + Pad, RowTop - LabelHeight) });
			}
		}
	}

	// Side by side: the right view's own control, in its header.
	if (bComparing)
	{
		Toolbar.Buttons.Add({ TEXT("next_right_site"), TEXT("Next site >"), FBox2D(FVector2D(0.900f * W, 0.012f * H), FVector2D(0.988f * W, 0.052f * H)), ELsnButtonStyle::RightView, FString() });
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

FLsnSitePicker FLsnSitePicker::Make(float WindowSizeX, float SizeY, bool bComparing, const TArray<FString>& GroupOfSite)
{
	FLsnSitePicker Picker;
	const float W = WindowSizeX, H = SizeY;
	const FLsnToolbar Toolbar = FLsnToolbar::Make(W, H, bComparing);
	// Below the main buttons, above the time strips; side by side across both halves.
	const float StripsTop = FLsnToolbar::BarTop(H) - 0.126f * H;
	Picker.Sheet = FBox2D(FVector2D(0.012f * W, Toolbar.HeaderBottom + 0.086f * H), FVector2D(bComparing ? 0.988f * W : 0.685f * W, StripsTop - 0.034f * H));
	const float Pad = 0.008f * H, TitleHeight = 0.036f * H, FooterHeight = 0.090f * H;
	Picker.TitlePosition = FVector2D(Picker.Sheet.Min.X + Pad, Picker.Sheet.Min.Y + Pad);

	// The rows: a header where a group first appears, then its sites in the order of the list.
	TArray<FString> Groups;
	for (const FString& Group : GroupOfSite)
	{
		Groups.AddUnique(Group);
	}
	struct FItem { int32 Site; FString Group; };
	TArray<FItem> Items;
	for (const FString& Group : Groups)
	{
		Items.Add({ -1, Group });
		for (int32 I = 0; I < GroupOfSite.Num(); ++I)
		{
			if (GroupOfSite[I] == Group)
			{
				Items.Add({ I, Group });
			}
		}
	}
	const float RowsTop = Picker.Sheet.Min.Y + Pad + TitleHeight, RowsBottom = Picker.Sheet.Max.Y - Pad - FooterHeight;
	// A short list fills the first column before the next one is begun.
	const int32 FullColumn = FMath::Max(FMath::FloorToInt32((RowsBottom - RowsTop) / (0.032f * H)), 1);
	// Columns: two in one view; side by side two in each half, so that nothing lies across the middle.
	TArray<TPair<float, float>> Columns;
	const float Gap = 0.006f * W;
	if (bComparing && Items.Num() > 2 * FullColumn)
	{
		const float HalfLeft0 = Picker.Sheet.Min.X + Pad, HalfLeft1 = 0.5f * W - Gap, HalfRight0 = 0.5f * W + Gap, HalfRight1 = Picker.Sheet.Max.X - Pad;
		Columns.Add({ HalfLeft0, 0.5f * (HalfLeft0 + HalfLeft1) - 0.5f * Gap });
		Columns.Add({ 0.5f * (HalfLeft0 + HalfLeft1) + 0.5f * Gap, HalfLeft1 });
		Columns.Add({ HalfRight0, 0.5f * (HalfRight0 + HalfRight1) - 0.5f * Gap });
		Columns.Add({ 0.5f * (HalfRight0 + HalfRight1) + 0.5f * Gap, HalfRight1 });
	}
	else if (bComparing)
	{
		// A short list: one wide column in each half.
		Columns.Add({ Picker.Sheet.Min.X + Pad, 0.5f * W - Gap });
		Columns.Add({ 0.5f * W + Gap, Picker.Sheet.Max.X - Pad });
	}
	else
	{
		const float X0 = Picker.Sheet.Min.X + Pad, X1 = Picker.Sheet.Max.X - Pad;
		Columns.Add({ X0, 0.5f * (X0 + X1) - 0.5f * Gap });
		Columns.Add({ 0.5f * (X0 + X1) + 0.5f * Gap, X1 });
	}
	const int32 PerColumn = FMath::Max(FMath::DivideAndRoundUp(Items.Num(), Columns.Num()), FMath::Min(Items.Num(), FullColumn));
	const float RowHeight = FMath::Min(0.032f * H, (RowsBottom - RowsTop) / PerColumn);
	for (int32 I = 0; I < Items.Num(); ++I)
	{
		const TPair<float, float>& Column = Columns[FMath::Min(I / PerColumn, Columns.Num() - 1)];
		const float Y0 = RowsTop + RowHeight * (I % PerColumn);
		FLsnPickerRow Row;
		Row.SiteIndex = Items[I].Site;
		Row.Group = Items[I].Group;
		Row.Row = FBox2D(FVector2D(Column.Key, Y0), FVector2D(Column.Value, Y0 + RowHeight));
		if (Row.SiteIndex >= 0)
		{
			// The name is the "show" box; at the right end two small boxes pin the site for a view.
			const float PinWidth = FMath::Max(0.13f * (Column.Value - Column.Key), 44.0f);
			Row.PinRight = FBox2D(FVector2D(Column.Value - PinWidth, Y0 + 1.0f), FVector2D(Column.Value, Y0 + RowHeight - 1.0f));
			Row.PinLeft = FBox2D(FVector2D(Column.Value - 2.0f * PinWidth - 2.0f, Y0 + 1.0f), FVector2D(Column.Value - PinWidth - 2.0f, Y0 + RowHeight - 1.0f));
			Row.Show = FBox2D(FVector2D(Column.Key, Y0 + 1.0f), FVector2D(Column.Value - 2.0f * PinWidth - 6.0f, Y0 + RowHeight - 1.0f));
		}
		Picker.Rows.Add(Row);
	}

	// Custom coordinates, in the left part of the sheet: a label, two fields and a button, and a line for the message.
	const float EntryTop = Picker.Sheet.Max.Y - Pad - FooterHeight + 0.010f * H;
	const float EntryWidth = (bComparing ? 0.5f * W - Gap : Picker.Sheet.Max.X - Pad) - (Picker.Sheet.Min.X + Pad);
	const float FieldTop = EntryTop + 0.022f * H, FieldHeight = FMath::Max(0.034f * H, 22.0f);
	const float X0 = Picker.Sheet.Min.X + Pad;
	Picker.EntryLabelPosition = FVector2D(X0, EntryTop);
	Picker.LatField = FBox2D(FVector2D(X0 + 0.10f * EntryWidth, FieldTop), FVector2D(X0 + 0.30f * EntryWidth, FieldTop + FieldHeight));
	Picker.LonField = FBox2D(FVector2D(X0 + 0.48f * EntryWidth, FieldTop), FVector2D(X0 + 0.68f * EntryWidth, FieldTop + FieldHeight));
	Picker.Compute = FBox2D(FVector2D(X0 + 0.72f * EntryWidth, FieldTop), FVector2D(X0 + 0.99f * EntryWidth, FieldTop + FieldHeight));
	Picker.MessagePosition = FVector2D(X0, FieldTop + FieldHeight + 0.004f * H);
	return Picker;
}

ELsnPickerHit FLsnSitePicker::HitAt(const FVector2D& Point, int32& OutSiteIndex) const
{
	OutSiteIndex = -1;
	if (!Sheet.IsInside(Point))
	{
		return ELsnPickerHit::None;
	}
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

FLsnTimeStripLayout FLsnTimeStripLayout::Make(float SizeX, float SizeY, const FLsnSitePackage& Package)
{
	FLsnTimeStripLayout Layout;
	const float Left = 0.06f * SizeX, Right = 0.94f * SizeX;
	// Bottom-up from the bar of buttons: each strip has a line of text below it.
	const float WholeBottom = FLsnToolbar::BarTop(SizeY) - 0.026f * SizeY, ZoomBottom = WholeBottom - 0.024f * SizeY - 0.026f * SizeY;
	Layout.WholeRange = FBox2D(FVector2D(Left, WholeBottom - 0.024f * SizeY), FVector2D(Right, WholeBottom));
	Layout.Zoom = FBox2D(FVector2D(Left, ZoomBottom - 0.050f * SizeY), FVector2D(Right, ZoomBottom));
	// The zoom strip shows six days around the selected time, or the whole axis if that is shorter.
	const double SixDays = Package.Time.StepS > 0.0 ? 6.0 * 86400.0 / Package.Time.StepS : 0.0;
	Layout.ZoomHalfWidthSamples = FMath::Min(0.5 * SixDays, 0.5 * FMath::Max(Package.Time.Count - 1, 1));
	return Layout;
}

bool FLsnTimeStripLayout::PositionAt(const FVector2D& Point, const FLsnSitePackage& Package, double CurrentPosition, double& OutPosition) const
{
	const double Last = FMath::Max(Package.Time.Count - 1, 0);
	if (WholeRange.IsInside(Point))
	{
		OutPosition = FMath::Clamp((Point.X - WholeRange.Min.X) / (WholeRange.Max.X - WholeRange.Min.X), 0.0, 1.0) * Last;
		return true;
	}
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
	DrawRect(FLinearColor(0.04f, 0.04f, 0.05f, 0.85f), Box.Min.X, Box.Min.Y, Width, Height);
	const double FromEt = P.EtOfPosition(FromPosition), ToEt = P.EtOfPosition(ToPosition);
	const double AxisStartEt = P.EtOfPosition(0.0), AxisEndEt = P.EtOfPosition(P.Time.Count - 1);
	auto X = [&](double EtS) { return Box.Min.X + Width * static_cast<float>(FMath::Clamp((EtS - FromEt) / (ToEt - FromEt), 0.0, 1.0)); };

	// Outside the package's time axis there is nothing to show.
	if (FromEt < AxisStartEt)
	{
		DrawRect(FLinearColor(0.2f, 0.2f, 0.2f, 0.6f), Box.Min.X, Box.Min.Y, X(AxisStartEt) - Box.Min.X, Height);
	}
	if (ToEt > AxisEndEt)
	{
		DrawRect(FLinearColor(0.2f, 0.2f, 0.2f, 0.6f), X(AxisEndEt), Box.Min.Y, Box.Max.X - X(AxisEndEt), Height);
	}
	// Upper half: Sun visible; lower half: Earth visible. Both are the package's windows.
	struct FRow { const TCHAR* WindowId; FLinearColor Color; float Top; };
	const FRow Rows[] = { { TEXT("sun_visible"), SunColor, 0.08f }, { TEXT("earth_visible"), EarthColor, 0.54f } };
	for (const FRow& Row : Rows)
	{
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
				// Opaque tones over the dark strip, so that a pale band does not add up with what lies on it.
				const FLinearColor Color(Row.Color.R * Tone.Alpha, Row.Color.G * Tone.Alpha, Row.Color.B * Tone.Alpha, 1.0f);
				DrawRect(Color, X0, Box.Min.Y + Row.Top * Height, FMath::Max(X1 - X0, 1.0f), 0.38f * Height);
			}
		}
	}
	const float Cursor = X(P.EtOfPosition(CurrentPosition));
	DrawRect(FLinearColor::White, Cursor - Scale, Box.Min.Y - 4.0f * Scale, 2.0f * Scale, Height + 8.0f * Scale);
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
	if (Width > MaxWidth && Width > 0.0f)
	{
		TextScale *= MaxWidth / Width;
		Width = MaxWidth;
	}
	DrawText(Text, Color, X, Y, Font, TextScale);
	return Width;
}

void ALsnHud::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas || !GEngine)
	{
		return;
	}
	UFont* Font = GEngine->GetMediumFont();
	const ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>();
	const APlayerController* Player = GetOwningPlayerController();
	const bool bComparing = GameMode && GameMode->IsComparing();
	const int32 View = GameMode ? GameMode->GetViewIndexOf(Player) : 0;
	const float SizeX = Canvas->SizeX, SizeY = Canvas->SizeY;
	const float Scale = FLsnToolbar::TextScale(SizeX, SizeY);
	// The buttons are laid out in the whole window; a view draws what lies in it.
	const float WindowX = bComparing ? 2.0f * SizeX : SizeX;
	const float ViewX0 = bComparing ? View * SizeX : 0.0f;
	const float Margin = 0.012f * WindowX;
	// One type scale: extra large (site name), large (times, countdowns, main buttons), medium (text), small (captions).
	const float TypeXL = 2.0f * Scale, TypeL = 1.45f * Scale, TypeM = 1.12f * Scale, TypeS = 0.9f * Scale;

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
		DrawText(TEXT("No package loaded."), Alert, Margin, Margin, Font, TypeL);
		if (GameMode)
		{
			DrawWrapped(GameMode->GetLoadError(), Alert, Margin, Margin + 40.0f * Scale, SizeX - 2.0f * Margin, TypeM);
		}
		return;
	}
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();
	const double Position = Scene->GetTimePosition();
	const ALsnObserverPawn* Pawn = Cast<ALsnObserverPawn>(GetOwningPawn());
	// The left observer holds what both views share (details, help).
	const APlayerController* FirstPlayer = GetWorld()->GetFirstPlayerController();
	const ALsnObserverPawn* LeftPawn = FirstPlayer ? Cast<ALsnObserverPawn>(FirstPlayer->GetPawn()) : Pawn;

	// For stills: no panels. A synthetic package keeps its marker; every still keeps a caption
	// that says which package, site and time it shows.
	if (FParse::Param(FCommandLine::Get(), TEXT("LsnNoHud")))
	{
		if (P.bSynthetic)
		{
			DrawText(FString::Printf(TEXT("%s - invented values for interface testing, not results"), LsnHudText::SyntheticMarker()), Alert, Margin, Margin, Font, 1.4f * Scale);
		}
		const FString Viewpoint = (Pawn && Pawn->IsOverview()) ? (Pawn->GetCameraUpM() >= 1000.0 ? FString::Printf(TEXT("overview from %.0f km above the site, not the observer's view"), Pawn->GetCameraUpM() / 1000.0)
			: FString::Printf(TEXT("camera %.0f m above and behind the observer, not the observer's view"), Pawn->GetCameraUpM()))
			: FString::Printf(TEXT("observer %.1f m"), P.ObserverHeightsM[H]);
		DrawText(FString::Printf(TEXT("%s   %s   %s   package %s (contract %s)"), *P.SiteName, *LsnHudText::UtcLabelOfPosition(P, Position), *Viewpoint, *P.PackageId, *P.ContractVersion)
			+ (Scene->IsFillForced() ? TEXT("   weak fill light on as a viewing aid: shadows are black without it") : TEXT("")),
			Dim, Margin, SizeY - 26.0f * Scale, Font, Scale * 0.9f);
		return;
	}

	// For the pitch clip: the view without its controls, with a caption that says what is shown.
	const bool bPresentation = FParse::Param(FCommandLine::Get(), TEXT("LsnPresentation"));
	const FLsnToolbar Toolbar = FLsnToolbar::Make(WindowX, SizeY, bComparing);
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	const bool bOverview = Pawn && Pawn->IsOverview();
	const double EtS = P.bHasTimeline ? P.EtOfPosition(Position) : 0.0;
	const int32 Sample = Scene->GetTimeIndex();

	// --- header: site name, time, state chips --------------------------------------------
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.66f), 0.0f, 0.0f, SizeX, Toolbar.HeaderBottom);
	float NameY = 0.012f * SizeY;
	if (P.bSynthetic)
	{
		// The marker a synthetic package carries at all times (SPEC 3.3).
		DrawFit(FString::Printf(TEXT("%s - invented values for interface testing, not results"), LsnHudText::SyntheticMarker()), Alert, Margin, 0.003f * SizeY, SizeX - 2.0f * Margin, TypeM);
		NameY = 0.026f * SizeY;
	}
	const FString Utc = P.bHasTimeline ? LsnHudText::UtcLabelOfPosition(P, Position) : FString();
	const FString TimeText = !P.bHasTimeline ? FString(TEXT("terrain horizon only: no Sun or Earth timeline")) : Utc.IsEmpty() ? FString(TEXT("UTC label not available")) : Utc;
	const int32 SiteCount = GameMode ? GameMode->GetSites().Num() : 0;
	const int32 SiteIndex = GameMode ? GameMode->GetSelectedSite(View) : -1;
	FString Sub = FString::Printf(TEXT("lat %.4f   lon %.4f (east +)   observer %.1f m above the surface"), P.LatDeg, P.LonDeg, P.ObserverHeightsM[H]);
	if (bComparing && P.TerrainSource.bPresent)
	{
		Sub += TEXT("   ") + LsnPlanner::TerrainSourceLabel(P.TerrainSource);
	}
	if (SiteIndex >= 0 && SiteCount > 0)
	{
		Sub += FString::Printf(TEXT("   site %d of %d"), SiteIndex + 1, SiteCount);
	}
	TArray<FString> Metrics;
	if (P.bHasTimeline)
	{
		LsnPlanner::BuildMetricLines(P, H, Metrics);
	}
	if (bComparing)
	{
		for (const FString& Metric : Metrics)
		{
			if (Metric.StartsWith(TEXT("Sun visible")) || Metric.StartsWith(TEXT("Earth visible")))
			{
				Sub += TEXT("   ") + Metric.Replace(TEXT(" of the window"), TEXT(""));
			}
		}
		Sub = Sub.Replace(TEXT(" above the surface"), TEXT("")) + (Metrics.Num() > 0 ? TEXT(" of the computed window") : TEXT(""));
	}
	FBox2D ChipArea;
	if (bComparing)
	{
		// The right view keeps the right end of its first line for its own button.
		const float NameWidth = SizeX - 2.0f * Margin - (View == 1 ? 0.10f * WindowX : 0.0f);
		float TimeWidth = 0.0f, Unused = 0.0f;
		GetTextSize(TimeText, TimeWidth, Unused, Font, TypeL);
		DrawFit(P.SiteName, White, Margin, NameY - 0.004f * SizeY, NameWidth - TimeWidth - 2.0f * Margin, 1.35f * TypeXL);
		DrawText(TimeText, White, Margin + NameWidth - TimeWidth, NameY + 0.006f * SizeY, Font, TypeL);
		DrawFit(Sub, White, Margin, NameY + 0.042f * SizeY, SizeX - 2.0f * Margin, 1.15f * TypeM);
		ChipArea = FBox2D(FVector2D(Margin, 0.082f * SizeY), FVector2D(SizeX - Margin, Toolbar.HeaderBottom - 0.008f * SizeY));
	}
	else
	{
		// Next to the name: what elevation data the result rests on (since contract 0.9).
		const FString Terrain = LsnPlanner::TerrainSourceLabel(P.TerrainSource);
		float TerrainWidth = 0.0f, TerrainHeight = 0.0f;
		GetTextSize(Terrain, TerrainWidth, TerrainHeight, Font, TypeS);
		const float NameWidth = DrawFit(P.SiteName, White, Margin, NameY, 0.37f * SizeX - (Terrain.IsEmpty() ? 0.0f : TerrainWidth + 14.0f * Scale), TypeXL);
		if (!Terrain.IsEmpty())
		{
			DrawText(Terrain, P.TerrainSource.ResolutionClass == TEXT("fine") ? Good : P.TerrainSource.ResolutionClass == TEXT("medium") ? SunColor : Lost, Margin + NameWidth + 12.0f * Scale, NameY + 0.016f * SizeY, Font, TypeS);
		}
		DrawText(TimeText, White, Margin, NameY + 0.044f * SizeY, Font, TypeL);
		DrawFit(Sub, Dim, Margin, NameY + 0.080f * SizeY, 0.37f * SizeX, TypeS);
		ChipArea = FBox2D(FVector2D(0.40f * SizeX, 0.012f * SizeY), FVector2D(SizeX - Margin, Toolbar.HeaderBottom - 0.010f * SizeY));
	}

	// A chip: a title with the state, a large line, a small line. Filled in the body's colour
	// while the state is good, dark with a coloured edge while it is not.
	struct FChip { FString Title; FString Headline; FString Detail; FLinearColor Color; bool bGood; };
	TArray<FChip> Chips;
	const FLsnCountdown SunCountdown = P.bHasTimeline ? P.CountdownAt(TEXT("SUN"), H, EtS) : FLsnCountdown();
	const FLsnCountdown EarthCountdown = P.bHasTimeline ? P.CountdownAt(TEXT("EARTH"), H, EtS) : FLsnCountdown();
	auto BodyChip = [&](const TCHAR* Body, const TCHAR* Name, const FLsnCountdown& Countdown, const FLinearColor& Color)
	{
		if (!Countdown.bAvailable)
		{
			return;
		}
		FChip Chip;
		Chip.Color = Color;
		Chip.bGood = Countdown.bVisibleNow;
		FLsnBlocking Blocking;
		const bool bBlocked = P.BlockingAt(Body, H, Sample, Blocking) && Blocking.bHiddenOrPartly;
		const bool bPartly = bBlocked && Blocking.VisibleFraction > 0.0;
		Chip.Title = FString::Printf(TEXT("%s  %s"), Name, bPartly ? *FString::Printf(TEXT("partly hidden, %.0f %% visible"), 100.0 * Blocking.VisibleFraction) : Countdown.bVisibleNow ? TEXT("visible") : TEXT("hidden"));
		Chip.Headline = FString::Printf(TEXT("%s in %s%s"), Countdown.bVisibleNow ? TEXT("sets") : TEXT("rises"), Countdown.bLowerBound ? TEXT("at least ") : TEXT(""), *LsnHudText::FormatDuration(Countdown.SecondsToChange));
		// With a stated horizon error the event is a range, not an instant.
		const FLsnEvent* Event = LsnPlanner::EventEndingCountdown(P, Body, H, EtS, Countdown);
		if (Event && Event->bHasBand && Event->LatestEtS > Event->EarliestEtS && P.Uncertainty.bHasHorizonError)
		{
			Chip.Detail = FString::Printf(TEXT("horizon +/- %.2f deg: %s to %s"), P.Uncertainty.HorizonErrorDeg, *LsnHudText::FormatDuration(Event->EarliestEtS - EtS), *LsnHudText::FormatDuration(Event->LatestEtS - EtS));
		}
		else if (Countdown.bLowerBound)
		{
			Chip.Detail = TEXT("no such event in the computed range");
		}
		Chips.Add(Chip);
	};
	BodyChip(TEXT("SUN"), TEXT("SUN"), SunCountdown, SunColor);
	BodyChip(TEXT("EARTH"), TEXT("EARTH"), EarthCountdown, EarthColor);
	const FLsnRequirement* Requirement = P.Requirements.Num() > 0 ? &P.Requirements[(GameMode ? GameMode->GetRequirementIndex() : 0) % P.Requirements.Num()] : nullptr;
	const FLsnOpportunity* Opportunity = (Requirement && P.bHasTimeline) ? P.FindOpportunity(Requirement->Id, H) : nullptr;
	if (Opportunity)
	{
		const FLsnLandingCheck Check = LsnPlanner::LandingAt(*Opportunity, EtS);
		FChip Chip;
		Chip.Color = Good;
		Chip.bGood = Check.bJudgeable && Check.bFeasible;
		Chip.Title = !Check.bJudgeable ? TEXT("LANDING NOW  cannot be judged") : Check.bFeasible ? TEXT("LANDING NOW  meets the requirement") : TEXT("LANDING NOW  does not meet it");
		Chip.Headline = !Check.bJudgeable ? FString(TEXT("stay runs past the range")) : Check.bFeasible ? FString::Printf(TEXT("can slip %s%s"), Check.bSlipIsLowerBound ? TEXT("at least ") : TEXT(""), *LsnHudText::FormatDuration(Check.SlipS))
			: Check.bHasNextWindow ? FString::Printf(TEXT("window in %s"), *LsnHudText::FormatDuration(Check.WaitS)) : FString(TEXT("no window left in the range"));
		Chip.Detail = FString::Printf(TEXT("example requirement '%s'"), *Requirement->Id);
		Chips.Add(Chip);
	}
	if (Chips.Num() > 0)
	{
		const float Gap = 0.006f * WindowX;
		const float ChipWidth = (ChipArea.Max.X - ChipArea.Min.X - 2.0f * Gap) / 3.0f, ChipHeight = ChipArea.Max.Y - ChipArea.Min.Y;
		for (int32 I = 0; I < Chips.Num(); ++I)
		{
			const FChip& Chip = Chips[I];
			const float X0 = ChipArea.Min.X + I * (ChipWidth + Gap), Y0 = ChipArea.Min.Y;
			const FLinearColor Edge = Chip.bGood ? Chip.Color : Lost;
			DrawRect(Edge, X0, Y0, ChipWidth, ChipHeight);
			const FLinearColor Fill = Chip.bGood ? FLinearColor(Chip.Color.R * 0.86f, Chip.Color.G * 0.86f, Chip.Color.B * 0.86f, 1.0f) : FLinearColor(0.07f, 0.07f, 0.08f, 1.0f);
			DrawRect(Fill, X0 + 2.0f, Y0 + 2.0f, ChipWidth - 4.0f, ChipHeight - 4.0f);
			const FLinearColor Ink = Chip.bGood ? FLinearColor(0.02f, 0.02f, 0.03f) : Lost;
			const float Inset = 10.0f * Scale, TextWidth = ChipWidth - 2.0f * Inset;
			DrawFit(Chip.Title, Ink, X0 + Inset, Y0 + 0.006f * SizeY, TextWidth, (bComparing ? 1.25f : 1.0f) * TypeM);
			DrawFit(Chip.Headline, Ink, X0 + Inset, Y0 + (bComparing ? 0.034f : 0.030f) * SizeY, TextWidth, (bComparing ? 1.6f : 1.12f) * TypeL);
			DrawFit(Chip.Detail, Chip.bGood ? FLinearColor(0.10f, 0.10f, 0.12f) : Dim, X0 + Inset, Y0 + ChipHeight - 0.026f * SizeY, TextWidth, TypeS);
		}
	}

	// --- buttons ----------------------------------------------------------------------------
	if (!bPresentation)
	{
		DrawToolbar(Toolbar, ViewX0, *Scene, LeftPawn, GameMode, Scale);
	}

	// --- below the header: horizon all round and the numbers of the whole window ------------
	const float ContentTop = Toolbar.HeaderBottom + 0.086f * SizeY;   // below the main buttons
	FLsnPanorama Pano;
	LsnPlanner::PanoramaRange(P, H, Pano.MinElevationDeg, Pano.MaxElevationDeg);
	if (bComparing)
	{
		Pano.Box = FBox2D(FVector2D(0.52f * SizeX, ContentTop), FVector2D(SizeX - Margin, ContentTop + 0.075f * SizeY));
	}
	else
	{
		Pano.Box = FBox2D(FVector2D(0.70f * SizeX, Toolbar.HeaderBottom + 0.012f * SizeY), FVector2D(SizeX - Margin, Toolbar.HeaderBottom + 0.012f * SizeY + 0.115f * SizeY));
	}
	if (!bPresentation)
	{
		DrawPanorama(Pano, *Scene, Pawn, Scale);
	}
	float RightY = Pano.Box.Max.Y + 22.0f * Scale;
	if (P.bHasTimeline && Page == ELsnPlannerPage::Summary && !bComparing)
	{
		if (Metrics.Num() > 0)
		{
			DrawFit(FString::Printf(TEXT("WHOLE COMPUTED WINDOW   %s to %s"), *P.Time.StartUtc.Left(10), *P.Time.EndUtc.Left(10)), Dim, Pano.Box.Min.X, RightY, Pano.Box.Max.X - Pano.Box.Min.X, TypeS);
			RightY += 19.0f * Scale;
			for (const FString& Metric : Metrics)
			{
				RightY = DrawWrapped(Metric, White, Pano.Box.Min.X, RightY, Pano.Box.Max.X - Pano.Box.Min.X, TypeM) + 2.0f * Scale;
			}
		}
	}

	// --- left column: notices, what blocks the Sun or the Earth, details --------------------
	const float ColumnWidth = (bPresentation ? 0.95f : bComparing ? 0.50f : 0.66f) * SizeX - Margin;
	// Without the main buttons the column starts right under the header.
	float Y = bPresentation ? Toolbar.HeaderBottom + 0.014f * SizeY : ContentTop;
	auto Notice = [&](const FString& Text)
	{
		Y = DrawWrapped(Text, Alert, Margin, Y, ColumnWidth, TypeM) + 4.0f * Scale;
	};
	if (bOverview)
	{
		Notice(FString::Printf(TEXT("Camera %.0f m above the observer: not the observer's view. Horizon, countdowns and obstacle refer to the observer at the site."), Pawn->GetCameraUpM()));
	}
	if (Scene->GetSkippedHorizonSamples() > 0)
	{
		Notice(FString::Printf(TEXT("%d horizon samples are unknown in the package and are not drawn."), Scene->GetSkippedHorizonSamples()));
	}
	if (bComparing && View == 1 && GameMode && !GameMode->IsRightViewInRange())
	{
		Notice(TEXT("The selected instant is outside this package's time range: this half shows its nearest sample."));
	}
	for (const FString& Warning : P.Warnings)
	{
		Notice(FString::Printf(TEXT("warning of the package: %s"), *Warning));
	}
	if (Scene->GetNearGroundShadeShare() >= 0.05 && !bOverview && !bPresentation && Page == ELsnPlannerPage::Summary)
	{
		// The scene must not seem to contradict the package where the user looks: say what the dark ground is.
		FLsnBodyAtTime SunNow;
		Scene->SampleBody(TEXT("SUN"), Position, SunNow);
		Y = DrawWrapped(FString::Printf(TEXT("About %.0f %% of the ground within %.0f m is drawn in shadow: the elevation data rises towards the Sun there by more than the Sun's height of %.1f deg. The package's horizon search starts %.0f m out; its result is for the observer at the site, who is in sunlight."),
			100.0 * Scene->GetNearGroundShadeShare(), FMath::Max(P.HorizonSearchStartM(), 5.0), SunNow.ElevationDeg, P.HorizonSearchStartM()), White, Margin, Y, ColumnWidth, TypeS) + 6.0f * Scale;
	}
	if (GameMode && View == 0 && SiteIndex >= 0 && GameMode->GetSites()[SiteIndex].Programme.StartsWith(TEXT("Custom")) && Page == ELsnPlannerPage::Summary)
	{
		// A site computed for custom coordinates: the two steps, what each said, and how far the running one is.
		const FLsnCustomEntry& Entry = GameMode->GetCustomEntry();
		if (!Entry.HorizonLine.IsEmpty())
		{
			Y = DrawWrapped(Entry.HorizonLine, Good, Margin, Y, ColumnWidth, TypeS) + 4.0f * Scale;
		}
		if (Entry.bRunning && Entry.Step == 2)
		{
			const float RunS = static_cast<float>(FPlatformTime::Seconds() - Entry.StartedS);
			Y = DrawWrapped(Entry.Message, SunColor, Margin, Y, ColumnWidth, TypeM) + 4.0f * Scale;
			const float BarWidth = 0.5f * ColumnWidth, BarHeight = 10.0f * Scale;
			DrawRect(FLinearColor(0.20f, 0.20f, 0.22f, 1.0f), Margin, Y, BarWidth, BarHeight);
			DrawRect(SunColor, Margin, Y, BarWidth * static_cast<float>(LsnPlanner::StepShare(RunS, Entry.StatedS)), BarHeight);
			Y += BarHeight + 8.0f * Scale;
		}
		else if (!Entry.TimelineLine.IsEmpty())
		{
			Y = DrawWrapped(Entry.TimelineLine, Entry.bFailed ? Alert : P.bHasTimeline ? Good : Dim, Margin, Y, ColumnWidth, TypeS) + 6.0f * Scale;
		}
	}
	const bool bDetails = LeftPawn && LeftPawn->AreDetailsShown();
	const FLsnTimeStripLayout Layout = FLsnTimeStripLayout::Make(SizeX, SizeY, P);
	const float SheetBottom = Layout.Zoom.Min.Y - 0.030f * SizeY;
	if (Page == ELsnPlannerPage::Summary && P.bHasTimeline)
	{
		// What hides a body now, and what that obstacle costs: the package's own blocker (SPEC 5.5).
		struct FCardLine { FString Text; FLinearColor Color; float Size; };
		TArray<FCardLine> Card;
		auto AddBlocker = [&](const TCHAR* Body, const FLinearColor& Color)
		{
			FLsnBlocking Blocking;
			TArray<FString> Sentences;
			if (Scene->IsObstacleViewEnabled() && P.BlockingAt(Body, H, Sample, Blocking))
			{
				LsnHudText::BlockerSentences(Body, P, Blocking, Sentences);
				for (int32 I = 0; I < Sentences.Num(); ++I)
				{
					Card.Add({ Sentences[I], I == 2 ? Alert : Color, I == 0 ? TypeL : TypeM });
				}
			}
		};
		AddBlocker(TEXT("SUN"), FLinearColor(1.0f, 0.55f, 0.25f));
		AddBlocker(TEXT("EARTH"), FLinearColor(0.35f, 0.85f, 1.0f));
		if (Card.Num() > 0 && !bOverview)
		{
			const float CardTop = Y;
			// Measured first, so that the dark box behind is as high as the text.
			float CardHeight = 0.0f;
			for (const FCardLine& Line : Card)
			{
				float Width = 0.0f, Height = 0.0f;
				GetTextSize(Line.Text, Width, Height, Font, Line.Size);
				CardHeight += 18.0f * Line.Size * FMath::CeilToFloat(FMath::Max(Width, 1.0f) / (ColumnWidth - 16.0f * Scale));
			}
			DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.60f), Margin - 6.0f * Scale, CardTop - 6.0f * Scale, ColumnWidth, CardHeight + 14.0f * Scale);
			for (const FCardLine& Line : Card)
			{
				Y = DrawWrapped(Line.Text, Line.Color, Margin, Y, ColumnWidth - 16.0f * Scale, Line.Size);
			}
			Y += 14.0f * Scale;
		}
	}
	if (bDetails && Page == ELsnPlannerPage::Summary)
	{
		// On demand: where every number comes from, and how far it has been checked.
		if (bComparing)
		{
			Y = FMath::Max(Y, RightY + 6.0f * Scale);
		}
		const float PanelWidth = (bComparing ? SizeX - 2.0f * Margin : 0.66f * SizeX - Margin);
		TArray<FLsnHudLine> Lines;
		LsnHudText::BuildStatusLines(P, H, Position, Lines, Scene->GetGroundNote());
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
		if (!P.BlockingMethod.IsEmpty())
		{
			Lines.Add({ FString::Printf(TEXT("what blocks a body and its cost: package blockers   [%s: %s]"), *P.BlockingMethod, *P.ValidationStatusOf(P.BlockingMethod)), Dim, 1.0f });
		}
		if (P.Uncertainty.bHasHorizonError)
		{
			Lines.Add({ FString::Printf(TEXT("ranges for the stated horizon error of %.2f deg   [%s]"), P.Uncertainty.HorizonErrorDeg, *P.ValidationStatusOf(P.Uncertainty.HorizonMethod)), Dim, 1.0f });
		}
		if (Opportunity)
		{
			Lines.Add({ FString::Printf(TEXT("landing windows of the example requirement '%s': %s   [%s]"), *Requirement->Id, *Requirement->Label, *P.ValidationStatusOf(Opportunity->Method)), Dim, 1.0f });
		}
		const float PanelTop = Y;
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.86f), Margin - 6.0f * Scale, PanelTop - 6.0f * Scale, PanelWidth, FMath::Max(SheetBottom - PanelTop, 10.0f));
		DrawText(TEXT("DETAILS: package, frame, contract and how far each number has been checked"), White, Margin, Y, Font, TypeS);
		Y += 20.0f * Scale;
		for (const FLsnHudLine& Line : Lines)
		{
			if (Y > SheetBottom - 20.0f * Scale)
			{
				break;
			}
			Y = DrawWrapped(Line.Text, Line.Color, Margin, Y, PanelWidth - 16.0f * Scale, TypeS * FMath::Min(Line.Size, 1.15f));
		}
	}

	// --- planner pages: a sheet of their own over the view ---------------------------------
	if (Page == ELsnPlannerPage::Sites && GameMode)
	{
		DrawSitePicker(WindowX, ViewX0, *GameMode, Scale);
	}
	else if (Page != ELsnPlannerPage::Summary && GameMode)
	{
		const float SheetTop = bComparing ? RightY + 4.0f * Scale : ContentTop;
		const FBox2D Sheet(FVector2D(Margin, SheetTop), FVector2D(bComparing ? SizeX - Margin : 0.685f * SizeX, SheetBottom));
		DrawRect(FLinearColor(0.015f, 0.015f, 0.02f, 0.94f), Sheet.Min.X - 6.0f * Scale, Sheet.Min.Y - 6.0f * Scale, Sheet.Max.X - Sheet.Min.X + 12.0f * Scale, Sheet.Max.Y - Sheet.Min.Y + 12.0f * Scale);
		const float Inset = 10.0f * Scale;
		const float InnerX = Sheet.Min.X + Inset, InnerWidth = Sheet.Max.X - Sheet.Min.X - 2.0f * Inset;
		float InnerY = Sheet.Min.Y + Inset;
		const TCHAR* Title = Page == ELsnPlannerPage::Calendar ? TEXT("CALENDAR AND LANDING WINDOWS") : Page == ELsnPlannerPage::Uncertainty ? TEXT("UNCERTAINTY") : TEXT("MAST HEIGHT AND SITE PAIRS");
		DrawText(Title, White, InnerX, InnerY, Font, TypeL);
		InnerY += 30.0f * Scale;
		if (Page == ELsnPlannerPage::Calendar)
		{
			// Side by side each half shows its own site; the two charts share the time axis of the packages.
			DrawCalendar(FBox2D(FVector2D(InnerX, InnerY), FVector2D(InnerX + InnerWidth, Sheet.Max.Y - Inset)), { Scene }, GameMode->GetRequirementIndex(), Scale);
		}
		else if (Page == ELsnPlannerPage::Uncertainty)
		{
			DrawUncertainty(*Scene, InnerX, InnerY, InnerWidth, Scale);
		}
		else
		{
			DrawTrade(*Scene, *GameMode, InnerX, InnerY, InnerWidth, Scale);
		}
	}
	if (!P.bHasTimeline)
	{
		DrawText(TEXT("This package has no timeline: no Sun or Earth is shown."), Dim, Margin, Y, Font, TypeM);
		if (View == 0 && LeftPawn && LeftPawn->IsHelpShown())
		{
			DrawHelp(SizeX, SizeY, Scale);
		}
		return;
	}

	// --- where the Sun and the Earth are when they are outside the view -----------------
	if (Pawn && !bOverview && !bPresentation && Page == ELsnPlannerPage::Summary)
	{
		float IndicatorY = Layout.Zoom.Min.Y - 36.0f * Scale;
		for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
		{
			FLsnBodyAtTime At;
			if (!Scene->SampleBody(Body, Position, At))
			{
				continue;
			}
			const bool bSun = FCString::Stricmp(Body, TEXT("SUN")) == 0;
			const FVector Screen = Project(Scene->GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(At.AzimuthDeg, At.ElevationDeg) * 1.0e6, false);
			if (Screen.Z > 0.0 && Screen.X >= 0.0 && Screen.X <= SizeX && Screen.Y >= 0.0 && Screen.Y <= SizeY)
			{
				continue;
			}
			const double Turn = FMath::Fmod(At.AzimuthDeg - Pawn->GetAzimuthDeg() + 540.0, 360.0) - 180.0;
			const FString Text = Turn >= 0.0
				? FString::Printf(TEXT("%s %.0f deg to the right, el %.1f  >>"), bSun ? TEXT("Sun") : TEXT("Earth"), Turn, At.ElevationDeg)
				: FString::Printf(TEXT("<<  %s %.0f deg to the left, el %.1f"), bSun ? TEXT("Sun") : TEXT("Earth"), -Turn, At.ElevationDeg);
			float TextWidth = 0.0f, TextHeight = 0.0f;
			GetTextSize(Text, TextWidth, TextHeight, Font, Scale * 1.2f);
			DrawText(Text, bSun ? SunColor : EarthColor, Layout.Zoom.Max.X - TextWidth, IndicatorY, Font, Scale * 1.2f);
			IndicatorY -= 24.0f * Scale;
		}
	}

	// A marker at the peak of each highlighted obstacle, and an outline where the hidden body stands.
	for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
	{
		FLsnBlocking Blocking;
		if (bOverview || bDetails || Page != ELsnPlannerPage::Summary || !Scene->IsObstacleViewEnabled() || !P.BlockingAt(Body, H, Sample, Blocking) || !Blocking.bHiddenOrPartly || !Blocking.Obstacle)
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
				const float Radius = FMath::Max(static_cast<float>(FVector2D::Distance(FVector2D(Centre.X, Centre.Y), FVector2D(Rim.X, Rim.Y))), 3.0f * Scale);
				const int32 Segments = 48;
				for (int32 I = 0; I < Segments; I += 2)  // dashed
				{
					const float A0 = 2.0f * UE_PI * I / Segments, A1 = 2.0f * UE_PI * (I + 1) / Segments;
					DrawLine(Centre.X + Radius * FMath::Cos(A0), Centre.Y + Radius * FMath::Sin(A0), Centre.X + Radius * FMath::Cos(A1), Centre.Y + Radius * FMath::Sin(A1), Outline, 1.5f * Scale);
				}
				DrawText(FString::Printf(TEXT("%s (behind terrain)"), bSun ? TEXT("Sun") : TEXT("Earth")), Outline, Centre.X + Radius + 6.0f * Scale, Centre.Y - 8.0f * Scale, Font, Scale);
			}
		}
		const FVector Peak = Project(Scene->GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(Blocking.Obstacle->PeakAzimuthDeg, Blocking.Obstacle->PeakElevationDeg) * 1.0e6, false);
		if (Peak.Z <= 0.0 || Peak.X < 0.0 || Peak.X > SizeX || Peak.Y < 0.0 || Peak.Y > SizeY)
		{
			continue;
		}
		const FLinearColor Color = bSun ? FLinearColor(1.0f, 0.45f, 0.2f) : FLinearColor(0.3f, 0.85f, 1.0f);
		const FString Distance = Blocking.Obstacle->PeakDistanceM < 1000.0 ? FString::Printf(TEXT("%.0f m"), Blocking.Obstacle->PeakDistanceM) : FString::Printf(TEXT("%.1f km"), Blocking.Obstacle->PeakDistanceM / 1000.0);
		const FString Cost = Blocking.Blocker ? FString::Printf(TEXT("costs %.0f h of %s"), Blocking.Blocker->LostS / 3600.0, Body) : FString::Printf(TEXT("hides the %s now"), bSun ? TEXT("Sun") : TEXT("Earth"));
		const float Top = Peak.Y - 70.0f * Scale;
		DrawLine(Peak.X, Peak.Y - 6.0f * Scale, Peak.X, Top + 34.0f * Scale, Color, 2.0f * Scale);
		const FString Headline = FString::Printf(TEXT("this ridge %s"), *Cost);
		const FString Detail = FString::Printf(TEXT("peak %s away, azimuth %.1f deg"), *Distance, Blocking.Obstacle->PeakAzimuthDeg);
		float HeadlineWidth = 0.0f, DetailWidth = 0.0f, Unused = 0.0f;
		GetTextSize(Headline, HeadlineWidth, Unused, Font, Scale * 1.4f);
		GetTextSize(Detail, DetailWidth, Unused, Font, Scale);
		const bool bLabelLeft = Peak.X > 0.45f * SizeX;
		DrawText(Headline, Color, bLabelLeft ? Peak.X - 8.0f * Scale - HeadlineWidth : Peak.X + 8.0f * Scale, Top, Font, Scale * 1.4f);
		DrawText(Detail, Color, bLabelLeft ? Peak.X - 8.0f * Scale - DetailWidth : Peak.X + 8.0f * Scale, Top + 24.0f * Scale, Font, Scale);
	}

	// --- time strips ------------------------------------------------------------------------
	DrawStrip(Layout.Zoom, P, H, Position - Layout.ZoomHalfWidthSamples, Position + Layout.ZoomHalfWidthSamples, Position, Scale);
	if (bPresentation)
	{
		// The strip of six days and one line under it; a caption across the window says what is shown.
		DrawText(TEXT("six days around this instant   yellow: Sun visible   blue: Earth visible"), Dim, Layout.Zoom.Min.X, Layout.Zoom.Max.Y + 2.0f * Scale, Font, TypeM);
		FString Caption;
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnCaption="), Caption, false) && GameMode)
		{
			// "first|second": the second text from the moment the package gives the Sun of the left site as hidden.
			FString First = Caption, Second;
			Caption.Split(TEXT("|"), &First, &Second);
			const ALsnSiteScene* LeftScene = GameMode->GetSceneOfView(0);
			const bool bLeftSunDown = LeftScene && LeftScene->HasPackage() && LeftScene->GetSunVisibleFraction() <= 0.0;
			const FString Text = (bLeftSunDown && !Second.IsEmpty()) ? Second : First;
			const float CaptionScale = 1.75f * FLsnToolbar::TextScale(WindowX, SizeY);
			float TextWidth = 0.0f, TextHeight = 0.0f;
			GetTextSize(Text, TextWidth, TextHeight, Font, CaptionScale);
			const float Fit = FMath::Min(1.0f, (WindowX - 60.0f) / FMath::Max(TextWidth, 1.0f));
			const float BandTop = Layout.Zoom.Max.Y + 0.045f * SizeY, BandHeight = 0.075f * SizeY;
			DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f), 0.0f, BandTop, SizeX, BandHeight);
			// Centred in the window; each view draws its part.
			DrawText(Text, White, 0.5f * (WindowX - TextWidth * Fit) - ViewX0, BandTop + 0.5f * (BandHeight - TextHeight * Fit), Font, CaptionScale * Fit);
		}
		return;
	}
	DrawStrip(Layout.WholeRange, P, H, 0.0, P.Time.Count - 1, Position, Scale);
	DrawText(FString::Printf(TEXT("%.0f days around the selected time   yellow: Sun visible   blue: Earth visible%s"), 2.0 * Layout.ZoomHalfWidthSamples * P.Time.StepS / 86400.0,
		P.Uncertainty.bHasHorizonError ? TEXT("   pale: only if the horizon is lower than computed") : TEXT("")), Dim, Layout.Zoom.Min.X, Layout.Zoom.Max.Y + 2.0f * Scale, Font, TypeS);
	DrawText(FString::Printf(TEXT("whole computed range   %s   to   %s"), *P.Time.StartUtc.Left(10), *P.Time.EndUtc.Left(10)), Dim, Layout.WholeRange.Min.X, Layout.WholeRange.Max.Y + 2.0f * Scale, Font, TypeS);
	if (View == 0)
	{
		const FString Hint = (LeftPawn && LeftPawn->IsPlaying()) ? FString::Printf(TEXT("playing: %.1f h of site time per second"), LeftPawn->GetPlayRateSamplesPerSecond() * P.Time.StepS / 3600.0)
			: FString(TEXT("drag on a strip to choose the time   hold the right mouse button to look round   wheel to zoom"));
		float HintWidth = 0.0f, HintHeight = 0.0f;
		GetTextSize(Hint, HintWidth, HintHeight, Font, TypeS);
		DrawText(Hint, White, Layout.WholeRange.Max.X - HintWidth, Layout.WholeRange.Max.Y + 2.0f * Scale, Font, TypeS);
	}
	if (View == 0 && LeftPawn && LeftPawn->IsHelpShown())
	{
		DrawHelp(SizeX, SizeY, Scale);
	}
}

void ALsnHud::DrawToolbar(const FLsnToolbar& Toolbar, float ViewX0, const ALsnSiteScene& Scene, const ALsnObserverPawn* Pawn, const ALsnViewGameMode* GameMode, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	// The pointer belongs to the left player; its position is in window pixels.
	FVector2D Mouse(-1.0, -1.0);
	float MouseX = 0.0f, MouseY = 0.0f;
	const APlayerController* First = GetWorld()->GetFirstPlayerController();
	if (First && First->bShowMouseCursor && First->GetMousePosition(MouseX, MouseY))
	{
		Mouse = FVector2D(MouseX, MouseY);
	}
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	const bool bComparing = GameMode && GameMode->IsComparing();
	const float ViewX1 = ViewX0 + Canvas->SizeX;
	const FLinearColor Accent(1.0f, 0.70f, 0.18f);
	Scale = FLsnToolbar::TextScale(bComparing ? 2.0f * Canvas->SizeX : Canvas->SizeX, Canvas->SizeY);
	for (const FLsnButtonGroupLabel& Label : Toolbar.GroupLabels)
	{
		if (Label.Position.X >= ViewX0 && Label.Position.X < ViewX1)
		{
			DrawText(Label.Text, Dim, Label.Position.X - ViewX0, Label.Position.Y + 1.0f * Scale, Font, 0.82f * Scale);
		}
	}
	for (const FLsnButton& Button : Toolbar.Buttons)
	{
		if (Button.Box.Max.X <= ViewX0 || Button.Box.Min.X >= ViewX1)
		{
			continue;
		}
		// A button that is a switch is drawn lit while it is on.
		const FName A = Button.Action;
		const bool bOn = (A == TEXT("play") && Pawn && Pawn->IsPlaying()) || (A == TEXT("compare") && bComparing)
			|| (A == TEXT("page_calendar") && Page == ELsnPlannerPage::Calendar) || (A == TEXT("page_uncertainty") && Page == ELsnPlannerPage::Uncertainty)
			|| (A == TEXT("page_trade") && Page == ELsnPlannerPage::Trade) || (A == TEXT("page_sites") && Page == ELsnPlannerPage::Sites) || (A == TEXT("obstacle") && Scene.IsObstacleViewEnabled())
			|| (A == TEXT("follow_sun") && Pawn && Pawn->IsFollowingSun()) || (A == TEXT("quality") && GameMode && GameMode->IsLowQuality())
			|| (A == TEXT("scale_objects") && Scene.AreScaleObjectsVisible()) || (A == TEXT("fill_light") && Scene.IsFillLightVisible())
			|| (A == TEXT("details") && Pawn && Pawn->AreDetailsShown()) || (A == TEXT("help") && Pawn && Pawn->IsHelpShown());
		const bool bHover = Button.Box.IsInside(Mouse);
		const float X0 = Button.Box.Min.X - ViewX0, Y0 = Button.Box.Min.Y;
		const float Width = Button.Box.Max.X - Button.Box.Min.X, Height = Button.Box.Max.Y - Button.Box.Min.Y;
		FString Label = Button.Label;
		FLinearColor Edge, Fill, Ink = White;
		float TextSize = 0.95f * Scale;
		if (Button.Style == ELsnButtonStyle::Main)
		{
			// The three main actions: the largest and brightest things on screen that can be clicked.
			if (A == TEXT("compare") && bComparing) { Label = TEXT("Back to one site"); }
			if (A == TEXT("obstacle")) { Label = bOn ? TEXT("Hide what blocks it") : TEXT("What blocks the Sun?"); }
			Edge = Accent;
			Fill = bHover ? FLinearColor(1.0f, 0.80f, 0.36f, 1.0f) : FLinearColor(Accent.R * 0.92f, Accent.G * 0.92f, Accent.B * 0.92f, 1.0f);
			Ink = FLinearColor(0.03f, 0.02f, 0.0f);
			TextSize = 1.3f * Scale;
		}
		else
		{
			Edge = bHover ? FLinearColor(0.9f, 0.9f, 0.9f, 1.0f) : bOn ? FLinearColor(0.45f, 0.70f, 0.95f, 1.0f) : FLinearColor(0.34f, 0.34f, 0.38f, 1.0f);
			Fill = bOn ? FLinearColor(0.13f, 0.27f, 0.42f, 0.97f) : FLinearColor(0.07f, 0.07f, 0.09f, 0.94f);
			if (bHover)
			{
				Fill = FLinearColor(Fill.R + 0.10f, Fill.G + 0.10f, Fill.B + 0.10f, 1.0f);
			}
			TextSize = (Button.Style == ELsnButtonStyle::RightView ? 1.05f : 0.95f) * Scale;
		}
		DrawRect(Edge, X0, Y0, Width, Height);
		DrawRect(Fill, X0 + 2.0f, Y0 + 2.0f, Width - 4.0f, Height - 4.0f);
		// The label is made smaller where it would not fit.
		float TextWidth = 0.0f, TextHeight = 0.0f;
		GetTextSize(Label, TextWidth, TextHeight, Font, TextSize);
		if (TextWidth > Width - 10.0f)
		{
			TextSize *= (Width - 10.0f) / TextWidth;
			GetTextSize(Label, TextWidth, TextHeight, Font, TextSize);
		}
		DrawText(Label, Ink, X0 + 0.5f * (Width - TextWidth), Y0 + 0.5f * (Height - TextHeight), Font, TextSize);
	}
}

void ALsnHud::DrawSitePicker(float WindowSizeX, float ViewX0, const ALsnViewGameMode& GameMode, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	TArray<FString> Groups;
	for (const FLsnSiteInfo& Info : GameMode.GetSiteInfos())
	{
		Groups.Add(Info.Group);
	}
	const bool bComparing = GameMode.IsComparing();
	const FLsnSitePicker Picker = FLsnSitePicker::Make(WindowSizeX, Canvas->SizeY, bComparing, Groups);
	const float ViewX1 = ViewX0 + Canvas->SizeX;
	// Sized for the window, like the bar; a view draws what lies in it.
	Scale = FLsnToolbar::TextScale(WindowSizeX, Canvas->SizeY);
	auto Visible = [&](const FBox2D& Box) { return Box.Max.X > ViewX0 && Box.Min.X < ViewX1; };
	auto Fill = [&](const FBox2D& Box, const FLinearColor& Color)
	{
		const float X0 = FMath::Max(static_cast<float>(Box.Min.X), ViewX0), X1 = FMath::Min(static_cast<float>(Box.Max.X), ViewX1);
		if (X1 > X0)
		{
			DrawRect(Color, X0 - ViewX0, Box.Min.Y, X1 - X0, Box.Max.Y - Box.Min.Y);
		}
	};
	FVector2D Mouse(-1.0, -1.0);
	float MouseX = 0.0f, MouseY = 0.0f;
	const APlayerController* First = GetWorld()->GetFirstPlayerController();
	if (First && First->bShowMouseCursor && First->GetMousePosition(MouseX, MouseY))
	{
		Mouse = FVector2D(MouseX, MouseY);
	}
	Fill(Picker.Sheet, FLinearColor(0.015f, 0.015f, 0.02f, 0.95f));
	if (Picker.TitlePosition.X >= ViewX0 && Picker.TitlePosition.X < ViewX1)
	{
		DrawText(TEXT("SITES   click a name to show it; Left and Right pin a site for the comparison"), White, Picker.TitlePosition.X - ViewX0, Picker.TitlePosition.Y, Font, 1.2f * Scale);
	}
	const int32 LeftSite = GameMode.GetSelectedSite(0), RightSite = bComparing ? GameMode.GetSelectedSite(1) : -1;
	for (const FLsnPickerRow& Row : Picker.Rows)
	{
		if (!Visible(Row.Row))
		{
			continue;
		}
		const float X0 = Row.Row.Min.X - ViewX0, Height = Row.Row.Max.Y - Row.Row.Min.Y;
		const float TextY = Row.Row.Min.Y + 0.5f * Height - 9.0f * Scale;
		if (Row.SiteIndex < 0)
		{
			DrawFit(Row.Group.ToUpper(), SunColor, X0, TextY + 2.0f * Scale, Row.Row.Max.X - Row.Row.Min.X, 0.85f * Scale);
			continue;
		}
		const bool bLeft = Row.SiteIndex == LeftSite, bRight = Row.SiteIndex == RightSite;
		if (Row.Row.IsInside(Mouse) || bLeft || bRight)
		{
			Fill(Row.Show, Row.Row.IsInside(Mouse) ? FLinearColor(0.20f, 0.22f, 0.28f, 1.0f) : FLinearColor(0.10f, 0.16f, 0.24f, 1.0f));
		}
		// The name, and what the terrain behind the result is (since contract 0.9).
		const FLsnSiteInfo& Info = GameMode.GetSiteInfos()[Row.SiteIndex];
		const float ShowWidth = Row.Show.Max.X - Row.Show.Min.X;
		FString Class = Info.TerrainSource.bPresent ? FString::Printf(TEXT("%s %.0f m"), *Info.TerrainSource.ResolutionClass, Info.TerrainSource.PixelM) : FString();
		float ClassWidth = 0.0f, Unused = 0.0f;
		GetTextSize(Class, ClassWidth, Unused, Font, 0.85f * Scale);
		DrawFit(GameMode.GetSites()[Row.SiteIndex].Name, White, X0 + 6.0f * Scale, TextY, ShowWidth - ClassWidth - 18.0f * Scale, 1.05f * Scale);
		if (!Class.IsEmpty())
		{
			const FLinearColor ClassColor = Info.TerrainSource.ResolutionClass == TEXT("fine") ? Good : Info.TerrainSource.ResolutionClass == TEXT("medium") ? SunColor : Lost;
			DrawText(Class, ClassColor, Row.Show.Max.X - ViewX0 - ClassWidth - 4.0f * Scale, TextY + 2.0f * Scale, Font, 0.85f * Scale);
		}
		const TPair<const FBox2D*, const TCHAR*> Pins[] = { { &Row.PinLeft, TEXT("Left") }, { &Row.PinRight, TEXT("Right") } };
		for (int32 I = 0; I < 2; ++I)
		{
			const FBox2D& Box = *Pins[I].Key;
			const bool bOn = I == 0 ? bLeft : bRight;
			Fill(Box, Box.IsInside(Mouse) ? FLinearColor(0.9f, 0.9f, 0.9f, 1.0f) : bOn ? FLinearColor(0.45f, 0.70f, 0.95f, 1.0f) : FLinearColor(0.34f, 0.34f, 0.38f, 1.0f));
			Fill(Box.ExpandBy(-1.5), bOn ? FLinearColor(0.13f, 0.27f, 0.42f, 1.0f) : FLinearColor(0.07f, 0.07f, 0.09f, 1.0f));
			float TextWidth = 0.0f;
			GetTextSize(Pins[I].Value, TextWidth, Unused, Font, 0.85f * Scale);
			DrawText(Pins[I].Value, White, 0.5f * (Box.Min.X + Box.Max.X) - ViewX0 - 0.5f * TextWidth, TextY + 2.0f * Scale, Font, 0.85f * Scale);
		}
	}
	// Custom coordinates: handed to the science core, which must be on this machine.
	if (Picker.EntryLabelPosition.X >= ViewX0 && Picker.EntryLabelPosition.X < ViewX1)
	{
		const FLsnCustomEntry& Entry = GameMode.GetCustomEntry();
		DrawFit(TEXT("CUSTOM COORDINATES   computed by the science core on this machine; type the numbers, Tab changes the field, Enter computes"), Dim,
			Picker.EntryLabelPosition.X - ViewX0, Picker.EntryLabelPosition.Y, Picker.Compute.Max.X - Picker.EntryLabelPosition.X, 0.85f * Scale);
		const TPair<const FBox2D*, const TCHAR*> Fields[] = { { &Picker.LatField, TEXT("latitude") }, { &Picker.LonField, TEXT("longitude, east +") } };
		for (int32 I = 0; I < 2; ++I)
		{
			const FBox2D& Box = *Fields[I].Key;
			const bool bFocus = Entry.Focus == I;
			float LabelWidth = 0.0f, Unused = 0.0f;
			GetTextSize(Fields[I].Value, LabelWidth, Unused, Font, 0.9f * Scale);
			DrawText(Fields[I].Value, White, Box.Min.X - ViewX0 - LabelWidth - 8.0f * Scale, Box.Min.Y + 0.5f * (Box.Max.Y - Box.Min.Y) - 8.0f * Scale, Font, 0.9f * Scale);
			Fill(Box, bFocus ? FLinearColor(1.0f, 0.70f, 0.18f, 1.0f) : FLinearColor(0.34f, 0.34f, 0.38f, 1.0f));
			Fill(Box.ExpandBy(-2.0), FLinearColor(0.03f, 0.03f, 0.04f, 1.0f));
			const FString& Value = I == 0 ? Entry.Latitude : Entry.Longitude;
			// A caret in the focused field, blinking.
			const bool bCaret = bFocus && FMath::Fmod(GetWorld()->GetRealTimeSeconds(), 1.0) < 0.5;
			DrawText(Value + (bCaret ? TEXT("_") : TEXT("")), White, Box.Min.X - ViewX0 + 8.0f * Scale, Box.Min.Y + 0.5f * (Box.Max.Y - Box.Min.Y) - 10.0f * Scale, Font, 1.2f * Scale);
		}
		const bool bHover = Picker.Compute.IsInside(Mouse);
		Fill(Picker.Compute, FLinearColor(1.0f, 0.70f, 0.18f, 1.0f));
		Fill(Picker.Compute.ExpandBy(-2.0), bHover ? FLinearColor(1.0f, 0.80f, 0.36f, 1.0f) : FLinearColor(0.92f, 0.64f, 0.17f, 1.0f));
		const TCHAR* Label = Entry.bRunning ? TEXT("computing ...") : TEXT("Compute and show");
		float LabelWidth = 0.0f, Unused = 0.0f;
		GetTextSize(Label, LabelWidth, Unused, Font, 1.05f * Scale);
		DrawText(Label, FLinearColor(0.03f, 0.02f, 0.0f), 0.5f * (Picker.Compute.Min.X + Picker.Compute.Max.X) - ViewX0 - 0.5f * LabelWidth, Picker.Compute.Min.Y + 0.5f * (Picker.Compute.Max.Y - Picker.Compute.Min.Y) - 9.0f * Scale, Font, 1.05f * Scale);
		const float MessageWidth = (bComparing ? 0.5f * WindowSizeX : Picker.Sheet.Max.X) - Picker.MessagePosition.X - 8.0f * Scale;
		DrawWrapped(Entry.Message, Entry.bFailed ? Alert : Entry.bRunning ? SunColor : Good, Picker.MessagePosition.X - ViewX0, Picker.MessagePosition.Y, MessageWidth, 0.9f * Scale);
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
		TEXT("  I  details: package, frame, contract, test status      P  scale objects (lander, boulders)"),
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
		Y += 18.0f * TextScale;
		Rest = Part.Len() < Rest.Len() ? Rest.Mid(Part.Len()).TrimStart() : FString();
	}
	return Y;
}

void ALsnHud::DrawCalendar(const FBox2D& Box, const TArray<const ALsnSiteScene*>& Rows, int32 RequirementIndex, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	const float Width = Box.Max.X - Box.Min.X;
	if (Rows.Num() == 0 || Box.Max.Y - Box.Min.Y < 60.0f * Scale)
	{
		return;
	}
	const FLsnSitePackage& First = Rows[0]->GetPackage();
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.82f), Box.Min.X - 8.0f * Scale, Box.Min.Y - 6.0f * Scale, Width + 16.0f * Scale, Box.Max.Y - Box.Min.Y + 8.0f * Scale);
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
	Y = DrawWrapped(FString::Printf(TEXT("Lunar-day calendar, %s to %s: share of each lunar day with the Sun visible (yellow) and with the Earth visible (blue line)   [%s]"),
		*First.Time.StartUtc.Left(10), *First.Time.EndUtc.Left(10), *First.ValidationStatusOf(First.Calendar.Method)), White, Box.Min.X, Y, Width, Scale * 1.15f);
	if (Requirement)
	{
		Y = DrawWrapped(FString::Printf(TEXT("Green: landing times that meet the requirement '%s' - %s"), *Requirement->Id, *Requirement->Label), Good, Box.Min.X, Y, Width, Scale);
		Y = DrawWrapped(TEXT("This requirement is an example chosen by the team, not a mission requirement; the package cannot tell whether it is the right one. R: next requirement."), Dim, Box.Min.X, Y, Width, Scale * 0.9f);
	}
	Y += 6.0f * Scale;

	const float TextBlock = 90.0f * Scale;
	const float RowHeight = FMath::Clamp((Box.Max.Y - Y) / Rows.Num() - TextBlock, 34.0f * Scale, 120.0f * Scale);
	for (const ALsnSiteScene* Row : Rows)
	{
		const FLsnSitePackage& P = Row->GetPackage();
		const int32 H = Row->GetHeightIndex();
		DrawText(FString::Printf(TEXT("%s, observer %.1f m"), *P.SiteName, P.ObserverHeightsM[H]), White, Box.Min.X, Y, Font, Scale * 1.2f);
		Y += 22.0f * Scale;
		const FLsnCalendarQuantity* SunQ = P.Calendar.bPresent ? P.Calendar.Find(TEXT("sun_visible_s")) : nullptr;
		const FLsnCalendarQuantity* EarthQ = P.Calendar.bPresent ? P.Calendar.Find(TEXT("earth_visible_s")) : nullptr;
		if (!SunQ)
		{
			DrawText(TEXT("no calendar in this package"), Dim, Box.Min.X, Y, Font, Scale);
			Y += RowHeight + TextBlock - 22.0f * Scale;
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
			if (Period % 3 == 0 && Row == Rows[0])
			{
				DrawText(Day.StartUtc.Left(7), Dim, X0, BarBottom + 9.0f * Scale, Font, Scale * 0.8f);
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
		Y = BarBottom + 24.0f * Scale;
		if (Opportunity)
		{
			const FLsnLandingCheck Check = LsnPlanner::LandingAt(*Opportunity, NowEt);
			DrawText(FString::Printf(TEXT("%s: %s"), *LsnHudText::UtcLabelOfPosition(P, Row->GetTimePosition()), *LsnHudText::LandingSentence(Check)),
				!Check.bJudgeable ? Dim : Check.bFeasible ? Good : Lost, Box.Min.X, Y, Font, Scale * 1.15f);
			Y += 21.0f * Scale;
			FString Summary = FString::Printf(TEXT("landing possible in %.1f %% of the range that can be judged (%d windows, longest %s)"), 100.0 * Opportunity->FeasibleFraction,
				Opportunity->WindowCount, *LsnHudText::FormatDuration(Opportunity->LongestWindowS));
			if (Opportunity->Planned.bPresent)
			{
				// The slip report of the scenario's planned landing, as the package gives it.
				const FLsnSlipReport& Planned = Opportunity->Planned;
				Summary += FString::Printf(TEXT("; planned landing %s (green line): %s"), *Planned.Utc.Left(16).Replace(TEXT("T"), TEXT(" ")),
					Planned.bFeasible ? *FString::Printf(TEXT("meets it, can slip %s%s"), Planned.bSlipIsLowerBound ? TEXT("at least ") : TEXT(""), *LsnHudText::FormatDuration(Planned.SlipToleranceS))
					: Planned.bHasWait ? *FString::Printf(TEXT("does not meet it, next window after %s"), *LsnHudText::FormatDuration(Planned.WaitS)) : TEXT("does not meet it, no window left"));
			}
			Y = DrawWrapped(Summary + FString::Printf(TEXT("   [%s]"), *P.ValidationStatusOf(Opportunity->Method)), Dim, Box.Min.X, Y, Width, Scale * 0.9f);
		}
		else
		{
			DrawText(TEXT("this package states no requirement: no landing windows"), Dim, Box.Min.X, Y, Font, Scale * 0.9f);
			Y += 39.0f * Scale;
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
		Y = DrawWrapped(FString::Printf(TEXT("Stated horizon error %.2f deg: the pale edges of the time strips and the ranges under the countdowns   [%s]"), U.HorizonErrorDeg, *P.ValidationStatusOf(U.HorizonMethod)), White, X, Y, Width, Scale * 1.1f);
		Y = DrawWrapped(U.HorizonAssumption, Dim, X, Y, Width, Scale * 0.85f);
		Y += 8.0f * Scale;
	}
	if (U.bHasEllipse)
	{
		const FLsnEllipseStats* Stats = U.EllipseStats.Find(TEXT("SUN"));
		Y = DrawWrapped(FString::Printf(TEXT("Stated landing ellipse %.1f x %.1f km, major axis towards azimuth %.0f deg, %d sample points, observer %.1f m   [%s]"), 2.0 * U.SemiMajorM / 1000.0, 2.0 * U.SemiMinorM / 1000.0,
			U.AzimuthDeg, U.Points.Num(), P.ObserverHeightsM.IsValidIndex(U.EllipseHeightIndex) ? P.ObserverHeightsM[U.EllipseHeightIndex] : 0.0, *P.ValidationStatusOf(U.EllipseMethod)), White, X, Y, Width, Scale * 1.1f);
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
		const FLsnHeightTradeQuantity* Sun = P.HeightTrade.Find(TEXT("sun_visible_s"));
		Y = DrawWrapped(Lines[0] + FString::Printf(TEXT("   [%s]"), Sun ? *P.ValidationStatusOf(Sun->Method) : TEXT("unknown")), Dim, X, Y, Width, Scale * 0.9f);
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
