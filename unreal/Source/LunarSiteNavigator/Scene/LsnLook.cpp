#include "Scene/LsnLook.h"

namespace LsnLook
{
	TAutoConsoleVariable<float> ExposureBias(TEXT("lsn.Look.ExposureBias"), 0.2f, TEXT("Fixed exposure of the view, in stops. Set for sunlit ground, not for the black sky."));
	TAutoConsoleVariable<float> SunLux(TEXT("lsn.Look.SunLux"), 10.0f, TEXT("Display intensity of the Sun's light."));
	TAutoConsoleVariable<float> FillLux(TEXT("lsn.Look.FillLux"), 0.12f, TEXT("Display intensity of the fill light that is on while the Sun is down."));
	TAutoConsoleVariable<float> BloomIntensity(TEXT("lsn.Look.BloomIntensity"), 0.45f, TEXT("Glare of what is far brighter than sunlit ground (the Sun's disc)."));
	TAutoConsoleVariable<float> BloomThreshold(TEXT("lsn.Look.BloomThreshold"), 6.0f, TEXT("Brightness from which the glare starts."));
	TAutoConsoleVariable<float> FilmSlope(TEXT("lsn.Look.FilmSlope"), 0.88f, TEXT("Contrast of the tone curve (engine default 0.88)."));
	TAutoConsoleVariable<float> FilmToe(TEXT("lsn.Look.FilmToe"), 0.55f, TEXT("Depth of the dark end of the tone curve (engine default 0.55)."));
	TAutoConsoleVariable<float> CraterStrength(TEXT("lsn.Look.CraterStrength"), 1.0f, TEXT("Strength of the illustrative small craters in the surface shading."));
	TAutoConsoleVariable<float> NoiseStrength(TEXT("lsn.Look.NoiseStrength"), 1.0f, TEXT("Strength of the illustrative roughness in the surface shading."));
}
