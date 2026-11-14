// Contract 0.3 to 0.5 in the planner: calendar, landing windows and slip tolerance,
// uncertainty band, landing ellipse, mast-height trade, site pairs.
//
// Criteria and tolerances, written before the first run:
//
// S. Reader. The sample gives a calendar whose periods follow each other without gaps and
//    cover the time axis, with one value per observer height and period for every
//    quantity; requirements with a label; one opportunity per requirement and height.
//
// T. Slip of a selected landing time. Whether a landing at the selected time meets the
//    requirement, and by how much it can slip, is read from the landing windows of the
//    package: the selected time lies in a window or not, and the slip is the distance to
//    the end of that window. On a hand-made opportunity this is exact (1e-9 s). At the
//    scenario's own planned landing it equals the slip report the package carries
//    (feasible flag, slip, early tolerance and wait within 1e-3 s): the package is the
//    reference, this reading must agree with it. A time after latest_landing is "cannot
//    be judged", never "not feasible".
//
// U. Uncertainty. At every sample of the sample package: inside the certain window
//    implies inside the visible window implies inside the possible window. The band of
//    an event contains the event time. A countdown that ends at an event states the
//    package's earliest and latest time of that event.
//
// V. Mast-height trade and site pairs are tables of package numbers: one value per
//    listed height, change 0 at the lowest; for a pair, either + neither is the length
//    of the range (1e-3 s). The lines shown are those numbers with seconds turned into
//    hours or days and fractions into per cent.
//
// X. A package without these fields (the pinned sample with the fields removed, and any
//    0.1 package) gives no calendar, no landing sentence, no band and no panel lines.

#include "Tests/LsnTestSupport.h"
#include "Planner/LsnPlanner.h"
#include "Scene/LsnHud.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPlanningHandMadeTest, "LunarSiteNavigator.Planner.LandingSlipAndPanels", LsnTest::Flags)
bool FLsnPlanningHandMadeTest::RunTest(const FString& Parameters)
{
	// T. Hand-made opportunity: landing windows 100-200 s and 300-400 s, judged up to 450 s.
	FLsnOpportunity O;
	O.RequirementId = TEXT("example");
	O.StartsEtS = { 100.0, 300.0 };
	O.EndsEtS = { 200.0, 400.0 };
	O.StartsUtc = { TEXT("s1"), TEXT("s2") };
	O.EndsUtc = { TEXT("e1"), TEXT("e2") };
	O.LatestLandingEtS = 450.0;

	FLsnLandingCheck C = LsnPlanner::LandingAt(O, 150.0);
	TestTrue(TEXT("T: 150 s can be judged and is feasible"), C.bJudgeable && C.bFeasible);
	TestEqual(TEXT("T: slip 50 s"), C.SlipS, 50.0, 1e-9);
	TestEqual(TEXT("T: early 50 s"), C.EarlyS, 50.0, 1e-9);
	TestFalse(TEXT("T: not a lower bound"), C.bSlipIsLowerBound);
	TestEqual(TEXT("T: wait from the end of this window to the next"), C.WaitAfterWindowS, 100.0, 1e-9);

	C = LsnPlanner::LandingAt(O, 250.0);
	TestTrue(TEXT("T: 250 s can be judged"), C.bJudgeable);
	TestFalse(TEXT("T: 250 s is not feasible"), C.bFeasible);
	TestTrue(TEXT("T: there is a next window"), C.bHasNextWindow);
	TestEqual(TEXT("T: wait 50 s"), C.WaitS, 50.0, 1e-9);
	TestEqual(TEXT("T: next window start is the package string"), C.NextWindowStartUtc, FString(TEXT("s2")));
	TestEqual(TEXT("T: next window length"), C.NextWindowLengthS, 100.0, 1e-9);

	C = LsnPlanner::LandingAt(O, 420.0);
	TestTrue(TEXT("T: 420 s can be judged, not feasible, no further window"), C.bJudgeable && !C.bFeasible && !C.bHasNextWindow);
	C = LsnPlanner::LandingAt(O, 460.0);
	TestFalse(TEXT("T: after latest_landing nothing can be judged"), C.bJudgeable);
	TestFalse(TEXT("T: and it is not called feasible"), C.bFeasible);

	O.EndsEtS[1] = 450.0;
	O.bClippedEnd = true;
	C = LsnPlanner::LandingAt(O, 350.0);
	TestTrue(TEXT("T: a window cut by latest_landing gives a lower bound"), C.bFeasible && C.bSlipIsLowerBound);
	TestEqual(TEXT("T: at least 100 s"), C.SlipS, 100.0, 1e-9);

	// Wording.
	O.bClippedEnd = false;
	O.EndsEtS[1] = 400.0;
	TestEqual(TEXT("feasible"), LsnHudText::LandingSentence(LsnPlanner::LandingAt(O, 100.0 + 0.0)),
		FString(TEXT("landing now meets the requirement; it can slip by 1 min 40 s (earlier: 0 min 00 s)")));
	TestTrue(TEXT("not feasible, with the wait"), LsnHudText::LandingSentence(LsnPlanner::LandingAt(O, 250.0)).StartsWith(TEXT("landing now does not meet the requirement; next landing window in 0 min 50 s")));
	TestTrue(TEXT("no window left"), LsnHudText::LandingSentence(LsnPlanner::LandingAt(O, 420.0)).Contains(TEXT("no further landing window in the computed range")));
	TestTrue(TEXT("cannot be judged"), LsnHudText::LandingSentence(LsnPlanner::LandingAt(O, 460.0)).Contains(TEXT("cannot be judged")));

	// V. Mast-height trade lines.
	FLsnSitePackage P;
	P.HeightTrade.bPresent = true;
	P.HeightTrade.HeightsM = { 0.0, 2.0, 10.0 };
	FLsnHeightTradeQuantity Sun;
	Sun.Id = TEXT("sun_visible_s");
	Sun.Values = { 3600.0 * 100.0, 3600.0 * 110.0, 3600.0 * 150.5 };
	Sun.ChangeS = { 0.0, 3600.0 * 10.0, 3600.0 * 50.5 };
	FLsnHeightTradeQuantity Outage;
	Outage.Id = TEXT("sun_longest_outage_s");
	Outage.Values = { 3600.0 * 200.0, 3600.0 * 190.0, 3600.0 * 120.0 };
	Outage.ChangeS = { 0.0, -3600.0 * 10.0, -3600.0 * 80.0 };
	P.HeightTrade.Quantities = { Sun, Outage };
	TArray<FString> Lines;
	LsnPlanner::BuildHeightTradeLines(P, Lines);
	TestEqual(TEXT("V: a heading and one line per height"), Lines.Num(), 4);
	if (Lines.Num() == 4)
	{
		TestEqual(TEXT("V: lowest height"), Lines[1], FString(TEXT("   0 m   Sun 100.0 h          longest outage 200.0 h")));
		TestEqual(TEXT("V: 2 m"), Lines[2], FString(TEXT("   2 m   Sun 110.0 h (+10.0)  longest outage 190.0 h (-10.0)")));
		TestEqual(TEXT("V: 10 m"), Lines[3], FString(TEXT("  10 m   Sun 150.5 h (+50.5)  longest outage 120.0 h (-80.0)")));
	}
	FLsnSitePackage Empty;
	LsnPlanner::BuildHeightTradeLines(Empty, Lines);
	TestEqual(TEXT("X: no height trade, no lines"), Lines.Num(), 0);

	// V. Pair lines.
	FLsnSitePairs Pairs;
	FLsnSitePair Pair;
	Pair.SiteA = TEXT("a");
	Pair.SiteB = TEXT("b");
	Pair.DistanceM = 22801.0;
	FLsnPairWindow W;
	W.Window = TEXT("sun_visible");
	W.AS = 3600.0 * 100.0;
	W.BS = 3600.0 * 120.0;
	W.EitherS = 3600.0 * 150.0;
	W.EitherFraction = 0.625;
	W.LongestNeitherS = 3600.0 * 30.0;
	W.GainOverBetterS = 3600.0 * 30.0;
	W.bHasCoveredShare = true;
	W.CoveredShareOfBetterOutage = 0.25;
	Pair.Windows.Add(W);
	Pairs.Pairs.Add(Pair);
	TestTrue(TEXT("a pair is found whichever site is named first"), Pairs.FindPair(TEXT("b"), TEXT("a")) == &Pairs.Pairs[0] && Pairs.FindPair(TEXT("a"), TEXT("b")) == &Pairs.Pairs[0]);
	TestTrue(TEXT("no pair with a site that is not in the package"), Pairs.FindPair(TEXT("a"), TEXT("c")) == nullptr);
	LsnPlanner::BuildPairLines(Pairs.Pairs[0], Lines);
	TestEqual(TEXT("V: distance line and one line per compared window"), Lines.Num(), 2);
	if (Lines.Num() == 2)
	{
		TestEqual(TEXT("V: distance"), Lines[0], FString(TEXT("22.8 km apart")));
		TestEqual(TEXT("V: Sun"), Lines[1], FString(TEXT("Sun at one site at least 62.5 % of the window (+30.0 h over the better site, 25 % of its outage); longest joint outage 30.0 h")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPlanningSampleTest, "LunarSiteNavigator.Package.PlanningFieldsOfTheSample", LsnTest::Flags)
bool FLsnPlanningSampleTest::RunTest(const FString& Parameters)
{
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("the sample package loads (%s)"), *Error),
		LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const int32 H = P.NumHeights();
	const double AxisStart = P.Time.StartEtS, AxisEnd = P.EtOfPosition(P.Time.Count - 1);

	// S. Calendar.
	if (TestTrue(TEXT("S: the sample has a calendar"), P.Calendar.bPresent && P.Calendar.Periods.Num() > 0))
	{
		TestEqual(TEXT("S: the first period starts with the time axis"), P.Calendar.Periods[0].StartEtS, AxisStart, 1e-3);
		TestEqual(TEXT("S: the last period ends with the time axis"), P.Calendar.Periods.Last().EndEtS, AxisEnd, 1e-3);
		for (int32 I = 1; I < P.Calendar.Periods.Num(); ++I)
		{
			TestEqual(TEXT("S: periods follow each other without gaps"), P.Calendar.Periods[I].StartEtS, P.Calendar.Periods[I - 1].EndEtS, 1e-3);
		}
		TestTrue(TEXT("S: Sun-visible time per lunar day is there"), P.Calendar.Find(TEXT("sun_visible_s")) != nullptr);
		for (const FLsnCalendarQuantity& Q : P.Calendar.Quantities)
		{
			TestEqual(FString::Printf(TEXT("S: %s has one value per height and period"), *Q.Id), Q.Values.Num(), H * P.Calendar.Periods.Num());
		}
	}

	// S, T. Requirements and opportunities; the package's slip report as the reference.
	TestTrue(TEXT("S: the sample states a requirement with a label"), P.Requirements.Num() > 0 && !P.Requirements[0].Label.IsEmpty());
	int32 Compared = 0;
	for (const FLsnRequirement& R : P.Requirements)
	{
		for (int32 Height = 0; Height < H; ++Height)
		{
			const FLsnOpportunity* O = P.FindOpportunity(R.Id, Height);
			if (!TestNotNull(*FString::Printf(TEXT("S: opportunity of %s at height %d"), *R.Id, Height), O))
			{
				continue;
			}
			TestEqual(TEXT("S: as many window starts as ends"), O->StartsEtS.Num(), O->EndsEtS.Num());
			TestEqual(TEXT("S: feasible time per period, one value per period"), O->FeasibleSPerPeriod.Num(), P.Calendar.Periods.Num());
			if (!O->Planned.bPresent)
			{
				continue;
			}
			const FLsnLandingCheck C = LsnPlanner::LandingAt(*O, O->Planned.EtS);
			TestTrue(TEXT("T: the planned landing can be judged"), C.bJudgeable);
			TestEqual(TEXT("T: feasible as the package says"), C.bFeasible, O->Planned.bFeasible);
			TestEqual(TEXT("T: slip tolerance as the package says"), C.SlipS, O->Planned.SlipToleranceS, 1e-3);
			TestEqual(TEXT("T: early tolerance as the package says"), C.EarlyS, O->Planned.EarlyToleranceS, 1e-3);
			TestEqual(TEXT("T: lower-bound flag as the package says"), C.bSlipIsLowerBound, O->Planned.bSlipIsLowerBound);
			if (O->Planned.bHasWait)
			{
				TestEqual(TEXT("T: wait as the package says"), C.WaitS, O->Planned.WaitS, 1e-3);
			}
			++Compared;
		}
	}
	TestTrue(TEXT("T: slip reports of the package were compared"), Compared > 0);

	// U. Certain inside visible inside possible; event bands.
	if (TestTrue(TEXT("U: the sample states a horizon error"), P.Uncertainty.bHasHorizonError && P.Uncertainty.HorizonErrorDeg > 0.0 && !P.Uncertainty.HorizonAssumption.IsEmpty()))
	{
		int32 Broken = 0;
		for (const TCHAR* Body : { TEXT("sun"), TEXT("earth") })
		{
			for (int32 Height = 0; Height < H; ++Height)
			{
				const FLsnWindow* Certain = P.FindWindow(FString(Body) + TEXT("_visible_certain"), Height);
				const FLsnWindow* Visible = P.FindWindow(FString(Body) + TEXT("_visible"), Height);
				const FLsnWindow* Possible = P.FindWindow(FString(Body) + TEXT("_visible_possible"), Height);
				if (!TestTrue(TEXT("U: the three windows exist"), Certain && Visible && Possible))
				{
					continue;
				}
				for (int32 T = 0; T < P.Time.Count; ++T)
				{
					const double EtS = P.EtOfPosition(T);
					const bool bCertain = LsnPlanner::WindowHoldsAt(*Certain, EtS), bVisible = LsnPlanner::WindowHoldsAt(*Visible, EtS), bPossible = LsnPlanner::WindowHoldsAt(*Possible, EtS);
					Broken += ((bCertain && !bVisible) || (bVisible && !bPossible)) ? 1 : 0;
				}
			}
		}
		TestEqual(TEXT("U: samples where certain, visible, possible are not nested"), Broken, 0);
	}
	int32 Banded = 0, Outside = 0;
	for (const FLsnEvent& E : P.Events)
	{
		if (E.bHasBand)
		{
			++Banded;
			Outside += (E.EarliestEtS <= E.EtS + 1e-6 && E.EtS <= E.LatestEtS + 1e-6) ? 0 : 1;
		}
	}
	TestTrue(TEXT("U: events carry a band"), Banded > 0);
	TestEqual(TEXT("U: events outside their own band"), Outside, 0);

	// U. A countdown that ends at an event states the band of that event.
	bool bFoundBandedCountdown = false;
	for (int32 T = 0; T < P.Time.Count && !bFoundBandedCountdown; ++T)
	{
		const double EtS = P.EtOfPosition(T);
		const FLsnCountdown Countdown = P.CountdownAt(TEXT("SUN"), P.DefaultHeightIndex, EtS);
		const FLsnEvent* Event = LsnPlanner::EventEndingCountdown(P, TEXT("SUN"), P.DefaultHeightIndex, EtS, Countdown);
		if (Event && Event->bHasBand && Event->LatestEtS > Event->EarliestEtS)
		{
			const FString Band = LsnHudText::CountdownBandSentence(P, EtS, *Event);
			TestTrue(TEXT("U: the band sentence names the stated error"), Band.Contains(FString::Printf(TEXT("%.2f deg"), P.Uncertainty.HorizonErrorDeg)));
			TestTrue(TEXT("U: the band sentence gives a range"), Band.Contains(TEXT(" to ")));
			TestEqual(TEXT("U: the event is the one the countdown runs to"), Event->EtS, EtS + Countdown.SecondsToChange, 1.0);
			bFoundBandedCountdown = true;
		}
	}
	TestTrue(TEXT("U: a countdown with a band was found in the sample"), bFoundBandedCountdown);

	// Landing ellipse.
	if (TestTrue(TEXT("the sample states a landing ellipse"), P.Uncertainty.bHasEllipse && P.Uncertainty.Points.Num() > 0))
	{
		const FLsnSiteFrame Frame = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);
		const FVector2D First = LsnPlanner::EllipsePointEastNorthM(Frame, P.Uncertainty.Points[0]);
		TestTrue(TEXT("the first point of the ellipse is the site itself (1 m)"), First.Size() < 1.0);
		double Farthest = 0.0;
		for (const FLsnEllipsePoint& Point : P.Uncertainty.Points)
		{
			Farthest = FMath::Max(Farthest, LsnPlanner::EllipsePointEastNorthM(Frame, Point).Size());
		}
		TestTrue(TEXT("no point lies outside the stated semi-major axis (1 %)"), Farthest <= 1.01 * P.Uncertainty.SemiMajorM);
		const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN"));
		TestTrue(TEXT("the share of ellipse points with the Sun in view is a series"), Sun && Sun->EllipseVisibleShare.Num() == P.Time.Count);
		TestTrue(TEXT("ellipse statistics for the Sun"), P.Uncertainty.EllipseStats.Contains(TEXT("SUN")));
	}

	// V. Mast-height trade.
	if (TestTrue(TEXT("V: the sample has a mast-height trade"), P.HeightTrade.bPresent))
	{
		TestEqual(TEXT("V: its heights are the heights of the package"), P.HeightTrade.HeightsM.Num(), H);
		for (const FLsnHeightTradeQuantity& Q : P.HeightTrade.Quantities)
		{
			TestTrue(FString::Printf(TEXT("V: %s has one value and one change per height, change 0 at the lowest"), *Q.Id),
				Q.Values.Num() == H && Q.ChangeS.Num() == H && FMath::Abs(Q.ChangeS[0]) < 1e-9);
		}
	}

	// V. Site pairs of the sample root.
	TArray<FLsnIndexEntry> Entries;
	FLsnSitePairs Pairs;
	bool bPairsLoaded = false;
	if (LsnPackageIO::LoadIndex(LsnTest::FixtureRoot(), Entries, Error))
	{
		for (const FLsnIndexEntry& Entry : Entries)
		{
			if (Entry.Kind == TEXT("site_pairs"))
			{
				bPairsLoaded = LsnPackageIO::LoadSitePairs(FPaths::Combine(LsnTest::FixtureRoot(), Entry.Path), Pairs, Error);
			}
		}
	}
	if (TestTrue(FString::Printf(TEXT("V: the site-pairs package of the sample loads (%s)"), *Error), bPairsLoaded) && TestTrue(TEXT("V: it has a pair"), Pairs.Pairs.Num() > 0))
	{
		for (const FLsnPairWindow& W : Pairs.Pairs[0].Windows)
		{
			TestEqual(FString::Printf(TEXT("V: %s: either + neither is the length of the range"), *W.Window), W.EitherS + W.NeitherS, Pairs.RangeLengthS, 1e-3);
		}
		TestTrue(TEXT("V: the pair is found by its two site ids"), Pairs.FindPair(Pairs.Pairs[0].SiteB, Pairs.Pairs[0].SiteA) != nullptr);
	}

	// X. Without the fields nothing is shown.
	FLsnSitePackage Old = P;
	Old.Calendar = FLsnCalendar();
	Old.Requirements.Reset();
	Old.Opportunities.Reset();
	Old.Uncertainty = FLsnUncertainty();
	Old.HeightTrade = FLsnHeightTrade();
	TArray<FString> Lines;
	LsnPlanner::BuildHeightTradeLines(Old, Lines);
	TestEqual(TEXT("X: no mast lines"), Lines.Num(), 0);
	TestTrue(TEXT("X: no opportunity"), Old.FindOpportunity(TEXT("example-surface-stay"), 0) == nullptr);
	TestFalse(TEXT("X: no calendar"), Old.Calendar.bPresent);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPlanningPublishedTest, "LunarSiteNavigator.Real.PlanningFieldsOnlyWhenPublished", LsnTest::Flags)
bool FLsnPlanningPublishedTest::RunTest(const FString& Parameters)
{
	// The published packages decide what the planner can show. This test states, per site,
	// which planning fields they carry, and checks the slip report where there is one.
	const FString Root = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Sites;
	FString Error;
	if (Root.IsEmpty() || !LsnPlanner::ListSites(Root, Sites, Error))
	{
		AddWarning(FString::Printf(TEXT("NOT RUN: no published packages found. %s"), *Error));
		return true;
	}
	for (const FLsnIndexEntry& Entry : Sites)
	{
		FLsnSitePackage P;
		if (!TestTrue(FString::Printf(TEXT("%s loads (%s)"), *Entry.SiteId, *Error), LsnPackageIO::LoadSitePackage(FPaths::Combine(Root, Entry.Path), P, Error)))
		{
			continue;
		}
		int32 Compared = 0;
		for (const FLsnOpportunity& O : P.Opportunities)
		{
			if (O.Planned.bPresent)
			{
				const FLsnLandingCheck C = LsnPlanner::LandingAt(O, O.Planned.EtS);
				TestEqual(FString::Printf(TEXT("%s: feasible as the package says"), *P.SiteId), C.bFeasible, O.Planned.bFeasible);
				TestEqual(FString::Printf(TEXT("%s: slip tolerance as the package says"), *P.SiteId), C.SlipS, O.Planned.SlipToleranceS, 1e-3);
				++Compared;
			}
		}
		AddInfo(FString::Printf(TEXT("%s (%s, contract %s): obstacles %s, calendar %s (%d lunar days), requirements %d, opportunities %d (%d slip reports compared), horizon-error band %s, landing ellipse %s, mast-height trade %s"),
			*P.SiteId, *P.PackageId, *P.ContractVersion, P.HasObstacles() ? TEXT("yes") : TEXT("no"), P.Calendar.bPresent ? TEXT("yes") : TEXT("no"), P.Calendar.Periods.Num(),
			P.Requirements.Num(), P.Opportunities.Num(), Compared, P.Uncertainty.bHasHorizonError ? TEXT("yes") : TEXT("no"), P.Uncertainty.bHasEllipse ? TEXT("yes") : TEXT("no"),
			P.HeightTrade.bPresent ? TEXT("yes") : TEXT("no")));
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
