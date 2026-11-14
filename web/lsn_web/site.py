"""Build the public site in one command: the evidence page and the charts as static files.

Output folder (default ``web/dist/site``)::

    index.html          the evidence page (self-contained; charts embedded)
    charts/*.svg        the same charts as separate files, linked from the page
    .nojekyll           serve the files as they are on GitHub Pages

The notice shown on the page and on every chart is read from a text file (default
``web/site_notice.txt``). An empty or missing file means no notice. The output depends only
on the packages, the validation card and the notice, so a rebuild gives identical bytes.

Usage (from ``web/``; every argument has a default)::

    python -m lsn_web.site [--packages ../packages/index.json] [--card ../validation/card/validation_card.json]
                           [--notice-file site_notice.txt] [--out dist/site]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python web/lsn_web/site.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web import charts, evidence
    from lsn_web.package import load_packages
else:
    from . import charts, evidence
    from .package import load_packages

WEB = Path(__file__).resolve().parent.parent
REPO = WEB.parent


def read_notice(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = " ".join(path.read_text(encoding="utf-8").split())
    return text or None


def build(packages: list[str], card: Path | None, notice: str | None, out: Path) -> list[Path]:
    sites = load_packages(packages)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    written = []

    def write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)

    for site in sites:
        write(out / "charts" / f"horizon_panorama__{site.manifest['site']['site_id']}.svg", charts.horizon_panorama(site, notice))
    if any(site.timeline for site in sites):
        write(out / "charts" / "window_strip.svg", charts.window_strip(sites, notice))
    write(out / "index.html", evidence.build_page(sites, card, notice, chart_links=True))
    write(out / ".nojekyll", "")
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the static public site from published packages.")
    parser.add_argument("--packages", nargs="+", default=[str(REPO / "packages" / "index.json")],
                        help="index.json files and/or site package directories (default: packages/index.json)")
    parser.add_argument("--card", default=str(REPO / "validation" / "card" / "validation_card.json"),
                        help="validation card of the ephemeris stream; pass an empty string to leave it out")
    parser.add_argument("--notice-file", default=str(WEB / "site_notice.txt"), help="text shown as a banner; empty file = none")
    parser.add_argument("--out", default=str(WEB / "dist" / "site"), help="output folder")
    args = parser.parse_args(argv)
    card = Path(args.card) if args.card else None
    written = build(args.packages, card, read_notice(Path(args.notice_file)), Path(args.out))
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
