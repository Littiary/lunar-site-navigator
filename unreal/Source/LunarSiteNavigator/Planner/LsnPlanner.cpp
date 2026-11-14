#include "Planner/LsnPlanner.h"

FVector2D FLsnPanorama::Point(double AzimuthDeg, double ElevationDeg) const
{
	const double Az = FMath::Fmod(FMath::Fmod(AzimuthDeg, 360.0) + 360.0, 360.0);
	const double T = FMath::Clamp((ElevationDeg - MinElevationDeg) / (MaxElevationDeg - MinElevationDeg), 0.0, 1.0);
	return FVector2D(Box.Min.X + (Box.Max.X - Box.Min.X) * Az / 360.0, Box.Max.Y - (Box.Max.Y - Box.Min.Y) * T);
}

FVector LsnPlanner::SecondSceneOffsetCm()
{
	// 20 000 km to the north: ten times the Moon's diameter. The shadow clipmaps of a view
	// reach a few hundred kilometres, the terrain 300 km, the Moon sphere 3474 km.
	return FVector(2.0e9, 0.0, 0.0);
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
		OutLines.Add(FString::Printf(TEXT("terrain against a smooth sphere: Sun -%.1f h, +%.1f h"), V / 3600.0, W / 3600.0));
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
