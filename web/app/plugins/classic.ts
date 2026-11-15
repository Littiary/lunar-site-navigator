// Build-time link to the classic comparison page (web/viewer/compare.html).
//
// The comparison module viewer/js/compare.js fills each pane from the <template id="pane-template">
// of the page it runs on. The React comparison page uses that template as it stands in
// compare.html, read here at build time, so the two pages cannot drift apart.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import { REPO } from "./facts";

const VIRTUAL = "virtual:lsn-classic";
export const CLASSIC_PAGE = resolve(REPO, "web", "viewer", "compare.html");

/** The inner HTML of <template id="pane-template"> of the classic comparison page, unchanged. */
export function paneTemplate(html = readFileSync(CLASSIC_PAGE, "utf-8")): string {
  const match = /<template id="pane-template">([\s\S]*?)<\/template>/.exec(html);
  if (!match) throw new Error(`${CLASSIC_PAGE} has no <template id="pane-template">`);
  return match[1];
}

// `import { paneTemplate } from "virtual:lsn-classic"` in the app.
export function classicPlugin(): Plugin {
  const resolved = "\0" + VIRTUAL;
  return {
    name: "lsn-classic",
    resolveId(id) { return id === VIRTUAL ? resolved : null; },
    load(id) {
      if (id !== resolved) return null;
      this.addWatchFile(CLASSIC_PAGE);
      return `export const paneTemplate = ${JSON.stringify(paneTemplate())};\n`;
    },
  };
}
