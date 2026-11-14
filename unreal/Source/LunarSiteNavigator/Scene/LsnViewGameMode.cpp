#include "Scene/LsnViewGameMode.h"

#include "LunarSiteNavigator.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Package/LsnPackage.h"
#include "Scene/LsnHud.h"
#include "Scene/LsnObserverPawn.h"
#include "Scene/LsnSiteScene.h"
#include "UnrealClient.h"
#if WITH_EDITOR
#include "ShaderCompiler.h"
#endif

ALsnViewGameMode::ALsnViewGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	DefaultPawnClass = ALsnObserverPawn::StaticClass();
	HUDClass = ALsnHud::StaticClass();
}

FString ALsnViewGameMode::ResolvePackageDirectory(FString& OutError)
{
	FString Directory;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPackage="), Directory))
	{
		return FPaths::ConvertRelativePathToFull(Directory);
	}

	TArray<FString> Roots;
	FString Root;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPackageRoot="), Root))
	{
		Roots.Add(FPaths::ConvertRelativePathToFull(Root));
	}
	else
	{
		// The sample that ships with the contract, then the copy pinned for the tests.
		Roots.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../docs/contract/sample/packages"))));
		Roots.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("TestData/contract-sample/packages"))));
	}
	for (const FString& Candidate : Roots)
	{
		TArray<FLsnIndexEntry> Entries;
		FString IndexError;
		if (!LsnPackageIO::LoadIndex(Candidate, Entries, IndexError))
		{
			OutError = IndexError;
			continue;
		}
		for (const FLsnIndexEntry& Entry : Entries)
		{
			if (Entry.Kind == TEXT("site"))
			{
				OutError.Reset();
				return FPaths::Combine(Candidate, Entry.Path);
			}
		}
		OutError = FString::Printf(TEXT("%s lists no site package"), *Candidate);
	}
	return FString();
}

void ALsnViewGameMode::StartPlay()
{
	Super::StartPlay();

	// Shadows must reach the far terrain: more clipmap levels, and no distance culling of shadow casters.
	if (IConsoleVariable* LastLevel = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Shadow.Virtual.Clipmap.LastLevel")))
	{
		LastLevel->Set(25, ECVF_SetByGameSetting);
	}
	if (IConsoleVariable* FarCulling = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Shadow.Virtual.UseFarShadowCulling")))
	{
		FarCulling->Set(0, ECVF_SetByGameSetting);
	}

	Scene = GetWorld()->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity);

	const FString Directory = ResolvePackageDirectory(LoadError);
	if (!Directory.IsEmpty())
	{
		Scene->LoadPackageDirectory(Directory, LoadError);
	}
	if (!Scene->HasPackage())
	{
		UE_LOG(LogLsn, Error, TEXT("No package is shown: %s"), *LoadError);
	}
	else
	{
		int32 Index = 0;
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnHeight="), Index))
		{
			Scene->SetHeightIndex(Index);
		}
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnTime="), Index))
		{
			Scene->SetTimeIndex(Index);
		}
		Scene->SetHorizonLineVisible(FParse::Param(FCommandLine::Get(), TEXT("LsnHorizonLine")));
	}

	if (FParse::Value(FCommandLine::Get(), TEXT("LsnShot="), ShotPath))
	{
		ShotPath = FPaths::ConvertRelativePathToFull(ShotPath);
		// Leave time for shaders and shadow pages before the capture.
		FramesUntilShot = 240;
	}
}

void ALsnViewGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

#if WITH_EDITOR
	// Run from the editor binaries, materials may still be compiling: do not capture a half-built frame.
	if (FramesUntilShot > 0 && FramesUntilShot < 60 && GShaderCompilingManager && GShaderCompilingManager->IsCompiling())
	{
		FramesUntilShot = 60;
	}
#endif
	if (FramesUntilShot > 0 && --FramesUntilShot == 0)
	{
		FScreenshotRequest::RequestScreenshot(ShotPath, true, false);
		FramesUntilQuit = 30;
		UE_LOG(LogLsn, Display, TEXT("Screenshot requested: %s"), *ShotPath);
	}
	else if (FramesUntilQuit > 0 && --FramesUntilQuit == 0)
	{
		UKismetSystemLibrary::QuitGame(this, GetWorld()->GetFirstPlayerController(), EQuitPreference::Quit, false);
	}
}
