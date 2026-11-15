// Inputs of the 3-D ground view (js/view3d.js) for one site, height and time sample, shared by
// the single-site viewer and the panes of the comparison. Moved here from viewer.js unchanged in
// what it reads: the terrain patches and angular radius arrays of the site package, the Sun and
// Earth series already loaded, and the direction table's earth_view record (lookup, no
// interpolation). No trigonometry; the Earth's pole direction is made by view3d.js's display
// transform.

import { loadDirectionTable, PackageError } from "./package.js";
import { BODIES, NAMES, esc, fixed, inWindow, sampleEt, sampleUtc } from "./panel.js";

// The direction table named by a site's timeline, read once per page (cache: an object).
export async function directionTableFor(index, site, cache) {
  const id = site.timeline && site.timeline.direction_table_id;
  if (!id) return null;
  if (!cache[id]) {
    const entry = index.index.packages.find((p) => p.kind === "direction_table" && p.package_id === id);
    if (!entry) throw new PackageError(`direction table ${id} is not in the index`);
    cache[id] = (async () => {
      const table = await loadDirectionTable(index.base, entry);
      return { table, positions: await table.array(table.manifest.positions_km) };
    })();
  }
  return cache[id];
}

// Arrays the ground view needs beyond the Sun and Earth series (read and checked once per site).
export async function groundData(site, index, tableCache) {
  const m = site.manifest, up = {}, radius = {};
  if (m.terrain) for (const p of m.terrain.patches) up[p.id] = (await site.array(p.up_m)).values;
  for (const body of BODIES) {
    const s = site.timeline && site.timeline.series[body];
    if (s && s.angular_radius_deg) radius[body] = (await site.array(s.angular_radius_deg)).values;
  }
  let earthView = null;
  const t = await directionTableFor(index, site, tableCache);
  const ev = t && t.table.manifest.earth_view;
  if (ev) {
    earthView = { lat: (await t.table.array(ev.sub_lunar_lat_deg)).values, lon: (await t.table.array(ev.sub_lunar_lon_deg)).values,
      angle: (await t.table.array(ev.north_pole_angle_deg)).values, flattening: ev.flattening, status: t.table.methodStatus(ev.method) };
  }
  return { siteId: site.id, up, radius, earthView, table: t };
}

// The direction-table record at an instant: lookup, no interpolation.
export function tableRecord(t, et) {
  const grid = t.table.manifest.time;
  const k = Math.min(grid.count - 1, Math.max(0, Math.round((et - grid.start_et_s) / grid.step_s)));
  return { k, exact: grid.start_et_s + k * grid.step_s === et };
}

// The input of view3d.update() for site, height h, sample i, its loaded data and ground data g.
export function groundInput({ site, h, i, data, g, view3dModule, missing = null }) {
  const et = site.timeline ? sampleEt(site, i) : null;
  const pick = (body) => {
    const s = data.series[body];
    return s ? { az: s.az[i], el: s.el[i], r: g.radius[body] ? g.radius[body][i] : NaN, fraction: s.fraction[i] } : null;
  };
  let earthPole = null, subLunar = "";
  if (g.earthView && g.table && site.timeline) {
    const { k, exact } = tableRecord(g.table, et), B = g.table.table.manifest.bodies.length, b = g.table.table.manifest.bodies.indexOf("EARTH");
    if (b >= 0) {
      const gBody = Array.from(g.table.positions.values.subarray((k * B + b) * 3, (k * B + b) * 3 + 3));
      earthPole = view3dModule.earthPole(gBody, g.earthView.lat[k], g.earthView.angle[k], g.earthView.flattening, site.manifest.site.enu);
      subLunar = `Earth's disc centred over ${fixed(g.earthView.lat[k], 2)}°, ${fixed(g.earthView.lon[k], 2)}° (earth_view record ${k}${exact ? "" : ", nearest"}) [${esc(g.earthView.status)}]`;
    }
  }
  const status = (body) => {
    const s = data.series[body];
    if (!s) return "";
    const inside = et === null ? null : inWindow(site, h, `${body.toLowerCase()}_visible`, et);
    return `${NAMES[body]}: ${fixed(100 * s.fraction[i], 1)} % of the disc above the horizon, window <code>${body.toLowerCase()}_visible</code> ${inside ? "holds" : "does not hold"}`;
  };
  const height = site.manifest.horizon.observer_heights_m[h];
  const hud = `<div class="mono">${esc(site.timeline ? sampleUtc(site, i) : "")}</div>
    <div>${status("SUN")}</div><div>${status("EARTH")}</div>
    ${subLunar ? `<div>${subLunar}</div>` : ""}
    <div>Observer ${esc(height)} m above the ground · from the package; the drawn terrain, light and shadows are for orientation only</div>`;
  const share = (body) => { const s = data.series[body]; return s ? `${NAMES[body]} ${fixed(100 * s.fraction[i], 0)} %` : ""; };
  const hudSummary = `${[share("SUN"), share("EARTH")].filter(Boolean).join(" · ")} above the horizon`;
  return { siteId: site.id, h, horizon: data.horizon, hudSummary, distance: data.distance, azimuth: site.manifest.horizon.azimuth,
    terrain: site.manifest.terrain || null, up: g.up, observerHeight: height,
    sun: pick("SUN"), earth: pick("EARTH"), earthPole, hud, missing };
}
