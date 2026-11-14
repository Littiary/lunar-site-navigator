#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "LsnObserverPawn.generated.h"

class ALsnSiteScene;
class UCameraComponent;

/**
 * The observer: a camera at the eye height of the selected observer height of
 * the package, looking around from the site. Yaw is azimuth, pitch is elevation.
 *
 * Every action has a name (DoAction). The buttons on screen and the keys both go
 * through it, so nothing can be done with a key that cannot be done with the mouse.
 *
 * Mouse: the cursor is visible. Click a button; drag on a time strip to choose the
 * time; hold the right button and move to look around; wheel to zoom.
 *
 * Keys (left or only view; the right view of a comparison follows it):
 *   arrow keys            look
 *   Q / E                 one sample back / forward (Shift: 24 samples)
 *   , / .                 one day back / forward
 *   B / N                 previous / next rise or set of the Sun in the package (Shift: of the Earth)
 *   Home / End            first / last sample
 *   Space, [ and ]        play and pause the timeline, halve and double the playing speed
 *   1 .. 9                show that site of the list (Shift: in the right view, side by side)
 *   C                     comparison of two sites on and off
 *   K, U, M               calendar and landing windows; uncertainty; mast-height trade and site pairs
 *   R                     next requirement of the package
 *   F                     keep the view on the Sun's azimuth
 *   PageUp / PageDown     observer height
 *   Z / X                 zoom
 *   O, H, L               obstacle view, package horizon line, weak fill light (a display aid)
 *   G                     lower drawing quality for slower graphics cards
 *   I                     details: package, frame, contract version, test status
 *   P                     scale objects (lander, boulders) on and off
 *   F1                    list of keys on screen
 *   Tab                   hide the cursor and look with the mouse alone
 *   Esc                   quit
 *
 * Command line: -LsnPlayFrom=<sample> -LsnPlayTo=<sample> (or -LsnPlayFromUtc=<utc>
 * -LsnPlayToUtc=<utc>) -LsnPlaySeconds=<s> plays that stretch of the timeline once,
 * for recordings.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnObserverPawn : public APawn
{
	GENERATED_BODY()

public:
	ALsnObserverPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Carries out a named action; false if the name is not one of KnownActions(). */
	bool DoAction(FName Action);
	/** The names DoAction understands. */
	static const TArray<FName>& KnownActions();

	double GetAzimuthDeg() const { return AzimuthDeg; }
	double GetElevationDeg() const { return ElevationDeg; }
	double GetFovDeg() const { return FovDeg; }
	bool IsPlaying() const { return bPlaying; }
	double GetPlayRateSamplesPerSecond() const { return PlayRate; }
	bool IsFollowingSun() const { return bFollowSun; }
	double GetFollowOffsetDeg() const { return FollowOffsetDeg; }
	bool IsHelpShown() const { return bShowHelp; }
	/** The details panel: package id, frame, contract version and test status of what is shown. */
	bool AreDetailsShown() const { return bShowDetails; }
	/** True if the camera stands above or behind the observer (overview stills): not the observer's view. */
	bool IsOverview() const { return CameraUpM > 0.0 || CameraBackM > 0.0; }
	double GetCameraUpM() const { return CameraUpM; }
	/** True once a stretch given on the command line has been played to its end. */
	bool HasFinishedCommandLinePlay() const { return bCommandLinePlayDone; }

private:
	ALsnSiteScene* FindScene() const;
	void ApplyView();
	void HandleInput(APlayerController* PC, ALsnSiteScene* Scene, float DeltaSeconds);
	void FollowLeftView(const ALsnObserverPawn& Left);
	void StepSamples(ALsnSiteScene* Scene, int32 Samples);
	void JumpToEvent(ALsnSiteScene* Scene, const TCHAR* Body, int32 Direction);

	UPROPERTY()
	TObjectPtr<UCameraComponent> Camera;

	double AzimuthDeg = 0.0;
	double ElevationDeg = 0.0;
	double FovDeg = 60.0;
	bool bInitialised = false;
	bool bShowHelp = false;
	bool bShowDetails = false;

	/** Overview camera: metres above and behind the observer along the viewing azimuth. */
	double CameraUpM = 0.0;
	double CameraBackM = 0.0;

	/** Keep the view on the Sun's azimuth plus an offset the user turns. */
	bool bFollowSun = false;
	double FollowOffsetDeg = 0.0;

	/** Timeline playing: samples of the package per second of real time. */
	bool bPlaying = false;
	double PlayRate = 6.0;
	double PlayTo = -1.0;
	bool bCommandLinePlayDone = false;
};
