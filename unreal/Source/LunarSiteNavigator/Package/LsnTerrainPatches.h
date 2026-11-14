#pragma once

#include "CoreMinimal.h"

/**
 * A terrain patch of a site package (SPEC 5.9, since 0.7): the ground around the site on a
 * square grid in the local East/North/Up frame of the site, metres, the curvature of the
 * Moon already in the values. For drawing only: nothing about visibility is derived from it.
 */
struct LUNARSITENAVIGATOR_API FLsnTerrainPatch
{
	FString Id;
	double SpacingM = 0.0;
	double HalfWidthM = 0.0;
	double EastMinM = 0.0;
	double NorthMinM = 0.0;
	int32 CountEast = 0;
	int32 CountNorth = 0;
	/** [CountNorth][CountEast], row by row from the south; NaN where the elevation data ends. */
	TArray<float> UpM;

	/** Height of the patch at a point, linear between its nodes; false outside the patch or where data is missing. */
	bool UpAt(double EastM, double NorthM, double& OutUpM) const;
};

namespace LsnPackageIO
{
	/**
	 * The terrain patches of the package in a directory, whatever their ids, number and order
	 * (a reader selects by id, SPEC 5.9). False with a reason if the package has none or one of
	 * them cannot be read as its manifest describes it.
	 */
	LUNARSITENAVIGATOR_API bool LoadTerrainPatches(const FString& PackageDirectory, TArray<FLsnTerrainPatch>& OutPatches, FString& OutError);
}
