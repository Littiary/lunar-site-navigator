import { useEffect, useState } from "react";
import { at } from "./links";

/** notice.json of the site build: the banner text (null = none) and the card's counts. */
export interface NoticeFile {
  notice: string | null;
  validation: { checks: number; passed: number; failed: number; failed_ids: string[] } | null;
}

export async function loadNotice(): Promise<NoticeFile | null> {
  try {
    const response = await fetch(at("notice.json"), { cache: "no-cache" });
    return response.ok ? ((await response.json()) as NoticeFile) : null;
  } catch {
    return null;
  }
}

/** The notice text of the site build, once loaded; null while loading or when there is none. */
export function useNotice(): string | null {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    loadNotice().then((file) => { if (live) setText(file?.notice ?? null); });
    return () => { live = false; };
  }, []);
  return text;
}
