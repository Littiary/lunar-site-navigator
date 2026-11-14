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
// W. Custom coordinates are handed to the science core, not computed here.
//    1. A latitude is accepted from -90 to 90 and a longitude from -180 to 360, as plain
//       decimal numbers; empty text, text with two points, letters and values outside the
//       range are refused.
//    2. The command is the core's own: the arguments are exactly
//       -m lsncore site --lat <lat> --lon <lon> --name "<name>" --out "<root>"
//       with the numbers as they were typed, and the name says the coordinates.
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
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(TEXT("the sample package loads"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	for (const FVector2D& Size : { FVector2D(1280, 720), FVector2D(1920, 1080) })
	{
		for (const bool bComparing : { false, true })
		{
			const FString Where = FString::Printf(TEXT("%.0f x %.0f%s"), Size.X, Size.Y, bComparing ? TEXT(" side by side") : TEXT(""));
			const FLsnSitePicker Picker = FLsnSitePicker::Make(Size.X, Size.Y, bComparing, GroupOfSite);
			const FLsnToolbar Toolbar = FLsnToolbar::Make(Size.X, Size.Y, bComparing);
			const FLsnTimeStripLayout Strips = FLsnTimeStripLayout::Make(bComparing ? 0.5 * Size.X : Size.X, Size.Y, P);
			TestTrue(Where + TEXT(": the sheet lies in the window"), Picker.Sheet.Min.X >= 0.0 && Picker.Sheet.Max.X <= Size.X && Picker.Sheet.Min.Y > Toolbar.HeaderBottom && Picker.Sheet.Max.Y < Strips.Zoom.Min.Y);

			TArray<FString> HeaderOrder;
			TSet<int32> SitesSeen;
			FString CurrentGroup;
			for (int32 I = 0; I < Picker.Rows.Num(); ++I)
			{
				const FLsnPickerRow& Row = Picker.Rows[I];
				const FString Name = Where + FString::Printf(TEXT(": row %d"), I);
				TestTrue(Name + TEXT(" lies in the sheet"), Picker.Sheet.IsInside(Row.Row.Min) && Picker.Sheet.IsInside(Row.Row.Max));
				TestTrue(Name + TEXT(" is at least 18 px high"), Row.Row.Max.Y - Row.Row.Min.Y >= 18.0);
				TestTrue(Name + TEXT(" does not lie across the middle"), !bComparing || Row.Row.Max.X <= 0.5 * Size.X || Row.Row.Min.X >= 0.5 * Size.X);
				for (int32 J = I + 1; J < Picker.Rows.Num(); ++J)
				{
					TestFalse(Name + TEXT(" does not overlap another row"), Row.Row.ExpandBy(-0.5).Intersect(Picker.Rows[J].Row.ExpandBy(-0.5)));
				}
				for (const FBox2D& Box : { Picker.LatField, Picker.LonField, Picker.Compute })
				{
					TestFalse(Name + TEXT(" does not overlap the custom coordinates"), Row.Row.ExpandBy(-0.5).Intersect(Box));
				}
				int32 HitSite = -2;
				if (Row.SiteIndex < 0)
				{
					HeaderOrder.Add(Row.Group);
					CurrentGroup = Row.Group;
					TestEqual(Name + TEXT(" (group header) gives nothing"), Picker.HitAt(Row.Row.GetCenter(), HitSite), ELsnPickerHit::None);
					continue;
				}
				TestEqual(Name + TEXT(" follows the header of its group"), GroupOfSite[Row.SiteIndex], CurrentGroup);
				TestFalse(Name + TEXT(": one row per site"), SitesSeen.Contains(Row.SiteIndex));
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
			TestEqual(Where + TEXT(": every site has a row"), SitesSeen.Num(), GroupOfSite.Num());
			TestEqual(Where + TEXT(": one header per group"), HeaderOrder.Num(), static_cast<int32>(UE_ARRAY_COUNT(GroupNames)));
			for (int32 G = 0; G < HeaderOrder.Num() && G < UE_ARRAY_COUNT(GroupNames); ++G)
			{
				TestEqual(Where + TEXT(": groups in the order of the list"), HeaderOrder[G], FString(GroupNames[G]));
			}
			int32 Ignored = 0;
			const TPair<const FBox2D*, ELsnPickerHit> Custom[] = { { &Picker.LatField, ELsnPickerHit::LatField }, { &Picker.LonField, ELsnPickerHit::LonField }, { &Picker.Compute, ELsnPickerHit::Compute } };
			for (int32 B = 0; B < 3; ++B)
			{
				TestTrue(Where + TEXT(": a custom-coordinate box lies in the sheet"), Picker.Sheet.IsInside(Custom[B].Key->Min) && Picker.Sheet.IsInside(Custom[B].Key->Max));
				TestTrue(Where + TEXT(": a custom-coordinate box does not lie across the middle"), !bComparing || Custom[B].Key->Max.X <= 0.5 * Size.X || Custom[B].Key->Min.X >= 0.5 * Size.X);
				TestEqual(Where + TEXT(": the middle of a custom-coordinate box gives its meaning"), Picker.HitAt(Custom[B].Key->GetCenter(), Ignored), Custom[B].Value);
				for (int32 C = B + 1; C < 3; ++C)
				{
					TestFalse(Where + TEXT(": custom-coordinate boxes do not overlap"), Custom[B].Key->ExpandBy(-0.5).Intersect(Custom[C].Key->ExpandBy(-0.5)));
				}
			}
			TestEqual(Where + TEXT(": outside the sheet gives nothing"), Picker.HitAt(FVector2D(Size.X - 2.0, 2.0), Ignored), ELsnPickerHit::None);
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
