"""Regression tests that execute the viewer's JavaScript (with Node) instead of reading its source.

Covered:
* site files (packages/index.json, notice.json) resolve to the right place from every built page,
  including the copies of the comparison at the site root;
* the CSV export reproduces every package value of the series exactly;
* the planning-details block handles any 0.x version, a missing planned landing, units per
  observer height and the assumption sentences.

The tests are skipped where Node is not installed. Run from the repository root:
python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urljoin

from lsn_web import site as site_build

WEB = Path(__file__).resolve().parents[1]
REPO = WEB.parent
JS = WEB / "viewer" / "js"
INDEX = REPO / "packages" / "index.json"
NODE = shutil.which("node")


def run_node(code: str) -> str:
    result = subprocess.run([NODE, "--input-type=module", "-e", code], capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return result.stdout


def module(name: str) -> str:
    return (JS / name).as_uri()


def published_site(site_id: str) -> Path:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    entry = next(p for p in index["packages"] if p["kind"] == "site" and p["site_id"] == site_id)
    return INDEX.parent / entry["path"]


# A plain object with the parts of a SitePackage that the functions under test use.
SITE_OBJECT = """
import { readFileSync } from "node:fs";
function loadSite(dir) {
  const manifest = JSON.parse(readFileSync(dir + "/manifest.json", "utf8"));
  const f4 = (ref) => { const b = readFileSync(dir + "/" + ref.file); return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); };
  const row = (ref, h) => { const v = f4(ref), w = ref.shape[ref.shape.length - 1]; return v.subarray(h * w, (h + 1) * w); };
  return {
    manifest, id: manifest.package_id, timeline: manifest.timeline,
    methodStatus: (m) => ((manifest.methods || {})[m] || {}).validation?.status || "unknown",
    f4, row,
  };
}
"""


@unittest.skipUnless(NODE, "node is not installed")
class SiteFileUrlTests(unittest.TestCase):
    def test_site_files_resolve_two_levels_above_the_script(self):
        out = run_node(f"""
          import {{ siteFileUrl }} from "{module('panel.js')}";
          console.log(JSON.stringify([
            siteFileUrl("packages/index.json", "https://example.org/proj/viewer/js/panel.js"),
            siteFileUrl("notice.json", "https://example.org/proj/viewer/js/panel.js"),
          ]));""")
        self.assertEqual(json.loads(out), ["https://example.org/proj/packages/index.json", "https://example.org/proj/notice.json"])

    def test_every_built_page_reaches_the_packages_and_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            site_build.main(["--packages", str(INDEX), "--out", str(out), "--card", ""])
            base = "https://example.org/proj/"
            pages = ["index.html", "compare.html", "viewer/index.html", "viewer/compare.html"]
            for page in pages:
                html = (out / page).read_text(encoding="utf-8")
                scripts = re.findall(r'<script type="module" src="([^"]+)"', html)
                self.assertEqual(len(scripts), 1, page)
                script_url = urljoin(base + page, scripts[0])
                # panel.js lives next to the page script; siteFileUrl resolves from panel.js.
                panel_url = urljoin(script_url, "panel.js")
                resolved = json.loads(run_node(f"""
                  import {{ siteFileUrl }} from "{module('panel.js')}";
                  console.log(JSON.stringify([siteFileUrl("packages/index.json", "{panel_url}"), siteFileUrl("notice.json", "{panel_url}")]));"""))
                self.assertEqual(resolved, [base + "packages/index.json", base + "notice.json"], page)
                for url in resolved:
                    self.assertTrue((out / url[len(base):]).is_file(), f"{page}: {url} is not in the build")

    def test_pages_take_their_defaults_from_site_file_url(self):
        for name in ("viewer.js", "compare.js"):
            code = (JS / name).read_text(encoding="utf-8")
            self.assertIn('siteFileUrl("packages/index.json")', code, name)
            self.assertIn('siteFileUrl("notice.json")', code, name)
            self.assertNotIn('"../packages/index.json"', code, name)


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class CsvAccuracyTests(unittest.TestCase):
    def test_every_csv_value_equals_the_package(self):
        site_dir = published_site("shackleton-rim-crest")
        manifest = json.loads((site_dir / "manifest.json").read_text(encoding="utf-8"))
        h = manifest["horizon"]["default_height_index"]
        out = run_node(SITE_OBJECT + f"""
          import {{ seriesCsv }} from "{module('csv.js')}";
          const s = loadSite({json.dumps(site_dir.as_posix())});
          const series = {{}};
          for (const b of ["SUN", "EARTH"]) {{
            const r = s.timeline.series[b];
            series[b] = {{ az: s.f4(r.azimuth_deg), el: s.f4(r.elevation_deg), margin: s.row(r.margin_deg, {h}), fraction: s.row(r.visible_fraction, {h}) }};
          }}
          process.stdout.write(seriesCsv([{{ site: s, data: {{ series }}, height: {h} }}]));""")
        lines = out.lstrip("﻿").splitlines()  # text mode has already turned CRLF into LF
        header = lines[0].split(",")
        rows = [dict(zip(header, line.split(","))) for line in lines[1:] if line]
        count = manifest["timeline"]["time"]["count"]
        self.assertEqual(len(rows), 2 * count)

        def f4(ref, row=None):
            data = (site_dir / ref["file"]).read_bytes()
            values = struct.unpack(f"<{len(data) // 4}f", data)
            width = ref["shape"][-1]
            return values if row is None else values[row * width:(row + 1) * width]

        t = manifest["timeline"]
        expected = {}
        for body, name in (("SUN", "Sun"), ("EARTH", "Earth")):
            r = t["series"][body]
            expected[name] = (f4(r["azimuth_deg"]), f4(r["elevation_deg"]), f4(r["margin_deg"], h), f4(r["visible_fraction"], h))
        start, step = t["time"]["start_et_s"], t["time"]["step_s"]
        for row in rows:
            i = int(row["sample_index"])
            az, el, margin, frac = expected[row["body"]]
            # float(text) must give back exactly the stored float32 value: no rounding anywhere.
            self.assertEqual(float(row["azimuth_deg"]), az[i])
            self.assertEqual(float(row["elevation_deg"]), el[i])
            self.assertEqual(float(row["margin_deg"]), margin[i])
            self.assertEqual(float(row["visible_fraction"]), frac[i])
            self.assertEqual(float(row["et_s"]), start + i * step)
            self.assertEqual(row["package_id"], manifest["package_id"])
            self.assertEqual(float(row["observer_height_m"]), manifest["horizon"]["observer_heights_m"][h])


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class PlanningDetailsTests(unittest.TestCase):
    def render(self, edit: str = "") -> str:
        site_dir = published_site("shackleton-rim-crest")
        return run_node(SITE_OBJECT + f"""
          import {{ contract06Html }} from "{module('panel.js')}";
          const s = loadSite({json.dumps(site_dir.as_posix())});
          {edit}
          process.stdout.write(contract06Html(s, s.manifest.horizon.default_height_index));""")

    def test_trade_table_has_one_column_per_height_with_units(self):
        html = self.render()
        heights = json.loads((published_site("shackleton-rim-crest") / "manifest.json").read_text(encoding="utf-8"))["timeline"]["height_trade"]["observer_heights_m"]
        head = re.search(r"Observer-height trade-offs.*?<thead><tr>(.*?)</tr></thead>", html, re.S).group(1)
        self.assertEqual(re.findall(r"<th>([^<]*)</th>", head), ["Quantity"] + [f"{h:g} m" for h in heights])  # JavaScript number format
        body = re.search(r"Observer-height trade-offs.*?<tbody>(.*?)</tbody>", html, re.S).group(1)
        # Read from the package, not pinned: the first quantity at the last height, shown in hours.
        q = json.loads((published_site("shackleton-rim-crest") / "manifest.json").read_text(encoding="utf-8"))["timeline"]["height_trade"]["quantities"][0]
        seconds = q["values"][-1]
        self.assertNotIn(repr(seconds), body)          # raw seconds are not shown
        self.assertIn(f"{seconds / 3600:.1f} h", body)  # formatted as hours

    def test_assumption_sentences_are_shown(self):
        manifest = json.loads((published_site("shackleton-rim-crest") / "manifest.json").read_text(encoding="utf-8"))
        html = self.render()
        u = manifest["timeline"]["uncertainty"]
        import html as html_module
        text = html_module.unescape(html)
        for part in ("horizon_error", "landing_ellipse"):
            self.assertIn(u[part]["assumption"], text, part)

    def test_a_later_minor_version_is_still_shown(self):
        html = self.render('s.manifest.contract.version = "0.7";')
        self.assertIn("Observer-height trade-offs", html)
        self.assertIn("Landing-date tolerance", html)

    def test_missing_planned_landing_is_not_called_infeasible(self):
        html = self.render("for (const o of s.timeline.opportunities) o.planned_landing = null;")
        self.assertIn("No planned landing is stated in the scenario.", html)
        self.assertNotIn("requirement does not hold", html)


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class TerrainGeometryTests(unittest.TestCase):
    """The drawn terrain (js/terrain.js) is the package grid, placed as SPEC 5.9 says."""

    def sites(self):
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        return [INDEX.parent / p["path"] for p in index["packages"] if p["kind"] == "site"]

    def geometry(self, site_dir: Path, reverse: bool = False) -> list[dict]:
        out = run_node(f"""
          import {{ readFileSync }} from "node:fs";
          import {{ terrainGeometry, groundAtSite, patchesFinestFirst }} from "{module('terrain.js')}";
          const dir = {json.dumps(site_dir.as_posix())};
          const m = JSON.parse(readFileSync(dir + "/manifest.json", "utf8"));
          if ({'true' if reverse else 'false'}) m.terrain.patches.reverse();  // order is not part of the contract (0.11)
          const up = {{}};
          for (const p of m.terrain.patches) {{ const b = readFileSync(dir + "/" + p.up_m.file); up[p.id] = new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); }}
          const g = terrainGeometry(m.terrain, up);
          const finest = patchesFinestFirst(m.terrain)[0];
          console.log(JSON.stringify(g.map((x) => ({{ id: x.id, nodeCount: x.nodeCount, kept: x.kept, skippedFiner: x.skippedFiner, skippedNaN: x.skippedNaN,
            surfaceIndexCount: x.surfaceIndexCount, indexCount: x.indices.length, skirtVertices: (x.positions.length / 3) - x.nodeCount,
            positions: Buffer.from(x.positions.buffer, x.positions.byteOffset, x.nodeCount * 12).toString("base64"),
            ground: groundAtSite(finest, up[finest.id]) }}))));""")
        return json.loads(out)

    def test_vertices_are_the_package_grid(self):
        import base64
        for site_dir in self.sites():
            manifest = json.loads((site_dir / "manifest.json").read_text(encoding="utf-8"))
            patches = {p["id"]: p for p in manifest["terrain"]["patches"]}
            for g in self.geometry(site_dir):
                p = patches[g["id"]]
                up = struct.unpack(f"<{p['count_north'] * p['count_east']}f", (site_dir / p["up_m"]["file"]).read_bytes())
                drawn = struct.unpack(f"<{g['nodeCount'] * 3}f", base64.b64decode(g["positions"]))
                f32 = lambda v: struct.unpack("<f", struct.pack("<f", v))[0]
                for i in range(p["count_north"]):
                    for j in range(p["count_east"]):
                        k = (i * p["count_east"] + j) * 3
                        east = p["east_min_m"] + j * p["spacing_m"]
                        north = p["north_min_m"] + i * p["spacing_m"]
                        self.assertEqual(drawn[k], f32(east))
                        self.assertEqual(drawn[k + 2], f32(-north))
                        u = up[i * p["count_east"] + j]
                        if u == u:  # not NaN
                            self.assertEqual(drawn[k + 1], u)

    def test_patches_are_ordered_by_spacing_not_by_list_position(self):
        # SPEC 5.9 since 0.11: select patches by id; the list order is not part of the contract.
        for site_dir in self.sites():
            as_written, reversed_list = self.geometry(site_dir), self.geometry(site_dir, reverse=True)
            self.assertEqual(as_written, reversed_list)
            spacings = [g["id"] for g in as_written]
            manifest = json.loads((site_dir / "manifest.json").read_text(encoding="utf-8"))
            by_id = {p["id"]: p["spacing_m"] for p in manifest["terrain"]["patches"]}
            self.assertEqual([by_id[i] for i in spacings], sorted(by_id.values()))

    def test_each_place_is_drawn_once_by_the_finest_patch(self):
        for site_dir in self.sites():
            manifest = json.loads((site_dir / "manifest.json").read_text(encoding="utf-8"))
            # Finest first by spacing; the order of the list is not part of the contract (0.11).
            patches = sorted(manifest["terrain"]["patches"], key=lambda p: p["spacing_m"])
            for k, (p, g) in enumerate(zip(patches, self.geometry(site_dir))):
                cells = (p["count_north"] - 1) * (p["count_east"] - 1)
                if k == 0:
                    self.assertEqual(g["skippedFiner"], 0)
                else:
                    finer = patches[k - 1]
                    # The finer square's edge lies on this patch's grid lines, so the cut is exact.
                    self.assertEqual((finer["half_width_m"] - p["east_min_m"]) % p["spacing_m"], 0)
                    inner = int(2 * finer["half_width_m"] / p["spacing_m"])
                    self.assertEqual(g["skippedFiner"], inner * inner)
                self.assertEqual(g["kept"] + g["skippedFiner"] + g["skippedNaN"], cells)
                self.assertEqual(g["surfaceIndexCount"], 6 * g["kept"])
                # Skirts below every patch but the coarsest.
                self.assertEqual(g["skirtVertices"] > 0, k < len(patches) - 1, p["id"])

    def test_observer_stands_on_the_centre_node(self):
        for site_dir in self.sites():
            manifest = json.loads((site_dir / "manifest.json").read_text(encoding="utf-8"))
            p = manifest["terrain"]["patches"][0]
            up = struct.unpack(f"<{p['count_north'] * p['count_east']}f", (site_dir / p["up_m"]["file"]).read_bytes())
            centre = up[(p["count_north"] // 2) * p["count_east"] + p["count_east"] // 2]
            self.assertEqual(self.geometry(site_dir)[0]["ground"], centre)


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class TerrainSourceTests(unittest.TestCase):
    """horizon.terrain_source (contract 0.9): a class other than fine is shown as a warning."""

    def render(self, edit: str = "") -> str:
        site_dir = published_site("shackleton-rim-crest")
        return run_node(SITE_OBJECT + f"""
          import {{ terrainSourceHtml }} from "{module('panel.js')}";
          const s = loadSite({json.dumps(site_dir.as_posix())});
          {edit}
          process.stdout.write(terrainSourceHtml(s));""")

    def test_fine_site_is_stated_without_a_warning(self):
        html = self.render()
        at = json.loads((published_site("shackleton-rim-crest") / "manifest.json").read_text(encoding="utf-8"))["horizon"]["terrain_source"]["at_site"]
        self.assertIn(f"Terrain: fine ({at['product_id']}, {at['pixel_m']:g} m pixels at the site)", html)
        self.assertNotIn("terrain-warn", html)

    def test_coarse_site_is_warned_with_the_package_warning(self):
        html = self.render("""
          s.manifest.horizon.terrain_source.resolution_class = "coarse";
          s.manifest.horizon.terrain_source.at_site = { product_id: "LDEM_16", pixel_m: 1895 };
          s.manifest.warnings = ["Terrain at the site from LDEM_16 with 1895 m pixels."];""")
        self.assertIn("terrain-warn", html)
        self.assertIn("Terrain: coarse (LDEM_16, 1895 m pixels at the site)", html)
        self.assertIn("Relief narrower than about two pixels is not in this horizon", html)
        self.assertIn("Terrain at the site from LDEM_16 with 1895 m pixels.", html)

    def test_older_packages_show_nothing(self):
        self.assertEqual(self.render("delete s.manifest.horizon.terrain_source;"), "")


@unittest.skipUnless(NODE, "node is missing")
class SiteSelectorTests(unittest.TestCase):
    """Site selectors for a list of about 20 sites (contract 0.11 adds `programme` to the index)."""

    def options(self, sites) -> str:
        return run_node(f"""
          import {{ siteOptionsHtml }} from "{module('panel.js')}";
          process.stdout.write(siteOptionsHtml({json.dumps(sites)}));""")

    def test_grouped_by_programme_with_index_positions_kept(self):
        html = self.options([
            {"site_id": "a1", "name": "Apollo 11", "programme": "Apollo"},
            {"site_id": "s", "name": "Shackleton", "programme": "Project sites"},
            {"site_id": "a12", "name": "Apollo 12", "programme": "Apollo"},
            {"site_id": "x", "name": "No programme"},
        ])
        self.assertEqual(html,
            '<optgroup label="Apollo"><option value="0">Apollo 11</option><option value="2">Apollo 12</option></optgroup>'
            '<optgroup label="Project sites"><option value="1">Shackleton</option></optgroup>'
            '<optgroup label="Other sites"><option value="3">No programme</option></optgroup>')

    def test_flat_list_without_programmes(self):
        html = self.options([{"site_id": "a", "name": "A"}, {"site_id": "b"}])
        self.assertEqual(html, '<option value="0">A</option><option value="1">b</option>')


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class OpportunityCalendarTests(unittest.TestCase):
    """Task 9: the calendar shows timeline.calendar and timeline.opportunities as published."""

    A, B = "shackleton-rim-crest", "apollo-11"

    def manifest(self, site_id):
        return json.loads((published_site(site_id) / "manifest.json").read_text(encoding="utf-8"))

    def render(self, entries, req=None, edit=""):
        # entries: [(site_id, height_index)]
        load = "".join(f"const s{k} = loadSite({json.dumps(published_site(sid).as_posix())});\n" for k, (sid, _) in enumerate(entries))
        items = ", ".join(f"{{ site: s{k}, h: {h}, name: {json.dumps(sid)} }}" for k, (sid, h) in enumerate(entries))
        return run_node(SITE_OBJECT + f"""
          import {{ calendarHtml }} from "{module('calendar.js')}";
          {load}{edit}
          process.stdout.write(calendarHtml([{items}], {{ requirementId: {json.dumps(req)} }}));""")

    def table_rows(self, html):
        body = re.search(r"<details.*?<tbody>(.*?)</tbody>", html, re.S).group(1)
        return [re.findall(r"<td[^>]*>([^<]*)</td>", row) for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]

    def test_values_are_the_package_values_at_the_selected_heights(self):
        ha, hb = 4, 1  # 10 m at Shackleton, 2 m at Apollo 11: not the default heights
        html = self.render([(self.A, ha), (self.B, hb)], "example-standard")
        rows = self.table_rows(html)
        ma, mb = self.manifest(self.A), self.manifest(self.B)
        periods = ma["timeline"]["calendar"]["periods"]
        self.assertEqual(len(rows), len(periods))
        expected_cols = []
        for m, h in ((ma, ha), (mb, hb)):
            for q in m["timeline"]["calendar"]["quantities"]:
                expected_cols.append([v for v in q["values"][h]])
            o = next(o for o in m["timeline"]["opportunities"] if o["requirement_id"] == "example-standard" and o["height_index"] == h)
            expected_cols.append(o["feasible_s_per_period"])
        for j, (row, p) in enumerate(zip(rows, periods)):
            self.assertEqual(row[:4], [str(p["index"]), p["start_utc"], p["end_utc"], "complete" if p["complete"] else "incomplete"])
            self.assertEqual(row[4:], [f"{col[j] / 3600:.1f} h" for col in expected_cols], f"lunar day {j}")

    def test_two_sites_share_one_time_axis(self):
        html = self.render([(self.A, 2), (self.B, 1)])
        # Every row draws the same lunar days at the same x positions.
        rows = re.findall(r'<g class="cal-cell" data-et="([^"]+)"[^>]*><title>[^<]*</title><rect x="([^"]+)"', html)
        by_period = {}
        for et, xpos in rows:
            by_period.setdefault(et, set()).add(xpos)
        periods = self.manifest(self.A)["timeline"]["calendar"]["periods"]
        for p in periods:
            self.assertEqual(len(by_period[repr(p["start_et_s"]) if repr(p["start_et_s"]) in by_period else str(p["start_et_s"])]), 1)

    def test_incomplete_lunar_days_are_marked(self):
        html = self.render([(self.A, 2), (self.B, 1)])
        periods = self.manifest(self.A)["timeline"]["calendar"]["periods"]
        incomplete = sum(not p["complete"] for p in periods)
        rows = len(self.manifest(self.A)["timeline"]["calendar"]["quantities"]) * 2
        self.assertEqual(html.count('fill="url(#cal-hatch)"'), incomplete * rows)
        self.assertEqual(html.count("incomplete: cut by the end of the computed range"), incomplete * rows)

    def test_requirement_label_conditions_status_and_planned_landing(self):
        m = self.manifest(self.A)
        req = next(r for r in m["request"]["timeline"]["requirements"] if r["id"] == "example-strict")
        html = self.render([(self.A, 2)], "example-strict")
        import html as html_module
        text = html_module.unescape(html)
        self.assertIn(req["label"], text)
        self.assertIn(f"[{m['methods']['timeline.opportunity']['validation']['status']}]", text)
        self.assertIn(f"[{m['methods']['timeline.calendar']['validation']['status']}]", text)
        o = next(o for o in m["timeline"]["opportunities"] if o["requirement_id"] == "example-strict" and o["height_index"] == 2)
        self.assertIn(f"{o['feasible_fraction'] * 100:.1f} %", text)
        self.assertIn(o["latest_landing_utc"], text)
        self.assertEqual(text.count('fill="#3fb950"'), o["window_count"])  # one bar per published window
        p = o["planned_landing"]
        if p:
            self.assertIn(p["utc"], text)
            if not p["feasible"] and p["wait_s"] is not None:
                self.assertIn(f"wait {p['wait_s'] / 3600:.1f} h", text)

    def test_missing_fields_are_stated_not_invented(self):
        html = self.render([(self.A, 2)], "example-standard", edit="s0.manifest.timeline.opportunities.forEach((o) => { o.planned_landing = null; });")
        self.assertIn("No planned landing is stated in the scenario, so there is no slip tolerance or wait time.", html)
        html = self.render([(self.A, 2), (self.B, 1)], None, edit="delete s1.timeline.calendar;")
        self.assertIn("apollo-11: this package has no <code>timeline.calendar</code>", html)
        html = self.render([(self.A, 2)], None, edit="delete s0.timeline.opportunities;")
        self.assertIn("No landing requirement is stated in these packages", html)


@unittest.skipUnless(NODE and INDEX.exists(), "node or the published packages are missing")
class StatusCardTests(unittest.TestCase):
    """Status cards of the comparison: lookups in the package, checked against Python lookups."""

    SITE = "shackleton-rim-crest"

    def manifest(self):
        return json.loads((published_site(self.SITE) / "manifest.json").read_text(encoding="utf-8"))

    def cards(self, h, i, req="example-standard", edit=""):
        return run_node(SITE_OBJECT + f"""
          import {{ statusCardsHtml }} from "{module('status.js')}";
          import {{ sampleEt }} from "{module('panel.js')}";
          const s = loadSite({json.dumps(published_site(self.SITE).as_posix())});
          {edit}
          process.stdout.write(statusCardsHtml(s, {h}, sampleEt(s, {i}), {json.dumps(req)}));""")

    @staticmethod
    def duration(seconds):
        m = int(seconds // 60); h = m // 60; d = h // 24
        return f"{d} d {h % 24} h" if d else f"{h} h {m % 60} min" if h else f"{m} min" if m else "under 1 min"

    def test_sun_and_earth_cards_follow_windows_and_events(self):
        m = self.manifest()
        t = m["timeline"]
        for h in (0, 2, 4):
            for i in (0, 1234, 8000, 15000):
                et = t["time"]["start_et_s"] + i * t["time"]["step_s"]
                html = self.cards(h, i)
                for body, name in (("SUN", "Sun"), ("EARTH", "Earth")):
                    w = next(w for w in t["windows"] if w["id"] == f"{body.lower()}_visible" and w["height_index"] == h)
                    visible = any(a <= et <= b for a, b in w["intervals_et_s"])
                    card = re.search(rf'<div class="status-title">{name}</div>(.*?)</div></div>', html, re.S).group(1)
                    self.assertIn("Visible now" if visible else "Not visible now", card, (h, i, body))
                    nxt = next((e for e in t["events"] if e["body"] == body and e["height_index"] == h and e["et_s"] > et), None)
                    if nxt:
                        verb = "Sets" if nxt["type"] == "set" else "Rises"
                        self.assertIn(f"{verb} in <strong>{self.duration(nxt['et_s'] - et)}</strong>", card, (h, i, body))
                        self.assertIn(nxt["utc"][:16].replace("T", " "), card)

    def test_landing_card_follows_the_published_landing_windows(self):
        m = self.manifest()
        t = m["timeline"]
        for i in (0, 1234, 8000):
            et = t["time"]["start_et_s"] + i * t["time"]["step_s"]
            o = next(o for o in t["opportunities"] if o["requirement_id"] == "example-standard" and o["height_index"] == 2)
            html = self.cards(2, i)
            inside = any(a <= et <= b for a, b in o["landing_windows_et_s"])
            if et > o["latest_landing_et_s"]:
                self.assertIn("Cannot be judged", html)
            elif inside:
                self.assertIn("Satisfied", html)
            else:
                self.assertIn("Not satisfied", html)
                nxt = next((a for a, b in o["landing_windows_et_s"] if a > et), None)
                if nxt:
                    self.assertIn(f"opens in <strong>{self.duration(nxt - et)}</strong>", html)
            self.assertIn("Example requirement, not a mission criterion", html)

    def test_landing_not_specified_without_requirements(self):
        html = self.cards(2, 0, edit="s.timeline.opportunities = [];")
        self.assertIn("Not specified", html)

    def test_package_countdown_keeps_its_reference(self):
        m = self.manifest()
        ref = next(x for x in m["timeline"]["metrics"] if x["id"] == "sun_time_to_set_s" and x["height_index"] == 2)["reference"]
        out = run_node(SITE_OBJECT + f"""
          import {{ countdownHtml }} from "{module('status.js')}";
          const s = loadSite({json.dumps(published_site(self.SITE).as_posix())});
          const a = countdownHtml(s, 2);
          s.timeline.metrics.forEach((x) => {{ delete x.reference; }});
          s.manifest.request.timeline.landing_utc = null;
          process.stdout.write(JSON.stringify([a, countdownHtml(s, 2)]));""")
        with_ref, fallback = json.loads(out)
        self.assertIn(ref["utc"], with_ref)
        self.assertIn(ref["is"], with_ref)
        self.assertIn("not from the selected time", with_ref)
        self.assertIn(m["timeline"]["time"]["start_utc"], fallback)  # no landing in the request: start of the window
        self.assertIn("rule of SPEC 5.4 for packages before contract 0.10", fallback)


if __name__ == "__main__":
    unittest.main()
