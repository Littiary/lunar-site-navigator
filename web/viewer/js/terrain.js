// Terrain patches of a site package (contract 0.7 and later, SPEC 5.9) as plain arrays for
// drawing. No three.js here, so that the geometry can be checked against the package in Node.
//
// Scene axes, metres, origin at the ground point of the site: x = east, y = up, z = -north.
// A node is placed exactly as SPEC 5.9 says:
//   east = east_min_m + j * spacing_m,  north = north_min_m + i * spacing_m,  up = up_m[i][j].
// Nothing is projected, smoothed or corrected: the curvature of the Moon is in the values.
//
// Overlaps: patches are taken finest first by their own spacing_m (SPEC 5.9 since 0.11: the
// order and number of the list are not part of the contract; a package may add a finer patch,
// for example a 5 m `site` patch). A cell of a coarser patch whose four corners all lie in
// the square of the next finer patch is left out, so every place is drawn once, by the finest
// patch that covers it. Where the finer square's edge does not meet the coarser surface exactly
// (block averages differ), a vertical skirt below the finer edge closes the gap. Cells with a
// NaN corner (no elevation data) are left out, as the contract requires.
//
// The surface is for drawing only (SPEC 5.9): visibility always comes from the timeline.

// The finer patch's square, inside which a coarser patch draws nothing.
function insideSquare(east, north, half) {
  return Math.abs(east) <= half && Math.abs(north) <= half;
}

// Geometry of one patch. `up` is the patch's float32 array [count_north * count_east];
// `finerHalf` the half width of the next finer patch (null for the finest); `skirt_m` the depth
// of the skirt below this patch's own edge (0 for none).
export function patchGeometry(patch, up, finerHalf = null, skirt_m = 0) {
  const nE = patch.count_east, nN = patch.count_north, s = patch.spacing_m;
  const e0 = patch.east_min_m, n0 = patch.north_min_m;
  if (up.length !== nE * nN) throw new Error(`patch ${patch.id}: ${up.length} values for ${nN} x ${nE} nodes`);
  const positions = new Float32Array(nE * nN * 3);
  for (let i = 0; i < nN; i++) {
    for (let j = 0; j < nE; j++) {
      const k = (i * nE + j) * 3;
      positions[k] = e0 + j * s;          // east
      positions[k + 1] = up[i * nE + j];  // up (NaN nodes are never referenced)
      positions[k + 2] = -(n0 + i * s);   // -north
    }
  }
  const node = (i, j) => i * nE + j;
  const ok = (i, j) => Number.isFinite(up[node(i, j)]);
  const covered = (i, j) => finerHalf !== null && insideSquare(e0 + j * s, n0 + i * s, finerHalf);
  const indices = [];
  let kept = 0, skippedFiner = 0, skippedNaN = 0;
  for (let i = 0; i < nN - 1; i++) {
    for (let j = 0; j < nE - 1; j++) {
      if (covered(i, j) && covered(i, j + 1) && covered(i + 1, j) && covered(i + 1, j + 1)) { skippedFiner++; continue; }
      if (!(ok(i, j) && ok(i, j + 1) && ok(i + 1, j) && ok(i + 1, j + 1))) { skippedNaN++; continue; }
      const a = node(i, j), b = node(i, j + 1), c = node(i + 1, j), d = node(i + 1, j + 1);
      indices.push(a, b, c, b, d, c); // counter-clockwise seen from above: normals point up
      kept++;
    }
  }
  // Skirt: for each edge between two boundary nodes, a wall from the edge down by skirt_m.
  let skirt = new Float32Array(0), skirtIndices = [];
  if (skirt_m > 0) {
    const ring = [];
    for (let j = 0; j < nE; j++) ring.push([0, j]);
    for (let i = 1; i < nN; i++) ring.push([i, nE - 1]);
    for (let j = nE - 2; j >= 0; j--) ring.push([nN - 1, j]);
    for (let i = nN - 2; i >= 1; i--) ring.push([i, 0]);
    const walls = [];
    for (let r = 0; r < ring.length; r++) {
      const [i1, j1] = ring[r], [i2, j2] = ring[(r + 1) % ring.length];
      if (ok(i1, j1) && ok(i2, j2)) walls.push([node(i1, j1), node(i2, j2)]);
    }
    skirt = new Float32Array(walls.length * 2 * 3);
    const base = nE * nN;
    walls.forEach(([p, q], w) => {
      for (const [slot, n] of [[0, p], [1, q]]) {
        const t = (w * 2 + slot) * 3;
        skirt[t] = positions[n * 3]; skirt[t + 1] = positions[n * 3 + 1] - skirt_m; skirt[t + 2] = positions[n * 3 + 2];
      }
      const p2 = base + w * 2, q2 = base + w * 2 + 1;
      skirtIndices.push(p, q, p2, q, q2, p2);
    });
  }
  const all = new Float32Array(positions.length + skirt.length);
  all.set(positions); all.set(skirt, positions.length);
  return { id: patch.id, spacing_m: s, positions: all, nodeCount: nE * nN, indices: Uint32Array.from(indices.concat(skirtIndices)), surfaceIndexCount: indices.length, kept, skippedFiner, skippedNaN };
}

// The patches of a package ordered by spacing, finest first (never by their place in the list).
export function patchesFinestFirst(terrain) {
  return terrain.patches.slice().sort((a, b) => a.spacing_m - b.spacing_m);
}

// All patches of a package, finest first, each without the part a finer patch covers. The
// skirt below each patch except the coarsest is two cells of the next coarser patch deep.
export function terrainGeometry(terrain, upArrays) {
  const patches = patchesFinestFirst(terrain);
  return patches.map((p, k) => {
    const finer = k > 0 ? patches[k - 1] : null;
    const coarser = k + 1 < patches.length ? patches[k + 1] : null;
    return patchGeometry(p, upArrays[p.id], finer ? finer.half_width_m : null, coarser ? 2 * coarser.spacing_m : 0);
  });
}

// Height of the ground point under the observer in the finest patch: the node at the centre of
// the grid (SPEC 5.9: element [0][0] is at -half_width_m, so the centre node is the site).
export function groundAtSite(patch, up) {
  const j = Math.round(-patch.east_min_m / patch.spacing_m), i = Math.round(-patch.north_min_m / patch.spacing_m);
  return up[i * patch.count_east + j];
}
