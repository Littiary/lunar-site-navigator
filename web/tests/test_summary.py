"""The first-screen summaries (lsn_web.summary): every value is a value of the site manifest,
each file is listed with its SHA-256, and only what the first screen needs is in them."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from lsn_web import summary

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / "packages" / "index.json"


@unittest.skipUnless(INDEX.exists(), "the published packages are missing")
class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "summary"
        summary.write_summaries(INDEX, cls.out)
        cls.index = json.loads(INDEX.read_text(encoding="utf-8"))
        cls.catalogue = json.loads((cls.out / "index.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def sites(self):
        for entry in self.index["packages"]:
            if entry["kind"] == "site":
                manifest = json.loads((INDEX.parent / entry["path"] / "manifest.json").read_text(encoding="utf-8"))
                yield entry, manifest, json.loads((self.out / f"{entry['site_id']}.json").read_text(encoding="utf-8"))

    def test_every_site_of_the_index_is_listed_with_its_digest(self):
        listed = {s["site_id"]: s for s in self.catalogue["sites"]}
        sites = [e for e in self.index["packages"] if e["kind"] == "site"]
        self.assertEqual(sorted(listed), sorted(e["site_id"] for e in sites))  # no hard-coded count
        for entry in sites:
            item = listed[entry["site_id"]]
            data = (self.out / item["file"]).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(item["bytes"], len(data))
            self.assertEqual(item["package_id"], entry["package_id"])

    def test_values_are_copied_from_the_manifest(self):
        for entry, m, s in self.sites():
            t, st = m["timeline"], s["timeline"]
            self.assertEqual(s["summary_of"]["package_id"], m["package_id"])
            self.assertEqual(s["summary_of"]["content_sha256"], m["content_sha256"])
            self.assertEqual(st["time"], t["time"])
            self.assertEqual(st["series"], t["series"])
            for k in ("observer_heights_m", "default_height_index", "terrain_source", "azimuth", "elevation_deg"):
                self.assertEqual(s["horizon"][k], m["horizon"][k], k)
            wins = [w for w in t["windows"] if w["id"] in summary.WINDOWS]
            self.assertEqual(st["windows"], [{k: w[k] for k in ("id", "subject", "height_index", "definition", "intervals_et_s", "method") if k in w} for w in wins])
            evs = [e for e in t["events"] if e["body"] in ("SUN", "EARTH")]
            self.assertEqual(st["events"], [{k: e[k] for k in summary.EVENT_FIELDS if k in e} for e in evs])
            self.assertEqual(st["opportunities"], [{k: v for k, v in o.items() if k not in summary.OPPORTUNITY_LEFT_OUT} for o in t.get("opportunities", [])])
            self.assertEqual(st["metrics"], [x for x in t["metrics"] if any(x["id"].endswith(c) for c in summary.COUNTDOWN)])
            self.assertEqual(s["request"]["timeline"].get("requirements"), m["request"]["timeline"].get("requirements"))
            for method, card in s["methods"].items():
                self.assertEqual(card["validation"]["status"], m["methods"][method]["validation"]["status"])

    def test_summaries_are_small(self):
        for entry, m, s in self.sites():
            path = INDEX.parent / entry["path"] / "manifest.json"
            self.assertLess((self.out / f"{entry['site_id']}.json").stat().st_size, path.stat().st_size / 4, entry["site_id"])


if __name__ == "__main__":
    unittest.main()
