#pragma once

#include "CoreMinimal.h"
#include "Mesh/LsnMesh.h"

struct FLsnSitePackage;

/** One star of the catalogue: where it stands in the J2000 frame and how bright it is. */
struct FLsnStar
{
	FVector DirectionJ2000 = FVector::ZeroVector;
	float VisualMagnitude = 0.0f;
	/** B-V colour index; NaN where the catalogue has none. */
	float ColourIndex = 0.0f;
};

/**
 * The star list written by Scripts/export_sky.py from the Yale Bright Star Catalogue.
 * Decoration: no number on screen comes from it.
 */
struct LUNARSITENAVIGATOR_API FLsnStarCatalogue
{
	TArray<FLsnStar> Stars;
	FString Source;

	/** Loads <project>/Content/LsnSky/stars.json and its array. */
	static bool Load(FLsnStarCatalogue& OutCatalogue, FString& OutError);
	static bool LoadFrom(const FString& Directory, FLsnStarCatalogue& OutCatalogue, FString& OutError);
};

/** A direction the exporter got from SPICE, for checking the orientation against the package. */
struct FLsnSkyCheck
{
	int32 Sample = 0;
	double EtS = 0.0;
	FVector SunJ2000 = FVector::ZeroVector;
};

/**
 * Orientation of the sky at a site over the time range of its package: for a list of
 * times, the matrix that takes a J2000 vector to the site's east, north and up axes.
 * Written by Scripts/export_sky.py from the SPICE kernels of the ephemeris stream; the
 * scene computes no orientation itself and only interpolates between two listed times.
 * A viewer-side cache like the terrain samples, tied to the package id.
 */
struct LUNARSITENAVIGATOR_API FLsnSkyOrientation
{
	FString SiteId;
	FString PackageId;
	double StartEtS = 0.0;
	double StepS = 0.0;
	/** [T] rows east, north, up of the matrix, each a vector of J2000 components. */
	TArray<FVector> East, North, Up;
	TArray<FLsnSkyCheck> Checks;

	int32 Num() const { return East.Num(); }

	static bool Load(const FString& Directory, FLsnSkyOrientation& OutSky, FString& OutError);
	/** Loads <project>/Content/LsnSky/<site_id>. */
	static bool LoadForSite(const FString& InSiteId, FLsnSkyOrientation& OutSky, FString& OutError);
	bool Matches(const FLsnSitePackage& Package, FString& OutError) const;

	/**
	 * The turn that takes the star mesh (built by LsnSky::BuildStarMesh, in J2000 with Z
	 * mirrored) to Unreal axes (+X north, +Y east, +Z up) at a time; between two listed
	 * times the shortest turn between them, in proportion. False outside the listed range.
	 */
	bool MeshRotationAt(double EtS, FQuat& OutRotation) const;

	/** Unreal unit direction (+X north, +Y east, +Z up) of a J2000 direction at a listed time index. */
	FVector UnrealDirectionAtIndex(int32 Index, const FVector& DirectionJ2000) const;
};

namespace LsnSky
{
	/** Display brightness of a star, 0 .. 1, from its magnitude: a compressed scale, not photometry. */
	LUNARSITENAVIGATOR_API float DisplayBrightness(float VisualMagnitude);

	/** Angular half size of the drawn dot, degrees: brighter stars are drawn larger. */
	LUNARSITENAVIGATOR_API double DotHalfSizeDeg(float VisualMagnitude);

	/** Tint from the B-V colour index: bluish for hot stars, reddish for cool ones. A drawing choice. */
	LUNARSITENAVIGATOR_API FLinearColor Tint(float ColourIndex);

	/**
	 * One small square per star on a sphere of the given radius round the origin, facing the
	 * origin. Directions are the catalogue's with Z mirrored, so that a turn alone (see
	 * FLsnSkyOrientation::MeshRotationAt) brings them to Unreal's left-handed axes. Vertex
	 * colour: tint, with the display brightness in alpha. UV: 0 .. 1 across each square.
	 */
	LUNARSITENAVIGATOR_API void BuildStarMesh(const FLsnStarCatalogue& Catalogue, double RadiusCm, FLsnMeshData& OutMesh);

	/** Where a star of the mesh ends up: the mirrored catalogue direction turned by the rotation. */
	LUNARSITENAVIGATOR_API FVector MeshDirection(const FVector& DirectionJ2000, const FQuat& Rotation);
}
