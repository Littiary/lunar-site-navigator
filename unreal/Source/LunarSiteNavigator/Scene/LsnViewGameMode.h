#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LsnViewGameMode.generated.h"

class ALsnSiteScene;

/**
 * Stage 1 view: spawns the scene for one site package and puts the camera at
 * the eye of the observer. The whole scene is built in code; the project has
 * no map asset of its own.
 *
 * Command line:
 *   -LsnPackage=<site package directory>   or
 *   -LsnPackageRoot=<package root>         (the first site in index.json is shown)
 *   -LsnTime=<timeline sample index>   -LsnHeight=<observer height index>
 *   -LsnYaw=<azimuth, deg>  -LsnPitch=<elevation, deg>  -LsnFov=<horizontal field of view, deg>
 *   -LsnHorizonLine                        (draw the package horizon as a line)
 *   -LsnSite=<site_id>                     (with a package root: that site instead of the first)
 *   -LsnShot=<file.png>                    (save one screenshot and quit)
 *   -LsnMovieDir=<folder>                  (with -LsnPlayFrom/-LsnPlayTo: save every frame of that
 *                                           stretch as frame_00000.png ... and quit; run with
 *                                           -benchmark -fps=30 for a fixed frame rate)
 *
 * Without -LsnPackage and -LsnPackageRoot the packages are looked for in
 * <project>/Content/LsnPackages (copied there by Scripts/import_packages.ps1 and staged
 * with a packaged build), then in the contract sample, then in the pinned test copy.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnViewGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALsnViewGameMode();

	virtual void StartPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	ALsnSiteScene* GetScene() const { return Scene; }
	const FString& GetLoadError() const { return LoadError; }

	/** Finds the package to show: command line first, then the sample of the contract. */
	static FString ResolvePackageDirectory(FString& OutError);

private:
	UPROPERTY()
	TObjectPtr<ALsnSiteScene> Scene;

	FString LoadError;
	FString ShotPath;
	int32 FramesUntilShot = -1;
	int32 FramesUntilQuit = -1;
	FString MovieDir;
	int32 MovieWarmUpFrames = 0;
	int32 MovieFrame = 0;
};
