"""Static evidence page: one self-contained HTML file built from site packages.

The page shows, for each site package, the two charts, the summary metrics and events at
the default observer height, the method cards with their validation status, the data
versions, and (optionally) the validation card of the ephemeris stream. It loads nothing
from the network: charts are embedded as data URIs and the style sheet is inline, so the
file opens offline, in a private window and on a phone. All numbers come from the
packages and the card; this module only formats them.

Usage (from ``web/``)::

    python -m lsn_web.evidence <site package dir> [...] [--card validation_card.json] --out index.html
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from html import escape
from pathlib import Path

if __package__ in (None, ""):  # allow `python web/lsn_web/evidence.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web import charts
    from lsn_web.package import SitePackage, load_site_package
else:
    from . import charts
    from .package import SitePackage, load_site_package

REPOSITORY = "https://github.com/Littiary/lunar-site-navigator"

CSS = """
:root { --bg: #ffffff; --surface: #f6f8fa; --ink: #1b1f24; --muted: #57606a; --line: #d0d7de;
        --accent: #1f5fbf; --warn: #b42318; --warn-bg: #fdecea; --ok: #1a7f37; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0d1117; --surface: #161b22; --ink: #e6edf3; --muted: #9da7b3; --line: #30363d;
          --accent: #6ea8fe; --warn: #ff7b72; --warn-bg: #3a1514; --ok: #56d364; }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 4px; }
h2 { font-size: 1.25rem; margin: 40px 0 8px; padding-top: 8px; border-top: 1px solid var(--line); }
h3 { font-size: 1.05rem; margin: 24px 0 8px; }
p, li { max-width: 72ch; }
a { color: var(--accent); }
code, .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.85em; overflow-wrap: anywhere; }
.muted { color: var(--muted); }
nav { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 12px 0 0; font-size: 0.95rem; }
.banner { background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn); border-radius: 6px;
          padding: 10px 14px; margin: 16px 0; font-weight: 600; }
.banner p { margin: 4px 0 0; font-weight: 400; }
figure { margin: 16px 0; }
.chart { overflow-x: auto; -webkit-overflow-scrolling: touch; border: 1px solid var(--line); border-radius: 6px; }
.chart img { width: 100%; min-width: 760px; height: auto; display: block; }
figcaption { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
.table { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 8px 0 16px; border: 1px solid var(--line); border-radius: 6px; }
table { border-collapse: collapse; width: 100%; min-width: 720px; font-size: 0.9rem; }
td code { white-space: nowrap; }
th, td { text-align: left; vertical-align: top; padding: 6px 10px; border-bottom: 1px solid var(--line); }
th { background: var(--surface); font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 8px 0 16px; }
dl.facts dt { color: var(--muted); }
dl.facts dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 560px) { dl.facts { grid-template-columns: 1fr; } dl.facts dd { margin-bottom: 6px; } }
details { border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; margin: 8px 0; background: var(--surface); }
summary { cursor: pointer; font-weight: 600; }
.status { display: inline-block; padding: 0 8px; border-radius: 10px; font-size: 0.8rem; font-weight: 600;
          border: 1px solid currentColor; white-space: nowrap; }
.status.pass, .status.externally-validated, .status.analytic-test-passed { color: var(--ok); }
.status.fail, .status.unverified, .status.synthetic, .status.unknown { color: var(--warn); }
footer { margin-top: 48px; font-size: 0.85rem; color: var(--muted); }
"""


# ---------------------------------------------------------------- small helpers

def e(value) -> str:
    return escape("" if value is None else str(value))


def sig(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    if value == 0:
        return "0"
    return f"{value:.{digits}g}"


def status_badge(status: str) -> str:
    return f'<span class="status {e(status.lower())}">{e(status)}</span>'


def table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td class="num">{cell}</td>' if i in numeric else f"<td>{cell}</td>" for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def facts(pairs: list[tuple[str, str]]) -> str:
    return '<dl class="facts">' + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in pairs) + "</dl>"


def svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def metric_value(metric: dict) -> str:
    value, unit = metric.get("value"), metric.get("unit")
    if value is None:
        return "—"
    if unit == "1":
        return f"{charts.num(100 * value, 1)} %"
    if unit == "s":
        return f"{charts.num(value / 3600, 1)} h ({charts.num(value, 0)} s)"
    return f"{sig(value, 4)} {e(unit)}"


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


# ---------------------------------------------------------------- sections

def site_section(site: SitePackage) -> str:
    m = site.manifest
    s = m["site"]
    horizon = m["horizon"]
    index = horizon["default_height_index"]
    height = horizon["observer_heights_m"][index]
    timeline = site.timeline
    out = [f'<h2 id="site-{e(slug(s["site_id"]))}">{e(s["name"])}</h2>']
    if site.synthetic:
        out.append(
            '<div class="banner">SYNTHETIC SAMPLE DATA — not a result'
            f"<p>{e(m.get('synthetic_notice', ''))}</p></div>"
        )
    for warning in m.get("warnings", []):
        out.append(f'<div class="banner">Package warning<p>{e(warning)}</p></div>')
    pairs = [
        ("Package", f'<span class="mono">{e(site.package_id)}</span> (status {e(m["status"])}, contract {e(m["contract"]["version"])})'),
        ("Content SHA-256", f'<span class="mono">{e(m["content_sha256"])}</span>'),
        ("Site", f"{charts.num(s['lat_deg'], 5)}°, {charts.num(s['lon_deg'], 5)}° (planetocentric latitude, east-positive longitude)"),
        ("Reference frame", f'<span class="mono">{e(s["frame"])}</span>'),
        ("Reference sphere radius", e(charts.km(charts.quantity(site, s["reference_radius_m"])))),
        ("Terrain height at the site", f"{charts.num(charts.quantity(site, s['surface_height_m']), 1)} m above the sphere"),
        ("Observer height shown", f"{charts.num(height)} m above terrain (computed heights: "
                                  f"{', '.join(charts.num(h) for h in horizon['observer_heights_m'])} m)"),
        ("Horizon search radius", e(charts.km(charts.quantity(site, horizon["max_range_m"])))),
    ]
    if timeline:
        t = timeline["time"]
        pairs.append(("Time window", f"{e(t['start_utc'])} to {e(t['end_utc'])} UTC "
                                     f"(grid {e(t['scale'])}, step {charts.num(t['step_s'])} s, {t['count']} samples)"))
    out.append(facts(pairs))

    panorama = charts.horizon_panorama(site)
    out.append(
        f'<figure><div class="chart"><img src="{svg_data_uri(panorama)}" alt="{e("Terrain horizon panorama of " + s["name"])}"></div>'
        "<figcaption>Terrain horizon at the observer height shown, with the paths of the Sun and Earth disc "
        "centres. Drawn from the package arrays without recomputation. On a narrow screen, swipe the chart "
        "sideways.</figcaption></figure>"
    )
    if not timeline:
        out.append('<p class="muted">This package has no time window, so windows, events and metrics are not shown.</p>')
        return "\n".join(out)

    strip = charts.window_strip([site])
    out.append(
        f'<figure><div class="chart"><img src="{svg_data_uri(strip)}" alt="{e("Lighting and direct-to-Earth windows of " + s["name"])}"></div>'
        "<figcaption>Visibility windows from the package (<code>timeline.windows</code>).</figcaption></figure>"
    )

    metrics = [mt for mt in timeline.get("metrics", []) if mt.get("height_index") == index]
    if metrics:
        out.append(f"<h3>Summary at {charts.num(height)} m</h3>")
        out.append(table(
            ["Quantity", "Value", "Method", "Status"],
            [[e(mt["label"]), metric_value(mt), f'<code>{e(mt["method"])}</code>', status_badge(site.method_status(mt["method"]))]
             for mt in metrics],
            numeric={1},
        ))

    events = [ev for ev in timeline.get("events", []) if ev.get("height_index") == index]
    out.append(f"<h3>Rise and set events at {charts.num(height)} m</h3>")
    if events:
        out.append(table(
            ["Time (UTC)", "Body", "Event", "Body azimuth", "Terrain horizon elevation", "Obstacle distance", "Status"],
            [[f'<span class="mono">{e(ev["utc"])}</span>', e(ev["body"].title()), e(ev["type"]),
              f"{charts.num(ev['azimuth_deg'], 2)}°", f"{charts.num(ev['horizon_elevation_deg'], 3)}°",
              "—" if ev.get("obstacle_distance_m") is None else e(charts.km(ev["obstacle_distance_m"])),
              status_badge(site.method_status(ev["method"]))]
             for ev in events],
            numeric={3, 4, 5},
        ))
    else:
        out.append('<p class="muted">No rise or set event in the time window at this height.</p>')
    return "\n".join(out)


def methods_section(sites: list[SitePackage]) -> str:
    out = ['<h2 id="methods">Methods behind the numbers</h2>',
           '<p>Each number above refers to one of these method cards. A status of <em>unverified</em> or '
           "<em>synthetic</em> means the number has not been checked against an independent source.</p>"]
    for site in sites:
        if len(sites) > 1:
            out.append(f"<h3>{e(site.manifest['site']['name'])}</h3>")
        for method_id, card in site.manifest.get("methods", {}).items():
            validation = card.get("validation", {})
            evidence = validation.get("evidence") or []
            limits = card.get("limits") or []
            data = card.get("data") or []
            parameters = card.get("parameters") or {}
            pairs = [
                ("Definition", e(card.get("definition"))),
                ("Algorithm", e(card.get("algorithm"))),
                ("Frame", e(card.get("frame"))),
                ("Time scale", e(card.get("time_scale"))),
                ("Data", e(", ".join(str(d) for d in data)) or "—"),
                ("Parameters", f'<span class="mono">{e(json.dumps(parameters, sort_keys=True))}</span>' if parameters else "—"),
                ("Evidence", e("; ".join(str(x) for x in evidence)) or "—"),
                ("Limits", "<br>".join(e(x) for x in limits) or "—"),
            ]
            out.append(
                f"<details><summary><code>{e(method_id)}</code> — {e(card.get('title'))} "
                f"{status_badge(validation.get('status', 'unknown'))}</summary>{facts(pairs)}</details>"
            )
    return "\n".join(out)


def data_section(sites: list[SitePackage]) -> str:
    out = ['<h2 id="data">Data and software versions</h2>']
    for site in sites:
        m = site.manifest
        inputs, prov = m.get("inputs", {}), m.get("provenance", {})
        software = prov.get("software", {})
        if len(sites) > 1:
            out.append(f"<h3>{e(m['site']['name'])}</h3>")
        dem = inputs.get("dem") or {}
        table_ref = inputs.get("direction_table") or {}
        out.append(facts([
            ("Elevation data set", f'<span class="mono">{e(dem.get("dem_set_id"))}</span>'),
            ("Direction table", f'<span class="mono">{e(table_ref.get("package_id"))}</span> '
                                f'(content SHA-256 <span class="mono">{e(table_ref.get("content_sha256"))}</span>)'),
            ("Science version", e(inputs.get("science_version"))),
            ("Package written", f"{e(prov.get('created_utc'))} by core {e(software.get('core_version'))}, "
                                f'commit <span class="mono">{e(software.get("git_commit"))}</span>'
                                + (" (with uncommitted changes)" if software.get("git_dirty") else "")),
        ]))
        layers = dem.get("layers") or []
        if layers:
            out.append(table(
                ["Layer", "Product", "Version", "Pixel", "Source", "SHA-256"],
                [[e(l.get("layer_id")), e(l.get("product_id")), e(l.get("version")), f"{charts.num(l.get('pixel_m') or 0)} m",
                  f'<span class="mono">{e(l.get("source_url"))}</span>', f'<span class="mono">{e(l.get("sha256"))}</span>']
                 for l in layers],
            ))
    out.append(f'<p>Every third-party data set, library and tool is listed with its licence and source in '
               f'<a href="{REPOSITORY}/blob/main/CREDITS.md">CREDITS.md</a>.</p>')
    return "\n".join(out)


def validation_section(card: dict) -> str:
    summary, core, source = card["summary"], card.get("core", {}), card.get("generated_from", {})
    out = [
        '<h2 id="validation">Validation of the ephemeris, time and event layer</h2>',
        f"<p><strong>{summary['passed']} of {summary['checks']} checks pass</strong>"
        + (f", {summary['failed']} fail" if summary.get("failed") else "") + ". "
        f"Core: frame <code>{e(core.get('frame'))}</code>, aberration correction <code>{e(core.get('aberration_correction'))}</code>, "
        f"sphere {e(core.get('reference_radius_km'))} km, kernel set <code>{e(core.get('kernel_set_id'))}</code>.</p>",
        f'<p class="muted">From <code>validation/card/validation_card.json</code>, generated {e(card.get("generated_utc"))} '
        f'from commit <span class="mono">{e(source.get("commit"))}</span>'
        + (" with uncommitted changes" if source.get("uncommitted_changes") else "")
        + ". Each threshold was fixed before the comparison it governs.</p>",
    ]

    def threshold(check: dict) -> str:
        t = check.get("threshold") or {}
        return f"{e(t.get('comparison', ''))} {sig(t.get('value'), 4)} {e(t.get('unit', ''))}".strip()

    def measured(check: dict) -> str:
        mv = check.get("measured") or {}
        return f"{sig(mv.get('value'), 3)} {e(mv.get('unit', ''))}".strip()

    out.append(table(
        ["What was compared", "Against", "Cases", "Threshold", "Measured", "Result"],
        [[e(c["quantity"]), e(c.get("compared_against")), e(c.get("cases")), threshold(c), measured(c),
          status_badge(c.get("status", "unknown"))] for c in card["checks"]],
        numeric={3, 4},
    ))
    if card.get("not_validated"):
        out.append("<h3>Not validated</h3><ul>" + "".join(
            f"<li><strong>{e(item['item'])}</strong> {status_badge(item.get('state', 'unknown'))}<br>{e(item.get('reason'))}</li>"
            for item in card["not_validated"]) + "</ul>")
    if card.get("limits"):
        out.append("<h3>Limits</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in card["limits"]) + "</ul>")
    return "\n".join(out)


# ---------------------------------------------------------------- page

def build_page(sites: list[SitePackage], card_path: str | Path | None = None) -> str:
    card = json.loads(Path(card_path).read_text(encoding="utf-8")) if card_path else None
    nav = [(f"#site-{slug(s.manifest['site']['site_id'])}", s.manifest["site"]["name"]) for s in sites]
    nav += [("#methods", "Methods"), ("#data", "Data")]
    if card:
        nav.append(("#validation", "Validation"))
    banner = ""
    if any(site.synthetic for site in sites):
        banner = ('<div class="banner">SYNTHETIC SAMPLE DATA — this page shows invented interface-test values, '
                  "not results.</div>")
    ids = ", ".join(site.package_id for site in sites)
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        "<title>Lunar Site Navigator evidence</title>",
        f"<style>{CSS.strip()}</style>",
        "</head>",
        "<body><main>",
        "<header>",
        "<h1>Lunar Site Navigator — evidence</h1>",
        "<p>For a chosen point on the Moon, the science core computes the local 360° terrain horizon from NASA LOLA "
        "elevation data and finds when the Sun and the Earth are above that horizon. This page shows those results "
        "with the method, reference frame, data version and validation status of every number.</p>",
        f'<p class="muted">Built from package(s) <span class="mono">{e(ids)}</span>. Numbers are read from the packages '
        "and are not recomputed on this page. The page needs no network connection.</p>",
        "<nav>" + "".join(f'<a href="{e(href)}">{e(label)}</a>' for href, label in nav) + "</nav>",
        banner,
        "</header>",
    ]
    parts += [site_section(site) for site in sites]
    parts.append(methods_section(sites))
    parts.append(data_section(sites))
    if card:
        parts.append(validation_section(card))
    parts += [
        f'<footer><p>Team Kestro Aerospace, NASA Space Apps Challenge 2026. Source code and data provenance: '
        f'<a href="{REPOSITORY}">{REPOSITORY}</a>. Candidate sites are the project\'s own points, not official '
        "landing sites.</p></footer>",
        "</main></body>",
        "</html>",
    ]
    return "\n".join(part for part in parts if part) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the static evidence page from site packages.")
    parser.add_argument("packages", nargs="+", help="site package directories (each holds manifest.json)")
    parser.add_argument("--card", help="validation_card.json of the ephemeris stream (optional)")
    parser.add_argument("--out", required=True, help="output HTML file")
    args = parser.parse_args(argv)
    sites = [load_site_package(path) for path in args.packages]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(sites, args.card), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
