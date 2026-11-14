Pitch material of the Unreal planner view. Every file is a real render of the running scene
from the published packages (packages/ of the repository). Made by unreal/Scripts/pitch.ps1
at repository commit 2264c78 on 2026-11-14 13:11 UTC.

Packages: Shackleton crater rim crest: site-3d084d7f181d1b64 (contract 0.1); de Gerlache crater rim crest: site-08105a0f3060aee8 (contract 0.1).
Published fields: obstacles and their cost: False; lunar-day calendar: False; stated horizon error or landing ellipse: False.

pitch_two_sites_sunset_1080p60.mp4
    Shackleton crater rim crest (left) and de Gerlache crater rim crest (right), the same instant in both halves, observer 2 m, each view on its own Sun. Time runs from 2027-07-28T11:00:00Z to 2027-07-29T01:00:00Z in 26 s at 60 frames per second; the Sun sets behind a ridge at the left site and stays up at the right one; the ridge is NOT highlighted and no cost is shown, because the published packages (contract 0.1) carry no obstacles.

still_1_planner_two_sites.png
    Shackleton crater rim crest and de Gerlache crater rim crest side by side at 2027-07-29T06:00:00Z, observer 2 m: countdowns, time strips, horizon panorama and the summary numbers of the whole window.

still_2_obstacle_highlight.png  -  NOT PRODUCED
    The obstacle that hides the Sun and the hours it costs (contract 0.2, SPEC 5.5) is not in the published packages (contract 0.1). Run this script again once packages/ carries it.

still_3_calendar.png  -  NOT PRODUCED
    The lunar-day calendar and the landing windows (contract 0.3, SPEC 5.6) is not in the published packages (contract 0.1). Run this script again once packages/ carries it.

still_4_uncertainty_band.png  -  NOT PRODUCED
    The band for a stated horizon error and the landing-ellipse survey (contract 0.4, SPEC 5.7) is not in the published packages (contract 0.1). Run this script again once packages/ carries it.

still_5_south_pole_wide.png
    The south-polar terrain around Shackleton crater rim crest at 2027-09-19T13:00:00Z, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg: LOLA elevation data sampled for drawing, the Sun and the Earth in the directions and sizes of the package.

still_6_astronaut_height.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z from the observer height of 2 m, looking towards azimuth 128 deg with a 62 deg field of view: the Sun low on the left, the Earth as a crescent on the right.

Not in any of these: textures, an atmosphere, stars or a map of the Earth. The ground is LOLA elevation data sampled on 320
rings per azimuth; surface shading, exposure and the weak fill light are display choices (see unreal/README.md).
