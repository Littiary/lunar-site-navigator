"""The reusable time objects of the core: a uniform time grid and an interval set.

Every window in the project (Sun visible, Earth visible, both, a mission phase, the union
of two sites) is an :class:`IntervalSet`. The operations are defined here once so that
all features share the same arithmetic and report the same numbers.

Times are TDB seconds past J2000 (the SPICE "ET" axis).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class TimeGrid:
    """Uniform time axis: sample i is at start_et_s + i * step_s."""

    start_et_s: float
    step_s: float
    count: int

    def __post_init__(self) -> None:
        if not self.step_s > 0 or self.count < 1:
            raise ValueError("TimeGrid needs step_s > 0 and count >= 1")

    @property
    def end_et_s(self) -> float:
        return self.start_et_s + (self.count - 1) * self.step_s

    def times(self) -> np.ndarray:
        return self.start_et_s + np.arange(self.count, dtype=np.float64) * self.step_s

    def to_contract(self, start_utc: str, end_utc: str, leap_seconds_in_range: int = 0) -> dict:
        return {
            "scale": "TDB",
            "epoch": "J2000",
            "start_et_s": float(self.start_et_s),
            "step_s": float(self.step_s),
            "count": int(self.count),
            "start_utc": start_utc,
            "end_utc": end_utc,
            "leap_seconds_in_range": int(leap_seconds_in_range),
        }

    @classmethod
    def from_contract(cls, obj: dict) -> "TimeGrid":
        return cls(float(obj["start_et_s"]), float(obj["step_s"]), int(obj["count"]))


class IntervalSet:
    """A finite set of disjoint time intervals inside a domain [t0, t1].

    Intervals are stored sorted and merged; touching or overlapping inputs become one
    interval, empty inputs are dropped, and everything is clipped to the domain. The
    measure of a set does not depend on whether end points are included, so intervals
    are treated as closed.
    """

    __slots__ = ("domain", "_iv")

    def __init__(self, intervals: Iterable[Sequence[float]], domain: Sequence[float]):
        t0, t1 = float(domain[0]), float(domain[1])
        if not t0 < t1:
            raise ValueError("domain must satisfy t0 < t1")
        self.domain = (t0, t1)
        clipped = []
        for a, b in intervals:
            a, b = max(float(a), t0), min(float(b), t1)
            if a < b:
                clipped.append((a, b))
        clipped.sort()
        merged: list[tuple[float, float]] = []
        for a, b in clipped:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        self._iv = tuple(merged)

    # -- construction -------------------------------------------------------------

    @classmethod
    def empty(cls, domain: Sequence[float]) -> "IntervalSet":
        return cls((), domain)

    @classmethod
    def full(cls, domain: Sequence[float]) -> "IntervalSet":
        return cls((tuple(domain),), domain)

    @classmethod
    def from_samples(cls, grid: TimeGrid, values: np.ndarray, threshold: float = 0.0) -> "IntervalSet":
        """Times at which a sampled quantity exceeds a threshold.

        Crossing times are located by linear interpolation between neighbouring samples.
        NaN samples count as "condition not met". This is the baseline used for sampled
        series; an event finder that refines roots builds the set from its own times.
        """
        v = np.asarray(values, dtype=np.float64) - threshold
        if v.shape != (grid.count,):
            raise ValueError("values must have one entry per grid sample")
        if grid.count < 2:
            raise ValueError("at least two samples are needed to form intervals")
        t = grid.times()
        above = v > 0  # NaN compares False
        intervals = []
        start = t[0] if above[0] else None
        for i in range(grid.count - 1):
            if above[i] == above[i + 1]:
                continue
            a, b = v[i], v[i + 1]
            if np.isnan(a) or np.isnan(b):
                cross = t[i + 1] if above[i + 1] else t[i]
            else:
                cross = t[i] + (t[i + 1] - t[i]) * (a / (a - b))
            if above[i + 1]:
                start = cross
            else:
                intervals.append((start, cross))
                start = None
        if start is not None:
            intervals.append((start, t[-1]))
        return cls(intervals, (t[0], t[-1]))

    # -- queries ------------------------------------------------------------------

    @property
    def intervals(self) -> tuple[tuple[float, float], ...]:
        return self._iv

    def as_list(self) -> list[list[float]]:
        return [[a, b] for a, b in self._iv]

    def __len__(self) -> int:
        return len(self._iv)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, IntervalSet) and self.domain == other.domain and self._iv == other._iv

    def __repr__(self) -> str:
        return f"IntervalSet({list(self._iv)}, domain={self.domain})"

    def total_s(self) -> float:
        return float(sum(b - a for a, b in self._iv))

    def longest_s(self) -> float:
        return float(max((b - a for a, b in self._iv), default=0.0))

    def fraction(self) -> float:
        return self.total_s() / (self.domain[1] - self.domain[0])

    def contains(self, t: float) -> bool:
        return any(a <= t <= b for a, b in self._iv)

    @property
    def clipped_start(self) -> bool:
        """True if the first interval begins at the domain start (its true start is unknown)."""
        return bool(self._iv) and self._iv[0][0] == self.domain[0]

    @property
    def clipped_end(self) -> bool:
        return bool(self._iv) and self._iv[-1][1] == self.domain[1]

    # -- algebra ------------------------------------------------------------------

    def _same_domain(self, other: "IntervalSet") -> None:
        if self.domain != other.domain:
            raise ValueError("interval sets must share the same domain")

    def union(self, other: "IntervalSet") -> "IntervalSet":
        self._same_domain(other)
        return IntervalSet(self._iv + other._iv, self.domain)

    def intersection(self, other: "IntervalSet") -> "IntervalSet":
        self._same_domain(other)
        out = []
        i = j = 0
        while i < len(self._iv) and j < len(other._iv):
            a = max(self._iv[i][0], other._iv[j][0])
            b = min(self._iv[i][1], other._iv[j][1])
            if a < b:
                out.append((a, b))
            if self._iv[i][1] < other._iv[j][1]:
                i += 1
            else:
                j += 1
        return IntervalSet(out, self.domain)

    def complement(self) -> "IntervalSet":
        out = []
        position = self.domain[0]
        for a, b in self._iv:
            if a > position:
                out.append((position, a))
            position = b
        if position < self.domain[1]:
            out.append((position, self.domain[1]))
        return IntervalSet(out, self.domain)

    def close_gaps(self, max_gap_s: float) -> "IntervalSet":
        """Fill every gap between two intervals that is no longer than max_gap_s."""
        if not self._iv:
            return self
        out = [self._iv[0]]
        for a, b in self._iv[1:]:
            if a - out[-1][1] <= max_gap_s:
                out[-1] = (out[-1][0], b)
            else:
                out.append((a, b))
        return IntervalSet(out, self.domain)

    def drop_short(self, min_duration_s: float) -> "IntervalSet":
        """Remove every interval shorter than min_duration_s."""
        return IntervalSet([(a, b) for a, b in self._iv if b - a >= min_duration_s], self.domain)
