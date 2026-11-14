#include "Planner/LsnPlanner.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#include "Frame/LsnSiteFrame.h"
#include "Misc/Paths.h"

FVector2D FLsnPanorama::Point(double AzimuthDeg, double ElevationDeg) const
{
	const double Az = FMath::Fmod(FMath::Fmod(AzimuthDeg, 360.0) + 360.0, 360.0);
	const double T = FMath::Clamp((ElevationDeg - MinElevationDeg) / (MaxElevationDeg - MinElevationDeg), 0.0, 1.0);
	return FVector2D(Box.Min.X + (Box.Max.X - Box.Min.X) * Az / 360.0, Box.Max.Y - (Box.Max.Y - Box.Min.Y) * T);
}

FVector LsnPlanner::SecondSceneOffsetCm()
{
	// Both scenes stand at the same place. Each view hides the other scene, and each scene is
	// lit and shadowed on its own lighting channel, so they never meet on screen.
	// They used to stand 20 000 km apart. Measured on 2026-11-14: with the two scenes that far
	// apart in one world, the shadows of both broke into dark horizontal stripes in the
	// side-by-side view (not in the single view, not with shadows off, and the pattern changed
	// with the distance and its direction); with the scenes at the same place the side-by-side
	// view shows the same shadows as the single view.
	return FVector::ZeroVector;
}

FString LsnPlanner::PublishedPackageRoot()
{
	const FString Candidates[] = {
		FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../packages"))),
		FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("LsnPackages"))),
	};
	for (const FString& Candidate : Candidates)
	{
		if (FPaths::FileExists(FPaths::Combine(Candidate, TEXT("index.json"))))
		{
			return Candidate;
		}
	}
	return FString();
}

bool LsnPlanner::ListSites(const FString& PackageRoot, TArray<FLsnIndexEntry>& OutSites, FString& OutError)
{
	OutSites.Reset();
	TArray<FLsnIndexEntry> Entries;
	if (!LsnPackageIO::LoadIndex(PackageRoot, Entries, OutError))
	{
		return false;
	}
	for (const FLsnIndexEntry& Entry : Entries)
	{
		if (Entry.Kind == TEXT("site"))
		{
			OutSites.Add(Entry);
		}
	}
	if (OutSites.Num() == 0)
	{
		OutError = FString::Printf(TEXT("%s lists no site package"), *PackageRoot);
		return false;
	}
	return true;
}

bool LsnPlanner::LinkedPosition(const FLsnSitePackage& A, double PositionA, const FLsnSitePackage& B, double& OutPositionB)
{
	if (!A.bHasTimeline || !B.bHasTimeline || !(B.Time.StepS > 0.0) || B.Time.Count < 1)
	{
		return false;
	}
	const double Position = (A.EtOfPosition(PositionA) - B.Time.StartEtS) / B.Time.StepS;
	// A whole sample must stay a whole sample despite rounding in the division.
	const double Snapped = FMath::Abs(Position - FMath::RoundToDouble(Position)) < 1e-9 ? FMath::RoundToDouble(Position) : Position;
	if (Snapped < 0.0 || Snapped > B.Time.Count - 1)
	{
		return false;
	}
	OutPositionB = Snapped;
	return true;
}

const FLsnEvent* LsnPlanner::AdjacentEvent(const FLsnSitePackage& Package, const FString& Body, int32 HeightIndex, double EtS, int32 Direction)
{
	const FLsnEvent* Best = nullptr;
	for (const FLsnEvent& Event : Package.Events)
	{
		if (Event.HeightIndex != HeightIndex || (!Body.IsEmpty() && Event.Body != Body))
		{
			continue;
		}
		if (Direction > 0 ? (Event.EtS > EtS && (!Best || Event.EtS < Best->EtS)) : (Event.EtS < EtS && (!Best || Event.EtS > Best->EtS)))
		{
			Best = &Event;
		}
	}
	return Best;
}

void LsnPlanner::BuildMetricLines(const FLsnSitePackage& Package, int32 HeightIndex, TArray<FString>& OutLines)
{
	OutLines.Reset();
	auto Value = [&](const TCHAR* Id, double& Out)
	{
		const FLsnMetric* Metric = Package.FindMetric(Id, HeightIndex);
		if (!Metric || !Metric->bHasValue)
		{
			return false;
		}
		Out = Metric->Value;
		return true;
	};
	double V = 0.0, W = 0.0;
	if (Value(TEXT("sun_visible_fraction_of_time"), V))
	{
		OutLines.Add(FString::Printf(TEXT("Sun visible %.1f %% of the window"), 100.0 * V));
	}
	if (Value(TEXT("sun_longest_outage_s"), V))
	{
		OutLines.Add(FString::Printf(TEXT("longest time without Sun %.1f h"), V / 3600.0));
	}
	if (Value(TEXT("earth_visible_fraction_of_time"), V))
	{
		OutLines.Add(FString::Printf(TEXT("Earth visible %.1f %% of the window"), 100.0 * V));
	}
	if (Value(TEXT("earth_longest_outage_s"), V))
	{
		OutLines.Add(FString::Printf(TEXT("longest time without Earth %.1f h"), V / 3600.0));
	}
	if (Value(TEXT("sun_lost_to_terrain_s"), V) && Value(TEXT("sun_gained_from_terrain_s"), W))
	{
		OutLines.Add(FString::Printf(TEXT("Terrain here costs %.0f h of Sun and gives %.0f h that a smooth sphere would not have"), V / 3600.0, W / 3600.0));
	}
}

void LsnPlanner::PanoramaRange(const FLsnSitePackage& Package, int32 HeightIndex, double& OutMinDeg, double& OutMaxDeg)
{
	double Min = 0.0, Max = 0.0;
	for (int32 A = 0; A < Package.AzimuthCount; ++A)
	{
		const double El = Package.HorizonElevationAt(HeightIndex, A);
		if (!FMath::IsNaN(El))
		{
			Min = FMath::Min(Min, El);
			Max = FMath::Max(Max, El);
		}
	}
	for (const TPair<FString, FLsnBodySeries>& Pair : Package.Series)
	{
		for (const float El : Pair.Value.ElevationDeg)
		{
			if (!FMath::IsNaN(El))
			{
				Min = FMath::Min(Min, static_cast<double>(El));
				Max = FMath::Max(Max, static_cast<double>(El));
			}
		}
	}
	OutMinDeg = FMath::FloorToDouble(Min - 0.5);
	OutMaxDeg = FMath::CeilToDouble(Max + 0.5);
}

bool LsnPlanner::WindowHoldsAt(const FLsnWindow& Window, double EtS)
{
	const int32 Num = Window.StartsEtS.Num();
	for (int32 I = 0; I < Num; ++I)
	{
		if (EtS < Window.StartsEtS[I])
		{
			return false;
		}
		// A last interval cut off by the end of the computed range still holds at its very end.
		if (EtS < Window.EndsEtS[I] || (I == Num - 1 && Window.bClippedEnd && EtS <= Window.EndsEtS[I]))
		{
			return true;
		}
	}
	return false;
}

FLsnLandingCheck LsnPlanner::LandingAt(const FLsnOpportunity& O, double EtS)
{
	FLsnLandingCheck Out;
	if (EtS > O.LatestLandingEtS)
	{
		return Out;
	}
	Out.bJudgeable = true;
	const int32 Num = O.StartsEtS.Num();
	for (int32 I = 0; I < Num; ++I)
	{
		if (EtS < O.StartsEtS[I])
		{
			Out.bHasNextWindow = true;
			Out.WaitS = O.StartsEtS[I] - EtS;
			Out.NextWindowStartUtc = O.StartsUtc.IsValidIndex(I) ? O.StartsUtc[I] : FString();
			Out.NextWindowLengthS = O.EndsEtS[I] - O.StartsEtS[I];
			return Out;
		}
		if (EtS <= O.EndsEtS[I])
		{
			Out.bFeasible = true;
			Out.SlipS = O.EndsEtS[I] - EtS;
			Out.EarlyS = EtS - O.StartsEtS[I];
			Out.bSlipIsLowerBound = (I == Num - 1) && O.bClippedEnd;
			if (I + 1 < Num)
			{
				Out.WaitAfterWindowS = O.StartsEtS[I + 1] - O.EndsEtS[I];
			}
			return Out;
		}
	}
	return Out;
}

const FLsnEvent* LsnPlanner::EventEndingCountdown(const FLsnSitePackage& Package, const FString& Body, int32 HeightIndex, double EtS, const FLsnCountdown& Countdown)
{
	if (!Countdown.bAvailable || Countdown.bLowerBound)
	{
		return nullptr;
	}
	const double Target = EtS + Countdown.SecondsToChange;
	return Package.Events.FindByPredicate([&](const FLsnEvent& Event)
	{
		return Event.HeightIndex == HeightIndex && Event.Body == Body && FMath::Abs(Event.EtS - Target) < 1.0;
	});
}

FVector2D LsnPlanner::EllipsePointEastNorthM(const FLsnSiteFrame& Frame, const FLsnEllipsePoint& Point)
{
	const FVector Body = FLsnSiteFrame::LatLonToBodyDir(Point.LatDeg, Point.LonDeg) * (Frame.SphereRadiusM + Point.SurfaceHeightM);
	const FVector Unreal = Frame.BodyPointMToUnreal(Body);
	// Unreal +X is north, +Y is east, centimetres.
	return FVector2D(Unreal.Y / FLsnSiteFrame::CmPerM, Unreal.X / FLsnSiteFrame::CmPerM);
}

void LsnPlanner::BuildHeightTradeLines(const FLsnSitePackage& Package, TArray<FString>& OutLines)
{
	OutLines.Reset();
	const FLsnHeightTrade& Trade = Package.HeightTrade;
	const FLsnHeightTradeQuantity* Sun = Trade.bPresent ? Trade.Find(TEXT("sun_visible_s")) : nullptr;
	const FLsnHeightTradeQuantity* Outage = Trade.bPresent ? Trade.Find(TEXT("sun_longest_outage_s")) : nullptr;
	if (!Sun || !Outage)
	{
		return;
	}
	OutLines.Add(TEXT("mast-height trade: only the listed heights, nothing between them"));
	for (int32 H = 0; H < Trade.HeightsM.Num(); ++H)
	{
		auto Change = [H](const FLsnHeightTradeQuantity& Q) { return H == 0 ? FString() : FString::Printf(TEXT(" (%+.1f)"), Q.ChangeS[H] / 3600.0); };
		const FString SunChange = Change(*Sun).RightPad(8);
		OutLines.Add(FString::Printf(TEXT("%4.0f m   Sun %.1f h%s  longest outage %.1f h%s"), Trade.HeightsM[H], Sun->Values[H] / 3600.0, *SunChange, Outage->Values[H] / 3600.0, *Change(*Outage)));
	}
}

void LsnPlanner::BuildPairLines(const FLsnSitePair& Pair, TArray<FString>& OutLines)
{
	OutLines.Reset();
	OutLines.Add(Pair.DistanceM < 1000.0 ? FString::Printf(TEXT("%.0f m apart"), Pair.DistanceM) : FString::Printf(TEXT("%.1f km apart"), Pair.DistanceM / 1000.0));
	for (const FLsnPairWindow& W : Pair.Windows)
	{
		const TCHAR* Name = W.Window == TEXT("sun_visible") ? TEXT("Sun") : W.Window == TEXT("earth_visible") ? TEXT("Earth") : W.Window == TEXT("sun_and_earth_visible") ? TEXT("Sun and Earth together") : nullptr;
		if (!Name)
		{
			continue;
		}
		const FString Covered = W.bHasCoveredShare ? FString::Printf(TEXT(", %.0f %% of its outage"), 100.0 * W.CoveredShareOfBetterOutage) : FString();
		OutLines.Add(FString::Printf(TEXT("%s at one site at least %.1f %% of the window (+%.1f h over the better site%s); longest joint outage %.1f h"),
			Name, 100.0 * W.EitherFraction, W.GainOverBetterS / 3600.0, *Covered, W.LongestNeitherS / 3600.0));
	}
}

bool LsnPlanner::PositionOfUtc(const FLsnSitePackage& Package, const FString& Utc, double& OutPosition)
{
	FDateTime Start, When;
	if (!Package.bHasTimeline || Package.Time.LeapSecondsInRange != 0 || !(Package.Time.StepS > 0.0)
		|| !FDateTime::ParseIso8601(*Package.Time.StartUtc, Start) || !FDateTime::ParseIso8601(*Utc, When))
	{
		return false;
	}
	const double Position = (When - Start).GetTotalSeconds() / Package.Time.StepS;
	if (Position < 0.0 || Position > Package.Time.Count - 1)
	{
		return false;
	}
	OutPosition = Position;
	return true;
}
