"""Minimal reader for uncompressed, strip- or tile-free single-band GeoTIFFs (standard library + NumPy only).

Enough for the 5 m/pixel LOLA site DEMs of Barker et al. (2021) (PGDA product 78): classic little-endian TIFF,
one IFD, no compression, float32 or integer samples in strips. Georeferencing from ModelPixelScale (33550) and
ModelTiepoint (33922). The products state (README) that their X/Y follow the GMT pixel-registered convention, the
tie point being the corner of the upper-left pixel in GeoTIFF's default PixelIsArea raster space; the raster type
key (GTRasterTypeGeoKey 1025) is read and reported so this can be checked per file.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1), 8: ("h", 2),
          9: ("i", 4), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8)}


@dataclass
class TiffInfo:
    width: int
    height: int
    bits: int
    sample_format: int          # 1 uint, 2 int, 3 float
    compression: int
    strip_offsets: list[int]
    strip_byte_counts: list[int]
    rows_per_strip: int
    pixel_scale: tuple[float, float]
    tiepoint: tuple[float, ...]  # (i, j, k, x, y, z)
    geokeys: dict[int, object]
    nodata: str | None

    @property
    def dtype(self) -> str:
        kind = {1: "u", 2: "i", 3: "f"}[self.sample_format]
        return f"<{kind}{self.bits // 8}"

    @property
    def raster_type(self) -> str:
        v = self.geokeys.get(1025, 1)
        return {1: "PixelIsArea", 2: "PixelIsPoint"}.get(v, str(v))

    @property
    def contiguous(self) -> bool:
        """True if the strips follow each other without gaps (then the image is one block of bytes)."""
        off, cnt = self.strip_offsets, self.strip_byte_counts
        return all(off[i] + cnt[i] == off[i + 1] for i in range(len(off) - 1))


def parse_header(buf: bytes) -> TiffInfo:
    """Parse the first IFD from the leading bytes of a TIFF (the IFD and its arrays must lie inside ``buf``)."""
    if buf[:4] != b"II*\x00":
        raise ValueError("not a little-endian classic TIFF")
    (ifd,) = struct.unpack_from("<I", buf, 4)
    (n,) = struct.unpack_from("<H", buf, ifd)
    tags: dict[int, object] = {}
    for k in range(n):
        tag, typ, count, val = struct.unpack_from("<HHI4s", buf, ifd + 2 + 12 * k)
        fmt, size = _TYPES[typ]
        total = size * count
        raw = val if total <= 4 else buf[struct.unpack("<I", val)[0] : struct.unpack("<I", val)[0] + total]
        if len(raw) < total and total > 4:
            raise ValueError(f"tag {tag} lies outside the bytes read")
        if typ == 2:
            tags[tag] = raw[:count].rstrip(b"\x00").decode("ascii", "replace")
        else:
            vals = struct.unpack("<" + fmt * count, raw[:total])
            tags[tag] = vals
    gk: dict[int, object] = {}
    if 34735 in tags:
        g = tags[34735]
        for i in range(int(g[3])):
            key, loc, cnt, off = g[4 + 4 * i : 8 + 4 * i]
            gk[key] = off if loc == 0 else (loc, cnt, off)
    return TiffInfo(
        width=int(tags[256][0]),
        height=int(tags[257][0]),
        bits=int(tags[258][0]),
        sample_format=int(tags.get(339, (1,))[0]),
        compression=int(tags.get(259, (1,))[0]),
        strip_offsets=[int(v) for v in tags[273]],
        strip_byte_counts=[int(v) for v in tags[279]],
        rows_per_strip=int(tags.get(278, (tags[257][0],))[0]),
        pixel_scale=(float(tags[33550][0]), float(tags[33550][1])),
        tiepoint=tuple(float(v) for v in tags[33922][:6]),
        geokeys=gk,
        nodata=tags.get(42113),
    )


def read_header(path: str | Path, nbytes: int = 1 << 20) -> TiffInfo:
    with open(path, "rb") as f:
        return parse_header(f.read(nbytes))


def open_array(path: str | Path, info: TiffInfo | None = None) -> np.ndarray:
    """The image as a read-only memory map (uncompressed, contiguous strips only)."""
    info = info or read_header(path)
    if info.compression != 1:
        raise ValueError(f"compressed TIFF (compression {info.compression}) is not supported")
    if not info.contiguous:
        raise ValueError("strips are not contiguous")
    return np.memmap(path, dtype=info.dtype, mode="r", offset=info.strip_offsets[0], shape=(info.height, info.width))


def write_test_tiff(path: str | Path, arr: np.ndarray, x_ul: float, y_ul: float, pixel: float) -> None:
    """Write a small uncompressed float32 GeoTIFF (for tests; PixelIsArea, tie point at the upper-left corner)."""
    arr = np.ascontiguousarray(arr, dtype="<f4")
    h, w = arr.shape
    entries = []
    extra = b""
    data_off = 8

    def add(tag, typ, count, payload: bytes):
        nonlocal extra
        if len(payload) <= 4:
            entries.append((tag, typ, count, payload.ljust(4, b"\x00"), None))
        else:
            entries.append((tag, typ, count, None, payload))

    image = arr.tobytes()
    add(256, 4, 1, struct.pack("<I", w))
    add(257, 4, 1, struct.pack("<I", h))
    add(258, 3, 1, struct.pack("<H", 32))
    add(259, 3, 1, struct.pack("<H", 1))
    add(262, 3, 1, struct.pack("<H", 1))
    add(273, 4, 1, struct.pack("<I", data_off))
    add(277, 3, 1, struct.pack("<H", 1))
    add(278, 4, 1, struct.pack("<I", h))
    add(279, 4, 1, struct.pack("<I", len(image)))
    add(339, 3, 1, struct.pack("<H", 3))
    add(33550, 12, 3, struct.pack("<3d", pixel, pixel, 0.0))
    add(33922, 12, 6, struct.pack("<6d", 0.0, 0.0, 0.0, x_ul, y_ul, 0.0))
    add(34735, 3, 8, struct.pack("<8H", 1, 1, 0, 1, 1025, 0, 1, 1))
    ifd_off = data_off + len(image)
    ifd_size = 2 + 12 * len(entries) + 4
    ext_off = ifd_off + ifd_size
    body = b""
    ifd = struct.pack("<H", len(entries))
    for tag, typ, count, inline, payload in sorted(entries, key=lambda e: e[0]):
        if payload is None:
            ifd += struct.pack("<HHI4s", tag, typ, count, inline)
        else:
            ifd += struct.pack("<HHII", tag, typ, count, ext_off + len(body))
            body += payload
    ifd += struct.pack("<I", 0)
    with open(path, "wb") as f:
        f.write(b"II*\x00" + struct.pack("<I", ifd_off) + image + ifd + body)
