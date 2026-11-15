#include "Scene/LsnLook.h"

namespace LsnLook
{
	TAutoConsoleVariable<float> ExposureBias(TEXT("lsn.Look.ExposureBias"), 0.0f, TEXT("Fixed exposure of the view, in stops. Set for sunlit ground, not for the black sky."));
	TAutoConsoleVariable<float> SunLux(TEXT("lsn.Look.SunLux"), 10.0f, TEXT("Display intensity of the Sun's light."));
	TAutoConsoleVariable<float> FillLux(TEXT("lsn.Look.FillLux"), 0.12f, TEXT("Display intensity of the fill light that is on while the Sun is down."));
	TAutoConsoleVariable<float> BloomIntensity(TEXT("lsn.Look.BloomIntensity"), 0.25f, TEXT("Glare of what is far brighter than sunlit ground (the Sun's disc)."));
	TAutoConsoleVariable<float> BloomThreshold(TEXT("lsn.Look.BloomThreshold"), 6.0f, TEXT("Brightness from which the glare starts."));
	TAutoConsoleVariable<float> FilmSlope(TEXT("lsn.Look.FilmSlope"), 1.0f, TEXT("Contrast of the tone curve (engine default 0.88)."));
	TAutoConsoleVariable<float> FilmToe(TEXT("lsn.Look.FilmToe"), 0.4f, TEXT("Depth of the dark end of the tone curve (engine default 0.55)."));
	TAutoConsoleVariable<float> CraterStrength(TEXT("lsn.Look.CraterStrength"), 1.0f, TEXT("Strength of the illustrative small craters in the surface shading."));
	TAutoConsoleVariable<float> HeroBackM(TEXT("lsn.Cam.HeroBackM"), 16.0f, TEXT("Camera near the lander: metres behind it, away from the Sun."));
	TAutoConsoleVariable<float> HeroRightM(TEXT("lsn.Cam.HeroRightM"), 4.5f, TEXT("Camera near the lander: metres to its right."));
	TAutoConsoleVariable<float> HeroUpM(TEXT("lsn.Cam.HeroUpM"), 5.5f, TEXT("Camera near the lander: metres above the ground."));
	TAutoConsoleVariable<float> HeroYawDeg(TEXT("lsn.Cam.HeroYawDeg"), -7.0f, TEXT("Camera near the lander: turn from the Sun's azimuth."));
	TAutoConsoleVariable<float> HeroPitchDeg(TEXT("lsn.Cam.HeroPitchDeg"), -12.0f, TEXT("Camera near the lander: pitch."));
	TAutoConsoleVariable<float> HeroFovDeg(TEXT("lsn.Cam.HeroFovDeg"), 52.0f, TEXT("Camera near the lander: field of view."));
	TAutoConsoleVariable<float> WideBackM(TEXT("lsn.Cam.WideBackM"), 120.0f, TEXT("Wide view: metres behind the site, away from the Sun."));
	TAutoConsoleVariable<float> WideUpM(TEXT("lsn.Cam.WideUpM"), 30.0f, TEXT("Wide view: metres above the site."));
	TAutoConsoleVariable<float> WidePitchDeg(TEXT("lsn.Cam.WidePitchDeg"), -11.0f, TEXT("Wide view: pitch."));
	TAutoConsoleVariable<float> LitYawDeg(TEXT("lsn.Cam.LitYawDeg"), 130.0f, TEXT("Camera on the lander's sunlit side: turn of the view from the Sun's azimuth; at 130 the Sun stands 50 degrees off the axis behind the camera."));
	TAutoConsoleVariable<float> LitBackM(TEXT("lsn.Cam.LitBackM"), 17.0f, TEXT("Camera on the lander's sunlit side: metres from the lander."));
	TAutoConsoleVariable<float> LitUpM(TEXT("lsn.Cam.LitUpM"), 4.0f, TEXT("Camera on the lander's sunlit side: metres above the ground."));
	TAutoConsoleVariable<float> LitPitchDeg(TEXT("lsn.Cam.LitPitchDeg"), -7.0f, TEXT("Camera on the lander's sunlit side: pitch."));
	TAutoConsoleVariable<float> LitFovDeg(TEXT("lsn.Cam.LitFovDeg"), 46.0f, TEXT("Camera on the lander's sunlit side: field of view."));
	TAutoConsoleVariable<float> WideYawDeg(TEXT("lsn.Cam.WideYawDeg"), -60.0f, TEXT("Wide view: turn of the whole view from the Sun's azimuth."));
	TAutoConsoleVariable<float> HighSunExposure(TEXT("lsn.Look.HighSunExposure"), 0.35f, TEXT("Share of the Sun's display intensity left when the Sun stands 45 degrees or more above the ground (a camera stops down for bright ground)."));
	TAutoConsoleVariable<float> OppositionStrength(TEXT("lsn.Look.OppositionStrength"), 0.4f, TEXT("Opposition surge of the regolith: amplitude B0 (0 switches it off)."));
	TAutoConsoleVariable<float> OppositionWidth(TEXT("lsn.Look.OppositionWidth"), 0.06f, TEXT("Opposition surge of the regolith: angular width h."));
	TAutoConsoleVariable<float> EarthshineShare(TEXT("lsn.Look.EarthshineShare"), 0.025f, TEXT("Earthshine as shown, as a share of the Sun's display intensity, for a full Earth."));
	TAutoConsoleVariable<float> GrainStrength(TEXT("lsn.Look.GrainStrength"), 1.0f, TEXT("Strength of the fine grain of the regolith."));
	TAutoConsoleVariable<float> BounceScale(TEXT("lsn.Look.BounceScale"), 1.0f, TEXT("Light the sunlit ground throws back onto the scale objects, as a multiple of what the formula gives."));
	TAutoConsoleVariable<float> WideFovDeg(TEXT("lsn.Cam.WideFovDeg"), 58.0f, TEXT("Wide view: field of view."));
	TAutoConsoleVariable<float> NoiseStrength(TEXT("lsn.Look.NoiseStrength"), 0.6f, TEXT("Strength of the illustrative roughness in the surface shading."));
}
