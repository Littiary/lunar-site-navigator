"""Acceptance tests for reading packages of every 0.x contract version, for the
provisional notice, and (when present locally) for the real site packages.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from lsn_web import charts, evidence, package
from tests.test_charts import SITE_DIR as SITE_01, real_layout_copy
from tests.test_evidence import parse

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INDEX_03 = FIXTURES / "contract-sample-0.3" / "packages" / "index.json"
SITE_03 = INDEX_03.parent / "site" / "synthetic-sample-site" / "site-0c0ce671f55e8cb1"
REPO = Path(__file__).resolve().parents[2]
REAL_INDEX = REPO / "packages" / "index.json"  # published by the core stream (main, 945546d)
SVG = "{http://www.w3.org/2000/svg}"
NOTICE = "PROVISIONAL TEST NOTICE"


def text_of(html: str) -> str:
    return " ".join(" ".join(parse(html).text).split())


class ContractVersionTests(unittest.TestCase):
    def test_reads_0_1_and_0_3(self):
        self.assertEqual(package.load_site_package(SITE_01).contract_version, "0.1")
        self.assertEqual(package.load_site_package(SITE_03).contract_version, "0.3")

    def test_index_lists_the_site_packages(self):
        sites = package.load_index(INDEX_03)
        self.assertEqual([s.package_id for s in sites], ["site-0c0ce671f55e8cb1"])

    def test_0_3_package_builds_charts_and_page(self):
        site = package.load_site_package(SITE_03)
        ET.fromstring(charts.horizon_panorama(site))
        ET.fromstring(charts.window_strip([site]))
        self.assertIn(site.package_id, text_of(evidence.build_page([site])))

    def test_blockers_are_listed_when_present(self):
        site = package.load_site_package(SITE_03)
        index = site.manifest["horizon"]["default_height_index"]
        expected = [b for b in site.timeline["blockers"] if b["height_index"] == index]
        self.assertTrue(expected)
        rows = [attrs for tag, attrs in parse(evidence.build_page([site])).tags if tag == "tr" and "data-obstacle" in attrs]
        self.assertEqual([(r["data-body"], int(r["data-obstacle"])) for r in rows],
                         [(b["body"], b["obstacle_id"]) for b in expected])

    def test_blockers_section_is_hidden_when_absent(self):
        site = package.load_site_package(SITE_01)
        self.assertNotIn("timeline.blockers", site.timeline)
        self.assertNotIn('id="blockers', evidence.build_page([site]))

    def test_every_window_at_the_default_height_is_listed(self):
        site = package.load_site_package(SITE_03)
        index = site.manifest["horizon"]["default_height_index"]
        rows = [attrs["data-window"] for tag, attrs in parse(evidence.build_page([site])).tags
                if tag == "tr" and "data-window" in attrs]
        self.assertEqual(rows, [w["id"] for w in site.timeline["windows"] if w["height_index"] == index])


class NoticeTests(unittest.TestCase):
    def test_notice_is_on_every_chart_and_the_page(self):
        site = package.load_site_package(SITE_01)
        for svg in (charts.horizon_panorama(site, notice=NOTICE), charts.window_strip([site], notice=NOTICE)):
            self.assertIn(NOTICE, " ".join("".join(t.itertext()) for t in ET.fromstring(svg).iter(f"{SVG}text")))
        self.assertIn(NOTICE, text_of(evidence.build_page([site], notice=NOTICE)))

    def test_no_notice_by_default(self):
        site = package.load_site_package(SITE_01)
        self.assertNotIn(NOTICE, charts.horizon_panorama(site))

    def test_uncommitted_core_is_flagged(self):
        site = package.load_site_package(SITE_01)
        self.assertTrue(site.manifest["provenance"]["software"]["git_dirty"])
        self.assertIn("uncommitted changes", text_of(evidence.build_page([site])))

    def test_dsn_row_is_drawn_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = real_layout_copy(tmp)
            document = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
            for window in list(document["timeline"]["windows"]):
                if window["id"] == "earth_visible":
                    document["timeline"]["windows"].append(dict(window, id="earth_network_dsn"))
            (copy / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
            site = package.load_site_package(copy)
            root = ET.fromstring(charts.window_strip([site]))
            index = site.manifest["horizon"]["default_height_index"]
            dsn = next(w for w in site.timeline["windows"] if w["id"] == "earth_network_dsn" and w["height_index"] == index)
            self.assertEqual(len(root.findall(f".//{SVG}rect[@data-window='earth_network_dsn']")), len(dsn["intervals_et_s"]))


class CommandLineTests(unittest.TestCase):
    def test_charts_from_an_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            charts.main([str(INDEX_03), "--out", tmp, "--notice", NOTICE])
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["horizon_panorama__synthetic-sample-site.svg", "window_strip.svg"])
            self.assertIn(NOTICE, (Path(tmp) / "window_strip.svg").read_text(encoding="utf-8"))


@unittest.skipUnless(REAL_INDEX.exists(), "published packages/ not present on this branch")
class RealPackageTests(unittest.TestCase):
    """Reads and draws the real packages published in packages/ by the core stream."""

    def test_every_real_package_is_read_and_drawn(self):
        sites = package.load_index(REAL_INDEX)
        self.assertEqual(len(sites), 3)
        for site in sites:
            self.assertFalse(site.synthetic)
            for ref in package.array_refs(site.manifest):
                site.array(ref)  # size and SHA-256 against the manifest
            ET.fromstring(charts.horizon_panorama(site))
        ET.fromstring(charts.window_strip(sites))
        page = text_of(evidence.build_page(sites, notice=NOTICE))
        for site in sites:
            self.assertIn(site.package_id, page)
        self.assertNotIn("SYNTHETIC SAMPLE DATA", page)


if __name__ == "__main__":
    unittest.main()
