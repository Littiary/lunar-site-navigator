#pragma once

#include "CoreMinimal.h"

/**
 * Planning fields of the contract since 0.3 (SPEC 5.6 to 5.8 and 6a). All of them are
 * optional: a package that lacks one leaves the matching struct empty, and the viewer
 * hides the panel instead of filling it.
 */

/** A stated mission requirement on the landing time (SPEC 5.6). It is the scenario's, an example chosen by the team. */
struct FLsnRequirement
{
	FString Id;
	FString Label;
	double MissionDurationS = 0.0;
};

/** One lunar day of the calendar (SPEC 5.6). */
struct FLsnCalendarPeriod
{
	int32 Index = 0;
	double StartEtS = 0.0;
	double EndEtS = 0.0;
	FString StartUtc;
	FString EndUtc;
	/** False for the first and the last period, which are cut by the ends of the range. */
	bool bComplete = false;
};

struct FLsnCalendarQuantity
{
	FString Id;
	FString Label;
	FString Unit;
	FString Window;
	FString Method;
	/** [H, P]: flat index HeightIndex * NumPeriods + PeriodIndex. */
	TArray<double> Values;
};

struct LUNARSITENAVIGATOR_API FLsnCalendar
{
	bool bPresent = false;
	FString Definition;
	FString Method;
	TArray<FLsnCalendarPeriod> Periods;
	TArray<FLsnCalendarQuantity> Quantities;

	const FLsnCalendarQuantity* Find(const FString& Id) const;
	/** Value of a quantity for a height and a period; NaN if it is not there. */
	double Value(const FLsnCalendarQuantity& Quantity, int32 HeightIndex, int32 PeriodIndex) const;
};

/** The slip report of the scenario's planned landing, as the package gives it (SPEC 5.6). */
struct FLsnSlipReport
{
	bool bPresent = false;
	FString Utc;
	double EtS = 0.0;
	bool bFeasible = false;
	double SlipToleranceS = 0.0;
	double EarlyToleranceS = 0.0;
	bool bSlipIsLowerBound = false;
	/** False when the package gives null: no landing window left in the range. */
	bool bHasWait = false;
	double WaitS = 0.0;
	FString NextWindowStartUtc;
};

/** Landing windows of one requirement and observer height (SPEC 5.6). */
struct FLsnOpportunity
{
	FString RequirementId;
	int32 HeightIndex = 0;
	TArray<double> StartsEtS;
	TArray<double> EndsEtS;
	TArray<FString> StartsUtc;
	TArray<FString> EndsUtc;
	/** Last landing time that can be judged; later landings are in no window, whatever the truth. */
	double LatestLandingEtS = 0.0;
	FString LatestLandingUtc;
	bool bClippedStart = false;
	bool bClippedEnd = false;
	double FeasibleFraction = 0.0;
	int32 WindowCount = 0;
	double LongestWindowS = 0.0;
	TArray<double> FeasibleSPerPeriod;
	FLsnSlipReport Planned;
	FString Method;
};

/** One sample point of the stated landing ellipse (SPEC 5.7). */
struct FLsnEllipsePoint
{
	double LatDeg = 0.0;
	double LonDeg = 0.0;
	double SurfaceHeightM = 0.0;
	/** Visible time per body over the computed range; a body is missing where the package gives null. */
	TMap<FString, double> VisibleS;
};

struct FLsnEllipseStats
{
	double CentreS = 0.0;
	double MinS = 0.0;
	double MedianS = 0.0;
	double MaxS = 0.0;
};

/** Stated assumptions and what follows from them (SPEC 5.7). Neither is an error estimate. */
struct FLsnUncertainty
{
	bool bHasHorizonError = false;
	double HorizonErrorDeg = 0.0;
	FString HorizonAssumption;
	FString HorizonMethod;

	bool bHasEllipse = false;
	double SemiMajorM = 0.0;
	double SemiMinorM = 0.0;
	double AzimuthDeg = 0.0;
	int32 EllipseHeightIndex = 0;
	FString EllipseAssumption;
	FString EllipseMethod;
	TArray<FLsnEllipsePoint> Points;
	TMap<FString, FLsnEllipseStats> EllipseStats;
};

struct FLsnHeightTradeQuantity
{
	FString Id;
	FString Label;
	FString Window;
	FString Method;
	/** One value per listed height, seconds. */
	TArray<double> Values;
	/** Value minus the value at the lowest height. */
	TArray<double> ChangeS;
};

/** The observer heights of a package side by side (SPEC 5.8). Only the listed heights; nothing between them. */
struct LUNARSITENAVIGATOR_API FLsnHeightTrade
{
	bool bPresent = false;
	TArray<double> HeightsM;
	TArray<FLsnHeightTradeQuantity> Quantities;

	const FLsnHeightTradeQuantity* Find(const FString& Id) const;
};

/** One compared window of a pair of sites (SPEC 6a). */
struct FLsnPairWindow
{
	FString Window;
	double AS = 0.0;
	double BS = 0.0;
	double EitherS = 0.0;
	double BothS = 0.0;
	double NeitherS = 0.0;
	double EitherFraction = 0.0;
	double LongestNeitherS = 0.0;
	double GainOverBetterS = 0.0;
	/** False when the package gives null: the better site lacks nothing. */
	bool bHasCoveredShare = false;
	double CoveredShareOfBetterOutage = 0.0;
	FString Method;
};

struct FLsnSitePair
{
	FString SiteA;
	FString SiteB;
	double DistanceM = 0.0;
	TArray<FLsnPairWindow> Windows;
};

/** Site-pairs package (SPEC 6a): what every two sites of a scenario achieve together. */
struct LUNARSITENAVIGATOR_API FLsnSitePairs
{
	FString PackageId;
	FString ContractVersion;
	bool bSynthetic = false;
	/** Length of the common time range, seconds. */
	double RangeLengthS = 0.0;
	/** Site id -> package id of the site package the pairs were computed from. */
	TMap<FString, FString> SitePackageIds;
	TArray<FLsnSitePair> Pairs;
	/** Method id -> validation status. */
	TMap<FString, FString> MethodStatus;

	/** The pair of two sites, whichever is named first; null if the package has none. */
	const FLsnSitePair* FindPair(const FString& SiteIdOne, const FString& SiteIdTwo) const;
};
