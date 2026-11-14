// Site picker, custom coordinates, terrain source.
//
// Criteria, written before the first run:
//
// V. The site picker scales to the curated list.
//    With a hand-made list of 20 sites in 7 groups, for the windows 1280 x 720 and
//    1920 x 1080, one view and side by side:
//    1. the sheet lies in the window, below the header and above the time strips; side by
//       side it spans both halves like the bar of buttons, and no row or box lies across
//       the middle of the window;
//    2. every group has one header row, in the order in which the groups first appear in
//       the list, and every site has one row after its group's header;
//    3. every site row has three boxes (show, pin left, pin right) that lie in the row and
//       do not overlap each other; rows do not overlap; a row is at least 18 px high;
//    4. the boxes for the custom coordinates (latitude, longitude, compute) lie in the sheet
//       and overlap no row and not each other;
//    5. a point in the middle of a box gives that box's meaning and site; a point in a group
//       header or outside the sheet gives nothing.
//
// V2. (Revision of 14 November 2026 for the interface pass, written before its first run.
//    It replaces V.1 to V.5: the list moved into the drawer, in one column that scrolls,
//    with a search field.)
//    With a hand-made list of 20 sites in 7 groups, for the windows 1280 x 720, 1920 x 1080
//    and 2560 x 1440, one view and side by side, and for every place the list can be
//    scrolled to:
//    1. the sheet is the content of the drawer; every row lies in the sheet, rows do not
//       overlap, a row is at least 18 px high;
//    2. the first row shown is a group header, the last row shown is never one (no header
//       stands alone), and every site row stands under the header of its group;
//    3. every site row has three boxes (show, pin left, pin right) that lie in the row and
//       do not overlap each other;
//    4. the search field and the boxes for the custom coordinates lie in the sheet and
//       overlap no row and not each other;
//    5. a point in the middle of a box gives that box's meaning and site; a point in a group
//       header or outside the sheet gives nothing;
//    6. scrolled through, every site is shown at some place, and the groups appear in the
//       order of the list;
//    7. with the sites of one group taken out by the search, neither they nor the header of
//       their group are shown anywhere.
//
// W. Custom coordinates are handed to the science core, not computed here.
//    1. A latitude is accepted from -90 to 90 and a longitude from -180 to 360, as plain
//       decimal numbers; empty text, text with two points, letters and values outside the
//       range are refused.
//    2. The command is the core's own: the arguments are exactly
//       -m lsncore site --lat <lat> --lon <lon> --name "<name>" --out "<root>"
//       with the numbers as they were typed, and the name says the coordinates.
//    3. (Added on 2026-11-14 for the two-step flow, before its first run.) The second step,
//       the timeline, is another command of the core, given to the view as a template with
//       the places {lat}, {lon}, {name} and {out}. The view fills in the same four values
//       and nothing else; without a template there is no second step (empty arguments).
//       The share of a step that is shown as done is the time it has run over the time
//       the core's documentation states for it, never more than 0.95 while it still runs.
//
// X. The resolution class of the terrain is the package's.
//    A manifest with horizon.terrain_source (contract 0.9) gives its resolution_class and
//    the pixel size at the site unchanged; a manifest without it gives none, and then
//    nothing is shown.

#include "Tests/LsnTestSupport.h"
#include "Dom/JsonObject.h"
#include "Planner/LsnPlanner.h"
#include "Scene/LsnHud.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPickerLayoutTest, "LunarSiteNavigator.Planner.SitePicker", LsnTest::Flags)
bool FLsnPickerLayoutTest::RunTest(const FString& Parameters)
{
	// 20 sites in 7 groups, the groups not sorted.
	const TCHAR* GroupNames[] = { TEXT("Apollo"), TEXT("Chang'e"), TEXT("Chandrayaan"), TEXT("SLIM"), TEXT("Intuitive Machines"), TEXT("Blue Ghost"), TEXT("Artemis III candidate regions") };
	const int32 GroupSizes[] = { 6, 3, 1, 1, 1, 1, 7 };
	TArray<FString> GroupOfSite;
	for (int32 G = 0; G < UE_ARRAY_COUNT(GroupNames); ++G)
	{
		for (int32 I = 0; I < GroupSizes[G]; ++I)
		{
			GroupOfSite.Add(GroupNames[G]);
		}
	}
	TestEqual(TEXT("the hand-made list has 20 sites"), GroupOfSite.Num(), 20);
	// The search takes the three sites of the second group out.
	TArray<bool> Hidden;
	Hidden.Init(false, GroupOfSite.Num());
	Hidden[6] = Hidden[7] = Hidden[8] = true;
	for (const FVector2D& Size : { FVector2D(1280, 720), FVector2D(1920, 1080), FVector2D(2560, 1440) })
	{
		for (int32 Variant = 0; Variant < 4; ++Variant)
		{
			const bool bComparing = (Variant & 1) != 0, bSearch = (Variant & 2) != 0;
			const FString Where = FString::Printf(TEXT("%.0f x %.0f%s%s"), Size.X, Size.Y, bComparing ? TEXT(" side by side") : TEXT(""), bSearch ? TEXT(", with a search") : TEXT(""));
			const FBox2D Content = FLsnToolbar::DrawerContent(Size.X, Size.Y, bComparing);
			TSet<int32> SitesSeen;
			TArray<FString> HeaderOrder;
			const int32 NumRows = FLsnSitePicker::Make(Size.X, Size.Y, bComparing, GroupOfSite, bSearch ? &Hidden : nullptr, 0).NumRows;
			TestEqual(Where + TEXT(": rows of the whole list"), NumRows, bSearch ? 17 + 6 : 20 + 7);
			for (int32 First = 0; First < NumRows; ++First)
			{
				const FLsnSitePicker Picker = FLsnSitePicker::Make(Size.X, Size.Y, bComparing, GroupOfSite, bSearch ? &Hidden : nullptr, First);
				const FString At = Where + FString::Printf(TEXT(", scrolled to %d"), First);
				TestTrue(At + TEXT(": the sheet is the content of the drawer"), Picker.Sheet.Min.Equals(Content.Min, 0.5) && Picker.Sheet.Max.Equals(Content.Max, 0.5));
				if (!TestTrue(At + TEXT(": rows are shown"), Picker.Rows.Num() > 0))
				{
					continue;
				}
				TestTrue(At + TEXT(": the first row is a group header"), Picker.Rows[0].SiteIndex < 0);
				TestTrue(At + TEXT(": the last row is not a group header"), Picker.Rows.Last().SiteIndex >= 0);
				FString CurrentGroup;
				for (int32 I = 0; I < Picker.Rows.Num(); ++I)
				{
					const FLsnPickerRow& Row = Picker.Rows[I];
					const FString Name = At + FString::Printf(TEXT(": row %d"), I);
					// Half a pixel of slack: a row may touch the edge of the sheet.
					TestTrue(Name + TEXT(" lies in the sheet"), Picker.Sheet.ExpandBy(0.5).IsInside(Row.Row.Min) && Picker.Sheet.ExpandBy(0.5).IsInside(Row.Row.Max));
					TestTrue(Name + TEXT(" is at least 18 px high"), Row.Row.Max.Y - Row.Row.Min.Y >= 18.0);
					for (int32 J = I + 1; J < Picker.Rows.Num(); ++J)
					{
						TestFalse(Name + TEXT(" does not overlap another row"), Row.Row.ExpandBy(-0.5).Intersect(Picker.Rows[J].Row.ExpandBy(-0.5)));
					}
					for (const FBox2D& Box : { Picker.LatField, Picker.LonField, Picker.Compute, Picker.SearchField })
					{
						TestFalse(Name + TEXT(" does not overlap a field"), Row.Row.ExpandBy(-0.5).Intersect(Box));
					}
					int32 HitSite = -2;
					if (Row.SiteIndex < 0)
					{
						CurrentGroup = Row.Group;
						if (HeaderOrder.Num() == 0 || HeaderOrder.Last() != Row.Group)
						{
							HeaderOrder.AddUnique(Row.Group);
						}
						TestEqual(Name + TEXT(" (group header) gives nothing"), Picker.HitAt(Row.Row.GetCenter(), HitSite), ELsnPickerHit::None);
						continue;
					}
					TestEqual(Name + TEXT(" stands under the header of its group"), GroupOfSite[Row.SiteIndex], CurrentGroup);
					TestFalse(Name + TEXT(" is not a site the search took out"), bSearch && Hidden[Row.SiteIndex]);
					SitesSeen.Add(Row.SiteIndex);
					const TPair<const FBox2D*, ELsnPickerHit> Boxes[] = { { &Row.Show, ELsnPickerHit::Show }, { &Row.PinLeft, ELsnPickerHit::PinLeft }, { &Row.PinRight, ELsnPickerHit::PinRight } };
					for (int32 B = 0; B < 3; ++B)
					{
						TestTrue(Name + TEXT(": a box lies in its row"), Row.Row.ExpandBy(0.5).IsInside(Boxes[B].Key->Min) && Row.Row.ExpandBy(0.5).IsInside(Boxes[B].Key->Max));
						TestEqual(Name + TEXT(": the middle of a box gives its meaning"), Picker.HitAt(Boxes[B].Key->GetCenter(), HitSite), Boxes[B].Value);
						TestEqual(Name + TEXT(": and its site"), HitSite, Row.SiteIndex);
						for (int32 C = B + 1; C < 3; ++C)
						{
							TestFalse(Name + TEXT(": boxes of a row do not overlap"), Boxes[B].Key->ExpandBy(-0.5).Intersect(Boxes[C].Key->ExpandBy(-0.5)));
						}
					}
				}
				int32 Ignored = 0;
				const TPair<const FBox2D*, ELsnPickerHit> Fields[] = { { &Picker.LatField, ELsnPickerHit::LatField }, { &Picker.LonField, ELsnPickerHit::LonField }, { &Picker.Compute, ELsnPickerHit::Compute }, { &Picker.SearchField, ELsnPickerHit::SearchField } };
				for (int32 B = 0; B < 4; ++B)
				{
					TestTrue(At + TEXT(": a field lies in the sheet"), Picker.Sheet.ExpandBy(0.5).IsInside(Fields[B].Key->Min) && Picker.Sheet.ExpandBy(0.5).IsInside(Fields[B].Key->Max));
					TestEqual(At + TEXT(": the middle of a field gives its meaning"), Picker.HitAt(Fields[B].Key->GetCenter(), Ignored), Fields[B].Value);
					for (int32 C = B + 1; C < 4; ++C)
					{
						TestFalse(At + TEXT(": fields do not overlap"), Fields[B].Key->ExpandBy(-0.5).Intersect(Fields[C].Key->ExpandBy(-0.5)));
					}
				}
				TestEqual(At + TEXT(": outside the sheet gives nothing"), Picker.HitAt(FVector2D(2.0, 2.0), Ignored), ELsnPickerHit::None);
			}
			TestEqual(Where + TEXT(": scrolled through, every site of the list is shown"), SitesSeen.Num(), bSearch ? 17 : 20);
			TestEqual(Where + TEXT(": the header of a group without sites is not shown"), HeaderOrder.Contains(FString(GroupNames[1])), !bSearch);
			int32 Expected = 0;
			for (int32 G = 0; G < UE_ARRAY_COUNT(GroupNames); ++G)
			{
				if (bSearch && G == 1)
				{
					continue;
				}
				TestTrue(Where + TEXT(": groups in the order of the list"), HeaderOrder.IsValidIndex(Expected) && HeaderOrder[Expected] == GroupNames[G]);
				++Expected;
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnCustomCoordinatesTest, "LunarSiteNavigator.Planner.CustomCoordinatesGoToTheCore", LsnTest::Flags)
bool FLsnCustomCoordinatesTest::RunTest(const FString& Parameters)
{
	double Value = 0.0;
	TestTrue(TEXT("W: -89.45 is a latitude"), LsnPlanner::ParseCoordinate(TEXT("-89.45"), -90.0, 90.0, Value));
	TestEqual(TEXT("W: its value"), Value, -89.45, 1e-12);
	TestTrue(TEXT("W: 222.8 is a longitude"), LsnPlanner::ParseCoordinate(TEXT("222.8"), -180.0, 360.0, Value));
	TestTrue(TEXT("W: 90 is a latitude"), LsnPlanner::ParseCoordinate(TEXT("90"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: 91 is no latitude"), LsnPlanner::ParseCoordinate(TEXT("91"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: empty text is refused"), LsnPlanner::ParseCoordinate(TEXT(""), -90.0, 90.0, Value));
	TestFalse(TEXT("W: a lone minus is refused"), LsnPlanner::ParseCoordinate(TEXT("-"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: two points are refused"), LsnPlanner::ParseCoordinate(TEXT("12.3.4"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: letters are refused"), LsnPlanner::ParseCoordinate(TEXT("12a"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: a minus inside is refused"), LsnPlanner::ParseCoordinate(TEXT("1-2"), -90.0, 90.0, Value));
	TestFalse(TEXT("W: 361 is no longitude"), LsnPlanner::ParseCoordinate(TEXT("361"), -180.0, 360.0, Value));

	FString Name;
	const FString Arguments = LsnPlanner::CustomSiteArguments(TEXT("-89.45"), TEXT("222.8"), TEXT("C:/Out/Custom"), Name);
	TestEqual(TEXT("W: the name says the coordinates"), Name, FString(TEXT("Custom -89.45, 222.8")));
	TestEqual(TEXT("W3: the template is filled with the same values"), LsnPlanner::CustomTimelineArguments(TEXT("-m lsncore point --lat {lat} --lon {lon} --name \"{name}\" --out \"{out}\" --days 30"), TEXT("-89.45"), TEXT("222.8"), Name, TEXT("C:/Out/Custom")),
		FString(TEXT("-m lsncore point --lat -89.45 --lon 222.8 --name \"Custom -89.45, 222.8\" --out \"C:/Out/Custom\" --days 30")));
	TestTrue(TEXT("W3: no template, no second step"), LsnPlanner::CustomTimelineArguments(TEXT(""), TEXT("-89.45"), TEXT("222.8"), Name, TEXT("C:/Out/Custom")).IsEmpty());
	TestEqual(TEXT("W3: a third of the stated time has run"), LsnPlanner::StepShare(10.0, 30.0), 1.0 / 3.0, 1e-12);
	TestEqual(TEXT("W3: never shown as done while it runs"), LsnPlanner::StepShare(45.0, 30.0), 0.95, 1e-12);
	TestEqual(TEXT("W3: no stated time, no share"), LsnPlanner::StepShare(10.0, 0.0), 0.0, 1e-12);
	// The core's one command for a complete package (contract 0.11, core/README.md) and what it prints.
	TestEqual(TEXT("W4: the start date is filled in"), LsnPlanner::CustomTimelineArguments(LsnPlanner::DefaultCustomTimelineTemplate(), TEXT("-89.45"), TEXT("222.8"), Name, TEXT("C:/Out/Custom"), TEXT("2026-11-14")),
		FString(TEXT("-m lsncore custom --lat -89.45 --lon 222.8 --start 2026-11-14 --name \"Custom -89.45, 222.8\" --out \"C:/Out/Custom\"")));
	int32 Stage = 0, Stages = 0;
	FString StageText;
	TestTrue(TEXT("W4: the last progress line counts"), LsnPlanner::LastProgress(TEXT("progress 1/6 checking the kernels\nprogress 4/6 Sun and Earth visibility: 30 days\nC:/Out/site/x\n"), Stage, Stages, StageText));
	TestEqual(TEXT("W4: its stage"), Stage, 4);
	TestEqual(TEXT("W4: of how many"), Stages, 6);
	TestEqual(TEXT("W4: its text"), StageText, FString(TEXT("Sun and Earth visibility: 30 days")));
	TestFalse(TEXT("W4: no progress line, no stage"), LsnPlanner::LastProgress(TEXT("error: kernels are missing\n"), Stage, Stages, StageText));
	TestFalse(TEXT("W4: a broken line is not a stage"), LsnPlanner::LastProgress(TEXT("progress x/6 text\n"), Stage, Stages, StageText));

	// What an event rests on (contract 0.10, terrain_quality).
	FLsnEvent Event;
	TestTrue(TEXT("W4: an event without the field says nothing"), LsnPlanner::TerrainQualityPhrase(Event).IsEmpty());
	Event.bHasTerrainQuality = true;
	Event.LimitingPixel = TEXT("constrained");
	Event.QualityHeightErrorM = 5.0;
	TestEqual(TEXT("W4: a pixel with a laser return"), LsnPlanner::TerrainQualityPhrase(Event), FString(TEXT("measured terrain pixel, height +/- 5.0 m")));
	Event.LimitingPixel = TEXT("interpolated");
	Event.QualityHeightErrorM = 0.46;
	TestEqual(TEXT("W4: a filled pixel"), LsnPlanner::TerrainQualityPhrase(Event), FString(TEXT("interpolated terrain pixel, height +/- 0.5 m")));
	Event.LimitingPixel = TEXT("unknown");
	Event.QualityHeightErrorM = std::numeric_limits<double>::quiet_NaN();
	TestEqual(TEXT("W4: nothing known"), LsnPlanner::TerrainQualityPhrase(Event), FString(TEXT("terrain pixel of unknown kind")));
	TestTrue(TEXT("W4: 0.10 is newer than 0.9"), LsnPlanner::ContractAtLeast(TEXT("0.10"), 0, 9));
	TestFalse(TEXT("W4: 0.9 is older than 0.10"), LsnPlanner::ContractAtLeast(TEXT("0.9"), 0, 10));

	TestEqual(TEXT("W: the core's own command"), Arguments, FString(TEXT("-m lsncore site --lat -89.45 --lon 222.8 --name \"Custom -89.45, 222.8\" --out \"C:/Out/Custom\"")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnTerrainSourceTest, "LunarSiteNavigator.Package.TerrainSourceOfThePackage", LsnTest::Flags)
bool FLsnTerrainSourceTest::RunTest(const FString& Parameters)
{
	auto Parse = [](const TCHAR* Text)
	{
		TSharedPtr<FJsonObject> Object;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(FString(Text));
		FJsonSerializer::Deserialize(Reader, Object);
		return Object;
	};
	FLsnTerrainSource Source;
	LsnPackageIO::ReadTerrainSource(Parse(TEXT("{\"horizon\": {\"terrain_source\": {\"at_site\": {\"product_id\": \"LDEM_60S_60M\", \"pixel_m\": 60.0, \"projection\": \"polar stereographic\"}, \"resolution_class\": \"medium\", \"method\": \"horizon.terrain_source\"}}}")), Source);
	TestTrue(TEXT("X: present"), Source.bPresent);
	TestEqual(TEXT("X: class as written"), Source.ResolutionClass, FString(TEXT("medium")));
	TestEqual(TEXT("X: pixel as written"), Source.PixelM, 60.0, 1e-12);
	TestEqual(TEXT("X: product as written"), Source.ProductId, FString(TEXT("LDEM_60S_60M")));
	TestEqual(TEXT("X: what is shown"), LsnPlanner::TerrainSourceLabel(Source), FString(TEXT("terrain: medium, 60 m pixels")));
	LsnPackageIO::ReadTerrainSource(Parse(TEXT("{\"horizon\": {\"azimuth_step_deg\": 0.25}}")), Source);
	TestFalse(TEXT("X: absent in an older package"), Source.bPresent);
	TestTrue(TEXT("X: then nothing is shown"), LsnPlanner::TerrainSourceLabel(Source).IsEmpty());

	// The pinned sample is older than contract 0.9: its package carries none.
	FLsnSitePackage P;
	FString Error;
	if (TestTrue(TEXT("the sample package loads"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		AddInfo(FString::Printf(TEXT("sample (contract %s): terrain source %s"), *P.ContractVersion, P.TerrainSource.bPresent ? *LsnPlanner::TerrainSourceLabel(P.TerrainSource) : TEXT("absent")));
	}
	return true;
}

#endif
