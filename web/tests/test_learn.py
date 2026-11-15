"""Acceptance tests for the education page (Task 15).

Done when: the page explains lunar horizons, visibility windows, terrain uncertainty and
landing opportunities in a few sentences each; every number in its examples is a value of a
published package; scientific values, units and the package's own statements are unchanged;
it is one self-contained file; and a further language can be added as one entry of the text
file, which these tests then hold to the English entry.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from lsn_web import charts, learn, package, site as site_build

WEB = Path(__file__).resolve().parent.parent
REPO = WEB.parent
SAMPLE_INDEX = WEB / "tests" / "fixtures" / "contract-sample-0.3" / "packages" / "index.json"
SAMPLE_CARD = WEB / "tests" / "fixtures" / "validation-card" / "validation_card.json"
OLD_SAMPLE = WEB / "tests" / "fixtures" / "contract-sample" / "packages" / "index.json"
REAL_INDEX = REPO / "packages" / "index.json"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def parse(html: str) -> tuple[Tags, str]:
    parser = Tags()
    parser.feed(html)
    return parser, " ".join(" ".join(parser.text).split())


class TextFile(unittest.TestCase):
    def test_english_covers_the_four_topics(self):
        text = learn.load_text()["en"]
        self.assertEqual([s["id"] for s in text["sections"]], ["horizon", "windows", "uncertainty", "opportunities"])
        for section in text["sections"]:
            self.assertLessEqual(len(section["paragraphs"]), 3, "concise: at most three paragraphs per topic")

    def test_every_language_has_the_keys_and_placeholders_of_english(self):
        texts = learn.load_text()
        english = texts["en"]
        for code, text in texts.items():
            self.assertEqual(set(text), set(english), code)
            self.assertEqual([s["id"] for s in text["sections"]], [s["id"] for s in english["sections"]], code)
            for mine, theirs in zip(text["sections"], english["sections"]):
                self.assertEqual(len(mine["paragraphs"]), len(theirs["paragraphs"]), code)
                self.assertEqual(learn.fields(mine["example"]), learn.fields(theirs["example"]), code)
            for key in ("example_source", "planned_feasible", "planned_not_feasible", "planned_no_window"):
                self.assertEqual(learn.fields(text[key]), learn.fields(english[key]), (code, key))


class RealPackages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = package.load_packages([str(REAL_INDEX)])
        cls.site = learn.pick_example(cls.sites)
        cls.html = learn.build_page(cls.sites)
        cls.page, cls.text = parse(cls.html)

    def test_is_self_contained_with_viewport_and_language(self):
        for tag, attrs in self.page.tags:
            self.assertNotIn(tag, ("script", "link", "img", "iframe", "object", "embed"), attrs)
        self.assertNotIn("@import", self.html)
        self.assertNotIn("url(", self.html)
        self.assertIn(("html", {"lang": "en"}), self.page.tags)
        metas = [attrs for tag, attrs in self.page.tags if tag == "meta"]
        self.assertTrue(any(m.get("name") == "viewport" and "width=device-width" in m.get("content", "") for m in metas))

    def test_rebuild_gives_identical_bytes(self):
        self.assertEqual(self.html, learn.build_page(self.sites))

    def test_all_four_examples_are_shown(self):
        shown = [attrs["data-example"] for tag, attrs in self.page.tags if "data-example" in attrs]
        self.assertEqual(shown, ["horizon", "windows", "uncertainty", "opportunities"])

    def test_example_numbers_are_package_values(self):
        m, t = self.site.manifest, self.site.timeline
        index = m["horizon"]["default_height_index"]
        blocker = next(b for b in t["blockers"] if b["height_index"] == index and b["body"] == "SUN")
        self.assertIn(f"only {charts.num(blocker['peak_distance_m'], 0)} m away", self.text)
        self.assertIn(f"for {charts.num(blocker['lost_s'] / 3600, 0)} hours", self.text)
        sun = next(x for x in t["metrics"] if x["id"] == "sun_visible_fraction_of_time" and x["height_index"] == index)
        self.assertIn(f"{100 * sun['value']:.1f} % of the time at", self.text)
        event = next(x for x in t["events"] if x["height_index"] == index and x["body"] == "SUN")
        for key in ("utc", "earliest_utc", "latest_utc"):
            self.assertIn(event[key], self.text)
        requirement = m["request"]["timeline"]["requirements"][0]
        opportunity = next(o for o in t["opportunities"] if o["height_index"] == index and o["requirement_id"] == requirement["id"])
        self.assertIn(f"has {opportunity['window_count']} landing windows", self.text)
        self.assertIn(f"{100 * opportunity['feasible_fraction']:.1f} % of the time", self.text)
        self.assertIn(opportunity["planned_landing"]["utc"], self.text)

    def test_package_statements_are_quoted_unchanged(self):
        m, t = self.site.manifest, self.site.timeline
        self.assertIn(" ".join(t["uncertainty"]["horizon_error"]["assumption"].split()), self.text)
        self.assertIn(m["request"]["timeline"]["requirements"][0]["label"], self.text)
        self.assertIn(self.site.package_id, self.text)

    def test_says_the_requirement_is_an_example_and_makes_no_claims(self):
        lowered = self.text.lower()
        self.assertIn("not a mission requirement", lowered)
        for phrase in ("nasa-approved", "nasa approved", "endorsed by nasa", "most accurate", "the first tool", "the only tool"):
            self.assertNotIn(phrase, lowered)


class OlderPackagesAndSiteBuild(unittest.TestCase):
    def test_missing_fields_remove_the_example_and_the_page_says_so(self):
        sites = package.load_packages([str(OLD_SAMPLE)])  # contract 0.1: no obstacles, band or opportunities
        html = learn.build_page(sites)
        page, text = parse(html)
        missing = [attrs["data-no-example"] for tag, attrs in page.tags if "data-no-example" in attrs]
        self.assertIn("uncertainty", missing)
        self.assertIn("opportunities", missing)
        self.assertIn(learn.load_text()["en"]["no_example"], text)
        self.assertIn("SYNTHETIC SAMPLE DATA", text)

    def test_site_build_writes_one_page_per_language_and_links_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            site_build.build([str(SAMPLE_INDEX)], SAMPLE_CARD, None, out)
            for code in learn.languages():
                self.assertTrue((out / learn.page_name(code)).is_file(), code)
            self.assertEqual(learn.page_name("en"), "learn.html")
            for name in ("index.html", "compare.html"):
                self.assertIn('href="learn.html"', (out / name).read_text(encoding="utf-8"), name)
            self.assertIn('href="../learn.html"', (out / "viewer" / "index.html").read_text(encoding="utf-8"))
            sites = package.load_packages([str(SAMPLE_INDEX)])
            self.assertEqual((out / "learn.html").read_text(encoding="utf-8"), learn.build_page(sites, "en", site_links=True))


if __name__ == "__main__":
    unittest.main()
