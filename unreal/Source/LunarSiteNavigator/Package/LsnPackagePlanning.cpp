// Reading of the planning fields of the contract since 0.3 (SPEC 5.6 to 5.8, 6a).
// Every field here is optional, so nothing in this file refuses a package: a field
// that is absent or malformed is left empty and its panel stays hidden.

#include "Package/LsnPackage.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	using FJsonPtr = TSharedPtr<FJsonObject>;
	using FJsonArray = TArray<TSharedPtr<FJsonValue>>;

	FJsonPtr Child(const FJsonPtr& Parent, const TCHAR* Field)
	{
		const FJsonPtr* Found = nullptr;
		return (Parent.IsValid() && Parent->TryGetObjectField(Field, Found) && Found && Found->IsValid()) ? *Found : nullptr;
	}

	const FJsonArray* List(const FJsonPtr& Parent, const TCHAR* Field)
	{
		const FJsonArray* Found = nullptr;
		return (Parent.IsValid() && Parent->TryGetArrayField(Field, Found)) ? Found : nullptr;
	}

	FJsonPtr AsObject(const TSharedPtr<FJsonValue>& Value)
	{
		const FJsonPtr* Found = nullptr;
		return (Value.IsValid() && Value->TryGetObject(Found) && Found) ? *Found : nullptr;
	}

	/** A number, or false if the field is absent or null. */
	bool Number(const FJsonPtr& Parent, const TCHAR* Field, double& Out)
	{
		return Parent.IsValid() && Parent->HasTypedField<EJson::Number>(Field) && Parent->TryGetNumberField(Field, Out);
	}

	double NumberOr(const FJsonPtr& Parent, const TCHAR* Field, double Default)
	{
		double Value = Default;
		Number(Parent, Field, Value);
		return Value;
	}

	FString Text(const FJsonPtr& Parent, const TCHAR* Field)
	{
		FString Value;
		if (Parent.IsValid())
		{
			Parent->TryGetStringField(Field, Value);
		}
		return Value;
	}

	bool Flag(const FJsonPtr& Parent, const TCHAR* Field)
	{
		bool bValue = false;
		if (Parent.IsValid())
		{
			Parent->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	void Numbers(const FJsonArray* Values, TArray<double>& Out)
	{
		for (int32 I = 0; Values && I < Values->Num(); ++I)
		{
			Out.Add((*Values)[I].IsValid() && (*Values)[I]->Type == EJson::Number ? (*Values)[I]->AsNumber() : std::numeric_limits<double>::quiet_NaN());
		}
	}

	/** Sorted pairs [[start, end], ...] with their UTC strings. */
	void Intervals(const FJsonPtr& Parent, const TCHAR* EtField, const TCHAR* UtcField, TArray<double>& Starts, TArray<double>& Ends, TArray<FString>& StartsUtc, TArray<FString>& EndsUtc)
	{
		const FJsonArray* Et = List(Parent, EtField);
		const FJsonArray* Utc = List(Parent, UtcField);
		for (int32 I = 0; Et && I < Et->Num(); ++I)
		{
			const FJsonArray& Pair = (*Et)[I]->AsArray();
			if (Pair.Num() != 2)
			{
				continue;
			}
			Starts.Add(Pair[0]->AsNumber());
			Ends.Add(Pair[1]->AsNumber());
			const bool bHasUtc = Utc && Utc->IsValidIndex(I) && (*Utc)[I]->AsArray().Num() == 2;
			StartsUtc.Add(bHasUtc ? (*Utc)[I]->AsArray()[0]->AsString() : FString());
			EndsUtc.Add(bHasUtc ? (*Utc)[I]->AsArray()[1]->AsString() : FString());
		}
	}
}

const FLsnCalendarQuantity* FLsnCalendar::Find(const FString& Id) const
{
	return Quantities.FindByPredicate([&Id](const FLsnCalendarQuantity& Q) { return Q.Id == Id; });
}

double FLsnCalendar::Value(const FLsnCalendarQuantity& Quantity, int32 HeightIndex, int32 PeriodIndex) const
{
	const int32 Flat = HeightIndex * Periods.Num() + PeriodIndex;
	return (HeightIndex >= 0 && Periods.IsValidIndex(PeriodIndex) && Quantity.Values.IsValidIndex(Flat)) ? Quantity.Values[Flat] : std::numeric_limits<double>::quiet_NaN();
}

const FLsnHeightTradeQuantity* FLsnHeightTrade::Find(const FString& Id) const
{
	return Quantities.FindByPredicate([&Id](const FLsnHeightTradeQuantity& Q) { return Q.Id == Id; });
}

const FLsnSitePair* FLsnSitePairs::FindPair(const FString& SiteIdOne, const FString& SiteIdTwo) const
{
	return Pairs.FindByPredicate([&](const FLsnSitePair& Pair)
	{
		return (Pair.SiteA == SiteIdOne && Pair.SiteB == SiteIdTwo) || (Pair.SiteA == SiteIdTwo && Pair.SiteB == SiteIdOne);
	});
}

const FLsnOpportunity* FLsnSitePackage::FindOpportunity(const FString& RequirementId, int32 InHeightIndex) const
{
	return Opportunities.FindByPredicate([&](const FLsnOpportunity& O) { return O.HeightIndex == InHeightIndex && O.RequirementId == RequirementId; });
}

void LsnPackageIO::ReadPlanningFields(const TSharedPtr<FJsonObject>& Manifest, FLsnSitePackage& P)
{
	const FJsonPtr Timeline = Child(Manifest, TEXT("timeline"));
	if (!Timeline.IsValid())
	{
		return;
	}

	// Requirements and the planned landing are part of the request (SPEC 5.1, 5.6).
	const FJsonPtr RequestTimeline = Child(Child(Manifest, TEXT("request")), TEXT("timeline"));
	for (const FJsonArray* Values = List(RequestTimeline, TEXT("requirements")); Values != nullptr;)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnRequirement R;
			R.Id = Text(Object, TEXT("id"));
			R.Label = Text(Object, TEXT("label"));
			R.MissionDurationS = NumberOr(Object, TEXT("mission_duration_s"), 0.0);
			if (!R.Id.IsEmpty())
			{
				P.Requirements.Add(MoveTemp(R));
			}
		}
		break;
	}
	P.PlannedLandingUtc = Text(RequestTimeline, TEXT("landing_utc"));

	// Calendar.
	const FJsonPtr Calendar = Child(Timeline, TEXT("calendar"));
	if (const FJsonArray* Periods = List(Calendar, TEXT("periods")))
	{
		P.Calendar.Definition = Text(Calendar, TEXT("definition"));
		P.Calendar.Method = Text(Calendar, TEXT("method"));
		for (const TSharedPtr<FJsonValue>& Value : *Periods)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnCalendarPeriod Period;
			Period.Index = static_cast<int32>(NumberOr(Object, TEXT("index"), P.Calendar.Periods.Num()));
			Period.StartEtS = NumberOr(Object, TEXT("start_et_s"), 0.0);
			Period.EndEtS = NumberOr(Object, TEXT("end_et_s"), 0.0);
			Period.StartUtc = Text(Object, TEXT("start_utc"));
			Period.EndUtc = Text(Object, TEXT("end_utc"));
			Period.bComplete = Flag(Object, TEXT("complete"));
			P.Calendar.Periods.Add(MoveTemp(Period));
		}
		const int32 NumPeriods = P.Calendar.Periods.Num();
		for (const FJsonArray* Quantities = List(Calendar, TEXT("quantities")); Quantities != nullptr;)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Quantities)
			{
				const FJsonPtr Object = AsObject(Value);
				FLsnCalendarQuantity Q;
				Q.Id = Text(Object, TEXT("id"));
				Q.Label = Text(Object, TEXT("label"));
				Q.Unit = Text(Object, TEXT("unit"));
				Q.Window = Text(Object, TEXT("window"));
				Q.Method = Text(Object, TEXT("method"));
				const FJsonArray* Rows = List(Object, TEXT("values"));
				bool bShapeOk = Rows != nullptr && Rows->Num() == P.NumHeights();
				for (int32 H = 0; bShapeOk && H < Rows->Num(); ++H)
				{
					const FJsonArray& Row = (*Rows)[H]->AsArray();
					bShapeOk = Row.Num() == NumPeriods;
					Numbers(&Row, Q.Values);
				}
				// A quantity whose table does not have one value per height and period is not shown.
				if (bShapeOk && !Q.Id.IsEmpty())
				{
					P.Calendar.Quantities.Add(MoveTemp(Q));
				}
			}
			break;
		}
		P.Calendar.bPresent = NumPeriods > 0 && P.Calendar.Quantities.Num() > 0;
	}

	// Opportunities.
	if (const FJsonArray* Opportunities = List(Timeline, TEXT("opportunities")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Opportunities)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnOpportunity O;
			O.RequirementId = Text(Object, TEXT("requirement_id"));
			O.HeightIndex = static_cast<int32>(NumberOr(Object, TEXT("height_index"), -1.0));
			Intervals(Object, TEXT("landing_windows_et_s"), TEXT("landing_windows_utc"), O.StartsEtS, O.EndsEtS, O.StartsUtc, O.EndsUtc);
			double Latest = 0.0;
			if (O.RequirementId.IsEmpty() || O.HeightIndex < 0 || !Number(Object, TEXT("latest_landing_et_s"), Latest))
			{
				continue;
			}
			O.LatestLandingEtS = Latest;
			O.LatestLandingUtc = Text(Object, TEXT("latest_landing_utc"));
			O.bClippedStart = Flag(Object, TEXT("clipped_start"));
			O.bClippedEnd = Flag(Object, TEXT("clipped_end"));
			O.FeasibleFraction = NumberOr(Object, TEXT("feasible_fraction"), 0.0);
			O.WindowCount = static_cast<int32>(NumberOr(Object, TEXT("window_count"), O.StartsEtS.Num()));
			O.LongestWindowS = NumberOr(Object, TEXT("longest_window_s"), 0.0);
			Numbers(List(Object, TEXT("feasible_s_per_period")), O.FeasibleSPerPeriod);
			O.Method = Text(Object, TEXT("method"));
			const FJsonPtr Planned = Child(Object, TEXT("planned_landing"));
			if (Planned.IsValid() && Number(Planned, TEXT("et_s"), O.Planned.EtS))
			{
				O.Planned.bPresent = true;
				O.Planned.Utc = Text(Planned, TEXT("utc"));
				O.Planned.bFeasible = Flag(Planned, TEXT("feasible"));
				O.Planned.SlipToleranceS = NumberOr(Planned, TEXT("slip_tolerance_s"), 0.0);
				O.Planned.EarlyToleranceS = NumberOr(Planned, TEXT("early_tolerance_s"), 0.0);
				O.Planned.bSlipIsLowerBound = Flag(Planned, TEXT("slip_tolerance_is_lower_bound"));
				O.Planned.bHasWait = Number(Planned, TEXT("wait_s"), O.Planned.WaitS);
				O.Planned.NextWindowStartUtc = Text(Planned, TEXT("next_window_start_utc"));
			}
			P.Opportunities.Add(MoveTemp(O));
		}
	}

	// Uncertainty: stated assumptions.
	const FJsonPtr Uncertainty = Child(Timeline, TEXT("uncertainty"));
	const FJsonPtr HorizonError = Child(Uncertainty, TEXT("horizon_error"));
	if (HorizonError.IsValid() && Number(HorizonError, TEXT("error_deg"), P.Uncertainty.HorizonErrorDeg))
	{
		P.Uncertainty.bHasHorizonError = true;
		P.Uncertainty.HorizonAssumption = Text(HorizonError, TEXT("assumption"));
		P.Uncertainty.HorizonMethod = Text(HorizonError, TEXT("method"));
	}
	const FJsonPtr Ellipse = Child(Uncertainty, TEXT("landing_ellipse"));
	if (const FJsonArray* Points = List(Ellipse, TEXT("points")))
	{
		P.Uncertainty.SemiMajorM = NumberOr(Ellipse, TEXT("semi_major_m"), 0.0);
		P.Uncertainty.SemiMinorM = NumberOr(Ellipse, TEXT("semi_minor_m"), 0.0);
		P.Uncertainty.AzimuthDeg = NumberOr(Ellipse, TEXT("azimuth_deg"), 0.0);
		P.Uncertainty.EllipseHeightIndex = static_cast<int32>(NumberOr(Ellipse, TEXT("height_index"), P.DefaultHeightIndex));
		P.Uncertainty.EllipseAssumption = Text(Ellipse, TEXT("assumption"));
		P.Uncertainty.EllipseMethod = Text(Ellipse, TEXT("method"));
		for (const TSharedPtr<FJsonValue>& Value : *Points)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnEllipsePoint Point;
			if (!Number(Object, TEXT("lat_deg"), Point.LatDeg) || !Number(Object, TEXT("lon_deg"), Point.LonDeg))
			{
				continue;
			}
			Point.SurfaceHeightM = NumberOr(Object, TEXT("surface_height_m"), 0.0);
			if (const FJsonPtr Visible = Child(Object, TEXT("visible_s")))
			{
				for (const auto& Pair : Visible->Values)
				{
					double Seconds = 0.0;
					if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Number && Pair.Value->TryGetNumber(Seconds))
					{
						Point.VisibleS.Add(FString(Pair.Key), Seconds);
					}
				}
			}
			P.Uncertainty.Points.Add(MoveTemp(Point));
		}
		if (const FJsonPtr Stats = Child(Ellipse, TEXT("visible_s")))
		{
			for (const auto& Pair : Stats->Values)
			{
				const FJsonPtr Object = AsObject(Pair.Value);
				FLsnEllipseStats S;
				if (Number(Object, TEXT("centre_s"), S.CentreS) && Number(Object, TEXT("min_s"), S.MinS) && Number(Object, TEXT("median_s"), S.MedianS) && Number(Object, TEXT("max_s"), S.MaxS))
				{
					P.Uncertainty.EllipseStats.Add(FString(Pair.Key), S);
				}
			}
		}
		P.Uncertainty.bHasEllipse = P.Uncertainty.Points.Num() > 0;
	}

	// The band of every event (same order as the events were read in).
	if (const FJsonArray* Events = List(Timeline, TEXT("events")))
	{
		int32 Index = 0;
		for (const TSharedPtr<FJsonValue>& Value : *Events)
		{
			const FJsonPtr Object = AsObject(Value);
			if (!Object.IsValid())
			{
				continue;
			}
			if (P.Events.IsValidIndex(Index) && FMath::Abs(P.Events[Index].EtS - NumberOr(Object, TEXT("et_s"), 0.0)) < 1e-6)
			{
				FLsnEvent& Event = P.Events[Index];
				Event.bHasBand = Number(Object, TEXT("earliest_et_s"), Event.EarliestEtS) && Number(Object, TEXT("latest_et_s"), Event.LatestEtS);
				Event.EarliestUtc = Text(Object, TEXT("earliest_utc"));
				Event.LatestUtc = Text(Object, TEXT("latest_utc"));
			}
			++Index;
		}
	}

	// Mast-height trade.
	const FJsonPtr Trade = Child(Timeline, TEXT("height_trade"));
	if (const FJsonArray* Quantities = List(Trade, TEXT("quantities")))
	{
		Numbers(List(Trade, TEXT("observer_heights_m")), P.HeightTrade.HeightsM);
		for (const TSharedPtr<FJsonValue>& Value : *Quantities)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnHeightTradeQuantity Q;
			Q.Id = Text(Object, TEXT("id"));
			Q.Label = Text(Object, TEXT("label"));
			Q.Window = Text(Object, TEXT("window"));
			Q.Method = Text(Object, TEXT("method"));
			Numbers(List(Object, TEXT("values")), Q.Values);
			Numbers(List(Object, TEXT("change_s")), Q.ChangeS);
			if (!Q.Id.IsEmpty() && Q.Values.Num() == P.HeightTrade.HeightsM.Num() && Q.ChangeS.Num() == Q.Values.Num())
			{
				P.HeightTrade.Quantities.Add(MoveTemp(Q));
			}
		}
		P.HeightTrade.bPresent = P.HeightTrade.HeightsM.Num() > 0 && P.HeightTrade.Quantities.Num() > 0;
	}
}

bool LsnPackageIO::LoadSitePairs(const FString& PackageDirectory, FLsnSitePairs& OutPairs, FString& OutError)
{
	OutPairs = FLsnSitePairs();
	const FString Path = FPaths::Combine(PackageDirectory, TEXT("manifest.json"));
	FString Json;
	FJsonPtr Root;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		OutError = FString::Printf(TEXT("cannot read %s"), *Path);
		return false;
	}
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = FString::Printf(TEXT("%s is not valid JSON"), *Path);
		return false;
	}
	const FJsonPtr Contract = Child(Root, TEXT("contract"));
	OutPairs.ContractVersion = Text(Contract, TEXT("version"));
	FString Major, Minor;
	if (Text(Contract, TEXT("name")) != TEXT("lsn-package") || !OutPairs.ContractVersion.Split(TEXT("."), &Major, &Minor) || FCString::Atoi(*Major) != LsnContractMajor || !Major.IsNumeric())
	{
		OutError = FString::Printf(TEXT("%s: this reader understands major version %d of lsn-package only"), *Path, LsnContractMajor);
		return false;
	}
	if (Text(Root, TEXT("kind")) != TEXT("site_pairs") || Text(Root, TEXT("status")) == TEXT("error"))
	{
		OutError = FString::Printf(TEXT("%s is not a usable package of kind site_pairs"), *Path);
		return false;
	}
	OutPairs.PackageId = Text(Root, TEXT("package_id"));
	OutPairs.bSynthetic = Flag(Root, TEXT("synthetic"));
	const FJsonPtr Time = Child(Root, TEXT("time"));
	OutPairs.RangeLengthS = NumberOr(Time, TEXT("step_s"), 0.0) * (NumberOr(Time, TEXT("count"), 1.0) - 1.0);
	if (const FJsonArray* Sites = List(Root, TEXT("sites")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Sites)
		{
			const FJsonPtr Object = AsObject(Value);
			OutPairs.SitePackageIds.Add(Text(Object, TEXT("site_id")), Text(Object, TEXT("package_id")));
		}
	}
	if (const FJsonPtr Methods = Child(Root, TEXT("methods")))
	{
		for (const auto& Pair : Methods->Values)
		{
			OutPairs.MethodStatus.Add(FString(Pair.Key), Text(Child(AsObject(Pair.Value), TEXT("validation")), TEXT("status")));
		}
	}
	if (const FJsonArray* Pairs = List(Root, TEXT("pairs")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Pairs)
		{
			const FJsonPtr Object = AsObject(Value);
			FLsnSitePair Pair;
			Pair.SiteA = Text(Object, TEXT("site_a"));
			Pair.SiteB = Text(Object, TEXT("site_b"));
			Pair.DistanceM = NumberOr(Object, TEXT("distance_m"), 0.0);
			for (const FJsonArray* Windows = List(Object, TEXT("windows")); Windows != nullptr;)
			{
				for (const TSharedPtr<FJsonValue>& WindowValue : *Windows)
				{
					const FJsonPtr W = AsObject(WindowValue);
					FLsnPairWindow Window;
					Window.Window = Text(W, TEXT("window"));
					Window.AS = NumberOr(W, TEXT("a_s"), 0.0);
					Window.BS = NumberOr(W, TEXT("b_s"), 0.0);
					Window.EitherS = NumberOr(W, TEXT("either_s"), 0.0);
					Window.BothS = NumberOr(W, TEXT("both_s"), 0.0);
					Window.NeitherS = NumberOr(W, TEXT("neither_s"), 0.0);
					Window.EitherFraction = NumberOr(W, TEXT("either_fraction"), 0.0);
					Window.LongestNeitherS = NumberOr(W, TEXT("longest_neither_s"), 0.0);
					Window.GainOverBetterS = NumberOr(W, TEXT("gain_over_better_s"), 0.0);
					Window.bHasCoveredShare = Number(W, TEXT("covered_share_of_better_outage"), Window.CoveredShareOfBetterOutage);
					Window.Method = Text(W, TEXT("method"));
					if (!Window.Window.IsEmpty())
					{
						Pair.Windows.Add(MoveTemp(Window));
					}
				}
				break;
			}
			if (!Pair.SiteA.IsEmpty() && !Pair.SiteB.IsEmpty())
			{
				OutPairs.Pairs.Add(MoveTemp(Pair));
			}
		}
	}
	return true;
}

void LsnPackageIO::ReadTerrainSource(const TSharedPtr<FJsonObject>& Manifest, FLsnTerrainSource& OutSource)
{
	OutSource = FLsnTerrainSource();
	const FJsonPtr Source = Child(Child(Manifest, TEXT("horizon")), TEXT("terrain_source"));
	if (!Source.IsValid())
	{
		return;
	}
	OutSource.ResolutionClass = Text(Source, TEXT("resolution_class"));
	const FJsonPtr AtSite = Child(Source, TEXT("at_site"));
	OutSource.PixelM = NumberOr(AtSite, TEXT("pixel_m"), 0.0);
	OutSource.ProductId = Text(AtSite, TEXT("product_id"));
	OutSource.bPresent = !OutSource.ResolutionClass.IsEmpty();
}

bool LsnPackageIO::ReadTerrainSourceOfDirectory(const FString& PackageDirectory, FLsnTerrainSource& OutSource)
{
	OutSource = FLsnTerrainSource();
	FString JsonText;
	TSharedPtr<FJsonObject> Manifest;
	if (!FFileHelper::LoadFileToString(JsonText, *FPaths::Combine(PackageDirectory, TEXT("manifest.json"))))
	{
		return false;
	}
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, Manifest) || !Manifest.IsValid())
	{
		return false;
	}
	ReadTerrainSource(Manifest, OutSource);
	return OutSource.bPresent;
}
