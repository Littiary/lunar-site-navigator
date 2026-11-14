#include "Scene/LsnObserverPawn.h"

#include "Camera/CameraComponent.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Scene/LsnSiteScene.h"

ALsnObserverPawn::ALsnObserverPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	SetRootComponent(Camera);
	Camera->bUsePawnControlRotation = false;

	// Fixed exposure: no eye adaptation, no bloom, no lens effects. An airless
	// scene has nothing that would scatter light. The values are display
	// settings of stage 1, not photometry.
	FPostProcessSettings& Post = Camera->PostProcessSettings;
	Post.bOverride_AutoExposureMethod = true;
	Post.AutoExposureMethod = AEM_Manual;
	Post.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	Post.AutoExposureApplyPhysicalCameraExposure = false;
	Post.bOverride_AutoExposureBias = true;
	Post.AutoExposureBias = 1.0f;
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
}

void ALsnObserverPawn::ApplyView()
{
	ElevationDeg = FMath::Clamp(ElevationDeg, -89.0, 89.0);
	AzimuthDeg = FMath::Fmod(AzimuthDeg + 360.0, 360.0);
	FovDeg = FMath::Clamp(FovDeg, 1.0, 120.0);
	// Yaw is azimuth and pitch is elevation in the site frame (see the frame tests).
	SetActorRotation(FRotator(ElevationDeg, AzimuthDeg, 0.0));
	Camera->SetFieldOfView(static_cast<float>(FovDeg));
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

	if (!bInitialised)
	{
		bInitialised = true;
		// Look towards the azimuth of the Sun by default, level.
		const FVector ToSun = Scene->GetSunDirectionFromLight();
		double El = 0.0;
		FLsnSiteFrame::UnrealDirToAzEl(ToSun, AzimuthDeg, El);
		ElevationDeg = 0.0;
		FParse::Value(FCommandLine::Get(), TEXT("LsnYaw="), AzimuthDeg);
		FParse::Value(FCommandLine::Get(), TEXT("LsnPitch="), ElevationDeg);
	}

	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		const double LookRate = 0.08 * FovDeg / 60.0;
		float MouseX = 0.0f, MouseY = 0.0f;
		PC->GetInputMouseDelta(MouseX, MouseY);
		AzimuthDeg += MouseX * LookRate;
		ElevationDeg += MouseY * LookRate;

		const double KeyRate = 30.0 * FovDeg / 60.0 * DeltaSeconds;
		if (PC->IsInputKeyDown(EKeys::Left)) { AzimuthDeg -= KeyRate; }
		if (PC->IsInputKeyDown(EKeys::Right)) { AzimuthDeg += KeyRate; }
		if (PC->IsInputKeyDown(EKeys::Up)) { ElevationDeg += KeyRate; }
		if (PC->IsInputKeyDown(EKeys::Down)) { ElevationDeg -= KeyRate; }
		if (PC->IsInputKeyDown(EKeys::Z)) { FovDeg *= FMath::Pow(0.5, static_cast<double>(DeltaSeconds)); }
		if (PC->IsInputKeyDown(EKeys::X)) { FovDeg *= FMath::Pow(2.0, static_cast<double>(DeltaSeconds)); }

		const int32 Step = (PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift)) ? 24 : 1;
		if (PC->WasInputKeyJustPressed(EKeys::E)) { Scene->SetTimeIndex(Scene->GetTimeIndex() + Step); }
		if (PC->WasInputKeyJustPressed(EKeys::Q)) { Scene->SetTimeIndex(Scene->GetTimeIndex() - Step); }
		if (PC->WasInputKeyJustPressed(EKeys::H)) { Scene->SetHorizonLineVisible(!Scene->IsHorizonLineVisible()); }
		if (PC->WasInputKeyJustPressed(EKeys::PageUp)) { Scene->SetHeightIndex(Scene->GetHeightIndex() + 1); }
		if (PC->WasInputKeyJustPressed(EKeys::PageDown)) { Scene->SetHeightIndex(Scene->GetHeightIndex() - 1); }
	}
	ApplyView();
}
