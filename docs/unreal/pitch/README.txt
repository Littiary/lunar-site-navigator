Pitch material of the Unreal planner view. Every file is a real render of the running scene
from the published packages (packages/ of the repository). Made by unreal/Scripts/pitch.ps1
at repository commit 1ea4245 on 2026-11-14 15:28 UTC.

Packages: Shackleton crater rim crest: site-a4f5f765a5d43bbf (contract 0.6); de Gerlache crater rim crest: site-6ded733f4be837e5 (contract 0.6).
Published fields: obstacles and their cost: True; lunar-day calendar: True; stated horizon error or landing ellipse: True.

pitch_two_sites_sunset_1080p60.mp4
    Shackleton crater rim crest (left) and de Gerlache crater rim crest (right), the same instant in both halves, observer 2 m, each view on its own Sun. Time runs from 2027-07-28T11:00:00Z to 2027-07-29T01:00:00Z in 26 s at 60 frames per second; the Sun sets behind a ridge at the left site and stays up at the right one; the blocking ridge lights up with the hours it costs.

still_1_planner_two_sites.png
    Shackleton crater rim crest and de Gerlache crater rim crest side by side at 2027-07-29T06:00:00Z, observer 2 m: countdowns, time strips, horizon panorama and the summary numbers of the whole window.

still_2_obstacle_highlight.png
    Shackleton crater rim crest at 2027-07-29T06:00:00Z, observer 2 m: the Sun behind the ridge the package names, its distance, azimuth and the hours it costs in the computed window.

still_3_calendar.png
    Shackleton crater rim crest and de Gerlache crater rim crest at 2027-07-29T06:00:00Z: lunar-day calendar of both sites on one time axis, landing windows of the example requirement and the slip of a landing at that time.

still_4_uncertainty_band.png
    Shackleton crater rim crest at 2027-07-28T17:00:00Z, observer 2 m: the band of the stated horizon error on the time strips and under the countdown, and the survey of the stated landing ellipse.

still_5_south_pole_wide.png
    The south-polar terrain around Shackleton crater rim crest at 2027-09-19T13:00:00Z, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg: LOLA elevation data sampled for drawing, the Sun and the Earth in the directions and sizes of the package.

still_7_mast_and_lander.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: the camera stands 5 m above and 22 m behind the observer (not the observer's view) and shows the mast that carries the observer at 10 m and the lander beside it. Both are scale objects of the team's own design, not part of the package.

still_6_astronaut_height.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z from the observer height of 2 m, looking towards azimuth 128 deg with a 62 deg field of view: the Sun low on the left, the Earth as a crescent on the right.

The ground is LOLA elevation data sampled on 320 rings per azimuth. Roughness and small craters finer than that data are
illustrative shading computed in the surface shader: positions, shadows and the horizon are those of the data. Stars are the
Yale Bright Star Catalogue, turned for the date. Lander, mast and boulders are scale objects of the team's own design, not part
of any package. Surface shading, exposure, the glare of the Sun and the fill light while the Sun is down are display choices
(see unreal/README.md). Not in any of these: image textures, an atmosphere or a map of the Earth.
