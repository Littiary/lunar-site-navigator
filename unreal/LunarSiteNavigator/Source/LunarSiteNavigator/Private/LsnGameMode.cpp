#include "LsnGameMode.h"

#include "Camera/CameraComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "LsnSiteScene.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"

ALsnGameMode::ALsnGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	DefaultPawnClass = ALsnObserverPawn::StaticClass();
	PlayerControllerClass = ALsnPlayerController::StaticClass();
	HUDClass = ALsnHud::StaticClass();
}

void ALsnGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);
	Scene = GetWorld()->SpawnActor<ALsnSiteScene>();

	const FString Root = LsnContract::FindPackageRoot();
	FLsnIndex Index;
	FString SiteId;
	FParse::Value(FCommandLine::Get(), TEXT("LsnSite="), SiteId);
	if (Root.IsEmpty())
	{
		LoadError = TEXT("No package root found. Pass -LsnPackageRoot=<dir> or put packages into <project>/Packages.");
	}
	else if (Index.Load(Root, LoadError))
	{
		const FString Dir = Index.FindPackageDir(TEXT("site"), SiteId);
		if (Dir.IsEmpty())
		{
			LoadError = FString::Printf(TEXT("No site package found in %s (site filter: '%s')"), *Root, *SiteId);
		}
		else if (Scene->LoadPackage(Dir, LoadError))
		{
			int32 TimeIndex = 0;
			if (FParse::Value(FCommandLine::Get(), TEXT("LsnTime="), TimeIndex))
			{
				Scene->SetTimeIndex(TimeIndex);
			}
		}
	}
	if (!LoadError.IsEmpty())
	{
		UE_LOG(LogTemp, Error, TEXT("Lsn: %s"), *LoadError);
	}
	FParse::Value(FCommandLine::Get(), TEXT("LsnScreenshot="), ScreenshotPath);
}

void ALsnGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (ScreenshotPath.IsEmpty())
	{
		return;
	}
	Elapsed += DeltaSeconds;
	if (!bScreenshotRequested && Elapsed > 6.0f)
	{
		FScreenshotRequest::RequestScreenshot(ScreenshotPath, true, false);
		bScreenshotRequested = true;
	}
	else if (bScreenshotRequested && Elapsed > 9.0f)
	{
		FPlatformMisc::RequestExit(false);
	}
}

ALsnSiteScene* ALsnGameMode::GetScene(const UObject* WorldContext)
{
	const UWorld* World = WorldContext != nullptr ? WorldContext->GetWorld() : nullptr;
	const ALsnGameMode* Mode = World != nullptr ? Cast<ALsnGameMode>(World->GetAuthGameMode()) : nullptr;
	return Mode != nullptr ? Mode->Scene.Get() : nullptr;
}

FString ALsnGameMode::GetLoadError(const UObject* WorldContext)
{
	const UWorld* World = WorldContext != nullptr ? WorldContext->GetWorld() : nullptr;
	const ALsnGameMode* Mode = World != nullptr ? Cast<ALsnGameMode>(World->GetAuthGameMode()) : nullptr;
	return Mode != nullptr ? Mode->LoadError : FString();
}

ALsnObserverPawn::ALsnObserverPawn()
{
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	RootComponent = Camera;
	Camera->bUsePawnControlRotation = true;
	Camera->SetFieldOfView(70.0f);
	float Fov = 0.0f;
	if (FParse::Value(FCommandLine::Get(), TEXT("LsnFov="), Fov) && Fov > 1.0f && Fov < 170.0f)
	{
		Camera->SetFieldOfView(Fov);
	}
}

void ALsnPlayerController::BeginPlay()
{
	Super::BeginPlay();
	SetInputMode(FInputModeGameOnly());
	bShowMouseCursor = false;
	bShowHorizonOverlay = !FParse::Param(FCommandLine::Get(), TEXT("LsnNoOverlay"));
}

void ALsnPlayerController::PlayerTick(float DeltaSeconds)
{
	Super::PlayerTick(DeltaSeconds);
	ALsnSiteScene* Scene = ALsnGameMode::GetScene(this);
	if (Scene == nullptr || !Scene->IsLoaded())
	{
		return;
	}
	const FLsnSitePackage& Package = Scene->GetPackage();
	if (APawn* Observer = GetPawn())
	{
		Observer->SetActorLocation(Package.ObserverWorldCm(Scene->GetHeightIndex()));
	}

	if (!bViewInitialised)
	{
		// Start looking at the horizon below the Sun, or north without a timeline.
		double Az = 0.0, El = 3.0;
		FLsnBodySky Sun;
		if (Scene->GetBody(TEXT("SUN"), Sun))
		{
			Az = Sun.AzimuthDeg;
		}
		FParse::Value(FCommandLine::Get(), TEXT("LsnAz="), Az);
		FParse::Value(FCommandLine::Get(), TEXT("LsnEl="), El);
		SetControlRotation(LsnFrame::AzElToRotator(Az, El));
		bViewInitialised = true;
	}

	float MouseX = 0.0f, MouseY = 0.0f;
	GetInputMouseDelta(MouseX, MouseY);
	FRotator View = GetControlRotation();
	View.Yaw += MouseX * 0.15;
	View.Pitch = FMath::Clamp(FRotator::NormalizeAxis(View.Pitch) + MouseY * 0.15, -89.0, 89.0);
	View.Roll = 0.0;
	SetControlRotation(View);

	// Time: Left / Right step one sample, held keys run, Shift runs ten times faster.
	const int32 Direction = (IsInputKeyDown(EKeys::Right) ? 1 : 0) - (IsInputKeyDown(EKeys::Left) ? 1 : 0);
	int32 Steps = (WasInputKeyJustPressed(EKeys::Right) ? 1 : 0) - (WasInputKeyJustPressed(EKeys::Left) ? 1 : 0);
	if (Direction != 0 && Steps == 0)
	{
		const double Rate = (IsInputKeyDown(EKeys::LeftShift) || IsInputKeyDown(EKeys::RightShift)) ? 120.0 : 12.0;
		TimeAccumulator += Direction * Rate * DeltaSeconds;
		Steps = static_cast<int32>(TimeAccumulator);
		TimeAccumulator -= Steps;
	}
	else if (Direction == 0)
	{
		TimeAccumulator = 0.0;
	}
	if (Steps != 0)
	{
		Scene->SetTimeIndex(Scene->GetTimeIndex() + Steps);
	}
	if (WasInputKeyJustPressed(EKeys::Up))
	{
		Scene->SetHeightIndex(Scene->GetHeightIndex() + 1);
	}
	if (WasInputKeyJustPressed(EKeys::Down))
	{
		Scene->SetHeightIndex(Scene->GetHeightIndex() - 1);
	}
	if (WasInputKeyJustPressed(EKeys::H))
	{
		bShowHorizonOverlay = !bShowHorizonOverlay;
	}
	if (WasInputKeyJustPressed(EKeys::Escape))
	{
		ConsoleCommand(TEXT("quit"));
	}
}

void ALsnHud::DrawHUD()
{
	Super::DrawHUD();
	if (Canvas == nullptr || GEngine == nullptr)
	{
		return;
	}
	UFont* Font = GEngine->GetMediumFont();
	const float Scale = FMath::Max(1.0f, Canvas->ClipY / 900.0f);
	const float LineHeight = 20.0f * Scale;
	const float X = 20.0f * Scale;
	float Y = 16.0f * Scale;
	auto Line = [&](const FString& Text, const FLinearColor& Color = FLinearColor::White, float Size = 1.0f)
	{
		DrawText(Text, Color, X, Y, Font, Scale * Size, false);
		Y += LineHeight * Size;
	};
	const FLinearColor Grey(0.7f, 0.7f, 0.7f);
	const FLinearColor Cyan(0.1f, 1.0f, 0.9f);

	const ALsnSiteScene* Scene = ALsnGameMode::GetScene(this);
	if (Scene == nullptr || !Scene->IsLoaded())
	{
		Line(TEXT("No package loaded."), FLinearColor::Red, 1.5f);
		Line(ALsnGameMode::GetLoadError(this), FLinearColor::Red);
		return;
	}
	const FLsnSitePackage& P = Scene->GetPackage();
	const int32 H = Scene->GetHeightIndex();
	const ALsnPlayerController* Controller = Cast<ALsnPlayerController>(GetOwningPlayerController());
	auto Status = [&P](const TCHAR* Method)
	{
		const FString* Found = P.Header.MethodStatus.Find(Method);
		return FString::Printf(TEXT("[%s: %s]"), Method, Found != nullptr ? **Found : TEXT("no method card"));
	};

	if (P.Header.bSynthetic)
	{
		Line(TEXT("SYNTHETIC DATA - NOT A RESULT"), FLinearColor(1.0f, 0.25f, 0.2f), 2.0f);
		Line(TEXT("Every value shown was generated by a formula for interface testing. No real place, no real date."), FLinearColor(1.0f, 0.5f, 0.4f));
	}
	Line(FString::Printf(TEXT("%s   lat %.4f  lon %.4f deg (planetocentric, east-positive, frame %s)"), *P.Name, P.LatDeg, P.LonDeg, *P.FrameName));
	Line(FString::Printf(TEXT("package %s   contract %s   status %s"), *P.Header.PackageId, *P.Header.ContractVersion, *P.Header.Status), Grey);
	Line(FString::Printf(TEXT("observer %.1f m above the surface (height %d of %d)"), P.ObserverHeightsM[H], H + 1, P.NumHeights()));

	if (P.bHasTimeline)
	{
		const FString Utc = P.UtcLabel(Scene->GetTimeIndex());
		Line(FString::Printf(TEXT("time %s   sample %d of %d, step %.0f s, TDB grid"), Utc.IsEmpty() ? TEXT("(no UTC label: leap second in range)") : *Utc,
			Scene->GetTimeIndex() + 1, P.Time.Count, P.Time.StepS));
		for (const TCHAR* Body : { TEXT("SUN"), TEXT("EARTH") })
		{
			FLsnBodySky Sky;
			if (Scene->GetBody(Body, Sky))
			{
				Line(FString::Printf(TEXT("%-5s az %7.2f  el %6.2f deg   margin above terrain %6.2f deg   visible fraction %.2f   %s %s"), Body,
					Sky.AzimuthDeg, Sky.ElevationDeg, Sky.MarginDeg, Sky.VisibleFraction, *Status(TEXT("timeline.direction")), *Status(TEXT("timeline.margin"))),
					Sky.VisibleFraction > 0.0 ? FLinearColor(0.6f, 1.0f, 0.6f) : FLinearColor(1.0f, 0.7f, 0.3f));
			}
		}
	}
	else
	{
		Line(TEXT("This package has no timeline: no Sun or Earth is shown. The light is a neutral overhead light, not the Sun."), FLinearColor::Yellow);
	}

	// Horizon of the package in the viewing direction: elevation interpolated, obstacle read at the nearest sample.
	if (Controller != nullptr)
	{
		FVector ViewLocation;
		FRotator ViewRotation;
		Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
		double ViewAz = 0.0, ViewEl = 0.0;
		LsnFrame::EnuToAzEl(LsnFrame::WorldToEnu(ViewRotation.Vector()), ViewAz, ViewEl);
		const int32 Nearest = P.NearestAzimuthIndex(ViewAz);
		Line(FString::Printf(TEXT("view az %7.2f  el %6.2f deg   terrain horizon there %6.2f deg, set by terrain %.1f km away   %s %s"), ViewAz, ViewEl,
			P.InterpolatedHorizonElevationDeg(H, ViewAz), P.HorizonDistanceM[H * P.AzimuthCount + Nearest] / 1000.0, *Status(TEXT("horizon.elevation")), *Status(TEXT("horizon.obstacle"))));
	}
	Line(TEXT("Terrain between the site and the ridge line is a stand-in fill, not elevation data."), Grey);
	Line(TEXT("mouse: look   Left/Right: time (Shift: fast)   Up/Down: observer height   H: horizon overlay   Esc: quit"), Grey);

	// Overlay: horizon.elevation_deg of the package, projected with the scene camera.
	if (Controller != nullptr && Controller->bShowHorizonOverlay)
	{
		const FVector Observer = P.ObserverWorldCm(H);
		const float* Row = P.HorizonElevationDeg.GetData() + H * P.AzimuthCount;
		FVector Previous = Project(Observer + LsnFrame::AzElToWorldDir(0.0, Row[0]) * 1.0e7, false);
		for (int32 I = 1; I <= P.AzimuthCount; ++I)
		{
			const FVector Current = Project(Observer + LsnFrame::AzElToWorldDir(I * P.AzimuthStepDeg, Row[I % P.AzimuthCount]) * 1.0e7, false);
			if (Previous.Z > 0.0 && Current.Z > 0.0 && FMath::Abs(Current.X - Previous.X) < Canvas->ClipX * 0.5f)
			{
				DrawLine(Previous.X, Previous.Y, Current.X, Current.Y, Cyan, 1.5f * Scale);
			}
			Previous = Current;
		}
		DrawText(TEXT("cyan line: horizon.elevation_deg of the package, drawn over the rendered terrain"), Cyan, X, Canvas->ClipY - 2.0f * LineHeight, Font, Scale, false);
	}
}
