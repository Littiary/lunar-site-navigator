# Working rules

These rules apply to everyone who changes this repository, people and AI assistants alike.

## Architecture

1. One science core computes every number and writes it to a versioned **package**. Viewers (web, Unreal) only read packages. No science in the browser or in the engine.
2. The package format is the **contract**. Only the core stream changes it. If you need a new field, ask for it; do not add it yourself.
3. Each stream owns its folder (`core/`, `data/`, `web/`, `unreal/`, `docs/`). Do not edit another stream's files.

## Quality

4. **Test first.** Write the acceptance test for a task before the implementation. A task is finished when its test is green, not before.
5. **Thresholds are written before measuring** and are never edited to make a test pass. Reference ("golden") files are never edited by hand or by an assistant.
6. **Every external number is fetched from its primary source during the hackathon** and stored with the query, the source URL and the retrieval time. Do not copy numbers from notes, memory or earlier drafts.
7. Every number shown to a user carries its method, reference frame, time scale and data version.
8. Mark anything unverified as "unverified". Do not present an estimate as a result.

## Compliance

9. Every third-party dataset, library or asset gets a row in `CREDITS.md` in the same commit that introduces it. Only material that is freely and publicly available or under an OSI-approved licence.
10. No raw NASA data, kernels or large binaries in git; scripts download them.
11. All text in the repository is English.
12. Do not write "first", "only" or "NASA-approved". No NASA logo or mission insignia.
13. No AI-generated images or video.

## Git

14. Work on a branch; `main` only receives changes whose tests are green and that have been reviewed.
15. Small commits with a clear message that says what changed and why.
