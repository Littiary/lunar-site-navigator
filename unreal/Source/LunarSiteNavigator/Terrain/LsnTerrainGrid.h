#pragma once

#include "CoreMinimal.h"

struct FLsnSitePackage;

/**
 * Terrain heights around a site on the polar layout of the scene's terrain mesh, written
 * by Scripts/export_terrain.py from the data stream's reader.
 *
 * It is a viewer-side cache for drawing and not part of the package contract: no number
 * shown to the user is taken from it. The horizon line of the scene still comes from the
 * package.
 */
struct LUNARSITENAVIGATOR_API FLsnTerrainGrid
{
	FString SiteId;
	/** The package the grid was sampled for. */
	FString PackageId;
	FString DemSetId;
	double ReferenceRadiusM = 0.0;
	double AzimuthStartDeg = 0.0;
	double AzimuthStepDeg = 0.0;
	int32 AzimuthCount = 0;
	/** Arc length along the reference sphere from the site to each ring, metres, increasing. */
	TArray<double> RingDistanceM;
	/** [A, R] height above the reference sphere, metres; NaN where the data has none. */
	TArray<double> HeightsM;

	double AzimuthDegAt(int32 AzimuthIndex) const { return AzimuthStartDeg + AzimuthStepDeg * AzimuthIndex; }

	/** Loads terrain.json and its array from a folder. On failure returns false and says why. */
	static bool Load(const FString& Directory, FLsnTerrainGrid& OutGrid, FString& OutError);

	/** Loads <project>/Content/LsnTerrain/<site_id>. */
	static bool LoadForSite(const FString& InSiteId, FLsnTerrainGrid& OutGrid, FString& OutError);

	/** True if the grid was sampled for this package, on its sphere and its azimuth layout. */
	bool Matches(const FLsnSitePackage& Package, FString& OutError) const;
};
