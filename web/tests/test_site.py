"""Acceptance tests for the one-command site build (lsn_web.site).

Done when: one command turns the published packages into a static folder that can be
hosted as it is (index.html, the charts as files, no Jekyll processing), and the notice
comes from a file so that it can be changed or removed without touching code.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
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
            top = [n for n in names if not n.startswith(("viewer/", "packages/"))]
            self.assertEqual(top, [".nojekyll", "charts/horizon_panorama__synthetic-sample-site.svg",
                                   "charts/window_strip.svg", "index.html", "notice.json"])
            self.assertIn("viewer/index.html", names)
            self.assertIn("packages/index.json", names)

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

    def test_viewer_and_packages_are_copied_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(tmp, "TEST NOTICE")
            root = INDEX.parent
            expected = {"index.json"}
            for s in package.load_index(INDEX):
                rel = s.path.relative_to(root)
                expected.add(str(rel / "manifest.json").replace("\\", "/"))
                expected |= {str(rel / r["file"]).replace("\\", "/") for r in package.array_refs(s.manifest)}
            index = json.loads((root / "index.json").read_text(encoding="utf-8"))
            for entry in index["packages"]:
                if entry["kind"] != "site":
                    d = root / entry["path"]
                    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                    expected.add(entry["path"] + "/manifest.json")
                    expected |= {entry["path"] + "/" + r["file"] for r in package.array_refs(m)}
            copied = {str(p.relative_to(out / "packages")).replace("\\", "/") for p in (out / "packages").rglob("*") if p.is_file()}
            self.assertEqual(copied, expected)
            for rel in expected:
                self.assertEqual((out / "packages" / rel).read_bytes(), (root / rel).read_bytes(), rel)
            viewer = Path(site.__file__).resolve().parent.parent / "viewer"
            for src in viewer.rglob("*"):
                if src.is_file():
                    self.assertEqual((out / "viewer" / src.relative_to(viewer)).read_bytes(), src.read_bytes(), src.name)

    def test_notice_json_carries_the_notice(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(json.loads((self.build(a, " A  B ") / "notice.json").read_text(encoding="utf-8")), {"notice": "A B"})
            self.assertEqual(json.loads((self.build(b, "") / "notice.json").read_text(encoding="utf-8")), {"notice": None})

    def test_page_links_the_viewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('href="viewer/"', (self.build(tmp, "N") / "index.html").read_text(encoding="utf-8"))

    def test_rebuild_is_identical(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = self.build(a, "N"), self.build(b, "N")
            for path in first.rglob("*"):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
