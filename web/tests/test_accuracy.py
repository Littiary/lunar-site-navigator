"""Acceptance tests for the "Accuracy and limits" page (Task 12).

Done when: the numbers come from the packages and the validation results, and the page makes
no claim such as "first", "only" or "NASA-approved". Here that means: one self-contained HTML
file (it opens without a login, in a private window, on a phone and offline), every check of
the validation card shown once with its stored status, checks against an outside source kept
apart from analytical tests, failed checks shown as failed, and every published value of the
real-mission cases shown with its source, printed precision and whether it is approximate.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from lsn_web import accuracy, package, site as site_build

WEB = Path(__file__).resolve().parent.parent
REPO = WEB.parent
FIXTURES = WEB / "tests" / "fixtures"
SAMPLE_INDEX = FIXTURES / "contract-sample-0.3" / "packages" / "index.json"
SAMPLE_CARD = FIXTURES / "validation-card" / "validation_card.json"
REAL_INDEX = REPO / "packages" / "index.json"
REAL_CARD = REPO / "validation" / "card" / "validation_card.json"


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


def rows_with(page: Tags, attribute: str) -> list[dict]:
    return [attrs for tag, attrs in page.tags if tag == "tr" and attribute in attrs]


class RealRepositoryPage(unittest.TestCase):
    """The page built from the published packages and the stored validation results."""

    @classmethod
    def setUpClass(cls):
        cls.sites = package.load_packages([str(REAL_INDEX)])
        cls.html = accuracy.build_page(cls.sites, REAL_CARD, repo=REPO)
        cls.page = parse(cls.html)
        cls.text = " ".join(" ".join(cls.page.text).split())
        cls.card = json.loads(REAL_CARD.read_text(encoding="utf-8"))

    def test_rebuild_gives_identical_bytes(self):
        self.assertEqual(self.html, accuracy.build_page(self.sites, REAL_CARD, repo=REPO))

    def test_is_self_contained(self):
        for tag, attrs in self.page.tags:
            self.assertNotIn(tag, ("script", "link", "iframe", "object", "embed", "video", "audio"), attrs)
            if tag == "img":
                self.assertTrue(attrs.get("src", "").startswith("data:"), attrs)
        self.assertNotIn("@import", self.html)
        self.assertNotIn("url(", self.html)

    def test_has_mobile_viewport_and_language(self):
        self.assertIn(("html", {"lang": "en"}), self.page.tags)
        metas = [attrs for tag, attrs in self.page.tags if tag == "meta"]
        self.assertTrue(any(m.get("name") == "viewport" and "width=device-width" in m.get("content", "") for m in metas))

    def test_states_the_counts_of_the_card(self):
        s = self.card["summary"]
        self.assertIn(f"{s['passed']} of {s['checks']} checks pass", self.text)
        self.assertIn(f"{s['failed']} fail", self.text)

    def test_every_check_of_the_card_is_shown_once_with_its_stored_status(self):
        rows = rows_with(self.page, "data-check")
        self.assertEqual(sorted(r["data-check"] for r in rows), sorted(c["id"] for c in self.card["checks"]))
        stored = {c["id"]: c["status"] for c in self.card["checks"]}
        for row in rows:
            self.assertEqual(row["data-status"], stored[row["data-check"]])

    def test_outside_sources_are_kept_apart_from_analytical_tests(self):
        by_id = {c["id"]: c for c in self.card["checks"]}
        kinds = {r["data-check"]: r["data-kind"] for r in rows_with(self.page, "data-check")}
        for check_id, kind in kinds.items():
            group = by_id[check_id]["group"]
            if group in accuracy.EXTERNAL_GROUPS:
                self.assertEqual(kind, "external", check_id)
            elif group in accuracy.ANALYTIC_GROUPS:
                self.assertEqual(kind, "analytic", check_id)
            else:
                self.assertEqual(kind, "other", check_id)
        self.assertIn("external", kinds.values())
        self.assertIn("analytic", kinds.values())
        # No group of the stored card is left unclassified without the page saying so.
        self.assertEqual(set(by_id[c]["group"] for c, k in kinds.items() if k == "other"), set())

    def test_failed_checks_are_named_as_failed(self):
        failed = [c for c in self.card["checks"] if c["status"] != "PASS"]
        self.assertTrue(failed, "the stored card has a failed check; the page must show it")
        for check in failed:
            self.assertIn(check["quantity"], self.text)
        self.assertIn("Checks that failed", self.text)

    def test_lists_what_is_not_validated_and_the_limits(self):
        for item in self.card["not_validated"]:
            self.assertIn(item["item"], self.text)
        for limit in self.card["limits"]:
            self.assertIn(" ".join(limit.split()), self.text)

    def test_every_published_site_is_listed_with_its_terrain(self):
        rows = rows_with(self.page, "data-site")
        index = json.loads(REAL_INDEX.read_text(encoding="utf-8"))
        expected = sorted(p["site_id"] for p in index["packages"] if p["kind"] == "site")
        self.assertEqual(sorted(r["data-site"] for r in rows), expected)
        for s in self.sites:
            source = s.manifest["horizon"]["terrain_source"]
            row = next(r for r in rows if r["data-site"] == s.manifest["site"]["site_id"])
            self.assertEqual(row["data-class"], source["resolution_class"])
            self.assertEqual(row["data-band"], "yes" if (s.timeline or {}).get("uncertainty") else "no")
            self.assertIn(source["at_site"]["product_id"], self.text)

    def test_mission_cases_show_source_precision_and_approximate(self):
        cases = []
        for name in ("cases.json", "cases_second_batch.json"):
            document = json.loads((REPO / "validation" / "landers" / name).read_text(encoding="utf-8"))
            cases += [(document, case) for case in document["cases"]]
        self.assertGreaterEqual(len(cases), 8)
        rows = rows_with(self.page, "data-published")
        for document, case in cases:
            for item in case["published"]:
                key = f"{case['id']}.{item['id']}"
                row = next((r for r in rows if r["data-published"] == key), None)
                self.assertIsNotNone(row, key)
                self.assertEqual(row["data-approximate"], "yes" if item["approximate"] else "no")
                self.assertIn(item["precision"], self.text)
                for source in item["source"].split(", "):
                    self.assertIn(document["sources"][source]["url"], self.html)
        eclipse = json.loads((REPO / "validation" / "eclipse" / "cases.json").read_text(encoding="utf-8"))
        for item in eclipse["published"]:
            self.assertIsNotNone(next((r for r in rows if r["data-published"] == f"eclipse.{item['id']}"), None))

    def test_mission_results_are_the_stored_ones(self):
        table = json.loads((REPO / "validation" / "landers" / "results" / "validation_table.json").read_text(encoding="utf-8"))
        rows = {r["data-result"]: r for r in rows_with(self.page, "data-result")}
        for case in table["cases"]:
            for row in case["rows"]:
                self.assertEqual(rows[row["id"]]["data-status"], row.get("status") or "reported")

    def test_terrain_checks_show_stored_failures(self):
        near = json.loads((REPO / "data" / "checkpoints" / "near_field_report.json").read_text(encoding="utf-8"))
        rows = {r["data-seam"]: r for r in rows_with(self.page, "data-seam")}
        self.assertEqual(sorted(rows), sorted(near["sites"]))
        for product, record in near["sites"].items():
            self.assertEqual(rows[product]["data-passed"], "yes" if record["seam"]["passed"] else "no")
        llr = json.loads((REPO / "data" / "checkpoints" / "llr_report.json").read_text(encoding="utf-8"))
        reflectors = rows_with(self.page, "data-reflector")
        self.assertEqual(len(reflectors), sum(len(v["reflectors"]) for k, v in llr["results"].items()
                                              if isinstance(v, dict) and "reflectors" in v and not k.endswith("_reported_only")))

    def test_makes_no_unsupported_claims(self):
        lowered = self.text.lower()
        for phrase in ("nasa-approved", "nasa approved", "endorsed by nasa", "official nasa", "most accurate",
                       "more accurate than", "the first tool", "the only tool", "world's first", "state of the art"):
            self.assertNotIn(phrase, lowered)
        self.assertIsNone(re.search(r"\b(first|only) (lunar|tool|planner|product|of its kind)", lowered))

    def test_links_the_source_records(self):
        hrefs = [attrs.get("href", "") for tag, attrs in self.page.tags if tag == "a"]
        for needed in ("validation/card/validation_card.md", "CREDITS.md", "data/notes/known_limits.md",
                       "validation/landers/cases.json", "docs/method"):
            self.assertTrue(any(needed in h for h in hrefs), needed)


class SamplePackagePage(unittest.TestCase):
    """Older and synthetic packages, and a build without the repository's result files."""

    def test_builds_without_result_files_and_says_so(self):
        sites = package.load_packages([str(SAMPLE_INDEX)])
        with tempfile.TemporaryDirectory() as empty:
            html = accuracy.build_page(sites, SAMPLE_CARD, repo=Path(empty))
        text = " ".join(" ".join(parse(html).text).split())
        self.assertIn("SYNTHETIC SAMPLE DATA", text)
        self.assertIn("not part of this build", text)
        card = json.loads(SAMPLE_CARD.read_text(encoding="utf-8"))
        self.assertEqual(len(rows_with(parse(html), "data-check")), len(card["checks"]))

    def test_builds_without_a_card(self):
        sites = package.load_packages([str(SAMPLE_INDEX)])
        html = accuracy.build_page(sites, None, repo=REPO)
        self.assertIn("No validation card was given to this build", html)

    def test_notice_is_shown(self):
        sites = package.load_packages([str(SAMPLE_INDEX)])
        html = accuracy.build_page(sites, SAMPLE_CARD, notice="Provisional results.", repo=REPO)
        self.assertIn("Provisional results.", html)


class SiteBuildLinksThePage(unittest.TestCase):
    def test_site_build_writes_the_page_and_links_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            site_build.build([str(SAMPLE_INDEX)], SAMPLE_CARD, None, out)
            self.assertTrue((out / "accuracy.html").is_file())
            sites = package.load_packages([str(SAMPLE_INDEX)])
            self.assertEqual((out / "accuracy.html").read_text(encoding="utf-8"),
                             accuracy.build_page(sites, SAMPLE_CARD, None, repo=REPO, site_links=True))
            for name in ("index.html", "compare.html", "evidence.html"):
                self.assertIn('href="accuracy.html"', (out / name).read_text(encoding="utf-8"), name)
            self.assertIn('href="../accuracy.html"', (out / "viewer" / "index.html").read_text(encoding="utf-8"))
            self.assertIn('href="evidence.html"', (out / "accuracy.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
