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
			if (FMath::IsNaN(Value))
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
				Event.ObstacleDistanceM = GetNumber(Ctx, *EventObject, TEXT("obstacle_distance_m"), TEXT("event"));
				Event.Method = GetString(Ctx, *EventObject, TEXT("method"), TEXT("event"));
				P.Events.Add(Event);
			}
		}
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
		OutEntries.Add(Entry);
	}
	return true;
}
