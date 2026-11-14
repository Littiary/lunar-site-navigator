#include "Frame/LsnSiteFrame.h"

FVector FLsnSiteFrame::LatLonToBodyDir(double InLatitudeDeg, double InEastLongitudeDeg)
{
	const double Lat = FMath::DegreesToRadians(InLatitudeDeg);
	const double Lon = FMath::DegreesToRadians(InEastLongitudeDeg);
	const double CosLat = FMath::Cos(Lat);
	return FVector(CosLat * FMath::Cos(Lon), CosLat * FMath::Sin(Lon), FMath::Sin(Lat));
}

FLsnSiteFrame FLsnSiteFrame::Make(double InLatitudeDeg, double InEastLongitudeDeg, double InSphereRadiusM, double InSiteHeightM)
{
	FLsnSiteFrame F;
	F.LatitudeDeg = InLatitudeDeg;
	F.EastLongitudeDeg = InEastLongitudeDeg;
	F.SphereRadiusM = InSphereRadiusM;
	F.SiteHeightM = InSiteHeightM;

	const double Lat = FMath::DegreesToRadians(InLatitudeDeg);
	const double Lon = FMath::DegreesToRadians(InEastLongitudeDeg);
	const double SinLat = FMath::Sin(Lat), CosLat = FMath::Cos(Lat);
	const double SinLon = FMath::Sin(Lon), CosLon = FMath::Cos(Lon);

	// At a pole the longitude that the caller passes still fixes east and
	// north, so the expressions stay finite there.
	F.UpBody = FVector(CosLat * CosLon, CosLat * SinLon, SinLat);
	F.EastBody = FVector(-SinLon, CosLon, 0.0);
	F.NorthBody = FVector(-SinLat * CosLon, -SinLat * SinLon, CosLat);
	return F;
}

FVector FLsnSiteFrame::AzElToUnrealDir(double AzimuthDeg, double ElevationDeg)
{
	const double Az = FMath::DegreesToRadians(AzimuthDeg);
	const double El = FMath::DegreesToRadians(ElevationDeg);
	const double CosEl = FMath::Cos(El);
	// X = north, Y = east, Z = up.
	return FVector(CosEl * FMath::Cos(Az), CosEl * FMath::Sin(Az), FMath::Sin(El));
}

void FLsnSiteFrame::UnrealDirToAzEl(const FVector& DirUnreal, double& OutAzimuthDeg, double& OutElevationDeg)
{
	const double Horizontal = FMath::Sqrt(DirUnreal.X * DirUnreal.X + DirUnreal.Y * DirUnreal.Y);
	OutElevationDeg = FMath::RadiansToDegrees(FMath::Atan2(DirUnreal.Z, Horizontal));
	double Az = FMath::RadiansToDegrees(FMath::Atan2(DirUnreal.Y, DirUnreal.X));
	if (Az < 0.0)
	{
		Az += 360.0;
	}
	if (Az >= 360.0)
	{
		Az -= 360.0;
	}
	OutAzimuthDeg = Az;
}

FVector FLsnSiteFrame::EnuMToUnreal(const FVector& EnuM)
{
	return FVector(EnuM.Y * CmPerM, EnuM.X * CmPerM, EnuM.Z * CmPerM);
}

FVector FLsnSiteFrame::UnrealToEnuM(const FVector& PosUnreal)
{
	return FVector(PosUnreal.Y / CmPerM, PosUnreal.X / CmPerM, PosUnreal.Z / CmPerM);
}

FVector FLsnSiteFrame::BodyDirToUnreal(const FVector& DirBody) const
{
	return FVector(
		FVector::DotProduct(DirBody, NorthBody),
		FVector::DotProduct(DirBody, EastBody),
		FVector::DotProduct(DirBody, UpBody));
}

FVector FLsnSiteFrame::UnrealDirToBody(const FVector& DirUnreal) const
{
	return NorthBody * DirUnreal.X + EastBody * DirUnreal.Y + UpBody * DirUnreal.Z;
}

FVector FLsnSiteFrame::BodyPointMToUnreal(const FVector& PointBodyM) const
{
	const FVector FromOriginM = PointBodyM - UpBody * OriginRadiusM();
	return BodyDirToUnreal(FromOriginM) * CmPerM;
}

FVector FLsnSiteFrame::UnrealToBodyPointM(const FVector& PosUnreal) const
{
	return UnrealDirToBody(PosUnreal / CmPerM) + UpBody * OriginRadiusM();
}

FVector FLsnSiteFrame::MoonCentreUnreal() const
{
	return FVector(0.0, 0.0, -OriginRadiusM() * CmPerM);
}

FVector FLsnSiteFrame::SurfacePointUnreal(double AzimuthDeg, double ArcDistanceM, double HeightM) const
{
	// Worked directly in local axes: the great circle through the site at this
	// azimuth lies in the plane spanned by "up" and the horizontal direction.
	const double Gamma = ArcDistanceM / SphereRadiusM;
	const double Az = FMath::DegreesToRadians(AzimuthDeg);
	const double Radius = SphereRadiusM + HeightM;
	const double Horizontal = Radius * FMath::Sin(Gamma);
	// Radius * cos(gamma) - origin radius, written to keep precision when gamma is small:
	// cos(gamma) - 1 = -2 sin^2(gamma / 2).
	const double SinHalf = FMath::Sin(0.5 * Gamma);
	const double Up = (HeightM - SiteHeightM) - 2.0 * Radius * SinHalf * SinHalf;
	return FVector(Horizontal * FMath::Cos(Az) * CmPerM, Horizontal * FMath::Sin(Az) * CmPerM, Up * CmPerM);
}

FVector FLsnSiteFrame::SightPointUnreal(double EyeHeightM, double AzimuthDeg, double ElevationDeg, double SlantRangeM)
{
	return FVector(0.0, 0.0, EyeHeightM * CmPerM) + AzElToUnrealDir(AzimuthDeg, ElevationDeg) * (SlantRangeM * CmPerM);
}
