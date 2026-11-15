# Submission material: backup slides and video subtitles

Task 13 of the web stream. Rules taken from the 2026 Project Submission Guide (https://www.spaceappschallenge.org/resources/project-submission-guide/, dated 13 November 2026, read on 2026-11-15) and from the Aachen kickoff deck.

## Files

| File | What it is |
|---|---|
| `Lunar_Site_Navigator_backup_slides.pdf` | The backup presentation: **7 slides**, 16:9, English. Problem, solution, NASA data and method, verification, interactive planner, comparison with existing tools and limits. |
| `slides/slides.html`, `slides/img/` | Source of the PDF. The images are downscaled JPEG copies of existing project pictures (list below). |
| `pitch_video_subtitles_en.vtt`, `pitch_video_subtitles_en.srt` | English subtitles for the pitch video `docs/unreal/pitch/f_pitch_video_1080p60.mp4` (27.90 s, no audio), the same six cues in two formats. |

## Rules of the guide and how the material meets them

| Rule (guide, "Tips for Creating a Project Demo") | State |
|---|---|
| Demo is a video of 30 seconds or less **or** a slide deck of up to seven slides including title and intro slides; more is not eligible for Global Judging | Video: 27.90 s (ffprobe). Deck: 7 pages (counted in the PDF). |
| Slide decks must be in English; a video must have English subtitles | Deck in English. Subtitle files in English; see "Subtitles" for what is still to do. |
| Slides name the team, its members and the challenge | Slide 1. |
| Slides show an image of the project, the user experience, and how NASA and space agency open data make the solution possible | Slides 2, 3, 6 (pictures of the running project); slide 4 (NASA LOLA, SPICE, LROC; JAXA Kaguya data inside SLDEM2015). |
| Demo is hosted on an external site with a public link, no login | **Open: not done here.** Nothing was uploaded or published. See "Still to do". |
| Use of AI stated; AI-generated images or video carry a visible watermark | Slide 7 states the use of AI assistants for code and text. No picture in the deck or the video is AI-generated, so no watermark applies. |
| No NASA logos, flags or mission identifiers in generated content | None in the deck. |

## Slides: where each number and picture comes from

| Slide | Numbers | Source |
|---|---|---|
| 2 | ridge 673 m away, 373 h, 31 % | `packages/site/shackleton-rim-crest/site-689eb279e17d7879/manifest.json`, `timeline.blockers`, observer height 2 m: `peak_distance_m` 672.9, `lost_s` 1,341,948 s, `share_of_lost` 0.307 |
| 3 | 20 sites, heights 0 to 20 m, two-year window | `packages/index.json`; `horizon.observer_heights_m`; `timeline.time` |
| 4 | 300 km, six heights, seven sites with an uncertainty band | package manifests (`horizon.max_range_m`, `timeline.uncertainty`) |
| 5 | 32 checks, 31 pass, 1 fails; 25 against outside sources, 7 analytical; the six rows; reflectors within 7 m | `validation/card/validation_card.json` (rows 1, 6, 8, 20, 23, 14; groups as on the accuracy page); `data/checkpoints/llr_report.json` (largest difference 6.9 m) |
| 7 | comparison rows | `web/docs/tool_comparison/README.md` |

| Picture in `slides/img/` | Made from |
|---|---|
| `a_opening_south_pole_wide.jpg`, `b_product_two_sites.jpg`, `c_key_moment_near_ridge.jpg` | `docs/unreal/pitch/` stills of the same names (renders of the running Unreal scene from the published packages; described in `docs/unreal/pitch/README.txt`) |
| `web_compare.jpg`, `web_calendar.jpg` | crops of `web/docs/tool_comparison/screenshots/2026-11-15_lsn_compare_horizon_2027-01-04T1000Z_0m.png` and `..._lsn_compare_calendar_2m.png` (the web view, local build from the contract 0.12 packages) |

## Subtitles

The video has no speech, so the subtitles are descriptive: each cue says what its part of the video shows. Timing and content were taken from the video itself and from `docs/unreal/pitch/README.txt`:

- The cuts were measured with ffmpeg scene detection at 5.9, 11.9, 19.9 and 23.9 s and agree with the five parts listed in the README. Part 3 (8 s) has two cues.
- Sites, dates and numbers in the cues are the ones shown in the frames (Shackleton and de Gerlache, 28 July 2027; ridge 673 m away; 373 h).
- Reading rate: 14 to 21 characters per second.

Checked by burning the SRT into a temporary copy with ffmpeg (not kept): the copy has the same length, and the cues appear at the cuts.

**Known conflict.** Parts 2 and 3 of the video already carry an English caption line of the interface in the lower middle of the picture (for example "A ridge 670 m away is about to hide the Sun"). Subtitles burned in at the default position overlap that line.

## Still to do (not done in this task)

1. **Decide how the subtitles reach the viewer.** Either upload the `.srt` or `.vtt` as a caption track on the hosting platform (YouTube accepts both), or burn them in at a position that does not cover the interface captions. The video belongs to the Unreal stream; no subtitled copy was committed.
2. **Host the demo** (video or the PDF) on an external site and test the link in a private window.
3. **Proofread** the deck once more before use; it was written in one pass.

## Rebuilding the PDF

With Microsoft Edge or Chrome (headless), from this folder:

```
msedge --headless=new --no-pdf-header-footer --print-to-pdf=Lunar_Site_Navigator_backup_slides.pdf slides/slides.html
```

Each `<section>` of `slides/slides.html` is one page of 1280 × 720 px. The deck must stay at seven sections.
