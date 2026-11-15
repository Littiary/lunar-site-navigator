// CSV export for package values. Values are serialized without display rounding.

import { BODIES, NAMES, canLabelUtc, sampleEt, sampleUtc } from "./panel.js";

export const SERIES_COLUMNS = [
  "utc_timestamp", "sample_index", "et_s", "package_start_utc", "package_end_utc",
  "shared_start_utc", "shared_end_utc", "site_id", "site_name", "package_id",
  "observer_height_m", "body", "azimuth_deg", "elevation_deg", "margin_deg", "visible_fraction",
];

function raw(value) {
  return value === null || value === undefined || (typeof value === "number" && !Number.isFinite(value))
    ? "" : String(value);
}

function cell(value) {
  const text = raw(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function rowsForSite(site, data, height, sharedRange) {
  if (!site.timeline) return [];
  const t = site.timeline.time;
  const siteId = site.manifest.site.site_id;
  const siteName = site.manifest.site.name;
  const heightM = site.manifest.horizon.observer_heights_m[height];
  const shared = sharedRange || [t.start_utc, t.end_utc];
  const rows = [];
  for (let i = 0; i < t.count; i++) {
    for (const body of BODIES) {
      const series = data.series[body];
      if (!series) continue;
      rows.push([
        canLabelUtc(site) ? sampleUtc(site, i) : "",
        i,
        sampleEt(site, i),
        t.start_utc,
        t.end_utc,
        shared[0],
        shared[1],
        siteId,
        siteName,
        site.id,
        heightM,
        NAMES[body],
        series.az[i],
        series.el[i],
        series.margin[i],
        series.fraction[i],
      ]);
    }
  }
  return rows;
}

export function seriesCsv(sites, sharedRange = null) {
  const rows = [];
  for (const item of sites) rows.push(...rowsForSite(item.site, item.data, item.height, sharedRange));
  return [SERIES_COLUMNS, ...rows].map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
}

export function downloadCsv(filename, text) {
  const blob = new Blob(["\ufeff", text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
