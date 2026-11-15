import type { ReactNode } from "react";
import { useNotice } from "../site/notice";
import { Footer } from "./Footer";
import { Nav, type Page } from "./Nav";

/** The frame of every page: skip link, navigation, the notice of the site build, footer. */
export function Shell({ page, children }: { page: Page; children: ReactNode }) {
  const notice = useNotice();
  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <Nav page={page} />
      {notice && <div className="site-notice" role="note">{notice}</div>}
      <div id="content">{children}</div>
      <Footer />
    </>
  );
}
