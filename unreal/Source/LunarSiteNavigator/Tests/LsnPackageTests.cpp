// Package reader tests, against the pinned copy of the contract sample.
//
// Tolerances, fixed before the first run:
//   - site frame unit vectors against the package's own "enu":      1e-12
//   - site ground point against the package's "position_km":        0.001 cm
//   - directions from the direction table against the site series:  0.0002 deg
//     (the series are 32-bit floats; near 360 deg one float step is 0.00003 deg)

#include "Tests/LsnTestSupport.h"
#include "Frame/LsnSiteFrame.h"
#include "Misc/FileHelper.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageLoadTest, "LunarSiteNavigator.Package.LoadSample", LsnTest::Flags)
bool FLsnPackageLoadTest::RunTest(const FString& Parameters)
{
	const FString Dir = LsnTest::FixturePackageDir(TEXT("site"));
	if (!TestFalse(TEXT("the fixture index lists a site package"), Dir.IsEmpty()))
	{
		return false;
	}
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(FString::Printf(TEXT("sample site package loads (%s)"), *Error), LsnPackageIO::LoadSitePackage(Dir, P, Error)))
	{
		return false;
	}

	TestEqual(TEXT("contract version"), P.ContractVersion, FString(TEXT("0.2")));
	TestTrue(TEXT("the sample is marked synthetic"), P.bSynthetic);
	TestFalse(TEXT("a synthetic package carries its notice"), P.SyntheticNotice.IsEmpty());
	TestEqual(TEXT("status"), P.Status, FString(TEXT("ok")));
	TestEqual(TEXT("azimuth count times step is a full circle"), P.AzimuthCount * P.AzimuthStepDeg, 360.0);
	TestTrue(TEXT("observer heights are present and increasing"), P.NumHeights() >= 1);
	for (int32 H = 1; H < P.NumHeights(); ++H)
	{
		TestTrue(TEXT("observer heights strictly increase"), P.ObserverHeightsM[H] > P.ObserverHeightsM[H - 1]);
	}
	TestEqual(TEXT("horizon elevation array size"), P.HorizonElevationDeg.Num(), P.NumHeights() * P.AzimuthCount);
	TestEqual(TEXT("horizon distance array size"), P.HorizonDistanceM.Num(), P.NumHeights() * P.AzimuthCount);
	TestTrue(TEXT("the sample has a timeline"), P.bHasTimeline);
	TestTrue(TEXT("the timeline has Sun and Earth series"), P.FindSeries(TEXT("SUN")) && P.FindSeries(TEXT("EARTH")));
	if (const FLsnBodySeries* Sun = P.FindSeries(TEXT("SUN")))
	{
		TestEqual(TEXT("Sun azimuth series length"), Sun->AzimuthDeg.Num(), P.Time.Count);
		TestEqual(TEXT("Sun elevation series length"), Sun->ElevationDeg.Num(), P.Time.Count);
		TestEqual(TEXT("Sun angular radius series length"), Sun->AngularRadiusDeg.Num(), P.Time.Count);
		TestEqual(TEXT("Sun visible fraction series length"), Sun->VisibleFraction.Num(), P.NumHeights() * P.Time.Count);
	}
	TestTrue(TEXT("events were read"), P.Events.Num() > 0);
	TestEqual(TEXT("validation status of the horizon comes from its method card"), P.ValidationStatusOf(P.HorizonElevationMethod), FString(TEXT("synthetic")));

	// Sample labels: the contract allows start_utc + i * step_s when no leap second is in range.
	TestEqual(TEXT("UTC label of sample 0"), P.UtcLabelOfSample(0), P.Time.StartUtc);
	TestEqual(TEXT("UTC label of the last sample"), P.UtcLabelOfSample(P.Time.Count - 1), P.Time.EndUtc);

	// Interpolation between azimuth samples is linear and periodic. The expected
	// values are formed in double precision from the stored 32-bit samples.
	const int32 H = P.DefaultHeightIndex;
	const double Mid = P.HorizonElevationInterpolated(H, P.AzimuthDegAt(10) + 0.5 * P.AzimuthStepDeg);
	TestTrue(TEXT("midpoint interpolation"), FMath::Abs(Mid - 0.5 * (static_cast<double>(P.HorizonElevationAt(H, 10)) + static_cast<double>(P.HorizonElevationAt(H, 11)))) < 1e-9);
	const double Wrap = P.HorizonElevationInterpolated(H, 360.0 - 0.5 * P.AzimuthStepDeg);
	TestTrue(TEXT("interpolation wraps from the last sample to the first"),
		FMath::Abs(Wrap - 0.5 * (static_cast<double>(P.HorizonElevationAt(H, P.AzimuthCount - 1)) + static_cast<double>(P.HorizonElevationAt(H, 0)))) < 1e-9);
	TestTrue(TEXT("negative azimuth wraps"), FMath::Abs(P.HorizonElevationInterpolated(H, -P.AzimuthStepDeg) - P.HorizonElevationAt(H, P.AzimuthCount - 1)) < 1e-9);
	return true;
}

// The frame this project builds from latitude and longitude must be the frame
// the core used: the package states its east, north and up vectors.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageFrameTest, "LunarSiteNavigator.Package.FrameAgreesWithCore", LsnTest::Flags)
bool FLsnPackageFrameTest::RunTest(const FString& Parameters)
{
	FLsnSitePackage P;
	FString Error;
	if (!TestTrue(TEXT("sample site package loads"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)))
	{
		return false;
	}
	const FLsnSiteFrame F = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);
	const double EastError = (F.EastBody - P.EastBody).GetAbsMax();
	const double NorthError = (F.NorthBody - P.NorthBody).GetAbsMax();
	const double UpError = (F.UpBody - P.UpBody).GetAbsMax();
	AddInfo(FString::Printf(TEXT("frame vector differences: east %.3g, north %.3g, up %.3g"), EastError, NorthError, UpError));
	TestTrue(TEXT("east agrees with the package (1e-12)"), EastError <= 1e-12);
	TestTrue(TEXT("north agrees with the package (1e-12)"), NorthError <= 1e-12);
	TestTrue(TEXT("up agrees with the package (1e-12)"), UpError <= 1e-12);

	TestTrue(TEXT("radius_m is reference radius plus surface height"), FMath::Abs(F.OriginRadiusM() - P.RadiusM) < 1e-6);
	const FVector GroundPoint = F.BodyPointMToUnreal(P.PositionKm * 1000.0);
	AddInfo(FString::Printf(TEXT("package ground point lands %.3g cm from the Unreal origin"), GroundPoint.Size()));
	TestTrue(TEXT("the package's ground point is the Unreal origin (0.001 cm)"), GroundPoint.Size() <= 0.001);

	// The package's own unit vectors land on the Unreal axes.
	TestTrue(TEXT("package north is +X"), (F.BodyDirToUnreal(P.NorthBody) - FVector(1, 0, 0)).GetAbsMax() <= 1e-12);
	TestTrue(TEXT("package east is +Y"), (F.BodyDirToUnreal(P.EastBody) - FVector(0, 1, 0)).GetAbsMax() <= 1e-12);
	TestTrue(TEXT("package up is +Z"), (F.BodyDirToUnreal(P.UpBody) - FVector(0, 0, 1)).GetAbsMax() <= 1e-12);
	return true;
}

// End-to-end check of the body-fixed mapping against numbers the core computed
// on its own: positions in the direction table, pushed through this project's
// frame, must point where the site series say the bodies are. This is a test
// of the coordinate mapping only; the scene never places anything this way.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageDirectionTest, "LunarSiteNavigator.Package.BodyFrameAgreesWithSeries", LsnTest::Flags)
bool FLsnPackageDirectionTest::RunTest(const FString& Parameters)
{
	constexpr double ToleranceDeg = 0.0002;

	FLsnSitePackage P;
	FLsnDirectionTable Table;
	FString Error;
	if (!TestTrue(TEXT("sample site package loads"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error)) ||
		!TestTrue(FString::Printf(TEXT("sample direction table loads (%s)"), *Error), LsnPackageIO::LoadDirectionTable(LsnTest::FixturePackageDir(TEXT("direction_table")), Table, Error)))
	{
		return false;
	}
	TestEqual(TEXT("the site was computed from this table"), P.DirectionTableId, Table.PackageId);
	TestEqual(TEXT("site and table use the same body-fixed frame"), P.Frame, Table.Frame);
	TestEqual(TEXT("same time step"), P.Time.StepS, Table.Time.StepS);

	const double OffsetRecords = (P.Time.StartEtS - Table.Time.StartEtS) / Table.Time.StepS;
	const int32 Offset = FMath::RoundToInt32(OffsetRecords);
	if (!TestTrue(TEXT("site samples fall on table records"), FMath::Abs(OffsetRecords - Offset) < 1e-9))
	{
		return false;
	}

	const FLsnSiteFrame F = FLsnSiteFrame::Make(P.LatDeg, P.LonDeg, P.ReferenceRadiusM, P.SurfaceHeightM);
	double WorstDeg = 0.0;
	int32 Compared = 0;
	for (const FString& Body : P.Bodies)
	{
		const FLsnBodySeries* Series = P.FindSeries(Body);
		for (int32 I = 0; I < P.Time.Count; I += 7)
		{
			FVector PositionKm;
			if (!Series || !Table.PositionKm(Body, I + Offset, PositionKm))
			{
				AddError(FString::Printf(TEXT("%s sample %d is missing from the table"), *Body, I));
				continue;
			}
			// From the site's ground point, as SPEC section 6 writes it.
			const FVector FromSiteBody = PositionKm - P.PositionKm;
			const FVector FromTable = F.BodyDirToUnreal(FromSiteBody);
			const FVector FromSeries = FLsnSiteFrame::AzElToUnrealDir(Series->AzimuthDeg[I], Series->ElevationDeg[I]);
			WorstDeg = FMath::Max(WorstDeg, LsnTest::AngleDeg(FromTable, FromSeries));
			++Compared;
		}
	}
	AddInfo(FString::Printf(TEXT("largest angle between table direction and series direction: %.7f deg over %d samples (tolerance %.4f)"), WorstDeg, Compared, ToleranceDeg));
	TestTrue(TEXT("samples were compared"), Compared > 100);
	TestTrue(TEXT("body-fixed positions map onto the series directions"), WorstDeg <= ToleranceDeg);
	return true;
}

// A reader must refuse what it cannot read correctly, and say why.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnPackageRefusalTest, "LunarSiteNavigator.Package.RefusesBadPackages", LsnTest::Flags)
bool FLsnPackageRefusalTest::RunTest(const FString& Parameters)
{
	const FString Source = LsnTest::FixturePackageDir(TEXT("site"));
	FLsnSitePackage P;
	FString Error;

	// Another major version of the contract.
	{
		const FString Dir = LsnTest::CopyPackageToScratch(Source, TEXT("major"));
		FString Manifest;
		FFileHelper::LoadFileToString(Manifest, *FPaths::Combine(Dir, TEXT("manifest.json")));
		const int32 Replaced = Manifest.ReplaceInline(TEXT("\"version\": \"0.2\""), TEXT("\"version\": \"1.0\""));
		TestEqual(TEXT("test set-up: version string replaced once"), Replaced, 1);
		FFileHelper::SaveStringToFile(Manifest, *FPaths::Combine(Dir, TEXT("manifest.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
		TestFalse(TEXT("a package with another major version is refused"), LsnPackageIO::LoadSitePackage(Dir, P, Error));
		TestTrue(TEXT("the refusal names the major version"), Error.Contains(TEXT("major")));
	}
	// An array file that is shorter than the manifest says.
	{
		const FString Dir = LsnTest::CopyPackageToScratch(Source, TEXT("short"));
		TArray<uint8> Bytes;
		const FString File = FPaths::Combine(Dir, TEXT("horizon_elevation_deg.f4"));
		FFileHelper::LoadFileToArray(Bytes, *File);
		Bytes.SetNum(Bytes.Num() - 4);
		FFileHelper::SaveArrayToFile(Bytes, *File);
		TestFalse(TEXT("a truncated array is refused"), LsnPackageIO::LoadSitePackage(Dir, P, Error));
		TestTrue(TEXT("the refusal names the file"), Error.Contains(TEXT("horizon_elevation_deg.f4")));
	}
	// A direction table where a site package is expected.
	{
		TestFalse(TEXT("a direction table is not a site package"), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("direction_table")), P, Error));
		TestTrue(TEXT("the refusal names the kind"), Error.Contains(TEXT("kind")));
	}
	// A directory without a manifest.
	{
		TestFalse(TEXT("a directory without a manifest is refused"), LsnPackageIO::LoadSitePackage(LsnTest::FixtureRoot(), P, Error));
	}
	// A package without a timeline is valid: the feature is simply absent.
	{
		const FString Dir = LsnTest::CopyPackageToScratch(Source, TEXT("notimeline"));
		FString Manifest;
		FFileHelper::LoadFileToString(Manifest, *FPaths::Combine(Dir, TEXT("manifest.json")));
		const int32 Replaced = Manifest.ReplaceInline(TEXT("\"timeline\": {"), TEXT("\"timeline_removed_by_test\": {"));
		TestTrue(TEXT("test set-up: timeline key renamed"), Replaced >= 1);
		FFileHelper::SaveStringToFile(Manifest, *FPaths::Combine(Dir, TEXT("manifest.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
		const bool bLoaded = LsnPackageIO::LoadSitePackage(Dir, P, Error);
		TestTrue(FString::Printf(TEXT("a horizon-only package loads (%s)"), *Error), bLoaded);
		TestFalse(TEXT("and reports that it has no timeline"), P.bHasTimeline);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
