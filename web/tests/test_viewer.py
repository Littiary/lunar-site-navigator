"""Static checks of the interactive viewer (web/viewer).

Done when (Task 7): every number comes from the package and the browser computes none.
These tests enforce the rule in the source: the package loader and the 2-D viewer contain
no trigonometric or other numerical functions, and the 3-D view uses trigonometry only in
its marked display transform (angle to screen direction). They also pin the one external
script (three.js) to an exact version on an allowed host.

The behaviour in a browser (horizon line against the package profile, phone layout) is
checked by hand with the steps in web/README.md.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "viewer"
NUMERIC = re.compile(r"Math\.(sin|cos|tan|asin|acos|atan|atan2|sqrt|cbrt|pow|exp|log|log10|log2|hypot|sinh|cosh|tanh)\b")


def strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(line.split("//")[0] if "//" in line and "http" not in line else line for line in source.splitlines())


class LinkDefaultsTests(unittest.TestCase):
    def test_a_link_without_a_height_opens_the_default_height(self):
        # Number(null) is 0, which is a valid index (the 0 m row); a missing h must not become it.
        code = strip_comments((VIEWER / "js" / "viewer.js").read_text(encoding="utf-8"))
        self.assertNotIn('Number(params.get("h"))', code)
        self.assertIn('hParam === null', code)


class NoScienceInTheBrowserTests(unittest.TestCase):
    def test_loader_and_2d_viewer_use_no_numerical_functions(self):
        for name in ("package.js", "panel.js", "viewer.js", "compare.js", "sky.js"):
            code = strip_comments((VIEWER / "js" / name).read_text(encoding="utf-8"))
            self.assertEqual(NUMERIC.findall(code), [], name)

    def test_3d_view_uses_trigonometry_only_in_the_display_transform(self):
        source = (VIEWER / "js" / "view3d.js").read_text(encoding="utf-8")
        start, end = source.index("// display-transform:start"), source.index("// display-transform:end")
        outside = strip_comments(source[:start] + source[end:])
        # Math.PI for drawing a round marker is not a computation of a value.
        self.assertEqual(NUMERIC.findall(outside), [])
        inside = source[start:end]
        self.assertTrue(NUMERIC.findall(inside))  # the transform is where it should be

    def test_no_value_is_interpolated(self):
        for name in ("panel.js", "viewer.js", "compare.js", "sky.js", "view3d.js", "calendar.js"):
            code = strip_comments((VIEWER / "js" / name).read_text(encoding="utf-8")).lower()
            self.assertNotIn("interpolat", code, name)


class ExternalResourceTests(unittest.TestCase):
    def test_nothing_is_loaded_from_outside(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"https?://[^\s\"'<>)]+", html), [])
        self.assertIn('"three": "./vendor/three/three.module.js"', html)
        for name in ("package.js", "panel.js", "viewer.js", "compare.js", "sky.js", "view3d.js", "calendar.js"):
            code = (VIEWER / "js" / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"""(?:from|import)\s*\(?\s*["'](https?:[^"']+)""", code), [], name)

    def test_compare_page_loads_nothing_from_outside(self):
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"https?://[^\s\"'<>)]+", html), [])

    def test_pages_read_the_package_index_and_the_notice_through_site_file_url(self):
        # Runtime resolution is tested in test_runtime.SiteFileUrlTests; here only that no page
        # falls back to a page-relative path, which breaks the copies at the site root.
        for name in ("viewer.js", "compare.js"):
            code = (VIEWER / "js" / name).read_text(encoding="utf-8")
            self.assertIn('siteFileUrl("packages/index.json")', code, name)
            self.assertIn('siteFileUrl("notice.json")', code, name)
            self.assertNotIn('"../packages/index.json"', code, name)
            self.assertNotIn('"../notice.json"', code, name)


class SplitScreenTests(unittest.TestCase):
    """Task 7 split screen: two sites, one shared time, values from the packages."""

    def test_two_panes_share_one_time_control(self):
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('class="pane"'), 2)
        for control in ('id="play"', 'id="speed"', 'id="date"', 'id="slider"'):
            self.assertEqual(html.count(control), 1, control)

    def test_each_pane_uses_the_sample_of_its_own_package(self):
        code = (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")
        self.assertIn("nearestSample(site, et)", code)
        self.assertIn("sampleUtc(site, i)", code)


class SkyPanoramaTests(unittest.TestCase):
    """Task 7 C: the 360° sky panorama is a tab of the single-site viewer."""

    def test_viewer_has_a_sky_tab_and_panel(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        for needle in ('id="tab-sky"', 'id="panel-sky"', 'id="sky"', 'id="sky-span"', 'id="check-sky"'):
            self.assertIn(needle, html)

    def test_paths_follow_the_package_window_and_horizon_is_checked(self):
        code = (VIEWER / "js" / "sky.js").read_text(encoding="utf-8")
        self.assertIn("_visible`", code)          # path style from the package window, not a threshold
        self.assertIn("containing(", code)
        self.assertIn("check()", code)            # drawn horizon read back against the package
        self.assertNotIn("fraction[j] >", code)   # no threshold applied to a package value


class SkyInComparisonTests(unittest.TestCase):
    """Task 7 C in the split screen: one panorama module, one instance per pane, shared time."""

    def test_compare_reuses_the_panorama_module(self):
        code = (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")
        self.assertIn('from "./sky.js"', code)
        self.assertIn("createSky(pane.q(\"sky\")", code)
        self.assertNotIn("getContext(", code)  # no second drawing implementation

    def test_compare_has_a_shared_view_switch(self):
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        for needle in ('id="view-chart"', 'id="view-sky"', 'id="sky-span"', 'data-role="sky"', 'data-role="band"'):
            self.assertEqual(html.count(needle), 1, needle)

    def test_band_comes_only_from_package_windows(self):
        code = (VIEWER / "js" / "sky.js").read_text(encoding="utf-8")
        self.assertIn("_visible_uncertain", code)
        self.assertIn("assumption", code)          # SPEC 5.7: the assumption is shown with the band
        self.assertNotIn("dem_height_error_m", code)  # no band computed from the stated error
        self.assertNotIn("horizon_error_deg", code)


class GroundViewTests(unittest.TestCase):
    """Task 8 B: three.js stored locally, WebGL fallback, ring from package fields only."""

    def test_vendored_three_js_is_the_recorded_file(self):
        import hashlib
        folder = VIEWER / "vendor" / "three"
        readme = (folder / "README.md").read_text(encoding="utf-8")
        for name in ("three.module.js", "LICENSE"):
            digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            self.assertIn(digest, readme, name)
        code = (folder / "three.module.js").read_text(encoding="utf-8")
        self.assertIn("REVISION = '160'", code)
        self.assertEqual(re.findall(r"^\s*import\s.*?from\s+['\"]", code, flags=re.M), [])  # self-contained

    def test_webgl_is_checked_before_the_renderer_starts(self):
        code = (VIEWER / "js" / "view3d.js").read_text(encoding="utf-8")
        self.assertLess(code.index("webglAvailable()) throw"), code.index("new THREE.WebGLRenderer"))
        viewer = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn("without WebGL", viewer)

    def test_ring_colours_come_from_the_package_distance(self):
        code = (VIEWER / "js" / "view3d.js").read_text(encoding="utf-8")
        self.assertIn("distanceColor(next.distance ? next.distance[k % n]", code)
        panel = (VIEWER / "js" / "panel.js").read_text(encoding="utf-8")
        self.assertIn("m.horizon.distance_m", panel)

    def test_display_settings_do_not_touch_geometry_or_add_an_atmosphere(self):
        code = strip_comments((VIEWER / "js" / "view3d.js").read_text(encoding="utf-8"))
        # No haze or fog: the Moon has no atmosphere.
        self.assertNotIn("Fog", code)
        self.assertNotIn("fog", code)
        # Display settings change light, exposure and colour only, never positions.
        start, end = code.index("function applyDisplay()"), code.index("function slopeColors(")
        apply = code[start:end]
        for word in ("position", "terrainGeometry", "eyeY", "horizon"):
            self.assertNotIn(word, apply)
        # Both lighting modes exist and can be switched by the reader.
        self.assertIn("physical:", code)
        self.assertIn("enhanced:", code)
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        for control in ('id="toggle-lighting"', 'id="toggle-slope"', 'id="toggle-edges"', 'id="reset-view"'):
            self.assertIn(control, html)

    def test_labels_keep_a_fixed_screen_size(self):
        code = strip_comments((VIEWER / "js" / "view3d.js").read_text(encoding="utf-8"))
        # Labels are HTML placed at projected positions, not sprites that scale with the zoom.
        self.assertNotIn("Sprite", code)
        self.assertIn(".project(camera)", code)
        css = (VIEWER / "viewer.css").read_text(encoding="utf-8")
        self.assertIn(".label3d", css)
        self.assertIn(".marker3d", css)
        # Markers are a fixed number of pixels; the bodies keep their package angular radius.
        self.assertIn("radiusAt(SKY_R, Number.isFinite(body.r) ? body.r : 0.25)", code)

    def test_overlay_folds_and_keeps_the_package_values(self):
        code = strip_comments((VIEWER / "js" / "view3d.js").read_text(encoding="utf-8"))
        # A real button with its state for keyboard, touch and screen readers.
        self.assertIn('hudToggle.type = "button"', code)
        self.assertIn('"aria-expanded"', code)
        self.assertIn('"aria-controls"', code)
        # Folded on narrow screens; the full text opens below the view there.
        self.assertIn("let hudOpen = container.clientWidth >= NARROW", code)
        self.assertIn('insertAdjacentElement("afterend", hudBelow)', code)
        # Moves off the Sun and the Earth on wider screens.
        self.assertIn("function placeHud(w, h)", code)
        # The full overlay is still the package text, built by ground.js (shared by both pages).
        self.assertIn("hudBody.innerHTML = next.hud", code)
        ground = (VIEWER / "js" / "ground.js").read_text(encoding="utf-8")
        for text in ("earth_view record", "g.earthView.status", "_visible</code>", "hudSummary"):
            self.assertIn(text, ground)

    def test_missing_newer_fields_are_named_not_invented(self):
        viewer = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        for field in ("horizon.obstacles", "timeline.blockers", "lit_fraction", "elevation_lower_deg"):
            self.assertIn(field, viewer)


class MoonGlobeTests(unittest.TestCase):
    """Task 8 A: distant Moon globe from package vectors, local texture, WebGL fallback."""

    def source(self, name):
        return (VIEWER / "js" / name).read_text(encoding="utf-8")

    def test_trigonometry_only_in_the_display_transform(self):
        code = self.source("globe.js")
        start, end = code.index("// display-transform:start"), code.index("// display-transform:end")
        self.assertEqual(NUMERIC.findall(strip_comments(code[:start] + code[end:])), [])
        self.assertNotIn("interpolat", strip_comments(code).lower())

    def test_vectors_come_from_the_packages(self):
        viewer = self.source("viewer.js")
        self.assertIn("table.manifest.positions_km", self.source("ground.js") + viewer)  # Sun and Earth vectors
        self.assertIn("manifest.site.position_km", viewer)         # site markers
        self.assertIn("directionTableFor(", viewer)
        self.assertIn("loadDirectionTable(", self.source("ground.js"))
        self.assertNotIn("Math.round((et - grid.start_et_s) / grid.step_s) +", viewer)  # nearest record, no blending

    def test_webgl_is_checked_first(self):
        code = self.source("globe.js")
        self.assertLess(code.index("webglAvailable()) throw"), code.index("new THREE.WebGLRenderer"))

    def test_texture_is_the_recorded_nasa_file(self):
        import hashlib
        folder = VIEWER / "vendor" / "moon"
        readme = (folder / "README.md").read_text(encoding="utf-8")
        digest = hashlib.sha256((folder / "lroc_color_2k.jpg").read_bytes()).hexdigest()
        self.assertIn(digest, readme)
        self.assertIn("https://svs.gsfc.nasa.gov/4720/", readme)
        self.assertIn('"../vendor/moon/lroc_color_2k.jpg"', self.source("globe.js"))

    def test_unavailable_fields_are_named(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        self.assertIn("Not available in the packages, so not shown", html)
        self.assertIn('id="tab-globe"', html)

    def test_clustered_site_labels_are_click_targets(self):
        code = self.source("globe.js")
        # Markers and labels are buttons: mouse, touch and keyboard (Tab, Enter) all pick the site.
        self.assertIn('const dot = el("button", "globe-site")', code)
        self.assertIn('const lab = el("button", "globe-label", s.name)', code)
        self.assertIn('dot.addEventListener("click", pick)', code)
        self.assertIn('lab.addEventListener("click", pick)', code)
        # Crowded markers get their labels further out, with a leader line to their own marker.
        self.assertIn("const crowded =", code)
        self.assertIn('s.leader.style.display = ""', code)

    def test_whole_moon_fits_and_no_arrows(self):
        code = self.source("globe.js")
        start, end = code.index("// display-transform:start"), code.index("// display-transform:end")
        self.assertIn("function fitDistance(", code[start:end])
        self.assertIn("orbit.dist = fitDistance(", code)
        self.assertNotIn("ArrowHelper", code)
        self.assertNotIn("Sprite", code)  # labels are HTML at a fixed screen size
        # The light and the sub-points still follow the package vectors.
        self.assertIn("sunLight.position.copy(sunDir)", code)
        self.assertIn("anchor.position.copy(d).multiplyScalar(1.002)", code)


class CsvExportTests(unittest.TestCase):
    def test_single_viewer_exports_package_series(self):
        code = (VIEWER / "js" / "csv.js").read_text(encoding="utf-8")
        viewer = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        for field in ("utc_timestamp", "sample_index", "et_s", "site_id", "package_id",
                      "observer_height_m", "azimuth_deg", "elevation_deg", "margin_deg", "visible_fraction"):
            self.assertIn(field, code)
        self.assertIn("seriesCsv([{ site: state.site, data: state.data, height: state.h }])", viewer)
        self.assertIn('id="export-csv"', (VIEWER / "index.html").read_text(encoding="utf-8"))

    def test_comparison_exports_both_selected_sites(self):
        code = (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertIn("seriesCsv(state.panes.map", code)
        self.assertIn("lunar-site-comparison-sun-earth.csv", code)
        self.assertIn('id="export-csv"', html)

    def test_csv_preserves_missing_values_and_excel_compatibility(self):
        code = (VIEWER / "js" / "csv.js").read_text(encoding="utf-8")
        self.assertIn('? "" : String(value)', code)
        self.assertIn('Blob(["\\ufeff", text]', code)
        self.assertIn("\\r\\n", code)
        self.assertIn('text.replace(/"/g, \'""\')', code)


class Contract06ViewerTests(unittest.TestCase):
    def test_viewer_reads_contract_06_package_fields(self):
        package = (VIEWER / "js" / "package.js").read_text(encoding="utf-8")
        panel = (VIEWER / "js" / "panel.js").read_text(encoding="utf-8")
        viewer = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn("loadSitePairs", package)
        for field in ("calendar", "height_trade", "opportunities", "uncertainty", "blockers"):
            self.assertIn(field, panel)
        self.assertIn("contract06Html", viewer)

    def test_comparison_reads_published_site_pairs(self):
        code = (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertIn('p.kind === "site_pairs"', code)
        self.assertIn("gain_over_better_s", code)
        self.assertIn('id="pair-results"', html)


class GlobeResourceTests(unittest.TestCase):
    """The globe rebuilds its markers only when the sites change and frees the old ones.
    Measured in a browser as well (no new label canvases while stepping through time)."""

    def test_markers_are_disposed_and_rebuilt_only_on_change(self):
        code = (VIEWER / "js" / "globe.js").read_text(encoding="utf-8")
        body = code[code.index("function disposeMarkers()"):code.index("function setSites(")]
        for call in ("s.dot.remove()", "s.label.remove()", "s.leader.remove()", "sites = []"):
            self.assertIn(call, body)
        self.assertIn("disposeMarkers();", code[code.index("function setSites("):])
        self.assertIn("if (key !== sitesKey)", code)

    def test_viewer_builds_the_site_list_once(self):
        code = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        update = code[code.index("async function updateGlobe()"):code.index("async function openGroundView(")]
        self.assertNotIn(".map(", update.split("const t = await directionTable();")[1].split("let sun")[0])
        self.assertIn("const sites = state.globeSites;", update)

    def test_sites_behind_the_moon_cannot_be_picked(self):
        code = (VIEWER / "js" / "globe.js").read_text(encoding="utf-8")
        # A marker (and its label) is hidden, so it cannot be clicked, unless its point on the
        # sphere faces the camera, or when it is outside the frame.
        self.assertIn("const facing = (n) => n.dot(camera.position) > 1;", code)
        self.assertIn("s.dot.hidden = s.label.hidden = !on;", code)
        self.assertIn("s.screen.x < 0 || s.screen.x > w", code)


class ComparisonInteractionTests(unittest.TestCase):
    """P6: the shared timeline, the site selectors and the links keep the choices of the reader."""

    def source(self, name):
        return (VIEWER / "js" / name).read_text(encoding="utf-8")

    def test_only_the_latest_site_or_height_choice_of_a_pane_is_applied(self):
        code = self.source("compare.js")
        self.assertIn("const token = (pane.loading = (pane.loading || 0) + 1)", code)
        self.assertGreaterEqual(code.count("if (token !== pane.loading) return"), 3)

    def test_changing_a_site_keeps_the_height_in_metres(self):
        code = self.source("compare.js")
        self.assertIn("hz.observer_heights_m.indexOf(keepMetres)", code)
        self.assertIn("setSite(pane, Number(ev.target.value), null, metres)", code)

    def test_steps_and_speed_follow_the_package_time_grid(self):
        code = self.source("compare.js")
        self.assertIn("reference().timeline.time.step_s", code[code.index("function samplesFor("):])
        self.assertIn('samplesFor(Number($("speed").value))', code)
        self.assertIn("samplesFor(Number(b.dataset.step))", code)

    def test_links_carry_site_height_and_time(self):
        self.assertIn('$("viewer-link").href = v.href', self.source("compare.js"))
        self.assertIn('$("compare-link").href = c.href', self.source("viewer.js"))
        self.assertIn('id="viewer-link"', (VIEWER / "compare.html").read_text(encoding="utf-8"))
        self.assertIn('id="compare-link"', (VIEWER / "index.html").read_text(encoding="utf-8"))

    def test_every_pair_window_field_is_shown(self):
        code = self.source("compare.js")
        pairs = code[code.index("function renderPairs()"):]
        for field in ("w.a_s", "w.b_s", "w.either_fraction", "w.both_s", "w.neither_s", "w.longest_neither_s",
                      "w.gain_over_better_s", "w.covered_share_of_better_outage", "state.pairs.time", "state.pairs.warnings"):
            self.assertIn(field, pairs)
        self.assertIn("no outage", pairs)  # null share (SPEC 6a) is not shown as 0 %


class OpportunityCalendarWiringTests(unittest.TestCase):
    """Task 9: reachable from the existing controls; selects and formats package values only."""

    def test_reachable_from_both_pages(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="tab-calendar"', html)
        self.assertIn('id="panel-calendar"', html)
        compare = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertIn('id="view-calendar"', compare)
        self.assertIn('id="calendar-section"', compare)
        self.assertIn('const VIEWS = ["chart", "sky", "ground", "calendar"];', (VIEWER / "js" / "compare.js").read_text(encoding="utf-8"))

    def test_reads_the_manifest_only_and_computes_no_visibility(self):
        code = strip_comments((VIEWER / "js" / "calendar.js").read_text(encoding="utf-8"))
        self.assertEqual(NUMERIC.findall(code), [])
        self.assertNotIn("interpolat", code.lower())
        self.assertNotIn(".array(", code)           # no array files are read for the calendar
        self.assertNotIn("loadSiteData", code)
        for field in ("timeline.calendar", "calendar.periods", "quantities", "values[e.h]", "opportunities", "feasible_s_per_period",
                      "landing_windows_et_s", "planned_landing", "requirements", "methodStatus"):
            self.assertIn(field, code)


class HomePageTests(unittest.TestCase):
    """Kaan's jury review: first impression, status first, details on demand, 0.11 support."""

    def page(self):
        return (VIEWER / "compare.html").read_text(encoding="utf-8")

    def code(self):
        return (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")

    def test_names_the_product_and_says_what_it_does(self):
        html = self.page()
        self.assertIn("<h1>Lunar Site Navigator</h1>", html)
        self.assertIn('class="lead"', html)
        self.assertIn('id="validation-note"', html)
        self.assertIn('id="load-status" role="status"', html)  # visible at once, before any package

    def test_validation_note_replaces_the_banner_and_states_the_card(self):
        code = self.code()
        self.assertIn("validationNoteHtml(noticeFile,", code)
        self.assertNotIn('$("notice").textContent = notice', code)  # the red box is for synthetic data only
        panel = (VIEWER / "js" / "panel.js").read_text(encoding="utf-8")
        note = panel[panel.index("export function validationNoteHtml("):]
        for needle in ("v.passed", "v.checks", "v.failed", "not_validated", "Evidence and limits"):
            self.assertIn(needle, note)

    def test_status_cards_first_and_details_behind_a_control(self):
        html = self.page()
        self.assertLess(html.index('data-role="cards"'), html.index('data-role="chart"'))
        start = html.index('<details class="details" data-role="details">')
        details = html[start:html.index("</details>", start)]
        for role in ("readout", "summary", "events", "countdown", "footer"):
            self.assertIn(f'data-role="{role}"', details)

    def test_progressive_loading_of_the_two_selected_sites_only(self):
        code = self.code()
        self.assertEqual(code.count("await loadSite("), 1)          # only in setSite, for one pane
        self.assertIn("loadSiteSummary(state.summaries, entry", code)
        self.assertIn("loadSiteData(summary, pane.h, { lean: true })", code)
        self.assertIn("Promise.all(loads)", code)                    # the two panes in parallel
        pkg = (VIEWER / "js" / "package.js").read_text(encoding="utf-8")
        self.assertIn("digest !== entry.sha256", pkg)               # summaries are checked
        self.assertIn("manifest.summary_of.package_id !== indexEntry.package_id", pkg)

    def test_initial_sites_come_from_the_published_pairs(self):
        self.assertIn("const pair = state.pairs && state.pairs.pairs[0];", self.code())

    def test_ground_view_is_a_pane_view_with_the_same_renderer(self):
        html, code = self.page(), self.code()
        self.assertIn('id="view-ground"', html)
        self.assertIn('"three": "./vendor/three/three.module.js"', html)
        self.assertIn('await import("./view3d.js")', code)
        self.assertIn("groundInput({", code)


class PairMetricsTests(unittest.TestCase):
    def test_pair_metrics_name_their_heights_and_status(self):
        code = (VIEWER / "js" / "compare.js").read_text(encoding="utf-8")
        pairs = code[code.index("function renderPairs()"):]
        for needle in ("observer_height_m", "validation.status", "entry.package_id !== view.id"):
            self.assertIn(needle, pairs)
        self.assertNotIn("w.distance_m || pair.distance_m", pairs)


if __name__ == "__main__":
    unittest.main()
