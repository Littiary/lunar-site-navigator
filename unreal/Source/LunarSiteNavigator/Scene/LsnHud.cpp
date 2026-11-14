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

FLsnToolbar FLsnToolbar::Make(float SizeX, float SizeY)
{
	// Upper rows: the time. Lower rows: sites, planner pages and view.
	static const TPair<const TCHAR*, const TCHAR*> Entries[] = {
		{ TEXT("play"), TEXT("Play / pause") }, { TEXT("slower"), TEXT("Slower") }, { TEXT("faster"), TEXT("Faster") },
		{ TEXT("sample_back"), TEXT("< Step") }, { TEXT("sample_forward"), TEXT("Step >") }, { TEXT("day_back"), TEXT("< Day") }, { TEXT("day_forward"), TEXT("Day >") },
		{ TEXT("sun_event_back"), TEXT("< Sunrise / set") }, { TEXT("sun_event_forward"), TEXT("Sunrise / set >") }, { TEXT("height_next"), TEXT("Observer height") },
		{ TEXT("next_site"), TEXT("Next site") }, { TEXT("compare"), TEXT("Two sites") }, { TEXT("next_right_site"), TEXT("Next right site") },
		{ TEXT("page_calendar"), TEXT("Calendar") }, { TEXT("page_uncertainty"), TEXT("Uncertainty") }, { TEXT("page_trade"), TEXT("Mast / pairs") },
		{ TEXT("obstacle"), TEXT("Obstacle") }, { TEXT("follow_sun"), TEXT("Follow Sun") }, { TEXT("quality"), TEXT("Low quality") }, { TEXT("help"), TEXT("Help (F1)") },
	};
	const int32 Count = UE_ARRAY_COUNT(Entries);
	const float Left = 0.06f * SizeX, Right = 0.94f * SizeX;
	// Ten in a row where a label fits; otherwise five.
	const int32 Columns = (Right - Left) / 10.0f >= 105.0f * TextScale(SizeX, SizeY) ? 10 : 5;
	const int32 Rows = (Count + Columns - 1) / Columns;
	const float RowHeight = FMath::Max(0.032f * SizeY, 23.0f), Gap = 0.006f * SizeY;
	const float Bottom = 0.992f * SizeY;
	const float CellWidth = (Right - Left) / Columns;

	FLsnToolbar Toolbar;
	Toolbar.Top = Bottom - Rows * RowHeight - (Rows - 1) * Gap;
	for (int32 I = 0; I < Count; ++I)
	{
		const float X0 = Left + CellWidth * (I % Columns), Y0 = Toolbar.Top + (RowHeight + Gap) * (I / Columns);
		Toolbar.Buttons.Add({ Entries[I].Key, Entries[I].Value, FBox2D(FVector2D(X0 + 0.5f * Gap, Y0), FVector2D(X0 + CellWidth - 0.5f * Gap, Y0 + RowHeight)) });
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

FLsnTimeStripLayout FLsnTimeStripLayout::Make(float SizeX, float SizeY, const FLsnSitePackage& Package)
{
	FLsnTimeStripLayout Layout;
	const float Left = 0.06f * SizeX, Right = 0.94f * SizeX;
	// Bottom-up from the buttons: each strip has a line of text below it.
	const float ButtonsTop = FLsnToolbar::Make(SizeX, SizeY).Top;
	const float WholeBottom = ButtonsTop - 0.030f * SizeY, ZoomBottom = WholeBottom - 0.060f * SizeY;
	Layout.WholeRange = FBox2D(FVector2D(Left, WholeBottom - 0.030f * SizeY), FVector2D(Right, WholeBottom));
	Layout.Zoom = FBox2D(FVector2D(Left, ZoomBottom - 0.060f * SizeY), FVector2D(Right, ZoomBottom));
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
	DrawText(FString::Printf(TEXT("horizon of the package all round, %+.0f to %+.0f deg; white lines: this view   [%s]"), Pano.MinElevationDeg, Pano.MaxElevationDeg,
		*P.ValidationStatusOf(P.HorizonElevationMethod)), Dim, Pano.Box.Min.X, Pano.Box.Max.Y + 1.0f * Scale, Font, Scale * 0.85f);
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
	// Text is sized for the height of the view, and made smaller where the view is narrow
	// (the two halves of a comparison).
	const float SizeX = Canvas->SizeX, SizeY = Canvas->SizeY;
	const float Scale = FLsnToolbar::TextScale(SizeX, SizeY);
	const float X = 16.0f * Scale;
	float Y = 16.0f * Scale;
	// The read-out keeps to the left column; a line that is too long continues on the next.
	const float ColumnWidth = (bComparing ? 1.0f : 0.60f) * SizeX - 2.0f * X;
	auto Line = [&](const FString& Text, const FLinearColor& Color, float Size = 1.0f)
	{
		FString Rest = Text;
		while (!Rest.IsEmpty())
		{
			FString Part = Rest;
			float Width = 0.0f, Height = 0.0f;
			GetTextSize(Part, Width, Height, Font, Scale * Size);
			while (Width > ColumnWidth)
			{
				int32 Space = INDEX_NONE;
				if (!Part.FindLastChar(TEXT(' '), Space) || Space <= 0)
				{
					break;
				}
				Part.LeftInline(Space);
				GetTextSize(Part, Width, Height, Font, Scale * Size);
			}
			DrawText(Part, Color, X, Y, Font, Scale * Size);
			Y += 18.0f * Scale * Size;
			Rest = Part.Len() < Rest.Len() ? TEXT("      ") + Rest.Mid(Part.Len()).TrimStart() : FString();
		}
	};

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
		Line(TEXT("No package loaded."), Alert);
		if (GameMode)
		{
			Line(GameMode->GetLoadError(), Alert);
		}
		return;
	}
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();
	const double Position = Scene->GetTimePosition();
	const ALsnObserverPawn* Pawn = Cast<ALsnObserverPawn>(GetOwningPawn());

	// For stills: no panels. A synthetic package keeps its marker; every still keeps a caption
	// that says which package, site and time it shows.
	if (FParse::Param(FCommandLine::Get(), TEXT("LsnNoHud")))
	{
		if (P.bSynthetic)
		{
			Line(FString::Printf(TEXT("%s - invented values for interface testing, not results"), LsnHudText::SyntheticMarker()), Alert, 1.4f);
		}
		const FString Viewpoint = (Pawn && Pawn->IsOverview()) ? (Pawn->GetCameraUpM() >= 1000.0 ? FString::Printf(TEXT("overview from %.0f km above the site, not the observer's view"), Pawn->GetCameraUpM() / 1000.0)
			: FString::Printf(TEXT("camera %.0f m above and behind the observer, not the observer's view"), Pawn->GetCameraUpM()))
			: FString::Printf(TEXT("observer %.1f m"), P.ObserverHeightsM[H]);
		DrawText(FString::Printf(TEXT("%s   %s   %s   package %s (contract %s)"), *P.SiteName, *LsnHudText::UtcLabelOfPosition(P, Position), *Viewpoint, *P.PackageId, *P.ContractVersion),
			Dim, X, SizeY - 26.0f * Scale, Font, Scale * 0.9f);
		return;
	}

	// --- read-out, top left ------------------------------------------------------------
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	// The calendar needs the middle of the screen: the read-out is then as short as side by side.
	const bool bOverview = Pawn && Pawn->IsOverview();
	const bool bCompact = bComparing || bOverview || Page == ELsnPlannerPage::Calendar;
	TArray<FLsnHudLine> Lines;
	LsnHudText::BuildStatusLines(P, H, Position, Lines, Scene->GetGroundNote());
	if (bCompact)
	{
		// Side by side there is room for the marker, the site and the package only;
		// the full read-out is in the single view (key C).
		const int32 Keep = P.bSynthetic ? 3 : 2;
		Lines.SetNum(FMath::Min(Lines.Num(), Keep));
		if (Lines.IsValidIndex(Keep - 2))
		{
			Lines[Keep - 2].Text = P.SiteName;
			Lines[Keep - 2].Size = 1.9f;
		}
		Lines.Add({ FString::Printf(TEXT("lat %.4f  lon %.4f (east +)   observer %.1f m   frame %s"), P.LatDeg, P.LonDeg, P.ObserverHeightsM[H], *P.Frame), White, 1.0f });
	}
	for (const FLsnHudLine& L : Lines)
	{
		Line(L.Text, L.Color, L.Size);
	}
	if (Pawn && !bCompact)
	{
		Line(FString::Printf(TEXT("looking az %.2f  el %.2f   field of view %.1f deg%s"), Pawn->GetAzimuthDeg(), Pawn->GetElevationDeg(), Pawn->GetFovDeg(),
			Pawn->IsFollowingSun() ? TEXT("   view follows the Sun's azimuth (F)") : TEXT("")), Dim);
	}
	if (bOverview)
	{
		Line(FString::Printf(TEXT("Overview from %.1f km above the site: not the observer's view. Horizon, countdowns and obstacle refer to the observer at the site."), Pawn->GetCameraUpM() / 1000.0), Alert, 1.1f);
	}
	if (Scene->GetSkippedHorizonSamples() > 0)
	{
		Line(FString::Printf(TEXT("%d horizon samples are unknown in the package and are not drawn."), Scene->GetSkippedHorizonSamples()), Alert);
	}
	if (bComparing && View == 1 && GameMode && !GameMode->IsRightViewInRange())
	{
		Line(TEXT("The selected instant is outside this package's time range: this half shows its nearest sample."), Alert, 1.2f);
	}

	// --- panorama, summary numbers and site list ----------------------------------------
	FLsnPanorama Pano;
	LsnPlanner::PanoramaRange(P, H, Pano.MinElevationDeg, Pano.MaxElevationDeg);
	float RightX = 0.0f, RightY = 0.0f;
	if (bComparing)
	{
		Y += 6.0f * Scale;
		Pano.Box = FBox2D(FVector2D(X, Y), FVector2D(SizeX - X, Y + 0.12f * SizeY));
		RightX = X;
		RightY = Pano.Box.Max.Y + 20.0f * Scale;
	}
	else
	{
		Pano.Box = FBox2D(FVector2D(0.62f * SizeX, 16.0f * Scale), FVector2D(SizeX - 16.0f * Scale, 16.0f * Scale + 0.15f * SizeY));
		RightX = Pano.Box.Min.X;
		RightY = Pano.Box.Max.Y + 20.0f * Scale;
	}
	DrawPanorama(Pano, *Scene, Pawn, Scale);

	const float RightWidth = (bComparing ? SizeX - X : SizeX - 16.0f * Scale) - RightX;
	if (Page == ELsnPlannerPage::Uncertainty)
	{
		RightY = DrawUncertainty(*Scene, RightX, RightY, RightWidth, Scale);
	}
	else if (Page == ELsnPlannerPage::Trade && GameMode)
	{
		RightY = DrawTrade(*Scene, *GameMode, RightX, RightY, RightWidth, Scale);
	}
	else if (Page != ELsnPlannerPage::Calendar)
	{
		TArray<FString> Metrics;
		LsnPlanner::BuildMetricLines(P, H, Metrics);
		if (Metrics.Num() > 0 && P.bHasTimeline)
		{
			const FLsnMetric* Any = P.Metrics.Num() > 0 ? &P.Metrics[0] : nullptr;
			DrawText(FString::Printf(TEXT("whole computed window, %s to %s, observer %.1f m   [%s]"), *P.Time.StartUtc.Left(10), *P.Time.EndUtc.Left(10), P.ObserverHeightsM[H],
				Any ? *P.ValidationStatusOf(Any->Method) : TEXT("unknown")), Dim, RightX, RightY, Font, Scale * 0.9f);
			RightY += 17.0f * Scale;
			for (const FString& Metric : Metrics)
			{
				DrawText(Metric, White, RightX, RightY, Font, Scale * 1.15f);
				RightY += 21.0f * Scale;
			}
		}
		if (GameMode && !bComparing && GameMode->GetSites().Num() > 0)
		{
			RightY += 8.0f * Scale;
			DrawText(TEXT("sites of the package root (keys 1-9; Shift: side by side on the right; C: comparison)"), Dim, RightX, RightY, Font, Scale * 0.9f);
			RightY += 17.0f * Scale;
			for (int32 I = 0; I < GameMode->GetSites().Num() && I < 9; ++I)
			{
				const bool bSelected = GameMode->GetSelectedSite(0) == I;
				DrawText(FString::Printf(TEXT("%s %d  %s"), bSelected ? TEXT(">") : TEXT("  "), I + 1, *GameMode->GetSites()[I].Name), bSelected ? White : Dim, RightX, RightY, Font, Scale * 1.1f);
				RightY += 20.0f * Scale;
			}
		}
	}
	// --- buttons: every main action can be reached with the mouse (left or only view) ------
	if (View == 0)
	{
		DrawToolbar(FLsnToolbar::Make(SizeX, SizeY), *Scene, Pawn, GameMode, Scale);
	}
	if (!P.bHasTimeline)
	{
		if (View == 0 && Pawn && Pawn->IsHelpShown())
		{
			DrawHelp(SizeX, SizeY, Scale);
		}
		return;
	}

	// --- countdown and obstacle panel, time strips, bottom -------------------------------
	const FLsnTimeStripLayout Layout = FLsnTimeStripLayout::Make(SizeX, SizeY, P);
	const double EtS = P.EtOfPosition(Position);
	const FLsnCountdown Sun = P.CountdownAt(TEXT("SUN"), H, EtS);
	const FLsnCountdown Earth = P.CountdownAt(TEXT("EARTH"), H, EtS);
	// The panel is laid out bottom-up from the time strips, so that it grows upwards.
	struct FPanelLine { FString Text; FLinearColor Color; float Size; };
	TArray<FPanelLine> Panel;
	const FString Utc = LsnHudText::UtcLabelOfPosition(P, Position);
	Panel.Add({ Utc.IsEmpty() ? FString(TEXT("UTC label not available")) : Utc, White, 2.0f });
	const int32 Sample = Scene->GetTimeIndex();
	auto AddBody = [&](const TCHAR* Body, const FLsnCountdown& Countdown, const FLinearColor& Color, const FLinearColor& BlockedColor)
	{
		if (Countdown.bAvailable)
		{
			Panel.Add({ LsnHudText::CountdownSentence(Body, Countdown), Countdown.bVisibleNow ? Color : Lost, 1.6f });
			// With a stated horizon error the event is a range, not an instant.
			const FLsnEvent* Event = LsnPlanner::EventEndingCountdown(P, Body, H, EtS, Countdown);
			if (Event && Event->bHasBand && Event->LatestEtS > Event->EarliestEtS && P.Uncertainty.bHasHorizonError)
			{
				Panel.Add({ TEXT("    ") + LsnHudText::CountdownBandSentence(P, EtS, *Event) + FString::Printf(TEXT("   [%s]"), *P.ValidationStatusOf(P.Uncertainty.HorizonMethod)), Color, 1.0f });
			}
		}
		FLsnBlocking Blocking;
		TArray<FString> Sentences;
		if (Scene->IsObstacleViewEnabled() && P.BlockingAt(Body, H, Sample, Blocking))
		{
			LsnHudText::BlockerSentences(Body, P, Blocking, Sentences);
			for (int32 I = 0; I < Sentences.Num(); ++I)
			{
				Panel.Add({ TEXT("    ") + Sentences[I], I == 2 ? Alert : BlockedColor, I == 0 ? 1.3f : 1.1f });
			}
			if (Sentences.Num() > 0)
			{
				Panel.Add({ FString::Printf(TEXT("    obstacle %d of the package, sample %d   [%s: %s]"), Blocking.ObstacleId, Sample, *P.BlockingMethod, *P.ValidationStatusOf(P.BlockingMethod)), Dim, 0.9f });
			}
		}
	};
	AddBody(TEXT("SUN"), Sun, SunColor, FLinearColor(1.0f, 0.45f, 0.2f));
	AddBody(TEXT("EARTH"), Earth, EarthColor, FLinearColor(0.3f, 0.85f, 1.0f));
	// Landing at the selected time, for the chosen requirement of the package.
	if (P.Requirements.Num() > 0)
	{
		const FLsnRequirement& Requirement = P.Requirements[(GameMode ? GameMode->GetRequirementIndex() : 0) % P.Requirements.Num()];
		if (const FLsnOpportunity* Opportunity = P.FindOpportunity(Requirement.Id, H))
		{
			const FLsnLandingCheck Check = LsnPlanner::LandingAt(*Opportunity, EtS);
			Panel.Add({ LsnHudText::LandingSentence(Check), !Check.bJudgeable ? Dim : Check.bFeasible ? Good : Lost, 1.3f });
			Panel.Add({ FString::Printf(TEXT("    requirement '%s': an example chosen by the team (K: calendar)   [%s]"), *Requirement.Id, *P.ValidationStatusOf(Opportunity->Method)), Dim, 0.9f });
		}
	}
	if (Sun.bAvailable || Earth.bAvailable)
	{
		const FString Method = Sun.bAvailable ? Sun.Method : Earth.Method;
		Panel.Add({ FString::Printf(TEXT("countdowns from the package windows sun_visible / earth_visible, TDB   [%s: %s]"), *Method, *P.ValidationStatusOf(Method)), Dim, 0.9f });
	}
	float PanelHeight = 0.0f;
	for (const FPanelLine& L : Panel)
	{
		PanelHeight += 19.0f * Scale * L.Size;
	}
	const float PanelX = Layout.Zoom.Min.X;
	float PanelY = Layout.Zoom.Min.Y - PanelHeight - 10.0f * Scale;
	const float PanelTop = PanelY;
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), PanelX - 8.0f * Scale, PanelY - 6.0f * Scale, (bComparing ? 0.88f : 0.62f) * SizeX, PanelHeight + 10.0f * Scale);
	for (int32 I = 0; I < Panel.Num(); ++I)
	{
		DrawText(Panel[I].Text, Panel[I].Color, PanelX, PanelY, Font, Scale * Panel[I].Size);
		if (I == 0 && Pawn && Pawn->IsPlaying())
		{
			DrawText(FString::Printf(TEXT("playing, %.1f h of site time per second"), Pawn->GetPlayRateSamplesPerSecond() * P.Time.StepS / 3600.0), Dim,
				PanelX + 330.0f * Scale, PanelY + 12.0f * Scale, Font, Scale);
		}
		PanelY += 19.0f * Scale * Panel[I].Size;
	}

	// --- where the Sun and the Earth are when they are outside the view -----------------
	if (Pawn && !bOverview)
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

	DrawStrip(Layout.Zoom, P, H, Position - Layout.ZoomHalfWidthSamples, Position + Layout.ZoomHalfWidthSamples, Position, Scale);
	DrawStrip(Layout.WholeRange, P, H, 0.0, P.Time.Count - 1, Position, Scale);
	DrawText(FString::Printf(TEXT("%.0f days around the selected time   yellow: Sun visible   blue: Earth visible"), 2.0 * Layout.ZoomHalfWidthSamples * P.Time.StepS / 86400.0),
		Dim, Layout.Zoom.Min.X, Layout.Zoom.Max.Y + 2.0f * Scale, Font, Scale * 0.9f);
	DrawText(FString::Printf(TEXT("%s   to   %s"), *P.Time.StartUtc, *P.Time.EndUtc), Dim, Layout.WholeRange.Min.X, Layout.WholeRange.Max.Y + 2.0f * Scale, Font, Scale * 0.9f);
	if (View == 0)
	{
		const FString Hint = TEXT("mouse: drag on a strip for the time   hold the right button to look round   wheel to zoom");
		float HintWidth = 0.0f, HintHeight = 0.0f;
		GetTextSize(Hint, HintWidth, HintHeight, Font, Scale * 0.9f);
		DrawText(Hint, White, Layout.Zoom.Max.X - HintWidth, Layout.Zoom.Max.Y + 2.0f * Scale, Font, Scale * 0.9f);
	}

	// Calendar page: the lunar days of this site, and of the other site of a comparison, on one time axis.
	if (Page == ELsnPlannerPage::Calendar && GameMode)
	{
		TArray<const ALsnSiteScene*> Rows;
		Rows.Add(Scene);
		if (bComparing)
		{
			const ALsnSiteScene* Other = GameMode->GetSceneOfView(1 - View);
			if (Other && Other->HasPackage())
			{
				Rows.Add(Other);
			}
		}
		const float Top = FMath::Max(RightY, Y) + 10.0f * Scale;
		DrawCalendar(FBox2D(FVector2D(Layout.Zoom.Min.X, Top), FVector2D(Layout.Zoom.Max.X, PanelTop - 14.0f * Scale)), Rows, GameMode->GetRequirementIndex(), Scale);
	}
	if (View == 0 && Pawn && Pawn->IsHelpShown())
	{
		DrawHelp(SizeX, SizeY, Scale);
	}
}

void ALsnHud::DrawToolbar(const FLsnToolbar& Toolbar, const ALsnSiteScene& Scene, const ALsnObserverPawn* Pawn, const ALsnViewGameMode* GameMode, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	FVector2D Mouse(-1.0, -1.0);
	float MouseX = 0.0f, MouseY = 0.0f;
	const APlayerController* Player = GetOwningPlayerController();
	if (Player && Player->bShowMouseCursor && Player->GetMousePosition(MouseX, MouseY))
	{
		Mouse = FVector2D(MouseX, MouseY);
	}
	const ELsnPlannerPage Page = GameMode ? GameMode->GetPage() : ELsnPlannerPage::Summary;
	for (const FLsnButton& Button : Toolbar.Buttons)
	{
		// A button that is a switch is drawn lit while it is on.
		const FName A = Button.Action;
		const bool bOn = (A == TEXT("play") && Pawn && Pawn->IsPlaying()) || (A == TEXT("compare") && GameMode && GameMode->IsComparing())
			|| (A == TEXT("page_calendar") && Page == ELsnPlannerPage::Calendar) || (A == TEXT("page_uncertainty") && Page == ELsnPlannerPage::Uncertainty)
			|| (A == TEXT("page_trade") && Page == ELsnPlannerPage::Trade) || (A == TEXT("obstacle") && Scene.IsObstacleViewEnabled())
			|| (A == TEXT("follow_sun") && Pawn && Pawn->IsFollowingSun()) || (A == TEXT("quality") && GameMode && GameMode->IsLowQuality())
			|| (A == TEXT("help") && Pawn && Pawn->IsHelpShown());
		const bool bHover = Button.Box.IsInside(Mouse);
		const float Width = Button.Box.Max.X - Button.Box.Min.X, Height = Button.Box.Max.Y - Button.Box.Min.Y;
		const FLinearColor Fill = bOn ? FLinearColor(0.16f, 0.30f, 0.46f, 0.95f) : FLinearColor(0.09f, 0.09f, 0.11f, 0.90f);
		DrawRect(bHover ? FLinearColor(0.85f, 0.85f, 0.85f, 1.0f) : FLinearColor(0.38f, 0.38f, 0.42f, 1.0f), Button.Box.Min.X, Button.Box.Min.Y, Width, Height);
		DrawRect(bHover ? FLinearColor(Fill.R + 0.10f, Fill.G + 0.10f, Fill.B + 0.10f, 1.0f) : Fill, Button.Box.Min.X + 1.0f, Button.Box.Min.Y + 1.0f, Width - 2.0f, Height - 2.0f);
		// The label is made smaller where it would not fit.
		float TextSize = Scale * 0.95f, TextWidth = 0.0f, TextHeight = 0.0f;
		GetTextSize(Button.Label, TextWidth, TextHeight, Font, TextSize);
		if (TextWidth > Width - 8.0f)
		{
			TextSize *= (Width - 8.0f) / TextWidth;
			GetTextSize(Button.Label, TextWidth, TextHeight, Font, TextSize);
		}
		DrawText(Button.Label, White, Button.Box.Min.X + 0.5f * (Width - TextWidth), Button.Box.Min.Y + 0.5f * (Height - TextHeight), Font, TextSize);
	}
}

void ALsnHud::DrawHelp(float SizeX, float SizeY, float Scale)
{
	static const TCHAR* Lines[] = {
		TEXT("Mouse"),
		TEXT("  click a button below; a lit button is switched on"),
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
		TEXT("  H  horizon line of the package      L  weak fill light (a display aid)      G  lower drawing quality"),
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
			DrawText(Summary + FString::Printf(TEXT("   [%s]"), *P.ValidationStatusOf(Opportunity->Method)), Dim, Box.Min.X, Y, Font, Scale * 0.9f);
			Y += 18.0f * Scale;
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
