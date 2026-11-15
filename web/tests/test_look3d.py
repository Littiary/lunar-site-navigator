"""The look of the 3-D ground view (web/viewer/js/look3d.js) changes pixels, never the science.

The bloom and tone-mapping path, the Earth's map and the regolith shading must not move the Sun
or the Earth, change their drawn size, or change the package horizon line or its colours. The
static tests read the source; the browser test (Playwright, skipped when it is not installed)
draws the same package input on the post-processed path and on the direct path and compares
what view3d.js reports back.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import os
import re
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

VIEWER = Path(__file__).resolve().parents[1] / "viewer"
NUMERIC = re.compile(r"Math\.(sin|cos|tan|asin|acos|atan|atan2|sqrt|cbrt|pow|exp|log|log10|log2|hypot|sinh|cosh|tanh)\b")


def strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(line.split("//")[0] if "//" in line and "http" not in line else line for line in source.splitlines())


def read(name: str) -> str:
    return (VIEWER / "js" / name).read_text(encoding="utf-8")


def function_body(code: str, name: str) -> str:
    start = code.index(f"function {name}(")
    depth, i = 0, code.index("{", start)
    for j in range(i, len(code)):
        depth += {"{": 1, "}": -1}.get(code[j], 0)
        if depth == 0:
            return code[i:j + 1]
    raise AssertionError(name)


class LookPlacesNothingTests(unittest.TestCase):
    def test_look_module_moves_scales_or_hides_nothing_and_reads_no_package_value(self):
        code = strip_comments(read("look3d.js"))
        self.assertEqual(NUMERIC.findall(code), [])
        for pattern in (r"\.position\.(set|copy|add|multiply)", r"\.scale\.", r"\.quaternion\.", r"\.rotation\.", r"\.visible\s*=", r"\.lookAt\("):
            self.assertEqual(re.findall(pattern, code), [], pattern)
        for field in ("horizon", "azimuth", "fraction", "elevation", "angular_radius", "direction("):
            self.assertNotIn(field, code)
        self.assertNotIn("Fog", code)
        self.assertNotIn("Sprite", code)
        self.assertNotIn("interpolat", code.lower())

    def test_bodies_are_placed_the_same_on_every_render_path(self):
        code = strip_comments(read("view3d.js"))
        place = function_body(code, "placeBodies")
        # Position and size come from the package fields only, as before the new look.
        self.assertIn("mesh.position.copy(d).multiplyScalar(SKY_R).add(eye)", place)
        self.assertIn("radiusAt(SKY_R, Number.isFinite(body.r) ? body.r : 0.25)", place)
        # Nothing in the placement depends on the render path.
        for word in ("quality", "pipeline", "bloom", "Q.", "composer"):
            self.assertNotIn(word, place)
        # The Earth's globe turns about its centre only (its map); position and scale are set above.
        self.assertIn("earthGlobe.quaternion", place)
        raw = read("view3d.js")
        frame = raw[raw.index("export function earthFrame("):raw.index("// display-transform:end")]
        self.assertNotIn("position", frame)

    def test_horizon_line_and_outlines_are_drawn_after_the_tone_mapping(self):
        code = strip_comments(read("view3d.js"))
        build = function_body(code, "buildScene")
        self.assertIn("overlay.add(line, dots)", build)
        self.assertIn("overlay.add(edges)", build)
        self.assertNotRegex(build, r"scene\.add\([^)]*\b(line|dots|edges)\b")
        self.assertIn("toneMapped: false", build)  # line and dots keep the legend colours
        self.assertIn("distanceColor(next.distance ? next.distance[k % n]", build)
        look = strip_comments(read("look3d.js"))
        render = look[look.index("render() {"):look.index("dispose()")]
        self.assertLess(render.index("composer.render()"), render.index("renderer.render(overlay, camera)"))
        self.assertLess(render.index("renderer.render(scene, camera)"), render.index("renderer.render(overlay, camera)"))

    def test_tone_mapping_bloom_and_quality_paths(self):
        look = strip_comments(read("look3d.js"))
        view = strip_comments(read("view3d.js"))
        self.assertIn("renderer.toneMapping = THREE.ACESFilmicToneMapping", view)
        self.assertIn("renderer.outputColorSpace = THREE.SRGBColorSpace", view)
        self.assertIn("THREE.PCFSoftShadowMap", view)
        self.assertIn("new UnrealBloomPass(", look)
        self.assertIn("new OutputPass()", look)
        self.assertIn("samples: webgl2 ? 2 : 0", look)          # MSAA in the half-float target
        self.assertIn('low: { bloom: false, shadowMap: 2048', look)
        self.assertIn('(pointer: coarse)', look)
        # A Sun the package puts wholly below the horizon gets no glow: its radiance drops below
        # the bloom threshold and the corona is hidden.
        self.assertIn("const sunHidden = Boolean(next.sun) && next.sun.fraction === 0", view)
        self.assertIn("sunLook.uniforms.radiance.value = sunHidden ? 1 : SUN_RADIANCE", view)
        self.assertIn("corona.visible = !sunHidden", view)
        threshold = float(re.search(r"threshold: ([0-9.]+)", look).group(1))
        radiance = float(re.search(r"SUN_RADIANCE = ([0-9.]+)", look).group(1))
        self.assertGreater(threshold, 1)
        self.assertGreater(radiance, threshold)

    def test_addons_are_imported_locally(self):
        look = read("look3d.js")
        imports = re.findall(r"""from\s+["']([^"']+)["']""", look)
        self.assertTrue(imports)
        for path in imports:
            self.assertTrue(path == "three" or path.startswith("../vendor/three/addons/"), path)
        self.assertEqual(re.findall(r"https?://", strip_comments(look)), [])


class VendoredFilesTests(unittest.TestCase):
    def test_addons_are_the_recorded_files_of_the_same_three_version(self):
        folder = VIEWER / "vendor" / "three" / "addons"
        readme = (folder / "README.md").read_text(encoding="utf-8")
        self.assertIn("three-0.160.0.tgz", readme)
        files = sorted(p for p in folder.rglob("*.js"))
        self.assertEqual(len(files), 10)
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertIn(digest, readme, path.name)
            for spec in re.findall(r"""from\s+['"]([^'"]+)['"]""", path.read_text(encoding="utf-8")):
                self.assertTrue(spec == "three" or spec.startswith("./") or spec.startswith("../shaders/"), spec)

    def test_earth_map_is_the_recorded_file(self):
        folder = VIEWER / "vendor" / "earth"
        readme = (folder / "README.md").read_text(encoding="utf-8")
        digest = hashlib.sha256((folder / "blue_marble_2048.jpg").read_bytes()).hexdigest()
        self.assertIn(digest, readme)
        self.assertIn("https://visibleearth.nasa.gov/images/73909", readme)
        self.assertIn('"../vendor/earth/blue_marble_2048.jpg"', read("look3d.js"))
        credits = (VIEWER.parents[1] / "CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("web/viewer/vendor/earth/blue_marble_2048.jpg", credits)
        self.assertIn("web/viewer/vendor/three/addons", credits)


# One package-shaped input for the browser test: a profile with a ridge, the Sun partly above it
# and the Earth well above it, and a pole direction for the Earth's map.
INPUT = """{
  siteId: 'look-test', h: 0, observerHeight: 2, terrain: null, up: {},
  azimuth: { start_deg: 0, step_deg: 1, count: 360 },
  horizon: Array.from({ length: 360 }, (_, k) => 1 + (k > 150 && k < 210 ? 2.5 : 0) + (k % 7) * 0.05),
  distance: Array.from({ length: 360 }, (_, k) => 500 + 300 * k),
  sun: { az: 180.25, el: 3.4, r: 0.2667, fraction: 0.62 },
  earth: { az: 12.5, el: 21.75, r: 0.9525, fraction: 1 },
  subLunar: { lat: -4.2, lon: 7.5 }, hud: '', hudSummary: ''
}"""


@unittest.skipUnless(sync_playwright, "Playwright is not installed")
class RenderPathRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(VIEWER)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL"), args=["--enable-unsafe-swiftshader"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_bloom_path_and_direct_path_draw_the_same_sun_earth_and_horizon(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{self.server.server_port}/viewer.css")
        page.set_content('''<script type="importmap">{"imports":{"three":"/vendor/three/three.module.js"}}</script>
          <div id="a" style="width:640px;height:360px"></div><div id="b" style="width:640px;height:360px"></div>''')
        result = page.evaluate(f'''async () => {{
          const THREE = await import('three');
          const {{ createView }} = await import('/js/view3d.js');
          const input = {INPUT};
          input.earthPole = new THREE.Vector3(0.1, 0.9, -0.42);
          const out = {{}};
          for (const [id, quality] of [['a', 'high'], ['b', 'low']]) {{
            let check = null;
            const v = createView(document.getElementById(id), {{ quality, onCheck: (t) => {{ check = t; }} }});
            v.update(input);
            await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
            out[quality] = {{ look: v.look(), bodies: v.bodies(), check: v.check(), text: check, ring: v.ringColors(), labels: v.labelState() }};
          }}
          return out;
        }}''')
        self.assertEqual(errors, [])
        high, low = result["high"], result["low"]
        self.assertTrue(high["look"]["bloom"])
        self.assertFalse(low["look"]["bloom"])
        self.assertEqual(high["bodies"], low["bodies"])        # same positions, sizes, visibility
        self.assertEqual(high["check"], low["check"])          # horizon line read back
        self.assertLess(high["check"]["maxElevationDiffDeg"], 1e-3)
        self.assertEqual(high["text"], low["text"])
        self.assertEqual(high["ring"], low["ring"])            # horizon line colours
        page.close()


if __name__ == "__main__":
    unittest.main()
