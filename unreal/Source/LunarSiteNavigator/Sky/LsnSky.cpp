#include "Sky/LsnSky.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Package/LsnPackage.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	bool LoadJson(const FString& File, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *File))
		{
			OutError = FString::Printf(TEXT("cannot read %s"), *File);
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		if (!FJsonSerializer::Deserialize(Reader, OutObject) || !OutObject.IsValid())
		{
			OutError = FString::Printf(TEXT("%s is not JSON"), *File);
			return false;
		}
		return true;
	}

	FString SkyDirectory()
	{
		return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("LsnSky")));
	}
}

bool FLsnStarCatalogue::Load(FLsnStarCatalogue& OutCatalogue, FString& OutError)
{
	return LoadFrom(SkyDirectory(), OutCatalogue, OutError);
}

bool FLsnStarCatalogue::LoadFrom(const FString& Directory, FLsnStarCatalogue& OutCatalogue, FString& OutError)
{
	OutCatalogue = FLsnStarCatalogue();
	TSharedPtr<FJsonObject> Json;
	if (!LoadJson(FPaths::Combine(Directory, TEXT("stars.json")), Json, OutError))
	{
		return false;
	}
	const int32 Count = Json->GetIntegerField(TEXT("count"));
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(Directory, Json->GetStringField(TEXT("file")))) || Bytes.Num() != Count * 5 * static_cast<int32>(sizeof(float)))
	{
		OutError = TEXT("the star array is missing or has the wrong size");
		return false;
	}
	const float* Values = reinterpret_cast<const float*>(Bytes.GetData());
	OutCatalogue.Stars.Reserve(Count);
	for (int32 I = 0; I < Count; ++I)
	{
		FLsnStar Star;
		Star.DirectionJ2000 = FVector(Values[5 * I], Values[5 * I + 1], Values[5 * I + 2]).GetSafeNormal();
		Star.VisualMagnitude = Values[5 * I + 3];
		Star.ColourIndex = Values[5 * I + 4];
		OutCatalogue.Stars.Add(Star);
	}
	OutCatalogue.Source = Json->GetStringField(TEXT("source"));
	return true;
}

bool FLsnSkyOrientation::LoadForSite(const FString& InSiteId, FLsnSkyOrientation& OutSky, FString& OutError)
{
	return Load(FPaths::Combine(SkyDirectory(), InSiteId), OutSky, OutError);
}

bool FLsnSkyOrientation::Load(const FString& Directory, FLsnSkyOrientation& OutSky, FString& OutError)
{
	OutSky = FLsnSkyOrientation();
	TSharedPtr<FJsonObject> Json;
	if (!LoadJson(FPaths::Combine(Directory, TEXT("orientation.json")), Json, OutError))
	{
		return false;
	}
	OutSky.SiteId = Json->GetStringField(TEXT("site_id"));
	OutSky.PackageId = Json->GetStringField(TEXT("package_id"));
	OutSky.StartEtS = Json->GetNumberField(TEXT("start_et_s"));
	OutSky.StepS = Json->GetNumberField(TEXT("step_s"));
	const int32 Count = Json->GetIntegerField(TEXT("count"));
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(Directory, Json->GetStringField(TEXT("file")))) || Bytes.Num() != Count * 9 * static_cast<int32>(sizeof(double))
		|| Count < 2 || !(OutSky.StepS > 0.0))
	{
		OutError = TEXT("the orientation array is missing or has the wrong size");
		return false;
	}
	const double* Values = reinterpret_cast<const double*>(Bytes.GetData());
	for (int32 I = 0; I < Count; ++I)
	{
		OutSky.East.Add(FVector(Values[9 * I], Values[9 * I + 1], Values[9 * I + 2]));
		OutSky.North.Add(FVector(Values[9 * I + 3], Values[9 * I + 4], Values[9 * I + 5]));
		OutSky.Up.Add(FVector(Values[9 * I + 6], Values[9 * I + 7], Values[9 * I + 8]));
	}
	const TArray<TSharedPtr<FJsonValue>>* Checks = nullptr;
	if (Json->TryGetArrayField(TEXT("check"), Checks))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Checks)
		{
			const TSharedPtr<FJsonObject> Entry = Value->AsObject();
			const TArray<TSharedPtr<FJsonValue>>& Sun = Entry->GetArrayField(TEXT("sun_j2000"));
			if (Sun.Num() == 3)
			{
				OutSky.Checks.Add({ static_cast<int32>(Entry->GetIntegerField(TEXT("sample"))), Entry->GetNumberField(TEXT("et_s")), FVector(Sun[0]->AsNumber(), Sun[1]->AsNumber(), Sun[2]->AsNumber()) });
			}
		}
	}
	return true;
}

bool FLsnSkyOrientation::Matches(const FLsnSitePackage& Package, FString& OutError) const
{
	if (PackageId != Package.PackageId)
	{
		OutError = FString::Printf(TEXT("the sky orientation was exported for package %s, not %s"), *PackageId, *Package.PackageId);
		return false;
	}
	return true;
}

FVector FLsnSkyOrientation::UnrealDirectionAtIndex(int32 Index, const FVector& DirectionJ2000) const
{
	// Unreal: +X north, +Y east, +Z up.
	return FVector(FVector::DotProduct(North[Index], DirectionJ2000), FVector::DotProduct(East[Index], DirectionJ2000), FVector::DotProduct(Up[Index], DirectionJ2000));
}

bool FLsnSkyOrientation::MeshRotationAt(double EtS, FQuat& OutRotation) const
{
	const double Position = (EtS - StartEtS) / StepS;
	if (Num() < 2 || Position < 0.0 || Position > Num() - 1)
	{
		return false;
	}
	const int32 I0 = FMath::Min(static_cast<int32>(FMath::FloorToDouble(Position)), Num() - 2);
	auto RotationAtIndex = [this](int32 I)
	{
		// The mesh holds (x, y, -z) of each J2000 direction. Images of the mesh's axes in Unreal axes:
		// J2000 X and Y as they are, J2000 Z negated. With the mirror on both sides this is a turn.
		const FVector ImageX = UnrealDirectionAtIndex(I, FVector(1.0, 0.0, 0.0));
		const FVector ImageY = UnrealDirectionAtIndex(I, FVector(0.0, 1.0, 0.0));
		const FVector ImageZ = -UnrealDirectionAtIndex(I, FVector(0.0, 0.0, 1.0));
		return FQuat(FMatrix(ImageX, ImageY, ImageZ, FVector::ZeroVector)).GetNormalized();
	};
	OutRotation = FQuat::Slerp(RotationAtIndex(I0), RotationAtIndex(I0 + 1), Position - I0).GetNormalized();
	return true;
}

float LsnSky::DisplayBrightness(float VisualMagnitude)
{
	// Flux falls by a factor of 100 over five magnitudes; the square root of it is drawn, so
	// that faint stars stay visible beside bright ones on a display. Magnitude -1.5 gives 1.
	return FMath::Clamp(FMath::Pow(10.0f, -0.2f * (VisualMagnitude + 1.5f)), 0.0f, 1.0f);
}

double LsnSky::DotHalfSizeDeg(float VisualMagnitude)
{
	return 0.035 + 0.075 * FMath::Clamp((6.5 - VisualMagnitude) / 8.0, 0.0, 1.0);
}

FLinearColor LsnSky::Tint(float ColourIndex)
{
	if (FMath::IsNaN(ColourIndex))
	{
		return FLinearColor::White;
	}
	// B-V of -0.3 (blue) to 1.8 (red), white near 0.6.
	const float T = FMath::Clamp((ColourIndex + 0.3f) / 2.1f, 0.0f, 1.0f);
	return FLinearColor(FMath::Lerp(0.72f, 1.0f, FMath::Clamp(T * 2.4f, 0.0f, 1.0f)), FMath::Lerp(0.82f, 0.78f, T) + 0.18f * (1.0f - FMath::Abs(2.0f * T - 0.85f)), FMath::Lerp(1.0f, 0.55f, T));
}

FVector LsnSky::MeshDirection(const FVector& DirectionJ2000, const FQuat& Rotation)
{
	return Rotation.RotateVector(FVector(DirectionJ2000.X, DirectionJ2000.Y, -DirectionJ2000.Z));
}

void LsnSky::BuildStarMesh(const FLsnStarCatalogue& Catalogue, double RadiusCm, FLsnMeshData& OutMesh)
{
	OutMesh = FLsnMeshData();
	const int32 Count = Catalogue.Stars.Num();
	OutMesh.Positions.Reserve(4 * Count);
	OutMesh.Triangles.Reserve(6 * Count);
	for (const FLsnStar& Star : Catalogue.Stars)
	{
		const FVector Direction(Star.DirectionJ2000.X, Star.DirectionJ2000.Y, -Star.DirectionJ2000.Z);
		FVector Side, Other;
		Direction.FindBestAxisVectors(Side, Other);
		const double Half = RadiusCm * FMath::Tan(FMath::DegreesToRadians(DotHalfSizeDeg(Star.VisualMagnitude)));
		FLinearColor Colour = Tint(Star.ColourIndex);
		Colour.A = DisplayBrightness(Star.VisualMagnitude);
		const FColor Packed = Colour.ToFColor(false);
		const int32 Base = OutMesh.Positions.Num();
		static const double Corners[4][2] = { { -1.0, -1.0 }, { 1.0, -1.0 }, { 1.0, 1.0 }, { -1.0, 1.0 } };
		for (const double* Corner : Corners)
		{
			OutMesh.Positions.Add(Direction * RadiusCm + Side * (Corner[0] * Half) + Other * (Corner[1] * Half));
			OutMesh.Normals.Add(-Direction);
			OutMesh.Colors.Add(Packed);
			OutMesh.UV0.Add(FVector2D(0.5 * (Corner[0] + 1.0), 0.5 * (Corner[1] + 1.0)));
		}
		OutMesh.AddTriangleFacing(Base, Base + 1, Base + 2, -Direction);
		OutMesh.AddTriangleFacing(Base, Base + 2, Base + 3, -Direction);
	}
}
