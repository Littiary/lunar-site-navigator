#include "Scene/LsnHud.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Scene/LsnObserverPawn.h"
#include "Scene/LsnSiteScene.h"
#include "Scene/LsnViewGameMode.h"

void ALsnHud::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas || !GEngine)
	{
		return;
	}
	UFont* Font = GEngine->GetMediumFont();
	const float Scale = FMath::Max(1.0f, Canvas->SizeY / 720.0f);
	float Y = 16.0f * Scale;
	const float X = 16.0f * Scale;
	auto Line = [&](const FString& Text, const FLinearColor& Color)
	{
		DrawText(Text, Color, X, Y, Font, Scale);
		Y += 18.0f * Scale;
	};
	const FLinearColor White(0.9f, 0.9f, 0.9f), Dim(0.6f, 0.6f, 0.6f), Alert(1.0f, 0.35f, 0.2f);

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
	const int32 T = Scene->GetTimeIndex();

	if (P.bSynthetic)
	{
		Line(TEXT("SYNTHETIC DATA - invented values for interface testing, not results"), Alert);
	}
	Line(FString::Printf(TEXT("%s   lat %.4f  lon %.4f (east +)   frame %s"), *P.SiteName, P.LatDeg, P.LonDeg, *P.Frame), White);
	Line(FString::Printf(TEXT("package %s   contract %s   status %s"), *P.PackageId, *P.ContractVersion, *P.Status), Dim);
	Line(FString::Printf(TEXT("observer height %.1f m above the surface (index %d of %d)"), P.ObserverHeightsM[H], H, P.NumHeights()), White);

	if (P.bHasTimeline)
	{
		const FString Utc = P.UtcLabelOfSample(T);
		const FString UtcText = Utc.IsEmpty() ? FString(TEXT("UTC label not available")) : (Utc + TEXT(" UTC"));
		Line(FString::Printf(TEXT("sample %d of %d   %s   ET %.1f s (TDB past J2000)"), T, P.Time.Count, *UtcText, P.Time.StartEtS + P.Time.StepS * T), White);
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
			Line(FString::Printf(TEXT("%s  az %.3f  el %.3f  margin over terrain %s  visible %s   [%s]"), *Body,
				S->AzimuthDeg[T], S->ElevationDeg[T], *Margin, *Visible, *P.ValidationStatusOf(P.DirectionMethod)), White);
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
	if (const ALsnObserverPawn* Pawn = Cast<ALsnObserverPawn>(GetOwningPawn()))
	{
		Line(FString::Printf(TEXT("looking az %.2f  el %.2f   field of view %.1f deg"), Pawn->GetAzimuthDeg(), Pawn->GetElevationDeg(), Pawn->GetFovDeg()), Dim);
	}
	Line(TEXT("Ground between the site and the horizon line is a placeholder surface, not elevation data."), Dim);
	if (Scene->GetSkippedHorizonSamples() > 0)
	{
		Line(FString::Printf(TEXT("%d horizon samples are unknown in the package and are not drawn."), Scene->GetSkippedHorizonSamples()), Alert);
	}
	for (const FString& Warning : P.Warnings)
	{
		Line(FString::Printf(TEXT("warning: %s"), *Warning), Alert);
	}
}
