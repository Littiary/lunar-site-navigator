// Look of the 3-D ground view (js/view3d.js): render pipeline and materials. Display only.
//
// Nothing here places, scales or hides an object, and nothing here reads a package value.
// view3d.js sets every position, direction, angular size and visibility state from the package;
// this module only decides how those pixels are shaded:
//   - pipeline: the scene is drawn into a half-float target (2x MSAA where WebGL 2 allows it), a
//     bloom pass spreads only very bright pixels (the Sun's disc), and the output pass applies
//     ACES filmic tone mapping and the sRGB transfer. The package horizon line and the patch
//     outlines are drawn afterwards straight to the screen, outside the tone mapping, so their
//     colours stay exactly the legend colours. On phones (coarse pointer or a small, dense
//     screen) the scene is drawn directly with tone mapping and no bloom, with a smaller
//     shadow map;
//   - the Sun: an emissive disc far above the bloom threshold, with limb darkening;
//   - the Earth: the NASA Blue Marble map (vendor/earth/README.md), lit from the Sun's
//     direction, so its phase follows the package directions, with a thin bright rim on the
//     day side for the atmosphere;
//   - the ground: very rough, non-metallic, with a Lommel-Seeliger term for the light from the
//     Sun (regolith shows almost no limb darkening) and a fine procedural detail in normal and
//     albedo that changes no vertex;
//   - stars: a fixed pseudo-random field for the look of a black sky. They are decorative, not
//     a star catalogue, and say nothing about the time or the place.
// No haze: the Moon has no atmosphere.

import * as THREE from "three";
import { EffectComposer } from "../vendor/three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "../vendor/three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "../vendor/three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "../vendor/three/addons/postprocessing/OutputPass.js";

export const EARTH_MAP = new URL("../vendor/earth/blue_marble_2048.jpg", import.meta.url).href;

// Quality from the device: phones and tablets (coarse pointer) and very dense small screens get
// the light path. ?quality=low or ?quality=high in the address overrides it (for testing).
export function chooseQuality(container) {
  let wanted = null;
  try { wanted = new URLSearchParams(window.location.search).get("quality"); } catch (e) { /* no address */ }
  if (wanted === "low" || wanted === "high") return wanted;
  const coarse = Boolean(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
  const dense = (window.devicePixelRatio || 1) >= 2.5 && Math.min(window.screen.width, window.screen.height) < 900;
  return coarse || dense ? "low" : "high";
}

export const QUALITY = {
  high: { bloom: true, shadowMap: 4096, maxPixelRatio: 1.5, stars: 6000 },
  low: { bloom: false, shadowMap: 2048, maxPixelRatio: 1.5, stars: 2500 },
};

// Bloom settings: only scene values above BLOOM_THRESHOLD (linear, before exposure) spread.
// Sunlit ground stays below it (see the clamp of the Lommel-Seeliger term); the Sun's disc is
// SUN_RADIANCE, far above it.
export const BLOOM = { strength: 0.18, radius: 0.2, threshold: 6 };
export const SUN_RADIANCE = 25;

// Draws the world scene, then the overlay (package horizon line and patch outlines) on top.
// depthScene holds depth-only copies of the terrain so that the outlines stay hidden behind
// the drawn ground in the post-processed path, as they are in the direct path.
export function createPipeline(renderer, scene, overlay, depthScene, camera, quality) {
  const q = QUALITY[quality];
  let composer = null, bloom = null;
  if (q.bloom) {
    const webgl2 = renderer.capabilities.isWebGL2;
    const target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: webgl2 ? 2 : 0 });
    composer = new EffectComposer(renderer, target);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), BLOOM.strength, BLOOM.radius, BLOOM.threshold);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());
  }
  let size = [0, 0, 0];
  return {
    quality,
    bloom: Boolean(composer),
    setSize(w, h) {
      const ratio = renderer.getPixelRatio();
      if (size[0] === w && size[1] === h && size[2] === ratio) return;
      size = [w, h, ratio];
      renderer.setSize(w, h, false);
      if (composer) { composer.setPixelRatio(ratio); composer.setSize(w, h); }
    },
    render() {
      if (!size[0] || !size[1]) return;   // a hidden pane: nothing to draw into
      if (composer) {
        composer.render();
        renderer.setRenderTarget(null);
        renderer.autoClear = false;
        renderer.clearDepth();
        if (overlay.children.some((o) => o.visible && o.isGroup)) renderer.render(depthScene, camera);
      } else {
        renderer.setRenderTarget(null);
        renderer.render(scene, camera);
        renderer.autoClear = false;
      }
      renderer.render(overlay, camera);
      renderer.autoClear = true;
    },
    dispose() { if (composer) { composer.renderTarget1.dispose(); composer.renderTarget2.dispose(); } },
  };
}

const LOGDEPTH_V = "#include <common>\n#include <logdepthbuf_pars_vertex>\n";
const LOGDEPTH_F = "#include <common>\n#include <logdepthbuf_pars_fragment>\n";

// The Sun: an emissive sphere seen from far away, with solar limb darkening
// (I(mu) = 1 - u (1 - mu), u = 0.6 in the visible).
export function sunMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { radiance: { value: SUN_RADIANCE }, tint: { value: new THREE.Color(1.0, 0.94, 0.84) } },
    vertexShader: `${LOGDEPTH_V}
      varying vec3 vNormalV;
      void main() {
        vNormalV = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `${LOGDEPTH_F}
      uniform float radiance;
      uniform vec3 tint;
      varying vec3 vNormalV;
      void main() {
        #include <logdepthbuf_fragment>
        float mu = clamp(normalize(vNormalV).z, 0.0, 1.0);
        gl_FragColor = vec4(tint * radiance * (1.0 - 0.6 * (1.0 - mu)), 1.0);
      }`,
  });
}

// Glow around the Sun: a disc facing the observer, CORONA_RADII Sun radii across, with a
// radial falloff. It is a child of the Sun's sphere (same centre, scaled with it) and depth
// tested, so terrain in front of the Sun cuts it as it cuts the disc. The bloom pass alone
// would make a square halo around so small and bright a source.
export const CORONA_RADII = 18;
export function coronaMesh() {
  const material = new THREE.ShaderMaterial({
    uniforms: { strength: { value: 1 } },
    vertexShader: `${LOGDEPTH_V}
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `${LOGDEPTH_F}
      uniform float strength;
      varying vec2 vUv;
      void main() {
        #include <logdepthbuf_fragment>
        float d = length(vUv - 0.5) * 2.0;
        float r = max(d * ${CORONA_RADII.toFixed(1)}, 1.0);
        float g = 0.9 / (r * r) + 0.05 * exp(-r * 0.25);
        g *= 1.0 - smoothstep(0.55, 1.0, d);
        gl_FragColor = vec4(vec3(1.0, 0.93, 0.82) * g * strength, 1.0);
      }`,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Mesh(new THREE.PlaneGeometry(2 * CORONA_RADII, 2 * CORONA_RADII), material);
}

// The Earth: day side from the Blue Marble map lit by the Sun, night side near black.
// sunDir is the scene direction to the Sun (set by view3d.js from the package direction).
export function earthMaterial(texture) {
  return new THREE.ShaderMaterial({
    uniforms: { map: { value: texture }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunLight: { value: 3.2 }, hasMap: { value: texture ? 1 : 0 } },
    vertexShader: `${LOGDEPTH_V}
      varying vec2 vUv;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vUv = uv;
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 w = modelMatrix * vec4(position, 1.0);
        vPosW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `${LOGDEPTH_F}
      uniform sampler2D map;
      uniform vec3 sunDir;
      uniform float sunLight;
      uniform float hasMap;
      varying vec2 vUv;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        #include <logdepthbuf_fragment>
        vec3 n = normalize(vNormalW);
        vec3 v = normalize(cameraPosition - vPosW);
        vec3 albedo = hasMap > 0.5 ? texture2D(map, vUv).rgb : vec3(0.18, 0.28, 0.45);
        float nl = dot(n, normalize(sunDir));
        float day = smoothstep(-0.06, 0.12, nl);
        vec3 lit = albedo * max(nl, 0.0) * sunLight * 0.45;
        // Atmosphere: a thin blue rim, brightest at the limb on the day side.
        float rim = pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 3.0);
        vec3 air = vec3(0.30, 0.55, 1.0) * rim * day * sunLight * 0.35;
        gl_FragColor = vec4(lit + air + albedo * 0.004, 1.0);
      }`,
  });
}

// Shell just outside the Earth's disc: the atmosphere seen edge-on, on the day side only.
export function earthHaloMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunLight: { value: 3.2 } },
    vertexShader: `${LOGDEPTH_V}
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 w = modelMatrix * vec4(position, 1.0);
        vPosW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `${LOGDEPTH_F}
      uniform vec3 sunDir;
      uniform float sunLight;
      varying vec3 vNormalW;
      varying vec3 vPosW;
      void main() {
        #include <logdepthbuf_fragment>
        vec3 n = normalize(vNormalW);
        vec3 v = normalize(cameraPosition - vPosW);
        float edge = 1.0 - abs(dot(n, v));
        float a = pow(edge, 6.0) * smoothstep(-0.25, 0.35, dot(n, normalize(sunDir)));
        gl_FragColor = vec4(vec3(0.35, 0.6, 1.0) * a * sunLight * 0.3, 1.0);
      }`,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
    side: THREE.FrontSide,
  });
}

// Ground: very rough regolith. The Sun's light follows Lommel-Seeliger (radiance relative to
// Lambert: 2 / (mu0 + mu), clamped), and a fine detail perturbs the shading normal and the albedo
// in world space. The detail is a small tiling texture made once here (value noise; red and green
// hold its slope, blue its height); its mipmaps fade it out where it would be finer than a pixel.
const LS_IRRADIANCE = `float dotNVls = saturate( dot( geometryNormal, geometryViewDir ) );
	vec3 irradiance = dotNL * directLight.color * min( 2.0 / max( dotNL + dotNVls, 1e-3 ), 2.5 );`;
const DETAIL_SIZE = 256;
function detailTexture() {
  const N = DETAIL_SIZE, h = new Float32Array(N * N);
  let seed = 7919;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  for (const [cell, weight] of [[64, 0.36], [32, 0.28], [16, 0.2], [8, 0.11], [4, 0.05]]) {
    const n = N / cell, lattice = Array.from({ length: n * n }, rnd);
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        const gx = Math.floor(x / cell), gy = Math.floor(y / cell);
        let fx = x / cell - gx, fy = y / cell - gy;
        fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
        const at = (i, j) => lattice[((j + n) % n) * n + ((i + n) % n)];
        const top = at(gx, gy) + (at(gx + 1, gy) - at(gx, gy)) * fx;
        const bottom = at(gx, gy + 1) + (at(gx + 1, gy + 1) - at(gx, gy + 1)) * fx;
        h[y * N + x] += weight * (top + (bottom - top) * fy);
      }
    }
  }
  const data = new Uint8Array(N * N * 4);
  const H = (x, y) => h[((y + N) % N) * N + ((x + N) % N)];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const k = (y * N + x) * 4, dx = (H(x + 1, y) - H(x - 1, y)) * 8, dy = (H(x, y + 1) - H(x, y - 1)) * 8;
      data[k] = Math.max(0, Math.min(255, Math.round(127.5 + 127.5 * dx)));
      data[k + 1] = Math.max(0, Math.min(255, Math.round(127.5 + 127.5 * dy)));
      data[k + 2] = Math.max(0, Math.min(255, Math.round(255 * H(x, y))));
      data[k + 3] = 255;
    }
  }
  const t = new THREE.DataTexture(data, N, N, THREE.RGBAFormat);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.magFilter = THREE.LinearFilter;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.generateMipmaps = true;
  t.anisotropy = 4;
  t.needsUpdate = true;
  return t;
}
export function groundMaterial(color) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: 1, metalness: 0, side: THREE.DoubleSide });
  const detail = detailTexture();
  m.onBeforeCompile = (shader) => {
    shader.uniforms.detailMap = { value: detail };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vDetailPos;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvDetailPos = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vDetailPos;\nuniform sampler2D detailMap;")
      .replace("#include <lights_physical_pars_fragment>", THREE.ShaderChunk.lights_physical_pars_fragment.replace("vec3 irradiance = dotNL * directLight.color;", LS_IRRADIANCE))
      .replace("#include <color_fragment>", `#include <color_fragment>
        vec2 dp = vDetailPos.xz;
        vec4 fine = texture2D(detailMap, dp / 2.1);
        vec4 mid = texture2D(detailMap, dp / 9.5 + 0.37);
        vec4 broad = texture2D(detailMap, dp / 61.0 + 0.71);
        diffuseColor.rgb *= 1.0 + 0.16 * (mid.b - 0.5) + 0.28 * (broad.b - 0.5);`)
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
        {
          vec2 slope = (fine.rg - 0.5) * 0.16 + (mid.rg - 0.5) * 0.12;
          vec3 bump = vec3(-slope.x, 0.0, -slope.y);
          normal = normalize(normal + (viewMatrix * vec4(bump, 0.0)).xyz);
        }`);
  };
  return m;
}

// Stars: count points on a sphere of radius r around the observer, from a fixed seed.
// Brightness falls off steeply so that most stars are faint, as on a long exposure.
export function starField(count, r) {
  let s = 20261115;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  const pos = new Float32Array(count * 3), bright = new Float32Array(count);
  const v = new THREE.Vector3();
  for (let k = 0; k < count; k++) {
    do { v.set(rnd() * 2 - 1, rnd() * 2 - 1, rnd() * 2 - 1); } while (v.lengthSq() > 1 || v.lengthSq() < 1e-4);
    v.normalize().multiplyScalar(r);
    pos.set([v.x, v.y, v.z], k * 3);
    const u = rnd();
    bright[k] = 0.04 + 1.6 * u * u * u * u * u * u;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("bright", new THREE.BufferAttribute(bright, 1));
  const material = new THREE.ShaderMaterial({
    uniforms: { pixelRatio: { value: 1 } },
    vertexShader: `${LOGDEPTH_V}
      attribute float bright;
      uniform float pixelRatio;
      varying float vBright;
      void main() {
        vBright = bright;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = (1.2 + 1.6 * bright) * pixelRatio;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `${LOGDEPTH_F}
      varying float vBright;
      void main() {
        #include <logdepthbuf_fragment>
        vec2 c = gl_PointCoord - 0.5;
        float a = smoothstep(0.5, 0.1, length(c));
        gl_FragColor = vec4(vec3(0.85, 0.9, 1.0) * vBright * a, 1.0);
      }`,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  });
  const points = new THREE.Points(g, material);
  points.frustumCulled = false;
  points.renderOrder = -1;
  return points;
}

export function loadEarthMap(onLoad) {
  const t = new THREE.TextureLoader().load(EARTH_MAP, () => { if (onLoad) onLoad(t); }, undefined, () => { /* the Earth stays plain blue */ });
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
