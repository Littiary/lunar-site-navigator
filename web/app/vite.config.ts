import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { classicPlugin } from "./plugins/classic";
import { factsPlugin, REPO } from "./plugins/facts";

// Static build for GitHub Pages under /lunar-site-navigator/. Two pages:
//   index.html          landing page
//   compare/index.html  two-site comparison (runs web/viewer/js/compare.js at run time)
// `python -m lsn_web.site` copies dist/ to the site root next to the viewer, the packages and
// the other pages, which the app reads at run time.
export default defineConfig({
  base: "/lunar-site-navigator/",
  plugins: [react(), factsPlugin(), classicPlugin()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        compare: resolve(__dirname, "compare", "index.html"),
      },
    },
  },
  server: { fs: { allow: [REPO] } },
});
