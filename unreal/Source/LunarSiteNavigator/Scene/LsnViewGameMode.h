#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "Package/LsnPackage.h"
#include "LsnViewGameMode.generated.h"

class ALsnSiteScene;

/** What the planner shows beside the view. */
enum class ELsnPlannerPage : uint8
{
	Summary,      // summary numbers and the site list
	Calendar,     // lunar-day calendar, landing windows and slip of a requirement
	Uncertainty,  // stated horizon error and landing ellipse
	Trade,        // mast-height trade and site pairs
	Sites,        // site picker and custom coordinates
};

/** What the site picker shows for a site besides its name. */
struct FLsnSiteInfo
{
	/** Group of the picker: the index field "programme", or one common group. */
	FString Group;
	FLsnTerrainSource TerrainSource;
};

/** The entry for custom coordinates: what was typed, and how the science core's run stands. */
struct FLsnCustomEntry
{
	FString Latitude, Longitude;
	/** 0: latitude field, 1: longitude field. */
	int32 Focus = 0;
	bool bRunning = false;
	bool bFailed = false;
	FString Message;
	double StartedS = 0.0;
};

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
 *   -LsnUtc=<2027-07-28T18:00:00Z>         (the time by UTC instead of by sample index)
 *   -LsnYaw=<azimuth, deg>  -LsnPitch=<elevation, deg>  -LsnFov=<horizontal field of view, deg>
 *   -LsnPage=calendar|uncertainty|trade    (the planner page shown; default: summary)
 *   -LsnRequirement=<index>                (which requirement of the package the landing windows are shown for)
 *   -LsnCameraUp=<m>  -LsnCameraBack=<m>   (overview: the camera stands that far above and behind the
 *                                           observer; for stills, not the observer's view)
 *   -LsnNoHud                              (for stills: no panels, only a caption line and, for a
 *                                           synthetic package, the synthetic marker)
 *   -LsnFollowSun                          (keep the view on the Sun's azimuth; default when comparing)
 *   -LsnHorizonLine                        (draw the package horizon as a line)
 *   -LsnNoFillLight  -LsnNoObstacle        (switch the fill light or the obstacle view off)
 *   -LsnLowQuality                         (lower drawing quality, for slower graphics cards; key G)
 *   -LsnDo=<action>,<action>               (carry out named actions of the observer at the start)
 *   -LsnBench=<file.txt> -LsnBenchSeconds=<s>  (measure the frame time for that long, write it and quit)
 *   -LsnShot=<file.png>                    (save one screenshot and quit)
 *   -LsnMovieDir=<folder>                  (with -LsnPlayFrom/-LsnPlayTo: save every frame of that
 *                                           stretch as frame_00000.png ... and quit; run with
 *                                           -benchmark -fps=30 for a fixed frame rate)
 *
 * Without -LsnPackage and -LsnPackageRoot the published packages are shown: packages/ at
 * the root of the repository (in a stand-alone build: the copy of that folder staged with
 * it). Failing that, the contract sample, then the pinned test copy.
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

	// --- site picker and custom coordinates -------------------------------

	const TArray<FLsnSiteInfo>& GetSiteInfos() const { return SiteInfos; }
	/** Directory of a site of the list. */
	FString SiteDirectory(int32 SiteIndex) const;
	const FLsnCustomEntry& GetCustomEntry() const { return Custom; }
	void SetCustomFocus(int32 Field) { Custom.Focus = FMath::Clamp(Field, 0, 1); }
	/** A character typed into the focused field (digits, point, minus); others are ignored. */
	void TypeCustom(TCHAR Character);
	void BackspaceCustom();
	/**
	 * Hands the typed coordinates to the science core (python -m lsncore site) if a Python
	 * environment with it is on this machine, and loads the package it writes. The engine
	 * computes nothing; without the environment it says so.
	 */
	void StartCustom();

	// --- planner pages -----------------------------------------------------

	ELsnPlannerPage GetPage() const { return Page; }
	/** Shows a page; asking for the page that is shown goes back to the summary. */
	void TogglePage(ELsnPlannerPage NewPage) { Page = (Page == NewPage) ? ELsnPlannerPage::Summary : NewPage; }
	/** Which of the package's requirements the landing windows are shown for. */
	int32 GetRequirementIndex() const { return RequirementIndex; }
	void NextRequirement() { ++RequirementIndex; }
	/** The site-pairs package of the package root, if it has one (contract 0.5). */
	const FLsnSitePairs* GetSitePairs() const { return bHasPairs ? &Pairs : nullptr; }
	ALsnSiteScene* GetSceneOfView(int32 ViewIndex) const { return Scenes.IsValidIndex(ViewIndex) ? Scenes[ViewIndex] : nullptr; }

	// --- drawing quality ----------------------------------------------------

	/**
	 * Lower drawing quality for slower graphics cards: the scene is drawn at two thirds of the
	 * resolution and the shadows with coarser pages and fewer rays. What is shown does not
	 * change; only how finely it is drawn.
	 */
	bool IsLowQuality() const { return bLowQuality; }
	void SetLowQuality(bool bLow);

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
	ELsnPlannerPage Page = ELsnPlannerPage::Summary;
	int32 RequirementIndex = 0;
	FLsnSitePairs Pairs;
	bool bHasPairs = false;

	bool bLowQuality = false;
	FString BenchPath;
	double BenchSeconds = 20.0;
	double BenchWarmUpS = 6.0;
	TArray<float> BenchFrameMs;

	TArray<FLsnSiteInfo> SiteInfos;
	FLsnCustomEntry Custom;
	FProcHandle CustomProcess;
	void* CustomReadPipe = nullptr;
	void* CustomWritePipe = nullptr;
	FString CustomOutput, CustomName, CustomRoot;
	void TickCustom();
	void AddSiteInfo(int32 SiteIndex);

	FString LoadError;
	FString ShotPath;
	int32 FramesUntilShot = -1;
	int32 FramesUntilQuit = -1;
	FString MovieDir;
	int32 MovieWarmUpFrames = 0;
	int32 MovieFrame = 0;
};
