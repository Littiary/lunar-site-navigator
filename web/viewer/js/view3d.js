// Ground view of a site package with three.js (Task 8 B).
//
// Real scale, metres, origin at the ground point of the site; scene axes x = east, y = up,
// z = -north (the same axes as js/terrain.js). What is drawn, and from which package field:
//   - the ground: the terrain patches (terrain.patches[].up_m, SPEC 5.9), finest where they
//     overlap, built by js/terrain.js; the observer stands at the observer height above the
//     centre node of the finest patch;
//   - terrain beyond the largest patch: a curtain whose top edge is the package horizon
//     profile (horizon.elevation_deg), seen from the observer;
//   - the package horizon line itself, drawn on top of everything and coloured by the
//     distance of the terrain that sets it (horizon.distance_m). It is the authority: where
//     the drawn surface and this line disagree, the line is right (SPEC 5.9);
//   - the Sun and the Earth at their package directions (timeline.series azimuth, elevation,
//     angular radius), at true angular size; the light comes from the Sun's direction;
//   - the Earth's spin axis from the direction table's earth_view (SPEC 6.1), for drawing.
// Shading and shadows come from the drawn surface and are for orientation only. Whether the
// Sun or the Earth is visible, and when, is never decided here: it comes from the timeline.
// Display settings (lighting mode, exposure, fill lights, slope colours, patch outlines,
// labels and markers) change how the scene looks, never the geometry or a package value.
// There is no haze or fog: the Moon has no atmosphere.
//
// Trigonometry only in the marked display transform.

import * as THREE from "three";
import { enableViewportResize } from "./viewport-resize.js";
import { terrainGeometry, groundAtSite, patchesFinestFirst } from "./terrain.js";

const PROFILE_R = 60000;   // m: curtain of the package profile, beyond the largest patch (45 km corner)
const SKY_R = 400000;      // m: Sun and Earth
const BOTTOM_DEG = -30;    // lower edge of the profile curtain

// display-transform:start
// Direction of azimuth A (clockwise from north) and elevation E in scene axes (SPEC 5.9:
// (sin A cos E, cos A cos E, sin E) in east/north/up).
const RAD = Math.PI / 180;
export function direction(azDeg, elDeg) {
  const a = azDeg * RAD, e = elDeg * RAD;
  return new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e));
}
export function azEl(v) {
  const n = v.clone().normalize();
  return [((Math.atan2(n.x, -n.z) / RAD) + 360) % 360, Math.asin(Math.max(-1, Math.min(1, n.y))) / RAD];
}
// Linear size at distance d of a disc of angular radius r (degrees).
function radiusAt(d, rDeg) {
  return d * Math.tan(rDeg * RAD);
}
// The Earth's north pole as a scene direction, from the direction table's earth_view
// (SPEC 6.1): g = unit vector to the Earth (body-fixed), sub-lunar latitude, pole angle,
// flattening; then projected on the site's East/North/Up.
export function earthPole(gBody, latDeg, angleDeg, flattening, enu) {
  const n = Math.hypot(gBody[0], gBody[1], gBody[2]);
  const g = gBody.map((v) => v / n);
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const unit = (v) => { const m = Math.hypot(v[0], v[1], v[2]); return v.map((x) => x / m); };
  const east = unit(cross([0, 0, 1], g)), north = cross(g, east);
  const phi = Math.atan(Math.tan(latDeg * RAD) * (1 - flattening) ** 2), a = angleDeg * RAD;
  const pole = [0, 1, 2].map((k) => -g[k] * Math.sin(phi) + Math.cos(phi) * (Math.cos(a) * north[k] + Math.sin(a) * east[k]));
  const dot = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  return new THREE.Vector3(dot(pole, enu.east), dot(pole, enu.up), -dot(pole, enu.north));
}
// display-transform:end

// Distance classes of the horizon line, in metres (comparison only). Below 1 km the horizon
// depends on single pixels of the elevation model (SPEC 5.3, near field).
const DISTANCE_CLASSES = [[1000, [1.0, 0.48, 0.45]], [10000, [0.94, 0.65, 0.29]], [100000, [0.9, 0.93, 0.95]], [Infinity, [0.43, 0.66, 1.0]]];
function distanceColor(d) {
  if (!Number.isFinite(d)) return [0.5, 0.5, 0.5];
  return DISTANCE_CLASSES.find(([limit]) => d < limit)[1];
}

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return Boolean(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) {
    return false;
  }
}

// Display settings. They change how the drawn surface is lit and coloured, never where it is,
// where the Sun and the Earth are, or any value in the overlay.
//   physical: the Sun alone, with a faint fill for earthshine and starlight, at plain exposure.
//             Near the poles the Sun stays within a few degrees of the horizon, so most of the
//             ground is lit at a grazing angle and looks nearly black, as it would.
//   enhanced: the same Sun light, a brighter exposure, and a soft fill from the sky and from
//             the side away from the Sun, so the shape of the ground in shadow can be read.
const LIGHTING = {
  physical: { exposure: () => 1.0, sky: 0.035, fill: 0 },
  // Exposure follows the height of the Sun (sunUp: the up component of the unit vector to it),
  // so that sunlit flat ground reads at about the same brightness at 1 and at 6 degrees.
  enhanced: { exposure: (sunUp) => Math.max(0.8, Math.min(1.6, 0.04 / Math.max(0.005, sunUp))), sky: 0.12, fill: 1.1 },
};
const GROUND = 0x9a968e;
// Slope shading: the steepness of the drawn surface, from its vertex normals (1 - normal.y is
// 0 on flat ground and 0.134 at 30 degrees). Flat ground light grey, steeper ground darker
// and warmer (stops at about 10, 20 and 30 degrees); display only.
const SLOPE_FULL = 0.134;
const SLOPE_RAMP = [[0, [0.70, 0.71, 0.74]], [0.11, [0.55, 0.55, 0.55]], [0.45, [0.80, 0.55, 0.22]], [1, [0.72, 0.16, 0.12]]];
function slopeColor(t) {
  const x = Math.max(0, Math.min(1, t));
  let k = 0;
  while (k < SLOPE_RAMP.length - 2 && x > SLOPE_RAMP[k + 1][0]) k++;
  const [x0, c0] = SLOPE_RAMP[k], [x1, c1] = SLOPE_RAMP[k + 1], f = (x - x0) / (x1 - x0);
  return c0.map((c, m) => c + (c1[m] - c) * f);
}
// Colours of the patch edges, finest patch first (where the drawn grid changes to the next
// coarser patch). Named for the legend; the largest patch has no outline.
export const EDGE_COLORS = [[0x7ee0c3, "green"], [0xd6b36a, "amber"], [0xc39bd3, "violet"], [0x8fb8ff, "blue"]];
const MARKER_PX = 22;   // diameter of the Sun and Earth markers on screen (not to scale)

function disposeObject(o) {
  o.traverse((x) => {
    if (x.geometry) x.geometry.dispose();
    if (x.material) { if (x.material.map) x.material.map.dispose(); x.material.dispose(); }
  });
}

// Labels are HTML, placed on screen at the projected position of their anchor every frame, so
// they keep the same size at every zoom. They are placed in priority order; a label that would
// cover the overlay or a label already placed tries the other side of its anchor, then is hidden.
function labelLayer(container) {
  const layer = document.createElement("div");
  layer.className = "labels3d";
  container.appendChild(layer);
  const items = [];
  function add(text, cls, { marker = false, priority = 0 } = {}) {
    const ring = marker ? document.createElement("div") : null;
    if (ring) { ring.className = `marker3d ${cls}`; ring.style.width = ring.style.height = `${MARKER_PX}px`; layer.appendChild(ring); }
    const tag = document.createElement("div");
    tag.className = `label3d ${cls}`;
    tag.textContent = text;
    layer.appendChild(tag);
    const item = { tag, ring, priority, world: new THREE.Vector3(), on: false, hideRing: false, radiusPx: 0, text };
    items.push(item);
    items.sort((a, b) => b.priority - a.priority);
    return item;
  }
  function overlaps(a, b) { return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; }
  function place(camera, w, h, obstacles) {
    const taken = obstacles.slice();
    for (const it of items) {
      const p = it.world.clone().project(camera);
      const show = it.on && p.z < 1 && Math.abs(p.x) <= 1.02 && Math.abs(p.y) <= 1.02;
      it.tag.style.visibility = show ? "visible" : "hidden";
      if (it.ring) it.ring.style.visibility = show && !it.hideRing ? "visible" : "hidden";
      if (!show) continue;
      const x = (p.x + 1) / 2 * w, y = (1 - p.y) / 2 * h;
      if (it.ring) { it.ring.style.left = `${x - MARKER_PX / 2}px`; it.ring.style.top = `${y - MARKER_PX / 2}px`; }
      const tw = it.tag.offsetWidth, th = it.tag.offsetHeight, gap = it.ring ? Math.max(MARKER_PX / 2, it.radiusPx || 0) + 4 : 0;
      const candidates = it.ring
        ? [[x + gap, y - th / 2], [x - gap - tw, y - th / 2], [x - tw / 2, y - gap - th], [x - tw / 2, y + gap]]
        : [[x - tw / 2, y - th / 2], [x - tw / 2, y - th - 6], [x - tw / 2, y + 6]];
      let spot = null;
      for (const [cx, cy] of candidates) {
        const r = { x: Math.max(2, Math.min(w - tw - 2, cx)), y: Math.max(2, Math.min(h - th - 2, cy)), w: tw, h: th };
        if (!taken.some((t) => overlaps(r, t))) { spot = r; break; }
      }
      if (!spot) { it.tag.style.visibility = "hidden"; continue; }
      taken.push(spot);
      it.tag.style.left = `${spot.x}px`; it.tag.style.top = `${spot.y}px`;
    }
  }
  return { add, place, items };
}

export function createView(container, { onCheck } = {}) {
  if (!webglAvailable()) throw new Error("WebGL is not available in this browser or on this device");
  container.innerHTML = "";
  const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  const labels = labelLayer(container);
  // Overlay with the package values. It folds to one line (the shares of the discs above the
  // horizon) and starts folded on narrow screens, so that it does not hide the view.
  const hud = document.createElement("div");
  hud.className = "hud3d at-tl";
  const hudToggle = document.createElement("button");
  hudToggle.type = "button";
  hudToggle.className = "hud-toggle";
  const hudBody = document.createElement("div");
  hudBody.className = "hud-body";
  hudBody.id = `hud-body-${Math.round(performance.now() * 1000)}`;
  hudToggle.setAttribute("aria-controls", hudBody.id);
  hud.append(hudToggle, hudBody);
  container.appendChild(hud);
  // On narrow screens the full values open below the view instead of over it.
  const NARROW = 600;
  const hudBelow = document.createElement("div");
  hudBelow.className = "hud3d-below";
  container.insertAdjacentElement("afterend", hudBelow);
  let hudOpen = container.clientWidth >= NARROW, hudSummary = "";
  function showHud() {
    const narrow = container.clientWidth < NARROW;
    if (narrow && hudBody.parentNode !== hudBelow) hudBelow.appendChild(hudBody);
    if (!narrow && hudBody.parentNode !== hud) hud.appendChild(hudBody);
    hudBody.hidden = !hudOpen;
    hudBelow.hidden = !(narrow && hudOpen);
    hudToggle.setAttribute("aria-expanded", String(hudOpen));
    hudToggle.textContent = hudOpen ? "Hide details ▴" : `${hudSummary} ▾`;
    hudToggle.title = hudOpen ? "Fold the overlay to one line" : "Show the package values in full";
    hud.classList.toggle("folded", !hudOpen || narrow);
  }
  hudToggle.addEventListener("click", () => { hudOpen = !hudOpen; showHud(); requestDraw(); });

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020306);
  const DEFAULT_FOV = 40;
  const camera = new THREE.PerspectiveCamera(DEFAULT_FOV, 16 / 9, 0.5, 2 * SKY_R);
  const look = { az: 180, el: -5 };
  let eyeY = 2;
  const display = { lighting: "enhanced", slope: false, edges: true };
  let sunUp = 0;

  // Light: the Sun, from its package direction, casting the shadows. Fill lights (display only,
  // no shadows): the sky, and a light from the side away from the Sun.
  const sun = new THREE.DirectionalLight(0xffffff, 3.2);
  sun.castShadow = true;
  const mapSize = container.clientWidth < 700 ? 2048 : 4096;
  sun.shadow.mapSize.set(mapSize, mapSize);
  Object.assign(sun.shadow.camera, { left: -33000, right: 33000, top: 33000, bottom: -33000, near: 100, far: 140000 });
  sun.shadow.bias = -0.002;   // with normalBias: no shadow streaks on grazing slopes
  sun.shadow.normalBias = 80;
  const sky = new THREE.HemisphereLight(0xdfe3ea, 0x2a2826, 0.035);
  const fill = new THREE.DirectionalLight(0xd8dde6, 0);
  scene.add(sun, sun.target, sky, fill, fill.target);

  const ground = new THREE.MeshStandardMaterial({ color: GROUND, roughness: 1, metalness: 0, side: THREE.DoubleSide });
  let terrain = null, edges = null, curtain = null, line = null, dots = null, key = null, input = null, pending = false, lastCheck = null;

  const sunDisc = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), new THREE.MeshBasicMaterial({ color: 0xfff4dc, toneMapped: false }));
  const earthGlobe = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), new THREE.MeshStandardMaterial({ color: 0x6f95d6, roughness: 0.8 }));
  const earthAxis = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -1.5, 0), new THREE.Vector3(0, 1.5, 0)]), new THREE.LineBasicMaterial({ color: 0xffffff, toneMapped: false }));
  earthGlobe.add(earthAxis);
  scene.add(sunDisc, earthGlobe);
  const sunMark = labels.add("Sun", "sun", { marker: true, priority: 3 });
  const earthMark = labels.add("Earth", "earth", { marker: true, priority: 2 });
  const compass = [["N", 0], ["E", 90], ["S", 180], ["W", 270]].map(([t, az]) => Object.assign(labels.add(t, "compass", { priority: 1 }), { az }));

  function applyDisplay() {
    const L = LIGHTING[display.lighting];
    renderer.toneMappingExposure = L.exposure(sunUp);
    sky.intensity = L.sky;
    fill.intensity = L.fill;
    ground.vertexColors = display.slope;
    ground.color.set(display.slope ? 0xffffff : GROUND);
    ground.needsUpdate = true;
    if (edges) edges.visible = display.edges;
  }

  // Slope colours of one patch mesh, from its own vertex normals.
  function slopeColors(geom) {
    const nrm = geom.getAttribute("normal"), out = new Float32Array(nrm.count * 3);
    for (let v = 0; v < nrm.count; v++) out.set(slopeColor((1 - Math.abs(nrm.getY(v))) / SLOPE_FULL), v * 3);
    return new THREE.BufferAttribute(out, 3);
  }

  // Outline of a patch: its boundary nodes, at their package heights, lifted slightly so that
  // the line is not hidden by the surface it lies on.
  function patchEdge(p, up, color) {
    const nE = p.count_east, nN = p.count_north, s = p.spacing_m, lift = 0.02 * s + 1;
    const ring = [];
    for (let j = 0; j < nE; j++) ring.push([0, j]);
    for (let i = 1; i < nN; i++) ring.push([i, nE - 1]);
    for (let j = nE - 2; j >= 0; j--) ring.push([nN - 1, j]);
    for (let i = nN - 2; i >= 0; i--) ring.push([i, 0]);
    const pts = [];
    for (const [i, j] of ring) {
      const h = up[i * nE + j];
      if (Number.isFinite(h)) pts.push(new THREE.Vector3(p.east_min_m + j * s, h + lift, -(p.north_min_m + i * s)));
    }
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color, dashSize: 4 * s, gapSize: 3 * s, transparent: true, opacity: 0.85, toneMapped: false }));
    l.computeLineDistances();
    return l;
  }

  function buildScene(next) {
    for (const o of [terrain, edges, curtain, line, dots]) if (o) { scene.remove(o); disposeObject(o); }
    terrain = new THREE.Group();
    edges = new THREE.Group();
    const patches = next.terrain ? patchesFinestFirst(next.terrain) : [];
    if (patches.length) {
      terrainGeometry(next.terrain, next.up).forEach((g) => {
        const geom = new THREE.BufferGeometry();
        geom.setAttribute("position", new THREE.BufferAttribute(g.positions, 3));
        geom.setIndex(new THREE.BufferAttribute(g.indices, 1));
        geom.computeVertexNormals();
        geom.setAttribute("color", slopeColors(geom));
        const mesh = new THREE.Mesh(geom, ground);
        mesh.castShadow = mesh.receiveShadow = true;
        mesh.userData.patch = g.id;
        terrain.add(mesh);
      });
      patches.slice(0, -1).forEach((p, k) => edges.add(patchEdge(p, next.up[p.id], EDGE_COLORS[k % EDGE_COLORS.length][0])));
      eyeY = groundAtSite(patches[0], next.up[patches[0].id]) + next.observerHeight;
    } else {
      eyeY = next.observerHeight;
    }
    scene.add(terrain, edges);

    // Package horizon: curtain (terrain beyond the patches) and the authoritative line.
    const az = next.azimuth, n = az.count, eye = new THREE.Vector3(0, eyeY, 0);
    const pos = [], idx = [], edge = [], edgeCol = [];
    for (let k = 0; k <= n; k++) {
      const a = az.start_deg + k * az.step_deg, e = next.horizon[k % n];
      const top = direction(a, e).multiplyScalar(PROFILE_R).add(eye);
      const bottom = direction(a, BOTTOM_DEG).multiplyScalar(PROFILE_R).add(eye);
      pos.push(top.x, top.y, top.z, bottom.x, bottom.y, bottom.z);
      edge.push(direction(a, e).multiplyScalar(PROFILE_R * 0.98).add(eye));
      edgeCol.push(...distanceColor(next.distance ? next.distance[k % n] : NaN));
      if (k < n) idx.push(2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 1, 2 * k + 3, 2 * k + 2);
    }
    const cg = new THREE.BufferGeometry();
    cg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    cg.setIndex(idx);
    // A flat dark grey, set apart from the sky: terrain beyond the patches, not drawn in relief.
    curtain = new THREE.Mesh(cg, new THREE.MeshBasicMaterial({ color: 0x2b2d31, side: THREE.DoubleSide, toneMapped: false }));
    const lg = new THREE.BufferGeometry().setFromPoints(edge);
    lg.setAttribute("color", new THREE.Float32BufferAttribute(edgeCol, 3));
    const lineMaterial = { vertexColors: true, depthTest: false, transparent: true, opacity: 0.9, toneMapped: false };
    line = new THREE.Line(lg, new THREE.LineBasicMaterial(lineMaterial));
    dots = new THREE.Points(lg, new THREE.PointsMaterial({ ...lineMaterial, size: 2.5, sizeAttenuation: false }));
    line.renderOrder = dots.renderOrder = 10;
    line.visible = dots.visible = next.showProfile !== false;
    scene.add(curtain, line, dots);
    applyDisplay();
    if (onCheck) onCheck(horizonCheck(next));
  }

  // Read the drawn horizon line back and compare it with the package profile.
  function horizonCheck(next) {
    const p = line.geometry.getAttribute("position"), eye = new THREE.Vector3(0, eyeY, 0);
    let dAz = 0, dEl = 0;
    for (let k = 0; k < next.azimuth.count; k++) {
      const [a, e] = azEl(new THREE.Vector3(p.getX(k), p.getY(k), p.getZ(k)).sub(eye));
      const want = next.azimuth.start_deg + k * next.azimuth.step_deg;
      dAz = Math.max(dAz, Math.min(Math.abs(a - want), 360 - Math.abs(a - want)));
      dEl = Math.max(dEl, Math.abs(e - next.horizon[k]));
    }
    lastCheck = { vertices: next.azimuth.count, maxAzimuthDiffDeg: dAz, maxElevationDiffDeg: dEl };
    return `Horizon line check: ${next.azimuth.count} vertices read back from the drawing differ from the package profile by at most ${dEl.toExponential(1)}° in elevation and ${dAz.toExponential(1)}° in azimuth.`;
  }

  // Package profile elevation at an azimuth (nearest sample; for placing a compass letter).
  function profileAt(next, a) {
    const az = next.azimuth, k = Math.round((((a - az.start_deg) % 360) + 360) % 360 / az.step_deg) % az.count;
    return next.horizon[k];
  }

  function placeBodies(next) {
    const eye = new THREE.Vector3(0, eyeY, 0);
    const place = (mesh, mark, body, name) => {
      const ok = body && Number.isFinite(body.az) && Number.isFinite(body.el);
      mesh.visible = mark.on = Boolean(ok);
      if (!ok) return null;
      const d = direction(body.az, body.el);
      mesh.position.copy(d).multiplyScalar(SKY_R).add(eye);
      mesh.scale.setScalar(radiusAt(SKY_R, Number.isFinite(body.r) ? body.r : 0.25));
      mark.world.copy(mesh.position);
      // The package share of the disc above the horizon, not a test made here.
      const hidden = Number.isFinite(body.fraction) && body.fraction === 0;
      mark.tag.textContent = hidden ? `${name} (below the horizon)` : name;
      mark.tag.classList.toggle("hidden-body", hidden);
      if (mark.ring) mark.ring.classList.toggle("hidden-body", hidden);
      return d;
    };
    const ds = place(sunDisc, sunMark, next.sun, "Sun");
    place(earthGlobe, earthMark, next.earth, "Earth");
    earthAxis.visible = Boolean(next.earthPole);
    if (next.earthPole) earthAxis.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), next.earthPole.clone().normalize());
    if (ds) {
      sun.position.copy(ds).multiplyScalar(60000);
      sun.target.position.set(0, 0, 0);
      sun.intensity = 3.2;
      sunUp = ds.y;
      applyDisplay();
      // Fill from the opposite azimuth, 25 degrees up: shows relief on slopes facing away.
      fill.position.copy(direction(next.sun.az + 180, 25)).multiplyScalar(60000);
      fill.target.position.set(0, 0, 0);
    }
    for (const c of compass) {
      c.on = true;
      c.world.copy(direction(c.az, profileAt(next, c.az) + 1.2)).multiplyScalar(PROFILE_R).add(eye);
    }
  }

  // The overlay sits in a corner of the view. If it would cover the Sun or the Earth, it moves
  // to the first corner that covers neither.
  const CORNERS = ["tl", "tr", "bl", "br"];
  function placeHud(w, h) {
    if (hud.hidden) return;
    const hw = hud.offsetWidth, hh = hud.offsetHeight, m = 8;
    const rect = (c) => ({ x: c[1] === "l" ? m : w - hw - m, y: c[0] === "t" ? m : h - hh - m, w: hw, h: hh });
    const bodies = [];
    for (const mark of [sunMark, earthMark]) {
      if (!mark.on) continue;
      const p = mark.world.clone().project(camera);
      if (p.z >= 1 || Math.abs(p.x) > 1 || Math.abs(p.y) > 1) continue;
      const r = Math.max(MARKER_PX / 2, mark.radiusPx) + 6;
      bodies.push({ x: (p.x + 1) / 2 * w - r, y: (1 - p.y) / 2 * h - r, w: 2 * r, h: 2 * r });
    }
    const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    const corner = CORNERS.find((c) => !bodies.some((b) => hit(rect(c), b))) || "tl";
    for (const c of CORNERS) hud.classList.toggle(`at-${c}`, c === corner);
  }

  // Hide a marker ring once the true disc is larger than it on screen.
  function discPixels(mesh, h) {
    const c = mesh.position.clone().project(camera);
    const e = mesh.position.clone().add(camera.up.clone().multiplyScalar(mesh.scale.x)).project(camera);
    return Math.abs(e.y - c.y) / 2 * h;
  }

  function draw() {
    pending = false;
    const w = container.clientWidth, h = container.clientHeight;
    const ratio = renderer.getPixelRatio();
    if (renderer.domElement.width !== Math.floor(w * ratio) || renderer.domElement.height !== Math.floor(h * ratio)) renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    camera.position.set(0, eyeY, 0);
    camera.lookAt(direction(look.az, look.el).add(camera.position));
    camera.updateMatrixWorld();
    renderer.render(scene, camera);
    for (const [mark, mesh] of [[sunMark, sunDisc], [earthMark, earthGlobe]]) {
      mark.radiusPx = discPixels(mesh, h);
      mark.hideRing = mark.radiusPx * 2 > MARKER_PX - 6;
    }
    placeHud(w, h);
    const box = container.getBoundingClientRect(), hb = hud.getBoundingClientRect();
    const obstacles = !hud.hidden && hb.width ? [{ x: hb.left - box.left, y: hb.top - box.top, w: hb.width, h: hb.height }] : [];
    labels.place(camera, w, h, obstacles);
  }
  const requestDraw = () => { if (!pending) { pending = true; requestAnimationFrame(draw); } };

  // Look around by dragging (mouse or touch); zoom with the wheel.
  let drag = null;
  const el = renderer.domElement;
  el.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY, az: look.az, el: look.el }; try { el.setPointerCapture(ev.pointerId); } catch (e) { /* optional */ } });
  el.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const degPerPx = camera.fov / Math.max(1, container.clientHeight);
    look.az = (drag.az - (ev.clientX - drag.x) * degPerPx + 360) % 360;
    look.el = Math.max(-80, Math.min(80, drag.el + (ev.clientY - drag.y) * degPerPx));
    requestDraw();
  });
  el.addEventListener("pointerup", () => { drag = null; });
  el.addEventListener("wheel", (ev) => { ev.preventDefault(); zoom(ev.deltaY > 0 ? 1.15 : 1 / 1.15); }, { passive: false });
  function zoom(f) { camera.fov = Math.max(2, Math.min(90, camera.fov * f)); requestDraw(); }
  new ResizeObserver(() => { showHud(); requestDraw(); }).observe(container);
  if (container.classList.contains("pane-ground")) enableViewportResize(container);

  // Default view: toward the Sun, a little below it, so the near ground fills the lower half.
  function lookAtSun(next) {
    camera.fov = DEFAULT_FOV;
    if (next.sun && Number.isFinite(next.sun.az)) { look.az = next.sun.az; look.el = Math.max(-12, Math.min(10, next.sun.el - 6)); }
  }

  return {
    update(next) {
      input = next;
      const k = `${next.siteId}:${next.h}`;
      if (k !== key) {
        key = k;
        buildScene(next);
        lookAtSun(next);
      }
      placeBodies(next);
      hudBody.innerHTML = next.hud || "";
      hudSummary = next.hudSummary || "";
      hud.hidden = !next.hud;
      showHud();
      requestDraw();
    },
    command(id) {
      if (id === "zoom-in") zoom(1 / 1.3);
      if (id === "zoom-out") zoom(1.3);
      if (id === "reset-view" && input) { lookAtSun(input); requestDraw(); return null; }
      const body = id === "look-sun" ? input && input.sun : id === "look-earth" ? input && input.earth : null;
      if (body && Number.isFinite(body.az)) { look.az = body.az; look.el = Math.max(-80, Math.min(80, body.el)); requestDraw(); }
      if (id === "toggle-profile" && line) { line.visible = dots.visible = !line.visible; requestDraw(); return line.visible; }
      if (id === "toggle-lighting") { display.lighting = display.lighting === "enhanced" ? "physical" : "enhanced"; applyDisplay(); requestDraw(); return display.lighting === "enhanced"; }
      if (id === "toggle-slope") { display.slope = !display.slope; applyDisplay(); requestDraw(); return display.slope; }
      if (id === "toggle-edges") { display.edges = !display.edges; applyDisplay(); requestDraw(); return display.edges; }
      return null;
    },
    display: () => ({ ...display, exposure: renderer.toneMappingExposure, fov: camera.fov, look: { ...look } }),
    resize: requestDraw,
    check: () => lastCheck,
    // Drawn terrain read back: largest difference between a mesh vertex and the package node.
    terrainCheck() {
      if (!input || !input.terrain) return null;
      const out = {};
      for (const mesh of terrain.children) {
        const p = input.terrain.patches.find((x) => x.id === mesh.userData.patch), up = input.up[p.id];
        const pos = mesh.geometry.getAttribute("position");
        let d = 0;
        for (let i = 0; i < p.count_north; i++) {
          for (let j = 0; j < p.count_east; j++) {
            const v = i * p.count_east + j;
            if (!Number.isFinite(up[v])) continue;
            d = Math.max(d, Math.abs(pos.getX(v) - (p.east_min_m + j * p.spacing_m)), Math.abs(pos.getY(v) - up[v]), Math.abs(pos.getZ(v) + (p.north_min_m + i * p.spacing_m)));
          }
        }
        out[p.id] = { maxDiff_m: d, triangles: mesh.geometry.index.count / 3 };
      }
      return { patches: out, eyeY };
    },
    ringColors: () => { const c = line && line.geometry.getAttribute("color"); return c ? Array.from(c.array) : null; },
    labelState: () => labels.items.map((it) => ({ text: it.tag.textContent, shown: it.tag.style.visibility === "visible", ring: Boolean(it.ring) && it.ring.style.visibility === "visible", left: it.tag.style.left, top: it.tag.style.top })),
  };
}
