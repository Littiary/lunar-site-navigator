# Lunar Site Navigator

![Shackleton crater rim crest and de Gerlache crater rim crest side by side on 28 July 2027: on the left the Sun sets behind a ridge, on the right it stays up](docs/media/two_sites.gif)

<sub>Shackleton crater rim crest (left) and de Gerlache crater rim crest (right), 40 km apart, from 16:35 to 19:58 UTC on 28 July 2027, observer 2 m above the ground: on the left the Sun sets behind a ridge, on the right it stays up. A 5.9 s cut of the pitch video, a real render of the Unreal planner reading the result packages (packages of contract 0.11 at the time of the render; see [docs/unreal/pitch/README.txt](docs/unreal/pitch/README.txt)).</sub>

[![Live site](https://img.shields.io/badge/live_site-open-2ea44f)](https://littiary.github.io/lunar-site-navigator/)
[![Slides PDF](https://img.shields.io/badge/slides-PDF-1f6feb)](https://littiary.github.io/lunar-site-navigator/submission/Lunar_Site_Navigator_backup_slides.pdf)
[![Validation card: 31 of 32 checks pass](https://img.shields.io/badge/validation-31_of_32_pass,_1_fails-yellowgreen)](validation/card/validation_card.md)
[![Licence: Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-blue)](LICENSE)
[![Tests: pytest, run locally](https://img.shields.io/badge/tests-pytest,_run_locally-lightgrey)](#how-to-run)

Team **Kestro Aerospace** (Kaan Eşrefoğlu, Barkın Kocatepe) · NASA Space Apps Challenge 2026, Aachen.
Challenge: *Lunar Landing Site Navigator*.

At the lunar south pole the Sun stays within a few degrees of the horizon, so a ridge a few hundred metres away can decide whether a lander has power. Lunar Site Navigator computes, for any point on the Moon, the 360° terrain horizon from NASA LOLA elevation data and the directions of the Sun and the Earth with NASA SPICE, and reports when each is visible, which terrain blocks it and how many hours that costs. Twenty sites are published as versioned result packages with checksums, read by a web viewer and an Unreal Engine planner, and every comparison with an outside source is on a validation card: 31 of 32 checks pass, and the one that fails stays on the card.

**Try it:** https://littiary.github.io/lunar-site-navigator/ &nbsp;·&nbsp; **Slides:** [Lunar_Site_Navigator_backup_slides.pdf](https://littiary.github.io/lunar-site-navigator/submission/Lunar_Site_Navigator_backup_slides.pdf) &nbsp;·&nbsp; **Architecture:** [docs/architecture.md](docs/architecture.md)

## Key figures

| Figure | Value | Where it comes from |
|---|---|---|
| Published sites | 20: three south-polar project sites, four more sites on the LOLA polar products (Chandrayaan-3, IM-1, IM-2, a point in an Artemis III candidate region), thirteen sites on the 118 m model (Apollo, Surveyor, Chang'e, SLIM, Blue Ghost Mission 1) | [packages/README.md](packages/README.md) |
| One ridge at the Shackleton rim (observer 2 m, 14 Nov 2026 to 14 Nov 2028, LOLA 5 m site model near the site) | 673 m away, costs 373 h of sunlight: 31 % of all the sunlight the site loses to terrain | Shackleton package, `timeline.blockers`; [validation/sites/results/site_summary.md](validation/sites/results/site_summary.md) |
| Spread of the Sun's return at the Shackleton rim for the stated height error (observer 2 m, 14 Nov to 14 Dec 2026) | 74.1 h on the LOLA 20 m product; 1.8 h with the LOLA 5 m site model | [docs/method/near_field.md](docs/method/near_field.md), section 4 |
| Directions of the Sun and the Earth against JPL Horizons (95,676 rows) | 0.005″ computed directly; 0.1″ through the direction table the packages use | validation card |
| Sunrise and sunset on a smooth sphere against JPL Horizons | within the one-minute steps of the reference (largest 57 s) | validation card |
| Eclipse of March 2025 at the Blue Ghost Mission 1 site against the contact times predicted by Firefly | 0.83 min (not blind) | validation card |
| Sun and Earth angles at six Apollo landings (48 published angles) | 0.047° (not blind) | validation card |
| Validation card | 32 checks: 31 pass, 1 fails (sunlit and shadowed ground along an LROC image strip: 89.6 % against a required 90 %) | [validation/card/validation_card.md](validation/card/validation_card.md) |

## What it does

Lunar Site Navigator compares landing sites and dates on one screen. For any point on the Moon it reports when the Sun and the Earth are visible, which terrain blocks them, how many hours that costs, and how far a landing date can slip. At the seven south-polar sites every rise and set time also carries an uncertainty band.

- **Compare** two sites at a chosen time: Sun and Earth visible or hidden, and the time until each rises or sets.
- **Explain** a result: the stretch of terrain that hides the Sun, its distance and direction, and the hours of sunlight it costs.
- **Plan** dates: a 24-month calendar of sunlight and Earth visibility per site, the landing windows that meet a stated requirement, and how many days a planned landing can slip.
- **State the uncertainty**: at the polar sites, and for a new coordinate by default, each rise and set time has a band that follows from a stated two-sigma height error of the terrain model. The 13 sites on the 118 m model have none, because no height error has been measured for that model.
- **Show what to change**: the effect of raising a mast and, at the three project sites, of landing elsewhere inside a 100 m landing circle.
- **Any coordinate**: twenty sites are published, from Apollo 11 to a point in an Artemis III candidate region. A new coordinate is computed in 10 to 20 seconds for a 30-day window on a laptop:

```
python -m lsncore custom --lat -85.3 --lon 31.2 --start 2026-11-15T00:00:00Z --out my-site
```

![Two sites side by side in the planner view](docs/unreal/pitch/b_product_two_sites.png)

![The ridge that hides the Sun, with its cost in hours](docs/unreal/pitch/c_key_moment_near_ridge.png)

At the Shackleton crater rim, for a sensor 2 m above the ground, a ridge 673 m away costs 373 hours of sunlight in two years: 31 % of everything the site loses to terrain, on NASA's 5 m site model. Moving a few metres changes such numbers, which is why the tool shows them.

## How it works

One science core in Python (`core/`) computes everything and writes versioned result **packages** with checksums (`packages/`, described by the contract in [docs/contract/SPEC.md](docs/contract/SPEC.md)). The web view (`web/`) and the Unreal Engine scene (`unreal/`) read those packages; neither computes a science result. They look values up and count down to the published times. The diagram and one paragraph per part are in [docs/architecture.md](docs/architecture.md).

- The horizon is traced on the sphere out to 300 km in every direction.
- The Sun is a disc, so a partial sunrise counts as sunlight.
- Terrain: LOLA 5 m site models at two of the three project sites (Shackleton rim and de Gerlache rim; at Malapert the 5 m model failed its seam check against the 20 m product, so the 20 m product is used), the LOLA 20 m and 60 m polar products near the poles, and SLDEM2015 at 118 m per pixel elsewhere (LOLA merged with Kaguya Terrain Camera data).
- Directions of the Sun and the Earth: SPICE with the DE440 ephemeris, light time and stellar aberration included.

Method notes: [docs/method/](docs/method/).

## Why the numbers can be trusted

For every comparison with an outside source, the pass criterion was committed before the comparison was run; the git history shows the order. Two of the rows below, the eclipse and the Apollo angles, were not blind: earlier research had already compared some of the published values with Horizons, and the card says so. The validation card ([validation/card/validation_card.md](validation/card/validation_card.md)) has 32 checks: 31 pass and 1 fails, and the failed one stays on the card.

| What is computed | Checked against | Largest difference |
|---|---|---|
| Directions of the Sun and the Earth | JPL Horizons, 95,676 rows | 0.005 arcseconds computed directly; 0.1 arcseconds through the direction table the packages use |
| Sunrise and sunset on a smooth sphere | JPL Horizons rise and set tables | within the one-minute steps of the reference (largest 57 s) |
| Eclipse of March 2025 at the Blue Ghost site | contact times predicted by Firefly | 0.83 minutes |
| Sun and Earth angles at six Apollo landings | 48 published angles | 0.047° |
| Sunlit and shadowed ground in an LRO image | LROC camera image strip | 89.6 % agreement against a required 90 %: **fails** |

The terrain model has its own acceptance checks ([data/checkpoints/](data/checkpoints/)):

- Height of the global models (SLDEM2015 118 m and LDEM_128 237 m) against the five Apollo and Lunokhod laser retroreflectors: within 7 m. This is the one height check that does not depend on LOLA.
- Height against 148,091 of the LOLA laser returns the 20 m product was built from: within 3.8 m for 95 % of points. This is a lower bound of its error, not an independent test.
- Position against 192 catalogued craters: an offset of 32 m and a rotation of −0.013°.

Checks that failed as written are kept with their cause, in [data/checkpoints/](data/checkpoints/) and [data/notes/](data/notes/).

## Limits

- Outside the polar products the terrain is 118 m per pixel, so relief narrower than about 240 m is not resolved and nearby obstacles of that size cannot be shown.
- All terrain is LOLA or, between 60° S and 60° N, SLDEM2015, which merges LOLA with Kaguya Terrain Camera data. The one independent height check is the five retroreflectors; two LROC images test lit and shadowed ground (one agrees, one fails).
- Event times on real terrain have no independent reference. The validation card lists what is not validated.
- The landing requirement shown in the views is an example chosen by the team, not a mission requirement.
- Known limit of the 118 m product near 90° E, 48° S: [data/notes/known_limit_sldem_step_90e_48s.md](data/notes/known_limit_sldem_step_90e_48s.md).

## Known limits and next steps

These are written and tested in the science core or proposed, but not yet in the published packages or not yet decided. They are the next steps, in this order.

1. **Publish the core additions that are ready.** The core on the `core` branch already writes them; the packages in `packages/` were made before them and do not carry them:
   - flags on a rise or set time whose uncertainty range is cut off by the start or the end of the computed time range (`earliest_clipped`, `latest_clipped`);
   - "cannot be judged" instead of a number where a landing window is shorter than the mission (`feasible_fraction` and `latest_landing` left empty, with a warning);
   - a flag where the longest stretch without the Sun or the Earth runs into the start or the end of the computed time range and is therefore a lower bound (`<body>_longest_outage_is_lower_bound`).
2. **Package id.** The id of a package depends on the request and the data versions. It should also depend on the ground-station kernels (today a separate kernel group with its own id) and on the quality layers of the elevation model (the RMS error maps of the 5 m site models that feed the uncertainty band).
3. **Validator.** The contract validator checks structure, types and the checksum of every array. It should also check value ranges (angles, fractions), that windows are ordered and do not overlap, and that every index into an array is inside it.
4. **Runtime limits apart from correctness tests.** A few core tests have wall-clock limits that fail on a slow or busy machine while the results are right. A proposal to move them into a separate runtime check is written but not applied: [docs/method/runtime_checks_proposal.md](https://github.com/Littiary/lunar-site-navigator/blob/core/docs/method/runtime_checks_proposal.md) (on the `core` branch).
5. **Localisation.** All text in the views is English. Units, dates and labels are not yet prepared for other languages.

## Layout

| Folder | Content |
|---|---|
| `core/` | Science core (Python): horizon, ephemeris, event finding. Writes versioned result packages. |
| `data/` | Download and processing scripts for NASA data. No raw data is committed. |
| `validation/` | Comparisons with independent sources and the validation card. |
| `packages/` | The published result packages: 20 sites, a direction table and a site-pairs package. |
| `web/` | Charts, evidence page and viewers. They read packages and compute no science result. |
| `unreal/` | Unreal Engine scene and planner interface. It reads packages and computes no science result. |
| `docs/` | Contract, architecture, method notes, pictures. |

## How to run

```
git clone https://github.com/Littiary/lunar-site-navigator.git
cd lunar-site-navigator
python scripts/bootstrap.py --test
```

This creates the Python environment (`.venv` in the checkout), installs the packages, downloads the SPICE kernels, the default LOLA products (south-polar 20 m and 60 m, and LDEM_16) and the validation inputs to a data folder outside the repository (`LSN_DATA_ROOT`), checks every download against a committed checksum and runs the tests against the committed results. Regenerating the published packages needs further downloads and one more command, described in [packages/README.md](packages/README.md). Options, the same steps as single commands, sizes and limits are in [docs/setup.md](docs/setup.md).

With that environment active:

```
python -m lsncore validate packages/index.json packages/direction_table/* packages/site/*/* packages/site_pairs/*
python -m lsncore custom --lat -85.3 --lon 31.2 --start 2026-11-15T00:00:00Z --out my-site
```

`validate` checks every published package against the contract, including the checksum of every array; `custom` computes a new coordinate. The Unreal planner is built and run with the scripts described in [unreal/README.md](unreal/README.md).

**Contributing.** The working rules (one science core, viewers read packages and compute nothing, thresholds written before measuring, credits in the same commit) are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Data and credits

Every third-party dataset, library and asset is listed with its licence and source in [CREDITS.md](CREDITS.md). To cite this work, see [CITATION.cff](CITATION.cff).

## Use of AI

Parts of the code and documentation in this repository were written with AI coding assistants. The team defines the scope, chooses the data, writes the acceptance thresholds and reviews every change. Details are recorded in [CREDITS.md](CREDITS.md).

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
