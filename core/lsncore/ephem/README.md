# Ephemeris and time

This folder answers one question for the science core: **seen from a point on the Moon, where are the Sun and the Earth in the local sky at a given time, and how large do they appear?** It contains no terrain. The terrain horizon comes from the core stream; the event finder combines the two.

## Layout

| Path | Content |
|---|---|
| `core/lsncore/ephem/kernels.py`, `fetch_kernels.py` | Kernel set definition, download, checksum check, loading |
| `core/lsncore/ephem/kernel_manifest.json` | What was downloaded: file, URL, size, SHA-256, retrieval time (written by the script) |
| `core/lsncore/ephem/directions.py` | Time conversion, site, site-independent direction table and its interpolation, azimuth / elevation / angular radius |
| `core/lsncore/events/finder.py` | Disc signals against a horizon profile, rise and set events, windows, countdown |
| `core/lsncore/events/eclipse.py` | Eclipses of the Sun by the Earth at a site; eclipse-aware power line |
| `core/lsncore/ephem/stations.py`, `core/lsncore/events/links.py` | Ground-station geometry (optional kernel group), direct-to-Earth windows, relay need |
| `core/lsncore/ephem/table.py`, `core/lsncore/events/timeline.py` | Direction-table package and per-site timeline in contract form |
| `core/tests/ephem/`, `core/tests/events/` | Acceptance tests |
| `validation/horizons/` | Comparison against JPL Horizons: thresholds, queries, raw responses, results |

Set-up from a fresh clone, in the repository root (the one setup path of the repository, described in [`docs/setup.md`](../../../docs/setup.md)):

```
python scripts/bootstrap.py --no-terrain
.venv/Scripts/python -m pytest core validation
```

That creates the environment, installs `core[test,validation]` and `data[test]`, and downloads the kernels and the validation inputs. Without `--no-terrain` it also downloads the LOLA elevation products.

Kernels are downloaded to `kernels/` under the data root, outside the repository (`LSN_DATA_ROOT`; default `C:\lsn-data` on Windows, `~/lsn-data` elsewhere). Set `LSN_KERNEL_DIR` to use another folder. A download that does not match the checksum in `kernel_manifest.json` is refused, and the manifest is not rewritten when the files match, so a fresh clone stays clean. The whole setup from a fresh clone is in [`docs/setup.md`](../../../docs/setup.md).

## Method

| Choice | Value | Why |
|---|---|---|
| Library | SpiceyPy 8.4.0 (CSPICE N0067) | NAIF's own geometry code; no hand-written ephemeris |
| Planetary ephemeris | JPL DE440 (`de440s.bsp`) | Current JPL ephemeris for the Sun, the Earth and the Moon |
| Lunar orientation | `moon_pa_de440_200625.bpc` | Numerically integrated orientation of the lunar principal-axis frame, including librations |
| Body-fixed frame | `MOON_ME_DE440_ME421` (generic alias `MOON_ME` in `moon_de440_250416.tf`) | Mean-Earth / polar-axis frame, aligned with the DE421 mean-Earth frame. LOLA elevation products are labelled "mean Earth / polar axis of DE421", so site coordinates read from a LOLA map can be used directly |
| Frame **not** used | `MOON_PA_*` (principal axes), `IAU_MOON` | The principal-axis frame is rotated by about 0.029° (about 875 m on the surface) against the mean-Earth frame; `IAU_MOON` is a low-accuracy series. A test guards against mixing them |
| Site coordinates | Planetocentric latitude, east-positive longitude, height above the sphere | Same convention as the LOLA products and as Horizons |
| Reference radius | 1737.4 km sphere (asserted equal to the Moon radii in `pck00011.tpc`) | Radius of the LOLA elevation reference |
| Local frame | East, North, Up; Up = outward normal of the sphere | Azimuth from north through east (N 0°, E 90°); elevation from the local horizontal plane, **not** from the visible horizon |
| Aberration correction | `LT+S`, reception case | Light time plus stellar aberration: the direction in which the body is actually seen. Without stellar aberration the Sun is off by about 20″ |
| Time | TDB seconds past J2000 for all computation; UTC only for input and display (`naif0012.tls`) | TDB − UTC is 69.184 s in 2026; mixing them moves the Sun by tens of arcseconds |
| Angular radius | asin(R / distance); Sun R = 695 700 km; Earth R = 6378.1366 km (equatorial) | The Earth's disc is slightly flattened; the polar radius is 21.4 km smaller (0.3 %) |

### Two computation paths

1. **Direction table (site-independent).** `direction_table(et)` returns the apparent vectors Moon centre → Sun and Moon centre → Earth in the body-fixed frame. `topocentric_from_table(site, table)` subtracts the site position vector and projects on East, North, Up. One table serves every site, map pixel and viewer. The parallax of the Earth (up to 0.28°) is handled exactly by the vector subtraction; only the light-time and aberration corrections are evaluated for the centre instead of the site.
2. **Exact path.** `topocentric_exact(site, et, body)` puts the observer at the site itself (SPICE `spkcpo`). It is the reference for validation.

Measured difference between the two paths (7 sites from the equator to 0.5° from the pole, 60 days, 262 epochs each): at most **0.096″ for the Earth and 0.003″ for the Sun**. The independent SPICE routine `azlcpo` agrees with the exact path to 1 × 10⁻¹³ degrees.

## Limits

* No terrain, no refraction (the Moon has no atmosphere), no gravitational light bending (SPICE corrections are Newtonian). Horizons does include light bending, so the Horizons comparison bounds what this omission costs.
* Elevation is relative to the horizontal plane of the reference sphere. A point above its surroundings sees a horizon below that plane; that is the job of the horizon profile.
* The kernel set covers 1849-12-26 to 2150-01-22 (`de440s.bsp`).
* Leap seconds: `naif0012.tls` contains leap seconds up to 2017-01-01. UTC for dates after any future leap second would be off by one second until a new kernel is published.
* SPICE is not thread-safe; use processes, or compute the table once and share it.

## Sources

Kernels, library versions and licences are listed in [CREDITS.md](../../../CREDITS.md).
