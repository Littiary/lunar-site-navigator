# Lunar Landing Site Navigator: how to use the view

Start `LunarSiteNavigator.exe`. No installation and no network are needed. The program shows
the published packages that were copied into the build; every number on screen is a field
of a package.

## With the mouse alone

The mouse pointer is visible. Everything a first look needs is on screen:

| What | How |
| --- | --- |
| Choose the time | drag on either time strip (upper: six days around the selected time; lower: the whole computed range) |
| Play the timeline | button **Play / pause**, **Slower**, **Faster** |
| Step in time | **< Step**, **Step >** (one sample of the package), **< Day**, **Day >** |
| Next or previous rise or set of the Sun | **< Sunrise / set**, **Sunrise / set >** |
| Another site | **Next site** |
| Two sites side by side at the same instant | **Two sites**; **Next right site** changes the right one |
| Calendar, uncertainty, mast-height trade and site pairs | **Calendar**, **Uncertainty**, **Mast / pairs** (a page is shown only if the package has the field) |
| Which terrain hides the Sun or the Earth | **Obstacle** (on at the start) |
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
| L | weak fill light (a display aid, not physics) |
| G | lower drawing quality |
| F1 | list of keys on screen |
| Tab | hide the pointer and look with the mouse alone (Tab again brings it back) |
| Esc | quit |

## Only on keys (no button)

A first-time user will not find these without this list:

- the events of the Earth (Shift + B / N); the buttons jump to the events of the Sun only;
- choosing a site by its number (1 .. 9) and choosing the right site directly (Shift + number);
- the next requirement (R), the horizon line (H), the fill light (L);
- jumping to the first or last sample (Home / End) and stepping 24 samples (Shift + Q / E);
- Tab for looking with the mouse without holding a button.

## Command line

`LunarSiteNavigator.exe -windowed -ResX=1920 -ResY=1080` runs in a window.
`-LsnLowQuality` starts with the lower drawing quality.
`-LsnSite=<site_id>` or `-LsnCompare=<site_id>,<site_id>` chooses the sites shown at the start.
