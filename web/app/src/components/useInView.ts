import { useEffect, useState, type RefObject } from "react";

/** True once the element has come within `margin` of the viewport (and stays true). */
export function useInView(ref: RefObject<Element>, margin = "300px"): boolean {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (!("IntersectionObserver" in window)) { setSeen(true); return; }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { setSeen(true); observer.disconnect(); }
    }, { rootMargin: margin });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, margin, seen]);
  return seen;
}
