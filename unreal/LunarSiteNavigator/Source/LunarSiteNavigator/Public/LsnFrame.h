#pragma once

#include "CoreMinimal.h"

/**
 * Frames of the scene. See unreal/README.md, "Frames and world origin".
 *
 * Body-fixed frame: right-handed, kilometres, origin at the centre of the Moon; its name
 *   comes from the package (site.frame).
 * Site frame (ENU): right-handed, metres, origin at the ground point of the site;
 *   X east, Y north, Z up (outward radial). Azimuth is clockwise from north, elevation is
 *   above the plane perpendicular to up (SPEC section 2).
 * Unreal world: left-handed, centimetres, origin at the ground point of the site;
 *   +X east, +Y south, +Z up. The Y axis is mirrored because Unreal is left-handed.
 *
 * All functions work in double precision.
 */
namespace LsnFrame
{
	constexpr double CmPerM = 100.0;

	/** Unit vector of a planetocentric latitude and east-positive longitude, body-fixed. */
	LUNARSITENAVIGATOR_API FVector LatLonToBodyFixedDir(double LatDeg, double LonDeg);

	/** Unit vector in the site frame for an azimuth and elevation in degrees. */
	LUNARSITENAVIGATOR_API FVector AzElToEnu(double AzDeg, double ElDeg);

	/** Azimuth in [0, 360) and elevation in degrees of a site-frame vector. */
	LUNARSITENAVIGATOR_API void EnuToAzEl(const FVector& Enu, double& OutAzDeg, double& OutElDeg);

	/** Site frame to Unreal axes, without a change of unit (directions). */
	inline FVector EnuToWorld(const FVector& Enu) { return FVector(Enu.X, -Enu.Y, Enu.Z); }
	inline FVector WorldToEnu(const FVector& World) { return FVector(World.X, -World.Y, World.Z); }

	/** Site frame in metres to Unreal world in centimetres, and back. */
	inline FVector EnuMToWorldCm(const FVector& EnuM) { return EnuToWorld(EnuM) * CmPerM; }
	inline FVector WorldCmToEnuM(const FVector& WorldCm) { return WorldToEnu(WorldCm) / CmPerM; }

	/** Unit vector in the Unreal world for an azimuth and elevation. */
	inline FVector AzElToWorldDir(double AzDeg, double ElDeg) { return EnuToWorld(AzElToEnu(AzDeg, ElDeg)); }

	/** Rotator whose forward (+X) axis points at the azimuth and elevation: yaw = azimuth - 90, pitch = elevation. */
	LUNARSITENAVIGATOR_API FRotator AzElToRotator(double AzDeg, double ElDeg);
}

/** Ground point and local axes of a site, expressed in the body-fixed frame. */
struct LUNARSITENAVIGATOR_API FLsnSiteFrame
{
	FVector PositionKm = FVector::ZeroVector;
	FVector East = FVector(1.0, 0.0, 0.0);
	FVector North = FVector(0.0, 1.0, 0.0);
	FVector Up = FVector(0.0, 0.0, 1.0);

	/** Same formulas as the core (lsncore.geometry.site_frame). Used for tests and cross-checks. */
	static FLsnSiteFrame FromLatLon(double LatDeg, double LonDeg, double RadiusM);

	/** Body-fixed position in kilometres to the site frame in metres. */
	FVector BodyFixedKmToEnuM(const FVector& PositionBodyFixedKm) const;

	/** Body-fixed direction to the site frame. */
	FVector BodyFixedDirToEnu(const FVector& DirBodyFixed) const;
};
