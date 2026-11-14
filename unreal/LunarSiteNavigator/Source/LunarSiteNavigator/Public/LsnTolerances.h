#pragma once

/**
 * Acceptance thresholds of the Unreal stream.
 *
 * They were written before the first measurement and are not edited to make a test pass
 * (CONTRIBUTING.md, rule 5). Each one states what it bounds and why it has that size.
 */
namespace LsnTolerances
{
	/** Frame mapping is plain double arithmetic; anything above rounding is a mistake. */
	constexpr double FrameUnitVector = 1e-12;

	/** A point a few kilometres from the site, mapped to centimetres. */
	constexpr double FramePointCm = 1e-6;

	/** site.enu and site.position_km of a package against the frame derived from lat/lon. */
	constexpr double SiteFrameAgainstLatLon = 1e-9;
	constexpr double SitePositionKm = 1e-6;

	/**
	 * Sun and Earth direction: the series of the site package (32-bit floats, degrees)
	 * against the direction-table positions mapped through the body-fixed frame.
	 * 32-bit storage of an azimuth near 360 degrees is good to about 3e-5 degrees.
	 */
	constexpr double BodyDirectionDeg = 1e-3;

	/** Azimuth of a horizon obstacle point against the azimuth of its sample. */
	constexpr double ObstacleAzimuthDeg = 1e-4;

	/**
	 * Horizon silhouette measured on the scene mesh against horizon.elevation_deg of the
	 * same package, at every azimuth sample and observer height.
	 *
	 * The mesh is built from the obstacle points (latitude, longitude, height) and the
	 * silhouette is measured from the observer position, so the comparison closes the loop
	 * package -> body-fixed frame -> site frame -> Unreal world -> mesh -> view angle.
	 * 0.05 degrees is less than a fifth of the angular radius of the Sun. The synthetic
	 * sample writes its obstacle heights with small-angle formulas, which by themselves are
	 * expected to cost about 0.02 degrees at its farthest obstacles.
	 */
	constexpr double HorizonSilhouetteDeg = 0.05;

	/** The same comparison half-way between azimuth samples (linear interpolation, SPEC 5.3). */
	constexpr double HorizonSilhouetteMidSampleDeg = 0.05;
}
