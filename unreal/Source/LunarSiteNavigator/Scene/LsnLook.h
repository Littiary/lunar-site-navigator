#pragma once

#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"

/**
 * How the scene is drawn: display choices, kept in console variables so that they can be
 * tried in the running editor (lsn.Look.*) and judged by eye. None of them changes a
 * number, a position or the horizon. The defaults are the values that were chosen.
 */
namespace LsnLook
{
	extern TAutoConsoleVariable<float> ExposureBias;
	extern TAutoConsoleVariable<float> SunLux;
	extern TAutoConsoleVariable<float> FillLux;
	extern TAutoConsoleVariable<float> BloomIntensity;
	extern TAutoConsoleVariable<float> BloomThreshold;
	extern TAutoConsoleVariable<float> FilmSlope;
	extern TAutoConsoleVariable<float> FilmToe;
	extern TAutoConsoleVariable<float> CraterStrength;
	extern TAutoConsoleVariable<float> NoiseStrength;
}
