Pitch material of the Unreal planner view. Every file is a real render of the running scene
from the published packages (packages/ of the repository). Made by unreal/Scripts/pitch.ps1
at repository commit 3d83adc on 2026-11-14 22:34 UTC.

Packages: Shackleton crater rim crest: site-38037e9b701a7d2d (contract 0.11); de Gerlache crater rim crest: site-61a82bfea156b494 (contract 0.11).
Published fields: obstacles and their cost: True; lunar-day calendar: True; stated horizon error or landing ellipse: True.

a_opening_south_pole_wide.png
    Opening. The south-polar terrain around Shackleton crater rim crest at 2027-09-19T13:00:00Z, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg, the Sun low over the horizon on the left. LOLA elevation data sampled for drawing; a weak fill light is on as a viewing aid, the shadows are black without it.

a_opening_south_pole_wide_interface.png
    The same picture with the interface of the tool.

b_product_two_sites.png
    Product. Shackleton crater rim crest and de Gerlache crater rim crest side by side at 2027-07-29T06:00:00Z, observer 2 m, each view on its own Sun: the default view, drawer closed, the obstacle view switched off (no outline, no card).

b_product_two_sites_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

c_key_moment_near_ridge.png
    Key moment. Shackleton crater rim crest at 2026-12-07T04:00:00Z, observer 2 m, looking at the Sun's azimuth: the Sun is behind the ridge 673 m away at azimuth 350.5 deg that costs 372.8 h of Sun in the window of the package (14 November 2026 to 14 November 2028). The package flags it as within 1 km: it depends on single pixels of the elevation model (here the 5 m site model).

c_key_moment_near_ridge_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

d_calendar_drawer.png
    Shackleton crater rim crest at 2027-07-28T17:00:00Z: the drawer open on the lunar-day calendar and the landing windows of the example requirement.

d_calendar_drawer_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

d_uncertainty_drawer.png
    Shackleton crater rim crest at 2027-07-28T17:00:00Z: the drawer open on the uncertainty page (the survey of the stated landing ellipse; the band of each event stands under its countdown).

d_uncertainty_drawer_clean.png
    The same picture without the interface: the view alone, with one line that says which site, time and package it shows.

e_lander_lit_side.png
    Shackleton crater rim crest at 2027-09-19T13:00:00Z: a camera on the lander's sunlit side, the Sun 50 deg off the view axis behind it (not the observer's view), with the mast that carries the observer in the background. Lander, mast and boulders are scale objects of the team's own design, not part of the package.

e_lander_lit_side_interface.png
    The same picture with the interface of the tool.

c_key_moment_near_ridge.mp4
    Key moment, 9 s at 60 frames per second. Shackleton crater rim crest, observer 2 m, the view on the Sun; time runs from 2026-12-06T18:00:00Z to 2026-12-07T03:30:00Z. The Sun goes behind the ridge 673 m away at azimuth 350.5 deg: when the package gives the Sun as partly hidden the outline of the ridge lights up and the card with its cost appears; the caption changes when the package gives the Sun as hidden.

f_pitch_video_1080p60.mp4
    One video, 27.90 s, 1920 x 1080 at 60 frames per second, H.264, no audio. Five parts, each a real render of the running scene: (1) 5.9 s, a camera move from 9 km above down to the lander at Shackleton crater rim crest, 2027-09-19T13:00:00Z (a camera move only; no descent is simulated); (2) 6 s, Shackleton crater rim crest and de Gerlache crater rim crest side by side from 2027-07-28T16:30:00Z to 2027-07-28T20:00:00Z: the Sun sets behind a ridge on the left and stays up on the right; (3) 8 s, the key moment as in c_key_moment_near_ridge.mp4; (4) 4 s, the calendar drawer while five days pass from 2027-07-28T17:00:00Z; (5) 4 s, the wide view with lander, mast and boulders while 36 h pass from 2027-09-19T13:00:00Z. The only text is that of the interface and its caption line.

The ground is LOLA elevation data sampled on 480 rings per azimuth (the 5 m site models near the three project sites). Roughness and small craters finer than that data are
illustrative shading computed in the surface shader: positions, shadows and the horizon are those of the data. Stars are the
Yale Bright Star Catalogue, turned for the date. Lander, mast and boulders are scale objects of the team's own design, not part
of any package. Surface shading, exposure, the glare of the Sun and the fill light while the Sun is down are display choices
(see unreal/README.md). The Earth carries the Blue Marble map of NASA (see CREDITS.md). Not in any of these: an atmosphere, clouds or night lights.
