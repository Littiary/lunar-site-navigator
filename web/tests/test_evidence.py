"""Acceptance tests for the static evidence page.

Done when: the page opens without a login in a private window and on a phone, and there is
a local copy that works without internet. Here that means one self-contained HTML file:
no external script, style sheet, font or image, a mobile viewport, and every number taken
from the packages and the validation card.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from lsn_web import evidence, package

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SITE_DIR = FIXTURES / "contract-sample" / "packages" / "site" / "synthetic-sample-site" / "site-a02ee316b65e2af1"
CARD = FIXTURES / "validation-card" / "validation_card.json"


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


def parse(html: str) -> Tags:
    parser = Tags()
    parser.feed(html)
    return parser


def build() -> str:
    return evidence.build_page([package.load_site_package(SITE_DIR)], card_path=CARD)


class EvidencePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = build()
        cls.page = parse(cls.html)
        cls.text = " ".join(" ".join(cls.page.text).split())
        cls.manifest = json.loads((SITE_DIR / "manifest.json").read_text(encoding="utf-8"))
        cls.card = json.loads(CARD.read_text(encoding="utf-8"))

    def test_rebuild_gives_identical_bytes(self):
        self.assertEqual(self.html, build())

    def test_is_self_contained(self):
        for tag, attrs in self.page.tags:
            if tag == "script":
                self.assertNotIn("src", attrs, "external script")
            if tag == "link":
                self.fail(f"external resource link {attrs}")
            if tag in ("img", "source", "iframe", "video", "audio", "embed", "object"):
                self.assertTrue(attrs.get("src", "").startswith("data:"), f"{tag} loads {attrs.get('src')}")
        self.assertNotIn("@import", self.html)
        self.assertNotIn("url(http", self.html)

    def test_has_mobile_viewport_and_language(self):
        metas = [attrs for tag, attrs in self.page.tags if tag == "meta"]
        self.assertTrue(any(m.get("name") == "viewport" and "width=device-width" in m.get("content", "") for m in metas))
        self.assertTrue(any(m.get("charset", "").lower() == "utf-8" for m in metas))
        self.assertIn(("html", {"lang": "en"}), self.page.tags)

    def test_embeds_both_charts(self):
        images = [attrs for tag, attrs in self.page.tags if tag == "img"]
        self.assertEqual(len(images), 2)
        for image in images:
            self.assertTrue(image["src"].startswith("data:image/svg+xml;base64,"))
            self.assertTrue(image.get("alt"))

    def test_states_package_frame_radius_and_utc_range(self):
        site = self.manifest["site"]
        time = self.manifest["timeline"]["time"]
        for expected in (self.manifest["package_id"], self.manifest["content_sha256"], site["frame"],
                         "1700 km", time["start_utc"], time["end_utc"]):
            self.assertIn(expected, self.text)

    def test_marks_synthetic_data(self):
        self.assertIn("SYNTHETIC SAMPLE DATA", self.text)
        self.assertIn(self.manifest["synthetic_notice"], self.text)

    def test_lists_every_metric_and_event_at_the_default_height(self):
        index = self.manifest["horizon"]["default_height_index"]
        for metric in self.manifest["timeline"]["metrics"]:
            if metric["height_index"] == index:
                self.assertIn(metric["label"], self.text)
        events = [e for e in self.manifest["timeline"]["events"] if e["height_index"] == index]
        self.assertTrue(events)
        for event in events:
            self.assertIn(event["utc"], self.text)

    def test_shows_every_method_card_with_its_status(self):
        for method_id, card in self.manifest["methods"].items():
            self.assertIn(method_id, self.text)
            self.assertIn(card["title"], self.text)
            self.assertIn(card["validation"]["status"], self.text)

    def test_shows_the_validation_card(self):
        summary = self.card["summary"]
        self.assertIn(f"{summary['passed']} of {summary['checks']} checks pass", self.text)
        for check in self.card["checks"]:
            self.assertIn(check["quantity"], self.text)
        for item in self.card["not_validated"]:
            self.assertIn(item["item"], self.text)
        self.assertIn(self.card["generated_from"]["commit"], self.text)

    def test_makes_no_endorsement_claims(self):
        lowered = self.text.lower()
        for phrase in ("nasa-approved", "nasa approved", "endorsed by nasa", "official nasa"):
            self.assertNotIn(phrase, lowered)


class CommandLineTests(unittest.TestCase):
    def test_writes_one_html_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "index.html"
            evidence.main([str(SITE_DIR), "--card", str(CARD), "--out", str(target)])
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["index.html"])
            self.assertEqual(target.read_text(encoding="utf-8"), build())


if __name__ == "__main__":
    unittest.main()
