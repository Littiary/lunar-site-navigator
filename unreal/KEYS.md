# Lunar Landing Site Navigator: how to use the view

Start `LunarSiteNavigator.exe`. No installation and no network are needed. The program shows
the published packages that were copied into the build; every number on screen is a field
of a package.

## With the mouse alone

The mouse pointer is visible. The header shows the site, the time and three chips: the Sun,
the Earth (each with the time to its next set or rise) and whether a landing now meets the
example requirement. Under it are the three main actions and, at the bottom, one time strip.
That is the whole view at the start. **More** (key T) brings the other controls in labelled
groups along the bottom, the panorama and the list of numbers; **Less** takes them away again.
When the Sun or the Earth is up but outside the picture, an arrow at the edge points to it;
click it to turn the view there.

| What | How |
| --- | --- |
| Choose the time | drag on either time strip (upper: six days around the selected time; lower: the whole computed range) |
| All other controls | **More** / **Less** |
| Turn to the Sun when it is outside the picture | click the arrow at the edge of the picture |
| Camera position | **Camera** goes round: the observer's own view, a camera near the lander looking towards the Sun, a wide view of the site |
| Camera move from high above down to the site | **Arrival view** (a camera move only; no descent is simulated) |
| The first lunar day after the planned landing, played fast | **First lunar day** |
| Play the timeline | button **Play / pause**, **Slower**, **Faster** |
| Step in time | **< Step**, **Step >** (one sample of the package), **< Day**, **Day >** |
| Jump to the next sunset | main button **Jump to next sunset** |
| Next or previous rise or set of the Sun | **< Sunrise / set**, **Sunrise / set >** |
| Another site | **Sites ...** opens the list: click a name |
| Any two sites for the comparison | in the list, **Left** and **Right** beside each site |
| A site of your own | at the foot of the list: type latitude and east longitude, **Compute and show** (needs the science core's Python environment on the machine; the view says so if it is missing) |
| Two sites side by side at the same instant | main button **Compare two sites**; **Next site >** in the header of the right view changes the right one |
| Calendar, uncertainty, mast-height trade and site pairs | **Calendar**, **Uncertainty**, **Mast / pairs** (a page is shown only if the package has the field) |
| Which terrain hides the Sun or the Earth, and what it costs | main button **What blocks the Sun?** (on at the start) |
| Package id, frame, contract version, test status | **Details** |
| Lander, mast and boulders for scale | **Scale objects** |
| A weak light while the Sun is down | **Night fill light** |
| Observer height (mast height) | **Observer height** goes round the heights of the package |
| Keep the view on the Sun | **Follow Sun** |
| Slower graphics card | **Low quality** |
| Look round | hold the right mouse button and move |
| Zoom | mouse wheel |
| This list on screen | **Help (F1)** |

A lit button is switched on.

## Keys

| Key | Action |
| --- | --- |
| arrow keys | look |
| Z / X | zoom in / out |
| Space | play and pause |
| [ / ] | half / double the playing speed |
| Q / E | one sample back / forward (Shift: 24 samples) |
| , / . | one day back / forward |
| B / N | previous / next rise or set of the Sun (Shift: of the Earth) |
| Home / End | first / last sample |
| 1 .. 9 | show that site of the list (Shift: on the right, side by side) |
| C | two sites side by side on and off |
| K | calendar and landing windows |
| U | uncertainty |
| M | mast-height trade and site pairs |
| R | next requirement of the package |
| O | obstacle view |
| F | keep the view on the Sun's azimuth |
| PageUp / PageDown | observer height |
| H | horizon line of the package |
| L | fill light while the Sun is down (a display aid, not physics) |
| G | lower drawing quality |
| I | details: package, frame, contract version, test status |
| S | site list, pinning two sites, custom coordinates |
| T | all controls on and off |
| V | camera position: observer, near the lander, wide |
| A | camera move from high above down to the site |
| D | play the first lunar day after the planned landing |
| P | scale objects (lander, boulders) |
| F1 | list of keys on screen |
| Tab | hide the pointer and look with the mouse alone (Tab again brings it back) |
| Esc | quit |

## Only on keys (no button)

A first-time user will not find these without this list:

- the events of the Earth (Shift + B / N); the buttons jump to the events of the Sun only;
- choosing a site by its number (1 .. 9) and choosing the right site directly (Shift + number);
- the next requirement (R), the horizon line (H);
- jumping to the first or last sample (Home / End) and stepping 24 samples (Shift + Q / E);
- Tab for looking with the mouse without holding a button.

## Command line

`LunarSiteNavigator.exe -windowed -ResX=1920 -ResY=1080` runs in a window.
`-LsnLowQuality` starts with the lower drawing quality.
`-LsnSite=<site_id>` or `-LsnCompare=<site_id>,<site_id>` chooses the sites shown at the start.
`-LsnControls` starts with all controls shown. `-LsnView=hero` or `-LsnView=wide` starts with
that camera position.
