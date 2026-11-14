#pragma once

#include "CoreMinimal.h"

class FLsnSitePackage;

/** Buffers in the form ProceduralMeshComponent takes them. */
struct FLsnMeshData
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;

	/** Rounds every vertex to 32-bit floats, as the render and collision buffers store them. */
	void QuantizeToFloat();
};

namespace LsnTerrain
{
	/** Horizon obstacle point of a height and azimuth sample, site frame, metres. Needs obstacle fields. */
	LUNARSITENAVIGATOR_API FVector ObstacleEnuM(const FLsnSitePackage& Package, int32 HeightIndex, int32 AzimuthIndex);

	/**
	 * Stand-in terrain patch around the site, Unreal world centimetres, origin at the site.
	 *
	 * Used until real elevation tiles are available. Along every azimuth sample the ridge
	 * vertex is the obstacle point of the package; the surface between the site and the
	 * ridge and beyond the ridge is a smooth fill that stays below the line of sight to
	 * the ridge. Only the ridge line carries information from the package; the fill is
	 * not terrain data and must not be read as such.
	 */
	LUNARSITENAVIGATOR_API bool BuildHorizonPatch(const FLsnSitePackage& Package, int32 HeightIndex, FLsnMeshData& Out);

	/**
	 * Reference sphere of the Moon without the cap around the site that the patch covers.
	 * Vertices are in centimetres relative to the centre of the Moon, Unreal axes;
	 * OutCentreWorldCm is where that centre lies in the world.
	 */
	LUNARSITENAVIGATOR_API void BuildReferenceSphere(const FLsnSitePackage& Package, FLsnMeshData& Out, FVector& OutCentreWorldCm);

	/** Unit disc in the local YZ plane, visible from both sides. */
	LUNARSITENAVIGATOR_API void BuildDisc(int32 Segments, FLsnMeshData& Out);

	/**
	 * Elevation angle, in degrees, of the highest point of a mesh seen from an observer in
	 * the vertical half-plane of an azimuth: the silhouette of the mesh at that azimuth.
	 * Exact for a triangle mesh. Returns -90 if the half-plane misses the mesh.
	 */
	LUNARSITENAVIGATOR_API double SilhouetteElevationDeg(const FLsnMeshData& Mesh, const FVector& ObserverWorldCm, double AzDeg);
}
