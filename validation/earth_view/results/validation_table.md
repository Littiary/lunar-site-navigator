# Orientation of the Earth as seen from the Moon: science core against JPL Horizons

Overall: **PASS**, 550 rows in 4 queries. Thresholds (fixed beforehand): sub-lunar latitude and longitude 0.05 deg, position angle of the north pole 0.1 deg.

| Query | Rows | Span (UT) | Sub-lunar latitude, largest difference | Sub-lunar longitude | Pole angle | Status |
|---|---|---|---|---|---|---|
| `earth_from_moon__week` | 169 | 2026-11-14T00:00:00 to 2026-11-21T00:00:00 | 0.0019 deg | 0.0038 deg | 0.0001 deg (reported, not judged) | PASS |
| `earth_from_moon__two_years` | 106 | 2026-11-14T00:00:00 to 2028-11-13T15:00:00 | 0.0024 deg | 0.0069 deg | 0.0002 deg (reported, not judged) | PASS |
| `moon_from_earth__week` | 169 | 2026-11-14T00:00:00 to 2026-11-21T00:00:00 | not in this query | not in this query | 0.0001 deg | PASS |
| `moon_from_earth__two_years` | 106 | 2026-11-14T00:00:00 to 2028-11-13T15:00:00 | not in this query | not in this query | 0.0002 deg | PASS |

The pole angle is judged on the queries with the Moon as target and the centre of the Earth as observer: the angle between the two projected poles is the same seen from either end of the line. The queries with the Earth as target print a pole angle as well; it is listed for information.

Definition printed in the responses: 'NP.ang, NP.dist,' = Targets' apparent north-pole position angle (counter-clockwise with respect to the direction of the true-of-date reference-frame north-pole) and its angular distance from the sub-observer point (center of disk) at observation time. A negative distance indicates the planets' north-pole is on the hidden hemisphere.

Horizons prints longitude and latitude with six decimals and the pole angle with four; the rounding is not subtracted.
