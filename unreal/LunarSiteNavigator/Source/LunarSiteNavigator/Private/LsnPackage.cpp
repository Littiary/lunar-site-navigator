#include "LsnPackage.h"

#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

static_assert(PLATFORM_LITTLE_ENDIAN, "Package arrays are little-endian and are read without byte swapping.");

namespace
{
	using FJsonPtr = TSharedPtr<FJsonObject>;

	bool LoadJsonFile(const FString& Path, FJsonPtr& Out, FString& OutError)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			OutError = FString::Printf(TEXT("Cannot read %s"), *Path);
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		if (!FJsonSerializer::Deserialize(Reader, Out) || !Out.IsValid())
		{
			OutError = FString::Printf(TEXT("%s is not valid JSON"), *Path);
			return false;
		}
		return true;
	}

	bool GetObject(const FJsonPtr& Parent, const TCHAR* Field, FJsonPtr& Out, FString& OutError)
	{
		const FJsonPtr* Found = nullptr;
		if (!Parent->TryGetObjectField(Field, Found) || Found == nullptr || !Found->IsValid())
		{
			OutError = FString::Printf(TEXT("Missing object '%s'"), Field);
			return false;
		}
		Out = *Found;
		return true;
	}

	bool GetNumber(const FJsonPtr& Parent, const TCHAR* Field, double& Out, FString& OutError)
	{
		if (!Parent->TryGetNumberField(Field, Out))
		{
			OutError = FString::Printf(TEXT("Missing number '%s'"), Field);
			return false;
		}
		return true;
	}

	/** A single quantity {"value", "unit", "method"} (SPEC 3.2). */
	bool GetQuantity(const FJsonPtr& Parent, const TCHAR* Field, double& Out, FString& OutError)
	{
		FJsonPtr Quantity;
		return GetObject(Parent, Field, Quantity, OutError) && GetNumber(Quantity, TEXT("value"), Out, OutError);
	}

	bool GetVector(const FJsonPtr& Parent, const TCHAR* Field, FVector& Out, FString& OutError)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Parent->TryGetArrayField(Field, Values) || Values == nullptr || Values->Num() != 3)
		{
			OutError = FString::Printf(TEXT("'%s' is not a vector of three numbers"), Field);
			return false;
		}
		Out = FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
		return true;
	}

	template <typename T> const TCHAR* DTypeOf();
	template <> const TCHAR* DTypeOf<float>() { return TEXT("<f4"); }
	template <> const TCHAR* DTypeOf<double>() { return TEXT("<f8"); }

	/** Reads an array reference (SPEC 3.1) and checks dtype, shape and file size. */
	template <typename T>
	bool ReadArray(const FString& Dir, const FJsonPtr& Parent, const TCHAR* Field, const TArray<int32>& ExpectedShape, TArray<T>& Out, FString& OutError)
	{
		FJsonPtr Ref;
		if (!GetObject(Parent, Field, Ref, OutError))
		{
			return false;
		}
		const FString DType = Ref->GetStringField(TEXT("dtype"));
		if (DType != DTypeOf<T>())
		{
			OutError = FString::Printf(TEXT("Array '%s' has dtype %s, expected %s"), Field, *DType, DTypeOf<T>());
			return false;
		}
		const TArray<TSharedPtr<FJsonValue>>* ShapeValues = nullptr;
		if (!Ref->TryGetArrayField(TEXT("shape"), ShapeValues) || ShapeValues == nullptr)
		{
			OutError = FString::Printf(TEXT("Array '%s' has no shape"), Field);
			return false;
		}
		TArray<int32> Shape;
		int64 Count = 1;
		for (const TSharedPtr<FJsonValue>& Value : *ShapeValues)
		{
			Shape.Add(static_cast<int32>(Value->AsNumber()));
			Count *= Shape.Last();
		}
		if (Shape != ExpectedShape)
		{
			OutError = FString::Printf(TEXT("Array '%s' has an unexpected shape"), Field);
			return false;
		}
		const FString Path = FPaths::Combine(Dir, Ref->GetStringField(TEXT("file")));
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Path))
		{
			OutError = FString::Printf(TEXT("Cannot read %s"), *Path);
			return false;
		}
		if (Bytes.Num() != Count * static_cast<int64>(sizeof(T)))
		{
			OutError = FString::Printf(TEXT("%s has %d bytes, the manifest states %lld values"), *Path, Bytes.Num(), Count);
			return false;
		}
		Out.SetNumUninitialized(static_cast<int32>(Count));
		FMemory::Memcpy(Out.GetData(), Bytes.GetData(), Bytes.Num());
		return true;
	}

	bool ReadTimeGrid(const FJsonPtr& Parent, FLsnTimeGrid& Out, FString& OutError)
	{
		FJsonPtr Time;
		double Count = 0.0, Leap = 0.0;
		if (!GetObject(Parent, TEXT("time"), Time, OutError)
			|| !GetNumber(Time, TEXT("start_et_s"), Out.StartEtS, OutError)
			|| !GetNumber(Time, TEXT("step_s"), Out.StepS, OutError)
			|| !GetNumber(Time, TEXT("count"), Count, OutError)
			|| !GetNumber(Time, TEXT("leap_seconds_in_range"), Leap, OutError))
		{
			return false;
		}
		Out.Count = static_cast<int32>(Count);
		Out.LeapSecondsInRange = static_cast<int32>(Leap);
		Out.StartUtc = Time->GetStringField(TEXT("start_utc"));
		Out.EndUtc = Time->GetStringField(TEXT("end_utc"));
		return true;
	}

	bool ReadHeader(const FJsonPtr& Manifest, const TCHAR* ExpectedKind, FLsnPackageHeader& Out, FString& OutError)
	{
		FJsonPtr Contract;
		if (!GetObject(Manifest, TEXT("contract"), Contract, OutError))
		{
			return false;
		}
		if (Contract->GetStringField(TEXT("name")) != TEXT("lsn-package"))
		{
			OutError = TEXT("Not an lsn-package");
			return false;
		}
		Out.ContractVersion = Contract->GetStringField(TEXT("version"));
		if (!LsnContract::IsSupportedVersion(Out.ContractVersion))
		{
			OutError = FString::Printf(TEXT("Contract version %s is not supported: this reader understands major version 0 only"), *Out.ContractVersion);
			return false;
		}
		Out.Kind = Manifest->GetStringField(TEXT("kind"));
		if (Out.Kind != ExpectedKind)
		{
			OutError = FString::Printf(TEXT("Package kind is '%s', expected '%s'"), *Out.Kind, ExpectedKind);
			return false;
		}
		Out.PackageId = Manifest->GetStringField(TEXT("package_id"));
		Out.ContentSha256 = Manifest->GetStringField(TEXT("content_sha256"));
		Out.Status = Manifest->GetStringField(TEXT("status"));
		Out.bSynthetic = Manifest->GetBoolField(TEXT("synthetic"));
		Manifest->TryGetStringField(TEXT("synthetic_notice"), Out.SyntheticNotice);
		Manifest->TryGetStringArrayField(TEXT("warnings"), Out.Warnings);
		if (Out.Status == TEXT("error"))
		{
			OutError = FString::Printf(TEXT("Package %s has status 'error'"), *Out.PackageId);
			return false;
		}
		const FJsonPtr* Methods = nullptr;
		if (Manifest->TryGetObjectField(TEXT("methods"), Methods) && Methods != nullptr)
		{
			for (const auto& Pair : (*Methods)->Values)
			{
				const FJsonPtr* Card = nullptr;
				if (!Pair.Value->TryGetObject(Card) || Card == nullptr)
				{
					continue;
				}
				Out.MethodTitle.Add(FString(Pair.Key), (*Card)->GetStringField(TEXT("title")));
				const FJsonPtr* Validation = nullptr;
				if ((*Card)->TryGetObjectField(TEXT("validation"), Validation) && Validation != nullptr)
				{
					Out.MethodStatus.Add(FString(Pair.Key), (*Validation)->GetStringField(TEXT("status")));
				}
			}
		}
		return true;
	}
}

bool LsnContract::IsSupportedVersion(const FString& Version)
{
	FString Major, Minor;
	return Version.Split(TEXT("."), &Major, &Minor) && Major == TEXT("0") && Minor.IsNumeric();
}

FString LsnContract::FindPackageRoot()
{
	TArray<FString> Candidates;
	FString FromCommandLine;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPackageRoot="), FromCommandLine))
	{
		Candidates.Add(FromCommandLine);
	}
	const FString Project = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
	Candidates.Add(FPaths::Combine(Project, TEXT("Packages")));
	Candidates.Add(FPaths::Combine(Project, TEXT("../../docs/contract/sample/packages")));
	Candidates.Add(FPaths::Combine(Project, TEXT("Saved/ContractSample/docs/contract/sample/packages")));
	for (FString& Candidate : Candidates)
	{
		FPaths::CollapseRelativeDirectories(Candidate);
		if (IFileManager::Get().FileExists(*FPaths::Combine(Candidate, TEXT("index.json"))))
		{
			return Candidate;
		}
	}
	return FString();
}

bool FLsnSitePackage::Load(const FString& PackageDir, FString& OutError)
{
	*this = FLsnSitePackage();
	Directory = PackageDir;

	FJsonPtr Manifest;
	if (!LoadJsonFile(FPaths::Combine(PackageDir, TEXT("manifest.json")), Manifest, OutError)
		|| !ReadHeader(Manifest, TEXT("site"), Header, OutError))
	{
		return false;
	}

	FJsonPtr Site, Enu;
	if (!GetObject(Manifest, TEXT("site"), Site, OutError)
		|| !GetNumber(Site, TEXT("lat_deg"), LatDeg, OutError)
		|| !GetNumber(Site, TEXT("lon_deg"), LonDeg, OutError)
		|| !GetQuantity(Site, TEXT("reference_radius_m"), ReferenceRadiusM, OutError)
		|| !GetQuantity(Site, TEXT("surface_height_m"), SurfaceHeightM, OutError)
		|| !GetQuantity(Site, TEXT("radius_m"), RadiusM, OutError)
		|| !GetVector(Site, TEXT("position_km"), Frame.PositionKm, OutError)
		|| !GetObject(Site, TEXT("enu"), Enu, OutError)
		|| !GetVector(Enu, TEXT("east"), Frame.East, OutError)
		|| !GetVector(Enu, TEXT("north"), Frame.North, OutError)
		|| !GetVector(Enu, TEXT("up"), Frame.Up, OutError))
	{
		return false;
	}
	SiteId = Site->GetStringField(TEXT("site_id"));
	Name = Site->GetStringField(TEXT("name"));
	FrameName = Site->GetStringField(TEXT("frame"));

	FJsonPtr Horizon, Azimuth;
	double Count = 0.0, DefaultIndex = 0.0;
	if (!GetObject(Manifest, TEXT("horizon"), Horizon, OutError)
		|| !GetObject(Horizon, TEXT("azimuth"), Azimuth, OutError)
		|| !GetNumber(Azimuth, TEXT("step_deg"), AzimuthStepDeg, OutError)
		|| !GetNumber(Azimuth, TEXT("count"), Count, OutError)
		|| !GetNumber(Horizon, TEXT("default_height_index"), DefaultIndex, OutError)
		|| !GetQuantity(Horizon, TEXT("max_range_m"), MaxRangeM, OutError))
	{
		return false;
	}
	AzimuthCount = static_cast<int32>(Count);
	DefaultHeightIndex = static_cast<int32>(DefaultIndex);
	const TArray<TSharedPtr<FJsonValue>>* Heights = nullptr;
	if (!Horizon->TryGetArrayField(TEXT("observer_heights_m"), Heights) || Heights == nullptr || Heights->Num() == 0)
	{
		OutError = TEXT("horizon.observer_heights_m is missing or empty");
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *Heights)
	{
		ObserverHeightsM.Add(Value->AsNumber());
	}
	if (AzimuthCount <= 0 || !FMath::IsNearlyEqual(AzimuthCount * AzimuthStepDeg, 360.0, 1e-9) || !ObserverHeightsM.IsValidIndex(DefaultHeightIndex))
	{
		OutError = TEXT("horizon.azimuth or default_height_index is inconsistent");
		return false;
	}

	const TArray<int32> HorizonShape = { NumHeights(), AzimuthCount };
	if (!ReadArray(PackageDir, Horizon, TEXT("elevation_deg"), HorizonShape, HorizonElevationDeg, OutError)
		|| !ReadArray(PackageDir, Horizon, TEXT("distance_m"), HorizonShape, HorizonDistanceM, OutError))
	{
		return false;
	}
	if (Horizon->HasField(TEXT("obstacle_height_m")) && Horizon->HasField(TEXT("obstacle_lat_deg")) && Horizon->HasField(TEXT("obstacle_lon_deg")))
	{
		if (!ReadArray(PackageDir, Horizon, TEXT("obstacle_height_m"), HorizonShape, ObstacleHeightM, OutError)
			|| !ReadArray(PackageDir, Horizon, TEXT("obstacle_lat_deg"), HorizonShape, ObstacleLatDeg, OutError)
			|| !ReadArray(PackageDir, Horizon, TEXT("obstacle_lon_deg"), HorizonShape, ObstacleLonDeg, OutError))
		{
			return false;
		}
		bHasObstaclePoints = true;
	}

	const FJsonPtr* TimelinePtr = nullptr;
	if (Manifest->TryGetObjectField(TEXT("timeline"), TimelinePtr) && TimelinePtr != nullptr && TimelinePtr->IsValid())
	{
		const FJsonPtr Timeline = *TimelinePtr;
		FJsonPtr SeriesObject;
		if (!ReadTimeGrid(Timeline, Time, OutError) || !GetObject(Timeline, TEXT("series"), SeriesObject, OutError))
		{
			return false;
		}
		DirectionTableId = Timeline->GetStringField(TEXT("direction_table_id"));
		Timeline->TryGetStringArrayField(TEXT("bodies"), Bodies);
		const TArray<int32> PerTime = { Time.Count };
		const TArray<int32> PerHeightAndTime = { NumHeights(), Time.Count };
		for (const FString& Body : Bodies)
		{
			FJsonPtr BodyObject;
			FLsnBodySeries& Out = Series.Add(Body);
			if (!GetObject(SeriesObject, *Body, BodyObject, OutError)
				|| !ReadArray(PackageDir, BodyObject, TEXT("azimuth_deg"), PerTime, Out.AzimuthDeg, OutError)
				|| !ReadArray(PackageDir, BodyObject, TEXT("elevation_deg"), PerTime, Out.ElevationDeg, OutError)
				|| !ReadArray(PackageDir, BodyObject, TEXT("margin_deg"), PerHeightAndTime, Out.MarginDeg, OutError)
				|| !ReadArray(PackageDir, BodyObject, TEXT("visible_fraction"), PerHeightAndTime, Out.VisibleFraction, OutError))
			{
				return false;
			}
			if (BodyObject->HasField(TEXT("angular_radius_deg"))
				&& !ReadArray(PackageDir, BodyObject, TEXT("angular_radius_deg"), PerTime, Out.AngularRadiusDeg, OutError))
			{
				return false;
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* EventValues = nullptr;
		if (Timeline->TryGetArrayField(TEXT("events"), EventValues) && EventValues != nullptr)
		{
			for (const TSharedPtr<FJsonValue>& Value : *EventValues)
			{
				const FJsonPtr* EventObject = nullptr;
				if (!Value->TryGetObject(EventObject) || EventObject == nullptr)
				{
					continue;
				}
				FLsnEvent& Event = Events.AddDefaulted_GetRef();
				Event.Type = (*EventObject)->GetStringField(TEXT("type"));
				Event.Body = (*EventObject)->GetStringField(TEXT("body"));
				Event.HeightIndex = static_cast<int32>((*EventObject)->GetNumberField(TEXT("height_index")));
				Event.EtS = (*EventObject)->GetNumberField(TEXT("et_s"));
				Event.Utc = (*EventObject)->GetStringField(TEXT("utc"));
				Event.AzimuthDeg = (*EventObject)->GetNumberField(TEXT("azimuth_deg"));
				Event.HorizonElevationDeg = (*EventObject)->GetNumberField(TEXT("horizon_elevation_deg"));
				Event.ObstacleDistanceM = (*EventObject)->GetNumberField(TEXT("obstacle_distance_m"));
				Event.Method = (*EventObject)->GetStringField(TEXT("method"));
			}
		}
		bHasTimeline = true;
	}
	return true;
}

double FLsnSitePackage::InterpolatedHorizonElevationDeg(int32 HeightIndex, double AzDeg) const
{
	const double Position = FMath::Fmod(FMath::Fmod(AzDeg, 360.0) + 360.0, 360.0) / AzimuthStepDeg;
	const int32 Lower = static_cast<int32>(FMath::FloorToDouble(Position)) % AzimuthCount;
	const int32 Upper = (Lower + 1) % AzimuthCount;
	const double T = Position - FMath::FloorToDouble(Position);
	const float* Row = HorizonElevationDeg.GetData() + HeightIndex * AzimuthCount;
	return (1.0 - T) * Row[Lower] + T * Row[Upper];
}

int32 FLsnSitePackage::NearestAzimuthIndex(double AzDeg) const
{
	const double Position = FMath::Fmod(FMath::Fmod(AzDeg, 360.0) + 360.0, 360.0) / AzimuthStepDeg;
	return static_cast<int32>(FMath::RoundToDouble(Position)) % AzimuthCount;
}

bool FLsnSitePackage::GetBodySky(const FString& Body, int32 TimeIndex, int32 HeightIndex, FLsnBodySky& Out) const
{
	const FLsnBodySeries* Found = bHasTimeline ? Series.Find(Body) : nullptr;
	if (Found == nullptr || TimeIndex < 0 || TimeIndex >= Time.Count || !ObserverHeightsM.IsValidIndex(HeightIndex))
	{
		return false;
	}
	Out.AzimuthDeg = Found->AzimuthDeg[TimeIndex];
	Out.ElevationDeg = Found->ElevationDeg[TimeIndex];
	Out.bHasAngularRadius = Found->AngularRadiusDeg.Num() == Time.Count;
	Out.AngularRadiusDeg = Out.bHasAngularRadius ? Found->AngularRadiusDeg[TimeIndex] : 0.0;
	Out.MarginDeg = Found->MarginDeg[HeightIndex * Time.Count + TimeIndex];
	Out.VisibleFraction = Found->VisibleFraction[HeightIndex * Time.Count + TimeIndex];
	Out.WorldDir = LsnFrame::AzElToWorldDir(Out.AzimuthDeg, Out.ElevationDeg);
	return true;
}

FVector FLsnSitePackage::ObserverWorldCm(int32 HeightIndex) const
{
	return LsnFrame::EnuMToWorldCm(FVector(0.0, 0.0, ObserverHeightsM[HeightIndex]));
}

FString FLsnSitePackage::UtcLabel(int32 TimeIndex) const
{
	// SPEC 3.5: start_utc + i * step_s may be used as a label only without a leap second in range.
	FDateTime Start;
	if (!bHasTimeline || Time.LeapSecondsInRange != 0 || !FDateTime::ParseIso8601(*Time.StartUtc, Start))
	{
		return FString();
	}
	const FDateTime When = Start + FTimespan::FromSeconds(TimeIndex * Time.StepS);
	return When.ToString(TEXT("%Y-%m-%d %H:%M:%S")) + TEXT(" UTC");
}

bool FLsnDirectionTable::Load(const FString& PackageDir, FString& OutError)
{
	*this = FLsnDirectionTable();
	FJsonPtr Manifest;
	if (!LoadJsonFile(FPaths::Combine(PackageDir, TEXT("manifest.json")), Manifest, OutError)
		|| !ReadHeader(Manifest, TEXT("direction_table"), Header, OutError)
		|| !ReadTimeGrid(Manifest, Time, OutError))
	{
		return false;
	}
	FrameName = Manifest->GetStringField(TEXT("frame"));
	Manifest->TryGetStringArrayField(TEXT("bodies"), Bodies);
	const TArray<int32> Shape = { Time.Count, Bodies.Num(), 3 };
	if (!ReadArray(PackageDir, Manifest, TEXT("positions_km"), Shape, PositionsKm, OutError))
	{
		return false;
	}
	const FJsonPtr* Radii = nullptr;
	if (Manifest->TryGetObjectField(TEXT("body_radii_km"), Radii) && Radii != nullptr)
	{
		for (const FString& Body : Bodies)
		{
			double Radius = 0.0;
			FString Ignored;
			if (GetQuantity(*Radii, *Body, Radius, Ignored))
			{
				BodyRadiiKm.Add(Body, Radius);
			}
		}
	}
	return true;
}

FVector FLsnDirectionTable::PositionKm(int32 TimeIndex, int32 BodyIndex) const
{
	const double* P = PositionsKm.GetData() + (static_cast<int64>(TimeIndex) * Bodies.Num() + BodyIndex) * 3;
	return FVector(P[0], P[1], P[2]);
}

bool FLsnIndex::Load(const FString& PackageRoot, FString& OutError)
{
	Root = PackageRoot;
	Packages.Reset();
	FJsonPtr Index;
	if (!LoadJsonFile(FPaths::Combine(PackageRoot, TEXT("index.json")), Index, OutError))
	{
		return false;
	}
	FJsonPtr Contract;
	if (!GetObject(Index, TEXT("contract"), Contract, OutError))
	{
		return false;
	}
	const FString Version = Contract->GetStringField(TEXT("version"));
	if (!LsnContract::IsSupportedVersion(Version))
	{
		OutError = FString::Printf(TEXT("Index has contract version %s; this reader understands major version 0 only"), *Version);
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Index->TryGetArrayField(TEXT("packages"), Values) || Values == nullptr)
	{
		OutError = TEXT("index.json has no 'packages'");
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		const FJsonPtr* Object = nullptr;
		if (!Value->TryGetObject(Object) || Object == nullptr)
		{
			continue;
		}
		FLsnIndexEntry& Entry = Packages.AddDefaulted_GetRef();
		Entry.Kind = (*Object)->GetStringField(TEXT("kind"));
		Entry.PackageId = (*Object)->GetStringField(TEXT("package_id"));
		Entry.Path = (*Object)->GetStringField(TEXT("path"));
		Entry.Status = (*Object)->GetStringField(TEXT("status"));
		Entry.bSynthetic = (*Object)->GetBoolField(TEXT("synthetic"));
		(*Object)->TryGetStringField(TEXT("site_id"), Entry.SiteId);
		(*Object)->TryGetStringField(TEXT("name"), Entry.Name);
		(*Object)->TryGetBoolField(TEXT("has_timeline"), Entry.bHasTimeline);
	}
	return true;
}

FString FLsnIndex::FindPackageDir(const FString& Kind, const FString& SiteId) const
{
	for (const FLsnIndexEntry& Entry : Packages)
	{
		if (Entry.Kind == Kind && Entry.Status != TEXT("error") && (SiteId.IsEmpty() || Entry.SiteId == SiteId))
		{
			return FPaths::Combine(Root, Entry.Path);
		}
	}
	return FString();
}

FString FLsnIndex::FindPackageDirById(const FString& PackageId) const
{
	for (const FLsnIndexEntry& Entry : Packages)
	{
		if (Entry.PackageId == PackageId)
		{
			return FPaths::Combine(Root, Entry.Path);
		}
	}
	return FString();
}
