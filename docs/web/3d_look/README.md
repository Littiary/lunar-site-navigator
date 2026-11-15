# 3-D ground view: look before and after

Screenshots of the web 3-D ground view (`web/viewer/js/view3d.js` with `web/viewer/js/look3d.js`) before and after the new look, single-site viewer, default observer height (2 m), 1280 x 720 canvas pixels, drawn from the published packages in `packages/`. Each pair shows the same package input: the same Sun and Earth directions and angular sizes, the same horizon profile and the same view direction. Only the shading differs.

| Site and time (UTC) | Default view (toward the Sun) | Toward the Earth |
|---|---|---|
| Shackleton crater rim crest, 2026-12-07T04:00Z (sample 556): the package gives 0.0 % of the Sun's disc and 0.0 % of the Earth's disc above the horizon, so neither body shows and the Sun has no glow | `before_shackleton_2026-12-07T0400Z_sun.png`, `after_shackleton_2026-12-07T0400Z_sun.png` | `before_shackleton_2026-12-07T0400Z_earth.png`, `after_shackleton_2026-12-07T0400Z_earth.png` |
| de Gerlache crater rim crest, 2027-07-29T06:00Z (sample 6174): Sun and Earth above the horizon | `before_degerlache_2027-07-29T0600Z_sun.png`, `after_degerlache_2027-07-29T0600Z_sun.png` | `before_degerlache_2027-07-29T0600Z_earth.png`, `after_degerlache_2027-07-29T0600Z_earth.png` |

The horizon line check printed under the view is the same before and after (1440 vertices read back, at most 2.0e-7° (Shackleton) and 2.3e-7° (de Gerlache) in elevation and 2.6e-6° in azimuth from the package profile).

## What changed in the look

- **Sun**: an emissive disc at the package angular size with solar limb darkening, far above the bloom threshold, ACES filmic tone mapping and sRGB output, a bloom pass (three.js `UnrealBloomPass`, vendored) and a round, depth-tested glow. When the package puts the whole disc below the horizon (`visible_fraction` 0) the disc drops below the bloom threshold and the glow is hidden.
- **Earth**: the NASA Blue Marble map (`web/viewer/vendor/earth/`), turned so that the sub-lunar point of the `earth_view` record faces the observer and the pole follows the package pole; lit from the Sun's package direction, so its phase is right; a thin blue rim on the day side.
- **Ground**: very rough, non-metallic, with a Lommel-Seeliger term for sunlight (regolith shows almost no limb darkening), a fine detail texture in normal and albedo (no vertex moves), soft-edged shadows (`PCFSoftShadowMap`) from a shadow camera fitted to the terrain patches as seen from the Sun, and near-black ambient light.
- **Sky**: a fixed pseudo-random star field. It is decoration, not a star catalogue.
- **Overlay**: the package horizon line and the patch outlines are drawn after the tone mapping, so their colours stay the legend colours.
- **Phones**: a coarse pointer or a small, very dense screen selects the light path (no bloom, direct tone mapping, 2048 shadow map). `?quality=low` or `?quality=high` in the address forces a path.

Every position, direction, angular size, visibility state and horizon value is still set by `view3d.js` from the package, the same on both paths. `web/tests/test_look3d.py` checks this in the source and, with Playwright, by drawing one package input on both paths and comparing the Sun and Earth positions and sizes, the horizon line read back and its colours.

## Frame time

Measured on the build laptop (Intel Iris Xe Graphics, Chrome through ANGLE/Direct3D 11), de Gerlache view above, canvas 1278 x 718, 120 redraws in a row with a GPU sync (`readPixels`) after each one, in a page that was not in the foreground. The numbers fall from series to series as the laptop warms up, so they are given as ranges of several series taken one after another.

| Render path | Frames per second |
|---|---|
| Before (one pass, no post-processing) | 48 to 63 |
| After, laptop path (bloom, 2x MSAA in a half-float target) | about 29 to 45 (measured with 2x MSAA; 25 to 32 with 4x) |
| After, phone path (`?quality=low`) | about 92 |

The view draws only when something changes (a drag, a zoom, a new time), not continuously, and the shadow map is drawn again only when the Sun or the terrain changes. Under the sustained load above, the laptop path does not reach a steady 60 fps on this integrated GPU; it was not measured in a foreground window or on a discrete GPU.
