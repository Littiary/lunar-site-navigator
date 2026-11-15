"""Static "Accuracy and limits" page: what has been checked, against what, and what has not.

One self-contained HTML file. It loads nothing from the network, so it opens offline, in a
private window and on a phone. Every number is read from a stored record and only formatted
here:

* the validation card (``validation/card/validation_card.json``): checks, thresholds,
  measured values, what is not validated, limits;
* the real-mission cases and their stored results (``validation/landers``,
  ``validation/eclipse``);
* the terrain acceptance reports of the data stream (``data/checkpoints``);
* the published packages: terrain source and resolution class of every site, the
  uncertainty band where a package has one, the status of every method.

A record that is missing in a build is named as missing; nothing is put in its place.

Usage (from ``web/``)::

    python -m lsn_web.accuracy <site package dir | index.json> [...] [--card validation_card.json] [--notice TEXT] --out accuracy.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python web/lsn_web/accuracy.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lsn_web import charts, evidence
    from lsn_web.package import SitePackage, load_packages
else:
    from . import charts, evidence
    from .package import SitePackage, load_packages

REPO = Path(__file__).resolve().parent.parent.parent
BLOB = evidence.REPOSITORY + "/blob/main/"

# Groups of the validation card (field "group" of each check). A check in EXTERNAL_GROUPS was
# compared with a source outside the project; one in ANALYTIC_GROUPS with a closed form, with
# the project's own second computation, or with another routine on the same inputs.
EXTERNAL_GROUPS = ("Independent source", "Independent computation on terrain", "Dated image", "Published mission record")
ANALYTIC_GROUPS = ("Closed form", "Internal consistency", "Independent implementation")

e = evidence.e
table = evidence.table
badge = evidence.status_badge
sig = evidence.sig

EXTRA_CSS = """
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0; }
.card { border: 1px solid var(--line); border-radius: 6px; padding: 10px 14px; background: var(--surface); }
.card strong { display: block; font-size: 1.5rem; }
.card.bad { border-color: var(--warn); }
.card.bad strong { color: var(--warn); }
.note { border-left: 4px solid var(--accent); padding: 2px 12px; margin: 12px 0; background: var(--surface); }
.note.bad { border-left-color: var(--warn); }
"""

MISSING = '<p class="muted">{what} is not part of this build, so nothing is shown here.</p>'


def link(path: str, label: str | None = None) -> str:
    """A link to a file of the repository on GitHub (the page itself needs no network)."""
    return f'<a href="{e(BLOB + path)}"><code>{e(label or path)}</code></a>'


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def kind_of(check: dict) -> str:
    group = check.get("group")
    return "external" if group in EXTERNAL_GROUPS else "analytic" if group in ANALYTIC_GROUPS else "other"


def shown(value) -> str:
    """A stored value as text: numbers to six significant digits, everything else as it is."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return sig(value, 6)
    if isinstance(value, dict):
        return "; ".join(f"{e(k)}: {shown(v)}" for k, v in value.items())
    return e(value)


# ---------------------------------------------------------------- validation card

def card_sections(card: dict | None) -> str:
    if card is None:
        return ('<h2 id="checks">Validation checks</h2>'
                '<p class="muted">No validation card was given to this build, so no check is listed.</p>')
    summary = card["summary"]
    checks = card["checks"]
    kinds = {"external": [], "analytic": [], "other": []}
    for check in checks:
        kinds[kind_of(check)].append(check)

    def count(group: list[dict]) -> str:
        failed = sum(1 for c in group if c.get("status") != "PASS")
        return f"{len(group) - failed} of {len(group)} pass" + (f", {failed} fail" if failed else "")

    source = card.get("generated_from", {})
    out = [
        '<h2 id="checks">Validation checks</h2>',
        f"<p><strong>{summary['passed']} of {summary['checks']} checks pass</strong>"
        + (f", <strong>{summary['failed']} fail</strong>" if summary.get("failed") else "")
        + ". A check counts as passed only against a threshold that was written down before the comparison was run; "
        "a failed check stays on this page as it is.</p>",
        f'<p class="muted">Read from {link("validation/card/validation_card.json")}, generated {e(card.get("generated_utc"))} '
        f'from commit <span class="mono">{e(source.get("commit"))}</span>. The same card as a table with the place where each '
        f'threshold was fixed: {link("validation/card/validation_card.md")}.</p>',
        '<div class="cards">'
        f'<div class="card"><strong>{len(kinds["external"])}</strong>checks against a source outside the project: {count(kinds["external"])}</div>'
        f'<div class="card"><strong>{len(kinds["analytic"])}</strong>analytical and internal tests: {count(kinds["analytic"])}</div>'
        + (f'<div class="card"><strong>{len(kinds["other"])}</strong>checks of a kind this page does not know: {count(kinds["other"])}</div>'
           if kinds["other"] else "")
        + f'<div class="card{" bad" if summary.get("failed") else ""}"><strong>{summary.get("failed", 0)}</strong>failed</div>'
        "</div>",
    ]

    failed = [c for c in checks if c.get("status") != "PASS"]
    out.append('<h3 id="failed">Checks that failed</h3>')
    if failed:
        for check in failed:
            limits = check.get("limits") or ([check["limit"]] if check.get("limit") else [])
            out.append(
                f'<div class="note bad"><p><strong>{e(check["quantity"])}</strong> {badge(check["status"])}</p>'
                f"<p>Against: {e(check.get('compared_against'))}. Cases: {e(check.get('cases'))}.<br>"
                f"Required {threshold(check)}; measured {measured(check)}.</p>"
                + ("<ul>" + "".join(f"<li>{e(x)}</li>" for x in limits) + "</ul>" if limits else "")
                + "</div>")
    else:
        out.append('<p class="muted">No check of this card failed.</p>')

    def block(title: str, ident: str, intro: str, group: list[dict], kind: str) -> None:
        out.append(f'<h3 id="{ident}">{title}</h3><p>{intro}</p>')
        if not group:
            out.append('<p class="muted">No check of this kind is on the card.</p>')
            return
        rows = [[e(c.get("group")), e(c["quantity"]), e(c.get("compared_against")), e(c.get("cases")), threshold(c),
                 measured(c), badge(c.get("status", "unknown")),
                 e(c.get("limit") or "; ".join(c.get("limits") or []))] for c in group]
        attrs = [{"data-check": c["id"], "data-kind": kind, "data-status": c.get("status", "unknown")} for c in group]
        out.append(table(["Kind", "What was compared", "Against", "Cases", "Threshold", "Measured", "Result", "Main limit of the check"],
                         rows, numeric={4, 5}, row_attrs=attrs))

    block("Compared with a source outside the project", "external",
          "The reference was produced by someone else: JPL Horizons, published LOLA illumination maps, LROC images, "
          "published mission records. Agreement here is evidence about the result itself, within the limit stated in the last column.",
          kinds["external"], "external")
    block("Analytical and internal tests", "analytic",
          "The reference is a closed-form answer, the project's own second computation, or another routine fed with the same "
          "kernels. These tests show that the code does what it is meant to do on given inputs. They say nothing about "
          "whether the inputs (the terrain model, the ephemeris) match the Moon.",
          kinds["analytic"], "analytic")
    if kinds["other"]:
        block("Checks of a kind this page does not know", "other-checks",
              "The card names a group for these checks that this page cannot sort into the two kinds above. "
              "They are shown with the group as the card states it.", kinds["other"], "other")

    if card.get("not_validated"):
        out.append('<h2 id="not-validated">Not validated</h2><ul>' + "".join(
            f"<li><strong>{e(item['item'])}</strong> {badge(item.get('state', 'unknown'))}<br>{e(item.get('reason'))}</li>"
            for item in card["not_validated"]) + "</ul>")
    if card.get("limits"):
        out.append('<h3 id="card-limits">Limits of the validation as a whole</h3><ul>'
                   + "".join(f"<li>{e(x)}</li>" for x in card["limits"]) + "</ul>")
    return "\n".join(out)


def threshold(check: dict) -> str:
    t = check.get("threshold") or {}
    return f"{e(t.get('comparison', ''))} {sig(t.get('value'), 4)} {e(t.get('unit', ''))}".strip()


def measured(check: dict) -> str:
    mv = check.get("measured") or {}
    return f"{sig(mv.get('value'), 3)} {e(mv.get('unit', ''))}".strip()


# ---------------------------------------------------------------- real missions

def published_rows(case_id: str, items: list[dict], sources: dict) -> tuple[list[list[str]], list[dict]]:
    rows, attrs = [], []
    for item in items:
        names = [name.strip() for name in str(item.get("source", "")).split(",") if name.strip()]
        links = "<br>".join(
            f'<a href="{e(sources[name]["url"])}">{e(sources[name]["title"])}</a>'
            f' <span class="muted">(read {e(sources[name].get("retrieved_utc"))})</span>' if name in sources else e(name)
            for name in names)
        rows.append([f"<code>{e(item['id'])}</code>", e(item.get("as_printed")), e(item.get("precision")),
                     "<strong>yes</strong>" if item.get("approximate") else "no", e(item.get("nature")), links or "—"])
        attrs.append({"data-published": f"{case_id}.{item['id']}", "data-approximate": "yes" if item.get("approximate") else "no"})
    return rows, attrs


def result_rows(rows_in: list[dict]) -> tuple[list[list[str]], list[dict]]:
    rows, attrs = [], []
    for row in rows_in:
        status = row.get("status")
        rows.append([e(row.get("quantity")), shown(row.get("published")), shown(row.get("computed")),
                     shown(row.get("difference")), shown(row.get("threshold")), e(row.get("unit")),
                     badge(status) if status else '<span class="muted">reported, not judged</span>', e(row.get("note"))])
        attrs.append({"data-result": row["id"], "data-status": status or "reported"})
    return rows, attrs


PUBLISHED_HEAD = ["Published value", "As printed by the source", "Printed precision", "Approximate", "What it is", "Source"]
RESULT_HEAD = ["Quantity", "Published", "Computed", "Difference", "Threshold", "Unit", "Result", "Note"]


def missions_section(repo: Path) -> str:
    out = ['<h2 id="missions">Real missions: published values and how the core compares</h2>',
           "<p>For each case the published values are shown as the source prints them, with the printed precision and whether "
           "the source itself calls the value approximate. Values and thresholds were committed before the core was run on "
           "the case. The comparisons are not blind: earlier research had compared some of these values with JPL Horizons, "
           "so each threshold follows a fixed rule from the printed precision of its source.</p>"]
    landers = repo / "validation" / "landers"
    results = read_json(landers / "results" / "validation_table.json")
    by_case = {case["id"]: case for case in (results or {}).get("cases", [])}
    found = False
    for name in ("cases.json", "cases_second_batch.json"):
        document = read_json(landers / name)
        if document is None:
            continue
        found = True
        for case in document["cases"]:
            stored = by_case.get(case["id"])
            judged = [r for r in (stored or {}).get("rows", []) if r.get("kind") == "pass_fail"]
            passed = sum(1 for r in judged if r.get("status") == "PASS")
            verdict = (f"{passed} of {len(judged)} judged checks pass; {len((stored or {}).get('rows', [])) - len(judged)} "
                       "values reported without a verdict" if stored else "no stored result")
            rows, attrs = published_rows(case["id"], case["published"], document["sources"])
            body = [f"<p>Terrain used: {e(case.get('terrain'))}</p>", table(PUBLISHED_HEAD, rows, row_attrs=attrs)]
            if stored:
                rrows, rattrs = result_rows(stored["rows"])
                body.append(table(RESULT_HEAD, rrows, numeric={1, 2, 3, 4}, row_attrs=rattrs))
            out.append(f"<details><summary>{e(case['mission'])} — {e(verdict)}</summary>{''.join(body)}</details>")
    if not found:
        out.append(MISSING.format(what="The record of the lander cases (<code>validation/landers</code>)"))
    else:
        if results:
            s = results["summary"]
            out.append(f"<p>All lander cases together: {s['passed']} of {s['pass_fail_checks']} judged checks pass, {s['failed']} fail, "
                       f"{s['reported_without_verdict']} values are reported without a verdict. Stored result: "
                       f'{link("validation/landers/results/validation_table.md")}; cases: {link("validation/landers/cases.json")}, '
                       f'{link("validation/landers/cases_second_batch.json")}; rules: {link("validation/landers/thresholds.json")}.</p>')
        out.append('<div class="note"><p>What these cases can and cannot show: the six Apollo landings test the direction of the Sun and '
                   "the Earth at a published time and place; the published angles were themselves computed from an almanac and involve no "
                   "terrain. The records of Blue Ghost Mission 1 and Chandrayaan-3 bound a computed sunrise or sunset from one side only. "
                   "No source that was examined prints a sunrise or sunset clock time for a landing site, so no event time on real terrain "
                   "is confirmed by a mission record.</p></div>")

    eclipse = read_json(repo / "validation" / "eclipse" / "cases.json")
    eclipse_results = read_json(repo / "validation" / "eclipse" / "results" / "validation_table.json")
    if eclipse is None:
        out.append(MISSING.format(what="The record of the eclipse case (<code>validation/eclipse</code>)"))
    else:
        rows, attrs = published_rows("eclipse", eclipse["published"], eclipse["sources"])
        body = [f"<p>{e(eclipse.get('description'))}</p>",
                f"<p>Site: {e(eclipse['site'].get('name'))}, {e(eclipse['site'].get('as_printed'))}. {e(eclipse['site'].get('note'))}</p>",
                table(PUBLISHED_HEAD, rows, row_attrs=attrs)]
        verdict = "no stored result"
        if eclipse_results:
            s = eclipse_results["summary"]
            verdict = (f"{s['passed']} of {s['pass_fail_checks']} judged checks pass; {s['reported_without_verdict']} values "
                       "reported without a verdict")
            rrows, rattrs = result_rows(eclipse_results["rows"])
            body.append(f"<p>Model: {e(eclipse_results.get('core', {}).get('model'))}.</p>")
            body.append(table(RESULT_HEAD, rrows, numeric={3, 4}, row_attrs=rattrs))
        body.append(f'<p>Cases: {link("validation/eclipse/cases.json")}; stored result: {link("validation/eclipse/results/validation_table.md")}.</p>')
        out.append(f"<details><summary>Eclipse of the Sun by the Earth, 14 March 2025, at the Blue Ghost landing point — {e(verdict)}</summary>"
                   + "".join(body) + "</details>")
    return "\n".join(out)


# ---------------------------------------------------------------- terrain

def terrain_section(sites: list[SitePackage], repo: Path) -> str:
    out = ['<h2 id="terrain">Terrain: resolution, near field and what was checked</h2>',
           "<p>Near the lunar poles the terrain horizon, not the ephemeris, sets the accuracy of a rise or set time. "
           "The table shows, for every published site, which elevation product lies under the site, its pixel size, and "
           "the class the package gives it. The package states the classes as: "
           f"{e(next((s.manifest['horizon'].get('terrain_source', {}).get('classes') for s in sites if s.manifest['horizon'].get('terrain_source')), 'not stated in these packages'))}.</p>"]
    rows, attrs = [], []
    for s in sites:
        m = s.manifest
        source = m["horizon"].get("terrain_source") or {}
        at_site = source.get("at_site") or {}
        band = bool((s.timeline or {}).get("uncertainty"))
        products = ", ".join(f"{p.get('product_id')} ({charts.num(p.get('pixel_m') or 0)} m, {100 * (p.get('azimuth_share') or 0):.0f} % of azimuths)"
                             for p in source.get("products") or [])
        rows.append([e(m["site"]["name"]), e(m["site"].get("programme") or "—"),
                     f"{e(at_site.get('product_id') or 'not stated')}", f"{charts.num(at_site['pixel_m'])} m" if at_site.get("pixel_m") else "—",
                     e(source.get("resolution_class") or "not stated"),
                     e(products) or "—", "yes" if band else "<strong>no</strong>",
                     "<br>".join(e(w) for w in m.get("warnings", [])) or "—"])
        attrs.append({"data-site": m["site"]["site_id"], "data-class": source.get("resolution_class") or "",
                      "data-band": "yes" if band else "no"})
    out.append(table(["Site", "Programme", "Product under the site", "Pixel", "Class", "Products that set the horizon",
                      "Uncertainty band on event times", "Package warning"], rows, numeric={3}, row_attrs=attrs))
    out.append('<div class="note"><p><strong>Reading the table.</strong> A site without an uncertainty band is not a more certain '
               "site: its package has no band because no height error has been measured for the elevation product it uses. "
               "Relief narrower than about two pixels is not in the horizon at all, so on a medium or coarse product a nearby "
               "boulder field, crater rim or hill of that size cannot be shown.</p></div>")

    out.append('<h3 id="near-field">Near field: terrain closer than 1 km</h3>'
               "<p>When the terrain that hides the Sun or the Earth is closer than about 1 km, the result depends on single pixels of "
               "the elevation model and on the exact position and height of the observer: moving a few metres changes it. "
               "The packages mark such obstacles. The rows below are the obstacles marked <code>near_field</code> in "
               "<code>timeline.blockers</code> at the default observer height, one per site and body: the one with the largest stored time lost.</p>")
    rows = []
    for s in sites:
        index = s.manifest["horizon"]["default_height_index"]
        height = s.manifest["horizon"]["observer_heights_m"][index]
        seen = set()
        for b in (s.timeline or {}).get("blockers", []):
            if b.get("height_index") != index or not b.get("near_field") or b["body"] in seen:
                continue
            seen.add(b["body"])  # blockers are stored largest cost first
            rows.append([e(s.manifest["site"]["name"]), f"{charts.num(height)} m", e(b["body"].title()),
                         f"{b['lost_s'] / 3600:.1f} h", f"{100 * b['share_of_lost']:.1f} %",
                         e(charts.km(b["peak_distance_m"])) if b.get("peak_distance_m") is not None else "—",
                         f"{charts.num(b['peak_azimuth_deg'], 2)}°"])
    if rows:
        out.append(table(["Site", "Observer height", "Body hidden", "Time lost over the window", "Share of the time lost to terrain",
                          "Distance of the obstacle", "Azimuth"], rows, numeric={3, 4, 5, 6}))
    else:
        out.append('<p class="muted">No package of this build marks a near-field obstacle at its default observer height.</p>')

    out.append(terrain_checks(repo))
    return "\n".join(out)


def terrain_checks(repo: Path) -> str:
    checkpoints = repo / "data" / "checkpoints"
    out = ['<h3 id="terrain-checks">Acceptance checks of the elevation data</h3>',
           "<p>These reports belong to the data stream. Their thresholds were committed before the first measurement. "
           f'The flags below are shown as stored; causes and follow-up checks are in {link("data/README.md")}, '
           f'{link("data/notes/known_limits.md")} and {link("data/checkpoints", "data/checkpoints/")}.</p>']
    report = read_json(checkpoints / "report.json")
    if report is None:
        out.append(MISSING.format(what="The checkpoint report of the south-polar products (<code>data/checkpoints/report.json</code>)"))
    else:
        rows = []
        for key, label in (("checkpoint_1_checksums", "Files match their published checksums"),
                           ("checkpoint_2_georeferencing", "Georeferencing: IAU crater outlines against the rim crests in the data"),
                           ("checkpoint_3_values_and_reference_radius", "Height values and reference radius")):
            part = report.get(key) or {}
            detail = ""
            craters = part.get("craters")
            if isinstance(craters, dict):
                good = sum(1 for c in craters.values() if c.get("passed"))
                detail = f"{good} of {len(craters)} craters meet the rule"
            rows.append([e(label), badge("PASS" if part.get("passed") else "FAIL"), e(detail) or "—"])
        out.append("<p><strong>South-polar products</strong> " + f'({link("data/checkpoints/report.json")}, generated {e(report.get("generated_utc"))}; '
                   f'all passed: {shown(report.get("all_passed"))}).</p>' + table(["Checkpoint", "Stored flag", "Detail"], rows))
        if not (report.get("checkpoint_2_georeferencing") or {}).get("passed", True):
            out.append('<div class="note bad"><p>The crater-outline checkpoint fails as written and is kept. The data stream then ran two '
                       f'further georeferencing checks with their own criteria ({link("data/checkpoints/supplementary_report.json")}, '
                       f'{link("data/checkpoints/catalogue_report.json")}) and a comparison with laser returns '
                       f'({link("data/checkpoints/independent_report.json")}); their results and open points are described in {link("data/README.md")}.</p></div>')

    llr = read_json(checkpoints / "llr_report.json")
    if llr is None:
        out.append(MISSING.format(what="The retroreflector report (<code>data/checkpoints/llr_report.json</code>)"))
    else:
        rows, attrs = [], []
        for product, record in llr["results"].items():
            if not isinstance(record, dict) or "reflectors" not in record or product.endswith("_reported_only"):
                continue
            for r in record["reflectors"]:
                rows.append([e(product), f"{charts.num(record.get('pixel_m') or 0, 0)} m", e(r["name"]),
                             f"{r['difference_m']:+.2f} m", f"{r['tolerance_m']:.2f} m", badge("PASS" if r.get("passed") else "FAIL")])
                attrs.append({"data-reflector": f"{product}.{r['name']}"})
        out.append("<p><strong>Height against the lunar laser retroreflectors</strong> (Apollo 11, 14, 15, Lunokhod 1, 2). "
                   "This is the one height check that does not depend on LOLA: the reflector radii come from lunar laser ranging. "
                   f'Stored result: {link("data/checkpoints/llr_report.json")} (passed: {shown(llr.get("passed"))}), criterion '
                   f'{link("data/checkpoints/thresholds_llr.json")}.</p>'
                   + table(["Product", "Pixel", "Reflector", "Model minus reflector", "Tolerance", "Result"], rows,
                           numeric={1, 3, 4}, row_attrs=attrs))

    near = read_json(checkpoints / "near_field_report.json")
    limits = read_json(checkpoints / "thresholds_near_field.json") or {}
    if near is None:
        out.append(MISSING.format(what="The near-field report (<code>data/checkpoints/near_field_report.json</code>)"))
    else:
        rule = (limits.get("seam") or {}).get("pass_if") or {}
        rows, attrs = [], []
        for product, record in near["sites"].items():
            seam, stats = record.get("seam") or {}, record.get("stats") or {}
            rows.append([e(product), f"{stats.get('median_abs_d_m', float('nan')):.2f} m", f"{stats.get('p95_abs_d_m', float('nan')):.2f} m",
                         badge("PASS" if record.get("passed") else "FAIL"),
                         f"{seam.get('median_abs_jump_m', float('nan')):.2f} m", f"{seam.get('p95_abs_jump_m', float('nan')):.2f} m",
                         badge("PASS" if seam.get("passed") else "FAIL")])
            attrs.append({"data-seam": product, "data-passed": "yes" if seam.get("passed") else "no"})
        out.append("<p><strong>5 m site models against the 20 m polar product</strong> at the three project sites, and the jump at the "
                   "edge where the terrain switches from 5 m to 20 m"
                   + (f" (rule: median jump at most {shown(rule.get('median_abs_jump_m'))} m and 95 % of jumps at most {shown(rule.get('p95_abs_jump_m'))} m)" if rule else "")
                   + f'. Stored result: {link("data/checkpoints/near_field_report.json")}, generated {e(near.get("generated_utc"))}; '
                   f'all passed: {shown(near.get("all_passed"))}.</p>'
                   + table(["5 m product", "Median height difference to 20 m", "95 % of differences within", "Comparison",
                            "Median jump at the edge", "95 % of jumps within", "Edge"], rows, numeric={1, 2, 4, 5}, row_attrs=attrs))
        out.append(f'<p class="muted">{e(near.get("what_this_can_and_cannot_show"))}</p>')
        if not near.get("all_passed", True):
            out.append('<div class="note bad"><p>At least one edge check fails as written. The correction note of the data stream gives the '
                       f'cause and the measured effect on the horizon: {link("data/notes/near_field_seam_correction.md")}.</p></div>')
    return "\n".join(out)


# ---------------------------------------------------------------- event times and assumptions

def event_times_section(sites: list[SitePackage]) -> str:
    out = ['<h2 id="event-times">Event times are approximate</h2>',
           "<p>A rise or set time in a package is the instant at which the computed margin between the body and the computed "
           "terrain horizon crosses zero. The arithmetic resolves that instant to a fraction of a second, but the terrain does not: "
           "<strong>no rise or set time on real terrain has been compared with an independent source</strong>, and near the poles "
           "a horizon error of 0.01° can move an event by many minutes. Treat event times as estimates with the band below "
           "where a package has one, and as estimates without a stated error where it has none.</p>"]
    banded = [s for s in sites if (s.timeline or {}).get("uncertainty")]
    if not banded:
        out.append('<p class="muted">No package of this build carries an uncertainty band.</p>')
        return "\n".join(out)
    first = banded[0].timeline["uncertainty"].get("horizon_error") or {}
    model = first.get("dem_height_error_model") or {}
    out.append(f"<p><strong>What the band is.</strong> {e(first.get('assumption'))}</p>")
    out.append(f'<p class="muted">Height error model <code>{e(model.get("id"))}</code>: {e(model.get("source"))}</p>')
    rows = []
    for s in banded:
        h = (s.timeline["uncertainty"].get("horizon_error") or {})
        height, angle, pixels = h.get("applied_height_error_m") or {}, h.get("applied_error_deg") or {}, h.get("limiting_pixels") or {}
        rows.append([e(s.manifest["site"]["name"]),
                     f"{shown(height.get('min'))} / {shown(height.get('median'))} / {shown(height.get('max'))} m",
                     f"{shown(angle.get('min'))} / {shown(angle.get('median'))} / {shown(angle.get('max'))}°",
                     f"{100 * pixels.get('constrained', 0):.0f} % / {100 * pixels.get('interpolated', 0):.0f} %"])
    out.append(table(["Site", "Height error applied (smallest / median / largest)", "As an angle at the horizon (smallest / median / largest)",
                      "Horizon pixels with laser returns / interpolated"], rows))
    out.append("<p>Examples as stored: the first Sun events of each of these sites at its default observer height, with the earliest "
               "and latest time of the band.</p>")
    rows = []
    for s in banded:
        index = s.manifest["horizon"]["default_height_index"]
        events = [ev for ev in s.timeline.get("events", [])
                  if ev.get("height_index") == index and ev.get("body") == "SUN" and ev.get("earliest_utc")][:2]
        for ev in events:
            quality = ev.get("terrain_quality") or {}
            rows.append([e(s.manifest["site"]["name"]), e(ev["type"]), f'<span class="mono">{e(ev.get("earliest_utc"))}</span>',
                         f'<span class="mono">{e(ev["utc"])}</span>', f'<span class="mono">{e(ev.get("latest_utc"))}</span>',
                         e(charts.km(ev["obstacle_distance_m"])) if ev.get("obstacle_distance_m") is not None else "—",
                         e(f"{quality.get('product_id', '')}, {quality.get('limiting_pixel', '')}".strip(", ")) or "—"])
    if rows:
        out.append(table(["Site", "Event", "Earliest (UTC)", "Computed (UTC)", "Latest (UTC)", "Distance of the limiting terrain",
                          "Terrain at that point"], rows, numeric={5}))
    out.append('<div class="note"><p>The band covers the stated height error of the terrain point that sets the horizon. It does not cover '
               "errors common to all LOLA products, the position of the lander, the observer height, or the ephemeris.</p></div>")
    return "\n".join(out)


def methods_section(sites: list[SitePackage]) -> str:
    methods: dict[str, dict] = {}
    for s in sites:
        for method_id, card in s.manifest.get("methods", {}).items():
            record = methods.setdefault(method_id, {"title": card.get("title"), "statuses": set(), "sites": 0, "limits": card.get("limits") or []})
            record["statuses"].add((card.get("validation") or {}).get("status", "unknown"))
            record["sites"] += 1
    counts: dict[str, int] = {}
    for record in methods.values():
        for status in record["statuses"]:
            counts[status] = counts.get(status, 0) + 1
    out = ['<h2 id="methods">Status of each method in the packages</h2>',
           "<p>Every number in a package names the method that produced it, and every method carries one status. "
           + "; ".join(f"{badge(status)} {n} method(s)" for status, n in sorted(counts.items()))
           + ". A method marked <em>analytic-test-passed</em> has been tested against known answers, not against the Moon.</p>"]
    rows = [[f"<code>{e(method_id)}</code>", e(record["title"]), " ".join(badge(x) for x in sorted(record["statuses"])),
             str(record["sites"]), "<br>".join(e(x) for x in record["limits"]) or "—"]
            for method_id, record in sorted(methods.items())]
    out.append(table(["Method", "What it produces", "Status", "Packages", "Limits stated in the package"], rows, numeric={3}))
    out.append("<p>The evidence of each method (tests, thresholds, measured values) is on the evidence page under "
               '"Methods behind the numbers".</p>')
    return "\n".join(out)


def assumptions_section(sites: list[SitePackage], card: dict | None) -> str:
    core = (card or {}).get("core", {})
    reference = next((s for s in sites if s.timeline), sites[0])
    m = reference.manifest
    t = (reference.timeline or {}).get("time", {})
    items = [
        f"The Moon is described in the frame <code>{e(m['site'].get('frame'))}</code> on a reference sphere of "
        f"{e(charts.km(charts.quantity(reference, m['site']['reference_radius_m'])))}; heights are above that sphere.",
        "The Sun and the Earth are uniform discs. \"Visible\" means that any part of the disc is above the terrain horizon; "
        "limb darkening and the flattening of the Earth are not modelled.",
        f"The terrain horizon is searched out to {e(charts.km(charts.quantity(reference, m['horizon']['max_range_m'])))} in every direction, "
        f"for observer heights of {', '.join(charts.num(h) for h in m['horizon']['observer_heights_m'])} m above the terrain.",
        "The observer is one point. A real lander has a footprint, a tilt and solar panels at several heights.",
        "The Earth is opaque and has no atmosphere in the eclipse computation; light refracted into the shadow is not modelled.",
        "Direct-to-Earth windows are geometry only: one elevation limit per ground station, no link budget, multipath or scheduling.",
        "The landing requirement offered in the views is an example chosen by the team, not a mission requirement.",
        "The sites are the project's own points or published landing coordinates. They are not official landing sites of a future mission.",
    ]
    if t:
        items.insert(2, f"The published window runs from {e(t.get('start_utc'))} to {e(t.get('end_utc'))} UTC on a grid of "
                        f"{charts.num(t.get('step_s'))} s; event times are found between the grid points. Outside the window nothing is published.")
    if core:
        items.insert(1, f"Directions come from SPICE with aberration correction <code>{e(core.get('aberration_correction'))}</code> "
                        f"(light time and stellar aberration), kernel set <code>{e(core.get('kernel_set_id'))}</code>.")
    return '<h2 id="assumptions">Assumptions behind every number</h2><ul>' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def sources_section(site_links: bool) -> str:
    rows = [
        ("Validation card (table, thresholds, limits)", link("validation/card/validation_card.md")),
        ("Stored comparison results", link("validation", "validation/") + " (folders <code>horizons</code>, <code>horizons_rts</code>, <code>pgda</code>, "
                                      "<code>lro_images</code>, <code>stations</code>, <code>landers</code>, <code>eclipse</code>, each with <code>results/</code>)"),
        ("Real-mission cases", link("validation/landers/cases.json") + ", " + link("validation/landers/cases_second_batch.json") + ", " + link("validation/eclipse/cases.json")),
        ("Terrain acceptance reports and known limits", link("data/checkpoints", "data/checkpoints/") + ", " + link("data/notes/known_limits.md")),
        ("Method notes (horizon, near field, uncertainty, obstacles, calendar)", link("docs/method", "docs/method/")),
        ("Package format and metadata", link("docs/contract/SPEC.md") + ", " + link("packages/README.md")),
        ("Comparison with LROC QuickMap and NASA Moon Trek", link("web/docs/tool_comparison/README.md")),
        ("Data, libraries, licences, use of AI tools", link("CREDITS.md")),
    ]
    if site_links:
        rows.insert(0, ("Every site: charts, events, windows, method cards, data versions", '<a href="evidence.html">Evidence page</a>'))
    return ('<h2 id="sources">Source records</h2>'
            + table(["Record", "Where"], [[e(a), b] for a, b in rows])
            + '<p class="muted">The links to the repository need a network connection; this page itself does not.</p>')


def in_short(card: dict | None) -> str:
    """The summary box. Each sentence about a result is written only if the card holds that check, with its stored value."""
    by_id = {c["id"]: c for c in (card or {}).get("checks", [])}
    sentences = []
    direction = by_id.get("direction_exact")
    if direction and direction.get("status") == "PASS":
        sentences.append(f"The directions of the Sun and the Earth differ from JPL Horizons by at most {measured(direction)} "
                         f"(required {threshold(direction)}).")
    shares = by_id.get("terrain_sun_share_difference")
    if shares and shares.get("status") == "PASS":
        sentences.append("The long-term share of sunlit time agrees with the published LOLA illumination maps on terrain of the same "
                         f"resolution (median difference {measured(shares)}).")
    failed = [c for c in by_id.values() if c.get("status") != "PASS"]
    if failed:
        sentences.append(f"{len(failed)} check{'s' if len(failed) != 1 else ''} failed and {'are' if len(failed) != 1 else 'is'} shown below.")
    sentences.append("Individual rise and set times on real terrain have no independent reference: they are estimates whose accuracy "
                     "is set by the elevation model, most of all where the limiting terrain is closer than about 1 km.")
    return '<div class="note"><p><strong>In short.</strong> ' + " ".join(sentences) + "</p></div>"


# ---------------------------------------------------------------- page

def build_page(sites: list[SitePackage], card_path: str | Path | None = None, notice: str | None = None,
               repo: str | Path = REPO, site_links: bool = False) -> str:
    """The page. ``repo`` is the repository root the result files are read from. ``site_links`` adds links
    to the other pages of the public site (as written by ``lsn_web.site``)."""
    repo = Path(repo)
    card = json.loads(Path(card_path).read_text(encoding="utf-8")) if card_path else None
    nav = [("#checks", "Validation checks"), ("#failed", "Failed checks"), ("#not-validated", "Not validated"),
           ("#missions", "Real missions"), ("#terrain", "Terrain"), ("#event-times", "Event times"),
           ("#methods", "Method status"), ("#assumptions", "Assumptions"), ("#sources", "Source records")]
    if site_links:
        nav += [("compare.html", "Compare two sites"), ("evidence.html", "Evidence page")]
    banner = ""
    if any(s.synthetic for s in sites):
        banner = ('<div class="banner">SYNTHETIC SAMPLE DATA — the packages of this build hold invented interface-test values, '
                  "not results.</div>")
    if notice:
        banner += f'<div class="banner">{e(notice)}</div>'
    count = len(sites)
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        "<title>Lunar Site Navigator: accuracy and limits</title>",
        f"<style>{evidence.CSS.strip()}{EXTRA_CSS.rstrip()}</style>",
        "</head>",
        "<body><main>",
        "<header>",
        "<h1>Lunar Site Navigator — accuracy and limits</h1>",
        "<p>This page says how far the numbers of Lunar Site Navigator can be trusted: what was checked and against what, "
        "what failed, what has not been checked at all, and which assumptions sit under every result. "
        "It is written for a reader who has to decide whether to rely on a number.</p>",
        f'<p class="muted">Built from {count} site package{"s" if count != 1 else ""} and the stored validation results of the repository. '
        "Numbers are read from those records and are not recomputed here. The page needs no network connection and no login.</p>",
        "<nav>" + "".join(f'<a href="{e(href)}">{e(label)}</a>' for href, label in nav) + "</nav>",
        banner,
        "</header>",
        in_short(card),
        card_sections(card),
        missions_section(repo),
        terrain_section(sites, repo),
        event_times_section(sites),
        methods_section(sites),
        assumptions_section(sites, card),
        sources_section(site_links),
        f'<footer><p>Team Kestro Aerospace, NASA Space Apps Challenge 2026. Source code and data provenance: '
        f'<a href="{evidence.REPOSITORY}">{evidence.REPOSITORY}</a>.</p></footer>',
        "</main></body>",
        "</html>",
    ]
    return "\n".join(part for part in parts if part) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description='Build the static "Accuracy and limits" page.')
    parser.add_argument("packages", nargs="+", help="site package directories and/or index.json files")
    parser.add_argument("--card", help="validation_card.json (optional)")
    parser.add_argument("--notice", help="warning shown at the top of the page")
    parser.add_argument("--repo", default=str(REPO), help="repository root the stored results are read from")
    parser.add_argument("--out", required=True, help="output HTML file")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(load_packages(args.packages), args.card, args.notice, args.repo), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
