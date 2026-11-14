"""Acceptance tests for the static charts (horizon panorama and window strip).

Done when: a chart can be rebuilt from a frozen package, and every chart states the
reference frame, the sphere radius, the UTC range and the package id.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from lsn_web import charts, package

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "contract-sample" / "packages"
SITE_DIR = FIXTURE / "site" / "synthetic-sample-site" / "site-a02ee316b65e2af1"
SVG = "{http://www.w3.org/2000/svg}"


def manifest() -> dict:
    return json.loads((SITE_DIR / "manifest.json").read_text(encoding="utf-8"))


def raw_f4(name: str) -> list[float]:
    data = (SITE_DIR / name).read_bytes()
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def plot_box(root: ET.Element) -> dict:
    group = root.find(f".//{SVG}g[@id='plot']")
    assert group is not None, "chart has no plot group"
    return {key: float(group.get(f"data-{key}")) for key in ("x0", "x1", "y0", "y1", "xmin", "xmax", "ymin", "ymax")}


def invert_x(box: dict, px: float) -> float:
    return box["xmin"] + (px - box["x0"]) / (box["x1"] - box["x0"]) * (box["xmax"] - box["xmin"])


def invert_y(box: dict, py: float) -> float:
    return box["ymin"] + (box["y1"] - py) / (box["y1"] - box["y0"]) * (box["ymax"] - box["ymin"])


def all_text(root: ET.Element) -> str:
    return " ".join("".join(node.itertext()) for node in root.iter(f"{SVG}text"))


class ReaderTests(unittest.TestCase):
    def test_reads_the_sample_package(self):
        site = package.load_site_package(SITE_DIR)
        self.assertEqual(site.package_id, "site-a02ee316b65e2af1")
        elevation = site.array(site.manifest["horizon"]["elevation_deg"])
        self.assertEqual(elevation.shape, (6, 1440))
        self.assertEqual(elevation.values, raw_f4("horizon_elevation_deg.f4"))

    def test_rejects_a_changed_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / SITE_DIR.name
            shutil.copytree(SITE_DIR, copy)
            data = bytearray((copy / "horizon_elevation_deg.f4").read_bytes())
            data[0] ^= 0x01
            (copy / "horizon_elevation_deg.f4").write_bytes(bytes(data))
            site = package.load_site_package(copy)
            with self.assertRaises(package.PackageError):
                site.array(site.manifest["horizon"]["elevation_deg"])

    def test_refuses_another_contract_major_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / SITE_DIR.name
            shutil.copytree(SITE_DIR, copy)
            document = manifest()
            document["contract"]["version"] = "1.0"
            (copy / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(package.PackageError):
                package.load_site_package(copy)


class PanoramaTests(unittest.TestCase):
    def setUp(self):
        self.site = package.load_site_package(SITE_DIR)
        self.svg = charts.horizon_panorama(self.site)
        self.root = ET.fromstring(self.svg)

    def test_rebuild_gives_identical_bytes(self):
        self.assertEqual(self.svg, charts.horizon_panorama(package.load_site_package(SITE_DIR)))

    def test_states_frame_radius_utc_and_package_id(self):
        text = all_text(self.root)
        document = manifest()
        self.assertIn(document["package_id"], text)
        self.assertIn(document["site"]["frame"], text)
        self.assertIn("1700 km", text)  # site.reference_radius_m = 1 700 000 m
        self.assertIn(document["timeline"]["time"]["start_utc"], text)
        self.assertIn(document["timeline"]["time"]["end_utc"], text)
        self.assertIn("UTC", text)

    def test_marks_synthetic_data(self):
        self.assertIn("SYNTHETIC", all_text(self.root))

    def test_horizon_line_is_the_package_profile(self):
        document = manifest()
        heights, count = 6, document["horizon"]["azimuth"]["count"]
        step = document["horizon"]["azimuth"]["step_deg"]
        index = document["horizon"]["default_height_index"]
        expected = raw_f4("horizon_elevation_deg.f4")[index * count:(index + 1) * count]
        self.assertEqual(len(raw_f4("horizon_elevation_deg.f4")), heights * count)

        line = self.root.find(f".//{SVG}polyline[@id='horizon']")
        self.assertIsNotNone(line)
        points = [tuple(map(float, pair.split(","))) for pair in line.get("points").split()]
        self.assertEqual(len(points), count + 1)  # closed: 360 deg repeats 0 deg
        box = plot_box(self.root)
        for i, (px, py) in enumerate(points):
            self.assertAlmostEqual(invert_x(box, px), i * step, delta=0.01)
            self.assertAlmostEqual(invert_y(box, py), expected[i % count], delta=0.001)

    def test_draws_sun_and_earth_tracks_from_the_series(self):
        for body in ("sun", "earth"):
            self.assertIsNotNone(self.root.find(f".//{SVG}path[@id='{body}-track']"), body)


class WindowStripTests(unittest.TestCase):
    def setUp(self):
        self.site = package.load_site_package(SITE_DIR)
        self.svg = charts.window_strip([self.site])
        self.root = ET.fromstring(self.svg)

    def test_rebuild_gives_identical_bytes(self):
        self.assertEqual(self.svg, charts.window_strip([package.load_site_package(SITE_DIR)]))

    def test_states_frame_radius_utc_and_package_id(self):
        text = all_text(self.root)
        document = manifest()
        self.assertIn(document["package_id"], text)
        self.assertIn(document["site"]["frame"], text)
        self.assertIn("1700 km", text)
        self.assertIn(document["timeline"]["time"]["start_utc"], text)
        self.assertIn(document["timeline"]["time"]["end_utc"], text)
        self.assertIn("SYNTHETIC", text)

    def test_bars_are_the_package_intervals(self):
        document = manifest()
        index = document["horizon"]["default_height_index"]
        box = plot_box(self.root)
        windows = [w for w in document["timeline"]["windows"] if w["height_index"] == index]
        self.assertEqual({w["subject"] for w in windows}, {"SUN", "EARTH", "COMBINED"})
        span = box["xmax"] - box["xmin"]
        for window in windows:
            bars = self.root.findall(f".//{SVG}rect[@data-window='{window['id']}']")
            self.assertEqual(len(bars), len(window["intervals_et_s"]), window["id"])
            for bar, (start, end) in zip(bars, window["intervals_et_s"]):
                x, width = float(bar.get("x")), float(bar.get("width"))
                self.assertAlmostEqual(invert_x(box, x), start, delta=span * 1e-5)
                self.assertAlmostEqual(invert_x(box, x + width), end, delta=span * 1e-5)

    def test_time_axis_is_utc_dates(self):
        labels = [t.text for t in self.root.iter(f"{SVG}text") if t.get("class") == "tick-time"]
        self.assertTrue(labels)
        for label in labels:
            self.assertRegex(label, re.compile(r"^\d{4}-\d{2}-\d{2}$"))


class CommandLineTests(unittest.TestCase):
    def test_writes_one_panorama_per_site_and_one_strip(self):
        with tempfile.TemporaryDirectory() as tmp:
            charts.main([str(SITE_DIR), "--out", tmp])
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["horizon_panorama__synthetic-sample-site.svg", "window_strip.svg"])


if __name__ == "__main__":
    unittest.main()
