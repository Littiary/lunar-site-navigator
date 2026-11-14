#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "LsnHud.generated.h"

/**
 * Text overlay of stage 1. Every number it shows is a field of the package,
 * printed with the validation status of its method card. A synthetic package
 * is marked as such, as the contract requires.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnHud : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};
