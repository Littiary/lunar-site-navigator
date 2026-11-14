#include "LsnTerrain.h"

#include "LsnFrame.h"
#include "LsnPackage.h"

namespace
{
	constexpr double DegToRad = UE_DOUBLE_PI / 180.0;

	// Shape of the fill of the stand-in patch. These are drawing choices, not data.
	const double InnerFractions[] = { 0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0 };
	const double OuterFractions[] = { 1.05, 1.15, 1.3 };
	constexpr double InnerSagDeg = 1.5;   // how far the fill sinks below the line of sight near the site
	constexpr double OuterDropDeg = 3.0;  // how far the fill has dropped at 1.3 times the ridge distance

	/** Face normal as the engine derives it from the winding (KismetProceduralMeshLibrary). */
	FVector FaceNormal(const FVector& P0, const FVector& P1, const FVector& P2)
	{
		return FVector::CrossProduct(P1 - P2, P0 - P2);
	}

	/** Adds a triangle, wound so that its front faces along Outward. */
	void AddTriangle(FLsnMeshData& Mesh, int32 A, int32 B, int32 C, const FVector& Outward)
	{
		if (FVector::DotProduct(FaceNormal(Mesh.Vertices[A], Mesh.Vertices[B], Mesh.Vertices[C]), Outward) < 0.0)
		{
			Swap(B, C);
		}
		Mesh.Triangles.Add(A);
		Mesh.Triangles.Add(B);
		Mesh.Triangles.Add(C);
	}

	void ComputeSmoothNormals(FLsnMeshData& Mesh)
	{
		Mesh.Normals.Init(FVector::ZeroVector, Mesh.Vertices.Num());
		for (int32 T = 0; T + 2 < Mesh.Triangles.Num(); T += 3)
		{
			const int32 A = Mesh.Triangles[T], B = Mesh.Triangles[T + 1], C = Mesh.Triangles[T + 2];
			const FVector N = FaceNormal(Mesh.Vertices[A], Mesh.Vertices[B], Mesh.Vertices[C]);
			Mesh.Normals[A] += N;
			Mesh.Normals[B] += N;
			Mesh.Normals[C] += N;
		}
		for (FVector& N : Mesh.Normals)
		{
			N = N.GetSafeNormal(UE_DOUBLE_SMALL_NUMBER, FVector::UpVector);
		}
	}
}

void FLsnMeshData::QuantizeToFloat()
{
	for (FVector& V : Vertices)
	{
		V = FVector(FVector3f(V));
	}
}

FVector LsnTerrain::ObstacleEnuM(const FLsnSitePackage& Package, int32 HeightIndex, int32 AzimuthIndex)
{
	const int32 I = HeightIndex * Package.AzimuthCount + AzimuthIndex;
	const FVector Dir = LsnFrame::LatLonToBodyFixedDir(Package.ObstacleLatDeg[I], Package.ObstacleLonDeg[I]);
	const double RadiusKm = (Package.ReferenceRadiusM + Package.ObstacleHeightM[I]) / 1000.0;
	return Package.Frame.BodyFixedKmToEnuM(Dir * RadiusKm);
}

bool LsnTerrain::BuildHorizonPatch(const FLsnSitePackage& Package, int32 HeightIndex, FLsnMeshData& Out)
{
	Out = FLsnMeshData();
	if (!Package.bHasObstaclePoints || !Package.ObserverHeightsM.IsValidIndex(HeightIndex))
	{
		return false;
	}
	const int32 NumAz = Package.AzimuthCount;
	const int32 NumInner = UE_ARRAY_COUNT(InnerFractions);
	const int32 NumOuter = UE_ARRAY_COUNT(OuterFractions);
	const int32 NumRings = NumInner + NumOuter + 1;  // + skirt down to the reference sphere

	Out.Vertices.Reserve(1 + NumAz * NumRings);
	Out.Vertices.Add(FVector::ZeroVector);  // the ground point of the site
	Out.UV0.Add(FVector2D(0.5, 0.5));

	for (int32 A = 0; A < NumAz; ++A)
	{
		const FVector Ridge = ObstacleEnuM(Package, HeightIndex, A);
		const double RidgeDistance = FMath::Max(FMath::Sqrt(Ridge.X * Ridge.X + Ridge.Y * Ridge.Y), 1.0);
		const FVector2D Heading(Ridge.X / RidgeDistance, Ridge.Y / RidgeDistance);
		const double RidgeElevation = FMath::Atan2(Ridge.Z, RidgeDistance);

		auto AddVertex = [&](double Distance, double Elevation)
		{
			const FVector Enu(Heading.X * Distance, Heading.Y * Distance, Distance * FMath::Tan(Elevation));
			Out.Vertices.Add(LsnFrame::EnuMToWorldCm(Enu));
			Out.UV0.Add(FVector2D(0.5 + 0.5 * Enu.X / Package.MaxRangeM, 0.5 - 0.5 * Enu.Y / Package.MaxRangeM));
		};

		for (int32 J = 0; J < NumInner; ++J)
		{
			const double S = InnerFractions[J];
			if (J == NumInner - 1)
			{
				Out.Vertices.Add(LsnFrame::EnuMToWorldCm(Ridge));  // exactly the obstacle point
				Out.UV0.Add(FVector2D(0.5 + 0.5 * Ridge.X / Package.MaxRangeM, 0.5 - 0.5 * Ridge.Y / Package.MaxRangeM));
			}
			else
			{
				AddVertex(S * RidgeDistance, RidgeElevation - InnerSagDeg * DegToRad * FMath::Square(1.0 - S));
			}
		}
		for (int32 J = 0; J < NumOuter; ++J)
		{
			const double S = OuterFractions[J];
			AddVertex(S * RidgeDistance, RidgeElevation - OuterDropDeg * DegToRad * (S - 1.0) / 0.3);
		}
		// Skirt: meets the reference sphere at the search radius, where the sphere mesh starts.
		const double SkirtDistance = FMath::Max(Package.MaxRangeM, 1.5 * RidgeDistance);
		const double SphereUp = FMath::Sqrt(FMath::Max(FMath::Square(Package.ReferenceRadiusM) - FMath::Square(SkirtDistance), 0.0)) - Package.RadiusM;
		const double SkirtElevation = FMath::Min(FMath::Atan2(SphereUp, SkirtDistance), RidgeElevation - (OuterDropDeg + 1.0) * DegToRad);
		AddVertex(SkirtDistance, SkirtElevation);
	}

	auto Index = [NumAz, NumRings](int32 A, int32 Ring) { return 1 + (A % NumAz) * NumRings + Ring; };
	const FVector Up = FVector::UpVector;
	Out.Triangles.Reserve(NumAz * (1 + 2 * (NumRings - 1)) * 3);
	for (int32 A = 0; A < NumAz; ++A)
	{
		AddTriangle(Out, 0, Index(A, 0), Index(A + 1, 0), Up);
		for (int32 Ring = 0; Ring + 1 < NumRings; ++Ring)
		{
			AddTriangle(Out, Index(A, Ring), Index(A, Ring + 1), Index(A + 1, Ring + 1), Up);
			AddTriangle(Out, Index(A, Ring), Index(A + 1, Ring + 1), Index(A + 1, Ring), Up);
		}
	}
	ComputeSmoothNormals(Out);
	return true;
}

void LsnTerrain::BuildReferenceSphere(const FLsnSitePackage& Package, FLsnMeshData& Out, FVector& OutCentreWorldCm)
{
	Out = FLsnMeshData();
	OutCentreWorldCm = LsnFrame::EnuMToWorldCm(FVector(0.0, 0.0, -Package.RadiusM));

	// Polar grid about the site's up axis. The cap inside the search radius is left open.
	const int32 NumRings = 180;
	const int32 NumSegments = 360;
	const double Radius = Package.ReferenceRadiusM;
	const double StartColatitude = FMath::Asin(FMath::Clamp(Package.MaxRangeM / Radius, 0.0, 1.0));

	for (int32 Ring = 0; Ring <= NumRings; ++Ring)
	{
		const double Colatitude = StartColatitude + (UE_DOUBLE_PI - StartColatitude) * Ring / NumRings;
		for (int32 Segment = 0; Segment <= NumSegments; ++Segment)
		{
			const double Az = 2.0 * UE_DOUBLE_PI * Segment / NumSegments;
			const FVector Dir(FMath::Sin(Colatitude) * FMath::Sin(Az), FMath::Sin(Colatitude) * FMath::Cos(Az), FMath::Cos(Colatitude));
			Out.Vertices.Add(LsnFrame::EnuMToWorldCm(Dir * Radius));
			Out.Normals.Add(LsnFrame::EnuToWorld(Dir));
			Out.UV0.Add(FVector2D(static_cast<double>(Segment) / NumSegments, static_cast<double>(Ring) / NumRings));
		}
	}
	const int32 Stride = NumSegments + 1;
	for (int32 Ring = 0; Ring < NumRings; ++Ring)
	{
		for (int32 Segment = 0; Segment < NumSegments; ++Segment)
		{
			const int32 A = Ring * Stride + Segment, B = A + 1, C = A + Stride, D = C + 1;
			const FVector Outward = Out.Vertices[A] + Out.Vertices[D];
			AddTriangle(Out, A, C, D, Outward);
			if (Ring + 1 < NumRings)  // the last ring collapses to the antipode
			{
				AddTriangle(Out, A, D, B, Outward);
			}
		}
	}
}

void LsnTerrain::BuildDisc(int32 Segments, FLsnMeshData& Out)
{
	Out = FLsnMeshData();
	Out.Vertices.Add(FVector::ZeroVector);
	for (int32 I = 0; I < Segments; ++I)
	{
		const double Angle = 2.0 * UE_DOUBLE_PI * I / Segments;
		Out.Vertices.Add(FVector(0.0, FMath::Cos(Angle), FMath::Sin(Angle)));
	}
	for (int32 I = 0; I < Segments; ++I)
	{
		const int32 A = 1 + I, B = 1 + (I + 1) % Segments;
		Out.Triangles.Append({ 0, A, B, 0, B, A });  // both windings: visible from both sides
	}
	Out.Normals.Init(FVector(-1.0, 0.0, 0.0), Out.Vertices.Num());
	Out.UV0.Init(FVector2D(0.5, 0.5), Out.Vertices.Num());
}

double LsnTerrain::SilhouetteElevationDeg(const FLsnMeshData& Mesh, const FVector& ObserverWorldCm, double AzDeg)
{
	const double Az = AzDeg * DegToRad;
	const double SinAz = FMath::Sin(Az), CosAz = FMath::Cos(Az);

	// Per vertex, relative to the observer: Forward along the azimuth, Side across it, Up.
	struct FLocal { double Forward, Side, Up; };
	TArray<FLocal> Local;
	Local.SetNumUninitialized(Mesh.Vertices.Num());
	for (int32 I = 0; I < Mesh.Vertices.Num(); ++I)
	{
		const FVector Enu = LsnFrame::WorldToEnu(Mesh.Vertices[I] - ObserverWorldCm);
		Local[I] = { Enu.X * SinAz + Enu.Y * CosAz, Enu.X * CosAz - Enu.Y * SinAz, Enu.Z };
	}

	// The largest elevation on a straight edge seen from a point off the edge is at an end
	// point, so only the points where edges cross the half-plane need to be looked at.
	double BestTan = -TNumericLimits<double>::Max();
	bool bFound = false;
	auto Consider = [&](double Forward, double Up)
	{
		if (Forward > 0.0)
		{
			BestTan = FMath::Max(BestTan, Up / Forward);
			bFound = true;
		}
	};
	for (int32 T = 0; T + 2 < Mesh.Triangles.Num(); T += 3)
	{
		for (int32 E = 0; E < 3; ++E)
		{
			const FLocal& P = Local[Mesh.Triangles[T + E]];
			const FLocal& Q = Local[Mesh.Triangles[T + (E + 1) % 3]];
			if (P.Side == 0.0)
			{
				Consider(P.Forward, P.Up);
			}
			else if (Q.Side != 0.0 && (P.Side < 0.0) != (Q.Side < 0.0))
			{
				const double K = P.Side / (P.Side - Q.Side);
				Consider(P.Forward + K * (Q.Forward - P.Forward), P.Up + K * (Q.Up - P.Up));
			}
		}
	}
	return bFound ? FMath::Atan(BestTan) / DegToRad : -90.0;
}
