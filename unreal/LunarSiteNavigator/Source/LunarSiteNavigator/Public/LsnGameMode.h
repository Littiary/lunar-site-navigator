#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "LsnGameMode.generated.h"

class ALsnSiteScene;
class UCameraComponent;

/**
 * Starts the view scene without any map asset: spawns the scene actor in the empty engine
 * map and loads a site package.
 *
 * Command line: -LsnPackageRoot=<dir> -LsnSite=<site_id> -LsnTime=<sample> -LsnAz=<deg>
 * -LsnEl=<deg> -LsnFov=<deg> -LsnNoOverlay -LsnScreenshot=<file> (capture one frame and exit).
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALsnGameMode();
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
	virtual void Tick(float DeltaSeconds) override;

	static ALsnSiteScene* GetScene(const UObject* WorldContext);
	static FString GetLoadError(const UObject* WorldContext);

private:
	UPROPERTY()
	TObjectPtr<ALsnSiteScene> Scene;

	FString LoadError;
	FString ScreenshotPath;
	float Elapsed = 0.0f;
	bool bScreenshotRequested = false;
};

/** Camera at the observer height above the site. It turns but does not move. */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnObserverPawn : public APawn
{
	GENERATED_BODY()

public:
	ALsnObserverPawn();

	UPROPERTY()
	TObjectPtr<UCameraComponent> Camera;
};

/** Mouse look, time and height stepping. */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	virtual void BeginPlay() override;
	virtual void PlayerTick(float DeltaSeconds) override;

	bool bShowHorizonOverlay = true;

private:
	double TimeAccumulator = 0.0;
	bool bViewInitialised = false;
};

/** Text read-out and the package horizon drawn over the rendered view. */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnHud : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};
