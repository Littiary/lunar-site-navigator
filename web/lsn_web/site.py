"""Build the public site in one command: the evidence page and the charts as static files.

Output folder (default ``web/dist/site``)::

    index.html          the split-screen comparison viewer
    compare.html        the split-screen comparison viewer
    evidence.html       the evidence page (self-contained; charts embedded)
    accuracy.html       the accuracy and limits page (self-contained)
    charts/*.svg        the same charts as separate files, linked from the page
    viewer/             the interactive viewer (copied from web/viewer)
    packages/           the packages the viewer reads: index.json and exactly the files it lists
    notice.json         the notice and the validation summary of the card, for the viewer
    summary/            the first-screen summary: a catalogue of the sites and, per site, the
                        package fields the first screen shows, copied unchanged (see summary.py)
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
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python web/lsn_web/site.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web import accuracy, charts, evidence, summary
    from lsn_web.package import array_refs, load_packages
else:
    from . import accuracy, charts, evidence, summary
    from .package import array_refs, load_packages

WEB = Path(__file__).resolve().parent.parent
REPO = WEB.parent


def read_notice(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = " ".join(path.read_text(encoding="utf-8").split())
    return text or None


def build(packages: list[str], card: Path | None, notice: str | None, out: Path) -> list[Path]:
    sites = load_packages(packages)
    # The folders this build owns are rewritten from scratch: a package, chart or viewer file
    # left from an earlier build must not be published with this one.
    for owned in ("charts", "viewer", "packages", "summary"):
        if (out / owned).is_dir():
            shutil.rmtree(out / owned)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    written = []

    def write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)

    for site in sites:
        write(out / "charts" / f"horizon_panorama__{site.manifest['site']['site_id']}.svg", charts.horizon_panorama(site, notice))
    if any(site.timeline for site in sites):
        write(out / "charts" / "window_strip.svg", charts.window_strip(sites, notice))
    write(out / "evidence.html", evidence.build_page(sites, card, notice, chart_links=True))
    write(out / "accuracy.html", accuracy.build_page(sites, card, notice, repo=REPO, site_links=True))
    write(out / "index.html", comparison_page())
    write(out / "compare.html", comparison_page())
    write(out / ".nojekyll", "")
    write(out / "notice.json", json.dumps({"notice": notice, "validation": summary.validation_note(card)}) + "\n")
    written += copy_viewer(out / "viewer")
    indexes = [Path(p) for p in packages if Path(p).is_file()]
    if len(indexes) == 1:
        written += copy_packages(indexes[0], out / "packages")
        written += summary.write_summaries(out / "packages" / "index.json", out / "summary")
    return written


def copy_viewer(target: Path) -> list[Path]:
    """Copy web/viewer as it is."""
    source = WEB / "viewer"
    copied = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            dest = target / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            copied.append(dest)
    return copied


def comparison_page() -> str:
    """Adapt the viewer comparison page for the public site root."""
    source = (WEB / "viewer" / "compare.html").read_text(encoding="utf-8")
    return (source
            .replace('href="viewer.css"', 'href="viewer/viewer.css"')
            .replace('href="index.html"', 'href="viewer/index.html"')
            .replace('href="../index.html"', 'href="evidence.html"')
            .replace('href="../evidence.html"', 'href="evidence.html"')
            .replace('href="../accuracy.html"', 'href="accuracy.html"')
            .replace('src="js/compare.js"', 'src="viewer/js/compare.js"')
            .replace('"./vendor/three/three.module.js"', '"./viewer/vendor/three/three.module.js"'))


def copy_packages(index_path: Path, target: Path) -> list[Path]:
    """Copy index.json and exactly the manifest and array files of every package it lists,
    byte for byte, keeping the layout (SPEC 1). Nothing else is copied."""
    root = index_path.parent
    files = ["index.json"]
    for entry in json.loads(index_path.read_text(encoding="utf-8"))["packages"]:
        manifest = json.loads((root / entry["path"] / "manifest.json").read_text(encoding="utf-8"))
        files.append(f"{entry['path']}/manifest.json")
        files += [f"{entry['path']}/{ref['file']}" for ref in array_refs(manifest)]
    copied = []
    for rel in sorted(set(files)):
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, dest)
        if dest.read_bytes() != (root / rel).read_bytes():
            raise OSError(f"copy of {rel} differs from the source")
        copied.append(dest)
    return copied


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
