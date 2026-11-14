#include "LsnFrame.h"

namespace
{
	constexpr double DegToRad = UE_DOUBLE_PI / 180.0;
}

FVector LsnFrame::LatLonToBodyFixedDir(double LatDeg, double LonDeg)
{
	const double Lat = LatDeg * DegToRad;
	const double Lon = LonDeg * DegToRad;
	return FVector(FMath::Cos(Lat) * FMath::Cos(Lon), FMath::Cos(Lat) * FMath::Sin(Lon), FMath::Sin(Lat));
}

FVector LsnFrame::AzElToEnu(double AzDeg, double ElDeg)
{
	const double Az = AzDeg * DegToRad;
	const double El = ElDeg * DegToRad;
	return FVector(FMath::Cos(El) * FMath::Sin(Az), FMath::Cos(El) * FMath::Cos(Az), FMath::Sin(El));
}

void LsnFrame::EnuToAzEl(const FVector& Enu, double& OutAzDeg, double& OutElDeg)
{
	const double Horizontal = FMath::Sqrt(Enu.X * Enu.X + Enu.Y * Enu.Y);
	double Az = FMath::Atan2(Enu.X, Enu.Y) / DegToRad;
	if (Az < 0.0)
	{
		Az += 360.0;
	}
	OutAzDeg = Az;
	OutElDeg = FMath::Atan2(Enu.Z, Horizontal) / DegToRad;
}

FRotator LsnFrame::AzElToRotator(double AzDeg, double ElDeg)
{
	return FRotator(ElDeg, AzDeg - 90.0, 0.0);
}

FLsnSiteFrame FLsnSiteFrame::FromLatLon(double LatDeg, double LonDeg, double RadiusM)
{
	const double Lat = LatDeg * DegToRad;
	const double Lon = LonDeg * DegToRad;
	const double SinLat = FMath::Sin(Lat), CosLat = FMath::Cos(Lat);
	const double SinLon = FMath::Sin(Lon), CosLon = FMath::Cos(Lon);
	FLsnSiteFrame Frame;
	Frame.East = FVector(-SinLon, CosLon, 0.0);
	Frame.North = FVector(-SinLat * CosLon, -SinLat * SinLon, CosLat);
	Frame.Up = FVector(CosLat * CosLon, CosLat * SinLon, SinLat);
	Frame.PositionKm = Frame.Up * (RadiusM / 1000.0);
	return Frame;
}

FVector FLsnSiteFrame::BodyFixedKmToEnuM(const FVector& PositionBodyFixedKm) const
{
	const FVector D = (PositionBodyFixedKm - PositionKm) * 1000.0;
	return FVector(FVector::DotProduct(D, East), FVector::DotProduct(D, North), FVector::DotProduct(D, Up));
}

FVector FLsnSiteFrame::BodyFixedDirToEnu(const FVector& DirBodyFixed) const
{
	return FVector(FVector::DotProduct(DirBodyFixed, East), FVector::DotProduct(DirBodyFixed, North), FVector::DotProduct(DirBodyFixed, Up));
}
