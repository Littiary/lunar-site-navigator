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
 * Keys: mouse or arrow keys look; Q / E step the timeline one sample back or
 * forward (hold Shift for 24 samples); Space plays and pauses the timeline,
 * [ and ] halve and double the playing speed; Tab shows the mouse cursor, with
 * which the time strips can be dragged; H toggles the package horizon line;
 * L toggles the weak fill light (a display aid); Z / X zoom; PageUp / PageDown change the observer height;
 * Esc quits.
 *
 * Command line: -LsnPlayFrom=<sample> -LsnPlayTo=<sample> -LsnPlaySeconds=<s>
 * plays that stretch of the timeline once, for recordings.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnObserverPawn : public APawn
{
	GENERATED_BODY()

public:
	ALsnObserverPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	double GetAzimuthDeg() const { return AzimuthDeg; }
	double GetElevationDeg() const { return ElevationDeg; }
	double GetFovDeg() const { return FovDeg; }
	bool IsPlaying() const { return bPlaying; }
	double GetPlayRateSamplesPerSecond() const { return PlayRate; }
	/** True once a stretch given on the command line has been played to its end. */
	bool HasFinishedCommandLinePlay() const { return bCommandLinePlayDone; }

private:
	ALsnSiteScene* FindScene() const;
	void ApplyView();

	UPROPERTY()
	TObjectPtr<UCameraComponent> Camera;

	double AzimuthDeg = 0.0;
	double ElevationDeg = 0.0;
	double FovDeg = 60.0;
	bool bInitialised = false;

	/** Timeline playing: samples of the package per second of real time. */
	bool bPlaying = false;
	double PlayRate = 6.0;
	double PlayTo = -1.0;
	bool bCommandLinePlayDone = false;
};
