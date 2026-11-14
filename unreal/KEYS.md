# Lunar Landing Site Navigator: how to use the view

Start `LunarSiteNavigator.exe`. No installation and no network are needed. The program shows
the published packages that were copied into the build; every number on screen is a field
of a package.

## With the mouse alone

The mouse pointer is visible. Top left: the site, the time (UTC), one line with the
coordinates and the observer height. Top right: three state chips, each with a bar of its
state colour (amber Sun, blue Earth, green requirement met, red not met), the state word and
the countdown as the largest thing; under a countdown stands its uncertainty where the package
states one. Bottom left: the control bar. Bottom: the time strip with a tick and a date at
every UTC midnight and a playhead that carries its own time.

| What | How |
| --- | --- |
| Choose the time | drag on the time strip (six days around the selected time) |
| Play the timeline | **Play** (it becomes **Pause**) |
| Jump to the next sunset | **Next sunset** |
| Which terrain hides the Sun or the Earth, and what it costs | **Obstacle** (on at the start): a thin line along the ridge and a card with the hours it costs, its distance and azimuth |
| Two sites side by side at the same instant | **Compare** (it becomes **One site**); **Next site** in the header of each half changes that half; one time strip is shared |
| Camera position | **Camera** goes round: the observer's own view, a camera near the lander looking towards the Sun, a wide view of the site |
| Everything else | **More** opens a drawer from the right (**Less** closes it). Its tabs: |
| ... calendar and landing windows | tab **Calendar** |
| ... uncertainty | tab **Uncertainty** |
| ... mast-height trade and site pairs | tab **Mast height** |
| ... another site, any two sites for the comparison | tab **Sites**: click a name to show it; **Left** and **Right** pin a site for a half; the wheel scrolls the list; click the search field and type to narrow it by name, programme or category |
| ... a site of your own | at the foot of the tab **Sites**: type latitude and east longitude, **Compute and show** (needs the science core's Python environment, elevation data and kernels on the machine; the view says what is missing) |
| ... package id, frame, contract version, test status, what each number rests on, the note on the example requirement | tab **Evidence** |
| ... slower, faster, steps, days, sunrise and sunset, first lunar day, arrival view, observer height, follow Sun, scale objects, night fill light, low quality, help | tab **Controls** |
| Turn to the Sun when it is outside the picture | **The Sun is outside the picture: look at it** (bottom left, shown only then) |
| Look round | hold the right mouse button and move |
| Zoom | mouse wheel (over the open list of sites it scrolls the list) |

A button whose switch is on has a brighter edge. A button that needs a timeline is grey for a
package without one. The line of hints above the control bar fades five seconds after the
pointer last moved and comes back when it moves.

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
| I | evidence: package, frame, contract version, test status |
| S | site list, pinning two sites, custom coordinates |
| T | the drawer (More / Less) |
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
`-LsnControls` starts with the drawer open. `-LsnView=hero` or `-LsnView=wide` starts with
that camera position.
