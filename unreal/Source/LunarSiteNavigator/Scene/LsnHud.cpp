#include "Scene/LsnHud.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
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

void LsnHudText::BuildStatusLines(const FLsnSitePackage& P, int32 H, double TimePosition, TArray<FLsnHudLine>& OutLines)
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
	Line(TEXT("Ground between the site and the horizon line is a placeholder surface, not elevation data."), Dim);
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

void ALsnHud::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas || !GEngine)
	{
		return;
	}
	UFont* Font = GEngine->GetMediumFont();
	const float Scale = FMath::Max(1.0f, Canvas->SizeY / 720.0f);
	const float X = 16.0f * Scale;
	float Y = 16.0f * Scale;
	auto Line = [&](const FString& Text, const FLinearColor& Color, float Size = 1.0f)
	{
		DrawText(Text, Color, X, Y, Font, Scale * Size);
		Y += 18.0f * Scale * Size;
	};

	const ALsnSiteScene* Scene = nullptr;
	for (TActorIterator<ALsnSiteScene> It(GetWorld()); It; ++It)
	{
		Scene = *It;
		break;
	}
	if (!Scene || !Scene->HasPackage())
	{
		Line(TEXT("No package loaded."), Alert);
		if (const ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>())
		{
			Line(GameMode->GetLoadError(), Alert);
		}
		return;
	}
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();
	const double Position = Scene->GetTimePosition();
	const ALsnObserverPawn* Pawn = Cast<ALsnObserverPawn>(GetOwningPawn());

	TArray<FLsnHudLine> Lines;
	LsnHudText::BuildStatusLines(P, H, Position, Lines);
	for (const FLsnHudLine& L : Lines)
	{
		Line(L.Text, L.Color, L.Size);
	}
	if (Pawn)
	{
		Line(FString::Printf(TEXT("looking az %.2f  el %.2f   field of view %.1f deg"), Pawn->GetAzimuthDeg(), Pawn->GetElevationDeg(), Pawn->GetFovDeg()), Dim);
	}
	if (Scene->GetSkippedHorizonSamples() > 0)
	{
		Line(FString::Printf(TEXT("%d horizon samples are unknown in the package and are not drawn."), Scene->GetSkippedHorizonSamples()), Alert);
	}
	if (!P.bHasTimeline)
	{
		return;
	}

	// Countdown panel and time strips.
	const FLsnTimeStripLayout Layout = FLsnTimeStripLayout::Make(Canvas->SizeX, Canvas->SizeY, P);
	const double EtS = P.EtOfPosition(Position);
	const FLsnCountdown Sun = P.CountdownAt(TEXT("SUN"), H, EtS);
	const FLsnCountdown Earth = P.CountdownAt(TEXT("EARTH"), H, EtS);
	float PanelY = Layout.Zoom.Min.Y - 118.0f * Scale;
	const float PanelX = Layout.Zoom.Min.X;
	const FString Utc = LsnHudText::UtcLabelOfPosition(P, Position);
	DrawText(Utc.IsEmpty() ? FString(TEXT("UTC label not available")) : Utc, White, PanelX, PanelY, Font, Scale * 2.0f);
	if (Pawn && Pawn->IsPlaying())
	{
		DrawText(FString::Printf(TEXT("playing, %.0f h of site time per second"), Pawn->GetPlayRateSamplesPerSecond() * P.Time.StepS / 3600.0), Dim,
			PanelX + 330.0f * Scale, PanelY + 12.0f * Scale, Font, Scale);
	}
	PanelY += 38.0f * Scale;
	if (Sun.bAvailable)
	{
		DrawText(LsnHudText::CountdownSentence(TEXT("SUN"), Sun), Sun.bVisibleNow ? SunColor : Lost, PanelX, PanelY, Font, Scale * 1.6f);
		PanelY += 29.0f * Scale;
	}
	if (Earth.bAvailable)
	{
		DrawText(LsnHudText::CountdownSentence(TEXT("EARTH"), Earth), Earth.bVisibleNow ? EarthColor : Lost, PanelX, PanelY, Font, Scale * 1.6f);
		PanelY += 29.0f * Scale;
	}
	if (Sun.bAvailable || Earth.bAvailable)
	{
		const FString Method = Sun.bAvailable ? Sun.Method : Earth.Method;
		DrawText(FString::Printf(TEXT("from the package windows sun_visible / earth_visible, TDB   [%s: %s]"), *Method, *P.ValidationStatusOf(Method)), Dim, PanelX, PanelY, Font, Scale * 0.9f);
	}

	DrawStrip(Layout.Zoom, P, H, Position - Layout.ZoomHalfWidthSamples, Position + Layout.ZoomHalfWidthSamples, Position, Scale);
	DrawStrip(Layout.WholeRange, P, H, 0.0, P.Time.Count - 1, Position, Scale);
	DrawText(FString::Printf(TEXT("%.0f days around the selected time   yellow: Sun visible   blue: Earth visible"), 2.0 * Layout.ZoomHalfWidthSamples * P.Time.StepS / 86400.0),
		Dim, Layout.Zoom.Min.X, Layout.Zoom.Max.Y + 2.0f * Scale, Font, Scale * 0.9f);
	DrawText(FString::Printf(TEXT("%s   to   %s"), *P.Time.StartUtc, *P.Time.EndUtc), Dim, Layout.WholeRange.Min.X, Layout.WholeRange.Max.Y + 2.0f * Scale, Font, Scale * 0.9f);
}
