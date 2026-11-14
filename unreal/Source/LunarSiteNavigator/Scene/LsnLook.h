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
	/** The camera near the lander: metres behind it (away from the Sun), to its right and above the ground; turn from the Sun's azimuth, pitch, field of view. */
	extern TAutoConsoleVariable<float> HeroBackM, HeroRightM, HeroUpM, HeroYawDeg, HeroPitchDeg, HeroFovDeg;
	/** The wide view: metres behind the site and above it; pitch and field of view. */
	extern TAutoConsoleVariable<float> WideBackM, WideUpM, WidePitchDeg, WideFovDeg;
	/** The wide view: turn of the whole view from the Sun's azimuth; 0 looks at the Sun, 90 has the Sun on the left. */
	extern TAutoConsoleVariable<float> WideYawDeg;
	/** Light on the sides of the scale objects that face away from the Sun, as a share of the lit side: stands for the light the ground throws back. */
	extern TAutoConsoleVariable<float> ObjectAmbient;
}
