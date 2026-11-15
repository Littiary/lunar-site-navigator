// Build-time facts for the landing page, read from the repository files the site is built from.
//
// Nothing is computed: every value is a field of a published package or of the validation card,
// copied as it is. The landing page rounds them for display and names the package they come from.
// The comparison page does not use this module: it reads the packages at run time through the
// viewer modules (web/viewer/js), exactly as the classic page does.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin } from "vite";

export const REPO = resolve(__dirname, "..", "..", "..");
const KEY_SITE = "shackleton-rim-crest";
const VIRTUAL = "virtual:lsn-facts";

type Json = Record<string, any>;

function readJson(path: string): Json {
  return JSON.parse(readFileSync(path, "utf-8"));
}

export interface Facts {
  contract: string;
  sites: { site_id: string; name: string; programme: string | null; category: string | null; lat_deg: number; lon_deg: number }[];
  ridge: {
    site_id: string; site_name: string; package_id: string; observer_height_m: number;
    lost_s: number; share_of_lost: number; peak_distance_m: number; near_field: boolean;
    window_start_utc: string; window_end_utc: string;
  } | null;
  card: {
    title: string; generated_utc: string; checks: number; passed: number; failed: number;
    rows: { id: string; group: string; quantity: string; status: string }[];
    failedRows: { id: string; group: string; quantity: string; compared_against: string; cases: string;
      threshold: { value: number; unit: string; comparison: string }; measured: { value: number; unit: string };
      limit: string; evidence: string }[];
  };
}

export function readFacts(repo = REPO): Facts {
  const index = readJson(resolve(repo, "packages", "index.json"));
  const siteEntries = index.packages.filter((p: Json) => p.kind === "site");
  const sites = siteEntries.map((p: Json) => ({
    site_id: p.site_id, name: p.name, programme: p.programme ?? null, category: p.category ?? null, lat_deg: p.lat_deg, lon_deg: p.lon_deg,
  }));

  let ridge: Facts["ridge"] = null;
  const entry = siteEntries.find((p: Json) => p.site_id === KEY_SITE);
  if (entry) {
    const manifestPath = resolve(repo, "packages", entry.path, "manifest.json");
    const manifest = readJson(manifestPath);
    const h = manifest.horizon.default_height_index;
    // The obstacle that costs the site the most sunlight at its default observer height:
    // the blocker record of the package with the largest lost_s (SPEC: timeline.blockers).
    const blockers = (manifest.timeline.blockers || []).filter((b: Json) => b.body === "SUN" && b.height_index === h);
    blockers.sort((a: Json, b: Json) => b.lost_s - a.lost_s);
    const top = blockers[0];
    if (top) {
      ridge = {
        site_id: KEY_SITE, site_name: manifest.site.name, package_id: manifest.package_id,
        observer_height_m: manifest.horizon.observer_heights_m[h],
        lost_s: top.lost_s, share_of_lost: top.share_of_lost, peak_distance_m: top.peak_distance_m, near_field: Boolean(top.near_field),
        window_start_utc: manifest.timeline.time.start_utc, window_end_utc: manifest.timeline.time.end_utc,
      };
    }
  }

  const card = readJson(resolve(repo, "validation", "card", "validation_card.json"));
  const checks: Json[] = card.checks || [];
  return {
    contract: index.contract.version,
    sites,
    ridge,
    card: {
      title: card.title, generated_utc: card.generated_utc,
      checks: card.summary.checks, passed: card.summary.passed, failed: card.summary.failed,
      rows: checks.map((c) => ({ id: c.id, group: c.group, quantity: c.quantity, status: c.status })),
      failedRows: checks.filter((c) => c.status !== "PASS").map((c) => ({
        id: c.id, group: c.group, quantity: c.quantity, compared_against: c.compared_against, cases: c.cases,
        threshold: c.threshold, measured: c.measured, limit: c.limit, evidence: c.evidence,
      })),
    },
  };
}

// `import facts from "virtual:lsn-facts"` in the app. The digest of the sources is part of the
// module, so a rebuild after a package or card change gives a different bundle.
export function factsPlugin(repo = REPO): Plugin {
  const resolved = "\0" + VIRTUAL;
  return {
    name: "lsn-facts",
    resolveId(id) { return id === VIRTUAL ? resolved : null; },
    load(id) {
      if (id !== resolved) return null;
      const facts = readFacts(repo);
      const digest = createHash("sha256").update(JSON.stringify(facts)).digest("hex").slice(0, 16);
      return `export const digest = ${JSON.stringify(digest)};\nexport default ${JSON.stringify(facts)};\n`;
    },
  };
}
