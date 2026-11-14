// Read result packages (contract 0.x, docs/contract/SPEC.md) in the browser.
//
// Every array is checked against its manifest entry (byte length and SHA-256) before it is
// used. Nothing here computes a scientific value: arrays are returned exactly as stored.

export class PackageError extends Error {}

const CONTRACT_NAME = "lsn-package";
const SUPPORTED_MAJOR = "0";
const DTYPES = {
  "<f4": [Float32Array, 4],
  "<f8": [Float64Array, 8],
  "<i4": [Int32Array, 4],
  "|u1": [Uint8Array, 1],
};
// Typed arrays use the byte order of the machine; packages are little-endian.
const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

function checkContract(where, contract) {
  if (!contract || contract.name !== CONTRACT_NAME) {
    throw new PackageError(`${where}: not an ${CONTRACT_NAME} document`);
  }
  const major = String(contract.version || "").split(".")[0];
  if (major !== SUPPORTED_MAJOR) {
    throw new PackageError(`${where}: contract version ${contract.version}; this viewer reads ${SUPPORTED_MAJOR}.x only`);
  }
}

async function fetchOk(url, kind) {
  const response = await fetch(url);
  if (!response.ok) throw new PackageError(`${url}: HTTP ${response.status}`);
  return kind === "json" ? response.json() : response.arrayBuffer();
}

async function sha256Hex(buffer) {
  if (!globalThis.crypto || !crypto.subtle) return null; // only in secure contexts (https, localhost)
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function loadIndex(url) {
  const absolute = new URL(url, location.href);
  const index = await fetchOk(absolute, "json");
  checkContract(absolute.pathname, index.contract);
  if (index.kind !== "index") throw new PackageError(`${absolute.pathname}: kind is ${index.kind}, expected index`);
  return { index, base: new URL(".", absolute), sites: index.packages.filter((p) => p.kind === "site") };
}

export async function loadSite(base, entry) {
  const dir = new URL(entry.path.replace(/\/?$/, "/"), base);
  const manifest = await fetchOk(new URL("manifest.json", dir), "json");
  checkContract(entry.path, manifest.contract);
  if (manifest.kind !== "site") throw new PackageError(`${entry.path}: kind is ${manifest.kind}, expected site`);
  if (manifest.package_id !== entry.package_id) {
    throw new PackageError(`${entry.path}: package_id ${manifest.package_id} differs from the index (${entry.package_id})`);
  }
  return new SitePackage(dir, manifest);
}

export class SitePackage {
  constructor(dir, manifest) {
    this.dir = dir;
    this.manifest = manifest;
    this.cache = new Map();
    this.unverified = new Set(); // files whose SHA-256 could not be checked (no Web Crypto)
  }

  get id() { return this.manifest.package_id; }
  get timeline() { return this.manifest.timeline || null; }

  methodStatus(id) {
    const card = (this.manifest.methods || {})[id];
    return (card && card.validation && card.validation.status) || "unknown";
  }

  // The array described by `ref`, checked against the manifest. Returns {values, shape, row(i)}.
  array(ref) {
    if (!this.cache.has(ref.file)) this.cache.set(ref.file, this.readArray(ref));
    return this.cache.get(ref.file);
  }

  async readArray(ref) {
    if (!LITTLE_ENDIAN) throw new PackageError("this browser is big-endian; packages are little-endian");
    const spec = DTYPES[ref.dtype];
    if (!spec) throw new PackageError(`${ref.file}: unsupported dtype ${ref.dtype}`);
    const [Type, size] = spec;
    const count = ref.shape.reduce((a, b) => a * b, 1);
    const buffer = await fetchOk(new URL(ref.file, this.dir), "buffer");
    if (buffer.byteLength !== count * size) {
      throw new PackageError(`${ref.file}: ${buffer.byteLength} bytes, expected ${count * size}`);
    }
    const digest = await sha256Hex(buffer);
    if (digest === null) this.unverified.add(ref.file);
    else if (digest !== ref.sha256) throw new PackageError(`${ref.file}: SHA-256 differs from the manifest`);
    const values = new Type(buffer);
    const width = ref.shape[ref.shape.length - 1];
    return { values, shape: ref.shape, row: (i) => values.subarray(i * width, (i + 1) * width) };
  }
}
