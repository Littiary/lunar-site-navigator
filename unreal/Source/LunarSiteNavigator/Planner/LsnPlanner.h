#pragma once

#include "CoreMinimal.h"
#include "Frame/LsnSiteFrame.h"
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

/** Whether a landing at a selected time meets a requirement, read from the landing windows of the package. */
struct FLsnLandingCheck
{
	/** False after latest_landing: the stay would run past the computed range and nothing can be said. */
	bool bJudgeable = false;
	bool bFeasible = false;
	/** While feasible: the landing can be delayed, or advanced, by this much. */
	double SlipS = 0.0;
	double EarlyS = 0.0;
	/** The window is cut by the end of what can be judged: the true slip is at least SlipS. */
	bool bSlipIsLowerBound = false;
	/** From the end of the current window to the next; 0 if there is none. */
	double WaitAfterWindowS = 0.0;
	/** While not feasible: the next landing window, if the computed range has one. */
	bool bHasNextWindow = false;
	double WaitS = 0.0;
	FString NextWindowStartUtc;
	double NextWindowLengthS = 0.0;
};

namespace LsnPlanner
{
	/** True if an interval set of the package holds at a time (interval closed at its start, open at its end). */
	LUNARSITENAVIGATOR_API bool WindowHoldsAt(const FLsnWindow& Window, double EtS);

	/** Reads the landing windows of an opportunity at a selected landing time (SPEC 5.6). */
	LUNARSITENAVIGATOR_API FLsnLandingCheck LandingAt(const FLsnOpportunity& Opportunity, double EtS);

	/** The package event a countdown runs to (same body and height, within one second of its end); null for a lower bound. */
	LUNARSITENAVIGATOR_API const FLsnEvent* EventEndingCountdown(const FLsnSitePackage& Package, const FString& Body, int32 HeightIndex, double EtS, const FLsnCountdown& Countdown);

	/** Offset of a sample point of the landing ellipse from the site, metres east and north (for the small map). */
	LUNARSITENAVIGATOR_API FVector2D EllipsePointEastNorthM(const FLsnSiteFrame& Frame, const FLsnEllipsePoint& Point);

	/** The mast-height trade of a package as a small table; no lines if the package has none. */
	LUNARSITENAVIGATOR_API void BuildHeightTradeLines(const FLsnSitePackage& Package, TArray<FString>& OutLines);

	/** What two sites achieve together, one line per compared window. */
	LUNARSITENAVIGATOR_API void BuildPairLines(const FLsnSitePair& Pair, TArray<FString>& OutLines);

	/**
	 * A latitude or longitude typed by the user: a plain decimal number (digits, at most one
	 * point, an optional leading minus) inside the range. False for anything else.
	 */
	LUNARSITENAVIGATOR_API bool ParseCoordinate(const FString& Text, double Min, double Max, double& OutValue);

	/**
	 * Arguments of the science core's own command for one site given by coordinates
	 * (python -m lsncore site ...). The numbers are passed as they were typed; the engine
	 * computes nothing. OutName is the site name given to the core.
	 */
	LUNARSITENAVIGATOR_API FString CustomSiteArguments(const FString& LatitudeText, const FString& LongitudeText, const FString& OutputRoot, FString& OutName);

	/**
	 * Arguments of the core's command for the second step of custom coordinates (a complete
	 * site package with a timeline), from a template with the places {lat}, {lon}, {name}
	 * and {out}. Empty when there is no template: then there is no second step.
	 */
	LUNARSITENAVIGATOR_API FString CustomTimelineArguments(const FString& Template, const FString& LatitudeText, const FString& LongitudeText, const FString& Name, const FString& OutputRoot, const FString& StartDate = FString());

	/** The core's one command for a complete package of a custom coordinate (core/README.md, contract 0.11); the place {start} takes the first day of its window. */
	LUNARSITENAVIGATOR_API FString DefaultCustomTimelineTemplate();

	/** The last line "progress <k>/<n> <text>" the core printed; false if it printed none. */
	LUNARSITENAVIGATOR_API bool LastProgress(const FString& Output, int32& OutStage, int32& OutStages, FString& OutText);

	/** "measured terrain pixel, height +/- 5.0 m" for an event that states its terrain quality (since 0.10); empty otherwise. */
	LUNARSITENAVIGATOR_API FString TerrainQualityPhrase(const FLsnEvent& Event);

	/** True if a contract version "major.minor" is at least the given one, compared part by part (0.10 is newer than 0.9). */
	LUNARSITENAVIGATOR_API bool ContractAtLeast(const FString& Version, int32 Major, int32 Minor);

	/** Share of a running step to show as done: time run over the time stated for it, at most 0.95. */
	LUNARSITENAVIGATOR_API double StepShare(double RunS, double StatedS);

	/** "terrain: fine, 20 m pixels" from the package's terrain source; empty when the package has none. */
	LUNARSITENAVIGATOR_API FString TerrainSourceLabel(const FLsnTerrainSource& Source);

	/**
	 * Where the second scene of a comparison stands in the world, centimetres: at the same
	 * place as the first. The views and the lighting channels keep the two apart.
	 */
	LUNARSITENAVIGATOR_API FVector SecondSceneOffsetCm();

	/**
	 * The published packages: the folder packages/ at the root of the repository, which the
	 * science core regenerates. A stand-alone build carries a copy of exactly that folder,
	 * made when it is built (Scripts/package.ps1). Empty if neither exists.
	 */
	LUNARSITENAVIGATOR_API FString PublishedPackageRoot();

	/**
	 * Position on the time axis of a UTC time such as "2027-07-28T18:00:00Z". As for
	 * labels (SPEC 3.5), this is only allowed without a leap second in the range; false
	 * then, and false for a time outside the axis.
	 */
	LUNARSITENAVIGATOR_API bool PositionOfUtc(const FLsnSitePackage& Package, const FString& Utc, double& OutPosition);

	/** The site packages of a package root, in the order of index.json. */
	/**
	 * The entry of a site list to show (SPEC 7: the input is identified by its package_id). A package
	 * id selects its entry; otherwise a site id selects its first entry, with a warning if more than
	 * one entry has it. False with the reason in OutWarning if nothing fits.
	 */
	LUNARSITENAVIGATOR_API bool ChooseSite(const TArray<FLsnIndexEntry>& Sites, const FString& PackageId, const FString& SiteId, int32& OutIndex, FString& OutWarning);

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
