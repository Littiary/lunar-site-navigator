// Interactive 360° sky panorama of one site package (canvas).
//
// Azimuth runs left to right (north, east, south, west, north) and wraps around; elevation
// runs bottom to top. The terrain is the horizon profile of the package. The paths of the Sun
// and the Earth are their package series over a chosen span of samples; a path is drawn solid
// where the package window `<body>_visible` contains the sample and faded elsewhere.
//
// Rule: every value comes from the package. Angles are mapped linearly to pixels; there is no
// trigonometry and nothing is computed or interpolated. Hovering shows the stored values of
// the nearest drawn sample; clicking selects that sample.

import { BODIES, NAMES, containing, esc, fixed, sampleEt, sampleUtc, windowsAtHeight } from "./panel.js";

const COLORS = { SUN: "#f0a54a", EARTH: "#6ea8fe" };
const PICK_PX = 14;

export function createSky(container, { onPick } = {}) {
  container.innerHTML = "";
  const canvas = document.createElement("canvas");
  const tip = document.createElement("div");
  tip.className = "sky-tip";
  tip.hidden = true;
  container.append(canvas, tip);
  const g = canvas.getContext("2d");

  const view = { center: 180, span: 360 };      // azimuth at the centre of the canvas, degrees shown
  let input = null, drawn = [], horizonPts = [], size = { w: 0, h: 0 };

  // ---------------------------------------------------------------- mapping (linear)
  const left = () => view.center - view.span / 2;
  const xOf = (az) => ((az - left()) / view.span) * size.w;
  const azOf = (x) => left() + (x / size.w) * view.span;
  const yOf = (el) => { const [lo, hi] = input.data.yRange; return size.h - 22 - ((el - lo) / (hi - lo)) * (size.h - 34); };
  const elOf = (y) => { const [lo, hi] = input.data.yRange; return lo + ((size.h - 22 - y) / (size.h - 34)) * (hi - lo); };
  // Copies of the 360° scene that fall into the visible azimuth range.
  const shifts = () => { const out = []; for (let s = -720; s <= 720; s += 360) if (left() < s + 360 && left() + view.span > s) out.push(s); return out; };

  function resize() {
    const w = container.clientWidth;
    const h = Math.max(240, Math.min(520, Math.round(w * 0.42)));
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio);
    canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    size = { w, h };
    draw();
  }

  function draw() {
    if (!input || !size.w) return;
    const { site, data, h, i, spanSamples } = input;
    const css = getComputedStyle(container);
    const ink = css.getPropertyValue("--muted").trim() || "#9da7b3";
    const line = css.getPropertyValue("--line").trim() || "#30363d";
    g.clearRect(0, 0, size.w, size.h);
    g.fillStyle = "#05070a";
    g.fillRect(0, 0, size.w, size.h);

    // grid
    g.font = "12px system-ui, sans-serif";
    g.strokeStyle = line; g.fillStyle = ink; g.lineWidth = 1;
    const stepAz = view.span > 180 ? 45 : view.span > 60 ? 15 : 5;
    const names = { 0: "N", 90: "E", 180: "S", 270: "W" };
    for (let a = Math.ceil(left() / stepAz) * stepAz; a <= left() + view.span; a += stepAz) {
      const x = xOf(a);
      g.beginPath(); g.moveTo(x, 0); g.lineTo(x, size.h - 22); g.stroke();
      const wrapped = ((a % 360) + 360) % 360;
      g.textAlign = "center";
      g.fillText(`${names[wrapped] ? names[wrapped] + " " : ""}${wrapped}°`, x, size.h - 6);
    }
    const [lo, hi] = data.yRange;
    const stepEl = hi - lo > 12 ? 5 : hi - lo > 6 ? 2 : 1;
    g.textAlign = "left";
    for (let e = Math.ceil(lo / stepEl) * stepEl; e <= hi; e += stepEl) {
      const y = yOf(e);
      g.beginPath(); g.moveTo(0, y); g.lineTo(size.w, y); g.stroke();
      g.fillText(`${e}°`, 4, y - 3);
    }

    // terrain: sample k at azimuth start_deg + k * step_deg (SPEC 5.3), periodic
    const az = site.manifest.horizon.azimuth;
    horizonPts = [];
    for (const s of shifts()) {
      g.beginPath();
      g.moveTo(xOf(s + az.start_deg), size.h - 22);
      for (let k = 0; k <= az.count; k++) {
        const x = xOf(s + az.start_deg + k * az.step_deg), y = yOf(data.horizon[k % az.count]);
        g.lineTo(x, y);
        if (s === shifts()[0] && k < az.count) horizonPts.push([x, y, k]);
      }
      g.lineTo(xOf(s + az.start_deg + 360), size.h - 22);
      g.closePath();
      g.fillStyle = "#262c33"; g.fill();
      g.strokeStyle = "#8b949e"; g.lineWidth = 1.5; g.stroke();
    }

    // paths over the chosen span, solid inside the package window <body>_visible
    drawn = [];
    if (site.timeline) {
      const count = site.timeline.time.count;
      const from = Math.max(0, i - spanSamples), to = Math.min(count - 1, i + spanSamples);
      for (const body of BODIES) {
        const s = data.series[body];
        if (!s) continue;
        const win = windowsAtHeight(site, h).find((w) => w.id === `${body.toLowerCase()}_visible`);
        for (const shift of shifts()) {
          let prev = null;
          for (let j = from; j <= to; j++) {
            const a = s.az[j], e = s.el[j];
            if (!Number.isFinite(a) || !Number.isFinite(e)) { prev = null; continue; }
            const x = xOf(shift + a), y = yOf(e);
            const on = win ? containing(win.intervals_et_s, sampleEt(site, j)) >= 0 : true;
            if (prev && (prev.a - a > 180 || a - prev.a > 180)) prev = null; // the path crosses north: no line across the panorama
            if (prev) {
              g.strokeStyle = COLORS[body]; g.globalAlpha = on && prev.on ? 1 : 0.3; g.lineWidth = on && prev.on ? 2 : 1.5;
              g.beginPath(); g.moveTo(prev.x, prev.y); g.lineTo(x, y); g.stroke();
            }
            prev = { x, y, a, on };
            if (x >= -PICK_PX && x <= size.w + PICK_PX) drawn.push({ x, y, body, j });
          }
        }
        g.globalAlpha = 1;
      }
      // current positions
      for (const body of BODIES) {
        const s = data.series[body];
        if (!s || !Number.isFinite(s.az[i])) continue;
        for (const shift of shifts()) {
          const x = xOf(shift + s.az[i]), y = yOf(s.el[i]);
          g.fillStyle = COLORS[body]; g.beginPath(); g.arc(x, y, 7, 0, 2 * Math.PI); g.fill();
          g.strokeStyle = "#05070a"; g.lineWidth = 2; g.stroke();
          g.fillStyle = "#e6edf3"; g.font = "600 13px system-ui, sans-serif"; g.textAlign = "left";
          g.fillText(NAMES[body], x + 10, y - 10);
        }
      }
    }
  }

  // ---------------------------------------------------------------- interaction
  const pointers = new Map();
  let drag = null, pinch = null, moved = false;

  function nearest(px, py) {
    let best = null, bestD = PICK_PX * PICK_PX;
    for (const p of drawn) {
      const dx = p.x - px, dy = p.y - py, d = dx * dx + dy * dy; // squared screen distance, compared only
      if (d < bestD) { bestD = d; best = p; }
    }
    return best;
  }

  function showTip(p, px, py) {
    if (!p) { tip.hidden = true; return; }
    const { site, data, h } = input;
    const s = data.series[p.body];
    const win = windowsAtHeight(site, h).find((w) => w.id === `${p.body.toLowerCase()}_visible`);
    const inside = win ? containing(win.intervals_et_s, sampleEt(site, p.j)) >= 0 : null;
    tip.innerHTML = `<strong>${NAMES[p.body]}</strong> · <span class="mono">${esc(sampleUtc(site, p.j))}</span><br>
      azimuth ${fixed(s.az[p.j], 3)}°, elevation ${fixed(s.el[p.j], 3)}° (centre, no terrain)<br>
      margin above terrain horizon ${fixed(s.margin[p.j], 3)}°, disc above it ${fixed(100 * s.fraction[p.j], 1)} %<br>
      in window <code>${p.body.toLowerCase()}_visible</code>: ${inside === null ? "—" : inside ? "yes" : "no"} · click to go to this time`;
    tip.hidden = false;
    tip.style.left = `${Math.min(px + 12, size.w - tip.offsetWidth - 4)}px`;
    tip.style.top = `${Math.max(4, py - tip.offsetHeight - 12)}px`;
  }

  function localXY(ev) {
    const r = canvas.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  }

  function zoom(factor, atX) {
    const anchor = azOf(atX === undefined ? size.w / 2 : atX);
    const span = Math.max(20, Math.min(360, view.span * factor));
    const frac = (atX === undefined ? size.w / 2 : atX) / size.w;
    view.span = span;
    view.center = anchor - span * frac + span / 2;
    draw();
  }

  canvas.addEventListener("pointerdown", (ev) => {
    pointers.set(ev.pointerId, ev.clientX);
    try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* capture is a convenience only */ }
    moved = false;
    if (pointers.size === 1) drag = { x: ev.clientX, center: view.center };
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { dist: Math.max(20, Math.abs(a - b)), span: view.span };
      drag = null;
    }
  });
  canvas.addEventListener("pointermove", (ev) => {
    const [px, py] = localXY(ev);
    if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, ev.clientX);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      view.span = Math.max(20, Math.min(360, pinch.span * (pinch.dist / Math.max(20, Math.abs(a - b)))));
      moved = true; draw(); return;
    }
    if (drag) {
      if (Math.abs(ev.clientX - drag.x) > 3) moved = true;
      view.center = drag.center - ((ev.clientX - drag.x) / size.w) * view.span;
      draw(); tip.hidden = true; return;
    }
    if (ev.pointerType === "mouse") showTip(nearest(px, py), px, py);
  });
  const end = (ev) => {
    const [px, py] = localXY(ev);
    const wasTap = drag && !moved && pointers.size === 1;
    pointers.delete(ev.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) drag = null;
    if (wasTap) {
      const p = nearest(px, py);
      if (p && onPick) onPick(p.j);
      if (p && ev.pointerType !== "mouse") showTip(p, px, py);
    }
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("pointerleave", () => { if (!drag) tip.hidden = true; });
  canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); zoom(ev.deltaY > 0 ? 1.2 : 1 / 1.2, localXY(ev)[0]); }, { passive: false });
  new ResizeObserver(resize).observe(container);

  return {
    update(next) {
      const fresh = !input || next.site !== input.site || next.h !== input.h;
      input = next;
      if (fresh && next.data.series.SUN && Number.isFinite(next.data.series.SUN.az[next.i]) && view.span < 360) view.center = next.data.series.SUN.az[next.i];
      if (!size.w) resize(); else draw();
    },
    command(id) {
      if (id === "sky-zoom-in") zoom(1 / 1.5);
      if (id === "sky-zoom-out") zoom(1.5);
      if (id === "sky-reset") { view.center = 180; view.span = 360; draw(); }
      if (id === "sky-center-sun" || id === "sky-center-earth") {
        const s = input && input.data.series[id === "sky-center-sun" ? "SUN" : "EARTH"];
        if (s && Number.isFinite(s.az[input.i])) { view.center = s.az[input.i]; draw(); }
      }
    },
    resize,
    // Read the drawn horizon back through the inverse mapping and compare it with the package.
    check() {
      if (!input) return null;
      const az = input.site.manifest.horizon.azimuth;
      let dAz = 0, dEl = 0;
      const first = shifts()[0];
      for (const [x, y, k] of horizonPts) {
        dAz = Math.max(dAz, Math.abs(azOf(x) - (first + az.start_deg + k * az.step_deg)));
        dEl = Math.max(dEl, Math.abs(elOf(y) - input.data.horizon[k]));
      }
      return { vertices: horizonPts.length, maxAzimuthDiffDeg: dAz, maxElevationDiffDeg: dEl, pathPoints: drawn.length };
    },
    pick: (x, y) => nearest(x, y),
    points: () => drawn.slice(), // drawn path points {x, y, body, j}, for checks
    viewSpan: () => view.span,   // degrees of azimuth across the canvas, for checks
  };
}
