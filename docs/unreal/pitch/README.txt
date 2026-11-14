Pitch material of the Unreal planner view. Every file is a real render of the running scene
from the published packages (packages/ of the repository). Made by unreal/Scripts/pitch.ps1
at repository commit 18e3fa9 on 2026-11-14 21:08 UTC.

Packages: Shackleton crater rim crest: site-e3810b35dcfa4777 (contract 0.11); de Gerlache crater rim crest: site-66887386ea4fc6ea (contract 0.11).
Published fields: obstacles and their cost: True; lunar-day calendar: True; stated horizon error or landing ellipse: True.

pitch_two_sites_sunset_1080p60.mp4
    Shackleton crater rim crest (left) and de Gerlache crater rim crest (right), the same instant in both halves, observer 2 m, each view on its own Sun. Time runs from 2027-07-28T16:30:00Z to 2027-07-28T20:00:00Z in 26 s at 60 frames per second; the Sun sets behind a ridge at the left site and stays up at the right one; the blocking ridge lights up with the hours it costs. Shown without the controls of the tool; the caption across the picture is part of the clip, and its second text appears when the package gives the Sun of the left site as hidden.

still_1_planner_two_sites.png
    Shackleton crater rim crest and de Gerlache crater rim crest side by side at 2027-07-29T06:00:00Z, observer 2 m: state chips and time strip of each site, without the controls, with a caption; readable when shown small.

still_1_planner_two_sites_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

still_1b_planner_with_controls.png
    The same view with the control bar and the drawer open on its tab of further controls. Meant for a close look, not for a small picture on a slide.

still_1b_planner_with_controls_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

still_2_obstacle_highlight.png
    Shackleton crater rim crest at 2027-07-29T06:00:00Z, observer 2 m: the Sun behind the ridge the package names, its distance, azimuth and the hours it costs in the computed window.

still_2_obstacle_highlight_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

still_3_calendar.png
    Shackleton crater rim crest and de Gerlache crater rim crest at 2027-07-29T06:00:00Z: lunar-day calendar of both sites on one time axis, landing windows of the example requirement and the slip of a landing at that time.

still_3_calendar_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

still_4_uncertainty_band.png
    Shackleton crater rim crest at 2027-07-28T17:00:00Z, observer 2 m: the band of the stated horizon error on the time strips and under the countdown, and the survey of the stated landing ellipse.

still_4_uncertainty_band_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

still_5_south_pole_wide.png
    The south-polar terrain around Shackleton crater rim crest at 2027-09-19T13:00:00Z, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg: LOLA elevation data sampled for drawing, the Sun and the Earth in the directions and sizes of the package. A weak fill light is on for this still only, as a viewing aid, so that the terrain in shadow can be told apart; without it shadows are black (the still says so).

still_5_south_pole_wide_interface.png
    The same picture with the interface of the tool.

still_7_mast_and_lander.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: the camera stands 5 m above and 22 m behind the observer (not the observer's view) and shows the mast that carries the observer at 10 m and the lander beside it. Both are scale objects of the team's own design, not part of the package.

still_7_mast_and_lander_interface.png
    The same picture with the interface of the tool.

still_6_astronaut_height.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z from the observer height of 2 m, looking towards azimuth 128 deg with a 62 deg field of view: the Sun low on the left, the Earth as a crescent on the right.

still_6_astronaut_height_interface.png
    The same picture with the interface of the tool.

still_8_camera_near_lander.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: a camera 16 m behind the lander and 5.5 m up, looking towards the Sun (not the observer's view). The lander is a scale object of the team's own design; the ground, the light and the shadows are those of the package and the elevation data.

still_8_camera_near_lander_interface.png
    The same picture with the interface of the tool.

still_9_wide_view.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: the wide view from 120 m away and 30 m up with the Sun 60 deg to the right, outside the picture (not the observer's view): lander, mast and boulders with their shadows, for scale.

still_9_wide_view_interface.png
    The same picture with the interface of the tool.

clip_arrival.mp4
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: a camera move of 8 s from 9 km above and 26 km behind the site down to the camera near the lander, for the opening of the video. A camera move only: no descent, trajectory or engine is simulated, and ten minutes of the package pass during the move.

The ground is LOLA elevation data sampled on 320 rings per azimuth. Roughness and small craters finer than that data are
illustrative shading computed in the surface shader: positions, shadows and the horizon are those of the data. Stars are the
Yale Bright Star Catalogue, turned for the date. Lander, mast and boulders are scale objects of the team's own design, not part
of any package. Surface shading, exposure, the glare of the Sun and the fill light while the Sun is down are display choices
(see unreal/README.md). Not in any of these: image textures, an atmosphere or a map of the Earth.
