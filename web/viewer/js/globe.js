// Distant Moon globe (Task 8 A) with three.js.
//
// What is drawn, and from which package field:
//   - Moon sphere with the NASA SVS colour map (vendor/moon), for orientation only, and a faint
//     latitude/longitude grid every 30 degrees (the body-fixed frame, for orientation).
//   - Lighting: one directional light along the Sun vector of the direction table
//     (positions_km, body SUN, nearest record to the selected time). The day/night boundary is
//     the shading of that light, not a computed line.
//   - Sites: markers at the latitude and longitude of each site in the index (SPEC 7), checked
//     against site.position_km of the selected package.
//   - Sub-solar and sub-Earth points: where the package Sun and Earth vectors (from the centre of
//     the Moon) meet the sphere, shown only on the side facing the viewer. The contract has no
//     sub-point coordinates, so none are shown as numbers.
//   - "Sun" and "Earth" tags at the edge of the disc, on the side towards each body as seen in
//     the current view.
// Markers, labels and tags are HTML placed at projected positions: a fixed size on screen,
// hidden behind the Moon, clickable and reachable with the keyboard.
// Trigonometry is used only in the marked display transform (sphere, grid, framing).
// No ephemeris or visibility value is computed here.

import * as THREE from "three";
import { webglAvailable } from "./view3d.js";
import { enableViewportResize } from "./viewport-resize.js";

const TEXTURE = new URL("../vendor/moon/lroc_color_2k.jpg", import.meta.url).href;
const FOV = 35;

// display-transform:start
// Body-fixed (x, y, z), z towards the north pole, to three.js (y up): (x, z, -y).
export function toScene(v) {
  return new THREE.Vector3(v[0], v[2], -v[1]);
}
const RAD = Math.PI / 180;
function bodyUnit(latDeg, lonDeg) {
  return [Math.cos(latDeg * RAD) * Math.cos(lonDeg * RAD), Math.cos(latDeg * RAD) * Math.sin(lonDeg * RAD), Math.sin(latDeg * RAD)];
}
// Unit sphere with an equirectangular texture centred on 0° longitude: u = (lon + 180) / 360.
function texturedSphere(segmentsLon, segmentsLat) {
  const pos = [], uv = [], idx = [];
  for (let j = 0; j <= segmentsLat; j++) {
    const lat = -90 + (180 * j) / segmentsLat;
    for (let i = 0; i <= segmentsLon; i++) {
      const lon = -180 + (360 * i) / segmentsLon;
      const p = toScene(bodyUnit(lat, lon));
      pos.push(p.x, p.y, p.z);
      uv.push(i / segmentsLon, j / segmentsLat);
      if (i < segmentsLon && j < segmentsLat) {
        const a = j * (segmentsLon + 1) + i, c = a + segmentsLon + 1;
        idx.push(a, a + 1, c, a + 1, c + 1, c);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}
// Latitude circles and meridians every `step` degrees, as line segments just above the sphere.
function graticule(step, r) {
  const pts = [];
  const seg = (a, b) => { pts.push(toScene(a).multiplyScalar(r), toScene(b).multiplyScalar(r)); };
  for (let lat = -90 + step; lat < 90; lat += step) for (let lon = -180; lon < 180; lon += 2) seg(bodyUnit(lat, lon), bodyUnit(lat, lon + 2));
  for (let lon = -180; lon < 180; lon += step) for (let lat = -90; lat < 90; lat += 2) seg(bodyUnit(lat, lon), bodyUnit(lat + 2, lon));
  return new THREE.BufferGeometry().setFromPoints(pts);
}
// Unit vector (body-fixed) of a planetocentric latitude and east longitude, for the site markers.
function unitFromLatLon(latDeg, lonDeg) {
  return bodyUnit(latDeg, lonDeg);
}
function unit(v) {
  const n = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
  return [v[0] / n, v[1] / n, v[2] / n];
}
// Camera distance at which a sphere of the given radius (with a margin) fits the narrower side.
function fitDistance(radius, fovDeg, aspect) {
  const v = (fovDeg / 2) * RAD, h = Math.atan(Math.tan(v) * aspect);
  return radius / Math.sin(Math.min(v, h));
}
// display-transform:end

export function createGlobe(container, { onPickSite } = {}) {
  if (!webglAvailable()) throw new Error("WebGL is not available in this browser or on this device");
  container.innerHTML = "";
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  container.appendChild(renderer.domElement);
  const layer = document.createElement("div");
  layer.className = "globe-layer";
  const leaders = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  leaders.classList.add("globe-leaders");
  layer.appendChild(leaders);
  container.appendChild(layer);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020306);
  const camera = new THREE.PerspectiveCamera(FOV, 16 / 9, 0.01, 100);

  const texture = new THREE.TextureLoader().load(TEXTURE, () => requestDraw());
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const moon = new THREE.Mesh(texturedSphere(240, 120), new THREE.MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0 }));
  scene.add(moon);
  const grid = new THREE.LineSegments(graticule(30, 1.0015), new THREE.LineBasicMaterial({ color: 0xc9d1d9, transparent: true, opacity: 0.12, toneMapped: false }));
  scene.add(grid);
  // The Sun; a very faint fill (earthshine) so that the night side is dark but not a hole.
  const sunLight = new THREE.DirectionalLight(0xffffff, 2.8);
  scene.add(sunLight, new THREE.HemisphereLight(0x9fb4d8, 0x000000, 0.025));

  // Anchors of the sub-points (kept as positions so that they can be read back and checked).
  const subSun = new THREE.Object3D(), subEarth = new THREE.Object3D();
  let sunDir = null, earthDir = null;

  let sites = [], selected = null, input = null, pending = false, sitesKey = null, fitted = false;
  const orbit = { dir: new THREE.Vector3(0, -1, 0.4).normalize(), up: new THREE.Vector3(0, 1, 0), dist: 4.2 };

  // ---- HTML overlay: site markers and labels, sub-points, Sun and Earth tags
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    e.className = cls;
    if (text) e.textContent = text;
    layer.appendChild(e);
    return e;
  }
  const subSunTag = el("div", "globe-sub sun", ""), subEarthTag = el("div", "globe-sub earth", "");
  subSunTag.title = "Sub-solar point: where the package Sun vector meets the sphere";
  subEarthTag.title = "Sub-Earth point: where the package Earth vector meets the sphere";
  const sunTag = el("div", "globe-tag sun", "Sun"), earthTag = el("div", "globe-tag earth", "Earth");

  // Free the markers and labels of the current site list.
  function disposeMarkers() {
    for (const s of sites) { s.dot.remove(); s.label.remove(); s.leader.remove(); }
    sites = [];
  }

  function setSites(list) {
    disposeMarkers();
    sites = list.map((s) => {
      // On the unit sphere at the site's latitude and longitude (from the index).
      const p = toScene(unitFromLatLon(s.lat_deg, s.lon_deg));
      const dot = el("button", "globe-site");
      dot.type = "button";
      dot.setAttribute("aria-label", `${s.name}: open its ground view`);
      dot.title = s.name;
      const lab = el("button", "globe-label", s.name);
      lab.type = "button";
      lab.tabIndex = -1; // the marker is the keyboard stop; the label is a larger target for the pointer
      const leader = document.createElementNS("http://www.w3.org/2000/svg", "line");
      leaders.appendChild(leader);
      const pick = () => { if (onPickSite) onPickSite(s.site_id); };
      dot.addEventListener("click", pick);
      lab.addEventListener("click", pick);
      return { ...s, scenePos: p, dot, label: lab, leader };
    });
  }

  // Is a point on the unit sphere on the side facing the camera?
  const facing = (n) => n.dot(camera.position) > 1;
  const toScreen = (v, w, h) => { const p = v.clone().project(camera); return { x: (p.x + 1) / 2 * w, y: (1 - p.y) / 2 * h }; };
  const hit = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

  function placeOverlay(w, h) {
    const c = toScreen(new THREE.Vector3(), w, h);
    const rightEdge = toScreen(new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0), w, h);
    const R = new THREE.Vector2(rightEdge.x - c.x, rightEdge.y - c.y).length(); // disc radius on screen (display)
    const taken = [];
    // Site markers first (they are the targets), the selected one on top.
    const order = sites.slice().sort((a, b) => (b.site_id === input.selectedId) - (a.site_id === input.selectedId));
    for (const s of order) {
      const on = facing(s.scenePos);
      s.dot.hidden = s.label.hidden = !on;
      s.leader.style.display = "none";
      s.dot.classList.toggle("selected", s.site_id === input.selectedId);
      s.label.classList.toggle("selected", s.site_id === input.selectedId);
      if (!on) continue;
      s.screen = toScreen(s.scenePos, w, h);
      // Outside the frame: no marker, and no label pinned to the edge.
      if (s.screen.x < 0 || s.screen.x > w || s.screen.y < 0 || s.screen.y > h) { s.dot.hidden = s.label.hidden = true; continue; }
      const r = s.site_id === input.selectedId ? 8 : 6;
      s.dot.style.left = `${s.screen.x - r}px`; s.dot.style.top = `${s.screen.y - r}px`;
      taken.push({ x: s.screen.x - r, y: s.screen.y - r, w: 2 * r, h: 2 * r });
    }
    // Sub-points on the facing side only.
    for (const [tag, anchor, dir] of [[subSunTag, subSun, sunDir], [subEarthTag, subEarth, earthDir]]) {
      const on = Boolean(dir) && facing(anchor.position.clone().normalize().multiplyScalar(1.0001));
      tag.hidden = !on;
      if (!on) continue;
      const p = toScreen(anchor.position, w, h);
      tag.style.left = `${p.x - 5}px`; tag.style.top = `${p.y - 5}px`;
      taken.push({ x: p.x - 5, y: p.y - 5, w: 10, h: 10 });
    }
    // Sun and Earth tags outside the disc edge, on the side of each body in this view.
    for (const [tag, dir] of [[sunTag, sunDir], [earthTag, earthDir]]) {
      tag.hidden = !dir;
      if (!dir) continue;
      const far = toScreen(dir.clone().multiplyScalar(3), w, h);
      let dx = far.x - c.x, dy = far.y - c.y;
      const l = new THREE.Vector2(dx, dy).length();
      const toward = dir.dot(camera.position) > 0;
      if (l < 0.05 * R) { // along the line of sight
        tag.textContent = `${tag.classList.contains("sun") ? "Sun" : "Earth"} ${toward ? "behind you" : "behind the Moon"}`;
        dx = tag.classList.contains("sun") ? -0.7 : 0.7; dy = -0.7;
      } else {
        tag.textContent = tag.classList.contains("sun") ? "Sun" : "Earth";
        dx /= l; dy /= l;
      }
      const tw = tag.offsetWidth, th = tag.offsetHeight;
      const px = c.x + dx * (R + 10 + tw / 2), py = c.y + dy * (R + 8 + th / 2);
      tag.style.left = `${Math.max(2, Math.min(w - tw - 2, px - tw / 2))}px`;
      tag.style.top = `${Math.max(2, Math.min(h - th - 2, py - th / 2))}px`;
      taken.push({ x: parseFloat(tag.style.left), y: parseFloat(tag.style.top), w: tw, h: th });
    }
    // Labels: try positions around the marker, further out each ring, with a leader line when
    // the label is away from its marker; hide it when nothing fits.
    for (const s of order) {
      if (s.dot.hidden) continue;
      const tw = s.label.offsetWidth, th = s.label.offsetHeight, { x, y } = s.screen;
      // Away from the centre of the disc first, so that clustered labels fan outwards.
      const out = { x: x - c.x, y: y - c.y }, len = new THREE.Vector2(out.x, out.y).length() || 1;
      const ux = out.x / len, uy = out.y / len;
      // A marker with another within 18 px gets its label further out, always with a leader line,
      // so that each label points at its own marker.
      const crowded = order.some((o) => o !== s && !o.dot.hidden && new THREE.Vector2(o.screen.x - x, o.screen.y - y).length() < 18);
      const spots = [];
      for (const d of crowded ? [30, 52, 76, 100] : [12, 34, 58, 84]) {
        for (const [sx, sy] of [[ux, uy], [1, 0], [-1, 0], [0.7, -0.7], [0.7, 0.7], [-0.7, -0.7], [-0.7, 0.7], [0, -1], [0, 1]]) {
          const ax = x + sx * d, ay = y + sy * d;
          spots.push({ x: sx >= 0 ? ax : ax - tw, y: ay - th / 2 + sy * th / 2, w: tw, h: th, d });
        }
      }
      let spot = null;
      for (const r of spots) {
        const q = { ...r, x: Math.max(2, Math.min(w - tw - 2, r.x)), y: Math.max(2, Math.min(h - th - 2, r.y)) };
        if (!taken.some((t) => hit(q, t))) { spot = q; break; }
      }
      if (!spot) { s.label.hidden = s.site_id !== input.selectedId; if (s.label.hidden) continue; spot = { x: Math.min(w - tw - 2, x + 12), y: y - th / 2, d: 12 }; }
      taken.push({ x: spot.x, y: spot.y, w: tw, h: th });
      s.label.style.left = `${spot.x}px`; s.label.style.top = `${spot.y}px`;
      if (spot.d > 12) {
        const lx = Math.max(spot.x, Math.min(spot.x + tw, x)), ly = Math.max(spot.y, Math.min(spot.y + th, y));
        Object.entries({ x1: x, y1: y, x2: lx, y2: ly }).forEach(([k, v]) => s.leader.setAttribute(k, v));
        s.leader.style.display = "";
      }
    }
  }

  function draw() {
    pending = false;
    const w = container.clientWidth, h = container.clientHeight;
    const ratio = renderer.getPixelRatio();
    if (renderer.domElement.width !== Math.floor(w * ratio) || renderer.domElement.height !== Math.floor(h * ratio)) renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    if (!fitted && w > 0) { orbit.dist = fitDistance(1.32, FOV, camera.aspect); fitted = true; }
    camera.position.copy(orbit.dir).multiplyScalar(orbit.dist);
    camera.up.copy(orbit.up);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    renderer.render(scene, camera);
    leaders.setAttribute("width", w); leaders.setAttribute("height", h);
    if (input) placeOverlay(w, h);
  }
  const requestDraw = () => { if (!pending) { pending = true; requestAnimationFrame(draw); } };

  // Turn the view about the camera's own axes, so that a drag moves the surface with the pointer
  // wherever the view is (also over the poles).
  function turn(dx, dy) {
    // Slower when close, so that the surface keeps up with the pointer.
    const k = 0.006 * Math.max(0.15, Math.min(1, (orbit.dist - 1) / 3.4));
    dx *= k / 0.006; dy *= k / 0.006;
    const right = new THREE.Vector3().crossVectors(orbit.up, orbit.dir).normalize();
    const q = new THREE.Quaternion().setFromAxisAngle(orbit.up, -dx * 0.006)
      .multiply(new THREE.Quaternion().setFromAxisAngle(right, -dy * 0.006));
    orbit.dir.applyQuaternion(q).normalize();
    orbit.up.applyQuaternion(q);
    orbit.up.sub(orbit.dir.clone().multiplyScalar(orbit.up.dot(orbit.dir))).normalize();
  }

  // Smooth move of the view direction (and its up vector) to a new direction.
  let anim = null;
  function lookAlong(target, upHint) {
    if (!target) return;
    const to = target.clone().normalize();
    const hint = (upHint || new THREE.Vector3(0, 1, 0)).clone();
    let up = hint.sub(to.clone().multiplyScalar(hint.dot(to)));
    if (up.lengthSq() < 1e-6) up = new THREE.Vector3(1, 0, 0).sub(to.clone().multiplyScalar(to.x));
    up.normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(orbit.dir.clone().normalize(), to);
    const from = { dir: orbit.dir.clone(), up: orbit.up.clone() }, t0 = performance.now(), ms = 450;
    const endUp = up;
    if (anim) cancelAnimationFrame(anim);
    const stepAnim = () => {
      const t = Math.min(1, (performance.now() - t0) / ms), e = t * t * (3 - 2 * t);
      const qt = new THREE.Quaternion().slerp(q, e);
      orbit.dir.copy(from.dir).applyQuaternion(qt).normalize();
      orbit.up.copy(from.up).applyQuaternion(qt).lerp(endUp, e);
      orbit.up.sub(orbit.dir.clone().multiplyScalar(orbit.up.dot(orbit.dir))).normalize();
      draw();
      anim = t < 1 ? requestAnimationFrame(stepAnim) : null;
    };
    stepAnim();
  }
  // The selected site seen from the side of the Sun, so that its surroundings are lit: the view
  // direction is the site direction turned partly towards the Sun's direction.
  function siteView(tilt = 0.55) {
    if (!selected) return null;
    const n = selected.scenePos.clone().normalize();
    if (sunDir && tilt > 0) {
      const side = sunDir.clone().sub(n.clone().multiplyScalar(sunDir.dot(n)));
      if (side.lengthSq() > 1e-6) return { dir: n.add(side.normalize().multiplyScalar(tilt)), up: new THREE.Vector3(0, 1, 0) };
    }
    return { dir: n, up: new THREE.Vector3(0, 1, 0) };
  }

  let drag = null;
  const canvas = renderer.domElement;
  canvas.addEventListener("pointerdown", (ev) => { if (anim) { cancelAnimationFrame(anim); anim = null; } drag = { x: ev.clientX, y: ev.clientY }; try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* optional */ } });
  canvas.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    turn(ev.clientX - drag.x, ev.clientY - drag.y);
    drag.x = ev.clientX; drag.y = ev.clientY;
    requestDraw();
  });
  const endDrag = () => { drag = null; };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
  canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); zoom(ev.deltaY > 0 ? 1.12 : 1 / 1.12); }, { passive: false });
  function zoom(f) { fitted = true; orbit.dist = Math.max(1.35, Math.min(12, orbit.dist * f)); requestDraw(); }
  new ResizeObserver(() => { if (!input) fitted = false; requestDraw(); }).observe(container);
  enableViewportResize(container);

  return {
    // sites: [{site_id, name, lat_deg, lon_deg}] from the index (markers on the unit sphere),
    // sun / earth: package vectors (km, body-fixed, from the centre of the Moon), selectedId.
    update(next) {
      const first = !input;
      input = next;
      // Rebuild the markers only when the set of sites or the scale changes, not on every time step.
      const key = JSON.stringify(next.sites.map((s) => [s.site_id, s.name, s.lat_deg, s.lon_deg]));
      if (key !== sitesKey) { setSites(next.sites); sitesKey = key; }
      selected = sites.find((s) => s.site_id === next.selectedId) || null;
      const place = (vec, anchor) => {
        const ok = vec && vec.every(Number.isFinite);
        if (!ok) return null;
        const d = toScene(unit(vec));
        anchor.position.copy(d).multiplyScalar(1.002);
        return d;
      };
      sunDir = place(next.sun, subSun);
      earthDir = place(next.earth, subEarth);
      if (sunDir) sunLight.position.copy(sunDir).multiplyScalar(10);
      if (first) { const v = siteView(); if (v) { orbit.dir.copy(v.dir).normalize(); const u = v.up.sub(orbit.dir.clone().multiplyScalar(v.up.dot(orbit.dir))); if (u.lengthSq() > 1e-6) orbit.up.copy(u.normalize()); } }
      requestDraw();
    },
    command(id) {
      if (id === "globe-zoom-in") zoom(1 / 1.25);
      if (id === "globe-zoom-out") zoom(1.25);
      if (id === "globe-from-earth" && earthDir) lookAlong(earthDir);
      if (id === "globe-from-sun" && sunDir) lookAlong(sunDir);
      // The selected site and its neighbours, closer in (clustered sites separate on screen).
      // Straight above the site, so that it is in the middle of the view.
      if (id === "globe-site") { const v = siteView(0); if (v) { fitted = true; orbit.dist = Math.min(orbit.dist, 2.1); lookAlong(v.dir, sunDir || v.up); } }
      if (id === "globe-fit") { fitted = false; requestDraw(); }
    },
    resize: requestDraw,
    markerCount: () => sites.length,
    // Read the drawn positions back and compare them with the package values (unit vectors).
    check(current) {
      if (!input) return null;
      const diff = (a, b) => Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y), Math.abs(a.z - b.z));
      const s = toScene(unit(input.sun)), e = toScene(unit(input.earth));
      return {
        // The selected site's marker against the direction of its package position_km.
        siteDirectionDiff: (() => {
          const m = current && sites.find((x) => x.site_id === current.site_id);
          return m ? diff(m.scenePos.clone().normalize(), toScene(unit(current.position_km))) : NaN;
        })(),
        sunLightDiff: diff(sunLight.position.clone().normalize(), s),
        subSolarDiff: diff(subSun.position.clone().divideScalar(1.002), s),
        subEarthDiff: diff(subEarth.position.clone().divideScalar(1.002), e),
      };
    },
    // Screen state of every site, for tests of the click path and of label placement.
    siteScreen() {
      return sites.map((s) => {
        const d = s.dot.getBoundingClientRect(), l = s.label.getBoundingClientRect();
        return { site_id: s.site_id, shown: !s.dot.hidden, labelShown: !s.label.hidden, selected: s.dot.classList.contains("selected"),
          dot: { x: d.left + d.width / 2, y: d.top + d.height / 2 }, label: { x: l.left, y: l.top, w: l.width, h: l.height } };
      });
    },
  };
}
