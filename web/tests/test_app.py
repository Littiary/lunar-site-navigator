"""Tests of the React site (web/app) and of its place in the site build (lsn_web.site).

Done when: `python -m lsn_web.site` places the React build at the site root (index.html,
compare/, assets/) next to everything it wrote before; the classic comparison page stays at
compare.html and classic.html; without an app build the root is the classic page as before; the
React comparison page runs the classic comparison module (viewer/js/compare.js) unchanged, on a
page that has every element that module looks up, so it shows the same numbers; and the app
computes no science.

The checks of the built app (web/app/dist) run only when it has been built
(`cd web/app && npm ci && npm run build`).

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from lsn_web import site

WEB = Path(__file__).resolve().parents[1]
REPO = WEB.parent
APP_SRC = WEB / "app"
APP_DIST = APP_SRC / "dist"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
INDEX = FIXTURES / "contract-sample-0.3" / "packages" / "index.json"
APP = FIXTURES / "app-build"
NUMERIC = re.compile(r"Math\.(sin|cos|tan|asin|acos|atan|atan2|sqrt|cbrt|pow|exp|log|log10|log2|hypot|sinh|cosh|tanh)\b")


def build(out: Path, *extra: str) -> str:
    """Run the site build; return what it wrote to stderr."""
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        site.main(["--packages", str(INDEX), "--card", "", "--out", str(out), *extra])
    return err.getvalue()


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


class SiteBuildPlacesTheApp(unittest.TestCase):
    def test_app_is_copied_byte_for_byte_to_the_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(out, "--app", str(APP))
            for rel in files(APP):
                self.assertEqual((out / rel).read_bytes(), (APP / rel).read_bytes(), rel)
            # Everything the build wrote before is still there; the classic page has a stable name.
            for rel in ("compare.html", "classic.html", "evidence.html", "accuracy.html", "learn.html", "notice.json",
                        "packages/index.json", "summary/index.json", "viewer/js/compare.js", "viewer/compare.html"):
                self.assertTrue((out / rel).is_file(), rel)
            self.assertEqual((out / "classic.html").read_text(encoding="utf-8"), site.comparison_page())
            self.assertEqual((out / "compare.html").read_text(encoding="utf-8"), site.comparison_page())

    def test_without_an_app_the_root_is_the_classic_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(out, "--app", "")
            self.assertEqual((out / "index.html").read_text(encoding="utf-8"), site.comparison_page())
            self.assertFalse((out / "assets").exists())
            self.assertFalse((out / "compare").exists())

    def test_a_missing_app_build_falls_back_to_the_classic_page_with_a_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            note = build(out, "--app", str(Path(tmp) / "no-such-build"))
            self.assertIn("no app build", note)
            self.assertEqual((out / "index.html").read_text(encoding="utf-8"), site.comparison_page())

    def test_rebuild_without_the_app_removes_its_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(out, "--app", str(APP))
            self.assertTrue((out / "assets" / "main-fixture.js").is_file())
            build(out, "--app", "")
            self.assertFalse((out / "assets").exists())
            self.assertFalse((out / "compare").exists())
            self.assertEqual((out / "index.html").read_text(encoding="utf-8"), site.comparison_page())

    def test_rebuild_with_the_app_is_identical(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = Path(a) / "site", Path(b) / "site"
            build(first, "--app", str(APP))
            build(second, "--app", str(APP))
            self.assertEqual(files(first), files(second))
            for rel in files(first):
                self.assertEqual((first / rel).read_bytes(), (second / rel).read_bytes(), rel)

    def test_the_app_may_not_overwrite_site_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            (app / "assets").mkdir(parents=True)
            (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
            (app / "evidence.html").write_text("not the evidence page", encoding="utf-8")
            with self.assertRaises(OSError):
                build(Path(tmp) / "site", "--app", str(app))


class ComparePageRunsTheClassicModule(unittest.TestCase):
    """The React comparison page is a layout around web/viewer/js/compare.js."""

    def setUp(self):
        self.compare_src = "\n".join(p.read_text(encoding="utf-8") for p in sorted((APP_SRC / "src" / "compare").glob("*.ts*")))
        self.classic = (WEB / "viewer" / "compare.html").read_text(encoding="utf-8")

    def test_pane_template_is_read_from_the_classic_page_not_copied(self):
        plugin = (APP_SRC / "plugins" / "classic.ts").read_text(encoding="utf-8")
        self.assertIn('resolve(REPO, "web", "viewer", "compare.html")', plugin)
        self.assertIn('<template id="pane-template">', plugin)
        self.assertIn('from "virtual:lsn-classic"', self.compare_src)
        # No pasted copy of the template in the app source.
        for path in (APP_SRC / "src").rglob("*.ts*"):
            self.assertNotIn('data-role="readout"', path.read_text(encoding="utf-8"), path.name)

    def test_every_element_the_module_looks_up_is_on_the_page(self):
        code = (WEB / "viewer" / "js" / "compare.js").read_text(encoding="utf-8")
        ids = set(re.findall(r'\$\("([\w-]+)"\)', code)) | {f"view-{v}" for v in ("chart", "sky", "ground", "calendar")}
        ids |= {"pane-a", "pane-b", "pane-template"}
        self.assertGreater(len(ids), 20)
        declared = set(re.findall(r'\bid(?:="|: ")([\w-]+)"', self.compare_src))
        self.assertEqual(sorted(ids - declared), [])
        steps = set(re.findall(r'step: "(-?\d+)"', self.compare_src))
        self.assertEqual(steps, set(re.findall(r'data-step="(-?\d+)"', self.classic)))

    def test_module_is_loaded_at_run_time_from_the_published_viewer(self):
        self.assertIn('at("viewer/js/compare.js")', self.compare_src)
        for path in (APP_SRC / "src").rglob("*.ts*"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"from\s+['\"][./]*viewer/js/", path.name)

    def test_app_computes_no_science(self):
        for path in list((APP_SRC / "src").rglob("*.ts*")) + list((APP_SRC / "plugins").rglob("*.ts")):
            self.assertIsNone(NUMERIC.search(path.read_text(encoding="utf-8")), path.name)

    def test_dependencies_are_locked(self):
        lock = json.loads((APP_SRC / "package-lock.json").read_text(encoding="utf-8"))
        manifest = json.loads((APP_SRC / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["name"], manifest["name"])
        for dep in list(manifest["dependencies"]) + list(manifest["devDependencies"]):
            self.assertIn(f"node_modules/{dep}", lock["packages"], dep)


class LandingGroundView(unittest.TestCase):
    """The "See it in 3-D" section of the landing page draws with the viewers' renderer."""

    def setUp(self):
        self.tsx = (APP_SRC / "src" / "landing" / "GroundView.tsx").read_text(encoding="utf-8")
        self.scene = (WEB / "viewer" / "js" / "ground-scene.js").read_text(encoding="utf-8")

    def test_section_follows_the_key_figures(self):
        landing = (APP_SRC / "src" / "landing" / "Landing.tsx").read_text(encoding="utf-8")
        self.assertLess(landing.index("<KeyFigures />"), landing.index("<GroundView />"))
        self.assertLess(landing.index("<GroundView />"), landing.index("<Stills />"))

    def test_scene_is_loaded_at_run_time_only_when_near_the_screen(self):
        self.assertIn('at("viewer/js/ground-scene.js")', self.tsx)
        self.assertIn("useInView(section)", self.tsx)
        self.assertLess(self.tsx.index("if (!near"), self.tsx.index("import(/* @vite-ignore */ SCENE_MODULE)"))

    def test_instant_sites_height_and_planner_link(self):
        self.assertIn('const INSTANT = "2026-12-07T04:00:00Z"', self.tsx)
        self.assertIn("const HEIGHT_M = 2;", self.tsx)
        for site_id in ("shackleton-rim-crest", "de-gerlache-rim-crest"):
            self.assertIn(f'id: "{site_id}"', self.tsx)
        self.assertIn('a: SITES[0].id, b: SITES[1].id, ha: "2", hb: "2", view: "ground"', self.tsx)
        self.assertIn('q.set("i", String(i))', self.tsx)

    def test_scene_uses_the_steps_of_a_comparison_pane(self):
        # Same loaders, lookups and renderer as a pane of compare.js; nothing of its own.
        for name in ("loadIndex(", "loadSite(", "nearestSample(", "loadSiteData(", "groundData(", "groundInput(",
                     'import("./view3d.js")', "createView("):
            self.assertIn(name, self.scene, name)
        self.assertIsNone(NUMERIC.search(self.scene))
        compare = (WEB / "viewer" / "js" / "compare.js").read_text(encoding="utf-8")
        for name in ("groundData(", "groundInput(", "createView("):
            self.assertIn(name, compare, name)


@unittest.skipUnless((APP_DIST / "index.html").is_file(), "web/app is not built (npm run build)")
class BuiltAppTests(unittest.TestCase):
    def test_build_has_the_layout_the_site_build_expects(self):
        for rel in files(APP_DIST):
            self.assertTrue(rel == "index.html" or rel.split("/")[0] in site.APP_FOLDERS, rel)
        self.assertTrue((APP_DIST / "compare" / "index.html").is_file())

    def test_pages_load_from_the_project_path_of_github_pages(self):
        for page in ("index.html", "compare/index.html"):
            html = (APP_DIST / page).read_text(encoding="utf-8")
            scripts = re.findall(r'<script type="module"[^>]*src="([^"]+)"', html)
            self.assertTrue(scripts, page)
            for src in scripts:
                self.assertTrue(src.startswith("/lunar-site-navigator/assets/"), src)
                self.assertTrue((APP_DIST / src[len("/lunar-site-navigator/"):]).is_file(), src)

    def test_import_map_comes_before_any_module_script(self):
        # three.js of viewer/vendor is resolved through the import map, as on the classic page;
        # a browser ignores an import map that follows a module script. The landing page needs
        # it for the 3-D section.
        for page, path in (("compare/index.html", "../viewer/vendor/three/three.module.js"),
                           ("index.html", "./viewer/vendor/three/three.module.js")):
            html = (APP_DIST / page).read_text(encoding="utf-8")
            self.assertIn(f'"three": "{path}"', html, page)
            self.assertLess(html.index('type="importmap"'), html.index('type="module"'), page)

    def test_compare_bundle_carries_the_classic_pane_template(self):
        classic = (WEB / "viewer" / "compare.html").read_text(encoding="utf-8")
        template = re.search(r'<template id="pane-template">(.*?)</template>', classic, re.S).group(1)
        bundle = "".join(p.read_text(encoding="utf-8") for p in (APP_DIST / "assets").glob("*.js"))
        roles = re.findall(r'data-role="([\w-]+)"', template)
        self.assertGreater(len(roles), 10)
        for role in roles:
            self.assertIn(f'data-role="{role}"', bundle, role)

    def test_landing_facts_are_those_of_the_published_files(self):
        bundle = "".join(p.read_text(encoding="utf-8") for p in (APP_DIST / "assets").glob("*.js"))
        index = json.loads((REPO / "packages" / "index.json").read_text(encoding="utf-8"))
        entry = next(p for p in index["packages"] if p.get("site_id") == "shackleton-rim-crest")
        self.assertIn(entry["package_id"], bundle)
        card = json.loads((REPO / "validation" / "card" / "validation_card.json").read_text(encoding="utf-8"))
        s = card["summary"]
        # The bundler may write the JSON as an object literal with unquoted keys.
        self.assertRegex(bundle, rf'checks"?:{s["checks"]},"?passed"?:{s["passed"]},"?failed"?:{s["failed"]}\b')
        for failed in s["failed_ids"]:
            self.assertIn(failed, bundle)


if __name__ == "__main__":
    unittest.main()
