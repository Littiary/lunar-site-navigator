# three.js 0.160.0 addons (vendored)

Post-processing modules of three.js, copied unchanged from the same npm package as `../three.module.js` (version 0.160.0, so the addons match the core exactly). The 3-D ground view (`js/look3d.js`) uses them for the bloom of the Sun's disc and for ACES filmic tone mapping with the sRGB output. They import `three` through the page's import map, so nothing is loaded from outside.

| Item | Value |
|---|---|
| Source | https://registry.npmjs.org/three/-/three-0.160.0.tgz (members `package/examples/jsm/postprocessing/*` and `package/examples/jsm/shaders/*` listed below) |
| Registry integrity of the tarball | `sha512-DLU8lc0zNIPkM7rH5/e1Ks1Z8tWCGRq6g8mPowdDJpw1CFBJMU7UoJjC6PefXW7z//SSl0b2+GCw14LB+uDhng==` (checked after download: match; the `three.module.js` in the same tarball has the SHA-256 recorded in `../README.md`) |
| Retrieved (UTC) | 2026-11-15T17:55:00Z |
| Licence | MIT, the licence of three.js (`../LICENSE`) |

| File | SHA-256 |
|---|---|
| `postprocessing/EffectComposer.js` | `d234e578618fa816955ebdc059c049c577e203e650e33cf22bde3f232c29e669` |
| `postprocessing/MaskPass.js` | `328cf7db0da5d9be83ffe39d54b01d5ac1fddf108cc98182ddbb056f5c8b537f` |
| `postprocessing/OutputPass.js` | `13817fc7a87f662d29d2c5e00f44d3a4588c9afac4a372de0cacb0e44e368ffd` |
| `postprocessing/Pass.js` | `b3c6128340eaa37e40a6a2f1b738e894c855239417d50959759b34a2b5e89f92` |
| `postprocessing/RenderPass.js` | `1c90c085312871c4bcdccfcf519499c6276dd503363fcf7cb7f703add45cf4a2` |
| `postprocessing/ShaderPass.js` | `3b28a1ee27e0eb96c0eab137a1f442ccf127a926904eced2d51e125ec44af781` |
| `postprocessing/UnrealBloomPass.js` | `8f09315c0cec117a0ca2494d3e3586035b3c4323d6dcb037537cc51b04c3cdba` |
| `shaders/CopyShader.js` | `4e3346db194db56a596cd074e9bdb39fb5eb52040c333e0d29dc4eb1324d3b1d` |
| `shaders/LuminosityHighPassShader.js` | `3d841cc594a0c1767d1b0185720b32761a0133c5f1b70b56658e28f2fb9b7900` |
| `shaders/OutputShader.js` | `53a52e430c27bc36ceaab8ae90a2b4af7b02672d7ee4b29d6ba3c28e09c92c2a` |

Do not edit these files. `web/tests/test_look3d.py` checks every checksum. To update, copy the same members from the tarball of the new core version, together with `../three.module.js`, and change this table and the test together.
