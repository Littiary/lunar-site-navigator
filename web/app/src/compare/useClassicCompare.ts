import { useEffect } from "react";
import { at } from "../site/links";

// The comparison module of the classic page. It is not bundled: it is loaded from the published
// viewer/ folder, so this page runs the very file classic.html runs (package loading with SHA-256
// checks, status cards, charts, sky panorama, ground view, calendar, pair table). It finds its
// elements by id and data-role in the document and fills them; it runs once per page load.
export const CLASSIC_MODULE = at("viewer/js/compare.js");

let started = false;

/** Start the classic comparison module once the page's elements are in the document. */
export function useClassicCompare(): void {
  useEffect(() => {
    if (started) return; // React may run effects twice in development
    started = true;
    import(/* @vite-ignore */ CLASSIC_MODULE).catch((e: unknown) => {
      const box = document.getElementById("error");
      if (!box) return;
      box.textContent = `The comparison module could not be loaded (${CLASSIC_MODULE}): ${e instanceof Error ? e.message : String(e)}`;
      box.hidden = false;
    });
  }, []);
}
