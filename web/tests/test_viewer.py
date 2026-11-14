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
        for name in ("package.js", "panel.js", "viewer.js", "compare.js"):
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
        for name in ("panel.js", "viewer.js", "compare.js", "view3d.js"):
            code = strip_comments((VIEWER / "js" / name).read_text(encoding="utf-8")).lower()
            self.assertNotIn("interpolat", code, name)


class ExternalResourceTests(unittest.TestCase):
    def test_only_a_pinned_three_js_is_loaded_from_outside(self):
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"'<>)]+", html)
        self.assertEqual(urls, ["https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"])
        for name in ("package.js", "panel.js", "viewer.js", "compare.js", "view3d.js"):
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


if __name__ == "__main__":
    unittest.main()
