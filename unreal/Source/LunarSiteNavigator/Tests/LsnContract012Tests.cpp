// Fixes of the reader and the view after contract 0.12 (15 November 2026).
//
// Criteria, written before the first run:
//
// R. Every array is checked against the SHA-256 its reference states (SPEC 3.1).
//    1. The digest function gives the published test vectors: "" -> e3b0c442...,
//       "abc" -> ba7816bf..., the 56-byte two-block message -> 248d6a61..., and a million "a" -> cdc76e5c....
//    2. The contract sample loads unchanged.
//    3. A copy of it with one bit of one array file changed (same size, no NaN made) is refused,
//       and the error names the file and says "SHA-256".
//    4. A copy whose manifest has one array reference without "sha256" is refused.
//    5. The time it costs is measured on the largest published site package and reported:
//       the load with the check, and the hashing of the same array files alone.
//
// S. The share of the range in which a landing meets the requirement (feasible_fraction, SPEC 5.6)
//    is shown only where it can be judged: absent (null) or with latest_landing before the
//    start of the range, the text says "cannot be judged"; otherwise "landing possible in
//    x.x % of the range that can be judged".
//
// T. The input is identified by package_id (SPEC 7).
//    With an index of four entries in which one site_id appears twice:
//    1. a package id selects its own entry, whichever of the two it is;
//    2. a site id that appears once selects its entry without a warning;
//    3. a site id that appears twice selects its first entry and gives a warning that names the
//       site id and both package ids;
//    4. an unknown package id or site id selects nothing and says so.
//
// U. The drawn ground is checked against the package horizon from the site outwards when the
//    horizon method card says that the ground at the site is searched (parameter
//    ground_at_the_site, since 0.12): the check starts at 0 m. A card without it starts the check
//    at first_point_m as before.

#include "Tests/LsnTestSupport.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Package/LsnSha256.h"
#include "Planner/LsnPlanner.h"
#include "Scene/LsnHud.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnContract012Test
{
	/** A fresh copy of the sample site package in Saved/, to be damaged. */
	FString CopySample(const TCHAR* Name)
	{
		const FString From = LsnTest::FixturePackageDir(TEXT("site"));
		const FString To = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("LsnTest"), Name));
		IFileManager::Get().DeleteDirectory(*To, false, true);
		IFileManager::Get().MakeDirectory(*To, true);
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *FPaths::Combine(From, TEXT("*")), true, false);
		for (const FString& File : Files)
		{
			IFileManager::Get().Copy(*FPaths::Combine(To, File), *FPaths::Combine(From, File));
		}
		return To;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnArrayDigestTest, "LunarSiteNavigator.Package.ArrayDigestChecked", LsnTest::Flags)
bool FLsnArrayDigestTest::RunTest(const FString& Parameters)
{
	using namespace LsnContract012Test;
	auto Hex = [](const FString& Text)
	{
		const FTCHARToUTF8 Bytes(*Text);
		return LsnSha256::HexOf(reinterpret_cast<const uint8*>(Bytes.Get()), Bytes.Length());
	};
	TestEqual(TEXT("R1: empty"), Hex(TEXT("")), FString(TEXT("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")));
	TestEqual(TEXT("R1: abc"), Hex(TEXT("abc")), FString(TEXT("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")));
	TestEqual(TEXT("R1: two blocks"), Hex(TEXT("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")), FString(TEXT("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")));
	TArray<uint8> Million;
	Million.Init('a', 1000000);
	TestEqual(TEXT("R1: a million a"), LsnSha256::HexOf(Million.GetData(), Million.Num()), FString(TEXT("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")));

	FLsnSitePackage P;
	FString Error;
	TestTrue(FString::Printf(TEXT("R2: the sample loads (%s)"), *Error), LsnPackageIO::LoadSitePackage(LsnTest::FixturePackageDir(TEXT("site")), P, Error));

	// R3: one bit of the horizon elevations, the lowest bit of the first value.
	{
		const FString Dir = CopySample(TEXT("digest_damaged"));
		const FString File = FPaths::Combine(Dir, TEXT("horizon_elevation_deg.f4"));
		TArray<uint8> Bytes;
		if (TestTrue(TEXT("R3: the array file is there"), FFileHelper::LoadFileToArray(Bytes, *File) && Bytes.Num() >= 4))
		{
			Bytes[0] ^= 1;
			FFileHelper::SaveArrayToFile(Bytes, *File);
			Error.Reset();
			TestFalse(TEXT("R3: a damaged array file is refused"), LsnPackageIO::LoadSitePackage(Dir, P, Error));
			TestTrue(FString::Printf(TEXT("R3: the error names the file and the digest (%s)"), *Error), Error.Contains(TEXT("horizon_elevation_deg.f4")) && Error.Contains(TEXT("SHA-256")));
		}
	}
	// R4: a reference without its digest.
	{
		const FString Dir = CopySample(TEXT("digest_missing"));
		const FString Manifest = FPaths::Combine(Dir, TEXT("manifest.json"));
		FString Text;
		FFileHelper::LoadFileToString(Text, *Manifest);
		// The first "sha256" of an array reference: it follows "nan_count" or "method" inside the object of a file.
		const int32 FileAt = Text.Find(TEXT("\"file\""));
		const int32 KeyAt = FileAt >= 0 ? Text.Find(TEXT("\"sha256\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, FileAt) : INDEX_NONE;
		if (TestTrue(TEXT("R4: the sample has a digest to remove"), KeyAt != INDEX_NONE))
		{
			Text = Text.Left(KeyAt) + TEXT("\"sha256_removed\"") + Text.Mid(KeyAt + 8);
			FFileHelper::SaveStringToFile(Text, *Manifest);
			Error.Reset();
			TestFalse(TEXT("R4: an array without its digest is refused"), LsnPackageIO::LoadSitePackage(Dir, P, Error));
			TestTrue(FString::Printf(TEXT("R4: the error says so (%s)"), *Error), Error.Contains(TEXT("sha256")));
		}
	}
	// R5: the cost, on the largest published site package.
	const FString Root = LsnPlanner::PublishedPackageRoot();
	TArray<FLsnIndexEntry> Entries;
	if (LsnPackageIO::LoadIndex(Root, Entries, Error))
	{
		FString Largest;
		int64 LargestBytes = 0;
		for (const FLsnIndexEntry& Entry : Entries)
		{
			if (Entry.Kind != TEXT("site"))
			{
				continue;
			}
			TArray<FString> Files;
			const FString Dir = FPaths::Combine(Root, Entry.Path);
			IFileManager::Get().FindFiles(Files, *FPaths::Combine(Dir, TEXT("*")), true, false);
			int64 Bytes = 0;
			for (const FString& File : Files)
			{
				Bytes += IFileManager::Get().FileSize(*FPaths::Combine(Dir, File));
			}
			if (Bytes > LargestBytes)
			{
				LargestBytes = Bytes;
				Largest = Dir;
			}
		}
		double LoadS = TNumericLimits<double>::Max(), HashS = TNumericLimits<double>::Max();
		int64 ArrayBytes = 0;
		for (int32 Run = 0; Run < 3; ++Run)
		{
			double Start = FPlatformTime::Seconds();
			FLsnSitePackage Loaded;
			TestTrue(TEXT("R5: the largest published package loads"), LsnPackageIO::LoadSitePackage(Largest, Loaded, Error));
			LoadS = FMath::Min(LoadS, FPlatformTime::Seconds() - Start);
			TArray<FString> Files;
			IFileManager::Get().FindFiles(Files, *FPaths::Combine(Largest, TEXT("*")), true, false);
			ArrayBytes = 0;
			Start = FPlatformTime::Seconds();
			for (const FString& File : Files)
			{
				if (File.EndsWith(TEXT(".json")))
				{
					continue;
				}
				TArray<uint8> Bytes;
				FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(Largest, File));
				ArrayBytes += Bytes.Num();
				LsnSha256::HexOf(Bytes.GetData(), Bytes.Num());
			}
			HashS = FMath::Min(HashS, FPlatformTime::Seconds() - Start);
		}
		AddInfo(FString::Printf(TEXT("R5: %s: load with the digest check %.1f ms; reading and hashing its %.1f MB of arrays alone %.1f ms (best of 3)"),
			*FPaths::GetCleanFilename(Largest), 1000.0 * LoadS, ArrayBytes / 1.0e6, 1000.0 * HashS));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnFeasibleShareTest, "LunarSiteNavigator.Planner.FeasibleShareOnlyWhereJudged", LsnTest::Flags)
bool FLsnFeasibleShareTest::RunTest(const FString& Parameters)
{
	FLsnOpportunity O;
	O.bHasFeasibleFraction = true;
	O.FeasibleFraction = 0.196;
	O.LatestLandingEtS = 2000.0;
	TestEqual(TEXT("S: a share that can be judged"), LsnHudText::FeasibleShareText(O, 1000.0), FString(TEXT("landing possible in 19.6 % of the range that can be judged")));
	O.bHasFeasibleFraction = false;
	TestEqual(TEXT("S: no share in the package (null)"), LsnHudText::FeasibleShareText(O, 1000.0), FString(TEXT("share of the range in which a landing meets it: cannot be judged")));
	O.bHasFeasibleFraction = true;
	O.FeasibleFraction = 0.0;
	O.LatestLandingEtS = 500.0;
	TestEqual(TEXT("S: latest landing before the start of the range"), LsnHudText::FeasibleShareText(O, 1000.0), FString(TEXT("share of the range in which a landing meets it: cannot be judged")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnChooseByPackageTest, "LunarSiteNavigator.Planner.InputIsThePackageId", LsnTest::Flags)
bool FLsnChooseByPackageTest::RunTest(const FString& Parameters)
{
	auto Entry = [](const TCHAR* SiteId, const TCHAR* PackageId)
	{
		FLsnIndexEntry E;
		E.Kind = TEXT("site");
		E.SiteId = SiteId;
		E.PackageId = PackageId;
		return E;
	};
	const TArray<FLsnIndexEntry> Sites = { Entry(TEXT("alpha"), TEXT("site-a1")), Entry(TEXT("beta"), TEXT("site-b1")), Entry(TEXT("beta"), TEXT("site-b2")), Entry(TEXT("gamma"), TEXT("site-c1")) };
	int32 Index = -9;
	FString Warning;
	TestTrue(TEXT("T1: a package id selects its entry"), LsnPlanner::ChooseSite(Sites, TEXT("site-b2"), TEXT(""), Index, Warning));
	TestEqual(TEXT("T1: the second of the two"), Index, 2);
	TestTrue(TEXT("T1: no warning"), Warning.IsEmpty());
	TestTrue(TEXT("T1: and the first"), LsnPlanner::ChooseSite(Sites, TEXT("site-b1"), TEXT("beta"), Index, Warning) && Index == 1 && Warning.IsEmpty());
	TestTrue(TEXT("T2: a unique site id"), LsnPlanner::ChooseSite(Sites, TEXT(""), TEXT("gamma"), Index, Warning) && Index == 3 && Warning.IsEmpty());
	TestTrue(TEXT("T3: a site id that appears twice"), LsnPlanner::ChooseSite(Sites, TEXT(""), TEXT("beta"), Index, Warning));
	TestEqual(TEXT("T3: its first entry"), Index, 1);
	TestTrue(FString::Printf(TEXT("T3: a warning that names it and both packages (%s)"), *Warning), Warning.Contains(TEXT("beta")) && Warning.Contains(TEXT("site-b1")) && Warning.Contains(TEXT("site-b2")));
	FString Error;
	TestFalse(TEXT("T4: an unknown package id"), LsnPlanner::ChooseSite(Sites, TEXT("site-zz"), TEXT(""), Index, Error));
	TestTrue(TEXT("T4: says so"), Error.Contains(TEXT("site-zz")));
	TestFalse(TEXT("T4: an unknown site id"), LsnPlanner::ChooseSite(Sites, TEXT(""), TEXT("delta"), Index, Error));
	TestTrue(TEXT("T4: says so"), Error.Contains(TEXT("delta")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLsnGroundCheckStartTest, "LunarSiteNavigator.Package.GroundCheckedFromTheSite", LsnTest::Flags)
bool FLsnGroundCheckStartTest::RunTest(const FString& Parameters)
{
	FLsnSitePackage P;
	P.HorizonElevationMethod = TEXT("horizon.elevation");
	FLsnMethodCard Card;
	Card.NumericParameters.Add(TEXT("first_point_m"), 5.0);
	P.Methods.Add(P.HorizonElevationMethod, Card);
	TestEqual(TEXT("U: before 0.12 the check starts at first_point_m"), P.GroundCheckStartM(), 5.0);
	P.Methods[P.HorizonElevationMethod].TextParameters.Add(TEXT("ground_at_the_site"), TEXT("searched for every observer height"));
	TestEqual(TEXT("U: with ground_at_the_site the check starts at the site"), P.GroundCheckStartM(), 0.0);
	return true;
}

#endif
