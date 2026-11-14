#include "Scene/LsnHud.h"

#include "Engine/Canvas.h"
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

FLsnTimeStripLayout FLsnTimeStripLayout::Make(float SizeX, float SizeY, const FLsnSitePackage& Package)
{
	FLsnTimeStripLayout Layout;
	const float Left = 0.06f * SizeX, Right = 0.94f * SizeX;
	Layout.Zoom = FBox2D(FVector2D(Left, SizeY * 0.835f), FVector2D(Right, SizeY * 0.895f));
	Layout.WholeRange = FBox2D(FVector2D(Left, SizeY * 0.935f), FVector2D(Right, SizeY * 0.965f));
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
		const FLsnWindow* Window = P.FindWindow(Row.WindowId, H);
		for (int32 I = 0; Window && I < Window->StartsEtS.Num(); ++I)
		{
			if (Window->EndsEtS[I] < FromEt || Window->StartsEtS[I] > ToEt)
			{
				continue;
			}
			const float X0 = X(Window->StartsEtS[I]), X1 = X(Window->EndsEtS[I]);
			DrawRect(Row.Color, X0, Box.Min.Y + Row.Top * Height, FMath::Max(X1 - X0, 1.0f), 0.38f * Height);
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
	const float Scale = FMath::Clamp(FMath::Min(Canvas->SizeY / 720.0f, Canvas->SizeX / 1000.0f), 0.55f, 4.0f);
	const float SizeX = Canvas->SizeX, SizeY = Canvas->SizeY;
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

	// --- read-out, top left ------------------------------------------------------------
	TArray<FLsnHudLine> Lines;
	LsnHudText::BuildStatusLines(P, H, Position, Lines, Scene->GetGroundNote());
	if (bComparing)
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
	if (Pawn && !bComparing)
	{
		Line(FString::Printf(TEXT("looking az %.2f  el %.2f   field of view %.1f deg%s"), Pawn->GetAzimuthDeg(), Pawn->GetElevationDeg(), Pawn->GetFovDeg(),
			Pawn->IsFollowingSun() ? TEXT("   view follows the Sun's azimuth (F)") : TEXT("")), Dim);
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
	if (!P.bHasTimeline)
	{
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
	if (Pawn)
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
		if (!Scene->IsObstacleViewEnabled() || !P.BlockingAt(Body, H, Sample, Blocking) || !Blocking.bHiddenOrPartly || !Blocking.Obstacle)
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
}
