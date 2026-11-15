"""Browser acceptance tests. Requires Playwright and its Chromium browser.

Run: python -m unittest discover -s web/tests -p test_viewport_resize.py
"""
import functools
import http.server
import os
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Playwright is not installed")
class ViewportResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1] / "viewer"
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
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
        cls.thread.join()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 1000}, device_scale_factor=1.5)
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(f"http://127.0.0.1:{self.server.server_port}/viewer.css")
        self.page.set_content('''<link rel="stylesheet" href="/viewer.css">
          <script type="importmap">{"imports":{"three":"/vendor/three/three.module.js"}}</script>
          <main><div id="globe" class="view3d"></div>
          <div class="split"><section class="pane"><div id="left" class="view3d pane-ground"></div></section>
          <section class="pane"><div id="right" class="view3d pane-ground"></div></section></div>
          <div id="single" class="view3d"></div></main>''')
        self.page.evaluate('''async () => {
          const THREE = await import('three');
          window.cameras = [];
          const original = THREE.PerspectiveCamera.prototype.updateProjectionMatrix;
          THREE.PerspectiveCamera.prototype.updateProjectionMatrix = function () {
            if (!cameras.includes(this)) cameras.push(this);
            return original.call(this);
          };
          const {createGlobe} = await import('/js/globe.js');
          const {createView} = await import('/js/view3d.js');
          const viewCameras = [];
          const capture = create => { const view = create(); viewCameras.push(cameras.at(-1)); return view; };
          window.views = [capture(() => createGlobe(document.querySelector('#globe'))),
            ...['left', 'right', 'single'].map(id => capture(() => createView(document.getElementById(id))))];
          window.cameras = viewCameras;
          THREE.PerspectiveCamera.prototype.updateProjectionMatrix = original;
          views[0].update({sites: [], sun: [1,0,0], earth: [0,1,0]});
          views.forEach(v => v.resize());
        }''')
        self.settle()

    def tearDown(self):
        self.page.close()

    def settle(self):
        self.page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def size(self, selector):
        return self.page.locator(selector).evaluate("e => [e.clientWidth, e.clientHeight]")

    def drag(self, selector, axis, dx, dy):
        handle = self.page.locator(f'{selector} .viewport-resize-{axis}')
        handle.scroll_into_view_if_needed()
        box = handle.bounding_box()
        x, y = box['x'] + box['width']/2, box['y'] + box['height']/2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + dx, y + dy, steps=5)
        self.page.mouse.up()
        self.settle()

    def assert_canvas(self, selector, camera_index):
        self.assertTrue(self.page.locator(selector).evaluate('''(e, i) => {
          const c = e.querySelector('canvas'), camera = cameras[i];
          return c.width === Math.floor(e.clientWidth * 1.5) && c.height === Math.floor(e.clientHeight * 1.5)
            && Math.abs(camera.aspect - e.clientWidth / e.clientHeight) < 1e-9;
        }''', camera_index))

    def test_height_only_updates_both_renderers(self):
        for i, selector in enumerate(['#globe', '#left', '#right']):
            before = self.size(selector)
            self.page.locator(selector).evaluate('(e) => { e.style.height = `${e.clientHeight + 80}px`; }')
            self.settle()
            self.assertEqual(self.size(selector)[0], before[0])
            self.assert_canvas(selector, i)

    def test_edges_corner_keyboard_bounds_and_mobile(self):
        self.assertEqual(self.page.locator('#single .viewport-resize').count(), 0)
        for i, selector in enumerate(['#globe', '#left', '#right']):
            self.page.evaluate('views.forEach((v,i) => v.command(i ? "zoom-in" : "globe-zoom-in"))')
            self.settle()
            camera = self.page.evaluate('(i) => ({fov:cameras[i].fov, position:cameras[i].position.toArray(), quaternion:cameras[i].quaternion.toArray()})', i)
            neighbor = self.size('#right' if selector == '#left' else '#left')
            w, h = self.size(selector)
            self.drag(selector, 'e', -90, 0)
            self.assertAlmostEqual(self.size(selector)[0], w-90, delta=2)
            self.assertAlmostEqual(self.size(selector)[1], h, delta=2)
            self.drag(selector, 's', 0, 70)
            self.assertAlmostEqual(self.size(selector)[1], h+70, delta=2)
            self.drag(selector, 'se', 40, 40)
            self.assert_canvas(selector, i)
            self.assertEqual(camera, self.page.evaluate('(i) => ({fov:cameras[i].fov, position:cameras[i].position.toArray(), quaternion:cameras[i].quaternion.toArray()})', i))
            self.assertEqual(neighbor, self.size('#right' if selector == '#left' else '#left'))
            before = self.size(selector)
            self.page.locator(f'{selector} .viewport-resize-e').press('ArrowLeft')
            self.settle()
            self.assertEqual(self.size(selector)[0], before[0]-10)
            self.drag(selector, 'se', 3000, 3000)
            self.assertTrue(self.page.locator(selector).evaluate('e => e.getBoundingClientRect().right <= e.parentElement.getBoundingClientRect().right && e.clientHeight <= 1200'))
        self.page.set_viewport_size({"width":390,"height":844})
        self.settle()
        self.assertEqual(self.page.locator('.viewport-resize:visible').count(), 0)
        for selector in ['#globe', '#left', '#right']:
            self.assertEqual(self.page.locator(selector).evaluate('e => e.style.width + e.style.height'), '')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        self.assertEqual(self.errors, [])
