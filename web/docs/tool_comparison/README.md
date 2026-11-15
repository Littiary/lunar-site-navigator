# Comparison with existing lunar tools: LROC QuickMap and NASA Moon Trek

Task 10 of the web stream. Every row of the tables below rests on a trial made on **15 November 2026** (UTC) or on a provider page read that day. Nothing here is a claim about accuracy: the three tools answer different questions with different inputs, and no independent reference was used to rank them.

## 1. Summary for the jury

LROC QuickMap and NASA Moon Trek are map portals. They show the whole Moon, hundreds of data layers, and, in QuickMap, long-term Sun and Earth visibility maps and simulated terrain shadows for a chosen UTC time. For the question "where is the light good?", QuickMap answers for every pixel of the polar region at once, which Lunar Site Navigator does not do.

Lunar Site Navigator starts where the map ends: at one chosen point and its mast height. For that point it publishes the 360° terrain horizon, every Sun and Earth rise and set over two years, the terrain that causes each loss, a 24-month calendar, the landing windows of a stated requirement and how far a landing date can slip, for two sites side by side on one UTC timeline. Every number is read from a checksummed result package, and the page links the validation card, including the check that failed.

The tools are complementary: a planner would use QuickMap or Moon Trek to find candidate places and Lunar Site Navigator to compare dates and heights at the candidates.

## 2. What was tried, and how

| | LROC QuickMap | NASA Moon Trek | Lunar Site Navigator |
|---|---|---|---|
| Address | https://quickmap.lroc.im-ldi.com (the former address quickmap.lroc.asu.edu redirects; the start notice says the site is now hosted at Intuitive Machines) | https://trek.nasa.gov/moon/ (portal version 3.6.29 in its file names) | local build of this repository (`python -m lsn_web.site`), served on localhost. First tried at commit `022f1e6` (contract 0.11); the package values and the two screenshots below were taken again the same day from the packages republished in contract 0.12 |
| Session (UTC) | 2026-11-15, 04:05 to 04:14 | 2026-11-15, 04:14 to 04:17 | 2026-11-15, 04:16 and 09:20 |
| Login | none | none; no account was created | none |
| Browser | desktop Chromium, viewport 1280 × 800 | same | headless Edge, viewport 1600 wide |

**Sites.** The two project sites, with the coordinates of the published packages (planetocentric latitude, east longitude, frame `MOON_ME_DE440_ME421`):

| Site | Latitude | Longitude | Package |
|---|---|---|---|
| Shackleton crater rim crest | −89.80531° | −154.23109° (205.76891° E) | `site-689eb279e17d7879`, contract 0.12 |
| de Gerlache crater rim crest | −88.66410° | −68.41044° (291.58956° E) | `site-9aced62d65a3bd00`, contract 0.12 |

**Instant.** 2027-01-04 10:00:00 UTC, inside the package window (2026-11-14 to 2028-11-14) and inside the stated validity of the QuickMap shadow layer (2025 to 2043).

**QuickMap settings.** Projection "Orthographic (South Pole)". Layers: "LRO LOLA / Sun Visibility 60m", "LRO LOLA / Earth Visibility 60m", "ACT: Temporal Illumination / Terrain Shadows @UTC (80S,20mpp)", basemap "WAC+NAC+NAC_ROI_MOSAIC". The sites were entered as point markers through the search box (`-89.80531,-154.23109` and `-88.6641,-68.41044`). The readout "Value at Cursor" was taken with the pointer on the marker; QuickMap's own LAT/LON readout confirmed the position to 0.00001° in latitude and 0.0005° in longitude. The time was typed into the time control as `2027-01-04T10:00:00Z`; the layer panel then showed "Requested Time 2027-01-04T10:00" and "Sub-Solar (lat,lon) −0.96249, 221.52318".

**Moon Trek settings.** "South Pole Map" projection (IAU2000:30120), default basemap. Tools menu opened; "Calculate Sun Angle" run with its default range 2026-11-15 00:00 to 2026-11-16 00:00 UTC and interval 50, at a pin near Shackleton crater.

**Evidence labels used below.**
- **[H]** seen hands-on in the session above.
- **[D]** stated by the provider (sources in section 7), not tried.
- **[N]** not found or not tested; the reason is given.

## 3. Capability table

| Capability | Lunar Site Navigator | LROC QuickMap | NASA Moon Trek |
|---|---|---|---|
| **Terrain visualisation** | Horizon chart, 360° sky panorama, 3-D ground view built from the package's terrain patches, Moon globe with site markers [H]. No map browser and no image layers; only the 20 published sites, or a coordinate computed locally with the Python core. | Whole-Moon map with polar projections, LROC WAC/NAC basemaps, LOLA and SLDEM2015 elevation, slope and roughness layers; 28 layers in the "LRO LOLA" group alone [H]. 3-D mode [D]. | Whole-Moon map with global, north-pole, south-pole and 3-D globe views; elevation profile, distance, 3-D print file, subsetting tools open without an account [H: menu]. Slope, crater and rock detection need a Trek account [H: menu tooltip]. |
| **Horizon information** (what the terrain hides, seen from one point) | 360° horizon elevation per site at six observer heights, the distance of the terrain that sets it, and the obstacles that cost visible time [H]. | Not found in the 2-D map in this session [N]. QuickMap TerrainShadows (QTS) is described as having "Traverse" and "Antenna" modes [D]; not tried. | "Line of Sight" is in the menu but needs a Trek account [H: greyed, tooltip]; not tried [N]. |
| **Sun visibility** | Per site: visible or hidden at each hour, exact rise and set times, share of the two-year window, longest outage [H]. The Sun is a disc: any visible fraction counts. | Long-term average map ("Sun Visibility 60m": share of 1-hour steps over about 18.6 years with any part of the disc visible; 85° to the pole) [H]. Simulated shadows at a chosen UTC time ("Terrain Shadows @UTC", 20 m per pixel, 80° S to the pole, Sun disc centre as the light source, valid 2025 to 2043) [H]. A layer of NAC images matching the current illumination [D]. | "Calculate Sun Angle": azimuth and elevation of the Sun over a UTC range at a pin, with CSV export, open without an account [H]. Whether it accounts for terrain was not determined [N]. "Surface Lighting" needs a Trek account [H: tooltip]; lighting analysis is described by the provider [D]. |
| **Earth visibility** | Per site: visible or hidden at each hour, rise and set times, share of the window, longest outage, Deep Space Network link window [H]. | Long-term average map ("Earth Visibility 60m", same method as the Sun layer) [H]. Earth as a light source in 3-D mode and a compass with the current Earth and Sun positions [D]. A per-instant Earth visibility layer was not found [N]. | Not found without an account [N]. |
| **Time-dependent planning** | Timeline with play and step controls; countdown to the next rise or set; 24-month calendar by lunar day; landing windows of a stated requirement; days a planned landing can slip [H]. Fixed window 2026-11-14 to 2028-11-14. The shipped landing requirement is an example chosen by the team. | Time control with play, speed and an ISO 8601 date field; the shadow layer follows it [H]. A list of rise and set times, windows or a calendar for a point was not found [N]. | Sun angle over a chosen date range [H]. Nothing found for windows or a calendar [N]. |
| **Observer height** | Six heights per site (0, 1, 2, 5, 10, 20 m), each with its own horizon, events and metrics [H]. | The search box accepts `lat,lon(,height)` [H: placeholder text]; its effect was not tested [N]. The description of the visibility layers does not state an observer height [H]. | No height field in the Sun Angle dialog [H]. |
| **Comparison of several sites** | Two sites side by side on one shared UTC timeline; a site-pairs package with the hours either, both or neither site sees the Sun or the Earth [H]. | Several markers on one map; a map layer by nature shows all places at once [H]. No side-by-side time comparison found [N]. | Not found [N]. |
| **Data provenance and validation** | Package id and SHA-256 of every array, checked in the browser; the method status of every number; a validation card with 32 checks, 31 passed and 1 failed, and a list of what is not validated; a separate accuracy and limits page [H]. | Each layer has a description with its method and citation (the visibility layers cite Mazarico et al. 2011) [H]. | Source information for each data product [D]. |
| **Coverage** | 20 published sites; any other coordinate needs the Python core and the terrain data on a computer. | Every pixel of the mapped region, in the browser [H]. | Whole Moon, in the browser [H]. |

## 4. Numbers read on the day

These are readouts, placed side by side for context. They are **not** an accuracy test: the time spans, the surface models, the definition of "visible" and the observer height differ, as the last column says.

### 4.1 Long-term share of time with the Sun or the Earth visible

| Site | QuickMap "Sun Visibility 60m" | Lunar Site Navigator `sun_visible_fraction_of_time` | QuickMap "Earth Visibility 60m" | Lunar Site Navigator `earth_visible_fraction_of_time` |
|---|---|---|---|---|
| Shackleton rim crest | 0.76840 (map shown at 57.48 m/px) | 0.4668 at 0 m, 0.7201 at 1 m, 0.7693 at 2 m, 0.8626 at 20 m | 0.56600 | 0.5244 at 0 m to 0.5248 at 20 m |
| de Gerlache rim crest | 0.82692 (map shown at 52.16 m/px) | 0.5003 at 0 m, 0.8378 at 1 m, 0.8465 at 2 m, 0.8848 at 20 m | 0.61420 | 0.2443 at 0 m, 0.5729 at 1 m, 0.5738 at 20 m |

Differences in definition:
- QuickMap: average over about 18.6 years in 1-hour steps, one value per 60 m pixel, method of Mazarico et al. (2011) with updated topography; observer height not stated in the layer description.
- Lunar Site Navigator: two years (2026-11-14 to 2028-11-14), one point, LOLA 5 m site model near the site and the 20 m polar product beyond it, six stated observer heights.

What the session showed about sensitivity: on a rim crest the QuickMap value changes sharply from pixel to pixel. Two screen pixels (about 115 m) from the Shackleton marker the Sun value read 0.61936, 0.46984, 0.70792 and 0.61276; at de Gerlache 0.70240, 0.64972, 0.46840 and 0.54064. With the map zoomed out to 212.75 m/px the readout at the Shackleton marker was 0.48660 instead of 0.76840. In the packages the same sensitivity appears as the step from 0 m to 1 m observer height. Any single number for such a site therefore depends on position to within tens of metres and on height to within a metre.

### 4.2 Sunlit or shadowed at 2027-01-04 10:00 UTC

| Site | QuickMap "Terrain Shadows @UTC" at the marker | Neighbouring pixels (3 screen pixels away) | Lunar Site Navigator window `sun_visible` |
|---|---|---|---|
| Shackleton rim crest | 0 (shadow), map at 39.27 m/px | 0, 1, 0, 0 | not visible at 0 m; visible at 1, 2, 5, 10 and 20 m |
| de Gerlache rim crest | 1 (sunlit), map at 34.06 m/px | 1, 1, 1, 0 | visible at all six heights |

Both tools place the Shackleton point at the edge of the light at that hour and the de Gerlache point in sunlight. QuickMap uses the centre of the solar disc on a 20 m surface; the package counts any visible fraction of the disc from a stated height above a 5 m surface. Agreement at two points and one instant is an observation, not a validation.

### 4.3 Moon Trek Sun Angle

The tool returned a plot of Sun azimuth (about 225° falling to about 213°) and elevation (close to 0°) for 2026-11-15 to 2026-11-16 UTC at a pin about 10 km from the Shackleton rim site, and offered a CSV export. The pin could not be placed on the exact site coordinates in the time available, so no value is compared with the package.

## 5. Screenshots

All taken on 2026-11-15 (UTC). The QuickMap and Moon Trek captures are 800 × 500 pixel views of a 1280 × 800 viewport. The two Moon Trek captures of the Sun Angle tool are cropped by 22 pixels at the bottom edge, which removes the portal's logo strip; nothing else was edited.

| File (`screenshots/`) | Shows |
|---|---|
| `2026-11-15_quickmap_shackleton_sun_earth_visibility_60m.jpg` | QuickMap, south-pole projection, pointer on the Shackleton marker: LAT −89.80531, LON 205.76849, Earth Visibility 0.56600, Sun Visibility 0.76840, 57.48 m/px. The grey overlay is the Earth Visibility layer. |
| `2026-11-15_quickmap_de_gerlache_sun_earth_visibility_60m.jpg` | The same at the de Gerlache marker: LAT −88.66410, LON 291.58955, Earth 0.61420, Sun 0.82692, 52.16 m/px. |
| `2026-11-15_quickmap_shackleton_terrain_shadows_2027-01-04T1000Z.jpg` | QuickMap Terrain Shadows layer with the time control at 2027-01-04 10:00 UTC, pointer on the Shackleton marker: value 0. Yellow is sunlit, purple is shadow. |
| `2026-11-15_quickmap_de_gerlache_terrain_shadows_2027-01-04T1000Z.jpg` | The same at the de Gerlache marker: value 1. |
| `2026-11-15_moontrek_tools_menu_account_required.jpg` | Moon Trek tools menu without an account. Greyed entries (Slope, Surface Lighting, Line of Sight and others) show the tooltip "This tool requires a Trek account". |
| `2026-11-15_moontrek_sun_angle_dialog_shackleton_area.jpg` | Moon Trek "Calculate Sun Angle" dialog: start and end date in UTC and an interval. |
| `2026-11-15_moontrek_sun_angle_result_shackleton_area.jpg` | Its result: azimuth and elevation against time, with "Export Sun Angle to CSV". |
| `2026-11-15_lsn_compare_horizon_2027-01-04T1000Z_0m.png` | Lunar Site Navigator, both sites at 2027-01-04 10:00 UTC and 0 m observer height: status cards and the horizon with the Sun and the Earth. |
| `2026-11-15_lsn_compare_calendar_2m.png` | Lunar Site Navigator opportunity calendar for both sites at 2 m: hours per lunar day, landing windows of the example requirement. |

## 6. What Lunar Site Navigator adds, and what it lacks

Adds, as observed in section 3:
1. **Events for a point**: rise and set times and windows, not a map value to be read at a cursor.
2. **Observer height as a variable**: the effect of a mast is a published number (section 4.1).
3. **Planning quantities**: lunar-day calendar, landing windows for a stated requirement, slip tolerance, joint outage of two sites.
4. **The cause of a loss**: the terrain that hides the Sun, with distance and hours lost.
5. **Stated validation**: every number names its method status, and the failed check stays on the card.

Lacks, compared with the two portals:
1. No map: a site cannot be found or explored spatially in the web view.
2. Twenty sites; a new coordinate needs the Python core and the terrain data on a computer.
3. No imagery layers, and no long-term (18.6-year) averages; the window is two years.
4. No independent reference for event times on real terrain (see the validation card).

## 7. Limits of this comparison

- One session per tool on one day, by one person, with the tools' default settings unless stated.
- No Trek account was created, so Moon Trek's Surface Lighting, Line of Sight and Slope tools were not tried. Their existence is taken from the menu and from the provider.
- QuickMap's 3-D mode, QTS-3D, the Traverse and Antenna modes and the `height` part of the coordinate search were not tried.
- "Not found" means not found in this session; the feature may exist elsewhere in the tool.
- Cursor readouts depend on the display resolution, as section 4.1 shows. Each reading states the resolution QuickMap reported.
- The numbers in section 4 compare different quantities. They do not show that any tool is more accurate than another.
- The landing requirement in the Lunar Site Navigator screenshots is an example chosen by the team, not a mission criterion.

## 8. Sources

Hands-on: the two tools at the addresses in section 2. Layer descriptions quoted in section 3 were read inside QuickMap ("Layer details") on 2026-11-15.

Provider pages, read on 2026-11-15:

| Source | Used for |
|---|---|
| LROC, "Lunar QuickMap Spring 2020 Update", https://lroc.im-ldi.com/posts/1153 | Sun and Earth visibility layers in the polar orthographic projections |
| LROC, "Lunar QuickMap Fall 2020 Update" (29 October 2020), https://lroc.im-ldi.com/news/1167 | Numeric layers and import of user data |
| Applied Coherent Technology, "July 2024 QuickMap release" (8 July 2024), https://www.actgate.com/post/july-2024-quickmap-release | NAC illumination layer at the current UTC time, shadows and Earth as a light source in 3-D mode, compass |
| Applied Coherent Technology, "QuickMap year 2022" (23 March 2023), https://actgate.com/post/quickmap-year-2022 | QuickMap TerrainShadows (QTS), QTS-2D modes |
| NASA Moon Trek, "About", https://trek.nasa.gov/moon/jpl/config/textAbout.html | Portal version, scope, source information per product |
| E. Law and B. Day, "Moon Trek" abstract EPSC2022-93 (2022), https://meetingorganizer.copernicus.org/EPSC2022/EPSC2022-93.html | Lighting analysis and Sun angle tools, line of sight being added |
| E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, M. H. Torrence (2011), "Illumination Conditions of the Lunar Polar Regions Using LOLA Topography", Icarus 211, 1066, doi:10.1016/j.icarus.2010.10.030 | Method cited by the QuickMap visibility layers (as quoted in their layer descriptions; the paper itself was not consulted) |

Package values: `packages/site/shackleton-rim-crest/site-689eb279e17d7879/manifest.json` and `packages/site/de-gerlache-rim-crest/site-9aced62d65a3bd00/manifest.json` (`timeline.metrics`, `timeline.windows`).

QuickMap and its layers are products of the LROC team and Applied Coherent Technology; Moon Trek is a NASA Solar System Treks portal developed at JPL. The screenshots are shown for comparison and are credited in `CREDITS.md`.
