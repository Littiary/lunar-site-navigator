# Requirement presets

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
