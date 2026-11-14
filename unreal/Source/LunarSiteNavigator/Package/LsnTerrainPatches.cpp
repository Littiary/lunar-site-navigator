#include "Package/LsnTerrainPatches.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

bool FLsnTerrainPatch::UpAt(double EastM, double NorthM, double& OutUpM) const
{
	if (!(SpacingM > 0.0) || CountEast < 2 || CountNorth < 2)
	{
		return false;
	}
	const double X = (EastM - EastMinM) / SpacingM, Y = (NorthM - NorthMinM) / SpacingM;
	if (X < 0.0 || Y < 0.0 || X > CountEast - 1 || Y > CountNorth - 1)
	{
		return false;
	}
	const int32 J = FMath::Min(FMath::FloorToInt32(X), CountEast - 2), I = FMath::Min(FMath::FloorToInt32(Y), CountNorth - 2);
	const double U = X - J, V = Y - I;
	const float A = UpM[I * CountEast + J], B = UpM[I * CountEast + J + 1], C = UpM[(I + 1) * CountEast + J], D = UpM[(I + 1) * CountEast + J + 1];
	if (FMath::IsNaN(A) || FMath::IsNaN(B) || FMath::IsNaN(C) || FMath::IsNaN(D))
	{
		return false;
	}
	OutUpM = (1.0 - V) * ((1.0 - U) * A + U * B) + V * ((1.0 - U) * C + U * D);
	return true;
}

bool LsnPackageIO::LoadTerrainPatches(const FString& PackageDirectory, TArray<FLsnTerrainPatch>& OutPatches, FString& OutError)
{
	OutPatches.Reset();
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(PackageDirectory, TEXT("manifest.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		OutError = TEXT("the manifest cannot be read");
		return false;
	}
	const TSharedPtr<FJsonObject>* Terrain = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* Patches = nullptr;
	if (!Root->TryGetObjectField(TEXT("terrain"), Terrain) || !Terrain || !(*Terrain)->TryGetArrayField(TEXT("patches"), Patches) || !Patches || Patches->Num() == 0)
	{
		OutError = TEXT("the package has no terrain patches");
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *Patches)
	{
		const TSharedPtr<FJsonObject>* Object = nullptr;
		const TSharedPtr<FJsonObject>* Ref = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object || !(*Object)->TryGetObjectField(TEXT("up_m"), Ref) || !Ref)
		{
			OutError = TEXT("a terrain patch has no heights");
			return false;
		}
		FLsnTerrainPatch Patch;
		double CountEast = 0.0, CountNorth = 0.0;
		FString File, DType;
		if (!(*Object)->TryGetStringField(TEXT("id"), Patch.Id) || !(*Object)->TryGetNumberField(TEXT("spacing_m"), Patch.SpacingM) || !(*Object)->TryGetNumberField(TEXT("half_width_m"), Patch.HalfWidthM)
			|| !(*Object)->TryGetNumberField(TEXT("east_min_m"), Patch.EastMinM) || !(*Object)->TryGetNumberField(TEXT("north_min_m"), Patch.NorthMinM)
			|| !(*Object)->TryGetNumberField(TEXT("count_east"), CountEast) || !(*Object)->TryGetNumberField(TEXT("count_north"), CountNorth)
			|| !(*Ref)->TryGetStringField(TEXT("file"), File) || !(*Ref)->TryGetStringField(TEXT("dtype"), DType))
		{
			OutError = FString::Printf(TEXT("terrain patch '%s' lacks a field of SPEC 5.9"), *Patch.Id);
			return false;
		}
		Patch.CountEast = static_cast<int32>(CountEast);
		Patch.CountNorth = static_cast<int32>(CountNorth);
		if (DType != TEXT("<f4") || !(Patch.SpacingM > 0.0) || Patch.CountEast < 2 || Patch.CountNorth < 2 || File.Contains(TEXT("/")) || File.Contains(TEXT("\\")) || File.Contains(TEXT("..")))
		{
			OutError = FString::Printf(TEXT("terrain patch '%s' is not a float32 grid in the package"), *Patch.Id);
			return false;
		}
		TArray<uint8> Bytes;
		const int64 Expected = static_cast<int64>(Patch.CountEast) * Patch.CountNorth * static_cast<int64>(sizeof(float));
		if (!FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(PackageDirectory, File)) || Bytes.Num() != Expected)
		{
			OutError = FString::Printf(TEXT("%s is missing or does not hold %d x %d 32-bit values"), *File, Patch.CountNorth, Patch.CountEast);
			return false;
		}
		Patch.UpM.SetNumUninitialized(Patch.CountEast * Patch.CountNorth);
		FMemory::Memcpy(Patch.UpM.GetData(), Bytes.GetData(), Bytes.Num());
		OutPatches.Add(MoveTemp(Patch));
	}
	return true;
}
