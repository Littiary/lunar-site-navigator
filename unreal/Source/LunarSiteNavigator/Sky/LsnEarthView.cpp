#include "Sky/LsnEarthView.h"

#include "Package/LsnPackage.h"

FLsnEarthAxes LsnEarth::Axes(const FVector& G, double SubLunarLatDeg, double SubLunarLonDeg, double NorthPoleAngleDeg, double Flattening)
{
	// SPEC 6.1, line by line.
	const FVector East = FVector::CrossProduct(FVector(0.0, 0.0, 1.0), G).GetSafeNormal();
	const FVector North = FVector::CrossProduct(G, East);
	const double Phi = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(SubLunarLatDeg)) * FMath::Square(1.0 - Flattening));
	const double Angle = FMath::DegreesToRadians(NorthPoleAngleDeg), Lon = FMath::DegreesToRadians(SubLunarLonDeg);
	FLsnEarthAxes Out;
	Out.Pole = FMath::Sin(Phi) * (-G) + FMath::Cos(Phi) * (FMath::Cos(Angle) * North + FMath::Sin(Angle) * East);
	const FVector Meridian = (-G - FMath::Sin(Phi) * Out.Pole).GetSafeNormal();
	Out.X = FMath::Cos(Lon) * Meridian - FMath::Sin(Lon) * FVector::CrossProduct(Out.Pole, Meridian);
	Out.Y = FVector::CrossProduct(Out.Pole, Out.X);
	return Out;
}

double LsnEarth::LerpLongitudeDeg(double FromDeg, double ToDeg, double Fraction)
{
	const double Step = FMath::Fmod(ToDeg - FromDeg + 540.0, 360.0) - 180.0;
	return FMath::Fmod(FromDeg + Fraction * Step + 540.0, 360.0) - 180.0;
}

bool LsnEarth::AxesAt(const FLsnDirectionTable& Table, double EtS, FLsnEarthAxes& OutAxes)
{
	if (!Table.bHasEarthView || Table.Time.Count < 2 || !(Table.Time.StepS > 0.0))
	{
		return false;
	}
	const double Position = (EtS - Table.Time.StartEtS) / Table.Time.StepS;
	if (Position < 0.0 || Position > Table.Time.Count - 1)
	{
		return false;
	}
	const int32 I0 = FMath::Min(static_cast<int32>(FMath::FloorToDouble(Position)), Table.Time.Count - 2), I1 = I0 + 1;
	const double F = Position - I0;
	FVector P0, P1;
	if (!Table.PositionKm(TEXT("EARTH"), I0, P0) || !Table.PositionKm(TEXT("EARTH"), I1, P1))
	{
		return false;
	}
	const float Lat0 = Table.EarthSubLunarLatDeg[I0], Lat1 = Table.EarthSubLunarLatDeg[I1], Lon0 = Table.EarthSubLunarLonDeg[I0], Lon1 = Table.EarthSubLunarLonDeg[I1];
	const float Angle0 = Table.EarthNorthPoleAngleDeg[I0], Angle1 = Table.EarthNorthPoleAngleDeg[I1];
	if (FMath::IsNaN(Lat0) || FMath::IsNaN(Lat1) || FMath::IsNaN(Lon0) || FMath::IsNaN(Lon1) || FMath::IsNaN(Angle0) || FMath::IsNaN(Angle1))
	{
		return false;
	}
	OutAxes = Axes(FMath::Lerp(P0, P1, F).GetSafeNormal(), FMath::Lerp(static_cast<double>(Lat0), static_cast<double>(Lat1), F), LerpLongitudeDeg(Lon0, Lon1, F),
		FMath::Lerp(static_cast<double>(Angle0), static_cast<double>(Angle1), F), Table.EarthFlattening);
	return true;
}
