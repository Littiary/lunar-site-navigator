#include "Scene/LsnObserverPawn.h"

#include "Camera/CameraComponent.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Planner/LsnPlanner.h"
#include "ProceduralMeshComponent.h"
#include "Scene/LsnHud.h"
#include "Scene/LsnSiteScene.h"
#include "Scene/LsnViewGameMode.h"

ALsnObserverPawn::ALsnObserverPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	SetRootComponent(Camera);
	Camera->bUsePawnControlRotation = false;
	// The two halves of a comparison are narrower than the screen; the field of view is the horizontal one.
	Camera->bConstrainAspectRatio = false;

	// Fixed exposure: no eye adaptation, no bloom, no lens effects. An airless
	// scene has nothing that would scatter light. The values are display
	// settings of stage 1, not photometry.
	FPostProcessSettings& Post = Camera->PostProcessSettings;
	Post.bOverride_AutoExposureMethod = true;
	Post.AutoExposureMethod = AEM_Manual;
	Post.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	Post.AutoExposureApplyPhysicalCameraExposure = false;
	Post.bOverride_AutoExposureBias = true;
	// Chosen for a Sun a few degrees above the horizon: level ground in grazing light is a
	// mid grey, slopes facing the Sun are bright, and nothing is lifted out of the shadows.
	Post.AutoExposureBias = -0.5f;
	Post.bOverride_BloomIntensity = true;
	Post.BloomIntensity = 0.0f;
	Post.bOverride_LensFlareIntensity = true;
	Post.LensFlareIntensity = 0.0f;
	Post.bOverride_VignetteIntensity = true;
	Post.VignetteIntensity = 0.0f;
	Post.bOverride_MotionBlurAmount = true;
	Post.MotionBlurAmount = 0.0f;
	Camera->PostProcessBlendWeight = 1.0f;
}

const TArray<FName>& ALsnObserverPawn::KnownActions()
{
	static const TArray<FName> Actions = {
		TEXT("play"), TEXT("slower"), TEXT("faster"), TEXT("sample_back"), TEXT("sample_forward"), TEXT("day_back"), TEXT("day_forward"),
		TEXT("sun_event_back"), TEXT("sun_event_forward"), TEXT("earth_event_back"), TEXT("earth_event_forward"), TEXT("first_sample"), TEXT("last_sample"),
		TEXT("next_site"), TEXT("next_right_site"), TEXT("compare"), TEXT("page_calendar"), TEXT("page_uncertainty"), TEXT("page_trade"), TEXT("next_requirement"),
		TEXT("obstacle"), TEXT("horizon_line"), TEXT("fill_light"), TEXT("follow_sun"), TEXT("height_up"), TEXT("height_down"), TEXT("height_next"), TEXT("quality"), TEXT("help"), TEXT("quit"),
	};
	return Actions;
}

ALsnSiteScene* ALsnObserverPawn::FindScene() const
{
	if (const ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>())
	{
		return GameMode->GetSceneOf(GetController());
	}
	for (TActorIterator<ALsnSiteScene> It(GetWorld()); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

void ALsnObserverPawn::BeginPlay()
{
	Super::BeginPlay();
	FParse::Value(FCommandLine::Get(), TEXT("LsnFov="), FovDeg);
	FParse::Value(FCommandLine::Get(), TEXT("LsnCameraUp="), CameraUpM);
	FParse::Value(FCommandLine::Get(), TEXT("LsnCameraBack="), CameraBackM);
}

void ALsnObserverPawn::ApplyView()
{
	ElevationDeg = FMath::Clamp(ElevationDeg, -89.0, 89.0);
	AzimuthDeg = FMath::Fmod(FMath::Fmod(AzimuthDeg, 360.0) + 360.0, 360.0);
	FovDeg = FMath::Clamp(FovDeg, 1.0, 120.0);
	// Yaw is azimuth and pitch is elevation in the site frame (see the frame tests).
	SetActorRotation(FRotator(ElevationDeg, AzimuthDeg, 0.0));
	if (IsOverview())
	{
		if (const ALsnSiteScene* Scene = FindScene())
		{
			const FVector Back = FLsnSiteFrame::AzElToUnrealDir(AzimuthDeg, 0.0) * (-CameraBackM * FLsnSiteFrame::CmPerM);
			SetActorLocation(Scene->GetEyeUnreal() + Back + FVector(0.0, 0.0, CameraUpM * FLsnSiteFrame::CmPerM));
		}
	}
	Camera->SetFieldOfView(static_cast<float>(FovDeg));
}

void ALsnObserverPawn::FollowLeftView(const ALsnObserverPawn& Left)
{
	// The right view of a comparison: same zoom and elevation, and either the same azimuth
	// or, when following the Sun, the same offset from its own Sun.
	FovDeg = Left.FovDeg;
	ElevationDeg = Left.ElevationDeg;
	bFollowSun = Left.bFollowSun;
	FollowOffsetDeg = Left.FollowOffsetDeg;
	if (!bFollowSun)
	{
		AzimuthDeg = Left.AzimuthDeg;
	}
}

void ALsnObserverPawn::StepSamples(ALsnSiteScene* Scene, int32 Samples)
{
	// Stepping lands on whole samples, where the scene shows the package values unchanged.
	bPlaying = false;
	const int32 Last = FMath::Max(Scene->GetPackage().Time.Count - 1, 0);
	const bool bBetween = Scene->GetTimePosition() > Scene->GetTimeIndex();
	const int32 From = Scene->GetTimeIndex() + ((Samples < 0 && bBetween) ? 1 : 0);
	Scene->SetTimeIndex(FMath::Clamp(From + Samples, 0, Last));
}

void ALsnObserverPawn::JumpToEvent(ALsnSiteScene* Scene, const TCHAR* Body, int32 Direction)
{
	const FLsnSitePackage& Package = Scene->GetPackage();
	if (!Package.bHasTimeline || !(Package.Time.StepS > 0.0))
	{
		return;
	}
	const double EtS = Package.EtOfPosition(Scene->GetTimePosition());
	if (const FLsnEvent* Event = LsnPlanner::AdjacentEvent(Package, Body, Scene->GetHeightIndex(), EtS, Direction))
	{
		bPlaying = false;
		Scene->SetTimePosition(FMath::Clamp((Event->EtS - Package.Time.StartEtS) / Package.Time.StepS, 0.0, static_cast<double>(FMath::Max(Package.Time.Count - 1, 0))));
	}
}

bool ALsnObserverPawn::DoAction(FName Action)
{
	if (!KnownActions().Contains(Action))
	{
		return false;
	}
	ALsnSiteScene* Scene = FindScene();
	ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>();
	if (!Scene || !Scene->HasPackage())
	{
		return true;
	}
	const FLsnSitePackage& Package = Scene->GetPackage();
	const int32 SamplesPerDay = Package.Time.StepS > 0.0 ? FMath::Max(FMath::RoundToInt32(86400.0 / Package.Time.StepS), 1) : 1;
	const int32 NumSites = GameMode ? GameMode->GetSites().Num() : 0;

	if (Action == TEXT("play")) { bPlaying = !bPlaying; PlayTo = -1.0; }
	else if (Action == TEXT("slower")) { PlayRate = FMath::Max(PlayRate * 0.5, 0.125); }
	else if (Action == TEXT("faster")) { PlayRate = FMath::Min(PlayRate * 2.0, 768.0); }
	else if (Action == TEXT("sample_back")) { StepSamples(Scene, -1); }
	else if (Action == TEXT("sample_forward")) { StepSamples(Scene, 1); }
	else if (Action == TEXT("day_back")) { StepSamples(Scene, -SamplesPerDay); }
	else if (Action == TEXT("day_forward")) { StepSamples(Scene, SamplesPerDay); }
	else if (Action == TEXT("sun_event_back")) { JumpToEvent(Scene, TEXT("SUN"), -1); }
	else if (Action == TEXT("sun_event_forward")) { JumpToEvent(Scene, TEXT("SUN"), 1); }
	else if (Action == TEXT("earth_event_back")) { JumpToEvent(Scene, TEXT("EARTH"), -1); }
	else if (Action == TEXT("earth_event_forward")) { JumpToEvent(Scene, TEXT("EARTH"), 1); }
	else if (Action == TEXT("first_sample")) { bPlaying = false; Scene->SetTimeIndex(0); }
	else if (Action == TEXT("last_sample")) { bPlaying = false; Scene->SetTimeIndex(FMath::Max(Package.Time.Count - 1, 0)); }
	else if (Action == TEXT("next_site"))
	{
		if (GameMode && NumSites > 0) { GameMode->SelectSite(0, (FMath::Max(GameMode->GetSelectedSite(0), -1) + 1) % NumSites); }
	}
	else if (Action == TEXT("next_right_site"))
	{
		if (GameMode && NumSites > 0)
		{
			// The first press shows the site after the left one; further presses go through the list.
			const int32 Current = GameMode->IsComparing() ? GameMode->GetSelectedSite(1) : GameMode->GetSelectedSite(0);
			GameMode->SelectSite(1, (FMath::Max(Current, -1) + 1) % NumSites);
			bFollowSun = true;
		}
	}
	else if (Action == TEXT("compare"))
	{
		if (GameMode)
		{
			GameMode->SetComparing(!GameMode->IsComparing());
			bFollowSun = bFollowSun || GameMode->IsComparing();
		}
	}
	else if (Action == TEXT("page_calendar")) { if (GameMode) { GameMode->TogglePage(ELsnPlannerPage::Calendar); } }
	else if (Action == TEXT("page_uncertainty")) { if (GameMode) { GameMode->TogglePage(ELsnPlannerPage::Uncertainty); } }
	else if (Action == TEXT("page_trade")) { if (GameMode) { GameMode->TogglePage(ELsnPlannerPage::Trade); } }
	else if (Action == TEXT("next_requirement")) { if (GameMode) { GameMode->NextRequirement(); } }
	else if (Action == TEXT("obstacle")) { Scene->SetObstacleViewEnabled(!Scene->IsObstacleViewEnabled()); }
	else if (Action == TEXT("horizon_line")) { Scene->SetHorizonLineVisible(!Scene->IsHorizonLineVisible()); }
	else if (Action == TEXT("fill_light")) { Scene->SetFillLightVisible(!Scene->IsFillLightVisible()); }
	else if (Action == TEXT("follow_sun")) { bFollowSun = !bFollowSun; FollowOffsetDeg = 0.0; }
	else if (Action == TEXT("height_up")) { Scene->SetHeightIndex(Scene->GetHeightIndex() + 1); }
	else if (Action == TEXT("height_down")) { Scene->SetHeightIndex(Scene->GetHeightIndex() - 1); }
	else if (Action == TEXT("height_next")) { Scene->SetHeightIndex((Scene->GetHeightIndex() + 1) % FMath::Max(Package.NumHeights(), 1)); }
	else if (Action == TEXT("quality")) { if (GameMode) { GameMode->SetLowQuality(!GameMode->IsLowQuality()); } }
	else if (Action == TEXT("help")) { bShowHelp = !bShowHelp; }
	else if (Action == TEXT("quit"))
	{
		if (APlayerController* PC = Cast<APlayerController>(GetController()))
		{
			PC->ConsoleCommand(TEXT("quit"));
		}
	}
	if (GameMode)
	{
		GameMode->SyncComparison();
	}
	return true;
}

void ALsnObserverPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	ALsnSiteScene* Scene = FindScene();
	if (!Scene || !Scene->HasPackage())
	{
		return;
	}
	SetActorLocation(Scene->GetEyeUnreal());

	ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>();
	const bool bRightView = GameMode && GameMode->GetViewIndexOf(GetController()) == 1;
	APlayerController* PC = Cast<APlayerController>(GetController());

	if (IsOverview() && Scene->GetMoonSphereComponent()->IsVisible())
	{
		// The reference sphere is drawn sunk so that the observer never sees it; where the real
		// terrain lies deeper than that (a crater floor) it would cover the terrain when seen
		// from above. An overview shows the elevation data only.
		Scene->GetMoonSphereComponent()->SetVisibility(false);
	}

	if (!bInitialised)
	{
		bInitialised = true;
		// Look towards the azimuth of the Sun by default, level.
		const FVector ToSun = Scene->GetSunDirectionFromLight();
		double El = 0.0;
		FLsnSiteFrame::UnrealDirToAzEl(ToSun, AzimuthDeg, El);
		ElevationDeg = 0.0;
		bFollowSun = FParse::Param(FCommandLine::Get(), TEXT("LsnFollowSun")) || (GameMode && GameMode->IsComparing());
		FParse::Value(FCommandLine::Get(), TEXT("LsnPitch="), ElevationDeg);
		if (bFollowSun)
		{
			// With the view on the Sun, -LsnYaw is the offset from the Sun's azimuth.
			FParse::Value(FCommandLine::Get(), TEXT("LsnYaw="), FollowOffsetDeg);
		}
		else
		{
			FParse::Value(FCommandLine::Get(), TEXT("LsnYaw="), AzimuthDeg);
		}

		// The cursor is visible from the start: the buttons and the time strips are used with it.
		if (PC && !bRightView)
		{
			PC->bShowMouseCursor = true;
			PC->bEnableClickEvents = true;
			PC->SetInputMode(FInputModeGameAndUI().SetHideCursorDuringCapture(false));
		}

		// -LsnDo=<action>,<action>: carry out named actions at the start (for captures and for
		// checking a build without a hand on the mouse).
		FString Do;
		if (!bRightView && FParse::Value(FCommandLine::Get(), TEXT("LsnDo="), Do, false))
		{
			TArray<FString> Names;
			Do.ParseIntoArray(Names, TEXT(","));
			for (const FString& Name : Names)
			{
				if (!DoAction(FName(*Name)))
				{
					UE_LOG(LogTemp, Error, TEXT("-LsnDo: '%s' is not an action."), *Name);
				}
			}
		}

		// A stretch of the timeline to play once, for recordings.
		double PlayFrom = 0.0, PlaySeconds = 25.0;
		// The stretch by sample positions, or by UTC (-LsnPlayFromUtc= -LsnPlayToUtc=).
		FString FromUtc, ToUtc;
		bool bHasStretch = FParse::Value(FCommandLine::Get(), TEXT("LsnPlayFrom="), PlayFrom) && FParse::Value(FCommandLine::Get(), TEXT("LsnPlayTo="), PlayTo);
		if (FParse::Value(FCommandLine::Get(), TEXT("LsnPlayFromUtc="), FromUtc) && FParse::Value(FCommandLine::Get(), TEXT("LsnPlayToUtc="), ToUtc))
		{
			bHasStretch = LsnPlanner::PositionOfUtc(Scene->GetPackage(), FromUtc, PlayFrom) && LsnPlanner::PositionOfUtc(Scene->GetPackage(), ToUtc, PlayTo);
		}
		if (!bRightView && bHasStretch && PlayTo > PlayFrom)
		{
			FParse::Value(FCommandLine::Get(), TEXT("LsnPlaySeconds="), PlaySeconds);
			Scene->SetTimePosition(PlayFrom);
			PlayRate = (PlayTo - PlayFrom) / FMath::Max(PlaySeconds, 1.0);
			bPlaying = true;
		}
		else
		{
			PlayTo = -1.0;
		}
	}

	if (bRightView)
	{
		const APlayerController* First = GetWorld()->GetFirstPlayerController();
		if (const ALsnObserverPawn* Left = First ? Cast<ALsnObserverPawn>(First->GetPawn()) : nullptr)
		{
			FollowLeftView(*Left);
		}
	}
	else if (PC)
	{
		HandleInput(PC, Scene, DeltaSeconds);
		if (GameMode)
		{
			GameMode->SyncComparison();
		}
	}

	if (bFollowSun)
	{
		// The Sun's azimuth is the package's, at the selected time.
		FLsnBodyAtTime Sun;
		if (Scene->SampleBody(TEXT("SUN"), Scene->GetTimePosition(), Sun))
		{
			AzimuthDeg = Sun.AzimuthDeg + FollowOffsetDeg;
		}
	}
	ApplyView();
}

void ALsnObserverPawn::HandleInput(APlayerController* PC, ALsnSiteScene* Scene, float DeltaSeconds)
{
	ALsnViewGameMode* GameMode = GetWorld()->GetAuthGameMode<ALsnViewGameMode>();
	const FLsnSitePackage& Package = Scene->GetPackage();
	const double LastPosition = FMath::Max(Package.Time.Count - 1, 0);
	const bool bShift = PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift);
	double Turn = 0.0;

	// Tab: hide the cursor and look with the mouse alone; Tab again brings the cursor back.
	if (PC->WasInputKeyJustPressed(EKeys::Tab))
	{
		PC->bShowMouseCursor = !PC->bShowMouseCursor;
		if (PC->bShowMouseCursor)
		{
			PC->SetInputMode(FInputModeGameAndUI().SetHideCursorDuringCapture(false));
		}
		else
		{
			PC->SetInputMode(FInputModeGameOnly());
		}
	}
	const double LookRate = 0.08 * FovDeg / 60.0;
	float MouseX = 0.0f, MouseY = 0.0f;
	PC->GetInputMouseDelta(MouseX, MouseY);
	if (PC->bShowMouseCursor)
	{
		// With the cursor: the right button held looks around, the left button drags the time strips
		// (laid out in the view of this player: the left half when comparing).
		if (PC->IsInputKeyDown(EKeys::RightMouseButton))
		{
			Turn += MouseX * LookRate;
			ElevationDeg += MouseY * LookRate;
		}
		int32 SizeX = 0, SizeY = 0;
		float CursorX = 0.0f, CursorY = 0.0f;
		PC->GetViewportSize(SizeX, SizeY);
		if (GameMode && GameMode->IsComparing())
		{
			SizeX /= 2;
		}
		// A click on a button carries out its action.
		if (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton) && PC->GetMousePosition(CursorX, CursorY) && !FParse::Param(FCommandLine::Get(), TEXT("LsnNoHud")))
		{
			const FName Clicked = FLsnToolbar::Make(SizeX, SizeY).ActionAt(FVector2D(CursorX, CursorY));
			if (!Clicked.IsNone())
			{
				DoAction(Clicked);
			}
		}
		double Position = 0.0;
		if (Package.bHasTimeline && PC->IsInputKeyDown(EKeys::LeftMouseButton) && PC->GetMousePosition(CursorX, CursorY)
			&& FLsnTimeStripLayout::Make(SizeX, SizeY, Package).PositionAt(FVector2D(CursorX, CursorY), Package, Scene->GetTimePosition(), Position))
		{
			bPlaying = false;
			Scene->SetTimePosition(Position);
		}
	}
	else
	{
		Turn += MouseX * LookRate;
		ElevationDeg += MouseY * LookRate;
	}
	if (PC->WasInputKeyJustPressed(EKeys::MouseScrollUp)) { FovDeg *= 0.85; }
	if (PC->WasInputKeyJustPressed(EKeys::MouseScrollDown)) { FovDeg /= 0.85; }

	const double KeyRate = 30.0 * FovDeg / 60.0 * DeltaSeconds;
	if (PC->IsInputKeyDown(EKeys::Left)) { Turn -= KeyRate; }
	if (PC->IsInputKeyDown(EKeys::Right)) { Turn += KeyRate; }
	if (PC->IsInputKeyDown(EKeys::Up)) { ElevationDeg += KeyRate; }
	if (PC->IsInputKeyDown(EKeys::Down)) { ElevationDeg -= KeyRate; }
	if (PC->IsInputKeyDown(EKeys::Z)) { FovDeg *= FMath::Pow(0.5, static_cast<double>(DeltaSeconds)); }
	if (PC->IsInputKeyDown(EKeys::X)) { FovDeg *= FMath::Pow(2.0, static_cast<double>(DeltaSeconds)); }
	if (bFollowSun)
	{
		FollowOffsetDeg = FMath::Fmod(FollowOffsetDeg + Turn + 540.0, 360.0) - 180.0;
	}
	else
	{
		AzimuthDeg += Turn;
	}

	// Keys are other ways to the same named actions as the buttons on screen.
	struct FKeyAction { FKey Key; const TCHAR* Plain; const TCHAR* Shifted; };
	static const FKeyAction KeyActions[] = {
		{ EKeys::SpaceBar, TEXT("play"), TEXT("play") }, { EKeys::LeftBracket, TEXT("slower"), TEXT("slower") }, { EKeys::RightBracket, TEXT("faster"), TEXT("faster") },
		{ EKeys::Period, TEXT("day_forward"), TEXT("day_forward") }, { EKeys::Comma, TEXT("day_back"), TEXT("day_back") },
		{ EKeys::N, TEXT("sun_event_forward"), TEXT("earth_event_forward") }, { EKeys::B, TEXT("sun_event_back"), TEXT("earth_event_back") },
		{ EKeys::Home, TEXT("first_sample"), TEXT("first_sample") }, { EKeys::End, TEXT("last_sample"), TEXT("last_sample") },
		{ EKeys::C, TEXT("compare"), TEXT("compare") }, { EKeys::K, TEXT("page_calendar"), TEXT("page_calendar") }, { EKeys::U, TEXT("page_uncertainty"), TEXT("page_uncertainty") },
		{ EKeys::M, TEXT("page_trade"), TEXT("page_trade") }, { EKeys::R, TEXT("next_requirement"), TEXT("next_requirement") },
		{ EKeys::O, TEXT("obstacle"), TEXT("obstacle") }, { EKeys::H, TEXT("horizon_line"), TEXT("horizon_line") }, { EKeys::L, TEXT("fill_light"), TEXT("fill_light") },
		{ EKeys::F, TEXT("follow_sun"), TEXT("follow_sun") }, { EKeys::PageUp, TEXT("height_up"), TEXT("height_up") }, { EKeys::PageDown, TEXT("height_down"), TEXT("height_down") },
		{ EKeys::G, TEXT("quality"), TEXT("quality") }, { EKeys::F1, TEXT("help"), TEXT("help") }, { EKeys::Escape, TEXT("quit"), TEXT("quit") },
	};
	for (const FKeyAction& KeyAction : KeyActions)
	{
		if (PC->WasInputKeyJustPressed(KeyAction.Key))
		{
			DoAction(bShift ? KeyAction.Shifted : KeyAction.Plain);
		}
	}
	if (PC->WasInputKeyJustPressed(EKeys::E)) { StepSamples(Scene, bShift ? 24 : 1); }
	if (PC->WasInputKeyJustPressed(EKeys::Q)) { StepSamples(Scene, bShift ? -24 : -1); }
	if (GameMode)
	{
		static const FKey Digits[] = { EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine };
		for (int32 I = 0; I < UE_ARRAY_COUNT(Digits); ++I)
		{
			if (PC->WasInputKeyJustPressed(Digits[I]))
			{
				GameMode->SelectSite(bShift ? 1 : 0, I);
				bFollowSun = bFollowSun || bShift;
			}
		}
	}

	if (bPlaying && Package.bHasTimeline && !(GameMode && GameMode->IsWarmingUpForMovie()))
	{
		const double End = PlayTo >= 0.0 ? FMath::Min(PlayTo, LastPosition) : LastPosition;
		const double Next = FMath::Min(Scene->GetTimePosition() + PlayRate * DeltaSeconds, End);
		Scene->SetTimePosition(Next);
		if (Next >= End)
		{
			bPlaying = false;
			bCommandLinePlayDone = PlayTo >= 0.0;
		}
	}
}
