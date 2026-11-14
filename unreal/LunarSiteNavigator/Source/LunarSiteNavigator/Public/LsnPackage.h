#pragma once

#include "CoreMinimal.h"
#include "LsnFrame.h"

/**
 * Readers for the package contract (docs/contract/SPEC.md, version 0.x).
 *
 * The scene shows what these readers return and computes no Sun or Earth position,
 * rise or set time, margin or visible fraction of its own.
 */

/** Uniform time axis (SPEC 3.5). */
struct FLsnTimeGrid
{
	double StartEtS = 0.0;
	double StepS = 0.0;
	int32 Count = 0;
	FString StartUtc;
	FString EndUtc;
	int32 LeapSecondsInRange = 0;
};

/** Series of one body in a site package (SPEC 5.4). */
struct FLsnBodySeries
{
	TArray<float> AzimuthDeg;        // [N]
	TArray<float> ElevationDeg;      // [N]
	TArray<float> AngularRadiusDeg;  // [N], empty if the package has none
	TArray<float> MarginDeg;         // [H, N]
	TArray<float> VisibleFraction;   // [H, N]
};

/** Rise or set event (SPEC 5.4). */
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
};

/** What the scene needs to draw one body at one time sample. Every value is read from the package. */
struct FLsnBodySky
{
	double AzimuthDeg = 0.0;
	double ElevationDeg = 0.0;
	bool bHasAngularRadius = false;
	double AngularRadiusDeg = 0.0;
	double MarginDeg = 0.0;
	double VisibleFraction = 0.0;
	/** Unit vector from the site towards the body, Unreal world axes. */
	FVector WorldDir = FVector::ZeroVector;
};

namespace LsnContract
{
	/** True for "0.<minor>". A reader must refuse another major version (SPEC 8). */
	LUNARSITENAVIGATOR_API bool IsSupportedVersion(const FString& Version);

	/**
	 * Package root used when none is given on the command line (-LsnPackageRoot=<dir>):
	 * <project>/Packages, the contract sample in the repository, then the local export of
	 * Scripts/sync_contract_sample.ps1. Empty if none of them has an index.json.
	 */
	LUNARSITENAVIGATOR_API FString FindPackageRoot();
}

/** Common header of a package (SPEC 3.3). */
struct LUNARSITENAVIGATOR_API FLsnPackageHeader
{
	FString ContractVersion;
	FString Kind;
	FString PackageId;
	FString ContentSha256;
	FString Status;
	bool bSynthetic = false;
	FString SyntheticNotice;
	TArray<FString> Warnings;
	/** Method id -> validation.status of its card. */
	TMap<FString, FString> MethodStatus;
	/** Method id -> title of its card. */
	TMap<FString, FString> MethodTitle;
};

/** Site package (SPEC 5). */
class LUNARSITENAVIGATOR_API FLsnSitePackage
{
public:
	bool Load(const FString& PackageDir, FString& OutError);

	FLsnPackageHeader Header;
	FString Directory;

	// site
	FString SiteId;
	FString Name;
	double LatDeg = 0.0;
	double LonDeg = 0.0;
	FString FrameName;
	double ReferenceRadiusM = 0.0;
	double SurfaceHeightM = 0.0;
	double RadiusM = 0.0;
	FLsnSiteFrame Frame;

	// horizon, arrays in [H, A] order: flat index H * AzimuthCount + A
	double AzimuthStepDeg = 0.0;
	int32 AzimuthCount = 0;
	TArray<double> ObserverHeightsM;
	int32 DefaultHeightIndex = 0;
	double MaxRangeM = 0.0;
	TArray<float> HorizonElevationDeg;
	TArray<float> HorizonDistanceM;
	bool bHasObstaclePoints = false;
	TArray<float> ObstacleHeightM;
	TArray<double> ObstacleLatDeg;
	TArray<double> ObstacleLonDeg;

	// timeline, absent when no time window was computed
	bool bHasTimeline = false;
	FString DirectionTableId;
	FLsnTimeGrid Time;
	TArray<FString> Bodies;
	TMap<FString, FLsnBodySeries> Series;
	TArray<FLsnEvent> Events;

	int32 NumHeights() const { return ObserverHeightsM.Num(); }

	/** Horizon elevation at any azimuth: linear, periodic interpolation between samples (SPEC 5.3). */
	double InterpolatedHorizonElevationDeg(int32 HeightIndex, double AzDeg) const;

	/** Nearest azimuth sample; obstacle fields must be read there and never interpolated (SPEC 5.3). */
	int32 NearestAzimuthIndex(double AzDeg) const;

	/** Direction, size and visibility of a body at a time sample. False if the package does not have it. */
	bool GetBodySky(const FString& Body, int32 TimeIndex, int32 HeightIndex, FLsnBodySky& Out) const;

	/** Observer position for a height index, Unreal world, centimetres. */
	FVector ObserverWorldCm(int32 HeightIndex) const;

	/** UTC label of a time sample; empty if the grid does not allow labelling (leap second in range). */
	FString UtcLabel(int32 TimeIndex) const;
};

/** Direction-table package (SPEC 6). */
class LUNARSITENAVIGATOR_API FLsnDirectionTable
{
public:
	bool Load(const FString& PackageDir, FString& OutError);

	FLsnPackageHeader Header;
	FString FrameName;
	TArray<FString> Bodies;
	FLsnTimeGrid Time;
	TArray<double> PositionsKm;  // [N, B, 3]
	TMap<FString, double> BodyRadiiKm;

	/** Position of a body relative to the centre of the Moon, body-fixed, kilometres. */
	FVector PositionKm(int32 TimeIndex, int32 BodyIndex) const;
};

/** One entry of index.json (SPEC 7). */
struct FLsnIndexEntry
{
	FString Kind;
	FString PackageId;
	FString Path;
	bool bSynthetic = false;
	FString Status;
	FString SiteId;
	FString Name;
	bool bHasTimeline = false;
};

struct LUNARSITENAVIGATOR_API FLsnIndex
{
	bool Load(const FString& PackageRoot, FString& OutError);

	FString Root;
	TArray<FLsnIndexEntry> Packages;

	/** Absolute directory of the first package of a kind, optionally restricted to a site id. Empty if none. */
	FString FindPackageDir(const FString& Kind, const FString& SiteId = FString()) const;
	FString FindPackageDirById(const FString& PackageId) const;
};
