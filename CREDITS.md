# Credits

Every third-party item used in this project gets one row here before it is merged.

## Data

| Name | Provider | Version or product ID | Licence or terms | Source URL | Retrieved (UTC) |
|---|---|---|---|---|---|
| naif0012.tls (LSK) | NASA/JPL NAIF, generic kernels | naif0012.tls; sha256 678e32bdb5a7… (full hash in `core/lsncore/ephem/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls | 2026-11-14T10:11:16Z |
| pck00011.tpc (text PCK) | NASA/JPL NAIF, generic kernels | pck00011.tpc; sha256 3dff7b1dbece… (full hash in `core/lsncore/ephem/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc | 2026-11-14T10:11:17Z |
| de440s.bsp (SPK) | NASA/JPL NAIF, generic kernels | de440s.bsp; sha256 c1c7feeab882… (full hash in `core/lsncore/ephem/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp | 2026-11-14T10:11:31Z |
| moon_pa_de440_200625.bpc (binary PCK) | NASA/JPL NAIF, generic kernels | moon_pa_de440_200625.bpc; sha256 60cd55aa401e… (full hash in `core/lsncore/ephem/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc | 2026-11-14T10:11:34Z |
| moon_de440_250416.tf (FK) | NASA/JPL NAIF, generic kernels | moon_de440_250416.tf; sha256 a47c71e9c9f3… (full hash in `core/lsncore/ephem/kernel_manifest.json`) | NAIF rules: free, no licence required; unmodified kernels may be redistributed (https://naif.jpl.nasa.gov/naif/rules.html) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf | 2026-11-14T10:11:35Z |
| JPL Horizons observer tables (Sun and Earth from seven lunar surface points), 28 responses | NASA/JPL Solar System Dynamics Group | Horizons API version 1.2; ephemeris DE441; queries and checksums in `validation/horizons/raw/*.meta.json` | Public NASA/JPL service; citation requested: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System | https://ssd.jpl.nasa.gov/api/horizons.api (full query URL per file in `validation/horizons/raw/*.meta.json`) | 2026-11-14T10:15:58Z to 2026-11-14T10:18:10Z |
| JPL Horizons rise/transit/set tables (Sun from four lunar surface points), 4 responses | NASA/JPL Solar System Dynamics Group | Horizons API version 1.2; ephemeris DE441; queries and checksums in `validation/horizons_rts/raw/*.meta.json` | Public NASA/JPL service; citation requested: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System | https://ssd.jpl.nasa.gov/api/horizons.api (full query URL per file in `validation/horizons_rts/raw/*.meta.json`) | 2026-11-14T10:33:32Z to 2026-11-14T10:33:43Z |
| NASA SP-2000-4029, Apollo by the Numbers (tables 'LM Lunar Landing' and 'Launch Windows', Apollo 16 summary) | NASA History Division | page checksums in `validation/landers/cases.json` | NASA publication; published values quoted with citation; no text, tables or images reproduced | https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_18-27_LM_Lunar_Landing.htm ; https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_18-14_Launch_Windows.htm ; https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_16a_Summary.htm | 2026-11-14T11:07:54Z to 2026-11-14T11:07:56Z |
| Apollo Lunar Surface Journal: Sun and Earth altitude and azimuth table; 'Sun Angles' (B. W. Lawrence) | Apollo Lunar Surface Journal (hosted by NASA and apollojournals.org) | page checksums in `validation/landers/cases.json` | Published values quoted with citation; no text, tables or images reproduced | https://www.nasa.gov/wp-content/uploads/static/history/alsj/Scotti_AltAz.txt ; https://apollojournals.org/alsj/sunangles.html | 2026-11-14T11:07:56Z to 2026-11-14T11:07:57Z |
| Firefly Blue Ghost Mission 1: press release of 17 March 2025 and live updates | Firefly Aerospace | page checksums in `validation/landers/cases.json` | Published values quoted with citation; no text, tables or images reproduced | https://fireflyspace.com/news/firefly-aerospace-successfully-completes-14-days-of-surface-operations-on-the-moon ; https://fireflyspace.com/news/blue-ghost-mission-1-live-updates/ | 2026-11-14T11:07:58Z to 2026-11-14T11:07:59Z |
| LROC featured images 1407 (Blue Ghost) and 1314 (Chandrayaan-3): landing coordinates | NASA/GSFC/Arizona State University (LROC) | page checksums in `validation/landers/cases.json` | Published values quoted with citation; no text, tables or images reproduced | https://lroc.im-ldi.com/images/1407 ; https://lroc.im-ldi.com/images/1314 | 2026-11-14T11:08:00Z to 2026-11-14T11:08:01Z |
| ISRO Chandrayaan-3 mission updates | Indian Space Research Organisation | page checksums in `validation/landers/cases.json` | Published values quoted with citation; no text, tables or images reproduced | https://www.isro.gov.in/Chandrayaan3.html | 2026-11-14T11:08:02Z |
| NASA GSFC eclipse chart 'Total Lunar Eclipse of 2025 Mar 14' (F. Espenak): whole-Moon contact times | NASA Goddard Space Flight Center | page checksum in `validation/eclipse/cases.json` | NASA publication; published values quoted with citation; no text, tables or images reproduced | https://eclipse.gsfc.nasa.gov/LEplot/LEplot2001/LE2025Mar14T.pdf | 2026-11-14T11:19:45Z |
| NASA Science: 'What You Need To Know About the March 2025 Total Lunar Eclipse': milestone times | NASA | page checksum in `validation/eclipse/cases.json` | NASA publication; published values quoted with citation; no text, tables or images reproduced | https://science.nasa.gov/solar-system/moon/what-you-need-to-know-about-the-march-2025-total-lunar-eclipse/ | 2026-11-14T11:19:43Z |

## Software libraries

| Name | Version | Licence | Source URL | Used in |
|---|---|---|---|---|
| NumPy | 2.5.4 | BSD-3-Clause | https://github.com/numpy/numpy | `core/` (array maths, binary array files) |
| jsonschema (with its dependencies attrs, referencing, rpds-py, jsonschema-specifications) | 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema | `core/lsncore/contract/` (package validation) |
| pytest | 9.2.0 | MIT | https://github.com/pytest-dev/pytest | `core/tests/` (test runner, development only) |
| setuptools | build-time only | MIT | https://github.com/pypa/setuptools | `core/pyproject.toml` (build backend) |
| SpiceyPy (includes the NAIF CSPICE Toolkit N0067) | 8.4.0 | MIT (SpiceyPy); NAIF rules for CSPICE (free, no licence required) | https://github.com/AndrewAnnex/SpiceyPy ; https://naif.jpl.nasa.gov/naif/toolkit.html | `core/lsncore/ephem/`, `core/lsncore/events/`, `validation/` |

## Images, fonts and other assets

| Name | Author or provider | Licence | Source URL | Used in |
|---|---|---|---|---|

## Use of AI tools

| Team member | Tool and model | Used for |
|---|---|---|
