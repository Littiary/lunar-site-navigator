#pragma once

#include "CoreMinimal.h"
#include "Frame/LsnSiteFrame.h"

struct FLsnSitePackage;
struct FLsnTerrainGrid;

/**
 * Plain mesh arrays, independent of the component that draws them.
 * Positions are centimetres relative to the mesh's own origin.
 *
 * Winding: Unreal treats triangle (a, b, c) as facing the direction
 * cross(c - a, b - a). AddTriangleFacing takes care of that.
 */
struct LUNARSITENAVIGATOR_API FLsnMeshData
{
	TArray<FVector> Positions;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FColor> Colors;

	int32 NumTriangles() const { return Triangles.Num() / 3; }

	/** Direction triangle TriangleIndex faces (not normalised). */
	FVector TriangleFacing(int32 TriangleIndex) const;

	/** Adds a triangle wound so that it faces the same side as TowardsDir. */
	void AddTriangleFacing(int32 A, int32 B, int32 C, const FVector& TowardsDir);

	/** Area-weighted vertex normals from the triangles. */
	void ComputeNormals();

	/**
	 * Rounds every position to 32-bit floats, as the vertex buffer will hold them.
	 * Measurements made after this call see what the GPU sees.
	 */
	void RoundPositionsToFloat();
};

/** Parameters of the placeholder surface between the site and the horizon points. */
struct FLsnHorizonTerrainParams
{
	/** Rings between the site and the horizon point of each azimuth (the last ring is the horizon point). */
	int32 NumRings = 96;
	/** Ring k sits at fraction (k / NumRings) ^ RingExponent of the way to the horizon point. */
	double RingExponent = 2.5;
	/** Adds procedural craters (depressions only) to the placeholder surface. */
	bool bCraters = true;
	/** Seed of the procedural craters. */
	uint32 CraterSeed = 20261114u;
	/** Linear albedo written to the vertex colour. A display value, not a measurement. */
	float Albedo = 0.13f;
};

namespace LsnMesh
{
	/**
	 * Unreal position of the terrain point that sets the horizon at one azimuth:
	 * the point at arc distance HorizonDistanceM along the reference sphere whose
	 * straight line from the eye has elevation HorizonElevationDeg. Both numbers
	 * are package fields; this is their geometric meaning (SPEC 5.3), not a new
	 * computation. Returns false if the numbers cannot describe a point
	 * (NaN, zero distance, or a sight line that never meets that radial).
	 */
	LUNARSITENAVIGATOR_API bool HorizonPointUnreal(const FLsnSiteFrame& Frame, double EyeHeightM, double AzimuthDeg,
		double HorizonElevationDeg, double HorizonDistanceM, FVector& OutPointUnreal);

	/**
	 * The site terrain of stage 1. Its outer edge is the package horizon: one
	 * vertex per azimuth sample at the horizon point. Between the site and that
	 * edge there is no elevation data yet, so the surface is a placeholder:
	 * straight lines from the site's ground point to each horizon point, with
	 * procedural craters that only ever lower it. Lowering a point lowers its
	 * elevation angle, so the placeholder can never rise above the horizon.
	 *
	 * Origin: the site's ground point (the Unreal world origin).
	 * OutSkippedAzimuths counts samples that could not be placed.
	 */
	LUNARSITENAVIGATOR_API void BuildHorizonTerrain(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
		const FLsnHorizonTerrainParams& Params, FLsnMeshData& OutMesh, int32& OutSkippedAzimuths);

	/**
	 * The site terrain from real elevation samples (FLsnTerrainGrid). Along every azimuth
	 * sample the vertices are the grid's ring points, at their height above the reference
	 * sphere, plus the package's horizon point of that azimuth, in order of distance. The
	 * horizon point is the terrain point the science core found to set the horizon, so
	 * the crest of the mesh is the package horizon and the rest is elevation data.
	 *
	 * Origin: the site's ground point. OutSkippedAzimuths counts horizon samples that could
	 * not be placed, OutUnknownSamples grid samples without data (drawn at the height of
	 * the nearest ring that has data).
	 */
	LUNARSITENAVIGATOR_API void BuildGridTerrain(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
		const FLsnTerrainGrid& Grid, float Albedo, FLsnMeshData& OutMesh, int32& OutSkippedAzimuths, int32& OutUnknownSamples);

	/**
	 * Depth of the procedural craters at a horizontal position, metres, always >= 0.
	 * Our own formula; it describes no real surface.
	 */
	LUNARSITENAVIGATOR_API double CraterDepthM(double EastM, double NorthM, uint32 Seed);

	/**
	 * Reference sphere of the Moon as a latitude-longitude grid.
	 * Origin: the Moon's centre; axes: Unreal axes of the site frame.
	 * RadiusM gives the radius to draw for a direction that is AngleFromSiteRad
	 * away from the site's "up" (used to keep the sphere out of sight near the site).
	 */
	LUNARSITENAVIGATOR_API void BuildMoonSphere(const FLsnSiteFrame& Frame, double GridStepDeg,
		TFunctionRef<double(double AngleFromSiteRad)> RadiusM, float Albedo, FLsnMeshData& OutMesh);

	/**
	 * Radius at which a sphere point AngleFromSiteRad away from the site may be
	 * drawn so that, seen from the eye, it stays below CapElevationDeg; never
	 * more than the reference radius. The cap is taken from an eye lowered by
	 * SinkM, so the sphere also passes SinkM below the site itself.
	 */
	LUNARSITENAVIGATOR_API double SunkSphereRadiusM(const FLsnSiteFrame& Frame, double EyeHeightM, double CapElevationDeg, double SinkM,
		double AngleFromSiteRad);

	/** Sphere of radius 1 cm around the origin, outward facing. Scaled by the component that draws it. */
	LUNARSITENAVIGATOR_API void BuildUnitSphere(int32 NumLatitudeBands, int32 NumLongitudeBands, const FColor& Color, FLsnMeshData& OutMesh);

	/**
	 * A band along the azimuth samples of one obstacle (their indices in order), for
	 * highlighting it: vertex 2 i is on the package horizon at azimuth index
	 * AzimuthIndices[i], vertex 2 i + 1 lies BandWidthDeg above it; both just in front of
	 * the horizon point.
	 */
	LUNARSITENAVIGATOR_API void BuildObstacleBand(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
		const TArray<int32>& AzimuthIndices, double BandWidthDeg, const FColor& Color, FLsnMeshData& OutMesh);

	/**
	 * A thin band whose lower edge is the package horizon, drawn just in front
	 * of the horizon points, for checking the silhouette by eye.
	 */
	LUNARSITENAVIGATOR_API void BuildHorizonLine(const FLsnSiteFrame& Frame, const FLsnSitePackage& Package, int32 HeightIndex,
		double BandWidthDeg, const FColor& Color, FLsnMeshData& OutMesh);
}

/** One mesh placed in the Unreal world, for silhouette measurements. */
struct FLsnPlacedMesh
{
	const FLsnMeshData* Mesh = nullptr;
	/** World position of the mesh origin, centimetres. */
	FVector Origin = FVector::ZeroVector;
};

/**
 * Measures the silhouette a set of meshes presents to an eye: for an azimuth,
 * the largest elevation angle at which any triangle is met by the vertical
 * half-plane through the eye at that azimuth. Pure geometry on the triangles
 * as built; it knows nothing about how they were made.
 */
class LUNARSITENAVIGATOR_API FLsnSilhouette
{
public:
	FLsnSilhouette(const TArray<FLsnPlacedMesh>& Meshes, const FVector& EyeUnreal);

	/** Largest elevation angle, degrees, at this azimuth; false if no triangle is met. */
	bool MaxElevationDeg(double AzimuthDeg, double& OutElevationDeg) const;

private:
	struct FTriangle
	{
		FVector V[3];
	};

	static constexpr int32 NumBins = 720;
	TArray<FTriangle> Triangles;
	TArray<TArray<int32>> Bins;
};
