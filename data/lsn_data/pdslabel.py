"""Minimal PDS3 label reader.

PDS3 labels are ``KEY = value`` text. Values can be quoted strings that span
lines, ``{...}`` sets, numbers with a ``<unit>`` suffix, or bare words. Nested
``OBJECT`` blocks are flattened: a key keeps its last value, and the object
nesting is ignored. That is enough for the LOLA GDR labels, whose keys are
unique inside one label. Comments (``/* ... */``) are dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_UNIT = re.compile(r"^(?P<num>[-+]?[0-9.eE+-]+)\s*<(?P<unit>[^>]+)>$")


def _scalar(text: str):
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        return " ".join(text[1:-1].split())
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    m = _UNIT.match(text)
    if m:
        return float(m.group("num"))
    # Bare number, with an optional trailing '.' as in "1737400."
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        return float(text)
    except ValueError:
        return text


def parse_label_text(text: str) -> dict:
    """Parse PDS3 label text into a flat dict."""
    text = _COMMENT.sub("", text)
    out: dict = {}
    key = None
    buf: list[str] = []
    depth_quote = False
    depth_brace = 0

    def flush():
        nonlocal key, buf
        if key is None:
            return
        raw = " ".join(s.strip() for s in buf).strip()
        if raw.startswith("{"):
            inner = raw.strip("{} ")
            items = re.findall(r'"[^"]*"|[^,\s]+', inner)
            out[key] = [_scalar(i) for i in items]
        else:
            out[key] = _scalar(raw)
        key, buf = None, []

    for line in text.splitlines():
        if key is not None and (depth_quote or depth_brace > 0):
            buf.append(line)
            depth_quote ^= line.count('"') % 2 == 1
            depth_brace += line.count("{") - line.count("}")
            if not depth_quote and depth_brace <= 0:
                flush()
            continue
        stripped = line.strip()
        if not stripped or stripped == "END":
            continue
        if "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k in ("OBJECT", "END_OBJECT"):
            continue
        key = k
        buf = [v]
        depth_quote = v.count('"') % 2 == 1
        depth_brace = v.count("{") - v.count("}")
        if not depth_quote and depth_brace <= 0:
            flush()
    flush()
    return out


def parse_label(path: str | Path) -> dict:
    """Parse a PDS3 ``.lbl`` file."""
    return parse_label_text(Path(path).read_text(encoding="ascii", errors="replace"))
