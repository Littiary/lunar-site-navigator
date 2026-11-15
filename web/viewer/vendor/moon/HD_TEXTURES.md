# Moon colour map, 4K and 8K copies

`lroc_color_4k.jpg` and `lroc_color_8k.jpg` are the same 2025 colour map as `lroc_color_2k.jpg` (see `README.md`), from the larger files of the NASA Scientific Visualization Studio "CGI Moon Kit". The SVS publishes these sizes only as 16-bit TIFFs, so each was converted once to an 8-bit JPEG: every 16-bit sRGB code value v became round(v × 255 / 65535) (same encoding, no colour change), alpha none, then saved as a progressive JPEG at quality 85 with Pillow 13.0.0 and tifffile 2026.11.12. Nothing else was changed: no resampling, cropping or colour correction. The mean absolute difference of the 4K copy, scaled down to 2048 × 1024, from `lroc_color_2k.jpg` is 2.4 of 255 per channel.

The Moon globe (`web/viewer/js/globe.js`) shows the 2K map first and then swaps in the sharpest copy the device should load: the 4K copy wherever WebGL accepts a 4096-pixel texture, the 8K copy only on a large screen with a fine pointer. The map is used for orientation only; no number depends on it.

| Item | 4K | 8K |
|---|---|---|
| Source file | https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_16bit_srgb_4k.tif | https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_16bit_srgb_8k.tif |
| Source size | 4096 × 2048, 16-bit sRGB, 61 891 324 bytes | 8192 × 4096, 16-bit sRGB, 243 289 792 bytes |
| Source Last-Modified | Wed, 03 Dec 2025 19:55:34 GMT | Wed, 03 Dec 2025 19:55:35 GMT |
| Retrieved (UTC) | 2026-11-15T16:06:32Z | 2026-11-15T16:07:58Z |
| Source SHA-256 | `9731fa8af425b6c2f88f277ecca82bf8c603f3743894f64ed7b25c5bfefa22ff` | `db7808e878b6a55eb409bb231eab8deb477f84b5c9d7396d76ff73e5d54992d9` |
| File here | `lroc_color_4k.jpg`, 1 411 546 bytes | `lroc_color_8k.jpg`, 4 802 989 bytes |
| SHA-256 here | `ae7d3b5ae33d7932bf4d8484ea59f252c81b5778656fabae1b0b9930ed81b0d9` | `064f3651c9e7d9b3f260c0e7bc3291bdc5ede242c4eedf626fdc3bf6a4c7f98a` |

Source page: https://svs.gsfc.nasa.gov/4720/ (CGI Moon Kit, ID 4720, "Last updated Friday, January 9, 2026", read 2026-11-15T16:05:58Z). Projection: equirectangular, centred on 0° longitude. Content: 2025 colour map adapted from the LROC WAC Hapke-normalised mosaic; latitudes the mosaic does not cover are filled with the LOLA albedo map. The page states that the map is "optimized for aesthetics, not science".

Credit, as the source page asks: NASA's Scientific Visualization Studio (visualizer Ernie Wright, scientist Noah Petro); LROC WAC data NASA/GSFC/Arizona State University; LOLA data NASA/GSFC. Terms: NASA content, used for information with this credit under the NASA Images and Media Usage Guidelines (https://www.nasa.gov/nasa-brand-center/images-and-media/).

`web/tests/test_moon_texture.py` checks the checksums above.
