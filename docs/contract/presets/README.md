# Presets

Two files: example requirements on the landing time, and stated height errors of the
terrain for the uncertainty band.

## Requirement presets

[`requirements.json`](requirements.json) holds three example requirements on the landing
time. They exist so that the viewers have something to show for the landing windows and
the slip tolerance ([SPEC](../SPEC.md), section 5.6).

**They are examples chosen by the team. They are not requirements of NASA or of any
mission.** A requirement is an input of a scenario, never a constant of the code: a user
states the one that matters, and the package echoes it in `request.timeline.requirements`.

| Id | In words |
|---|---|
| `example-standard` | Earth in view at landing; 10 Earth days of unbroken sunlight from landing |
| `example-strict` | Earth in view at landing; 14 Earth days of unbroken sunlight; Earth in view for at least half of those 14 days |
| `example-loose` | Earth in view at landing; 5 Earth days of unbroken sunlight from landing |

"Sunlight" here means that any part of the Sun's disc is above the terrain horizon
(window `sun_visible`). To ask for the eclipse-aware condition, name `sun_lit`; to ask
for visibility that survives a stated horizon error, name `sun_visible_certain`.

How to use them:

- Viewers read `requirements.json` to offer the presets by `id` and `label`, and show the
  `label` (which starts with "EXAMPLE") wherever a landing window or a slip tolerance is
  shown.
- The core puts presets into a scenario with
  `python -m lsncore scenario … --preset example-standard --preset example-strict`
  (or `--preset all`); `--requirements <file>` takes any other list of requirements.

Each entry has the form the contract defines for a requirement (`id`, `label`,
`mission_duration_s`, `conditions[]`); a test checks the file against the schema.

## Terrain height error

[`terrain_height_error.json`](terrain_height_error.json) holds the models a scenario can
state in `uncertainty.dem_height_error_model` ([SPEC](../SPEC.md), section 5.7). `default`
names the one to offer first.

| Id | In words | Source |
|---|---|---|
| `lola-two-sigma-2026-11` (default) | On the 5 m site rasters twice the producers' RMS error map at the pixel, 1 m where the map is empty; on every other product 5 m up to 30 degrees of slope, 7 m above | Measured by the data stream on 14 November 2026; the file names the reports. Every product is LOLA: errors common to all of them are not covered |
| `constant-0.5-m`, `constant-1-m`, `constant-2-m` | One number everywhere | None; illustrative |

The core puts a model into a scenario with `python -m lsncore scenario … --height-error-preset default`
(or an id); `--dem-height-error-m` states a single number instead. A viewer shows the
`label` of the model wherever a band or an earliest and latest time is shown.
