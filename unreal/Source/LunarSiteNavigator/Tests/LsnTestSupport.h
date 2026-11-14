#pragma once

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Package/LsnPackage.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace LsnTest
{
	inline constexpr EAutomationTestFlags Flags = EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter;

	/** Root of the pinned copy of the contract sample (see unreal/TestData/README.md). */
	inline FString FixtureRoot()
	{
		return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("TestData/contract-sample/packages")));
	}

	/** Directory of the first package of a kind listed in the fixture's index. */
	inline FString FixturePackageDir(const TCHAR* Kind)
	{
		TArray<FLsnIndexEntry> Entries;
		FString Error;
		if (LsnPackageIO::LoadIndex(FixtureRoot(), Entries, Error))
		{
			for (const FLsnIndexEntry& Entry : Entries)
			{
				if (Entry.Kind == Kind)
				{
					return FPaths::Combine(FixtureRoot(), Entry.Path);
				}
			}
		}
		return FString();
	}

	/** Copies a package directory to a scratch folder under Saved/ so a test can alter the copy. */
	inline FString CopyPackageToScratch(const FString& SourceDir, const TCHAR* ScratchName)
	{
		const FString Target = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("LsnTestScratch"), ScratchName));
		IFileManager& Files = IFileManager::Get();
		Files.DeleteDirectory(*Target, false, true);
		Files.MakeDirectory(*Target, true);
		TArray<FString> Names;
		Files.FindFiles(Names, *FPaths::Combine(SourceDir, TEXT("*")), true, false);
		for (const FString& Name : Names)
		{
			Files.Copy(*FPaths::Combine(Target, Name), *FPaths::Combine(SourceDir, Name));
		}
		return Target;
	}

	/** Angle between two directions, degrees. */
	inline double AngleDeg(const FVector& A, const FVector& B)
	{
		const FVector Na = A.GetSafeNormal(), Nb = B.GetSafeNormal();
		return FMath::RadiansToDegrees(FMath::Atan2(FVector::CrossProduct(Na, Nb).Size(), FVector::DotProduct(Na, Nb)));
	}
}

#endif // WITH_DEV_AUTOMATION_TESTS
