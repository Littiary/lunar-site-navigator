// Addresses of the site files the app reads at run time, and the notice of the site.
// BASE is the site root ("/lunar-site-navigator/"); every file below is published there by
// `python -m lsn_web.site`, next to this app.

export const BASE: string = import.meta.env.BASE_URL;
export const at = (path: string) => `${BASE}${path}`;

export const GITHUB = "https://github.com/Littiary/lunar-site-navigator";
export const repoFile = (path: string) => `${GITHUB}/blob/main/${path}`;
export const SLIDES = at("submission/Lunar_Site_Navigator_backup_slides.pdf");

export interface NoticeFile {
  notice: string | null;
  validation: { checks: number; passed: number; failed: number; failed_ids: string[] } | null;
}

// notice.json of the site build: the notice banner (null = none) and the card's counts.
export async function loadNotice(): Promise<NoticeFile | null> {
  try {
    const response = await fetch(at("notice.json"), { cache: "no-cache" });
    if (!response.ok) return null;
    return (await response.json()) as NoticeFile;
  } catch {
    return null;
  }
}
