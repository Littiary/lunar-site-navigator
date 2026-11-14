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
 * forward (hold Shift for 24 samples); H toggles the package horizon line;
 * Z / X zoom; PageUp / PageDown change the observer height.
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

private:
	ALsnSiteScene* FindScene() const;
	void ApplyView();

	UPROPERTY()
	TObjectPtr<UCameraComponent> Camera;

	double AzimuthDeg = 0.0;
	double ElevationDeg = 0.0;
	double FovDeg = 60.0;
	bool bInitialised = false;
};
