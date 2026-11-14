#include "Mesh/LsnProps.h"

#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FString LsnProps::ModelDirectory()
{
	return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("LsnModels")));
}

FColor LsnProps::MaterialColor(const FString& MaterialName)
{
	// Reflectances chosen by eye for the drawing; no measured values.
	if (MaterialName.EndsWith(TEXT("foil"))) { return FLinearColor(0.42f, 0.30f, 0.10f).ToFColor(false); }
	if (MaterialName.EndsWith(TEXT("metal"))) { return FLinearColor(0.55f, 0.55f, 0.57f).ToFColor(false); }
	if (MaterialName.EndsWith(TEXT("dark"))) { return FLinearColor(0.06f, 0.06f, 0.06f).ToFColor(false); }
	if (MaterialName.EndsWith(TEXT("panel"))) { return FLinearColor(0.03f, 0.05f, 0.12f).ToFColor(false); }
	return FLinearColor(0.28f, 0.28f, 0.27f).ToFColor(false);  // rock: fresh rock is brighter than the regolith around it
}

bool LsnProps::LoadObj(const FString& File, FLsnMeshData& OutMesh, FString& OutError)
{
	OutMesh = FLsnMeshData();
	TArray<FString> Lines;
	if (!FFileHelper::LoadFileToStringArray(Lines, *File))
	{
		OutError = FString::Printf(TEXT("cannot read %s"), *File);
		return false;
	}
	TArray<FVector> Points, Normals;
	FColor Color = MaterialColor(TEXT("rock"));
	for (const FString& Line : Lines)
	{
		TArray<FString> Parts;
		Line.ParseIntoArrayWS(Parts);
		if (Parts.Num() == 0)
		{
			continue;
		}
		if (Parts[0] == TEXT("v") && Parts.Num() >= 4)
		{
			// Metres to centimetres; Y mirrored (right-handed to left-handed).
			Points.Add(FVector(FCString::Atod(*Parts[1]), -FCString::Atod(*Parts[2]), FCString::Atod(*Parts[3])) * 100.0);
		}
		else if (Parts[0] == TEXT("vn") && Parts.Num() >= 4)
		{
			Normals.Add(FVector(FCString::Atod(*Parts[1]), -FCString::Atod(*Parts[2]), FCString::Atod(*Parts[3])).GetSafeNormal());
		}
		else if (Parts[0] == TEXT("usemtl") && Parts.Num() >= 2)
		{
			Color = MaterialColor(Parts[1]);
		}
		else if (Parts[0] == TEXT("f"))
		{
			if (Parts.Num() != 4)
			{
				OutError = FString::Printf(TEXT("%s: a face is not a triangle"), *File);
				return false;
			}
			int32 Corner[3];
			FVector FaceNormal = FVector::ZeroVector;
			for (int32 I = 0; I < 3; ++I)
			{
				// "v", "v/t", "v//n" or "v/t/n"; indices count from 1.
				TArray<FString> Indices;
				Parts[I + 1].ParseIntoArray(Indices, TEXT("/"), false);
				const int32 PointIndex = FCString::Atoi(*Indices[0]) - 1;
				const int32 NormalIndex = Indices.Num() >= 3 ? FCString::Atoi(*Indices[2]) - 1 : -1;
				if (!Points.IsValidIndex(PointIndex))
				{
					OutError = FString::Printf(TEXT("%s: a face names a point that is not there"), *File);
					return false;
				}
				Corner[I] = OutMesh.Positions.Add(Points[PointIndex]);
				OutMesh.Normals.Add(Normals.IsValidIndex(NormalIndex) ? Normals[NormalIndex] : FVector::ZeroVector);
				OutMesh.Colors.Add(Color);
				OutMesh.UV0.Add(FVector2D::ZeroVector);
				FaceNormal += OutMesh.Normals.Last();
			}
			if (FaceNormal.IsNearlyZero())
			{
				// No normals in the file: the face's own, by the order of its corners (mirrored with Y).
				FaceNormal = FVector::CrossProduct(OutMesh.Positions[Corner[2]] - OutMesh.Positions[Corner[0]], OutMesh.Positions[Corner[1]] - OutMesh.Positions[Corner[0]]).GetSafeNormal();
				for (const int32 C : Corner)
				{
					OutMesh.Normals[C] = FaceNormal;
				}
			}
			OutMesh.AddTriangleFacing(Corner[0], Corner[1], Corner[2], FaceNormal);
		}
	}
	if (OutMesh.Triangles.Num() == 0)
	{
		OutError = FString::Printf(TEXT("%s has no faces"), *File);
		return false;
	}
	return true;
}

void LsnProps::Append(const FLsnMeshData& Source, const FVector& Scale, double YawDeg, const FVector& Location, FLsnMeshData& InOutMesh)
{
	const FQuat Turn(FVector::UpVector, FMath::DegreesToRadians(YawDeg));
	const int32 Base = InOutMesh.Positions.Num();
	for (int32 I = 0; I < Source.Positions.Num(); ++I)
	{
		InOutMesh.Positions.Add(Location + Turn.RotateVector(Source.Positions[I] * Scale));
		// A normal under a stretch: divided by the scale, then made a unit vector again.
		InOutMesh.Normals.Add(Turn.RotateVector((Source.Normals[I] / Scale).GetSafeNormal()));
		InOutMesh.Colors.Add(Source.Colors[I]);
		InOutMesh.UV0.Add(FVector2D::ZeroVector);
	}
	for (const int32 Index : Source.Triangles)
	{
		InOutMesh.Triangles.Add(Base + Index);
	}
}

bool LsnProps::BuildMast(double ObserverHeightM, FLsnMeshData& OutMesh, FString& OutError)
{
	OutMesh = FLsnMeshData();
	FLsnMeshData Base, Pole, Head;
	const FString Directory = ModelDirectory();
	if (!LoadObj(FPaths::Combine(Directory, TEXT("mast_base.obj")), Base, OutError) || !LoadObj(FPaths::Combine(Directory, TEXT("mast_pole.obj")), Pole, OutError)
		|| !LoadObj(FPaths::Combine(Directory, TEXT("mast_head.obj")), Head, OutError))
	{
		return false;
	}
	const double BaseTopM = 0.70;
	if (ObserverHeightM >= 1.0)
	{
		Append(Base, FVector::OneVector, 0.0, FVector::ZeroVector, OutMesh);
		// The pole file is 1 m long: stretched from the top of the base to the head.
		Append(Pole, FVector(1.0, 1.0, ObserverHeightM - BaseTopM), 0.0, FVector(0.0, 0.0, BaseTopM * 100.0), OutMesh);
	}
	Append(Head, FVector::OneVector, 0.0, FVector(0.0, 0.0, FMath::Max(ObserverHeightM, 0.08) * 100.0), OutMesh);
	return true;
}
