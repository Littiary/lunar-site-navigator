# What the viewer pages fetch on the first screen

A measurement note for the web stream. Nothing here is an estimate: every number is a file size, the size of a file after gzip, or the length of a response of the hosted site. No code was changed.

Measured on 14 November 2026 on:

* the published set in `packages/` (commit `ec83a98`, contract 0.11, 20 sites);
* the web code of `main` (`web/` at `4184f75`), read only;
* the hosted site, branch `gh-pages` at `96f1d16`. It holds the contract 0.9 set of three sites, and its root page is the comparison of two sites. Its `compare.js` and `panel.js` differ from `main` in how the address of the index is formed, not in what is fetched.

Sizes are bytes. **Stored** is the file as it is in the repository. **gzip 6** is the file compressed locally with gzip at level 6. **Sent** is the length of the response body that the hosted site returned.

## 1. Files and bytes of the first screen, published set

The comparison page opens on the first two sites of the index, the single-site viewer on the first one.

| Screen | Package files | Stored | gzip 6 |
|---|---|---|---|
| Comparison, sites as the page opens (`apollo-11`, `apollo-12`) | 23: index, 2 manifests, 20 arrays | 4,766,882 | 1,911,674 |
| Single site, as the page opens (`apollo-11`) | 12: index, manifest, 10 arrays | 2,362,909 | 949,205 |
| Comparison of two project sites (`shackleton-rim-crest`, `de-gerlache-rim-crest`) | 23 | 9,464,260 | 3,407,261 |
| Single site, the largest package (`shackleton-rim-crest`) | 12 | 5,019,053 | 1,758,273 |

By part, for the two screens as they open:

| Part | Files per site | Comparison, stored | Comparison, gzip 6 | Single site, stored | Single site, gzip 6 |
|---|---|---|---|---|---|
| `index.json` | | 9,054 | 1,571 | 9,054 | 1,571 |
| `manifest.json` | 1 | 2,442,948 | 640,162 | 1,196,415 | 315,330 |
| `horizon.elevation_deg`; `azimuth_deg` and `elevation_deg` of the Sun and the Earth | 5 | 596,000 | 509,241 | 298,000 | 252,594 |
| `margin_deg` and `visible_fraction` of the Sun and the Earth | 4 | 1,684,320 | 736,678 | 842,160 | 368,205 |
| `horizon.distance_m` | 1 | 34,560 | 24,022 | 17,280 | 11,505 |
| Sum | 11 | 4,766,882 | 1,911,674 | 2,362,909 | 949,205 |

Every site has the same ten arrays and 17,545 time samples, so any pair can be summed from this table (add `index.json` once):

| Site | Observer heights | Manifest | Ten arrays | Sum | Sum, gzip 6 |
|---|---|---|---|---|---|
| `apollo-11` | 3 | 1,196,415 | 1,157,440 | 2,353,855 | 947,634 |
| `apollo-12` | 3 | 1,246,533 | 1,157,440 | 2,403,973 | 962,469 |
| `apollo-14` | 3 | 1,178,769 | 1,157,440 | 2,336,209 | 945,113 |
| `apollo-15` | 3 | 1,176,618 | 1,157,440 | 2,334,058 | 942,418 |
| `apollo-16` | 3 | 1,200,548 | 1,157,440 | 2,357,988 | 939,224 |
| `apollo-17` | 3 | 1,180,133 | 1,157,440 | 2,337,573 | 941,966 |
| `artemis3-region-mons-mouton-representative` | 3 | 1,295,153 | 1,157,440 | 2,452,593 | 994,252 |
| `blue-ghost-1` | 3 | 1,210,188 | 1,157,440 | 2,367,628 | 963,916 |
| `chandrayaan-3` | 3 | 1,300,354 | 1,157,440 | 2,457,794 | 970,583 |
| `change-3` | 3 | 1,277,802 | 1,157,440 | 2,435,242 | 969,396 |
| `change-4` | 3 | 310,921 | 1,157,440 | 1,468,361 | 689,384 |
| `change-5` | 3 | 1,299,068 | 1,157,440 | 2,456,508 | 976,189 |
| `change-6` | 3 | 352,636 | 1,157,440 | 1,510,076 | 705,097 |
| `de-gerlache-rim-crest` | 6 | 2,411,047 | 2,034,160 | 4,445,207 | 1,648,988 |
| `im-1-odysseus` | 3 | 1,297,829 | 1,157,440 | 2,455,269 | 993,093 |
| `im-2-athena` | 3 | 1,475,068 | 1,157,440 | 2,632,508 | 1,056,334 |
| `malapert-massif-summit` | 6 | 2,779,503 | 2,034,160 | 4,813,663 | 1,844,403 |
| `shackleton-rim-crest` | 6 | 2,975,839 | 2,034,160 | 5,009,999 | 1,756,702 |
| `slim` | 3 | 1,172,069 | 1,157,440 | 2,329,509 | 937,938 |
| `surveyor-1` | 3 | 1,241,791 | 1,157,440 | 2,399,231 | 961,906 |

## 2. What the first drawing needs

Order of loading on the comparison page: `notice.json`, `packages/index.json`, then for the left site its manifest and its ten arrays, then the same for the right site. Each request is sent after the one before it has arrived (`loadSiteData` in `panel.js` awaits each array in turn, and `main` in `compare.js` awaits the left site before the right one). The page draws once, after the last array of the right site. The single-site viewer does the same for one site.

What each part of the page reads:

| Part of the page | Reads |
|---|---|
| Status chips (Sun visible, Earth visible, DSN link, eclipse), time label, summary table, list of the next events, footer, column "In window" | The manifest: `timeline.windows`, `timeline.metrics`, `timeline.events`, `timeline.time`, `methods`. No array. |
| Horizon chart with the Sun and Earth markers | `horizon.elevation_deg` (the row of the chosen height); `azimuth_deg` and `elevation_deg` of both bodies |
| Readout table | The same, and `margin_deg` and `visible_fraction` of both bodies (the row of the chosen height) |
| Sky view (button on the comparison page, tab in the single-site viewer) | The same nine arrays |
| 3-D view (tab in the single-site viewer) | `horizon.elevation_deg`, `horizon.distance_m`, `azimuth_deg` and `elevation_deg` of both bodies; `three.module.js` is loaded when the tab is opened |

So:

* The chips, the countdown metrics (`*_time_to_set_s` and `*_time_to_rise_s` are entries of `timeline.metrics`), the summary numbers and the event list need the index and the manifests and nothing else: 2,452,002 bytes stored, 641,733 bytes gzip 6 for the two sites the comparison opens on.
* The horizon arrays are needed for the chart, not for the chips: five files per site, 596,000 bytes stored for the two sites.
* `margin_deg` and `visible_fraction` are needed for the readout table and the sky view: four files per site, 1,684,320 bytes stored for the two sites.
* `horizon.distance_m` is fetched on both pages. The 3-D view of the single-site viewer uses it; the comparison page does not use it (34,560 bytes stored for the two sites).
* The terrain patches, the obstacle arrays, `blocker_azimuth_index`, `lit_fraction`, `angular_radius_deg`, `ellipse_visible_share`, the direction table and the site-pairs package are fetched by no page. They cost nothing when a page opens.
* An array is fetched whole, with all observer heights, and the page uses one row. Of the 1,684,320 bytes of `margin_deg` and `visible_fraction` for the two sites the comparison opens on, 561,440 are the rows of the default height (three heights); for two project sites it is 561,440 of 3,368,640 (six heights). Choosing another height fetches nothing more. The viewer checks the size and the SHA-256 of each array against the manifest, and that check is on the whole file.

## 3. What the hosted site sends

Measured at 2026-11-14T20:49Z by asking the hosted site for each file with the header `Accept-Encoding: gzip, deflate, br, zstd`, as a browser does. Every response came with `content-encoding: gzip`, also the arrays, which are served as `application/octet-stream`. Every body, decompressed, was the file of the branch.

| Type | Files asked | Stored | Sent | gzip 6 of the same files |
|---|---|---|---|---|
| `.json` | 4 | 9,100,203 | 1,336,086 | 1,320,007 |
| `.f4` | 20 | 4,068,320 | 2,278,108 | 2,277,194 |
| `.i4` | 1 | 34,560 | 793 | 840 |
| `.js` | 7 | 1,332,178 | 284,725 | 280,726 |
| `.html` | 3 | 3,775,543 | 976,867 | 963,605 |
| `.css` | 1 | 5,603 | 1,755 | 1,759 |

The first screen of the hosted site (comparison of `de-gerlache-rim-crest` and `malapert-massif-summit`, contract 0.9 packages): 30 files, 13,217,004 bytes stored, 3,631,549 bytes sent.

| Part | Files | Stored | Sent |
|---|---|---|---|
| Page: `index.html`, `viewer.css`, `compare.js`, `package.js`, `panel.js`, `sky.js`, `notice.json` | 7 | 48,764 | 17,578 |
| `packages/index.json` | 1 | 1,807 | 537 |
| Two manifests | 2 | 9,098,113 | 1,335,326 |
| Twenty arrays | 20 | 4,068,320 | 2,278,108 |

Further files of the single-site viewer (`viewer/index.html`, `viewer.js`, `view3d.js`, `three.module.js`): 1,298,386 bytes stored, 272,250 sent; `three.module.js` alone is 1,272,972 stored and 263,040 sent.

The contract 0.11 set is not on the hosted site, so what the host sends for it has not been measured. The gzip 6 column of section 1 is the local computation. For the hosted files the host sent 0.04 % more than that computation for the `.f4` arrays, 1.2 % more for JSON and 1.4 % more for HTML and JavaScript.

The evidence page: the hosted `evidence.html` (three sites) is 3,766,457 bytes stored and 973,742 sent. Built from the published set of 20 sites with the web code of `main`, the page is 25,293,702 bytes, and 6,297,933 bytes after gzip 6.
