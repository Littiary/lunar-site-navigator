// 3-D view of a site package with three.js.
//
// The observer stands at the origin. The terrain horizon of the package is drawn on a sphere
// of radius R around the observer: for azimuth sample k (azimuth start_deg + k * step_deg)
// the edge of the terrain is at the package's horizon elevation. The Sun and the Earth are
// drawn farther out, in the directions given by the package series, so that the terrain hides
// them exactly when they are below its horizon. Markers are not to scale.
//
// The only trigonometry is the display transform between (azimuth, elevation) and a screen
// direction, in the marked block below; no scientific value is computed here.
//
// Ground view (Task 8 B): the horizon ring is coloured by the distance of the terrain that sets
// the horizon in each azimuth (horizon.distance_m of the package), in fixed classes.

import * as THREE from "three";

const R = 100;          // radius of the terrain sphere
const R_BODY = 160;     // Sun and Earth: behind the terrain
const BOTTOM_DEG = -60; // lower edge of the terrain curtain

// display-transform:start
// Three.js is y-up. North is -z, east is +x; azimuth is clockwise from north (SPEC 2).
const RAD = Math.PI / 180;
export function direction(azDeg, elDeg) {
  const a = azDeg * RAD, e = elDeg * RAD;
  return new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e));
}
export function azEl(v) {
  const n = v.clone().normalize();
  return [((Math.atan2(n.x, -n.z) / RAD) + 360) % 360, Math.asin(Math.max(-1, Math.min(1, n.y))) / RAD];
}
// display-transform:end

function textSprite(text, color, scale) {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 64;
  const g = canvas.getContext("2d");
  g.font = "600 36px system-ui, sans-serif";
  g.textAlign = "center"; g.textBaseline = "middle";
  g.fillStyle = color;
  g.fillText(text, 128, 32);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false, transparent: true }));
  sprite.scale.set(scale * 4, scale, 1);
  return sprite;
}

function discSprite(color, scale) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const g = canvas.getContext("2d");
  g.fillStyle = color;
  g.beginPath(); g.arc(32, 32, 28, 0, 2 * Math.PI); g.fill();
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true }));
  sprite.scale.set(scale, scale, 1);
  return sprite;
}

// Distance classes of the ring, in metres (comparison only). Below 1 km the horizon depends on
// single pixels of the elevation model (SPEC 5.3, near field).
const DISTANCE_CLASSES = [[1000, [1.0, 0.48, 0.45]], [10000, [0.94, 0.65, 0.29]], [100000, [0.9, 0.93, 0.95]], [Infinity, [0.43, 0.66, 1.0]]];
function distanceColor(d) {
  if (!Number.isFinite(d)) return [0.5, 0.5, 0.5];
  return DISTANCE_CLASSES.find(([limit]) => d < limit)[1];
}

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return Boolean(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) {
    return false;
  }
}

export function createView(container, { onCheck } = {}) {
  if (!webglAvailable()) throw new Error("WebGL is not available in this browser or on this device");
  container.innerHTML = "";
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x05070a);
  const camera = new THREE.PerspectiveCamera(60, 16 / 9, 0.1, 1000);
  const look = { az: 180, el: 5 };

  // Fixed parts: horizontal reference circle and compass labels.
  const ring = [];
  for (let a = 0; a <= 360; a += 2) ring.push(direction(a, 0).multiplyScalar(R * 1.002));
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ring), new THREE.LineBasicMaterial({ color: 0x3b4450 })));
  for (const [label, a] of [["N", 0], ["E", 90], ["S", 180], ["W", 270]]) {
    const s = textSprite(label, "#c9d1d9", 5);
    s.position.copy(direction(a, 0).multiplyScalar(R * 0.8));
    scene.add(s);
  }

  const sun = discSprite("#f0a54a", 7), earth = discSprite("#6ea8fe", 7);
  const sunLabel = textSprite("Sun", "#f0a54a", 4), earthLabel = textSprite("Earth", "#6ea8fe", 4);
  scene.add(sun, earth, sunLabel, earthLabel);

  let terrain = null, line = null, dots = null, key = null, input = null, pending = false;

  function buildTerrain(horizon, azimuth, distance) {
    if (terrain) { scene.remove(terrain, line, dots); terrain.geometry.dispose(); line.geometry.dispose(); }
    const n = azimuth.count;
    const pos = [], col = [], idx = [], edge = [], edgeCol = [];
    for (let k = 0; k <= n; k++) {
      const a = azimuth.start_deg + k * azimuth.step_deg;
      const top = direction(a, horizon[k % n]).multiplyScalar(R);
      const bottom = direction(a, BOTTOM_DEG).multiplyScalar(R);
      pos.push(top.x, top.y, top.z, bottom.x, bottom.y, bottom.z);
      col.push(0.05, 0.055, 0.065, 0.006, 0.006, 0.008); // linear values; shown lighter after sRGB output
      edge.push(direction(a, horizon[k % n]).multiplyScalar(R * 0.995));
      edgeCol.push(...distanceColor(distance ? distance[k % n] : NaN));
      if (k < n) idx.push(2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 1, 2 * k + 3, 2 * k + 2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
    terrain = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    const edgeGeometry = new THREE.BufferGeometry().setFromPoints(edge);
    edgeGeometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeCol, 3));
    line = new THREE.Line(edgeGeometry, new THREE.LineBasicMaterial({ vertexColors: true }));
    // WebGL draws lines one pixel wide; the same vertices as points make the colours readable.
    dots = new THREE.Points(edgeGeometry, new THREE.PointsMaterial({ vertexColors: true, size: 3, sizeAttenuation: false }));
    scene.add(terrain, line, dots);
    if (onCheck) onCheck(horizonCheck(horizon, azimuth));
  }

  // Read the drawn horizon line back and compare it with the package profile.
  function horizonCheck(horizon, azimuth) {
    const p = line.geometry.getAttribute("position");
    let dAz = 0, dEl = 0;
    for (let k = 0; k < azimuth.count; k++) {
      const [a, e] = azEl(new THREE.Vector3(p.getX(k), p.getY(k), p.getZ(k)));
      const want = azimuth.start_deg + k * azimuth.step_deg;
      dAz = Math.max(dAz, Math.min(Math.abs(a - want), 360 - Math.abs(a - want)));
      dEl = Math.max(dEl, Math.abs(e - horizon[k]));
    }
    lastCheck = { vertices: azimuth.count, maxAzimuthDiffDeg: dAz, maxElevationDiffDeg: dEl };
    return `Horizon line check: ${azimuth.count} vertices read back from the drawing differ from the package profile by at most ${dEl.toExponential(1)}° in elevation and ${dAz.toExponential(1)}° in azimuth.`;
  }
  let lastCheck = null;

  function placeBody(sprite, label, value) {
    const ok = value && Number.isFinite(value.az) && Number.isFinite(value.el);
    sprite.visible = label.visible = Boolean(ok);
    if (!ok) return;
    sprite.position.copy(direction(value.az, value.el).multiplyScalar(R_BODY));
    label.position.copy(direction(value.az, value.el + 4).multiplyScalar(R_BODY));
  }

  function draw() {
    pending = false;
    const w = container.clientWidth, h = container.clientHeight;
    if (renderer.domElement.width !== Math.floor(w * renderer.getPixelRatio())) renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    camera.position.set(0, 0, 0);
    camera.lookAt(direction(look.az, look.el));
    renderer.render(scene, camera);
  }
  const requestDraw = () => { if (!pending) { pending = true; requestAnimationFrame(draw); } };

  // Look around by dragging (mouse or touch); zoom with the wheel.
  let drag = null;
  const el = renderer.domElement;
  el.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY, az: look.az, el: look.el }; el.setPointerCapture(ev.pointerId); });
  el.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const degPerPx = camera.fov / Math.max(1, container.clientHeight);
    look.az = (drag.az - (ev.clientX - drag.x) * degPerPx + 360) % 360;
    look.el = Math.max(-80, Math.min(80, drag.el + (ev.clientY - drag.y) * degPerPx));
    requestDraw();
  });
  el.addEventListener("pointerup", () => { drag = null; });
  el.addEventListener("wheel", (ev) => { ev.preventDefault(); zoom(ev.deltaY > 0 ? 1.15 : 1 / 1.15); }, { passive: false });
  function zoom(f) { camera.fov = Math.max(5, Math.min(90, camera.fov * f)); requestDraw(); }
  new ResizeObserver(requestDraw).observe(container);

  return {
    update(next) {
      input = next;
      const k = `${next.siteId}:${next.h}`;
      if (k !== key) {
        key = k;
        buildTerrain(next.horizon, next.azimuth, next.distance);
        if (next.sun && Number.isFinite(next.sun.az)) { look.az = next.sun.az; look.el = Math.max(-10, Math.min(30, next.sun.el)); }
      }
      placeBody(sun, sunLabel, next.sun);
      placeBody(earth, earthLabel, next.earth);
      requestDraw();
    },
    command(id) {
      if (id === "zoom-in") zoom(1 / 1.3);
      if (id === "zoom-out") zoom(1.3);
      const body = id === "look-sun" ? input && input.sun : id === "look-earth" ? input && input.earth : null;
      if (body && Number.isFinite(body.az)) { look.az = body.az; look.el = Math.max(-80, Math.min(80, body.el)); requestDraw(); }
    },
    resize: requestDraw,
    check: () => lastCheck,
    ringColors: () => { const c = line && line.geometry.getAttribute("color"); return c ? Array.from(c.array) : null; },
  };
}
