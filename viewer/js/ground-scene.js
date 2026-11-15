// One ground view of a published site at a stated instant, for a page that shows it on its own
// (the landing page of the site). The steps are those of a comparison pane in compare.js: the
// index and the site package (checked as always), the sample of the package nearest to the
// instant, the Sun and Earth series of the observer height, the terrain patches and the
// direction-table record (ground.js), drawn by the renderer of the viewers (view3d.js).
// Nothing is computed here; the view only looks values up.

import { loadIndex, loadSite, PackageError } from "./package.js";
import { containing, etOfUtc, loadSiteData, nearestSample, sampleEt, sampleUtc, siteFileUrl } from "./panel.js";
import { groundData, groundInput } from "./ground.js";

// A ground view in `container` that can show several sites in turn (one renderer; each site
// and its arrays are loaded once). Throws if WebGL is not available.
export async function createGroundScene(container, { indexUrl = siteFileUrl("packages/index.json"), onCheck } = {}) {
  const view3dModule = await import("./view3d.js");
  const view = view3dModule.createView(container, { onCheck });
  const index = await loadIndex(indexUrl);
  const tables = {}, loaded = {};

  async function load(siteId, heightM) {
    const key = `${siteId}@${heightM}`;
    if (!loaded[key]) {
      loaded[key] = (async () => {
        const entry = index.sites.find((s) => s.site_id === siteId);
        if (!entry) throw new PackageError(`site ${siteId} is not in the index`);
        const site = await loadSite(index.base, entry);
        const h = site.manifest.horizon.observer_heights_m.indexOf(heightM);
        if (h < 0) throw new PackageError(`${siteId} has no observer height of ${heightM} m`);
        const [data, g] = await Promise.all([loadSiteData(site, h), groundData(site, index, tables)]);
        return { site, h, data, g };
      })();
    }
    return loaded[key];
  }

  return {
    // Show site `siteId` at observer height `heightM` (metres) at the package sample nearest to
    // `utc`. Returns what was drawn: the sample, its UTC label, and the package's Sun and Earth
    // shares of the disc above the horizon at that sample.
    async show({ siteId, heightM, utc }) {
      const { site, h, data, g } = await load(siteId, heightM);
      const i = nearestSample(site, etOfUtc(site, Date.parse(utc)));
      view.update(groundInput({ site, h, i, data, g, view3dModule }));
      // The package's Sun blocker whose intervals hold this sample (timeline.blockers), if any.
      const et = sampleEt(site, i);
      const blocker = (site.manifest.timeline.blockers || [])
        .find((b) => b.body === "SUN" && b.height_index === h && containing(b.intervals_et_s, et) >= 0) || null;
      return {
        siteId, name: site.manifest.site.name, packageId: site.id, h, i, utc: sampleUtc(site, i),
        sunFraction: data.series.SUN ? data.series.SUN.fraction[i] : null,
        earthFraction: data.series.EARTH ? data.series.EARTH.fraction[i] : null,
        sunBlocker: blocker && { obstacleId: blocker.obstacle_id, distanceM: blocker.peak_distance_m, nearField: Boolean(blocker.near_field) },
        terrainCheck: view.terrainCheck(),
      };
    },
    command: (id) => view.command(id),
  };
}
