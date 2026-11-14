#include "Package/LsnPackage.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

static_assert(PLATFORM_LITTLE_ENDIAN, "Package arrays are little-endian and are read without byte swapping.");

namespace
{
	using FJsonObjectPtr = TSharedPtr<FJsonObject>;

	/** Collects the first error; later steps become no-ops once something failed. */
	struct FLsnReadContext
	{
		FString Directory;
		FString Error;

		bool Failed() const { return !Error.IsEmpty(); }
		void Fail(const FString& Message)
		{
			if (Error.IsEmpty())
			{
				Error = Message;
			}
		}
	};

	bool LoadJsonFile(const FString& Path, FJsonObjectPtr& OutObject, FString& OutError)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			OutError = FString::Printf(TEXT("cannot read %s"), *Path);
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		if (!FJsonSerializer::Deserialize(Reader, OutObject) || !OutObject.IsValid())
		{
			OutError = FString::Printf(TEXT("%s is not valid JSON: %s"), *Path, *Reader->GetErrorMessage());
			return false;
		}
		return true;
	}

	FJsonObjectPtr GetObject(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TCHAR* Where)
	{
		const FJsonObjectPtr* Found = nullptr;
		if (Ctx.Failed() || !Parent.IsValid() || !Parent->TryGetObjectField(Field, Found) || !Found || !Found->IsValid())
		{
			Ctx.Fail(FString::Printf(TEXT("missing object '%s' in %s"), Field, Where));
			return nullptr;
		}
		return *Found;
	}

	FString GetString(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TCHAR* Where)
	{
		FString Value;
		if (Ctx.Failed() || !Parent.IsValid() || !Parent->TryGetStringField(Field, Value))
		{
			Ctx.Fail(FString::Printf(TEXT("missing string '%s' in %s"), Field, Where));
		}
		return Value;
	}

	double GetNumber(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TCHAR* Where)
	{
		double Value = 0.0;
		if (Ctx.Failed() || !Parent.IsValid() || !Parent->TryGetNumberField(Field, Value))
		{
			Ctx.Fail(FString::Printf(TEXT("missing number '%s' in %s"), Field, Where));
		}
		return Value;
	}

	/** A number that the contract allows to be null or absent: NaN in that case. */
	double GetNumberOrNaN(const FJsonObjectPtr& Parent, const TCHAR* Field)
	{
		double Value = 0.0;
		if (!Parent.IsValid() || !Parent->HasTypedField<EJson::Number>(Field) || !Parent->TryGetNumberField(Field, Value))
		{
			return std::numeric_limits<double>::quiet_NaN();
		}
		return Value;
	}

	/** A quantity is {"value", "unit", "method"}; the unit is checked against what the reader expects. */
	double GetQuantity(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TCHAR* ExpectedUnit, const TCHAR* Where)
	{
		const FJsonObjectPtr Quantity = GetObject(Ctx, Parent, Field, Where);
		if (!Quantity.IsValid())
		{
			return 0.0;
		}
		const FString Unit = GetString(Ctx, Quantity, TEXT("unit"), Field);
		if (!Ctx.Failed() && Unit != ExpectedUnit)
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' has unit '%s', expected '%s'"), Field, *Unit, ExpectedUnit));
		}
		return GetNumber(Ctx, Quantity, TEXT("value"), Field);
	}

	FVector GetVector3(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TCHAR* Where)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Ctx.Failed() || !Parent.IsValid() || !Parent->TryGetArrayField(Field, Values) || !Values || Values->Num() != 3)
		{
			Ctx.Fail(FString::Printf(TEXT("missing 3-vector '%s' in %s"), Field, Where));
			return FVector::ZeroVector;
		}
		return FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
	}

	template <typename T> const TCHAR* DTypeOf();
	template <> const TCHAR* DTypeOf<float>() { return TEXT("<f4"); }
	template <> const TCHAR* DTypeOf<double>() { return TEXT("<f8"); }
	template <> const TCHAR* DTypeOf<int32>() { return TEXT("<i4"); }

	inline bool IsUnknown(float Value) { return FMath::IsNaN(Value); }
	inline bool IsUnknown(double Value) { return FMath::IsNaN(Value); }
	inline bool IsUnknown(int32) { return false; }

	/**
	 * Reads the array an array reference points to (SPEC 3.1) and checks dtype,
	 * shape, unit, file size and the stated NaN count.
	 */
	template <typename T>
	void ReadArray(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, const TCHAR* Field, const TArray<int32>& ExpectedShape,
		const TCHAR* ExpectedUnit, TArray<T>& OutValues, FString* OutMethod = nullptr)
	{
		const FJsonObjectPtr Ref = GetObject(Ctx, Parent, Field, TEXT("array reference"));
		if (!Ref.IsValid())
		{
			return;
		}
		const FString File = GetString(Ctx, Ref, TEXT("file"), Field);
		const FString DType = GetString(Ctx, Ref, TEXT("dtype"), Field);
		const FString Unit = GetString(Ctx, Ref, TEXT("unit"), Field);
		const FString Method = GetString(Ctx, Ref, TEXT("method"), Field);
		const double NanCount = GetNumber(Ctx, Ref, TEXT("nan_count"), Field);
		const TArray<TSharedPtr<FJsonValue>>* ShapeValues = nullptr;
		if (!Ctx.Failed() && (!Ref->TryGetArrayField(TEXT("shape"), ShapeValues) || !ShapeValues))
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' has no shape"), Field));
		}
		if (Ctx.Failed())
		{
			return;
		}
		if (DType != DTypeOf<T>())
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' has dtype '%s', expected '%s'"), Field, *DType, DTypeOf<T>()));
			return;
		}
		if (Unit != ExpectedUnit)
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' has unit '%s', expected '%s'"), Field, *Unit, ExpectedUnit));
			return;
		}
		TArray<int32> Shape;
		int64 NumItems = 1;
		for (const TSharedPtr<FJsonValue>& Value : *ShapeValues)
		{
			Shape.Add(static_cast<int32>(Value->AsNumber()));
			NumItems *= Shape.Last();
		}
		if (Shape != ExpectedShape)
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' has an unexpected shape"), Field));
			return;
		}
		if (File.Contains(TEXT("/")) || File.Contains(TEXT("\\")) || File.Contains(TEXT("..")))
		{
			Ctx.Fail(FString::Printf(TEXT("'%s' refers to a file outside the package: %s"), Field, *File));
			return;
		}
		TArray<uint8> Bytes;
		const FString Path = FPaths::Combine(Ctx.Directory, File);
		if (!FFileHelper::LoadFileToArray(Bytes, *Path))
		{
			Ctx.Fail(FString::Printf(TEXT("cannot read array file %s"), *Path));
			return;
		}
		if (Bytes.Num() != NumItems * static_cast<int64>(sizeof(T)))
		{
			Ctx.Fail(FString::Printf(TEXT("%s has %d bytes, the manifest implies %lld"), *File, Bytes.Num(), NumItems * static_cast<int64>(sizeof(T))));
			return;
		}
		OutValues.SetNumUninitialized(static_cast<int32>(NumItems));
		FMemory::Memcpy(OutValues.GetData(), Bytes.GetData(), Bytes.Num());

		int64 FoundNans = 0;
		for (const T Value : OutValues)
		{
			if (IsUnknown(Value))
			{
				++FoundNans;
			}
		}
		if (FoundNans != static_cast<int64>(NanCount))
		{
			Ctx.Fail(FString::Printf(TEXT("%s holds %lld NaN values, the manifest states %lld"), *File, FoundNans, static_cast<int64>(NanCount)));
			return;
		}
		if (OutMethod)
		{
			*OutMethod = Method;
		}
	}

	/** Checks the common header (SPEC 3.3) and the contract version rule (SPEC 8). */
	void ReadHeader(FLsnReadContext& Ctx, const FJsonObjectPtr& Root, const TCHAR* ExpectedKind, FString& OutVersion, FString& OutPackageId,
		FString& OutStatus, bool& bOutSynthetic)
	{
		const FJsonObjectPtr Contract = GetObject(Ctx, Root, TEXT("contract"), TEXT("manifest"));
		const FString Name = GetString(Ctx, Contract, TEXT("name"), TEXT("contract"));
		OutVersion = GetString(Ctx, Contract, TEXT("version"), TEXT("contract"));
		const FString Kind = GetString(Ctx, Root, TEXT("kind"), TEXT("manifest"));
		if (Ctx.Failed())
		{
			return;
		}
		if (Name != TEXT("lsn-package"))
		{
			Ctx.Fail(FString::Printf(TEXT("not an lsn-package (contract name '%s')"), *Name));
			return;
		}
		FString MajorText, MinorText;
		if (!OutVersion.Split(TEXT("."), &MajorText, &MinorText) || !MajorText.IsNumeric())
		{
			Ctx.Fail(FString::Printf(TEXT("contract version '%s' is not major.minor"), *OutVersion));
			return;
		}
		if (FCString::Atoi(*MajorText) != LsnContractMajor)
		{
			Ctx.Fail(FString::Printf(TEXT("contract version %s has another major number than this reader (%d); the package is refused"), *OutVersion, LsnContractMajor));
			return;
		}
		if (Kind != ExpectedKind)
		{
			Ctx.Fail(FString::Printf(TEXT("package kind is '%s', expected '%s'"), *Kind, ExpectedKind));
			return;
		}
		OutPackageId = GetString(Ctx, Root, TEXT("package_id"), TEXT("manifest"));
		OutStatus = GetString(Ctx, Root, TEXT("status"), TEXT("manifest"));
		if (!Ctx.Failed() && !Root->TryGetBoolField(TEXT("synthetic"), bOutSynthetic))
		{
			Ctx.Fail(TEXT("missing boolean 'synthetic' in manifest"));
		}
		if (!Ctx.Failed() && OutStatus == TEXT("error"))
		{
			Ctx.Fail(TEXT("the package has status 'error'"));
		}
	}

	void ReadTimeGrid(FLsnReadContext& Ctx, const FJsonObjectPtr& Parent, FLsnTimeGrid& OutGrid)
	{
		const FJsonObjectPtr Time = GetObject(Ctx, Parent, TEXT("time"), TEXT("time grid"));
		const FString Scale = GetString(Ctx, Time, TEXT("scale"), TEXT("time"));
		const FString Epoch = GetString(Ctx, Time, TEXT("epoch"), TEXT("time"));
		OutGrid.StartEtS = GetNumber(Ctx, Time, TEXT("start_et_s"), TEXT("time"));
		OutGrid.StepS = GetNumber(Ctx, Time, TEXT("step_s"), TEXT("time"));
		OutGrid.Count = static_cast<int32>(GetNumber(Ctx, Time, TEXT("count"), TEXT("time")));
		OutGrid.StartUtc = GetString(Ctx, Time, TEXT("start_utc"), TEXT("time"));
		OutGrid.EndUtc = GetString(Ctx, Time, TEXT("end_utc"), TEXT("time"));
		OutGrid.LeapSecondsInRange = static_cast<int32>(GetNumber(Ctx, Time, TEXT("leap_seconds_in_range"), TEXT("time")));
		if (!Ctx.Failed() && (Scale != TEXT("TDB") || Epoch != TEXT("J2000")))
		{
			Ctx.Fail(FString::Printf(TEXT("time grid is %s past %s, expected TDB past J2000"), *Scale, *Epoch));
		}
		if (!Ctx.Failed() && (OutGrid.Count < 1 || OutGrid.StepS <= 0.0))
		{
			Ctx.Fail(TEXT("time grid has no samples or a non-positive step"));
		}
	}
}

double FLsnSitePackage::HorizonElevationInterpolated(int32 HeightIndex, double AzimuthDeg) const
{
	double Position = (AzimuthDeg - AzimuthStartDeg) / AzimuthStepDeg;
	Position = FMath::Fmod(Position, static_cast<double>(AzimuthCount));
	if (Position < 0.0)
	{
		Position += AzimuthCount;
	}
	const int32 Lower = FMath::Min(FMath::FloorToInt32(Position), AzimuthCount - 1);
	const int32 Upper = (Lower + 1) % AzimuthCount;
	const double Fraction = Position - Lower;
	return (1.0 - Fraction) * HorizonElevationAt(HeightIndex, Lower) + Fraction * HorizonElevationAt(HeightIndex, Upper);
}

double FLsnSitePackage::HorizonSearchStartM() const
{
	const FLsnMethodCard* Card = Methods.Find(HorizonElevationMethod);
	const double* Start = Card ? Card->NumericParameters.Find(TEXT("first_point_m")) : nullptr;
	return Start ? *Start : 0.0;
}

FString FLsnSitePackage::ValidationStatusOf(const FString& MethodId) const
{
	const FLsnMethodCard* Card = Methods.Find(MethodId);
	return Card ? Card->ValidationStatus : FString(TEXT("unknown"));
}

FString FLsnSitePackage::UtcLabelOfSample(int32 SampleIndex) const
{
	if (!bHasTimeline || Time.LeapSecondsInRange != 0 || SampleIndex < 0 || SampleIndex >= Time.Count)
	{
		return FString();
	}
	FDateTime Start;
	if (!FDateTime::ParseIso8601(*Time.StartUtc, Start))
	{
		return FString();
	}
	const FDateTime Sample = Start + FTimespan::FromSeconds(Time.StepS * SampleIndex);
	return FString::Printf(TEXT("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ"), Sample.GetYear(), Sample.GetMonth(), Sample.GetDay(),
		Sample.GetHour(), Sample.GetMinute(), Sample.GetSecond(), Sample.GetMillisecond());
}

void FLsnSitePackage::ObstacleRun(const FLsnObstacle& Obstacle, TArray<int32>& OutAzimuthIndices) const
{
	OutAzimuthIndices.Reset();
	for (int32 K = 0; AzimuthCount > 0 && K < Obstacle.AzimuthCount && K < AzimuthCount; ++K)
	{
		OutAzimuthIndices.Add((Obstacle.AzimuthStartIndex + K) % AzimuthCount);
	}
}

bool FLsnSitePackage::BlockingAt(const FString& Body, int32 InHeightIndex, int32 TimeIndex, FLsnBlocking& Out) const
{
	Out = FLsnBlocking();
	const FLsnBodySeries* S = bHasTimeline ? FindSeries(Body) : nullptr;
	if (!S || !ObserverHeightsM.IsValidIndex(InHeightIndex) || TimeIndex < 0 || TimeIndex >= Time.Count
		|| S->BlockerAzimuthIndex.Num() != NumHeights() * Time.Count || !HasObstacles())
	{
		return false;
	}
	const int32 Flat = InHeightIndex * Time.Count + TimeIndex;
	// SPEC 5.5, steps 1 to 4.
	Out.VisibleFraction = S->VisibleFraction.IsValidIndex(Flat) ? S->VisibleFraction[Flat] : 0.0;
	const int32 J = S->BlockerAzimuthIndex[Flat];
	if (J < 0 || J >= AzimuthCount)
	{
		return false;
	}
	Out.AzimuthIndex = J;
	Out.AzimuthDeg = AzimuthDegAt(J);
	Out.HorizonElevationDeg = HorizonElevationAt(InHeightIndex, J);
	Out.DistanceM = HorizonDistanceAt(InHeightIndex, J);
	Out.ObstacleId = ObstacleId[InHeightIndex * AzimuthCount + J];
	Out.Obstacle = Obstacles.IsValidIndex(Out.ObstacleId) ? &Obstacles[Out.ObstacleId] : nullptr;
	Out.Blocker = Blockers.FindByPredicate([&](const FLsnBlocker& B) { return B.ObstacleId == Out.ObstacleId && B.HeightIndex == InHeightIndex && B.Body == Body; });
	if (Body == TEXT("EARTH"))
	{
		Out.bHiddenOrPartly = S->MarginDeg.IsValidIndex(Flat) && S->MarginDeg[Flat] <= 0.0f;
	}
	else
	{
		Out.bHiddenOrPartly = Out.VisibleFraction < 1.0;
	}
	return true;
}

const FLsnWindow* FLsnSitePackage::FindWindow(const FString& Id, int32 InHeightIndex) const
{
	return Windows.FindByPredicate([&](const FLsnWindow& W) { return W.HeightIndex == InHeightIndex && W.Id == Id; });
}

const FLsnMetric* FLsnSitePackage::FindMetric(const FString& Id, int32 InHeightIndex) const
{
	return Metrics.FindByPredicate([&](const FLsnMetric& M) { return M.HeightIndex == InHeightIndex && M.Id == Id; });
}

FLsnCountdown FLsnSitePackage::CountdownAt(const FString& Body, int32 InHeightIndex, double EtS) const
{
	FLsnCountdown Out;
	const FLsnWindow* Window = bHasTimeline ? FindWindow(Body.ToLower() + TEXT("_visible"), InHeightIndex) : nullptr;
	if (!Window)
	{
		return Out;
	}
	Out.bAvailable = true;
	Out.WindowId = Window->Id;
	Out.Method = Window->Method;
	const double RangeEndEtS = Time.StartEtS + Time.StepS * (Time.Count - 1);
	const int32 Num = Window->StartsEtS.Num();
	for (int32 I = 0; I < Num; ++I)
	{
		if (EtS < Window->StartsEtS[I])
		{
			// Not visible; this interval is the next rise.
			Out.SecondsToChange = Window->StartsEtS[I] - EtS;
			Out.ChangeUtc = Window->StartsUtc[I];
			return Out;
		}
		// An interval is open at its end, except a last interval cut off by the end of the
		// computed range: there the condition still holds at the very last instant.
		const bool bCutOffAtRangeEnd = (I == Num - 1) && Window->bClippedEnd;
		if (EtS < Window->EndsEtS[I] || (bCutOffAtRangeEnd && EtS <= Window->EndsEtS[I]))
		{
			Out.bVisibleNow = true;
			Out.SecondsToChange = Window->EndsEtS[I] - EtS;
			// A last interval that touches the end of the computed range has no known end.
			Out.bLowerBound = (I == Num - 1) && Window->bClippedEnd;
			if (!Out.bLowerBound)
			{
				Out.ChangeUtc = Window->EndsUtc[I];
			}
			return Out;
		}
	}
	// After the last interval: no rise inside the computed range.
	Out.bLowerBound = true;
	Out.SecondsToChange = FMath::Max(RangeEndEtS - EtS, 0.0);
	return Out;
}

bool FLsnDirectionTable::PositionKm(const FString& Body, int32 RecordIndex, FVector& OutPositionKm) const
{
	const int32 BodyIndex = Bodies.IndexOfByKey(Body);
	if (BodyIndex == INDEX_NONE || RecordIndex < 0 || RecordIndex >= Time.Count)
	{
		return false;
	}
	const int32 Base = (RecordIndex * Bodies.Num() + BodyIndex) * 3;
	OutPositionKm = FVector(PositionsKm[Base], PositionsKm[Base + 1], PositionsKm[Base + 2]);
	return true;
}

bool LsnPackageIO::LoadSitePackage(const FString& PackageDirectory, FLsnSitePackage& OutPackage, FString& OutError)
{
	OutPackage = FLsnSitePackage();
	FLsnReadContext Ctx;
	Ctx.Directory = PackageDirectory;

	FJsonObjectPtr Root;
	if (!LoadJsonFile(FPaths::Combine(PackageDirectory, TEXT("manifest.json")), Root, OutError))
	{
		return false;
	}

	FLsnSitePackage& P = OutPackage;
	P.Directory = PackageDirectory;
	ReadHeader(Ctx, Root, TEXT("site"), P.ContractVersion, P.PackageId, P.Status, P.bSynthetic);
	if (!Ctx.Failed())
	{
		P.ContentSha256 = GetString(Ctx, Root, TEXT("content_sha256"), TEXT("manifest"));
		Root->TryGetStringField(TEXT("synthetic_notice"), P.SyntheticNotice);
		if (P.bSynthetic && P.SyntheticNotice.IsEmpty())
		{
			Ctx.Fail(TEXT("a synthetic package must carry a synthetic_notice"));
		}
		const TArray<TSharedPtr<FJsonValue>>* Warnings = nullptr;
		if (Root->TryGetArrayField(TEXT("warnings"), Warnings) && Warnings)
		{
			for (const TSharedPtr<FJsonValue>& Warning : *Warnings)
			{
				P.Warnings.Add(Warning->AsString());
			}
		}
	}

	// Method cards.
	if (const FJsonObjectPtr Methods = GetObject(Ctx, Root, TEXT("methods"), TEXT("manifest")))
	{
		for (const auto& Pair : Methods->Values)
		{
			const FJsonObjectPtr* CardObject = nullptr;
			if (!Pair.Value.IsValid() || !Pair.Value->TryGetObject(CardObject) || !CardObject)
			{
				continue;
			}
			FLsnMethodCard Card;
			(*CardObject)->TryGetStringField(TEXT("title"), Card.Title);
			(*CardObject)->TryGetStringField(TEXT("frame"), Card.Frame);
			(*CardObject)->TryGetStringField(TEXT("time_scale"), Card.TimeScale);
			const FJsonObjectPtr* CardParameters = nullptr;
			if ((*CardObject)->TryGetObjectField(TEXT("parameters"), CardParameters) && CardParameters && CardParameters->IsValid())
			{
				for (const auto& Parameter : (*CardParameters)->Values)
				{
					double Number = 0.0;
					if (Parameter.Value.IsValid() && Parameter.Value->Type == EJson::Number && Parameter.Value->TryGetNumber(Number))
					{
						Card.NumericParameters.Add(FString(Parameter.Key), Number);
					}
				}
			}
			const FJsonObjectPtr* Validation = nullptr;
			if ((*CardObject)->TryGetObjectField(TEXT("validation"), Validation) && Validation)
			{
				(*Validation)->TryGetStringField(TEXT("status"), Card.ValidationStatus);
			}
			P.Methods.Add(FString(Pair.Key), Card);
		}
	}

	// Site.
	if (const FJsonObjectPtr Site = GetObject(Ctx, Root, TEXT("site"), TEXT("manifest")))
	{
		P.SiteId = GetString(Ctx, Site, TEXT("site_id"), TEXT("site"));
		P.SiteName = GetString(Ctx, Site, TEXT("name"), TEXT("site"));
		P.Frame = GetString(Ctx, Site, TEXT("frame"), TEXT("site"));
		P.LatDeg = GetNumber(Ctx, Site, TEXT("lat_deg"), TEXT("site"));
		P.LonDeg = GetNumber(Ctx, Site, TEXT("lon_deg"), TEXT("site"));
		P.ReferenceRadiusM = GetQuantity(Ctx, Site, TEXT("reference_radius_m"), TEXT("m"), TEXT("site"));
		P.SurfaceHeightM = GetQuantity(Ctx, Site, TEXT("surface_height_m"), TEXT("m"), TEXT("site"));
		P.RadiusM = GetQuantity(Ctx, Site, TEXT("radius_m"), TEXT("m"), TEXT("site"));
		P.PositionKm = GetVector3(Ctx, Site, TEXT("position_km"), TEXT("site"));
		if (const FJsonObjectPtr Enu = GetObject(Ctx, Site, TEXT("enu"), TEXT("site")))
		{
			P.EastBody = GetVector3(Ctx, Enu, TEXT("east"), TEXT("site.enu"));
			P.NorthBody = GetVector3(Ctx, Enu, TEXT("north"), TEXT("site.enu"));
			P.UpBody = GetVector3(Ctx, Enu, TEXT("up"), TEXT("site.enu"));
		}
		if (!Ctx.Failed() && P.ReferenceRadiusM <= 0.0)
		{
			Ctx.Fail(TEXT("site.reference_radius_m must be positive"));
		}
	}

	// Horizon.
	if (const FJsonObjectPtr Horizon = GetObject(Ctx, Root, TEXT("horizon"), TEXT("manifest")))
	{
		if (const FJsonObjectPtr Azimuth = GetObject(Ctx, Horizon, TEXT("azimuth"), TEXT("horizon")))
		{
			P.AzimuthStartDeg = GetNumber(Ctx, Azimuth, TEXT("start_deg"), TEXT("horizon.azimuth"));
			P.AzimuthStepDeg = GetNumber(Ctx, Azimuth, TEXT("step_deg"), TEXT("horizon.azimuth"));
			P.AzimuthCount = static_cast<int32>(GetNumber(Ctx, Azimuth, TEXT("count"), TEXT("horizon.azimuth")));
		}
		const TArray<TSharedPtr<FJsonValue>>* Heights = nullptr;
		if (!Ctx.Failed() && Horizon->TryGetArrayField(TEXT("observer_heights_m"), Heights) && Heights)
		{
			for (const TSharedPtr<FJsonValue>& Height : *Heights)
			{
				P.ObserverHeightsM.Add(Height->AsNumber());
			}
		}
		P.DefaultHeightIndex = static_cast<int32>(GetNumber(Ctx, Horizon, TEXT("default_height_index"), TEXT("horizon")));
		P.MaxRangeM = GetQuantity(Ctx, Horizon, TEXT("max_range_m"), TEXT("m"), TEXT("horizon"));

		if (!Ctx.Failed())
		{
			if (P.AzimuthCount < 3 || P.ObserverHeightsM.Num() < 1)
			{
				Ctx.Fail(TEXT("horizon needs at least three azimuths and one observer height"));
			}
			else if (FMath::Abs(P.AzimuthCount * P.AzimuthStepDeg - 360.0) > 1e-6)
			{
				Ctx.Fail(TEXT("horizon azimuth count times step is not 360 degrees"));
			}
			else if (P.DefaultHeightIndex < 0 || P.DefaultHeightIndex >= P.ObserverHeightsM.Num())
			{
				Ctx.Fail(TEXT("horizon.default_height_index is out of range"));
			}
		}
		const TArray<int32> HorizonShape = { P.ObserverHeightsM.Num(), P.AzimuthCount };
		ReadArray<float>(Ctx, Horizon, TEXT("elevation_deg"), HorizonShape, TEXT("deg"), P.HorizonElevationDeg, &P.HorizonElevationMethod);
		ReadArray<float>(Ctx, Horizon, TEXT("distance_m"), HorizonShape, TEXT("m"), P.HorizonDistanceM, &P.HorizonDistanceMethod);
		if (!Ctx.Failed() && Horizon->HasField(TEXT("obstacle_height_m")))
		{
			ReadArray<float>(Ctx, Horizon, TEXT("obstacle_height_m"), HorizonShape, TEXT("m"), P.ObstacleHeightM);
		}
		// Since 0.2: the profile grouped into obstacles. Absent in older packages.
		const TArray<TSharedPtr<FJsonValue>>* Obstacles = nullptr;
		if (!Ctx.Failed() && Horizon->HasField(TEXT("obstacle_id")) && Horizon->TryGetArrayField(TEXT("obstacles"), Obstacles) && Obstacles)
		{
			ReadArray<int32>(Ctx, Horizon, TEXT("obstacle_id"), HorizonShape, TEXT("1"), P.ObstacleId, &P.ObstacleMethod);
			for (const TSharedPtr<FJsonValue>& Value : *Obstacles)
			{
				const FJsonObjectPtr* Object = nullptr;
				if (Ctx.Failed() || !Value.IsValid() || !Value->TryGetObject(Object) || !Object)
				{
					continue;
				}
				FLsnObstacle O;
				O.Id = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("id"), TEXT("obstacle")));
				O.HeightIndex = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("height_index"), TEXT("obstacle")));
				O.AzimuthStartIndex = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("azimuth_start_index"), TEXT("obstacle")));
				O.AzimuthCount = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("azimuth_count"), TEXT("obstacle")));
				O.AzimuthStartDeg = GetNumber(Ctx, *Object, TEXT("azimuth_start_deg"), TEXT("obstacle"));
				O.AzimuthEndDeg = GetNumber(Ctx, *Object, TEXT("azimuth_end_deg"), TEXT("obstacle"));
				O.PeakAzimuthDeg = GetNumber(Ctx, *Object, TEXT("peak_azimuth_deg"), TEXT("obstacle"));
				O.PeakElevationDeg = GetNumber(Ctx, *Object, TEXT("peak_elevation_deg"), TEXT("obstacle"));
				O.PeakDistanceM = GetNumber(Ctx, *Object, TEXT("peak_distance_m"), TEXT("obstacle"));
				O.PeakLatDeg = GetNumberOrNaN(*Object, TEXT("peak_lat_deg"));
				O.PeakLonDeg = GetNumberOrNaN(*Object, TEXT("peak_lon_deg"));
				O.PeakHeightM = GetNumberOrNaN(*Object, TEXT("peak_height_m"));
				O.DistanceMinM = GetNumberOrNaN(*Object, TEXT("distance_min_m"));
				O.DistanceMaxM = GetNumberOrNaN(*Object, TEXT("distance_max_m"));
				(*Object)->TryGetBoolField(TEXT("near_field"), O.bNearField);
				(*Object)->TryGetStringField(TEXT("method"), O.Method);
				if (!Ctx.Failed() && (O.Id != P.Obstacles.Num() || O.AzimuthCount < 1 || O.AzimuthStartIndex < 0 || O.AzimuthStartIndex >= P.AzimuthCount))
				{
					Ctx.Fail(FString::Printf(TEXT("obstacle %d is out of order or has an impossible run"), O.Id));
				}
				P.Obstacles.Add(MoveTemp(O));
			}
		}
	}

	// Timeline: optional. A feature that was not computed is absent, and the view is hidden.
	const FJsonObjectPtr* TimelinePtr = nullptr;
	if (!Ctx.Failed() && Root->TryGetObjectField(TEXT("timeline"), TimelinePtr) && TimelinePtr && TimelinePtr->IsValid())
	{
		const FJsonObjectPtr Timeline = *TimelinePtr;
		P.bHasTimeline = true;
		P.DirectionTableId = GetString(Ctx, Timeline, TEXT("direction_table_id"), TEXT("timeline"));
		ReadTimeGrid(Ctx, Timeline, P.Time);
		const TArray<TSharedPtr<FJsonValue>>* Bodies = nullptr;
		if (!Ctx.Failed() && Timeline->TryGetArrayField(TEXT("bodies"), Bodies) && Bodies)
		{
			for (const TSharedPtr<FJsonValue>& Body : *Bodies)
			{
				P.Bodies.Add(Body->AsString());
			}
		}
		const FJsonObjectPtr SeriesObject = GetObject(Ctx, Timeline, TEXT("series"), TEXT("timeline"));
		const TArray<int32> PerSample = { P.Time.Count };
		const TArray<int32> PerHeightAndSample = { P.ObserverHeightsM.Num(), P.Time.Count };
		for (const FString& Body : P.Bodies)
		{
			const FJsonObjectPtr BodyObject = GetObject(Ctx, SeriesObject, *Body, TEXT("timeline.series"));
			if (!BodyObject.IsValid())
			{
				break;
			}
			FLsnBodySeries& S = P.Series.Add(Body);
			ReadArray<float>(Ctx, BodyObject, TEXT("azimuth_deg"), PerSample, TEXT("deg"), S.AzimuthDeg, &P.DirectionMethod);
			ReadArray<float>(Ctx, BodyObject, TEXT("elevation_deg"), PerSample, TEXT("deg"), S.ElevationDeg);
			if (!Ctx.Failed() && BodyObject->HasField(TEXT("angular_radius_deg")))
			{
				ReadArray<float>(Ctx, BodyObject, TEXT("angular_radius_deg"), PerSample, TEXT("deg"), S.AngularRadiusDeg);
			}
			ReadArray<float>(Ctx, BodyObject, TEXT("margin_deg"), PerHeightAndSample, TEXT("deg"), S.MarginDeg);
			ReadArray<float>(Ctx, BodyObject, TEXT("visible_fraction"), PerHeightAndSample, TEXT("1"), S.VisibleFraction);
			if (!Ctx.Failed() && BodyObject->HasField(TEXT("blocker_azimuth_index")))
			{
				ReadArray<int32>(Ctx, BodyObject, TEXT("blocker_azimuth_index"), PerHeightAndSample, TEXT("1"), S.BlockerAzimuthIndex, &P.BlockingMethod);
			}
			if (!Ctx.Failed() && BodyObject->HasField(TEXT("lit_fraction")))
			{
				ReadArray<float>(Ctx, BodyObject, TEXT("lit_fraction"), PerHeightAndSample, TEXT("1"), S.LitFraction);
			}
			if (!Ctx.Failed() && BodyObject->HasField(TEXT("ellipse_visible_share")))
			{
				ReadArray<float>(Ctx, BodyObject, TEXT("ellipse_visible_share"), PerSample, TEXT("1"), S.EllipseVisibleShare);
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Events = nullptr;
		if (!Ctx.Failed() && Timeline->TryGetArrayField(TEXT("events"), Events) && Events)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Events)
			{
				const FJsonObjectPtr* EventObject = nullptr;
				if (!Value.IsValid() || !Value->TryGetObject(EventObject) || !EventObject)
				{
					continue;
				}
				FLsnEvent Event;
				Event.Type = GetString(Ctx, *EventObject, TEXT("type"), TEXT("event"));
				Event.Body = GetString(Ctx, *EventObject, TEXT("body"), TEXT("event"));
				Event.HeightIndex = static_cast<int32>(GetNumber(Ctx, *EventObject, TEXT("height_index"), TEXT("event")));
				Event.EtS = GetNumber(Ctx, *EventObject, TEXT("et_s"), TEXT("event"));
				Event.Utc = GetString(Ctx, *EventObject, TEXT("utc"), TEXT("event"));
				Event.AzimuthDeg = GetNumber(Ctx, *EventObject, TEXT("azimuth_deg"), TEXT("event"));
				Event.HorizonElevationDeg = GetNumber(Ctx, *EventObject, TEXT("horizon_elevation_deg"), TEXT("event"));
				// The terrain point of an event may be unknown (null in the package).
				Event.ObstacleDistanceM = GetNumberOrNaN(*EventObject, TEXT("obstacle_distance_m"));
				Event.Method = GetString(Ctx, *EventObject, TEXT("method"), TEXT("event"));
				P.Events.Add(Event);
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Windows = nullptr;
		if (!Ctx.Failed() && Timeline->TryGetArrayField(TEXT("windows"), Windows) && Windows)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Windows)
			{
				const FJsonObjectPtr* WindowObject = nullptr;
				if (!Value.IsValid() || !Value->TryGetObject(WindowObject) || !WindowObject)
				{
					continue;
				}
				FLsnWindow Window;
				Window.Id = GetString(Ctx, *WindowObject, TEXT("id"), TEXT("window"));
				Window.Subject = GetString(Ctx, *WindowObject, TEXT("subject"), TEXT("window"));
				Window.HeightIndex = static_cast<int32>(GetNumber(Ctx, *WindowObject, TEXT("height_index"), TEXT("window")));
				Window.Method = GetString(Ctx, *WindowObject, TEXT("method"), TEXT("window"));
				(*WindowObject)->TryGetBoolField(TEXT("clipped_start"), Window.bClippedStart);
				(*WindowObject)->TryGetBoolField(TEXT("clipped_end"), Window.bClippedEnd);
				const TArray<TSharedPtr<FJsonValue>>* IntervalsEt = nullptr;
				const TArray<TSharedPtr<FJsonValue>>* IntervalsUtc = nullptr;
				if (Ctx.Failed() || !(*WindowObject)->TryGetArrayField(TEXT("intervals_et_s"), IntervalsEt) || !IntervalsEt
					|| !(*WindowObject)->TryGetArrayField(TEXT("intervals_utc"), IntervalsUtc) || !IntervalsUtc || IntervalsUtc->Num() != IntervalsEt->Num())
				{
					Ctx.Fail(FString::Printf(TEXT("window '%s' has no matching intervals_et_s and intervals_utc"), *Window.Id));
					break;
				}
				for (int32 I = 0; I < IntervalsEt->Num(); ++I)
				{
					const TArray<TSharedPtr<FJsonValue>>& Et = (*IntervalsEt)[I]->AsArray();
					const TArray<TSharedPtr<FJsonValue>>& Utc = (*IntervalsUtc)[I]->AsArray();
					if (Et.Num() != 2 || Utc.Num() != 2 || !(Et[1]->AsNumber() > Et[0]->AsNumber())
						|| (I > 0 && !(Et[0]->AsNumber() >= Window.EndsEtS.Last())))
					{
						Ctx.Fail(FString::Printf(TEXT("window '%s' has intervals that are not sorted pairs"), *Window.Id));
						break;
					}
					Window.StartsEtS.Add(Et[0]->AsNumber());
					Window.EndsEtS.Add(Et[1]->AsNumber());
					Window.StartsUtc.Add(Utc[0]->AsString());
					Window.EndsUtc.Add(Utc[1]->AsString());
				}
				P.Windows.Add(MoveTemp(Window));
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Blockers = nullptr;
		if (!Ctx.Failed() && Timeline->TryGetArrayField(TEXT("blockers"), Blockers) && Blockers)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Blockers)
			{
				const FJsonObjectPtr* Object = nullptr;
				if (Ctx.Failed() || !Value.IsValid() || !Value->TryGetObject(Object) || !Object)
				{
					continue;
				}
				FLsnBlocker B;
				B.Body = GetString(Ctx, *Object, TEXT("body"), TEXT("blocker"));
				B.HeightIndex = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("height_index"), TEXT("blocker")));
				B.ObstacleId = static_cast<int32>(GetNumber(Ctx, *Object, TEXT("obstacle_id"), TEXT("blocker")));
				B.LostS = GetNumber(Ctx, *Object, TEXT("lost_s"), TEXT("blocker"));
				B.ShareOfLost = GetNumber(Ctx, *Object, TEXT("share_of_lost"), TEXT("blocker"));
				B.PeakAzimuthDeg = GetNumberOrNaN(*Object, TEXT("peak_azimuth_deg"));
				B.PeakElevationDeg = GetNumberOrNaN(*Object, TEXT("peak_elevation_deg"));
				B.PeakDistanceM = GetNumberOrNaN(*Object, TEXT("peak_distance_m"));
				(*Object)->TryGetBoolField(TEXT("near_field"), B.bNearField);
				B.Method = GetString(Ctx, *Object, TEXT("method"), TEXT("blocker"));
				const TArray<TSharedPtr<FJsonValue>>* Intervals = nullptr;
				if ((*Object)->TryGetArrayField(TEXT("intervals_et_s"), Intervals) && Intervals)
				{
					for (const TSharedPtr<FJsonValue>& Interval : *Intervals)
					{
						const TArray<TSharedPtr<FJsonValue>>& Pair = Interval->AsArray();
						if (Pair.Num() == 2)
						{
							B.StartsEtS.Add(Pair[0]->AsNumber());
							B.EndsEtS.Add(Pair[1]->AsNumber());
						}
					}
				}
				P.Blockers.Add(MoveTemp(B));
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Metrics = nullptr;
		if (!Ctx.Failed() && Timeline->TryGetArrayField(TEXT("metrics"), Metrics) && Metrics)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Metrics)
			{
				const FJsonObjectPtr* MetricObject = nullptr;
				if (!Value.IsValid() || !Value->TryGetObject(MetricObject) || !MetricObject)
				{
					continue;
				}
				FLsnMetric Metric;
				Metric.Id = GetString(Ctx, *MetricObject, TEXT("id"), TEXT("metric"));
				Metric.Unit = GetString(Ctx, *MetricObject, TEXT("unit"), TEXT("metric"));
				Metric.Method = GetString(Ctx, *MetricObject, TEXT("method"), TEXT("metric"));
				(*MetricObject)->TryGetStringField(TEXT("label"), Metric.Label);
				const double Height = GetNumberOrNaN(*MetricObject, TEXT("height_index"));
				Metric.HeightIndex = FMath::IsNaN(Height) ? -1 : static_cast<int32>(Height);
				const double Number = GetNumberOrNaN(*MetricObject, TEXT("value"));
				Metric.bHasValue = !FMath::IsNaN(Number);
				Metric.Value = Metric.bHasValue ? Number : 0.0;
				P.Metrics.Add(MoveTemp(Metric));
			}
		}
	}

	if (!Ctx.Failed())
	{
		ReadPlanningFields(Root, P);
		ReadTerrainSource(Root, P.TerrainSource);
	}

	if (Ctx.Failed())
	{
		OutError = FString::Printf(TEXT("%s: %s"), *PackageDirectory, *Ctx.Error);
		OutPackage = FLsnSitePackage();
		return false;
	}
	return true;
}

bool LsnPackageIO::LoadDirectionTable(const FString& PackageDirectory, FLsnDirectionTable& OutTable, FString& OutError)
{
	OutTable = FLsnDirectionTable();
	FLsnReadContext Ctx;
	Ctx.Directory = PackageDirectory;

	FJsonObjectPtr Root;
	if (!LoadJsonFile(FPaths::Combine(PackageDirectory, TEXT("manifest.json")), Root, OutError))
	{
		return false;
	}
	FString Version, Status;
	ReadHeader(Ctx, Root, TEXT("direction_table"), Version, OutTable.PackageId, Status, OutTable.bSynthetic);
	OutTable.Frame = GetString(Ctx, Root, TEXT("frame"), TEXT("manifest"));
	OutTable.Center = GetString(Ctx, Root, TEXT("center"), TEXT("manifest"));
	const TArray<TSharedPtr<FJsonValue>>* Bodies = nullptr;
	if (!Ctx.Failed() && Root->TryGetArrayField(TEXT("bodies"), Bodies) && Bodies)
	{
		for (const TSharedPtr<FJsonValue>& Body : *Bodies)
		{
			OutTable.Bodies.Add(Body->AsString());
		}
	}
	ReadTimeGrid(Ctx, Root, OutTable.Time);
	const TArray<int32> Shape = { OutTable.Time.Count, OutTable.Bodies.Num(), 3 };
	ReadArray<double>(Ctx, Root, TEXT("positions_km"), Shape, TEXT("km"), OutTable.PositionsKm);

	if (Ctx.Failed())
	{
		OutError = FString::Printf(TEXT("%s: %s"), *PackageDirectory, *Ctx.Error);
		OutTable = FLsnDirectionTable();
		return false;
	}
	return true;
}

bool LsnPackageIO::LoadIndex(const FString& PackageRoot, TArray<FLsnIndexEntry>& OutEntries, FString& OutError)
{
	OutEntries.Reset();
	FJsonObjectPtr Root;
	if (!LoadJsonFile(FPaths::Combine(PackageRoot, TEXT("index.json")), Root, OutError))
	{
		return false;
	}
	FString Kind;
	const TArray<TSharedPtr<FJsonValue>>* Packages = nullptr;
	if (!Root->TryGetStringField(TEXT("kind"), Kind) || Kind != TEXT("index") || !Root->TryGetArrayField(TEXT("packages"), Packages) || !Packages)
	{
		OutError = FString::Printf(TEXT("%s/index.json is not a package index"), *PackageRoot);
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *Packages)
	{
		const FJsonObjectPtr* Object = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object)
		{
			continue;
		}
		FLsnIndexEntry Entry;
		(*Object)->TryGetStringField(TEXT("kind"), Entry.Kind);
		(*Object)->TryGetStringField(TEXT("package_id"), Entry.PackageId);
		(*Object)->TryGetStringField(TEXT("path"), Entry.Path);
		(*Object)->TryGetStringField(TEXT("site_id"), Entry.SiteId);
		(*Object)->TryGetStringField(TEXT("name"), Entry.Name);
		(*Object)->TryGetBoolField(TEXT("synthetic"), Entry.bSynthetic);
		(*Object)->TryGetBoolField(TEXT("has_timeline"), Entry.bHasTimeline);
		(*Object)->TryGetStringArrayField(TEXT("site_ids"), Entry.SiteIds);
		(*Object)->TryGetStringField(TEXT("programme"), Entry.Programme);
		OutEntries.Add(Entry);
	}
	return true;
}
