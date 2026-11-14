#pragma once

#include "CoreMinimal.h"

struct FLsnDirectionTable;

/** The Earth's own axes in the frame of the direction table: north pole, latitude 0 longitude 0, and pole x X. */
struct FLsnEarthAxes
{
	FVector Pole = FVector::UpVector;
	FVector X = FVector::ForwardVector;
	FVector Y = FVector::RightVector;
};

/**
 * Turning a textured Earth the right way (SPEC 6.1, since contract 0.8). The three angles
 * come from the direction table; this is the geometry the contract writes down for them,
 * nothing is computed about where the Earth is or how it is oriented.
 */
namespace LsnEarth
{
	/**
	 * The Earth's axes from the unit direction g (centre of the Moon to the Earth, table
	 * frame) and the three angles of a record, as in SPEC 6.1.
	 */
	LUNARSITENAVIGATOR_API FLsnEarthAxes Axes(const FVector& G, double SubLunarLatDeg, double SubLunarLonDeg, double NorthPoleAngleDeg, double Flattening);

	/** Longitude between two records, the short way round (it wraps at 180 degrees). */
	LUNARSITENAVIGATOR_API double LerpLongitudeDeg(double FromDeg, double ToDeg, double Fraction);

	/**
	 * The axes at an instant of the table: latitude and pole angle linear between the two
	 * records, longitude the short way round, as the contract says. False if the table has
	 * no earth_view or the instant is outside it.
	 */
	LUNARSITENAVIGATOR_API bool AxesAt(const FLsnDirectionTable& Table, double EtS, FLsnEarthAxes& OutAxes);
}
