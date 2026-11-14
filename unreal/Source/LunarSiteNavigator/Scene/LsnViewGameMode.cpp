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
#include "Misc/FileHelper.h"
#include "RHIGlobals.h"
#include "Engine/GameViewportClient.h"
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
		// The published packages, the sample that ships with the contract, then the copy pinned for the tests.
		const FString Published = LsnPlanner::PublishedPackageRoot();
		if (!Published.IsEmpty())
		{
			Roots.Add(Published);
		}
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
	if (!Scene->LoadPackageDirectory(SiteDirectory(SiteIndex), Error))
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
			if (Next < 0 || !Scenes[1]->LoadPackageDirectory(SiteDirectory(Next), Error))
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

	SetLowQuality(FParse::Param(FCommandLine::Get(), TEXT("LsnLowQuality")));

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
			// The site-pairs package of the root, if the science core wrote one.
			TArray<FLsnIndexEntry> Entries;
			FString Ignored;
			if (LsnPackageIO::LoadIndex(PackageRoot, Entries, Ignored))
			{
				for (const FLsnIndexEntry& Entry : Entries)
				{
					if (Entry.Kind == TEXT("site_pairs") && !bHasPairs)
					{
						bHasPairs = LsnPackageIO::LoadSitePairs(FPaths::Combine(PackageRoot, Entry.Path), Pairs, Ignored);
					}
				}
			}
			for (int32 I = 0; I < Sites.Num(); ++I)
			{
				AddSiteInfo(I);
			}
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
		FString Utc;
		double Position = 0.0;
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnUtc="), Utc))
		{
			if (LsnPlanner::PositionOfUtc(Scenes[0]->GetPackage(), Utc, Position))
			{
				Scenes[0]->SetTimePosition(Position);
			}
			else
			{
				UE_LOG(LogLsn, Error, TEXT("-LsnUtc=%s is not a time of this package."), *Utc);
			}
		}
	}

	FString PageName;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPage="), PageName))
	{
		Page = PageName == TEXT("calendar") ? ELsnPlannerPage::Calendar : PageName == TEXT("uncertainty") ? ELsnPlannerPage::Uncertainty
			: PageName == TEXT("trade") ? ELsnPlannerPage::Trade : PageName == TEXT("sites") ? ELsnPlannerPage::Sites : ELsnPlannerPage::Summary;
	}
	FParse::Value(FCommandLine::Get(), TEXT("LsnRequirement="), RequirementIndex);

	if (FParse::Value(FCommandLine::Get(), TEXT("LsnBench="), BenchPath))
	{
		BenchPath = FPaths::ConvertRelativePathToFull(BenchPath);
		FParse::Value(FCommandLine::Get(), TEXT("LsnBenchSeconds="), BenchSeconds);
		// The frame time is that of drawing, not of waiting for the display.
		if (IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync")))
		{
			VSync->Set(0, ECVF_SetByCode);
		}
		if (IConsoleVariable* MaxFps = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS")))
		{
			MaxFps->Set(0.0f, ECVF_SetByCode);
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
		FParse::Value(FCommandLine::Get(), TEXT("LsnShotFrames="), FramesUntilShot);
	}
	// -LsnCustom=<lat>,<lon>: as if typed into the site picker and "Compute and show" pressed.
	FString CustomText;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnCustom="), CustomText, false) && CustomText.Split(TEXT(","), &Custom.Latitude, &Custom.Longitude))
	{
		Page = ELsnPlannerPage::Sites;
		StartCustom();
	}
}

FString ALsnViewGameMode::SiteDirectory(int32 SiteIndex) const
{
	if (!Sites.IsValidIndex(SiteIndex))
	{
		return FString();
	}
	// Sites of the package root are listed by a relative path; a site computed for custom coordinates by its full path.
	return FPaths::IsRelative(Sites[SiteIndex].Path) ? FPaths::Combine(PackageRoot, Sites[SiteIndex].Path) : Sites[SiteIndex].Path;
}

void ALsnViewGameMode::AddSiteInfo(int32 SiteIndex)
{
	FLsnSiteInfo Info;
	Info.Group = Sites[SiteIndex].Programme.IsEmpty() ? FString(TEXT("Sites of the package root")) : Sites[SiteIndex].Programme;
	LsnPackageIO::ReadTerrainSourceOfDirectory(SiteDirectory(SiteIndex), Info.TerrainSource);
	SiteInfos.SetNum(FMath::Max(SiteInfos.Num(), SiteIndex + 1));
	SiteInfos[SiteIndex] = Info;
}

void ALsnViewGameMode::TypeCustom(TCHAR Character)
{
	FString& Field = Custom.Focus == 0 ? Custom.Latitude : Custom.Longitude;
	if ((FChar::IsDigit(Character) || Character == TEXT('.') || Character == TEXT('-')) && Field.Len() < 12 && !Custom.bRunning)
	{
		Field.AppendChar(Character);
	}
}

void ALsnViewGameMode::BackspaceCustom()
{
	FString& Field = Custom.Focus == 0 ? Custom.Latitude : Custom.Longitude;
	if (Field.Len() > 0 && !Custom.bRunning)
	{
		Field.LeftChopInline(1);
	}
}

void ALsnViewGameMode::StartCustom()
{
	if (Custom.bRunning)
	{
		return;
	}
	Custom.bFailed = true;
	Custom.Step = 0;
	Custom.HorizonLine.Reset();
	Custom.TimelineLine.Reset();
	double Latitude = 0.0, Longitude = 0.0;
	if (!LsnPlanner::ParseCoordinate(Custom.Latitude, -90.0, 90.0, Latitude))
	{
		Custom.Message = TEXT("The latitude must be a number from -90 to 90, for example -89.45.");
		return;
	}
	if (!LsnPlanner::ParseCoordinate(Custom.Longitude, -180.0, 360.0, Longitude))
	{
		Custom.Message = TEXT("The longitude (east positive) must be a number from -180 to 360, for example 222.8.");
		return;
	}
	// A Python environment with the science core: named on the command line or in LSN_PYTHON, else the usual places.
	TArray<FString> Candidates;
	FString Named;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnPython="), Named))
	{
		Candidates.Add(Named);
	}
	Named = FPlatformMisc::GetEnvironmentVariable(TEXT("LSN_PYTHON"));
	if (!Named.IsEmpty())
	{
		Candidates.Add(Named);
	}
	Candidates.Add(FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../.venv/Scripts/python.exe"))));
	Candidates.Add(TEXT("C:/Projects/lsn-venv/Scripts/python.exe"));
	CustomPython.Reset();
	for (const FString& Candidate : Candidates)
	{
		if (FPaths::FileExists(Candidate))
		{
			CustomPython = Candidate;
			break;
		}
	}
	if (CustomPython.IsEmpty())
	{
		Custom.Message = TEXT("No Python environment with the science core was found on this machine, so custom coordinates cannot be computed here. The published sites work without it. (Looked for LSN_PYTHON, .venv next to the repository, C:/Projects/lsn-venv.)");
		return;
	}
	// The command of the second step, if one has been given.
	CustomTimelineTemplate.Reset();
	if (!FParse::Value(FCommandLine::Get(), TEXT("LsnCustomTimeline="), CustomTimelineTemplate, false) && GConfig)
	{
		GConfig->GetString(TEXT("LunarSiteNavigator"), TEXT("CustomTimelineCommand"), CustomTimelineTemplate, GGameIni);
	}
	// Run from a checkout, the core and the data reader of this very repository are used, so that
	// the package is of the same contract version as the published ones.
	const FString RepoCore = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../core")));
	const FString RepoData = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../data")));
	if (FPaths::DirectoryExists(FPaths::Combine(RepoCore, TEXT("lsncore"))) && FPaths::DirectoryExists(FPaths::Combine(RepoData, TEXT("lsn_data"))))
	{
		FPlatformMisc::SetEnvironmentVar(TEXT("PYTHONPATH"), *(RepoCore + TEXT(";") + RepoData));
	}
	CustomRoot = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("LsnCustom")));
	IFileManager::Get().MakeDirectory(*CustomRoot, true);
	const FString Arguments = LsnPlanner::CustomSiteArguments(Custom.Latitude, Custom.Longitude, CustomRoot, CustomName);
	// The core states a few seconds for the horizon of one site.
	LaunchCustom(Arguments, 1, 4.0);
}

bool ALsnViewGameMode::LaunchCustom(const FString& Arguments, int32 Step, double StatedS)
{
	if (!FPlatformProcess::CreatePipe(CustomReadPipe, CustomWritePipe))
	{
		Custom.bFailed = true;
		Custom.Message = TEXT("The science core could not be started (no pipe).");
		return false;
	}
	CustomOutput.Reset();
	CustomProcess = FPlatformProcess::CreateProc(*CustomPython, *Arguments, false, true, true, nullptr, 0, nullptr, CustomWritePipe, nullptr);
	if (!CustomProcess.IsValid())
	{
		FPlatformProcess::ClosePipe(CustomReadPipe, CustomWritePipe);
		CustomReadPipe = CustomWritePipe = nullptr;
		Custom.bFailed = true;
		Custom.Message = FString::Printf(TEXT("The science core could not be started (%s)."), *CustomPython);
		return false;
	}
	Custom.bRunning = true;
	Custom.bFailed = false;
	Custom.Step = Step;
	Custom.StatedS = StatedS;
	Custom.StartedS = FPlatformTime::Seconds();
	UE_LOG(LogLsn, Display, TEXT("Custom coordinates, step %d: %s %s"), Step, *CustomPython, *Arguments);
	return true;
}

bool ALsnViewGameMode::LoadCustomResult(bool bNeedTimeline, FString& OutPackageId, FString& OutError)
{
	TArray<FLsnIndexEntry> Written;
	if (!LsnPlanner::ListSites(CustomRoot, Written, OutError))
	{
		return false;
	}
	const FLsnIndexEntry* Found = Written.FindByPredicate([this, bNeedTimeline](const FLsnIndexEntry& Entry) { return Entry.Name == CustomName && (!bNeedTimeline || Entry.bHasTimeline); });
	if (!Found)
	{
		OutError = bNeedTimeline ? TEXT("the core wrote no package with a timeline for this name") : TEXT("the core wrote no package for this name");
		return false;
	}
	FLsnIndexEntry Entry = *Found;
	Entry.Path = FPaths::Combine(CustomRoot, Entry.Path);
	Entry.Programme = TEXT("Custom coordinates (computed on this machine)");
	// One row per custom site: the package with the timeline takes the place of the horizon-only one.
	int32 Index = Sites.IndexOfByPredicate([&Entry](const FLsnIndexEntry& Known) { return Known.Name == Entry.Name && Known.Programme == Entry.Programme; });
	if (Index == INDEX_NONE)
	{
		Index = Sites.Add(Entry);
	}
	else
	{
		Sites[Index] = Entry;
	}
	AddSiteInfo(Index);
	OutPackageId = Entry.PackageId;
	if (!SelectSite(0, Index))
	{
		OutError = LoadError;
		return false;
	}
	return true;
}

void ALsnViewGameMode::TickCustom()
{
	if (!Custom.bRunning)
	{
		return;
	}
	CustomOutput += FPlatformProcess::ReadPipe(CustomReadPipe);
	const double RunS = FPlatformTime::Seconds() - Custom.StartedS;
	Custom.Message = Custom.Step == 1
		? FString::Printf(TEXT("Step 1 of 2, terrain horizon of %s: the science core has run %.0f s (a few seconds)"), *CustomName, RunS)
		: FString::Printf(TEXT("Step 2 of 2, Sun and Earth timeline: the science core has run %.0f s of about %.0f s"), RunS, Custom.StatedS);
	if (FPlatformProcess::IsProcRunning(CustomProcess))
	{
		return;
	}
	int32 ReturnCode = -1;
	FPlatformProcess::GetProcReturnCode(CustomProcess, &ReturnCode);
	CustomOutput += FPlatformProcess::ReadPipe(CustomReadPipe);
	FPlatformProcess::ClosePipe(CustomReadPipe, CustomWritePipe);
	FPlatformProcess::CloseProc(CustomProcess);
	CustomReadPipe = CustomWritePipe = nullptr;
	Custom.bRunning = false;
	const int32 Step = Custom.Step;
	FString PackageId, Error;
	if (ReturnCode != 0 || !LoadCustomResult(Step == 2, PackageId, Error))
	{
		// The last line the core printed says what went wrong.
		TArray<FString> Lines;
		CustomOutput.ParseIntoArrayLines(Lines);
		const FString Why = FString::Printf(TEXT("the science core did not write a package (exit code %d). %s"), ReturnCode, Lines.Num() > 0 ? *Lines.Last() : *Error);
		if (Step == 2)
		{
			// The horizon of the first step stays on screen.
			Custom.TimelineLine = FString::Printf(TEXT("Step 2 of 2, Sun and Earth timeline: %s The terrain horizon stays shown."), *Why);
			Custom.Message = Custom.TimelineLine;
		}
		else
		{
			Custom.Message = TEXT("Step 1 of 2, terrain horizon: ") + Why;
		}
		Custom.bFailed = true;
		return;
	}
	// What the result rests on: the package's own terrain source (since contract 0.9).
	const FLsnSitePackage& Loaded = Scenes[0]->GetPackage();
	const FString Terrain = Loaded.TerrainSource.bPresent
		? FString::Printf(TEXT("terrain %s, %s class, %.0f m pixels"), *Loaded.TerrainSource.ProductId, *Loaded.TerrainSource.ResolutionClass, Loaded.TerrainSource.PixelM)
		: FString::Printf(TEXT("the package (contract %s) does not say which terrain product served the site"), *Loaded.ContractVersion);
	if (Step == 1)
	{
		Page = ELsnPlannerPage::Summary;
		Custom.HorizonLine = FString::Printf(TEXT("Step 1 of 2 done in %.0f s: terrain horizon of %s, package %s; %s."), RunS, *CustomName, *PackageId, *Terrain);
		const FString Arguments = LsnPlanner::CustomTimelineArguments(CustomTimelineTemplate, Custom.Latitude, Custom.Longitude, CustomName, CustomRoot);
		if (Arguments.IsEmpty())
		{
			Custom.TimelineLine = TEXT("Step 2 of 2, Sun and Earth timeline: not available in this build (no command of the science core has been set for it); the horizon only is shown.");
			Custom.Message = Custom.TimelineLine;
		}
		else
		{
			// The core states about half a minute for a complete package with a short timeline.
			LaunchCustom(Arguments, 2, 30.0);
		}
	}
	else
	{
		Custom.TimelineLine = FString::Printf(TEXT("Step 2 of 2 done in %.0f s: Sun and Earth timeline, package %s; %s."), RunS, *PackageId, *Terrain);
		Custom.Message = Custom.TimelineLine;
	}
}

void ALsnViewGameMode::SetLowQuality(bool bLow)
{
	bLowQuality = bLow;
	// An airless body has hard shadows whose only softness is the size of the Sun's disc:
	// finer shadow pages and more rays for the penumbra than the engine's defaults. The low
	// quality draws two thirds of the resolution (the engine scales it up) and coarser shadows.
	const TPair<const TCHAR*, float> Settings[] = {
		{ TEXT("r.ScreenPercentage"), bLow ? 67.0f : 100.0f },
		{ TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), bLow ? 0.5f : -1.0f },
		{ TEXT("r.Shadow.Virtual.SMRT.RayCountDirectional"), bLow ? 4.0f : 16.0f },
		{ TEXT("r.Shadow.Virtual.SMRT.SamplesPerRayDirectional"), bLow ? 4.0f : 8.0f },
	};
	for (const TPair<const TCHAR*, float>& Setting : Settings)
	{
		if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Setting.Key))
		{
			Variable->Set(Setting.Value, ECVF_SetByCode);
		}
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
		if (Right->AreScaleObjectsVisible() != Left->AreScaleObjectsVisible())
		{
			Right->SetScaleObjectsVisible(Left->AreScaleObjectsVisible());
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
	TickCustom();

#if WITH_EDITOR
	// Run from the editor binaries, materials may still be compiling: do not capture a half-built frame.
	if (FramesUntilShot > 0 && FramesUntilShot < 60 && GShaderCompilingManager && GShaderCompilingManager->IsCompiling())
	{
		FramesUntilShot = 60;
	}
#endif
	if (!BenchPath.IsEmpty() && FramesUntilQuit < 0)
	{
		if (BenchWarmUpS > 0.0)
		{
			BenchWarmUpS -= DeltaSeconds;
		}
		else
		{
			BenchFrameMs.Add(1000.0f * DeltaSeconds);
			BenchSeconds -= DeltaSeconds;
			if (BenchSeconds <= 0.0 && BenchFrameMs.Num() > 0)
			{
				BenchFrameMs.Sort();
				double Sum = 0.0;
				for (const float Ms : BenchFrameMs)
				{
					Sum += Ms;
				}
				const int32 N = BenchFrameMs.Num();
				const FIntPoint Size = GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport ? GEngine->GameViewport->Viewport->GetSizeXY() : FIntPoint::ZeroValue;
				const FString Report = FString::Printf(TEXT("frames %d\nmean_ms %.3f\nmedian_ms %.3f\np95_ms %.3f\np99_ms %.3f\nmax_ms %.3f\nresolution %dx%d\ncomparing %d\nlow_quality %d\ngpu %s\n"),
					N, Sum / N, BenchFrameMs[N / 2], BenchFrameMs[FMath::Min(N - 1, N * 95 / 100)], BenchFrameMs[FMath::Min(N - 1, N * 99 / 100)], BenchFrameMs[N - 1],
					Size.X, Size.Y, bComparing ? 1 : 0, bLowQuality ? 1 : 0, *GRHIAdapterName);
				FFileHelper::SaveStringToFile(Report, *BenchPath);
				UE_LOG(LogLsn, Display, TEXT("Frame times written: %s"), *BenchPath);
				FramesUntilQuit = 5;
			}
		}
	}
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
