#pragma once

#include "CoreMinimal.h"

/**
 * Mapping between three frames. See unreal/FRAMES.md for the full statement.
 *
 *  1. Moon body-fixed frame ("body"): right-handed, origin at the Moon's centre,
 *     +Z through the north pole, +X through latitude 0 / longitude 0,
 *     +Y through latitude 0 / longitude 90 E. Which realisation (for example
 *     a mean-Earth frame) is named by the package; this code only needs the
 *     axis convention.
 *  2. Site local frame: east, north, up at the site. "Up" is the normal of the
 *     reference sphere at the site, not the terrain normal. Azimuth is measured
 *     from north towards east; elevation from the local horizontal plane.
 *  3. Unreal world: left-handed, Z up, 1 unit = 1 cm.
 *       Unreal +X = north, +Y = east, +Z = up,
 *       origin = the site's ground point (reference sphere + site height).
 *
 * The body -> Unreal map is a reflection (right-handed to left-handed), so it
 * must never be expressed as an actor rotation or a quaternion. Positions are
 * converted here, in double precision, and written into meshes as they are.
 *
 * This type holds no engine objects and does no science: it converts
 * coordinates that the package supplies.
 */
struct LUNARSITENAVIGATOR_API FLsnSiteFrame
{
	/** Unreal units per metre. */
	static constexpr double CmPerM = 100.0;

	/** Unit vectors of the site local frame, expressed in the body frame. */
	FVector EastBody = FVector(0, 1, 0);
	FVector NorthBody = FVector(0, 0, 1);
	FVector UpBody = FVector(1, 0, 0);

	double LatitudeDeg = 0.0;
	double EastLongitudeDeg = 0.0;
	/** Radius of the reference sphere, metres. Comes from the package. */
	double SphereRadiusM = 0.0;
	/** Height of the site's ground point above the reference sphere, metres. */
	double SiteHeightM = 0.0;

	static FLsnSiteFrame Make(double InLatitudeDeg, double InEastLongitudeDeg, double InSphereRadiusM, double InSiteHeightM);

	/** Distance of the Unreal origin (site ground point) from the Moon's centre, metres. */
	double OriginRadiusM() const { return SphereRadiusM + SiteHeightM; }

	// --- Local frame <-> Unreal -------------------------------------------

	/** Unit direction in Unreal axes for an azimuth (north 0, east 90) and elevation, degrees. */
	static FVector AzElToUnrealDir(double AzimuthDeg, double ElevationDeg);

	/** Inverse of AzElToUnrealDir. Azimuth is returned in [0, 360). */
	static void UnrealDirToAzEl(const FVector& DirUnreal, double& OutAzimuthDeg, double& OutElevationDeg);

	/** (east, north, up) in metres -> Unreal position in centimetres. */
	static FVector EnuMToUnreal(const FVector& EnuM);

	/** Unreal position in centimetres -> (east, north, up) in metres. */
	static FVector UnrealToEnuM(const FVector& PosUnreal);

	// --- Body frame <-> Unreal --------------------------------------------

	/** Direction in the body frame -> direction in Unreal axes (length preserved). */
	FVector BodyDirToUnreal(const FVector& DirBody) const;

	/** Direction in Unreal axes -> direction in the body frame (length preserved). */
	FVector UnrealDirToBody(const FVector& DirUnreal) const;

	/** Point in the body frame, metres from the Moon's centre -> Unreal position, centimetres. */
	FVector BodyPointMToUnreal(const FVector& PointBodyM) const;

	/** Unreal position, centimetres -> point in the body frame, metres from the Moon's centre. */
	FVector UnrealToBodyPointM(const FVector& PosUnreal) const;

	/** Unreal position of the Moon's centre, centimetres. Always straight down from the origin. */
	FVector MoonCentreUnreal() const;

	/** Unit vector from the Moon's centre for a latitude and east longitude, body frame. */
	static FVector LatLonToBodyDir(double InLatitudeDeg, double InEastLongitudeDeg);

	// --- Points on and above the reference sphere -------------------------

	/**
	 * Unreal position of the point reached by leaving the site at the given
	 * azimuth, travelling ArcDistanceM along the reference sphere (great circle),
	 * and then rising HeightM above the sphere.
	 */
	FVector SurfacePointUnreal(double AzimuthDeg, double ArcDistanceM, double HeightM) const;

	/**
	 * Unreal position of the point seen from an eye EyeHeightM above the site's
	 * ground point at the given azimuth and elevation, at straight-line
	 * distance SlantRangeM.
	 */
	static FVector SightPointUnreal(double EyeHeightM, double AzimuthDeg, double ElevationDeg, double SlantRangeM);
};
