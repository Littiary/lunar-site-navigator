# The orientation of the Earth as seen from the Moon

Code: `core/lsncore/earth_view.py`; written into the direction table by
`core/lsncore/ephem/table.py`. Tests: `core/tests/test_earth_view.py`,
`validation/tests/test_earth_view.py`. Reference data, thresholds and report:
`validation/earth_view/`. Package fields: contract 0.8,
[`docs/contract/SPEC.md`](../contract/SPEC.md) section 6.

Status on 14 November 2026: checked against closed forms, against SPICE's own
sub-observer routine and against JPL Horizons, inside thresholds written and committed
before any Horizons response was requested. The three angles are for drawing a textured
Earth; nothing else in the tool depends on them.

## 1. What is written

Per record of the direction table, for an observer at the centre of the Moon:

| Array | Meaning |
|---|---|
| `sub_lunar_lat_deg` | Latitude of the point of the Earth's surface at the centre of the disc, as on a map (perpendicular to the reference ellipsoid) |
| `sub_lunar_lon_deg` | Its east longitude, in (-180, 180] |
| `north_pole_angle_deg` | Position angle of the Earth's north pole in the sky: counted from the Moon's north pole (+Z of the table's body-fixed frame, projected on the plane of the sky) counter-clockwise, towards east = +Z x (direction to the Earth) |

The Earth is taken as it appears at the record time: its direction with the correction
for light time and stellar aberration of the table, its orientation one light time
(1.3 s) earlier. The Earth's axes come from SPICE (`pxfrm2`, frame `ITRF93`, the two
binary Earth-orientation kernels of the optional kernel group); the sub-lunar point is
where the line from the Moon's centre to the Earth's centre meets the reference
ellipsoid of the planetary constants kernel (6378.1366 km, 6356.7519 km).

With the direction to the Earth, which the table already holds, the three angles fix the
orientation of the Earth completely; SPEC section 6 gives the recipe that turns them
into the Earth's north pole and prime-meridian axis in the frame of the table.

Over the two years from 14 November 2026 the sub-lunar latitude stays within 27.8
degrees of the equator and the pole angle between -23.2 and +22.8 degrees; the sub-lunar
point moves west by 14.3 to 14.6 degrees per hour. The three arrays of a 24-month hourly
table are 210 576 bytes; computing them takes less than a second.

## 2. Checks

Thresholds were fixed before the first run; those of the Horizons comparison are in
`validation/earth_view/thresholds.json`, committed before the responses were requested.

| Case | Threshold | Measured |
|---|---|---|
| Closed forms: the Earth turned about its pole, its pole tipped towards the Moon (with and without flattening) and tipped sideways in the sky | 1e-9 deg | passes |
| 300 random epochs in two years against SPICE's sub-observer routine (`subpnt`, `INTERCEPT/ELLIPSOID`) | 0.001 deg | 0.00009 deg |
| The Earth's north pole and prime-meridian axis rebuilt from the three angles as stored (float32), by the recipe written out in the test, against SPICE's rotation | 0.01 deg | 0.00001 deg |
| Angles interpolated between hourly records (latitude and pole angle linearly, longitude linearly the short way round), 17 547 places | 0.05 deg | 0.0005, 0.0003 and 0.0003 deg |
| JPL Horizons, sub-observer latitude of the Earth seen from the centre of the Moon, 275 rows (hourly for a week; every 167 h for two years) | 0.05 deg | 0.0024 deg |
| JPL Horizons, sub-observer longitude, same rows | 0.05 deg | 0.0069 deg |
| JPL Horizons, position angle of the Moon's north pole seen from the centre of the Earth, 275 rows | 0.1 deg | 0.0002 deg |

The pole angle is judged on the queries with the Moon as target and the Earth's centre
as observer. The angle between the two projected poles is the same seen from either end
of the line: Horizons counts the Moon's pole from the Earth's pole of date
counter-clockwise as seen from the Earth, the table counts the Earth's pole from the
Moon's pole counter-clockwise as seen from the Moon, and the two are equal. The queries
with the Earth as target print a pole angle too; it agrees to 0.0002 degrees and is
listed in the report for information.

Horizons used its ITRF93 high-precision Earth model and the MEAN_ME lunar frame (response
headers), ephemeris DE441, Earth-orientation file `eop.261113.p270209`. While looking at
the layout of the responses, before the comparison was run, the first data row of two of
them was printed; the code and the thresholds were complete by then and were not changed.

## 3. Limits

1. **For drawing.** No event, window or number of the tool is computed from these angles.
2. **Centre of the Moon.** From a site on the surface the sub-observer point on the Earth
   differs by up to 0.28 degrees (the Moon's radius seen from the Earth); not modelled.
3. **Prediction.** After the last measured Earth-orientation data (13 November 2026 in
   the kernel used) the kernels hold a prediction. Horizons uses a prediction of the same
   date; the agreement over two years (0.007 degrees) therefore does not measure the
   error of the prediction itself, which is not quantified here.
4. **Longitude wraps.** A viewer that interpolates the longitude without going the short
   way round turns the Earth backwards once a day.
5. **Geometry only.** No day and night side, no clouds; the lit part of the Earth follows
   from the Sun's direction in the same table and is the viewer's to draw.
6. **Optional kernels.** Without the Earth-orientation kernels the table is written
   without the block and with a warning.
