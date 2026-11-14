#include "Scene/LsnObserverPawn.h"

#include "Camera/CameraComponent.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Planner/LsnPlanner.h"
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

		// A stretch of the timeline to play once, for recordings.
		double PlayFrom = 0.0, PlaySeconds = 25.0;
		if (!bRightView && FParse::Value(FCommandLine::Get(), TEXT("LsnPlayFrom="), PlayFrom) && FParse::Value(FCommandLine::Get(), TEXT("LsnPlayTo="), PlayTo) && PlayTo > PlayFrom)
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

	APlayerController* PC = Cast<APlayerController>(GetController());
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

	// Tab: mouse cursor for the time strips instead of mouse look.
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
	if (PC->bShowMouseCursor)
	{
		// The strips are laid out in the view of this player (the left half when comparing).
		int32 SizeX = 0, SizeY = 0;
		float MouseX = 0.0f, MouseY = 0.0f;
		PC->GetViewportSize(SizeX, SizeY);
		if (GameMode && GameMode->IsComparing())
		{
			SizeX /= 2;
		}
		double Position = 0.0;
		if (Package.bHasTimeline && PC->IsInputKeyDown(EKeys::LeftMouseButton) && PC->GetMousePosition(MouseX, MouseY)
			&& FLsnTimeStripLayout::Make(SizeX, SizeY, Package).PositionAt(FVector2D(MouseX, MouseY), Package, Scene->GetTimePosition(), Position))
		{
			bPlaying = false;
			Scene->SetTimePosition(Position);
		}
	}
	else
	{
		const double LookRate = 0.08 * FovDeg / 60.0;
		float MouseX = 0.0f, MouseY = 0.0f;
		PC->GetInputMouseDelta(MouseX, MouseY);
		Turn += MouseX * LookRate;
		ElevationDeg += MouseY * LookRate;
	}

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
	if (PC->WasInputKeyJustPressed(EKeys::F))
	{
		bFollowSun = !bFollowSun;
		FollowOffsetDeg = 0.0;
	}

	// Stepping lands on whole samples, where the scene shows the package values unchanged.
	auto StepSamples = [&](int32 Samples)
	{
		bPlaying = false;
		const bool bBetween = Scene->GetTimePosition() > Scene->GetTimeIndex();
		const int32 From = Scene->GetTimeIndex() + ((Samples < 0 && bBetween) ? 1 : 0);
		Scene->SetTimeIndex(FMath::Clamp(From + Samples, 0, static_cast<int32>(LastPosition)));
	};
	const int32 SamplesPerDay = Package.Time.StepS > 0.0 ? FMath::Max(FMath::RoundToInt32(86400.0 / Package.Time.StepS), 1) : 1;
	if (PC->WasInputKeyJustPressed(EKeys::E)) { StepSamples(bShift ? 24 : 1); }
	if (PC->WasInputKeyJustPressed(EKeys::Q)) { StepSamples(bShift ? -24 : -1); }
	if (PC->WasInputKeyJustPressed(EKeys::Period)) { StepSamples(SamplesPerDay); }
	if (PC->WasInputKeyJustPressed(EKeys::Comma)) { StepSamples(-SamplesPerDay); }
	if (PC->WasInputKeyJustPressed(EKeys::Home)) { bPlaying = false; Scene->SetTimeIndex(0); }
	if (PC->WasInputKeyJustPressed(EKeys::End)) { bPlaying = false; Scene->SetTimeIndex(static_cast<int32>(LastPosition)); }

	// N / B: to the next or previous rise or set of the package (Shift: of the Earth).
	const int32 Direction = (PC->WasInputKeyJustPressed(EKeys::N) ? 1 : 0) - (PC->WasInputKeyJustPressed(EKeys::B) ? 1 : 0);
	if (Direction != 0 && Package.bHasTimeline && Package.Time.StepS > 0.0)
	{
		const double EtS = Package.EtOfPosition(Scene->GetTimePosition());
		if (const FLsnEvent* Event = LsnPlanner::AdjacentEvent(Package, bShift ? TEXT("EARTH") : TEXT("SUN"), Scene->GetHeightIndex(), EtS, Direction))
		{
			bPlaying = false;
			Scene->SetTimePosition(FMath::Clamp((Event->EtS - Package.Time.StartEtS) / Package.Time.StepS, 0.0, LastPosition));
		}
	}

	if (PC->WasInputKeyJustPressed(EKeys::SpaceBar)) { bPlaying = !bPlaying; PlayTo = -1.0; }
	if (PC->WasInputKeyJustPressed(EKeys::LeftBracket)) { PlayRate = FMath::Max(PlayRate * 0.5, 0.125); }
	if (PC->WasInputKeyJustPressed(EKeys::RightBracket)) { PlayRate = FMath::Min(PlayRate * 2.0, 768.0); }
	if (PC->WasInputKeyJustPressed(EKeys::H)) { Scene->SetHorizonLineVisible(!Scene->IsHorizonLineVisible()); }
	if (PC->WasInputKeyJustPressed(EKeys::Escape)) { PC->ConsoleCommand(TEXT("quit")); }
	if (PC->WasInputKeyJustPressed(EKeys::O)) { Scene->SetObstacleViewEnabled(!Scene->IsObstacleViewEnabled()); }
	if (PC->WasInputKeyJustPressed(EKeys::L)) { Scene->SetFillLightVisible(!Scene->IsFillLightVisible()); }
	if (PC->WasInputKeyJustPressed(EKeys::PageUp)) { Scene->SetHeightIndex(Scene->GetHeightIndex() + 1); }
	if (PC->WasInputKeyJustPressed(EKeys::PageDown)) { Scene->SetHeightIndex(Scene->GetHeightIndex() - 1); }

	// Sites and comparison.
	if (GameMode)
	{
		static const FKey Digits[] = { EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine };
		for (int32 I = 0; I < UE_ARRAY_COUNT(Digits); ++I)
		{
			if (PC->WasInputKeyJustPressed(Digits[I]))
			{
				GameMode->SelectSite(bShift ? 1 : 0, I);
				if (bShift)
				{
					bFollowSun = true;
				}
			}
		}
		if (PC->WasInputKeyJustPressed(EKeys::K)) { GameMode->TogglePage(ELsnPlannerPage::Calendar); }
		if (PC->WasInputKeyJustPressed(EKeys::U)) { GameMode->TogglePage(ELsnPlannerPage::Uncertainty); }
		if (PC->WasInputKeyJustPressed(EKeys::M)) { GameMode->TogglePage(ELsnPlannerPage::Trade); }
		if (PC->WasInputKeyJustPressed(EKeys::R)) { GameMode->NextRequirement(); }
		if (PC->WasInputKeyJustPressed(EKeys::C))
		{
			GameMode->SetComparing(!GameMode->IsComparing());
			if (GameMode->IsComparing())
			{
				bFollowSun = true;
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
