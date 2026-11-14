# Credits

Every third-party item used in this project gets one row here before it is merged.

## Data

| Name | Provider | Version or product ID | Licence or terms | Source URL | Retrieved (UTC) |
|---|---|---|---|---|---|
| naif0012.tls (LSK) | NASA/JPL NAIF, generic kernels | naif0012.tls; sha256 678e32bdb5a7… (full hash in `ephemeris/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls | 2026-11-14T10:11:16Z |
| pck00011.tpc (text PCK) | NASA/JPL NAIF, generic kernels | pck00011.tpc; sha256 3dff7b1dbece… (full hash in `ephemeris/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc | 2026-11-14T10:11:17Z |
| de440s.bsp (SPK) | NASA/JPL NAIF, generic kernels | de440s.bsp; sha256 c1c7feeab882… (full hash in `ephemeris/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp | 2026-11-14T10:11:31Z |
| moon_pa_de440_200625.bpc (binary PCK) | NASA/JPL NAIF, generic kernels | moon_pa_de440_200625.bpc; sha256 60cd55aa401e… (full hash in `ephemeris/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc | 2026-11-14T10:11:34Z |
| moon_de440_250416.tf (FK) | NASA/JPL NAIF, generic kernels | moon_de440_250416.tf; sha256 a47c71e9c9f3… (full hash in `ephemeris/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf | 2026-11-14T10:11:35Z |
| JPL Horizons observer tables (Sun and Earth from seven lunar surface points), 28 responses | NASA/JPL Solar System Dynamics Group | Horizons API version 1.2; ephemeris DE441; queries and checksums in `validation/horizons/raw/*.meta.json` | Public NASA/JPL service; citation requested: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System | https://ssd.jpl.nasa.gov/api/horizons.api (full query URL per file in `validation/horizons/raw/*.meta.json`) | 2026-11-14T10:15:58Z to 2026-11-14T10:18:10Z |

## Software libraries

| Name | Version | Licence | Source URL | Used in |
|---|---|---|---|---|
| NumPy | 2.5.4 | BSD-3-Clause | https://github.com/numpy/numpy | `core/` (array maths, binary array files) |
| jsonschema (with its dependencies attrs, referencing, rpds-py, jsonschema-specifications) | 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema | `core/lsncore/contract/` (package validation) |
| pytest | 9.2.0 | MIT | https://github.com/pytest-dev/pytest | `core/tests/` (test runner, development only) |
| setuptools | build-time only | MIT | https://github.com/pypa/setuptools | `core/pyproject.toml` (build backend) |
| SpiceyPy (includes the NAIF CSPICE Toolkit N0067) | 8.4.0 | MIT (SpiceyPy); NAIF rules for CSPICE (free, no licence required) | https://github.com/AndrewAnnex/SpiceyPy ; https://naif.jpl.nasa.gov/naif/toolkit.html | `ephemeris/`, `validation/` |

## Images, fonts and other assets

| Name | Author or provider | Licence | Source URL | Used in |
|---|---|---|---|---|

## Use of AI tools

| Team member | Tool and model | Used for |
|---|---|---|
