"""Writes the two detail textures of the regolith, procedurally, from fixed seeds.

No photograph, scan or downloaded texture is used: every value comes from the random
numbers and the formulas below, so the files are the same on every run. They are
illustrative detail below the resolution of the elevation data (the kind of surface the
data cannot resolve), not measurements.

    T_LsnRegolithMacro  8 m square: bumps and small craters, about 0.15 to 1.6 m across.
    T_LsnRegolithMicro  1 m square: gravel and clods, about 0.5 to 5 cm, in fine dust.

Each is 2048 x 2048, tileable (every field is periodic over the square), RGBA, 8 bit:

    R, G  slope of the height field, dh/dx and dh/dy, as 0.5 + slope / (2 * SLOPE_RANGE)
    B     ambient occlusion of the height field (1 = open), from the horizon in 16 directions
    A     albedo variation, 0.5 = the mean grey of the ground

Run with the project's Python (numpy only), from the repository root:

    python unreal/Scripts/make_regolith_textures.py

The files go to unreal/Assets/regolith; make_materials.py imports them.
"""

import os
import struct
import zlib

import numpy as np

SIZE = 2048
# Slopes beyond these are clipped; the material uses the same numbers to decode.
SLOPE_RANGE = {"macro": 1.0, "micro": 1.5}
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Assets", "regolith"))


def spectral(rng, size, tile_m, shortest_m, longest_m, beta):
    """Periodic noise with power ~ k^-beta between two wavelengths; zero mean, unit rms."""
    white = rng.standard_normal((size, size))
    k = np.fft.fftfreq(size, d=tile_m / size)
    kx, ky = np.meshgrid(k, k)
    kr = np.hypot(kx, ky)
    band = (kr >= 1.0 / longest_m) & (kr <= 1.0 / shortest_m)
    filt = np.where(band, np.power(np.maximum(kr, 1e-9), -beta / 2.0), 0.0)
    field = np.real(np.fft.ifft2(np.fft.fft2(white) * filt))
    field -= field.mean()
    return (field / max(field.std(), 1e-12)).astype(np.float32)


def window(size, cx, cy, radius_px):
    """Indices of a square around a point, wrapped over the tile, and the offsets in pixels."""
    r = int(np.ceil(radius_px)) + 1
    off = np.arange(-r, r + 1)
    ix = (int(np.floor(cx)) + off) % size
    iy = (int(np.floor(cy)) + off) % size
    dx = (np.floor(cx) + off) - cx
    dy = (np.floor(cy) + off) - cy
    return np.ix_(iy, ix), dx[None, :], dy[:, None]


def power_law(rng, count, smallest, largest, exponent):
    """Sizes with N(>s) ~ s^-exponent: many small, few large."""
    u = rng.random(count)
    a, b = smallest ** -exponent, largest ** -exponent
    return (a - u * (a - b)) ** (-1.0 / exponent)


def slopes(height, tile_m):
    px = tile_m / height.shape[0]
    sx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / (2.0 * px)
    sy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / (2.0 * px)
    return sx, sy


def occlusion(height, tile_m, radii_px):
    """Share of the sky open above each point: 1 - mean over 16 directions of sin(horizon angle)."""
    px = tile_m / height.shape[0]
    total = np.zeros_like(height)
    directions = 16
    for i in range(directions):
        a = 2.0 * np.pi * (i + 0.5) / directions
        best = np.zeros_like(height)
        for r in radii_px:
            sx, sy = int(round(r * np.cos(a))), int(round(r * np.sin(a)))
            if sx == 0 and sy == 0:
                continue
            dist = np.hypot(sx, sy) * px
            rise = (np.roll(height, (-sy, -sx), axis=(0, 1)) - height) / dist
            np.maximum(best, rise, out=best)
        total += best / np.sqrt(1.0 + best * best)  # sin of the angle
    return np.clip(1.0 - total / directions, 0.0, 1.0)


def make_macro(rng):
    tile = 8.0
    n = SIZE
    px = tile / n
    # Gentle undulation and bumps from 0.2 to 4 m: a few centimetres high.
    h = 0.030 * spectral(rng, n, tile, 0.2, 4.0, 3.2) + 0.0012 * spectral(rng, n, tile, 0.04, 0.4, 2.6)
    albedo = 0.025 * spectral(rng, n, tile, 0.1, 4.0, 2.0)
    # Small craters, 0.15 to 1.6 m across, worn to different degrees; fresh ones a little brighter.
    for d in power_law(rng, 260, 0.15, 1.6, 1.8):
        cx, cy = rng.random() * n, rng.random() * n
        radius = 0.5 * d / px
        idx, dx, dy = window(n, cx, cy, 2.2 * radius)
        rho = np.hypot(dx, dy) / radius
        fresh = rng.random() ** 2
        depth = (0.03 + 0.12 * fresh) * d
        rim = 0.25 * depth
        bowl = depth * (rho ** 2 - 1.0) + rim
        outside = rim * np.exp(-((rho - 1.0) / 0.35) ** 2)
        shape = np.where(rho < 1.0, bowl, outside)
        blend = np.clip(1.0 - (rho - 1.6) / 0.6, 0.0, 1.0)  # nothing beyond 2.2 radii
        h[idx] += (shape * blend).astype(np.float32)
        albedo[idx] += (0.06 * fresh * np.clip(1.25 - rho, 0.0, 1.0)).astype(np.float32)
    return h, albedo, tile, [2, 4, 8, 16, 32, 64, 128]


def make_micro(rng):
    tile = 1.0
    n = SIZE
    px = tile / n
    # Fine dust: a few millimetres of relief from 2 mm to 20 cm.
    h = 0.0025 * spectral(rng, n, tile, 0.02, 0.2, 3.0) + 0.00012 * spectral(rng, n, tile, 0.002, 0.03, 2.4)
    albedo = 0.02 * spectral(rng, n, tile, 0.005, 0.2, 1.6)
    # Gravel and clods, 0.5 to 5 cm, half buried, each with its own grey.
    for d in power_law(rng, 2600, 0.005, 0.05, 2.0):
        cx, cy = rng.random() * n, rng.random() * n
        radius = 0.5 * d / px
        stretch = 1.0 + 0.6 * rng.random()
        turn = rng.random() * np.pi
        idx, dx, dy = window(n, cx, cy, radius * stretch)
        u = (dx * np.cos(turn) + dy * np.sin(turn)) / stretch
        v = -dx * np.sin(turn) + dy * np.cos(turn)
        rho2 = (u * u + v * v) / (radius * radius)
        top = 0.5 * d * (0.35 + 0.4 * rng.random())
        stone = np.where(rho2 < 1.0, top * np.sqrt(np.clip(1.0 - rho2, 0.0, 1.0)) - 0.15 * d, -1.0)
        base = h[idx]
        h[idx] = np.maximum(base, base.mean() + stone).astype(np.float32)
        shade = 0.10 * (rng.random() - 0.4)
        albedo[idx] += (np.where(rho2 < 1.0, shade, 0.0)).astype(np.float32)
    return h, albedo, tile, [1, 2, 4, 8, 16, 32, 64]


def png(path, rgba):
    height, width, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def write(name, kind, h, albedo, tile, radii):
    sx, sy = slopes(h, tile)
    ao = occlusion(h, tile, radii)
    span = SLOPE_RANGE[kind]
    channels = [
        0.5 + np.clip(sx, -span, span) / (2.0 * span),
        0.5 + np.clip(sy, -span, span) / (2.0 * span),
        ao,
        np.clip(0.5 + albedo, 0.0, 1.0),
    ]
    rgba = np.stack([np.round(np.clip(c, 0.0, 1.0) * 255.0).astype(np.uint8) for c in channels], axis=-1)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}.png")
    png(path, rgba)
    print(f"{path}: rms slope {np.sqrt((sx ** 2 + sy ** 2).mean()):.3f}, clipped {np.mean((np.abs(sx) > span) | (np.abs(sy) > span)) * 100:.2f} %, "
          f"ao mean {ao.mean():.3f} min {ao.min():.3f}, albedo rms {albedo.std():.3f}")


if __name__ == "__main__":
    write("T_LsnRegolithMacro", "macro", *make_macro(np.random.default_rng(20261115)))
    write("T_LsnRegolithMicro", "micro", *make_micro(np.random.default_rng(1115)))
