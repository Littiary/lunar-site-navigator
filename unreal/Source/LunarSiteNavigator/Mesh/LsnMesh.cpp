#include "Mesh/LsnMesh.h"

#include "Algo/BinarySearch.h"
#include "Package/LsnPackage.h"
#include "Terrain/LsnTerrainGrid.h"

// ---------------------------------------------------------------------------
// FLsnMeshData
// ---------------------------------------------------------------------------

FVector FLsnMeshData::TriangleFacing(int32 TriangleIndex) const
{
	const FVector& A = Positions[Triangles[TriangleIndex * 3]];
	const FVector& B = Positions[Triangles[TriangleIndex * 3 + 1]];
	const FVector& C = Positions[Triangles[TriangleIndex * 3 + 2]];
	return FVector::CrossProduct(C - A, B - A);
}

void FLsnMeshData::AddTriangleFacing(int32 A, int32 B, int32 C, const FVector& TowardsDir)
{
	const FVector Facing = FVector::CrossProduct(Positions[C] - Positions[A], Positions[B] - Positions[A]);
	if (Facing.IsNearlyZero(1e-12))
	{
		return; // degenerate (for example at a pole of a latitude-longitude grid)
	}
	Triangles.Add(A);
	if (FVector::DotProduct(Facing, TowardsDir) >= 0.0)
	{
		Triangles.Add(B);
		Triangles.Add(C);
	}
	else
	{
		Triangles.Add(C);
		Triangles.Add(B);
	}
}

void FLsnMeshData::ComputeNormals()
{
	Normals.Init(FVector::ZeroVector, Positions.Num());
	for (int32 T = 0; T < NumTriangles(); ++T)
	{
		const FVector Facing = TriangleFacing(T); // length = twice the area
		Normals[Triangles[T * 3]] += Facing;
		Normals[Triangles[T * 3 + 1]] += Facing;
		Normals[Triangles[T * 3 + 2]] += Facing;
	}
	for (FVector& Normal : Normals)
	{
		if (!Normal.Normalize(1e-30))
		{
			Normal = FVector::UpVector;
		}
	}
}

void FLsnMeshData::RoundPositionsToFloat()
{
	for (FVector& Position : Positions)
	{
		Position = FVector(FVector3f(Position));
	}
}

// ---------------------------------------------------------------------------
// Horizon terrain
// ---------------------------------------------------------------------------

bool LsnMesh::HorizonPointUnreal(const FLsnSiteFrame& Frame, double EyeHeightM, double AzimuthDeg, double HorizonElevationDeg,
	double HorizonDistanceM, FVector& OutPointUnreal)
{
	if (FMath::IsNaN(HorizonElevationDeg) || FMath::IsNaN(HorizonDistanceM) || !(HorizonDistanceM > 0.0) || !(Frame.SphereRadiusM > 0.0))
	{
		return false;
	}
	// In the vertical plane of this azimuth, with the Moon's centre at the origin:
	//   eye   = (0, EyeRadius)
	//   point = Rho * (sin(gamma), cos(gamma)),  gamma = arc distance / sphere radius
	//   tan(elevation) = (Rho cos(gamma) - EyeRadius) / (Rho sin(gamma))
	// so Rho = EyeRadius / (cos(gamma) - tan(elevation) sin(gamma)).
	const double EyeRadiusM = Frame.OriginRadiusM() + EyeHeightM;
	const double Gamma = HorizonDistanceM / Frame.SphereRadiusM;
	const double TanEl = FMath::Tan(FMath::DegreesToRadians(HorizonElevationDeg));
	const double SinGamma = FMath::Sin(Gamma);
	const double Denominator = FMath::Cos(Gamma) - TanEl * SinGamma;
	if (!(Denominator > 1e-9) || !(Gamma < UE_DOUBLE_PI))
	{
		return false; // the sight line never meets that radial
	}
	// Rho - EyeRadius, written without cancellation: 1 - Denominator = 2 sin^2(gamma/2) + tan(el) sin(gamma).
	const double SinHalf = FMath::Sin(0.5 * Gamma);
	const double AboveEyeM = EyeRadiusM * (2.0 * SinHalf * SinHalf + TanEl * SinGamma) / Denominator;
	const double HeightAboveSphereM = Frame.SiteHeightM + EyeHeightM + AboveEyeM;
	OutPointUnreal = Frame.SurfacePointUnreal(AzimuthDeg, HorizonDistanceM, HeightAboveSphereM);
	return true;
}

namespace
{
	uint32 HashCell(int32 I, int32 J, uint32 ScaleIndex, uint32 Seed)
	{
		uint32 H = static_cast<uint32>(I) * 0x9E3779B1u ^ static_cast<uint32>(J) * 0x85EBCA77u ^ ScaleIndex * 0xC2B2AE3Du ^ Seed;
		H ^= H >> 15;
		H *= 0x2C1B3C6Du;
		H ^= H >> 12;
		H *= 0x297A2D39u;
		H ^= H >> 15;
		return H;
	}

	double Unit(uint32 H, uint32 Salt)
	{
		H ^= Salt * 0x9E3779B1u;
		H ^= H >> 16;
		H *= 0x7FEB352Du;
		H ^= H >> 15;
		return static_cast<double>(H & 0xFFFFFFu) / static_cast<double>(0x1000000u);
	}

	double SmoothStep01(double X)
	{
		X = FMath::Clamp(X, 0.0, 1.0);
		return X * X * (3.0 - 2.0 * X);
	}
}

double LsnMesh::CraterDepthM(double EastM, double NorthM, uint32 Seed)
{
	static const double CellSizesM[] = { 30.0, 120.0, 480.0, 1920.0 };
	double Depth = 0.0;
	for (uint32 ScaleIndex = 0; ScaleIndex < UE_ARRAY_COUNT(CellSizesM); ++ScaleIndex)
	{
		const double Cell = CellSizesM[ScaleIndex];
		const int32 I0 = FMath::FloorToInt32(EastM / Cell);
		const int32 J0 = FMath::FloorToInt32(NorthM / Cell);
		for (int32 I = I0 - 1; I <= I0 + 1; ++I)
		{
			for (int32 J = J0 - 1; J <= J0 + 1; ++J)
			{
				const uint32 H = HashCell(I, J, ScaleIndex, Seed);
				if (Unit(H, 1) > 0.55)
				{
					continue; // no crater in this cell
				}
				const double CentreE = (I + 0.2 + 0.6 * Unit(H, 2)) * Cell;
				const double CentreN = (J + 0.2 + 0.6 * Unit(H, 3)) * Cell;
				const double Radius = Cell * (0.12 + 0.20 * Unit(H, 4));
				const double DistSq = FMath::Square(EastM - CentreE) + FMath::Square(NorthM - CentreN);
				if (DistSq < Radius * Radius)
				{
					const double Bowl = 1.0 - DistSq / (Radius * Radius);
					Depth += 0.18 * Radius * Bowl * Bowl;
				}
			}
		}
	}
	return Depth;
}

namespace
{
	/**
	 * Heights of a polar terrain grid averaged over a square of half-width RadiusM, for
	 * normals only. The grid is first read onto a square raster in metres east and north
	 * of the site (averaging on the polar grid itself would wipe out a plain tilt near the
	 * site, where one ring is a small circle), then averaged twice with a running mean.
	 */
	class FSmoothedHeights
	{
	public:
		FSmoothedHeights(const TArray<double>& InHeightsM, const TArray<double>& InRingsM, int32 InNumAz, double InSiteHeightM, double RadiusM, double ExtentM)
			: HeightsM(InHeightsM), RingsM(InRingsM), NumAz(InNumAz), NumRings(InRingsM.Num()), SiteHeightM(InSiteHeightM), Extent(ExtentM + 2.0 * RadiusM)
		{
			Cell = FMath::Max(RadiusM / 4.0, 1.0);
			Size = 2 * FMath::CeilToInt32(Extent / Cell) + 1;
			Raster.SetNumUninitialized(Size * Size);
			for (int32 J = 0; J < Size; ++J)
			{
				for (int32 I = 0; I < Size; ++I)
				{
					Raster[J * Size + I] = Polar(-Extent + I * Cell, -Extent + J * Cell);
				}
			}
			const int32 Half = FMath::Max(FMath::RoundToInt32(RadiusM / Cell), 1);
			TArray<double> Line, Sum;
			for (int32 Pass = 0; Pass < 2; ++Pass)
			{
				for (int32 Axis = 0; Axis < 2; ++Axis)
				{
					Line.SetNumUninitialized(Size);
					Sum.SetNumUninitialized(Size + 1);
					for (int32 Other = 0; Other < Size; ++Other)
					{
						Sum[0] = 0.0;
						for (int32 K = 0; K < Size; ++K)
						{
							Line[K] = Raster[Axis == 0 ? Other * Size + K : K * Size + Other];
							Sum[K + 1] = Sum[K] + Line[K];
						}
						for (int32 K = 0; K < Size; ++K)
						{
							// A symmetric window, shortened equally on both sides at the edge, keeps a tilt a tilt.
							const int32 Reach = FMath::Min3(Half, K, Size - 1 - K);
							Raster[Axis == 0 ? Other * Size + K : K * Size + Other] = (Sum[K + Reach + 1] - Sum[K - Reach]) / (2 * Reach + 1);
						}
					}
				}
			}
		}

		/**
		 * Averaged height at a point east and north of the site, metres. Read with a cubic B-spline:
		 * its slope has no steps at the raster lines. Read linearly, each raster cell had its own
		 * slope, which a Sun a few degrees above the ground showed as bands of brightness.
		 */
		double At(double EastM, double NorthM) const
		{
			const double X = FMath::Clamp((EastM + Extent) / Cell, 0.0, static_cast<double>(Size - 1));
			const double Y = FMath::Clamp((NorthM + Extent) / Cell, 0.0, static_cast<double>(Size - 1));
			const int32 I = FMath::FloorToInt32(X), J = FMath::FloorToInt32(Y);
			double WeightX[4], WeightY[4];
			SplineWeights(X - I, WeightX);
			SplineWeights(Y - J, WeightY);
			double Height = 0.0;
			for (int32 B = 0; B < 4; ++B)
			{
				const int32 Row = FMath::Clamp(J + B - 1, 0, Size - 1) * Size;
				double Line = 0.0;
				for (int32 A = 0; A < 4; ++A)
				{
					Line += WeightX[A] * Raster[Row + FMath::Clamp(I + A - 1, 0, Size - 1)];
				}
				Height += WeightY[B] * Line;
			}
			return Height;
		}

	private:
		/** Weights of the uniform cubic B-spline on four neighbours, for a position T in [0, 1) between the middle two. */
		static void SplineWeights(double T, double Out[4])
		{
			const double T2 = T * T, T3 = T2 * T;
			Out[0] = (1.0 - 3.0 * T + 3.0 * T2 - T3) / 6.0;
			Out[1] = (4.0 - 6.0 * T2 + 3.0 * T3) / 6.0;
			Out[2] = (1.0 + 3.0 * T + 3.0 * T2 - 3.0 * T3) / 6.0;
			Out[3] = T3 / 6.0;
		}

		/** Height of the polar grid at a point, linear between its samples (and between the site and the first ring). */
		double Polar(double EastM, double NorthM) const
		{
			const double Distance = FMath::Sqrt(EastM * EastM + NorthM * NorthM);
			double Az = FMath::RadiansToDegrees(FMath::Atan2(EastM, NorthM));
			Az = FMath::Fmod(Az + 360.0, 360.0) * NumAz / 360.0;
			const int32 A0 = static_cast<int32>(Az) % NumAz, A1 = (A0 + 1) % NumAz;
			const double W = Az - FMath::FloorToDouble(Az);
			auto Ring = [&](int32 R) { return (1.0 - W) * HeightsM[A0 * NumRings + R] + W * HeightsM[A1 * NumRings + R]; };
			if (Distance <= RingsM[0])
			{
				const double T = Distance / RingsM[0];
				return (1.0 - T) * SiteHeightM + T * Ring(0);
			}
			int32 R1 = Algo::UpperBound(RingsM, Distance);
			if (R1 >= NumRings)
			{
				return Ring(NumRings - 1);
			}
			const double T = (Distance - RingsM[R1 - 1]) / (RingsM[R1] - RingsM[R1 - 1]);
			return (1.0 - T) * Ring(R1 - 1) + T * Ring(R1);
		}

		const TArray<double>& HeightsM;
		const TArray<double>& RingsM;
		int32 NumAz;
		int32 NumRings;
		double SiteHeightM;
		double Extent;
		double Cell = 10.0;
		int32 Size = 0;
		TArray<double> Raster;
	};
}

void LsnMesh::BuildGridTerrain(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
	const FLsnTerrainGrid& Grid, float Albedo, double NormalSmoothingM, FLsnMeshData& OutMesh, int32& OutSkippedAzimuths, int32& OutUnknownSamples)
{
	OutMesh = FLsnMeshData();
	OutSkippedAzimuths = 0;
	OutUnknownSamples = 0;

	const int32 NumAz = Package.AzimuthCount;
	const int32 NumRings = Grid.RingDistanceM.Num();
	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];

	TArray<double> DrawnHeightsM;  // [A, R], what the positions were built from
	DrawnHeightsM.Reserve(NumAz * NumRings);
	OutMesh.Positions.Reserve(1 + NumAz * NumRings);
	OutMesh.Positions.Add(FVector::ZeroVector); // the site's ground point
	for (int32 A = 0; A < NumAz; ++A)
	{
		const double Az = Package.AzimuthDegAt(A);
		FVector HorizonPoint;
		const double HorizonDistanceM = Package.HorizonDistanceAt(HeightIndex, A);
		const bool bHasHorizon = HorizonPointUnreal(Frame, EyeHeightM, Az, Package.HorizonElevationAt(HeightIndex, A), HorizonDistanceM, HorizonPoint);
		if (!bHasHorizon)
		{
			++OutSkippedAzimuths;
		}
		// The horizon point is itself a point of the terrain. It takes the place of the ring
		// sample nearest to it in distance (the rings grow by a constant factor, so nearest
		// by ratio). Every azimuth then has the same number of vertices, ring k of one
		// azimuth joins ring k of the next, and the crest of the mesh is the package horizon.
		int32 CrestRing = INDEX_NONE;
		if (bHasHorizon)
		{
			double Best = TNumericLimits<double>::Max();
			for (int32 R = 0; R < NumRings; ++R)
			{
				const double Ratio = FMath::Abs(FMath::Loge(Grid.RingDistanceM[R] / HorizonDistanceM));
				if (Ratio < Best)
				{
					Best = Ratio;
					CrestRing = R;
				}
			}
		}

		// Height to draw where the data has none: that of the nearest ring with data.
		double LastKnownHeightM = Package.SurfaceHeightM;
		for (int32 R = 0; R < NumRings; ++R)
		{
			const double HeightM = Grid.HeightsM[A * NumRings + R];
			if (FMath::IsNaN(HeightM))
			{
				++OutUnknownSamples;
			}
			else
			{
				LastKnownHeightM = HeightM;
			}
			DrawnHeightsM.Add(LastKnownHeightM);
			OutMesh.Positions.Add(R == CrestRing ? HorizonPoint : Frame.SurfacePointUnreal(Az, Grid.RingDistanceM[R], LastKnownHeightM));
		}
	}

	const uint8 Grey = static_cast<uint8>(FMath::Clamp(FMath::RoundToInt(Albedo * 255.0f), 0, 255));
	OutMesh.Colors.Init(FColor(Grey, Grey, Grey, 255), OutMesh.Positions.Num());
	OutMesh.UV0.Init(FVector2D::ZeroVector, OutMesh.Positions.Num());

	auto Index = [NumAz, NumRings](int32 A, int32 R) { return 1 + (A % NumAz) * NumRings + R; };
	const FVector Up(0.0, 0.0, 1.0);
	OutMesh.Triangles.Reserve(3 * NumAz * (2 * NumRings - 1));
	for (int32 A = 0; A < NumAz; ++A)
	{
		OutMesh.AddTriangleFacing(0, Index(A, 0), Index(A + 1, 0), Up);
		for (int32 R = 0; R + 1 < NumRings; ++R)
		{
			// A height field over the local horizontal plane: the visible side is the upper one.
			const int32 I00 = Index(A, R), I01 = Index(A + 1, R), I10 = Index(A, R + 1), I11 = Index(A + 1, R + 1);
			OutMesh.AddTriangleFacing(I00, I10, I11, Up);
			OutMesh.AddTriangleFacing(I00, I11, I01, Up);
		}
	}
	OutMesh.ComputeNormals();

	if (NormalSmoothingM > 0.0 && NumRings > 1)
	{
		// Normals for drawing: the same triangles over heights averaged near the site. The
		// positions above stay as they are.
		const FSmoothedHeights Smoothed(DrawnHeightsM, Grid.RingDistanceM, NumAz, Package.SurfaceHeightM, NormalSmoothingM, NormalSmoothingExtentM);
		FLsnMeshData Shading;
		Shading.Triangles = OutMesh.Triangles;
		Shading.Positions = OutMesh.Positions;
		const double FadeM = 0.2 * NormalSmoothingExtentM;
		for (int32 A = 0; A < NumAz; ++A)
		{
			const double AzDeg = Package.AzimuthDegAt(A);
			const double Sin = FMath::Sin(FMath::DegreesToRadians(AzDeg)), Cos = FMath::Cos(FMath::DegreesToRadians(AzDeg));
			for (int32 R = 0; R < NumRings && Grid.RingDistanceM[R] < NormalSmoothingExtentM; ++R)
			{
				const double DistanceM = Grid.RingDistanceM[R];
				// Full smoothing near the site, fading out to none at the edge of its extent.
				const double Weight = FMath::Clamp((NormalSmoothingExtentM - DistanceM) / FadeM, 0.0, 1.0);
				const double Drawn = DrawnHeightsM[A * NumRings + R];
				const double HeightM = Drawn + Weight * (Smoothed.At(DistanceM * Sin, DistanceM * Cos) - Drawn);
				// Every ring vertex stands at its own ring here, the crest ring included.
				Shading.Positions[Index(A, R)] = Frame.SurfacePointUnreal(AzDeg, DistanceM, HeightM);
			}
		}
		Shading.ComputeNormals();
		OutMesh.Normals = MoveTemp(Shading.Normals);
	}
}

void LsnMesh::BuildHorizonTerrain(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
	const FLsnHorizonTerrainParams& Params, FLsnMeshData& OutMesh, int32& OutSkippedAzimuths)
{
	OutMesh = FLsnMeshData();
	OutSkippedAzimuths = 0;

	const int32 NumAz = Package.AzimuthCount;
	const int32 NumRings = FMath::Max(Params.NumRings, 2);
	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];
	const FVector Eye(0.0, 0.0, EyeHeightM * FLsnSiteFrame::CmPerM);

	// Horizon point of every azimuth sample.
	TArray<FVector> HorizonPoints;
	HorizonPoints.SetNumUninitialized(NumAz);
	for (int32 A = 0; A < NumAz; ++A)
	{
		const double Az = Package.AzimuthDegAt(A);
		if (!HorizonPointUnreal(Frame, EyeHeightM, Az, Package.HorizonElevationAt(HeightIndex, A), Package.HorizonDistanceAt(HeightIndex, A), HorizonPoints[A]))
		{
			// Unknown horizon: keep the mesh closed with a point well below any
			// horizon and report it. The viewer warns that the profile is incomplete.
			HorizonPoints[A] = FLsnSiteFrame::SightPointUnreal(EyeHeightM, Az, -45.0, 100.0);
			++OutSkippedAzimuths;
		}
	}

	const uint8 Grey = static_cast<uint8>(FMath::Clamp(FMath::RoundToInt(Params.Albedo * 255.0f), 0, 255));
	const FColor Color(Grey, Grey, Grey, 255);

	OutMesh.Positions.Reserve(1 + NumAz * NumRings);
	OutMesh.Positions.Add(FVector::ZeroVector); // the site's ground point
	for (int32 K = 1; K <= NumRings; ++K)
	{
		const double T = FMath::Pow(static_cast<double>(K) / NumRings, Params.RingExponent);
		for (int32 A = 0; A < NumAz; ++A)
		{
			FVector P = HorizonPoints[A] * T;
			if (Params.bCraters && K < NumRings)
			{
				const double EastM = P.Y / FLsnSiteFrame::CmPerM;
				const double NorthM = P.X / FLsnSiteFrame::CmPerM;
				const double HorizontalM = FMath::Sqrt(EastM * EastM + NorthM * NorthM);
				// No craters under the observer's feet and none near the horizon edge.
				const double Weight = SmoothStep01((HorizontalM - 3.0) / 12.0) * SmoothStep01((1.0 - T) / 0.1);
				P.Z -= CraterDepthM(EastM, NorthM, Params.CraterSeed) * Weight * FLsnSiteFrame::CmPerM;
			}
			OutMesh.Positions.Add(P);
		}
	}
	OutMesh.Colors.Init(Color, OutMesh.Positions.Num());
	OutMesh.UV0.Init(FVector2D::ZeroVector, OutMesh.Positions.Num());

	auto Index = [NumAz](int32 Ring, int32 A) { return 1 + (Ring - 1) * NumAz + (A % NumAz); };

	OutMesh.Triangles.Reserve(3 * NumAz * (2 * NumRings - 1));
	for (int32 A = 0; A < NumAz; ++A)
	{
		const int32 B = Index(1, A), C = Index(1, A + 1);
		const FVector Centroid = (OutMesh.Positions[0] + OutMesh.Positions[B] + OutMesh.Positions[C]) / 3.0;
		OutMesh.AddTriangleFacing(0, B, C, Eye - Centroid);
	}
	for (int32 K = 1; K < NumRings; ++K)
	{
		for (int32 A = 0; A < NumAz; ++A)
		{
			const int32 I00 = Index(K, A), I01 = Index(K, A + 1), I10 = Index(K + 1, A), I11 = Index(K + 1, A + 1);
			const FVector Centroid = (OutMesh.Positions[I00] + OutMesh.Positions[I01] + OutMesh.Positions[I10] + OutMesh.Positions[I11]) / 4.0;
			const FVector Towards = Eye - Centroid;
			OutMesh.AddTriangleFacing(I00, I10, I11, Towards);
			OutMesh.AddTriangleFacing(I00, I11, I01, Towards);
		}
	}
	OutMesh.ComputeNormals();
}

// ---------------------------------------------------------------------------
// Moon sphere
// ---------------------------------------------------------------------------

double LsnMesh::SunkSphereRadiusM(const FLsnSiteFrame& Frame, double EyeHeightM, double CapElevationDeg, double SinkM, double AngleFromSiteRad)
{
	const double LoweredEyeRadiusM = Frame.OriginRadiusM() + EyeHeightM - SinkM;
	const double Denominator = FMath::Cos(AngleFromSiteRad) - FMath::Tan(FMath::DegreesToRadians(CapElevationDeg)) * FMath::Sin(AngleFromSiteRad);
	if (!(Denominator > 1e-9))
	{
		return Frame.SphereRadiusM;
	}
	return FMath::Min(Frame.SphereRadiusM, LoweredEyeRadiusM / Denominator);
}

void LsnMesh::BuildMoonSphere(const FLsnSiteFrame& Frame, double GridStepDeg, TFunctionRef<double(double AngleFromSiteRad)> RadiusM,
	float Albedo, FLsnMeshData& OutMesh)
{
	OutMesh = FLsnMeshData();
	const int32 NumLat = FMath::Max(2, FMath::RoundToInt32(180.0 / GridStepDeg));
	const int32 NumLon = FMath::Max(3, FMath::RoundToInt32(360.0 / GridStepDeg));
	const uint8 Grey = static_cast<uint8>(FMath::Clamp(FMath::RoundToInt(Albedo * 255.0f), 0, 255));

	for (int32 I = 0; I <= NumLat; ++I)
	{
		const double Lat = -90.0 + 180.0 * I / NumLat;
		for (int32 J = 0; J <= NumLon; ++J)
		{
			const double Lon = -180.0 + 360.0 * J / NumLon;
			const FVector DirBody = FLsnSiteFrame::LatLonToBodyDir(Lat, Lon);
			const double CosAngle = FMath::Clamp(FVector::DotProduct(DirBody, Frame.UpBody), -1.0, 1.0);
			const double Radius = RadiusM(FMath::Acos(CosAngle));
			OutMesh.Positions.Add(Frame.BodyDirToUnreal(DirBody) * (Radius * FLsnSiteFrame::CmPerM));
			OutMesh.UV0.Add(FVector2D(static_cast<double>(J) / NumLon, 1.0 - static_cast<double>(I) / NumLat));
			OutMesh.Colors.Add(FColor(Grey, Grey, Grey, 255));
		}
	}
	auto Index = [NumLon](int32 I, int32 J) { return I * (NumLon + 1) + J; };
	for (int32 I = 0; I < NumLat; ++I)
	{
		for (int32 J = 0; J < NumLon; ++J)
		{
			const int32 I00 = Index(I, J), I01 = Index(I, J + 1), I10 = Index(I + 1, J), I11 = Index(I + 1, J + 1);
			const FVector Outward = OutMesh.Positions[I00] + OutMesh.Positions[I01] + OutMesh.Positions[I10] + OutMesh.Positions[I11];
			OutMesh.AddTriangleFacing(I00, I10, I11, Outward);
			OutMesh.AddTriangleFacing(I00, I11, I01, Outward);
		}
	}
	OutMesh.ComputeNormals();
}

void LsnMesh::BuildUnitSphere(int32 NumLatitudeBands, int32 NumLongitudeBands, const FColor& Color, FLsnMeshData& OutMesh)
{
	OutMesh = FLsnMeshData();
	for (int32 I = 0; I <= NumLatitudeBands; ++I)
	{
		const double Lat = -90.0 + 180.0 * I / NumLatitudeBands;
		for (int32 J = 0; J <= NumLongitudeBands; ++J)
		{
			const double Lon = 360.0 * J / NumLongitudeBands;
			const FVector Dir = FLsnSiteFrame::LatLonToBodyDir(Lat, Lon);
			OutMesh.Positions.Add(Dir);
			OutMesh.Normals.Add(Dir);
			OutMesh.UV0.Add(FVector2D(static_cast<double>(J) / NumLongitudeBands, 1.0 - static_cast<double>(I) / NumLatitudeBands));
			OutMesh.Colors.Add(Color);
		}
	}
	auto Index = [NumLongitudeBands](int32 I, int32 J) { return I * (NumLongitudeBands + 1) + J; };
	for (int32 I = 0; I < NumLatitudeBands; ++I)
	{
		for (int32 J = 0; J < NumLongitudeBands; ++J)
		{
			const int32 I00 = Index(I, J), I01 = Index(I, J + 1), I10 = Index(I + 1, J), I11 = Index(I + 1, J + 1);
			const FVector Outward = OutMesh.Positions[I00] + OutMesh.Positions[I01] + OutMesh.Positions[I10] + OutMesh.Positions[I11];
			OutMesh.AddTriangleFacing(I00, I10, I11, Outward);
			OutMesh.AddTriangleFacing(I00, I11, I01, Outward);
		}
	}
}

void LsnMesh::BuildObstacleBand(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
	const TArray<int32>& AzimuthIndices, double BandWidthDeg, const FColor& Color, FLsnMeshData& OutMesh)
{
	OutMesh = FLsnMeshData();
	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];
	const FVector Eye(0.0, 0.0, EyeHeightM * FLsnSiteFrame::CmPerM);
	for (const int32 A : AzimuthIndices)
	{
		const double Az = Package.AzimuthDegAt(A);
		const double El = Package.HorizonElevationAt(HeightIndex, A);
		FVector HorizonPoint;
		double SlantCm = 100000.0;
		if (HorizonPointUnreal(Frame, EyeHeightM, Az, El, Package.HorizonDistanceAt(HeightIndex, A), HorizonPoint))
		{
			SlantCm = (HorizonPoint - Eye).Size();
		}
		const double ElSafe = FMath::IsNaN(El) ? 0.0 : El;
		// Slightly nearer than the horizon point, so the band is drawn in front of the terrain.
		const double BandCm = 0.97 * SlantCm;
		OutMesh.Positions.Add(Eye + FLsnSiteFrame::AzElToUnrealDir(Az, ElSafe) * BandCm);
		OutMesh.Positions.Add(Eye + FLsnSiteFrame::AzElToUnrealDir(Az, ElSafe + BandWidthDeg) * BandCm);
	}
	OutMesh.Colors.Init(Color, OutMesh.Positions.Num());
	OutMesh.UV0.Init(FVector2D::ZeroVector, OutMesh.Positions.Num());
	for (int32 I = 0; I + 1 < AzimuthIndices.Num(); ++I)
	{
		const int32 L0 = 2 * I, U0 = 2 * I + 1, L1 = 2 * I + 2, U1 = 2 * I + 3;
		const FVector Towards = Eye - (OutMesh.Positions[L0] + OutMesh.Positions[U1]) * 0.5;
		OutMesh.AddTriangleFacing(L0, L1, U1, Towards);
		OutMesh.AddTriangleFacing(L0, U1, U0, Towards);
	}
	OutMesh.ComputeNormals();
}

void LsnMesh::BuildHorizonLine(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex, double BandWidthDeg,
	const FColor& Color, FLsnMeshData& OutMesh)
{
	OutMesh = FLsnMeshData();
	const int32 NumAz = Package.AzimuthCount;
	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];
	const FVector Eye(0.0, 0.0, EyeHeightM * FLsnSiteFrame::CmPerM);

	for (int32 A = 0; A < NumAz; ++A)
	{
		const double Az = Package.AzimuthDegAt(A);
		const double El = Package.HorizonElevationAt(HeightIndex, A);
		FVector HorizonPoint;
		double SlantCm = 100000.0;
		if (HorizonPointUnreal(Frame, EyeHeightM, Az, El, Package.HorizonDistanceAt(HeightIndex, A), HorizonPoint))
		{
			SlantCm = (HorizonPoint - Eye).Size();
		}
		const double ElSafe = FMath::IsNaN(El) ? 0.0 : El;
		// Slightly nearer than the horizon point, so the band is drawn in front of it.
		const double BandCm = 0.98 * SlantCm;
		OutMesh.Positions.Add(Eye + FLsnSiteFrame::AzElToUnrealDir(Az, ElSafe) * BandCm);
		OutMesh.Positions.Add(Eye + FLsnSiteFrame::AzElToUnrealDir(Az, ElSafe + BandWidthDeg) * BandCm);
	}
	OutMesh.Colors.Init(Color, OutMesh.Positions.Num());
	OutMesh.UV0.Init(FVector2D::ZeroVector, OutMesh.Positions.Num());
	for (int32 A = 0; A < NumAz; ++A)
	{
		const int32 B = (A + 1) % NumAz;
		const int32 L0 = 2 * A, U0 = 2 * A + 1, L1 = 2 * B, U1 = 2 * B + 1;
		const FVector Towards = Eye - (OutMesh.Positions[L0] + OutMesh.Positions[U1]) * 0.5;
		OutMesh.AddTriangleFacing(L0, L1, U1, Towards);
		OutMesh.AddTriangleFacing(L0, U1, U0, Towards);
	}
	OutMesh.ComputeNormals();
}

// ---------------------------------------------------------------------------
// Silhouette
// ---------------------------------------------------------------------------

FLsnSilhouette::FLsnSilhouette(const TArray<FLsnPlacedMesh>& Meshes, const FVector& EyeUnreal)
{
	Bins.SetNum(NumBins);
	const double BinWidthDeg = 360.0 / NumBins;

	for (const FLsnPlacedMesh& Placed : Meshes)
	{
		const FLsnMeshData& Mesh = *Placed.Mesh;
		for (int32 T = 0; T < Mesh.NumTriangles(); ++T)
		{
			FTriangle Triangle;
			double AzDeg[3];
			bool bOnAxis = false;
			for (int32 V = 0; V < 3; ++V)
			{
				Triangle.V[V] = Mesh.Positions[Mesh.Triangles[T * 3 + V]] + Placed.Origin - EyeUnreal;
				const FVector& P = Triangle.V[V];
				if (FMath::Abs(P.X) < 1e-9 && FMath::Abs(P.Y) < 1e-9)
				{
					bOnAxis = true; // straight above or below the eye: every azimuth
				}
				AzDeg[V] = FMath::RadiansToDegrees(FMath::Atan2(P.Y, P.X));
			}
			const int32 TriangleIndex = Triangles.Add(Triangle);

			// Azimuth range of the triangle, unwrapped around its first vertex.
			double Lo = 0.0, Hi = 0.0;
			for (int32 V = 1; V < 3; ++V)
			{
				double Delta = AzDeg[V] - AzDeg[0];
				Delta -= 360.0 * FMath::RoundToDouble(Delta / 360.0);
				Lo = FMath::Min(Lo, Delta);
				Hi = FMath::Max(Hi, Delta);
			}
			if (bOnAxis || Hi - Lo >= 179.0)
			{
				// May surround the vertical axis through the eye: file it under every azimuth.
				for (TArray<int32>& Bin : Bins)
				{
					Bin.Add(TriangleIndex);
				}
				continue;
			}
			const int32 FirstBin = FMath::FloorToInt32((AzDeg[0] + Lo) / BinWidthDeg) - 1;
			const int32 LastBin = FMath::FloorToInt32((AzDeg[0] + Hi) / BinWidthDeg) + 1;
			for (int32 Bin = FirstBin; Bin <= LastBin; ++Bin)
			{
				Bins[((Bin % NumBins) + NumBins) % NumBins].Add(TriangleIndex);
			}
		}
	}
}

bool FLsnSilhouette::MaxElevationDeg(double AzimuthDeg, double& OutElevationDeg) const
{
	const double Az = FMath::DegreesToRadians(AzimuthDeg);
	const FVector Along(FMath::Cos(Az), FMath::Sin(Az), 0.0);   // horizontal direction of the half-plane
	const FVector Across(-FMath::Sin(Az), FMath::Cos(Az), 0.0); // normal of the vertical plane

	double Wrapped = FMath::Fmod(AzimuthDeg, 360.0);
	if (Wrapped < 0.0)
	{
		Wrapped += 360.0;
	}
	const int32 BinIndex = FMath::Min(FMath::FloorToInt32(Wrapped / (360.0 / NumBins)), NumBins - 1);

	bool bFound = false;
	double MaxTan = 0.0;
	auto Consider = [&](const FVector& Point)
	{
		const double Horizontal = FVector::DotProduct(Point, Along);
		if (Horizontal > 0.0)
		{
			const double Tan = Point.Z / Horizontal;
			if (!bFound || Tan > MaxTan)
			{
				MaxTan = Tan;
				bFound = true;
			}
		}
	};

	for (const int32 TriangleIndex : Bins[BinIndex])
	{
		const FTriangle& Triangle = Triangles[TriangleIndex];
		double Side[3];
		for (int32 V = 0; V < 3; ++V)
		{
			Side[V] = FVector::DotProduct(Triangle.V[V], Across);
			// A vertex within a billionth of its distance from the plane is on it
			// (6e-8 deg); otherwise rounding decides whether an edge is met at all.
			if (FMath::Abs(Side[V]) <= 1e-9 * Triangle.V[V].Size())
			{
				Side[V] = 0.0;
			}
		}
		for (int32 V = 0; V < 3; ++V)
		{
			const int32 W = (V + 1) % 3;
			if (Side[V] == 0.0)
			{
				Consider(Triangle.V[V]);
			}
			if ((Side[V] < 0.0 && Side[W] > 0.0) || (Side[V] > 0.0 && Side[W] < 0.0))
			{
				const double T = Side[V] / (Side[V] - Side[W]);
				Consider(Triangle.V[V] + (Triangle.V[W] - Triangle.V[V]) * T);
			}
		}
	}
	if (bFound)
	{
		OutElevationDeg = FMath::RadiansToDegrees(FMath::Atan(MaxTan));
	}
	return bFound;
}

double LsnMesh::NearGroundFacingAwayShare(const FLsnTerrainGrid& Grid, double SiteHeightM, double SunAzimuthDeg, double SunElevationDeg, double MaxDistanceM)
{
	const int32 Rings = Grid.RingDistanceM.Num();
	if (Rings < 2 || Grid.AzimuthCount <= 0 || Grid.HeightsM.Num() != Grid.AzimuthCount * Rings || !(Grid.AzimuthStepDeg > 0.0))
	{
		return 0.0;
	}
	// Height of the samples at a point east and north of the site: linear between the azimuth
	// samples and between the rings (and between the site and the first ring).
	auto HeightAt = [&](double EastM, double NorthM, bool& bKnown)
	{
		const double Distance = FMath::Sqrt(EastM * EastM + NorthM * NorthM);
		const double AzimuthPosition = FMath::Fmod(FMath::RadiansToDegrees(FMath::Atan2(EastM, NorthM)) - Grid.AzimuthStartDeg + 720.0, 360.0) / Grid.AzimuthStepDeg;
		const int32 A0 = static_cast<int32>(FMath::FloorToDouble(AzimuthPosition)) % Grid.AzimuthCount, A1 = (A0 + 1) % Grid.AzimuthCount;
		const double Fa = AzimuthPosition - FMath::FloorToDouble(AzimuthPosition);
		auto Along = [&](int32 A)
		{
			if (Distance <= Grid.RingDistanceM[0])
			{
				return FMath::Lerp(SiteHeightM, static_cast<double>(Grid.HeightsM[A * Rings]), Distance / Grid.RingDistanceM[0]);
			}
			int32 R = 0;
			while (R + 2 < Rings && Grid.RingDistanceM[R + 1] < Distance)
			{
				++R;
			}
			const double F = FMath::Clamp((Distance - Grid.RingDistanceM[R]) / (Grid.RingDistanceM[R + 1] - Grid.RingDistanceM[R]), 0.0, 1.0);
			return FMath::Lerp(static_cast<double>(Grid.HeightsM[A * Rings + R]), static_cast<double>(Grid.HeightsM[A * Rings + R + 1]), F);
		};
		const double Value = FMath::Lerp(Along(A0), Along(A1), Fa);
		bKnown = bKnown && !FMath::IsNaN(Value);
		return Value;
	};
	const double SunEast = FMath::Sin(FMath::DegreesToRadians(SunAzimuthDeg)), SunNorth = FMath::Cos(FMath::DegreesToRadians(SunAzimuthDeg));
	const double TanSun = FMath::Tan(FMath::DegreesToRadians(SunElevationDeg));
	int32 Points = 0, Away = 0;
	for (int32 Step = 0; Step < 6; ++Step)
	{
		const double Distance = 2.0 + (MaxDistanceM - 2.0) * (Step + 0.5) / 6.0;
		for (int32 AzimuthDeg = 0; AzimuthDeg < 360; AzimuthDeg += 10)
		{
			const double East = Distance * FMath::Sin(FMath::DegreesToRadians(static_cast<double>(AzimuthDeg))), North = Distance * FMath::Cos(FMath::DegreesToRadians(static_cast<double>(AzimuthDeg)));
			// Rise of the ground over one metre towards the Sun, centred on the point.
			bool bKnown = true;
			const double Rise = HeightAt(East + 0.5 * SunEast, North + 0.5 * SunNorth, bKnown) - HeightAt(East - 0.5 * SunEast, North - 0.5 * SunNorth, bKnown);
			if (bKnown)
			{
				++Points;
				Away += Rise > TanSun ? 1 : 0;
			}
		}
	}
	return Points > 0 ? static_cast<double>(Away) / Points : 0.0;
}
