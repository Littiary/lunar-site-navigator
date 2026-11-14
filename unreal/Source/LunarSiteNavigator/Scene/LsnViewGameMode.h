#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Package/LsnPackage.h"
#include "LsnViewGameMode.generated.h"

class ALsnSiteScene;

/**
 * The planner view: one site, or two sites side by side at the same instant. The scenes
 * are built in code; the project has no map asset of its own.
 *
 * Command line:
 *   -LsnPackage=<site package directory>   or
 *   -LsnPackageRoot=<package root>         (the sites of its index.json can be selected)
 *   -LsnSite=<site_id>                     (the site shown first; default: the first of the index)
 *   -LsnCompare=<site_id>,<site_id>        (start with these two sites side by side)
 *   -LsnTime=<timeline sample index>   -LsnHeight=<observer height index>
 *   -LsnYaw=<azimuth, deg>  -LsnPitch=<elevation, deg>  -LsnFov=<horizontal field of view, deg>
 *   -LsnFollowSun                          (keep the view on the Sun's azimuth; default when comparing)
 *   -LsnHorizonLine                        (draw the package horizon as a line)
 *   -LsnNoFillLight  -LsnNoObstacle        (switch the fill light or the obstacle view off)
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

	/** The scene of the left (or only) view. */
	ALsnSiteScene* GetScene() const { return Scenes.IsValidIndex(0) ? Scenes[0] : nullptr; }

	/** 0 for the left (or only) view, 1 for the right view of a comparison. */
	int32 GetViewIndexOf(const AController* Controller) const;
	ALsnSiteScene* GetSceneOf(const AController* Controller) const;

	const FString& GetLoadError() const { return LoadError; }

	/** True while a recording waits for shaders and shadows before its first frame; the timeline must not play yet. */
	bool IsWarmingUpForMovie() const { return !MovieDir.IsEmpty() && MovieWarmUpFrames > 0; }

	// --- sites and comparison ---------------------------------------------

	const TArray<FLsnIndexEntry>& GetSites() const { return Sites; }
	/** Index into GetSites() of the site a view shows; -1 if it shows a package given by directory. */
	int32 GetSelectedSite(int32 ViewIndex) const { return ViewIndex == 1 ? SelectedSite[1] : SelectedSite[0]; }

	/** Shows a site of the list in a view. Selecting a site for the right view starts the comparison. */
	bool SelectSite(int32 ViewIndex, int32 SiteIndex);

	bool IsComparing() const { return bComparing; }
	void SetComparing(bool bCompare);

	/**
	 * Gives the right view the instant, observer height and view options of the left one.
	 * Called by the left observer right after it has moved the time, so that both halves
	 * show the same instant in the same frame.
	 */
	void SyncComparison();

	/** False while the right view shows a clamped time because the instant of the left view is outside its package. */
	bool IsRightViewInRange() const { return bRightViewInRange; }

	/** Finds the package root: command line first, then the imported packages, the contract sample, the pinned copy. */
	static FString ResolvePackageRoot(FString& OutError);

private:
	void ApplyViewOptions(ALsnSiteScene* Scene) const;

	UPROPERTY()
	TArray<TObjectPtr<ALsnSiteScene>> Scenes;

	UPROPERTY()
	TObjectPtr<APlayerController> SecondController;

	FString PackageRoot;
	TArray<FLsnIndexEntry> Sites;
	int32 SelectedSite[2] = { -1, -1 };
	bool bComparing = false;
	bool bRightViewInRange = true;

	FString LoadError;
	FString ShotPath;
	int32 FramesUntilShot = -1;
	int32 FramesUntilQuit = -1;
	FString MovieDir;
	int32 MovieWarmUpFrames = 0;
	int32 MovieFrame = 0;
};
