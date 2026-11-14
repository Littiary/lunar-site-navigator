#include "Terrain/LsnTerrainGrid.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Package/LsnPackage.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

bool FLsnTerrainGrid::Load(const FString& Directory, FLsnTerrainGrid& OutGrid, FString& OutError)
{
	OutGrid = FLsnTerrainGrid();
	const FString MetaPath = FPaths::Combine(Directory, TEXT("terrain.json"));
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(Text, *MetaPath))
	{
		OutError = FString::Printf(TEXT("cannot read %s"), *MetaPath);
		return false;
	}
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = FString::Printf(TEXT("%s is not valid JSON"), *MetaPath);
		return false;
	}
	const TSharedPtr<FJsonObject>* Format = nullptr;
	const TSharedPtr<FJsonObject>* Azimuth = nullptr;
	const TSharedPtr<FJsonObject>* Heights = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* Rings = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* Shape = nullptr;
	if (!Root->TryGetObjectField(TEXT("format"), Format) || (*Format)->GetStringField(TEXT("name")) != TEXT("lsn-unreal-terrain-grid")
		|| (*Format)->GetStringField(TEXT("version")) != TEXT("1"))
	{
		OutError = FString::Printf(TEXT("%s is not a terrain grid of format version 1"), *MetaPath);
		return false;
	}
	if (!Root->TryGetObjectField(TEXT("azimuth"), Azimuth) || !Root->TryGetObjectField(TEXT("heights"), Heights)
		|| !Root->TryGetArrayField(TEXT("ring_distance_m"), Rings) || !(*Heights)->TryGetArrayField(TEXT("shape"), Shape) || Shape->Num() != 2)
	{
		OutError = FString::Printf(TEXT("%s lacks azimuth, ring_distance_m or heights"), *MetaPath);
		return false;
	}
	OutGrid.SiteId = Root->GetStringField(TEXT("site_id"));
	OutGrid.PackageId = Root->GetStringField(TEXT("package_id"));
	OutGrid.ReferenceRadiusM = Root->GetNumberField(TEXT("reference_radius_m"));
	OutGrid.AzimuthStartDeg = (*Azimuth)->GetNumberField(TEXT("start_deg"));
	OutGrid.AzimuthStepDeg = (*Azimuth)->GetNumberField(TEXT("step_deg"));
	OutGrid.AzimuthCount = static_cast<int32>((*Azimuth)->GetNumberField(TEXT("count")));
	const TSharedPtr<FJsonObject>* Dem = nullptr;
	if (Root->TryGetObjectField(TEXT("dem"), Dem))
	{
		(*Dem)->TryGetStringField(TEXT("dem_set_id"), OutGrid.DemSetId);
	}
	for (const TSharedPtr<FJsonValue>& Ring : *Rings)
	{
		if (OutGrid.RingDistanceM.Num() > 0 && !(Ring->AsNumber() > OutGrid.RingDistanceM.Last()))
		{
			OutError = FString::Printf(TEXT("%s: ring distances are not increasing"), *MetaPath);
			return false;
		}
		OutGrid.RingDistanceM.Add(Ring->AsNumber());
	}
	const int32 NumRings = OutGrid.RingDistanceM.Num();
	// 64-bit heights since the horizon search of a package can start 5 m from the site: a 32-bit
	// height of several kilometres is known to half a millimetre only, which at 5 m is 0.006 deg.
	// Older caches hold 32-bit values and are still read.
	const FString DType = (*Heights)->GetStringField(TEXT("dtype"));
	const bool bDouble = DType == TEXT("<f8");
	const int64 ValueSize = bDouble ? sizeof(double) : sizeof(float);
	if ((!bDouble && DType != TEXT("<f4")) || static_cast<int32>((*Shape)[0]->AsNumber()) != OutGrid.AzimuthCount
		|| static_cast<int32>((*Shape)[1]->AsNumber()) != NumRings || OutGrid.AzimuthCount <= 0 || NumRings <= 0)
	{
		OutError = FString::Printf(TEXT("%s: heights must be <f8 or <f4 with shape [azimuths, rings]"), *MetaPath);
		return false;
	}
	const FString DataPath = FPaths::Combine(Directory, (*Heights)->GetStringField(TEXT("file")));
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *DataPath) || Bytes.Num() != static_cast<int64>(OutGrid.AzimuthCount) * NumRings * ValueSize)
	{
		OutError = FString::Printf(TEXT("%s is missing or does not hold %d x %d values of type %s"), *DataPath, OutGrid.AzimuthCount, NumRings, *DType);
		return false;
	}
	OutGrid.HeightsM.SetNumUninitialized(OutGrid.AzimuthCount * NumRings);
	if (bDouble)
	{
		FMemory::Memcpy(OutGrid.HeightsM.GetData(), Bytes.GetData(), Bytes.Num());
	}
	else
	{
		const float* Values = reinterpret_cast<const float*>(Bytes.GetData());
		for (int32 Index = 0; Index < OutGrid.HeightsM.Num(); ++Index)
		{
			OutGrid.HeightsM[Index] = Values[Index];
		}
	}
	return true;
}

bool FLsnTerrainGrid::LoadForSite(const FString& InSiteId, FLsnTerrainGrid& OutGrid, FString& OutError)
{
	// -LsnTerrainRoot=<folder>: another folder of terrain samples (for previews made with export_terrain.py --out).
	FString Root = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("LsnTerrain"));
	FParse::Value(FCommandLine::Get(), TEXT("LsnTerrainRoot="), Root);
	return Load(FPaths::ConvertRelativePathToFull(FPaths::Combine(Root, InSiteId)), OutGrid, OutError);
}

bool FLsnTerrainGrid::Matches(const FLsnSitePackage& Package, FString& OutError) const
{
	if (PackageId != Package.PackageId)
	{
		OutError = FString::Printf(TEXT("the terrain grid was sampled for package %s, not for %s"), *PackageId, *Package.PackageId);
		return false;
	}
	if (FMath::Abs(ReferenceRadiusM - Package.ReferenceRadiusM) > 1e-6)
	{
		OutError = TEXT("the terrain grid and the package use different reference spheres");
		return false;
	}
	if (AzimuthCount != Package.AzimuthCount || FMath::Abs(AzimuthStepDeg - Package.AzimuthStepDeg) > 1e-12 || FMath::Abs(AzimuthStartDeg - Package.AzimuthStartDeg) > 1e-12)
	{
		OutError = TEXT("the terrain grid and the package have different azimuth samples");
		return false;
	}
	if (HeightsM.Num() != AzimuthCount * RingDistanceM.Num() || RingDistanceM.Num() == 0)
	{
		OutError = TEXT("the terrain grid is empty or incomplete");
		return false;
	}
	return true;
}
