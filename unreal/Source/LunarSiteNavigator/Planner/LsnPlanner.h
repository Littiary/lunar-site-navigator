#pragma once

#include "CoreMinimal.h"
#include "Package/LsnPackage.h"

/**
 * Logic of the planner interface that is not drawing: which sites a package root has,
 * how two packages are shown at the same instant, how to jump between the package's
 * events, and which summary numbers of a package are put side by side.
 *
 * Nothing here computes a result. Every number comes from a package.
 */

/** Horizon panorama: azimuth 0 .. 360 from left to right, elevation upwards. */
struct LUNARSITENAVIGATOR_API FLsnPanorama
{
	FBox2D Box;
	double MinElevationDeg = -5.0;
	double MaxElevationDeg = 10.0;

	/** Screen point of an azimuth and elevation; the azimuth wraps, the elevation clamps to the range. */
	FVector2D Point(double AzimuthDeg, double ElevationDeg) const;
};

namespace LsnPlanner
{
	/**
	 * Where the second scene of a comparison stands in the world, centimetres. Far enough
	 * that neither terrain, shadows nor the Moon sphere of one scene reach the other.
	 */
	LUNARSITENAVIGATOR_API FVector SecondSceneOffsetCm();

	/** The site packages of a package root, in the order of index.json. */
	LUNARSITENAVIGATOR_API bool ListSites(const FString& PackageRoot, TArray<FLsnIndexEntry>& OutSites, FString& OutError);

	/**
	 * Position on B's time axis of the instant at PositionA on A's (both TDB). False if
	 * that instant lies outside B's axis or a package has no timeline.
	 */
	LUNARSITENAVIGATOR_API bool LinkedPosition(const FLsnSitePackage& A, double PositionA, const FLsnSitePackage& B, double& OutPositionB);

	/**
	 * The package event of an observer height strictly after (Direction > 0) or strictly
	 * before (Direction < 0) a time. Body "SUN", "EARTH" or empty for either. Null if none.
	 */
	LUNARSITENAVIGATOR_API const FLsnEvent* AdjacentEvent(const FLsnSitePackage& Package, const FString& Body, int32 HeightIndex, double EtS, int32 Direction);

	/** Summary numbers of a package for one observer height, for the side-by-side comparison. */
	LUNARSITENAVIGATOR_API void BuildMetricLines(const FLsnSitePackage& Package, int32 HeightIndex, TArray<FString>& OutLines);

	/** Elevation range a panorama of this package and height needs: its horizon and the extremes of its Sun and Earth series. */
	LUNARSITENAVIGATOR_API void PanoramaRange(const FLsnSitePackage& Package, int32 HeightIndex, double& OutMinDeg, double& OutMaxDeg);
}
