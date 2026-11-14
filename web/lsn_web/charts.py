"""Static SVG charts drawn from site packages.

* ``horizon_panorama``: the 360 degree terrain horizon at the default observer height, with
  the tracks of the Sun and Earth disc centres over the package's time window.
* ``window_strip``: Sun, Earth and combined visibility windows of one or more sites on one
  shared UTC time axis.

Every chart prints the package id, reference frame, sphere radius, UTC range and the
validation status of the methods behind it, and marks synthetic data. The output depends
only on the package bytes, so a rebuild from the same frozen package is byte-identical.

Usage (from the repository root)::

    python -m lsn_web.charts <site package dir | index.json> [...] --out <folder> [--notice TEXT]
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

if __package__ in (None, ""):  # allow `python web/lsn_web/charts.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web.package import SitePackage, load_packages
else:
    from .package import SitePackage, load_packages

WIDTH = 1200
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
# Rows of the window strip, selected by window id. A package holds several windows per
# subject (for the Sun: visible, any part, full disc, lit, eclipsed), so the subject alone
# does not identify a row. Rows whose window is absent from a package are not drawn.
MIN_VISIBLE_PX = 1.5  # intervals narrower than this get a marker line in the window strip
STRIP_ROWS = (
    ("sun_visible", "Sun visible", "sun", "sun_visible_fraction_of_time"),
    ("earth_visible", "Earth visible", "earth", "earth_visible_fraction_of_time"),
    ("earth_network_dsn", "Two-way link with a DSN complex", "earth", None),
    ("sun_and_earth_visible", "Sun and Earth visible", "combined", None),
    ("sun_eclipsed_by_earth", "Sun eclipsed by the Earth", "eclipse", None),
)

STYLE = """
<style>
  svg { --bg: #ffffff; --ink: #1b1f24; --muted: #57606a; --grid: #d0d7de; --terrain: #8c959f;
        --terrain-fill: #d8dee4; --sun: #b35c00; --earth: #1f5fbf; --combined: #1a7f37; --warn: #b42318; }
  @media (prefers-color-scheme: dark) {
    svg { --bg: #0d1117; --ink: #e6edf3; --muted: #9da7b3; --grid: #30363d; --terrain: #8b949e;
          --terrain-fill: #262c33; --sun: #f0a54a; --earth: #6ea8fe; --combined: #56d364; --warn: #ff7b72; }
  }
  .bg { fill: var(--bg); }
  text { font-family: FONT; fill: var(--ink); }
  .title { font-size: 18px; font-weight: 600; }
  .sub, .foot, .tick, .tick-time, .row { font-size: 12px; fill: var(--muted); }
  .row { fill: var(--ink); }
  .banner { font-size: 14px; font-weight: 700; fill: var(--warn); }
  .grid { stroke: var(--grid); stroke-width: 1; }
  .frame { fill: none; stroke: var(--muted); stroke-width: 1; }
  .terrain { fill: var(--terrain-fill); }
  .horizon { fill: none; stroke: var(--terrain); stroke-width: 1.5; }
  .track { fill: none; stroke-width: 1.2; }
  .track.sun { stroke: var(--sun); }
  .track.earth { stroke: var(--earth); }
  .bar.sun { fill: var(--sun); }
  .bar.earth { fill: var(--earth); }
  .bar.combined { fill: var(--combined); }
  .bar.eclipse { fill: var(--muted); }
  .mark { stroke-width: 2; }
  .mark.sun { stroke: var(--sun); }
  .mark.earth { stroke: var(--earth); }
  .mark.combined { stroke: var(--combined); }
  .mark.eclipse { stroke: var(--ink); }
  .lane { fill: var(--grid); opacity: 0.35; }
</style>
""".replace("FONT", FONT)


# ---------------------------------------------------------------- formatting helpers

def num(value: float, digits: int = 2) -> str:
    text = f"{value:.{digits}f}"
    return "0" if text.strip("-0.") == "" else text.rstrip("0").rstrip(".") if "." in text else text


def km(metres: float) -> str:
    return f"{num(metres / 1000.0, 3)} km"


def text(x: float, y: float, content: str, cls: str, anchor: str = "start") -> str:
    return f'<text x="{num(x)}" y="{num(y)}" class="{cls}" text-anchor="{anchor}">{escape(content)}</text>'


def svg_document(height: int, body: list[str], label: str) -> str:
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
        f'preserveAspectRatio="xMinYMin meet" role="img" aria-label={quoteattr(label)}>'
    )
    return "\n".join([head, STYLE.strip(), f'<rect class="bg" x="0" y="0" width="{WIDTH}" height="{height}"/>', *body, "</svg>"]) + "\n"


def nice_step(span: float, candidates: tuple, max_ticks: int) -> float:
    for step in candidates:
        if span / step <= max_ticks:
            return step
    return candidates[-1]


def quantity(site: SitePackage, value: dict | float | None) -> float | None:
    if isinstance(value, dict):
        return value.get("value")
    return value


def site_lines(site: SitePackage) -> list[str]:
    """Footer lines that identify the package, frame, sphere and time range."""
    m = site.manifest
    s = m["site"]
    h_index = m["horizon"]["default_height_index"]
    height = m["horizon"]["observer_heights_m"][h_index]
    lines = [
        f"Package {site.package_id} · content SHA-256 {m['content_sha256'][:16]}… · "
        f"contract {m['contract']['version']} · status {m['status']}",
        f"Frame {s['frame']} · reference sphere radius {km(quantity(site, s['reference_radius_m']))} · "
        f"site {num(s['lat_deg'], 5)}°, {num(s['lon_deg'], 5)}° (planetocentric, east-positive) · "
        f"observer {num(height)} m above terrain",
    ]
    timeline = site.timeline
    if timeline:
        t = timeline["time"]
        lines.append(
            f"Time window {t['start_utc']} to {t['end_utc']} UTC "
            f"(series on a {t['scale']} grid, step {num(t['step_s'])} s, {t['count']} samples)"
        )
    else:
        lines.append("No time window in this package: the time views are hidden.")
    return lines


def banner_lines(sites: list[SitePackage], notice: str | None) -> list[str]:
    """Warning lines at the top of a chart: synthetic data, and the caller's notice
    (for example that the packages are provisional)."""
    lines = []
    if any(site.synthetic for site in sites):
        lines.append("SYNTHETIC SAMPLE DATA — invented values for interface testing, not a result")
    if notice:
        lines += textwrap.wrap(notice, 125)
    return lines


# ---------------------------------------------------------------- horizon panorama

def horizon_panorama(site: SitePackage, notice: str | None = None) -> str:
    m = site.manifest
    horizon = m["horizon"]
    h_index = horizon["default_height_index"]
    height = horizon["observer_heights_m"][h_index]
    count = horizon["azimuth"]["count"]
    step = horizon["azimuth"]["step_deg"]
    start = horizon["azimuth"]["start_deg"]
    profile = site.array(horizon["elevation_deg"]).row(h_index)

    tracks = {}
    timeline = site.timeline
    if timeline:
        for body in timeline["bodies"]:
            series = timeline["series"][body]
            tracks[body] = (site.array(series["azimuth_deg"]).values, site.array(series["elevation_deg"]).values)

    finite = [v for v in profile if math.isfinite(v)]
    for az, el in tracks.values():
        finite += [e for a, e in zip(az, el) if math.isfinite(a) and math.isfinite(e)]
    ymin, ymax = math.floor(min(finite)) - 1.0, math.ceil(max(finite)) + 1.0
    xmin, xmax = 0.0, 360.0

    banner = banner_lines([site], notice)
    top = 64 + 22 * len(banner)
    x0, x1, y0, y1 = 70.0, 1170.0, float(top), float(top + 290)

    def px(az: float) -> float:
        return x0 + (az - xmin) / (xmax - xmin) * (x1 - x0)

    def py(el: float) -> float:
        return y1 - (el - ymin) / (ymax - ymin) * (y1 - y0)

    body = [
        text(24, 30, f"Terrain horizon panorama — {m['site']['name']}", "title"),
        text(24, 50, "Elevation of the terrain horizon versus azimuth, with the paths of the Sun and Earth "
             "disc centres over the time window", "sub"),
    ]
    body += [text(24, 72 + 22 * i, line, "banner") for i, line in enumerate(banner)]
    body.append(
        f'<g id="plot" data-x0="{num(x0)}" data-x1="{num(x1)}" data-y0="{num(y0)}" data-y1="{num(y1)}" '
        f'data-xmin="{num(xmin)}" data-xmax="{num(xmax)}" data-ymin="{num(ymin)}" data-ymax="{num(ymax)}">'
    )
    ystep = nice_step(ymax - ymin, (0.5, 1, 2, 5, 10, 15, 30, 45, 90), 10)
    tick = math.ceil(ymin / ystep) * ystep
    while tick <= ymax + 1e-9:
        body.append(f'<line class="grid" x1="{num(x0)}" x2="{num(x1)}" y1="{num(py(tick))}" y2="{num(py(tick))}"/>')
        body.append(text(x0 - 8, py(tick) + 4, f"{num(tick)}°", "tick", "end"))
        tick += ystep
    compass = {0: "N", 90: "E", 180: "S", 270: "W", 360: "N"}
    for az in range(0, 361, 45):
        body.append(f'<line class="grid" x1="{num(px(az))}" x2="{num(px(az))}" y1="{num(y0)}" y2="{num(y1)}"/>')
        label = f"{compass[az]} {az}°" if az in compass else f"{az}°"
        body.append(text(px(az), y1 + 16, label, "tick", "middle"))

    points = [(px(start + i * step), py(profile[i % count])) for i in range(count + 1)]
    coords = " ".join(f"{num(x)},{num(y)}" for x, y in points)
    fill = f"{num(x0)},{num(y1)} {coords} {num(x1)},{num(y1)}"
    body.append(f'<polygon class="terrain" points="{fill}"/>')
    body.append(f'<polyline id="horizon" class="horizon" points="{coords}"/>')

    for name, (az, el) in tracks.items():
        commands, previous = [], None
        for a, e in zip(az, el):
            if not (math.isfinite(a) and math.isfinite(e)):
                previous = None
                continue
            a %= 360.0
            jump = previous is None or abs(a - previous) > 180.0
            commands.append(f"{'M' if jump else 'L'}{num(px(a))},{num(py(e))}")
            previous = a
        cls = name.lower()
        body.append(f'<path id="{cls}-track" class="track {cls}" d="{" ".join(commands)}"/>')
    body.append(f'<rect class="frame" x="{num(x0)}" y="{num(y0)}" width="{num(x1 - x0)}" height="{num(y1 - y0)}"/>')
    body.append("</g>")
    body.append(text(x0 + (x1 - x0) / 2, y1 + 34, "Azimuth (clockwise from north)", "tick", "middle"))
    body.append(
        f'<text x="18" y="{num((y0 + y1) / 2)}" class="tick" text-anchor="middle" '
        f'transform="rotate(-90 18 {num((y0 + y1) / 2)})">Elevation</text>'
    )

    legend_y = y1 + 56
    legend = [("horizon", f"Terrain horizon, observer {num(height)} m above terrain")]
    legend += [(name.lower(), f"{name.title()} disc centre (no terrain)") for name in tracks]
    x = x0
    for cls, label in legend:
        swatch = "horizon" if cls == "horizon" else f"track {cls}"
        body.append(f'<line class="{swatch}" x1="{num(x)}" x2="{num(x + 24)}" y1="{num(legend_y - 4)}" y2="{num(legend_y - 4)}"/>')
        body.append(text(x + 30, legend_y, label, "sub"))
        x += 30 + 7.2 * len(label) + 28

    foot_y = legend_y + 26
    lines = site_lines(site)
    statuses = [f"horizon.elevation [{site.method_status('horizon.elevation')}]"]
    if timeline:
        statuses.append(f"timeline.direction [{site.method_status('timeline.direction')}]")
    lines.append(
        "Validation status: " + ", ".join(statuses)
        + " · elevation above the local horizontal plane of the reference sphere"
    )
    body += [text(24, foot_y + 17 * i, line, "foot") for i, line in enumerate(lines)]
    height_px = int(foot_y + 17 * len(lines) + 12)
    return svg_document(height_px, body, f"Terrain horizon panorama, {m['site']['name']}, package {site.package_id}")


# ---------------------------------------------------------------- window strip

def window_strip(sites: list[SitePackage], notice: str | None = None) -> str:
    sites = [site for site in sites if site.timeline]
    if not sites:
        raise ValueError("no package has a time window; the window strip is hidden")
    grids = [site.timeline["time"] for site in sites]
    xmin = min(g["start_et_s"] for g in grids)
    xmax = max(g["start_et_s"] + (g["count"] - 1) * g["step_s"] for g in grids)

    banner = banner_lines(sites, notice)
    top = 64 + 22 * len(banner)
    x0, x1 = 300.0, 1170.0
    lane, gap, site_gap = 18.0, 6.0, 26.0

    def px(et: float) -> float:
        return x0 + (et - xmin) / (xmax - xmin) * (x1 - x0)

    rows = []
    y = float(top + 8)
    for site in sites:
        index = site.manifest["horizon"]["default_height_index"]
        windows = {w["id"]: w for w in site.timeline["windows"] if w["height_index"] == index}
        metrics = {m["id"]: m for m in site.timeline.get("metrics", []) if m.get("height_index") == index}
        y += 16
        rows.append(("site", y, site, None, None))
        y += 6
        for window_id, label, cls, metric_id in STRIP_ROWS:
            if window_id in windows:
                rows.append(("lane", y, site, (windows[window_id], label, cls), metrics.get(metric_id or "")))
                y += lane + gap
        y += site_gap - gap
    y0, y1 = float(top), y

    body = [
        text(24, 30, "Lighting and direct-to-Earth windows", "title"),
        text(24, 50, "Intervals in which the Sun and the Earth are above the terrain horizon, on one UTC axis", "sub"),
    ]
    body += [text(24, 72 + 22 * i, line, "banner") for i, line in enumerate(banner)]
    body.append(
        f'<g id="plot" data-x0="{num(x0)}" data-x1="{num(x1)}" data-y0="{num(y0)}" data-y1="{num(y1)}" '
        f'data-xmin="{num(xmin, 3)}" data-xmax="{num(xmax, 3)}" data-ymin="0" data-ymax="1">'
    )
    body += time_ticks(sites, xmin, xmax, px, y0, y1)
    for kind, row_y, site, window, metric in rows:
        if kind == "site":
            h_index = site.manifest["horizon"]["default_height_index"]
            height = site.manifest["horizon"]["observer_heights_m"][h_index]
            body.append(f'<rect class="bg" x="16" y="{num(row_y - 14)}" width="{num(x1 - 16)}" height="18"/>')
            body.append(text(24, row_y, f"{site.manifest['site']['name']} (observer {num(height)} m)", "row"))
            continue
        window, label, bar_class = window
        tooltip = escape(label)
        if metric and metric.get("unit") == "1" and metric.get("value") is not None:
            label += f" · {100 * metric['value']:.1f} % of window"
        body.append(text(36, row_y + lane - 5, label, "sub"))
        body.append(f'<rect class="lane" x="{num(x0)}" y="{num(row_y)}" width="{num(x1 - x0)}" height="{num(lane)}"/>')
        cls = "bar " + bar_class
        for (start, end), (start_utc, end_utc) in zip(window["intervals_et_s"], window["intervals_utc"]):
            body.append(
                f'<rect class="{cls}" data-window={quoteattr(window["id"])} data-site={quoteattr(site.manifest["site"]["site_id"])} '
                f'x="{num(px(start), 3)}" y="{num(row_y)}" width="{num(px(end) - px(start), 3)}" height="{num(lane)}">'
                f"<title>{tooltip}: {escape(start_utc)} to {escape(end_utc)}</title></rect>"
            )
            if px(end) - px(start) < MIN_VISIBLE_PX:
                # Too short to see at this scale: a marker line shows where it is; the bar
                # above keeps its exact width.
                mid = (px(start) + px(end)) / 2
                body.append(
                    f'<line class="mark {bar_class}" x1="{num(mid, 3)}" x2="{num(mid, 3)}" '
                    f'y1="{num(row_y)}" y2="{num(row_y + lane)}"><title>{tooltip}: {escape(start_utc)} to '
                    f"{escape(end_utc)}</title></line>"
                )
        if window.get("clipped_start"):
            body.append(text(x0 + 3, row_y + lane - 5, "◂", "tick"))
        if window.get("clipped_end"):
            body.append(text(x1 - 3, row_y + lane - 5, "▸", "tick", "end"))
    body.append("</g>")

    foot_y = y1 + 46
    lines = []
    for site in sites:
        lines += [f"{site.manifest['site']['name']}:"] + ["   " + line for line in site_lines(site)]
        lines.append(
            f"   Validation status: timeline.windows [{site.method_status('timeline.windows')}], "
            f"timeline.events [{site.method_status('timeline.events')}] · "
            "◂ ▸ the interval runs past the computed range"
        )
    body += [text(24, foot_y + 17 * i, line, "foot") for i, line in enumerate(lines)]
    height_px = int(foot_y + 17 * len(lines) + 12)
    ids = ", ".join(site.package_id for site in sites)
    return svg_document(height_px, body, f"Lighting and direct-to-Earth windows, packages {ids}")


def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc)


def time_ticks(sites, xmin, xmax, px, y0, y1) -> list[str]:
    """Date ticks at 00:00 UTC.

    The contract allows labelling a grid instant as start_utc + elapsed seconds only when the
    grid has no leap second (SPEC 3.5). Otherwise only the UTC strings of the package are used.
    """
    reference = min(sites, key=lambda s: s.timeline["time"]["start_et_s"]).timeline["time"]
    out = []
    if all(site.timeline["time"]["leap_seconds_in_range"] == 0 for site in sites):
        origin = parse_utc(reference["start_utc"])
        days = (xmax - xmin) / 86400.0
        step = int(nice_step(days, (1, 2, 5, 7, 14, 30, 61, 91, 183), 12))
        day = origin.replace(hour=0, minute=0, second=0, microsecond=0)
        if day < origin:
            day += dt.timedelta(days=1)
        ticks = []
        while True:
            et = reference["start_et_s"] + (day - origin).total_seconds()
            if et > xmax + 1e-6:
                break
            ticks.append((et, day.strftime("%Y-%m-%d")))
            day += dt.timedelta(days=step)
    else:
        ticks = [(reference["start_et_s"], reference["start_utc"][:10])]
        last = max(sites, key=lambda s: s.timeline["time"]["start_et_s"] + s.timeline["time"]["count"] * s.timeline["time"]["step_s"])
        g = last.timeline["time"]
        ticks.append((g["start_et_s"] + (g["count"] - 1) * g["step_s"], g["end_utc"][:10]))
    right_edge = px(xmax)
    for et, label in ticks:
        x = px(et)
        out.append(f'<line class="grid" x1="{num(x)}" x2="{num(x)}" y1="{num(y0)}" y2="{num(y1)}"/>')
        anchor = "end" if right_edge - x < 40 else "middle"
        out.append(text(x, y1 + 16, label, "tick-time", anchor))
    out.append(text((px(xmin) + px(xmax)) / 2, y1 + 32, "Date (UTC, ticks at 00:00)", "tick", "middle"))
    return out


# ---------------------------------------------------------------- command line

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Draw static SVG charts from site packages.")
    parser.add_argument("packages", nargs="+", help="site package directories and/or index.json files")
    parser.add_argument("--out", required=True, help="output folder")
    parser.add_argument("--notice", help="warning printed on every chart, e.g. that the packages are provisional")
    args = parser.parse_args(argv)
    sites = load_packages(args.packages)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for site in sites:
        name = f"horizon_panorama__{site.manifest['site']['site_id']}.svg"
        (out / name).write_text(horizon_panorama(site, args.notice), encoding="utf-8", newline="\n")
    if any(site.timeline for site in sites):
        (out / "window_strip.svg").write_text(window_strip(sites, args.notice), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
