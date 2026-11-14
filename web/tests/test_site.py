"""Acceptance tests for the one-command site build (lsn_web.site).

Done when: one command turns the published packages into a static folder that can be
hosted as it is (index.html, the charts as files, no Jekyll processing), and the notice
comes from a file so that it can be changed or removed without touching code.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lsn_web import charts, evidence, package, site

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INDEX = FIXTURES / "contract-sample-0.3" / "packages" / "index.json"
CARD = FIXTURES / "validation-card" / "validation_card.json"


class SiteBuildTests(unittest.TestCase):
    def build(self, tmp: str, notice_text: str | None) -> Path:
        out = Path(tmp) / "site"
        args = ["--packages", str(INDEX), "--card", str(CARD), "--out", str(out)]
        if notice_text is not None:
            notice = Path(tmp) / "notice.txt"
            notice.write_text(notice_text, encoding="utf-8")
            args += ["--notice-file", str(notice)]
        site.main(args)
        return out

    def test_writes_a_hostable_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(tmp, "TEST NOTICE")
            names = sorted(str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*") if p.is_file())
            self.assertEqual(names, [".nojekyll", "charts/horizon_panorama__synthetic-sample-site.svg",
                                     "charts/window_strip.svg", "index.html"])

    def test_page_and_charts_equal_the_direct_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(tmp, "TEST NOTICE\n")
            sites = package.load_index(INDEX)
            self.assertEqual((out / "index.html").read_text(encoding="utf-8"),
                             evidence.build_page(sites, CARD, "TEST NOTICE", chart_links=True))
            self.assertEqual((out / "charts" / "window_strip.svg").read_text(encoding="utf-8"),
                             charts.window_strip(sites, "TEST NOTICE"))

    def test_page_links_the_chart_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (self.build(tmp, "TEST NOTICE") / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="charts/window_strip.svg"', html)
            self.assertIn('href="charts/horizon_panorama__synthetic-sample-site.svg"', html)

    def test_empty_notice_file_means_no_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (self.build(tmp, "  \n") / "index.html").read_text(encoding="utf-8")
            self.assertEqual(html, evidence.build_page(package.load_index(INDEX), CARD, None, chart_links=True))

    def test_rebuild_is_identical(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = self.build(a, "N"), self.build(b, "N")
            for path in first.rglob("*"):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
