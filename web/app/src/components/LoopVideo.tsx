import { useEffect, useRef, useState } from "react";
import { useInView } from "./useInView";

/** True when the visitor asked the system for less motion. */
export function usePrefersReducedMotion(): boolean {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduce, setReduce] = useState(() => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(query).matches);
  useEffect(() => {
    if (!window.matchMedia) return;
    const list = window.matchMedia(query);
    const change = () => setReduce(list.matches);
    list.addEventListener("change", change);
    return () => list.removeEventListener("change", change);
  }, []);
  return reduce;
}

interface Props {
  src: string;
  /** First frame of the clip, shown while it loads. */
  poster: string;
  /** Picture shown without the clip (reduced motion, no autoplay); the poster if not given. */
  still?: string;
  label: string;
  className?: string;
  /** Start loading at once (hero) instead of when the video comes near the screen. */
  eager?: boolean;
}

/**
 * A muted, looping clip that plays inline without controls, with its poster image first. With
 * reduced motion, or if the clip cannot play, only the still picture is shown.
 */
export function LoopVideo({ src, poster, still, label, className, eager = false }: Props) {
  const reduce = usePrefersReducedMotion();
  const box = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const near = useInView(box, "200px");
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const active = !reduce && !failed && (eager || near);

  useEffect(() => {
    const v = video.current;
    if (!active || !v) return;
    v.muted = true; // set as a property too: some browsers ignore the attribute for autoplay
    // A refused play() (autoplay blocked, page in the background) is not an error: the still stays
    // visible until the clip really plays, and autoPlay starts it when the browser allows.
    v.play().catch(() => undefined);
  }, [active]);

  return (
    <div ref={box} className={`loop-video ${playing ? "playing" : ""} ${className ?? ""}`}>
      <img src={still ?? poster} alt={label} decoding="async" loading={eager ? "eager" : "lazy"} />
      {active && (
        <video ref={video} src={src} poster={poster} muted loop playsInline autoPlay preload={eager ? "auto" : "metadata"}
          aria-hidden="true" onPlaying={() => setPlaying(true)} onError={() => setFailed(true)} />
      )}
    </div>
  );
}
