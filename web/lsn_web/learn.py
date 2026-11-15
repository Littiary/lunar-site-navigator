"""Static education page: four short explanations with one example each from a published package.

One self-contained HTML file per language. The explanations are text (``learn_text.json``,
one entry per language with the same keys); the examples are sentences with placeholders
that are filled with values read from one site package and only formatted here. If a package
lacks a field an example needs, that example is left out and the page says so.

Adding a language is adding one entry to ``learn_text.json``; ``tests/test_learn.py`` checks
that every language has the keys and placeholders of the English entry.

Usage (from ``web/``)::

    python -m lsn_web.learn <site package dir | index.json> [...] [--lang en] --out learn.html
"""

from __future__ import annotations

import argparse
import json
import string
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python web/lsn_web/learn.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web import charts, evidence
    from lsn_web.package import SitePackage, load_packages
else:
    from . import charts, evidence
    from .package import SitePackage, load_packages

TEXT_FILE = Path(__file__).resolve().parent / "learn_text.json"
DEFAULT_LANGUAGE = "en"
e = evidence.e

EXTRA_CSS = """
.example { border-left: 4px solid var(--accent); padding: 6px 14px; margin: 14px 0; background: var(--surface); }
.example .label { font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.example p { margin: 4px 0; }
blockquote { margin: 8px 0; padding: 0 0 0 12px; border-left: 2px solid var(--line); color: var(--muted); }
"""


def load_text() -> dict:
    return json.loads(TEXT_FILE.read_text(encoding="utf-8"))


def languages() -> list[str]:
    return list(load_text())


def page_name(lang: str) -> str:
    return "learn.html" if lang == DEFAULT_LANGUAGE else f"learn.{lang}.html"


def fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def pick_example(sites: list[SitePackage]) -> SitePackage | None:
    """The site whose examples say most: among the sites that have obstacles, an uncertainty band and
    landing opportunities, the one whose costliest Sun obstacle at the default height costs most.
    The project's own sites are preferred. A comparison of stored values; nothing is computed."""
    best, best_cost = None, -1.0
    full = [s for s in sites if (s.timeline or {}).get("blockers") and s.timeline.get("uncertainty") and s.timeline.get("opportunities")]
    own = [s for s in full if s.manifest["site"].get("category") == "project site"]  # the project's own sites first
    for s in own or full:
        t = s.timeline
        index = s.manifest["horizon"]["default_height_index"]
        cost = max((b["lost_s"] for b in t["blockers"] if b.get("height_index") == index and b.get("body") == "SUN"), default=-1.0)
        if cost > best_cost:
            best, best_cost = s, cost
    return best or next((s for s in sites if s.timeline), None)


def example_values(site: SitePackage, text: dict) -> dict[str, str]:
    """Every placeholder the examples may use, as formatted text. A value that the package does not
    hold is simply absent, and the example that needs it is not shown."""
    m, t = site.manifest, site.timeline or {}
    horizon = m["horizon"]
    index = horizon["default_height_index"]
    heights = horizon["observer_heights_m"]
    low = min(range(len(heights)), key=lambda i: heights[i])
    time = t.get("time", {})
    v = {
        "site_name": m["site"]["name"],
        "package_id": site.package_id,
        "start_utc": time.get("start_utc"),
        "end_utc": time.get("end_utc"),
        "heights": ", ".join(charts.num(h) for h in heights),
        "default_height": charts.num(heights[index]),
        "low_height": charts.num(heights[low]),
        "max_range_km": charts.num(charts.quantity(site, horizon["max_range_m"]) / 1000, 0),
    }
    blocker = next((b for b in t.get("blockers", []) if b.get("height_index") == index and b.get("body") == "SUN"), None)
    if blocker and blocker.get("peak_distance_m") is not None:
        v["blocker_distance_m"] = charts.num(blocker["peak_distance_m"], 0)
        v["blocker_lost_h"] = charts.num(blocker["lost_s"] / 3600, 0)
        v["blocker_share_pct"] = charts.num(100 * blocker["share_of_lost"], 0)

    def metric(metric_id: str, height_index: int) -> str | None:
        found = next((x for x in t.get("metrics", []) if x.get("id") == metric_id and x.get("height_index") == height_index), None)
        return None if found is None or found.get("value") is None else f"{100 * found['value']:.1f}"

    v["sun_share_low_pct"] = metric("sun_visible_fraction_of_time", low)
    v["sun_share_default_pct"] = metric("sun_visible_fraction_of_time", index)
    v["earth_share_default_pct"] = metric("earth_visible_fraction_of_time", index)
    event = next((x for x in t.get("events", []) if x.get("height_index") == index and x.get("body") == "SUN"), None)
    if event:
        v["event_type"] = event["type"]
        v["event_utc"] = event["utc"]
        v["event_earliest_utc"] = event.get("earliest_utc")
        v["event_latest_utc"] = event.get("latest_utc")
        v["event_distance"] = charts.km(event["obstacle_distance_m"]) if event.get("obstacle_distance_m") is not None else None
    requirements = (m.get("request", {}).get("timeline") or {}).get("requirements") or []
    opportunity = next((o for o in t.get("opportunities") or [] if o.get("height_index") == index
                        and requirements and o.get("requirement_id") == requirements[0].get("id")), None)
    if opportunity:
        v["requirement_label"] = requirements[0].get("label")
        v["window_count"] = str(opportunity.get("window_count"))
        v["feasible_pct"] = f"{100 * opportunity['feasible_fraction']:.1f}"
        v["longest_window_h"] = charts.num(opportunity["longest_window_s"] / 3600, 0)
        planned = opportunity.get("planned_landing") or {}
        if planned.get("utc"):
            v["planned_utc"] = planned["utc"]
            if planned.get("feasible"):
                v["planned_verdict"] = text["planned_feasible"].format(slip_h=charts.num((planned.get("slip_tolerance_s") or 0) / 3600, 0))
            elif planned.get("wait_s") is not None:
                v["planned_verdict"] = text["planned_not_feasible"].format(wait_h=charts.num(planned["wait_s"] / 3600, 0))
            else:
                v["planned_verdict"] = text["planned_no_window"]
    return {k: str(x) for k, x in v.items() if x is not None}


def build_page(sites: list[SitePackage], lang: str = DEFAULT_LANGUAGE, site_links: bool = False,
               example_site_id: str | None = None) -> str:
    texts = load_text()
    text = texts[lang]
    site = next((s for s in sites if s.manifest["site"]["site_id"] == example_site_id), None) or pick_example(sites)
    values = example_values(site, text) if site else {}
    assumption = (((site.timeline or {}).get("uncertainty") or {}).get("horizon_error") or {}).get("assumption") if site else None
    banner = ""
    if site and site.synthetic:
        banner = '<div class="banner">SYNTHETIC SAMPLE DATA — the example values on this page are invented interface-test values, not results.</div>'
    nav = [(f"#{section['id']}", section["heading"]) for section in text["sections"]]
    if site_links:
        nav += [("compare.html", text["nav_compare"]), ("evidence.html", text["nav_evidence"]), ("accuracy.html", text["nav_accuracy"])]
    parts = [
        "<!doctype html>",
        f'<html lang="{e(lang)}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{e(text['title'])}</title>",
        f"<style>{evidence.CSS.strip()}{EXTRA_CSS.rstrip()}</style>",
        "</head>",
        "<body><main>",
        "<header>",
        f"<h1>{e(text['heading'])}</h1>",
        f"<p>{e(text['lead'])}</p>",
        "<nav>" + "".join(f'<a href="{e(href)}">{e(label)}</a>' for href, label in nav) + "</nav>",
        banner,
        "</header>",
    ]
    others = [code for code in texts if code != lang]
    if others and site_links:
        parts.append(f'<p class="muted">{e(text["other_languages"])} '
                     + " · ".join(f'<a href="{e(page_name(code))}" lang="{e(code)}">{e(texts[code]["language_name"])}</a>' for code in others) + "</p>")
    for section in text["sections"]:
        parts.append(f'<h2 id="{e(section["id"])}">{e(section["heading"])}</h2>')
        parts += [f"<p>{e(paragraph)}</p>" for paragraph in section["paragraphs"]]
        if fields(section["example"]) <= set(values):
            body = f"<p>{e(section['example'].format(**values))}</p>"
            if section["id"] == "uncertainty" and assumption:
                body += f'<p class="muted">{e(text["quoted_from_package"])}</p><blockquote lang="en">{e(assumption)}</blockquote>'
            if section["id"] == "opportunities" and values.get("requirement_label"):
                body += f'<p class="muted">{e(text["quoted_from_package"])}</p><blockquote lang="en">{e(values["requirement_label"])}</blockquote>'
            parts.append(f'<div class="example" data-example="{e(section["id"])}"><div class="label">{e(text["example_label"])}</div>{body}</div>')
        else:
            parts.append(f'<p class="muted" data-no-example="{e(section["id"])}">{e(text["no_example"])}</p>')
    if fields(text["example_source"]) <= set(values):
        parts.append(f'<p class="muted">{e(text["example_source"].format(**values))}</p>')
    parts += [f"<footer><p>{e(text['footer'])}</p></footer>", "</main></body>", "</html>"]
    return "\n".join(part for part in parts if part) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the static education page.")
    parser.add_argument("packages", nargs="+", help="site package directories and/or index.json files")
    parser.add_argument("--lang", default=DEFAULT_LANGUAGE, choices=languages())
    parser.add_argument("--out", required=True, help="output HTML file")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(load_packages(args.packages), args.lang), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
