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
        for name in ("panel.js", "viewer.js", "compare.js", "sky.js", "view3d.js"):
            code = strip_comments((VIEWER / "js" / name).read_text(encoding="utf-8")).lower()
            self.assertNotIn("interpolat", code, name)


class ExternalResourceTests(unittest.TestCase):
    def test_nothing_is_loaded_from_outside(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"https?://[^\s\"'<>)]+", html), [])
        self.assertIn('"three": "./vendor/three/three.module.js"', html)
        for name in ("package.js", "panel.js", "viewer.js", "compare.js", "sky.js", "view3d.js"):
            code = (VIEWER / "js" / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"""(?:from|import)\s*\(?\s*["'](https?:[^"']+)""", code), [], name)

    def test_compare_page_loads_nothing_from_outside(self):
        html = (VIEWER / "compare.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"https?://[^\s\"'<>)]+", html), [])

    def test_pages_read_the_package_index_and_the_notice_relative_to_the_site(self):
        for name in ("viewer.js", "compare.js"):
            code = (VIEWER / "js" / name).read_text(encoding="utf-8")
            self.assertIn('"../packages/index.json"', code, name)
            self.assertIn('"../notice.json"', code, name)


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
        self.assertIn("distanceColor(distance ? distance[k % n]", code)
        panel = (VIEWER / "js" / "panel.js").read_text(encoding="utf-8")
        self.assertIn("m.horizon.distance_m", panel)

    def test_missing_newer_fields_are_named_not_invented(self):
        viewer = (VIEWER / "js" / "viewer.js").read_text(encoding="utf-8")
        for field in ("horizon.obstacles", "timeline.blockers", "lit_fraction", "elevation_lower_deg"):
            self.assertIn(field, viewer)


if __name__ == "__main__":
    unittest.main()
