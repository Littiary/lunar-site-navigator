"""Mast-height trade: what a higher observer gains.

The horizon is computed for several observer heights in one pass and the event finder
runs for each, so the trade is a table read off the windows: total visible time and
longest outage per height, and the change against the lowest height.
"""

from __future__ import annotations

from . import packaging as pk
from .results import TimelineResult

_ROWS = (
    ("sun_visible_s", "Time with the Sun visible", "sun_visible", False),
    ("sun_longest_outage_s", "Longest continuous time without the Sun", "sun_visible", True),
    ("sun_lit_s", "Time with the Sun visible and not totally eclipsed by the Earth", "sun_lit", False),
    ("earth_visible_s", "Time with the Earth visible", "earth_visible", False),
    ("earth_longest_outage_s", "Longest continuous time without the Earth", "earth_visible", True),
    ("sun_and_earth_visible_s", "Time with the Sun and the Earth visible together", "sun_and_earth_visible", False),
)


def height_trade(observer_heights_m, windows: dict) -> dict:
    """Trade table from windows given per observer height: {window id: [IntervalSet per height]}.

    For each window: the total time it holds and the longest stretch it does not, per
    height, and the change of each against the first (lowest) height.
    """
    quantities = []
    for qid, label, window_id, outage in _ROWS:
        sets = windows.get(window_id)
        if sets is None:
            continue
        values = [float(s.complement().longest_s() if outage else s.total_s()) for s in sets]
        quantities.append(
            {
                "id": qid,
                "label": label,
                "unit": "s",
                "window": window_id,
                "values": values,
                "change_s": [v - values[0] for v in values],
                "method": pk.M_HEIGHT_TRADE,
            }
        )
    return {
        "observer_heights_m": [float(h) for h in observer_heights_m],
        "quantities": quantities,
        "method": pk.M_HEIGHT_TRADE,
    }


def add_height_trade_to_timeline(timeline: TimelineResult, observer_heights_m) -> None:
    """Add the trade table of a site to its timeline."""
    windows = {}
    for _, _, window_id, _ in _ROWS:
        try:
            windows[window_id] = [timeline.window(window_id, h) for h in range(len(observer_heights_m))]
        except KeyError:
            continue
    table = height_trade(observer_heights_m, windows)
    if timeline.calendar is not None:
        complete = [p["index"] for p in timeline.calendar["periods"] if p["complete"]]
        for quantity in timeline.calendar["quantities"]:
            if quantity["id"] == "sun_visible_s" and complete:
                values = [float(min(row[i] for i in complete)) for row in quantity["values"]]
                table["quantities"].append(
                    {
                        "id": "sun_least_lunar_day_s",
                        "label": "Sun-visible time in the least sunlit complete lunar day",
                        "unit": "s",
                        "window": "sun_visible",
                        "values": values,
                        "change_s": [v - values[0] for v in values],
                        "method": pk.M_HEIGHT_TRADE,
                    }
                )
    timeline.height_trade = table
