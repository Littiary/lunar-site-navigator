#include "Scene/LsnViewGameMode.h"

#include "LunarSiteNavigator.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Planner/LsnPlanner.h"
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

FString ALsnViewGameMode::ResolvePackageRoot(FString& OutError)
{
	TArray<FString> Roots;
	FString Root;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPackageRoot="), Root))
	{
		Roots.Add(FPaths::ConvertRelativePathToFull(Root));
	}
	else
	{
		// Packages imported for the demo, the sample that ships with the contract, then the copy pinned for the tests.
		Roots.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("LsnPackages"))));
		Roots.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../docs/contract/sample/packages"))));
		Roots.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("TestData/contract-sample/packages"))));
	}
	for (const FString& Candidate : Roots)
	{
		TArray<FLsnIndexEntry> Found;
		if (LsnPlanner::ListSites(Candidate, Found, OutError))
		{
			OutError.Reset();
			return Candidate;
		}
	}
	return FString();
}

int32 ALsnViewGameMode::GetViewIndexOf(const AController* Controller) const
{
	return (Controller != nullptr && Controller == SecondController) ? 1 : 0;
}

ALsnSiteScene* ALsnViewGameMode::GetSceneOf(const AController* Controller) const
{
	const int32 View = GetViewIndexOf(Controller);
	return Scenes.IsValidIndex(View) ? Scenes[View] : nullptr;
}

void ALsnViewGameMode::ApplyViewOptions(ALsnSiteScene* Scene) const
{
	Scene->SetHorizonLineVisible(FParse::Param(FCommandLine::Get(), TEXT("LsnHorizonLine")));
	Scene->SetFillLightVisible(!FParse::Param(FCommandLine::Get(), TEXT("LsnNoFillLight")));
	Scene->SetObstacleViewEnabled(!FParse::Param(FCommandLine::Get(), TEXT("LsnNoObstacle")));
}

bool ALsnViewGameMode::SelectSite(int32 ViewIndex, int32 SiteIndex)
{
	if (!Sites.IsValidIndex(SiteIndex) || !Scenes.IsValidIndex(ViewIndex))
	{
		return false;
	}
	ALsnSiteScene* Scene = Scenes[ViewIndex];
	// Keep the instant and the observer height across the change of site.
	const bool bHadPackage = Scenes[0]->HasPackage();
	const FLsnSitePackage Before = bHadPackage ? Scenes[0]->GetPackage() : FLsnSitePackage();
	const double PositionBefore = Scenes[0]->GetTimePosition();
	const int32 HeightBefore = Scenes[0]->GetHeightIndex();

	FString Error;
	if (!Scene->LoadPackageDirectory(FPaths::Combine(PackageRoot, Sites[SiteIndex].Path), Error))
	{
		LoadError = Error;
		return false;
	}
	SelectedSite[ViewIndex] = SiteIndex;
	ApplyViewOptions(Scene);
	if (bHadPackage)
	{
		Scene->SetHeightIndex(HeightBefore);
		double Position = 0.0;
		if (LsnPlanner::LinkedPosition(Before, PositionBefore, Scene->GetPackage(), Position))
		{
			Scene->SetTimePosition(Position);
		}
	}
	if (ViewIndex == 1)
	{
		SetComparing(true);
	}
	return true;
}

void ALsnViewGameMode::SetComparing(bool bCompare)
{
	if (bCompare == bComparing || !Scenes.IsValidIndex(1))
	{
		return;
	}
	APlayerController* First = GetWorld()->GetFirstPlayerController();
	if (bCompare)
	{
		if (!Scenes[1]->HasPackage())
		{
			// Default partner: the next site of the list.
			const int32 Next = Sites.Num() > 1 ? (FMath::Max(SelectedSite[0], 0) + 1) % Sites.Num() : -1;
			FString Error;
			if (Next < 0 || !Scenes[1]->LoadPackageDirectory(FPaths::Combine(PackageRoot, Sites[Next].Path), Error))
			{
				UE_LOG(LogLsn, Warning, TEXT("No second site to compare with. %s"), *Error);
				return;
			}
			SelectedSite[1] = Next;
			ApplyViewOptions(Scenes[1]);
		}
		// A second local player gives the second half of the screen its own camera and HUD.
		SecondController = UGameplayStatics::CreatePlayer(this, -1, true);
		if (!SecondController)
		{
			UE_LOG(LogLsn, Warning, TEXT("The second view could not be created."));
			return;
		}
		bComparing = true;
	}
	else
	{
		if (SecondController)
		{
			UGameplayStatics::RemovePlayer(SecondController, true);
			SecondController = nullptr;
		}
		bComparing = false;
	}
	// Each view sees its own scene only.
	if (First)
	{
		First->HiddenActors.Reset();
		First->HiddenActors.Add(Scenes[1]);
	}
	if (SecondController)
	{
		SecondController->HiddenActors.Reset();
		SecondController->HiddenActors.Add(Scenes[0]);
	}
}

void ALsnViewGameMode::StartPlay()
{
	Super::StartPlay();

	// The engine's own on-screen notices (development builds) do not belong in the planner view or in captures.
	GAreScreenMessagesEnabled = false;

	// Shadows must reach the far terrain: more clipmap levels, and no distance culling of shadow casters.
	if (IConsoleVariable* LastLevel = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Shadow.Virtual.Clipmap.LastLevel")))
	{
		LastLevel->Set(25, ECVF_SetByGameSetting);
	}
	if (IConsoleVariable* FarCulling = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Shadow.Virtual.UseFarShadowCulling")))
	{
		FarCulling->Set(0, ECVF_SetByGameSetting);
	}

	// Two scenes: the second stands far away, is lit on its own lighting channel and is
	// only ever seen by the right view of a comparison.
	Scenes.Add(GetWorld()->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform::Identity));
	Scenes.Add(GetWorld()->SpawnActor<ALsnSiteScene>(ALsnSiteScene::StaticClass(), FTransform(LsnPlanner::SecondSceneOffsetCm())));
	Scenes[0]->SetSceneSlot(0);
	Scenes[1]->SetSceneSlot(1);
	if (APlayerController* First = GetWorld()->GetFirstPlayerController())
	{
		First->HiddenActors.Add(Scenes[1]);
	}

	FString Directory;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPackage="), Directory))
	{
		// One package given by its directory: no site list.
		if (Scenes[0]->LoadPackageDirectory(FPaths::ConvertRelativePathToFull(Directory), LoadError))
		{
			ApplyViewOptions(Scenes[0]);
		}
	}
	else
	{
		PackageRoot = ResolvePackageRoot(LoadError);
		if (!PackageRoot.IsEmpty() && LsnPlanner::ListSites(PackageRoot, Sites, LoadError))
		{
			FString Wanted, CompareWith;
			FParse::Value(FCommandLine::Get(), TEXT("LsnSite="), Wanted);
			FString Compare;
			if (FParse::Value(FCommandLine::Get(), TEXT("LsnCompare="), Compare, false))
			{
				Compare.Split(TEXT(","), &Wanted, &CompareWith);
			}
			auto IndexOf = [this](const FString& SiteId)
			{
				return Sites.IndexOfByPredicate([&SiteId](const FLsnIndexEntry& Entry) { return Entry.SiteId == SiteId; });
			};
			const int32 FirstSite = Wanted.IsEmpty() ? 0 : IndexOf(Wanted);
			if (FirstSite == INDEX_NONE)
			{
				LoadError = FString::Printf(TEXT("%s has no site '%s'"), *PackageRoot, *Wanted);
			}
			else
			{
				SelectSite(0, FirstSite);
			}
			if (Scenes[0]->HasPackage() && !CompareWith.IsEmpty())
			{
				const int32 SecondSite = IndexOf(CompareWith);
				if (SecondSite == INDEX_NONE)
				{
					LoadError = FString::Printf(TEXT("%s has no site '%s'"), *PackageRoot, *CompareWith);
				}
				else
				{
					SelectSite(1, SecondSite);
				}
			}
		}
	}

	if (!Scenes[0]->HasPackage())
	{
		UE_LOG(LogLsn, Error, TEXT("No package is shown: %s"), *LoadError);
	}
	else
	{
		int32 Index = 0;
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnHeight="), Index))
		{
			Scenes[0]->SetHeightIndex(Index);
		}
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnTime="), Index))
		{
			Scenes[0]->SetTimeIndex(Index);
		}
	}

	if (FParse::Value(FCommandLine::Get(), TEXT("LsnMovieDir="), MovieDir))
	{
		MovieDir = FPaths::ConvertRelativePathToFull(MovieDir);
		IFileManager::Get().MakeDirectory(*MovieDir, true);
		// Leave time for shaders and shadow pages before the first frame is kept.
		MovieWarmUpFrames = 240;
	}
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnShot="), ShotPath))
	{
		ShotPath = FPaths::ConvertRelativePathToFull(ShotPath);
		// Leave time for shaders and shadow pages before the capture.
		FramesUntilShot = 240;
	}
}

void ALsnViewGameMode::SyncComparison()
{
	// The right view shows the instant, the observer height and the view options of the left one.
	if (bComparing && Scenes[0]->HasPackage() && Scenes[1]->HasPackage())
	{
		ALsnSiteScene* Left = Scenes[0];
		ALsnSiteScene* Right = Scenes[1];
		if (Right->GetHeightIndex() != Left->GetHeightIndex() && Left->GetHeightIndex() < Right->GetPackage().NumHeights())
		{
			Right->SetHeightIndex(Left->GetHeightIndex());
		}
		double Position = 0.0;
		bRightViewInRange = LsnPlanner::LinkedPosition(Left->GetPackage(), Left->GetTimePosition(), Right->GetPackage(), Position);
		if (bRightViewInRange && Position != Right->GetTimePosition())
		{
			Right->SetTimePosition(Position);
		}
		if (Right->IsObstacleViewEnabled() != Left->IsObstacleViewEnabled())
		{
			Right->SetObstacleViewEnabled(Left->IsObstacleViewEnabled());
		}
		if (Right->IsFillLightVisible() != Left->IsFillLightVisible())
		{
			Right->SetFillLightVisible(Left->IsFillLightVisible());
		}
		if (Right->IsHorizonLineVisible() != Left->IsHorizonLineVisible())
		{
			Right->SetHorizonLineVisible(Left->IsHorizonLineVisible());
		}
	}
}

void ALsnViewGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	SyncComparison();

#if WITH_EDITOR
	// Run from the editor binaries, materials may still be compiling: do not capture a half-built frame.
	if (FramesUntilShot > 0 && FramesUntilShot < 60 && GShaderCompilingManager && GShaderCompilingManager->IsCompiling())
	{
		FramesUntilShot = 60;
	}
#endif
	if (!MovieDir.IsEmpty())
	{
		const APlayerController* Player = GetWorld()->GetFirstPlayerController();
		const ALsnObserverPawn* Pawn = Player ? Cast<ALsnObserverPawn>(Player->GetPawn()) : nullptr;
		if (MovieWarmUpFrames > 0)
		{
			--MovieWarmUpFrames;
		}
		else if (FramesUntilQuit < 0)
		{
			FScreenshotRequest::RequestScreenshot(FPaths::Combine(MovieDir, FString::Printf(TEXT("frame_%05d.png"), MovieFrame++)), true, false);
			if (!Pawn || Pawn->HasFinishedCommandLinePlay())
			{
				FramesUntilQuit = 30;
				UE_LOG(LogLsn, Display, TEXT("%d movie frames requested in %s"), MovieFrame, *MovieDir);
			}
		}
	}
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
