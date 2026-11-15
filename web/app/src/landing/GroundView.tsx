import { useEffect, useRef, useState } from "react";
import { SectionHead } from "../components/Actions";
import { useInView } from "../components/useInView";
import { percent } from "../site/format";
import { at } from "../site/links";
import stillRidge from "../assets/c_key_moment_near_ridge.jpg";

// "See it in 3-D": the live ground view of the viewers (web/viewer/js/view3d.js, through
// ground-scene.js) at one instant, loaded from the published viewer/ folder only when the section
// comes near the screen, so the top of the page stays light. Every value in the caption is
// returned by the package lookup; this file only formats it.

const INSTANT = "2026-12-07T04:00:00Z";
const HEIGHT_M = 2;
const SITES = [
  { id: "shackleton-rim-crest", label: "Shackleton" },
  { id: "de-gerlache-rim-crest", label: "de Gerlache" },
] as const;
type SiteId = (typeof SITES)[number]["id"];

const SCENE_MODULE = at("viewer/js/ground-scene.js");

/** What ground-scene.js reports for the drawn site and sample. */
interface Shown {
  siteId: string; name: string; packageId: string; h: number; i: number; utc: string;
  sunFraction: number | null; earthFraction: number | null;
  sunBlocker: { obstacleId: number; distanceM: number; nearField: boolean } | null;
}
interface GroundScene { show(request: { siteId: string; heightM: number; utc: string }): Promise<Shown> }
interface GroundSceneModule { createGroundScene(container: HTMLElement): Promise<GroundScene> }

type State = { phase: "waiting" | "loading" } | { phase: "shown"; shown: Shown } | { phase: "failed"; message: string };

function plannerLink(i: number | null): string {
  const q = new URLSearchParams({ a: SITES[0].id, b: SITES[1].id, ha: "2", hb: "2", view: "ground" });
  if (i !== null) q.set("i", String(i));
  return at(`compare/?${q}`);
}

function Caption({ shown }: { shown: Shown }) {
  const share = (x: number | null) => (x === null ? "n/a" : percent(x, 0));
  const b = shown.sunBlocker;
  return (
    <p className="g3d-caption">
      <strong>{shown.name}</strong>, {shown.utc.slice(0, 16).replace("T", " ")} UTC, observer {HEIGHT_M} m.
      {" "}From the package: Sun {share(shown.sunFraction)} and Earth {share(shown.earthFraction)} of the disc above the horizon
      {b ? <>; the Sun is behind the terrain {Math.round(b.distanceM)} m away (obstacle {b.obstacleId}{b.nearField ? ", within 1 km" : ""})</> : null}.
    </p>
  );
}

export function GroundView() {
  const section = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const scene = useRef<Promise<GroundScene> | null>(null);
  const near = useInView(section);
  const [siteId, setSiteId] = useState<SiteId>(SITES[0].id);
  const [state, setState] = useState<State>({ phase: "waiting" });

  // A link to #see-3d: the page is drawn after the browser looked for the anchor, so scroll here.
  useEffect(() => {
    if (location.hash === "#see-3d") section.current?.scrollIntoView();
  }, []);

  useEffect(() => {
    if (!near || !canvas.current) return;
    let live = true;
    setState((s) => (s.phase === "shown" ? s : { phase: "loading" }));
    scene.current ??= (import(/* @vite-ignore */ SCENE_MODULE) as Promise<GroundSceneModule>)
      .then((m) => m.createGroundScene(canvas.current!));
    scene.current
      .then((s) => s.show({ siteId, heightM: HEIGHT_M, utc: INSTANT }))
      .then((shown) => { if (live) setState({ phase: "shown", shown }); })
      .catch((e: unknown) => { if (live) setState({ phase: "failed", message: e instanceof Error ? e.message : String(e) }); });
    return () => { live = false; };
  }, [near, siteId]);

  const shown = state.phase === "shown" ? state.shown : null;
  return (
    <section ref={section} className="section wrap g3d" id="see-3d" aria-labelledby="g3d-h">
      <SectionHead id="g3d-h" eyebrow="See it in 3-D" title="The moment the ridge hides the Sun, in the browser." />
      <p className="muted g3d-lead">
        The ground view of the planner at {INSTANT.slice(0, 16).replace("T", " ")} UTC, drawn from the package terrain.
        Drag to look round; the wheel zooms. Switch to de Gerlache to see the same instant there.
      </p>
      <div className="g3d-bar">
        <div className="segmented" role="group" aria-label="Site">
          {SITES.map((s) => (
            <button key={s.id} type="button" aria-pressed={siteId === s.id} onClick={() => setSiteId(s.id)}>{s.label}</button>
          ))}
        </div>
        <a className="btn btn-ghost btn-small" href={plannerLink(shown ? shown.i : null)}>Open in the planner <span aria-hidden="true">→</span></a>
      </div>
      <div className="g3d-frame">
        <div ref={canvas} className="view3d g3d-view" aria-label="Interactive ground view" />
        {state.phase !== "shown" && state.phase !== "failed" && (
          <div className="g3d-overlay"><p className="loading-status">{state.phase === "loading" ? "Loading the site package and its terrain…" : "The 3-D view loads when you get here."}</p></div>
        )}
        {state.phase === "failed" && (
          <div className="g3d-overlay g3d-failed" style={{ backgroundImage: `url(${stillRidge})` }}>
            <p>The live view could not start here ({state.message}). This is the same moment rendered in the Unreal scene.</p>
          </div>
        )}
      </div>
      {shown ? <Caption shown={shown} /> : <p className="g3d-caption muted">Observer {HEIGHT_M} m above the ground. Values appear once the package is loaded.</p>}
      <p className="source">
        Terrain, light and shadows are drawn for orientation; the horizon line and the Sun and Earth positions are those of the
        package. The same renderer draws the ground view of the planner.
      </p>
    </section>
  );
}
