#pragma once

#include "CoreMinimal.h"
#include "Package/LsnPlanningTypes.h"

class FJsonObject;

/**
 * Reader for packages written by the science core (docs/contract/SPEC.md,
 * contract "lsn-package", major version 0).
 *
 * The reader only reads. It does not compute Sun or Earth positions, rise or
 * set times, margins or visible fractions; those are fields of the package.
 */

/** Major version of the contract this reader understands. */
inline constexpr int32 LsnContractMajor = 0;

/** A uniform time axis (SPEC 3.5). Sample i is at StartEtS + i * StepS. */
struct FLsnTimeGrid
{
	double StartEtS = 0.0;
	double StepS = 0.0;
	int32 Count = 0;
	FString StartUtc;
	FString EndUtc;
	int32 LeapSecondsInRange = 0;
};

/** Per-body series of a site timeline (SPEC 5.4). */
struct FLsnBodySeries
{
	/** [N] azimuth of the centre of the disc, degrees. */
	TArray<float> AzimuthDeg;
	/** [N] elevation of the centre of the disc, degrees (geometric, no terrain). */
	TArray<float> ElevationDeg;
	/** [N] angular radius of the disc, degrees. Optional in the contract; empty when absent. */
	TArray<float> AngularRadiusDeg;
	/** [H, N] elevation of the disc centre minus the terrain horizon, degrees. */
	TArray<float> MarginDeg;
	/** [H, N] fraction of the disc above the terrain horizon, 0 to 1. */
	TArray<float> VisibleFraction;
	/** [H, N] since 0.2; empty when absent. Azimuth index of the horizon sample that limits the view of the disc (SPEC 5.5). */
	TArray<int32> BlockerAzimuthIndex;
	/** [H, N] since 0.2, optional; empty when absent. Fraction of the disc above the horizon and not hidden by another body. */
	TArray<float> LitFraction;
	/** [N] since 0.4, optional; empty when absent. Share of the sample points of the stated landing ellipse at which the body is visible. */
	TArray<float> EllipseVisibleShare;
};

/** A rise or set event (SPEC 5.4). */
struct FLsnEvent
{
	FString Type;
	FString Body;
	int32 HeightIndex = 0;
	double EtS = 0.0;
	FString Utc;
	double AzimuthDeg = 0.0;
	double HorizonElevationDeg = 0.0;
	double ObstacleDistanceM = 0.0;
	FString Method;
	/** Since 0.4: range of the event time for the stated horizon error (SPEC 5.7); false when absent. */
	bool bHasBand = false;
	double EarliestEtS = 0.0;
	double LatestEtS = 0.0;
	FString EarliestUtc;
	FString LatestUtc;
};

/** The part of a method card the viewer shows next to a number (SPEC 3.2). */
struct FLsnMethodCard
{
	FString Title;
	FString Frame;
	FString TimeScale;
	FString ValidationStatus;
	/** The numeric entries of the card's "parameters" object. */
	TMap<FString, double> NumericParameters;
};

/** A run of neighbouring azimuths whose horizon is set by the same piece of terrain (SPEC 5.3, since 0.2). */
struct FLsnObstacle
{
	int32 Id = -1;
	int32 HeightIndex = 0;
	int32 AzimuthStartIndex = 0;
	int32 AzimuthCount = 0;
	double AzimuthStartDeg = 0.0;
	double AzimuthEndDeg = 0.0;
	double PeakAzimuthDeg = 0.0;
	double PeakElevationDeg = 0.0;
	double PeakDistanceM = 0.0;
	double PeakLatDeg = 0.0;
	double PeakLonDeg = 0.0;
	double PeakHeightM = 0.0;
	double DistanceMinM = 0.0;
	double DistanceMaxM = 0.0;
	/** The peak is closer than 1 km: the obstacle depends on single pixels of the elevation model. */
	bool bNearField = false;
	FString Method;
};

/** An obstacle that costs visible time compared with a smooth sphere (SPEC 5.5, since 0.2). */
struct FLsnBlocker
{
	FString Body;
	int32 HeightIndex = 0;
	int32 ObstacleId = -1;
	double LostS = 0.0;
	double ShareOfLost = 0.0;
	TArray<double> StartsEtS;
	TArray<double> EndsEtS;
	double PeakAzimuthDeg = 0.0;
	double PeakElevationDeg = 0.0;
	double PeakDistanceM = 0.0;
	bool bNearField = false;
	FString Method;
};

/**
 * What stands in the way of a body at a time sample, read from the package by the
 * recipe of SPEC 5.5. Nothing here is decided by the viewer.
 */
struct FLsnBlocking
{
	/** series.<BODY>.blocker_azimuth_index at the sample. */
	int32 AzimuthIndex = -1;
	double AzimuthDeg = 0.0;
	/** horizon.elevation_deg and horizon.distance_m at that azimuth sample (read there, not interpolated). */
	double HorizonElevationDeg = 0.0;
	double DistanceM = 0.0;
	/** horizon.obstacle_id at that azimuth sample, and its record. */
	int32 ObstacleId = -1;
	const FLsnObstacle* Obstacle = nullptr;
	/** The blocker record of that body, height and obstacle; null if the obstacle costs no time. */
	const FLsnBlocker* Blocker = nullptr;
	/** series.<BODY>.visible_fraction at the sample. */
	double VisibleFraction = 0.0;
	/**
	 * The Sun: any part of the disc is behind terrain (visible_fraction < 1).
	 * The Earth: the centre of the disc is not above the terrain (margin_deg <= 0),
	 * the condition a radio link is judged by.
	 */
	bool bHiddenOrPartly = false;
};

/** An interval set of a site timeline (SPEC 5.4, "Window"). Interval i is [StartsEtS[i], EndsEtS[i]). */
struct FLsnWindow
{
	FString Id;
	FString Subject;
	int32 HeightIndex = 0;
	TArray<double> StartsEtS;
	TArray<double> EndsEtS;
	/** The same instants as the package's own UTC strings. */
	TArray<FString> StartsUtc;
	TArray<FString> EndsUtc;
	/** The first interval starts, or the last interval ends, at the edge of the computed range: its true start or end is unknown. */
	bool bClippedStart = false;
	bool bClippedEnd = false;
	FString Method;
};

/** A summary number of a site timeline (SPEC 5.4, "Metric"). */
struct FLsnMetric
{
	FString Id;
	FString Label;
	/** -1 when the metric does not depend on the observer height. */
	int32 HeightIndex = -1;
	/** False when the package gives null. */
	bool bHasValue = false;
	double Value = 0.0;
	FString Unit;
	FString Method;
};

/**
 * Time from a selected instant to the next set or rise of a body, read from a
 * visibility window of the package. No rise or set is found here: the
 * interval boundaries are the package's event times.
 */
struct FLsnCountdown
{
	/** False when the package has no "<body>_visible" window for the height. */
	bool bAvailable = false;
	bool bVisibleNow = false;
	/** To the next set while visible, to the next rise while not. */
	double SecondsToChange = 0.0;
	/** The package has no such event inside its computed range; the true time is at least SecondsToChange. */
	bool bLowerBound = false;
	/** UTC string of that event as the package gives it; empty for a lower bound. */
	FString ChangeUtc;
	FString WindowId;
	FString Method;
};

struct LUNARSITENAVIGATOR_API FLsnSitePackage
{
	// --- header ---
	FString Directory;
	FString ContractVersion;
	FString PackageId;
	FString ContentSha256;
	FString Status;
	bool bSynthetic = false;
	FString SyntheticNotice;
	TArray<FString> Warnings;
	TMap<FString, FLsnMethodCard> Methods;

	// --- site (SPEC 5.2) ---
	FString SiteId;
	FString SiteName;
	FString Frame;
	double LatDeg = 0.0;
	double LonDeg = 0.0;
	double ReferenceRadiusM = 0.0;
	double SurfaceHeightM = 0.0;
	double RadiusM = 0.0;
	FVector PositionKm = FVector::ZeroVector;
	FVector EastBody = FVector::ZeroVector;
	FVector NorthBody = FVector::ZeroVector;
	FVector UpBody = FVector::ZeroVector;

	// --- horizon (SPEC 5.3) ---
	double AzimuthStartDeg = 0.0;
	double AzimuthStepDeg = 0.0;
	int32 AzimuthCount = 0;
	TArray<double> ObserverHeightsM;
	int32 DefaultHeightIndex = 0;
	double MaxRangeM = 0.0;
	/** [H, A] elevation angle of the terrain horizon, degrees. */
	TArray<float> HorizonElevationDeg;
	/** [H, A] arc length along the reference sphere to the point that sets the horizon, metres. */
	TArray<float> HorizonDistanceM;
	/** [H, A] optional; empty when absent. */
	TArray<float> ObstacleHeightM;
	FString HorizonElevationMethod;
	FString HorizonDistanceMethod;
	/** [H, A] since 0.2; empty when absent. Index into Obstacles, -1 where the horizon has no data. */
	TArray<int32> ObstacleId;
	TArray<FLsnObstacle> Obstacles;
	FString ObstacleMethod;

	// --- timeline (SPEC 5.4); absent when no time window was computed ---
	bool bHasTimeline = false;
	FString DirectionTableId;
	FLsnTimeGrid Time;
	TArray<FString> Bodies;
	TMap<FString, FLsnBodySeries> Series;
	TArray<FLsnEvent> Events;
	TArray<FLsnWindow> Windows;
	TArray<FLsnMetric> Metrics;
	/** Since 0.2; empty when absent. */
	TArray<FLsnBlocker> Blockers;
	FString BlockingMethod;

	// --- planning fields since 0.3 (SPEC 5.6 to 5.8); all optional ---
	TArray<FLsnRequirement> Requirements;
	/** The scenario's planned landing the slip reports refer to; empty if none. */
	FString PlannedLandingUtc;
	FLsnCalendar Calendar;
	TArray<FLsnOpportunity> Opportunities;
	FLsnUncertainty Uncertainty;
	FLsnHeightTrade HeightTrade;
	/** Since 0.9: what elevation data the result rests on; absent in older packages. */
	FLsnTerrainSource TerrainSource;

	/** Landing windows of a requirement for an observer height; null if the package has none. */
	const FLsnOpportunity* FindOpportunity(const FString& RequirementId, int32 InHeightIndex) const;

	/** True if the package carries the obstacle fields of contract 0.2. */
	bool HasObstacles() const { return Obstacles.Num() > 0 && ObstacleId.Num() == NumHeights() * AzimuthCount; }

	/** The azimuth indices of an obstacle's run, in order; a run may pass through azimuth 0. */
	void ObstacleRun(const FLsnObstacle& Obstacle, TArray<int32>& OutAzimuthIndices) const;

	/** The recipe of SPEC 5.5 for "SUN" or "EARTH" at a time sample. False if the package does not carry the fields. */
	bool BlockingAt(const FString& Body, int32 InHeightIndex, int32 TimeIndex, FLsnBlocking& Out) const;
	FString DirectionMethod;

	/** TDB seconds past J2000 of a (possibly fractional) sample position on the time axis. */
	double EtOfPosition(double SamplePosition) const { return Time.StartEtS + Time.StepS * SamplePosition; }

	const FLsnWindow* FindWindow(const FString& Id, int32 InHeightIndex) const;
	const FLsnMetric* FindMetric(const FString& Id, int32 InHeightIndex) const;

	/** Countdown for "SUN" or "EARTH" from the window "<body>_visible" of the observer height. */
	FLsnCountdown CountdownAt(const FString& Body, int32 InHeightIndex, double EtS) const;

	int32 NumHeights() const { return ObserverHeightsM.Num(); }
	double AzimuthDegAt(int32 AzimuthIndex) const { return AzimuthStartDeg + AzimuthStepDeg * AzimuthIndex; }
	float HorizonElevationAt(int32 HeightIndex, int32 AzimuthIndex) const { return HorizonElevationDeg[HeightIndex * AzimuthCount + AzimuthIndex]; }
	float HorizonDistanceAt(int32 HeightIndex, int32 AzimuthIndex) const { return HorizonDistanceM[HeightIndex * AzimuthCount + AzimuthIndex]; }

	/** Terrain horizon at any azimuth: linear, periodic interpolation between samples (SPEC 5.3). */
	double HorizonElevationInterpolated(int32 HeightIndex, double AzimuthDeg) const;

	const FLsnBodySeries* FindSeries(const FString& Body) const { return Series.Find(Body); }

	/**
	 * Distance from the site at which the horizon search of the package starts, metres
	 * (parameter "first_point_m" of the horizon method card); 0 if the package does not say.
	 * Terrain nearer than this is not part of horizon.elevation_deg.
	 */
	double HorizonSearchStartM() const;

	/** Validation status of a method id, or "unknown" if the card is missing. */
	FString ValidationStatusOf(const FString& MethodId) const;

	/**
	 * UTC label of a timeline sample. The contract lets a reader label sample i
	 * as start_utc + i * step_s only when no leap second falls in the range;
	 * otherwise this returns an empty string.
	 */
	FString UtcLabelOfSample(int32 SampleIndex) const;
};

/** Direction-table package (SPEC 6). Positions relative to the centre of the Moon, body-fixed, km. */
struct LUNARSITENAVIGATOR_API FLsnDirectionTable
{
	FString PackageId;
	FString Frame;
	FString Center;
	bool bSynthetic = false;
	TArray<FString> Bodies;
	FLsnTimeGrid Time;
	/** [N, B, 3] */
	TArray<double> PositionsKm;

	/** Position of a body at a record. Returns false if the body or the record is not in the table. */
	bool PositionKm(const FString& Body, int32 RecordIndex, FVector& OutPositionKm) const;
};

/** One entry of index.json (SPEC 7). */
struct FLsnIndexEntry
{
	FString Kind;
	FString PackageId;
	/** Relative to the package root, forward slashes. */
	FString Path;
	FString SiteId;
	FString Name;
	bool bSynthetic = false;
	bool bHasTimeline = false;
	/** Since 0.5, for kind "site_pairs": the sites the package compares. */
	TArray<FString> SiteIds;
	/**
	 * The programme or list a site belongs to, for grouping the site picker. Read from the
	 * optional index field "programme"; empty when the index has none.
	 */
	FString Programme;
};

namespace LsnPackageIO
{
	/** Loads a site package directory. On failure returns false and says why. */
	LUNARSITENAVIGATOR_API bool LoadSitePackage(const FString& PackageDirectory, FLsnSitePackage& OutPackage, FString& OutError);

	LUNARSITENAVIGATOR_API bool LoadDirectionTable(const FString& PackageDirectory, FLsnDirectionTable& OutTable, FString& OutError);

	/** Loads a site-pairs package directory (SPEC 6a, since 0.5). */
	LUNARSITENAVIGATOR_API bool LoadSitePairs(const FString& PackageDirectory, FLsnSitePairs& OutPairs, FString& OutError);

	/** Fills the optional planning fields of a site package from its manifest. Never fails: what is absent stays empty. */
	void ReadPlanningFields(const TSharedPtr<FJsonObject>& Manifest, FLsnSitePackage& InOutPackage);

	/** Reads horizon.terrain_source of a manifest (since 0.9); leaves bPresent false when it is absent. */
	LUNARSITENAVIGATOR_API void ReadTerrainSource(const TSharedPtr<FJsonObject>& Manifest, FLsnTerrainSource& OutSource);
	/** The same for a package directory, reading its manifest only (no arrays): for the site picker. */
	LUNARSITENAVIGATOR_API bool ReadTerrainSourceOfDirectory(const FString& PackageDirectory, FLsnTerrainSource& OutSource);

	/** Loads index.json of a package root. */
	LUNARSITENAVIGATOR_API bool LoadIndex(const FString& PackageRoot, TArray<FLsnIndexEntry>& OutEntries, FString& OutError);
}
