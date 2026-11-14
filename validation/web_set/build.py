"""Build the set of packages for the web view: the published packages without arrays it does not use.

Nothing is computed. The source is the published set in ``packages/``; the output is a
second package root that the web build can be pointed at::

    python -m validation.web_set.build [--source packages] [--out build/packages_web] [--smaller] [--transfer]

What the web set is:

* every site package of the published set, with the same ``package_id``, the same
  ``request`` and ``inputs`` and, value for value, the same manifest (events, windows,
  metrics, calendar, landing windows, uncertainty, obstacles, blockers, method cards),
  except that the arrays named in ``LEFT_OUT`` are not in it. The contract marks every one
  of them as optional, and no file of the web code names them;
* the arrays that stay, byte for byte (same file, same SHA-256 in the manifest);
* the site-pairs package, byte for byte;
* an ``index.json`` listing these packages.

The direction-table package is not in the web set: the web view does not read it. Each
site package still names it in ``inputs``.

``--smaller`` also leaves out the arrays in ``CHECKED_FOR``. The web view does not fetch
them either, but its ground view looks whether the manifest has them and, if not, says on
the page that the package does not contain them. So this option changes one line of text
on that page; it changes no number. The method cards that only these arrays referred to go
with them, because the contract wants every card to be referred to.

A web-set package says what it is: it carries one more entry in ``warnings`` that names
the complete package (id and content digest) and what was left out. Its ``content_sha256``
is therefore not that of the complete package, although the id is the same. The complete
packages in ``packages/`` are the result; this set is a copy for one reader.

The contract does not let more be left out. The terrain patches stay because the request
names them, a per-height array cannot hold one height only, the series cannot hold every
third sample, and a window needs its UTC intervals. See ``validation/README.md``.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import shutil
from pathlib import Path

from lsncore.contract import validate_document, validate_package
from lsncore.contract.io import compute_content_sha256, write_json

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "packages"
OUT = REPO / "build" / "packages_web"

# Optional arrays of a site package that no file of the web code names: where they are in the
# manifest and their keys. A test checks both, against the contract schema and against web/.
LEFT_OUT = {
    "horizon": ("obstacle_height_m", "obstacle_lat_deg", "obstacle_lon_deg", "obstacle_height_error_m", "obstacle_constrained"),
    "series": ("angular_radius_deg", "ellipse_visible_share"),
}
# Optional arrays the web view does not fetch but looks for (web/viewer/js/viewer.js, missingForGroundView):
# without them its ground view lists them as not contained in the package. Left out only with --smaller.
CHECKED_FOR = {"horizon": (), "series": ("blocker_azimuth_index", "lit_fraction")}
# The arrays the web view fetches for one site and one observer height (web/viewer/js/panel.js).
READ_BY_THE_VIEWER = {"horizon": ("elevation_deg", "distance_m"), "series": ("azimuth_deg", "elevation_deg", "margin_deg", "visible_fraction")}

NOTE = (
    "web subset: this copy leaves out arrays the web view does not use ({what}); every other value is that of the complete package "
    "{package_id} with content_sha256 {content_sha256}, published in packages/"
)


def left_out(smaller: bool = False) -> dict:
    """The keys of the arrays that are left out, by place in the manifest."""
    return {place: LEFT_OUT[place] + (CHECKED_FOR[place] if smaller else ()) for place in LEFT_OUT}


def thin_manifest(manifest: dict, smaller: bool = False) -> tuple[dict, list]:
    """The manifest of a web-set site package and the array files that are left out."""
    thin = copy.deepcopy(manifest)
    keys = left_out(smaller)
    removed, names = [], []
    for key in keys["horizon"]:
        if key in thin["horizon"]:
            removed.append(thin["horizon"].pop(key)["file"])
            names.append(f"horizon.{key}")
    for body, series in thin.get("timeline", {}).get("series", {}).items():
        for key in keys["series"]:
            if key in series:
                removed.append(series.pop(key)["file"])
                names.append(f"series.{body}.{key}")
    # A method card must be referred to by a number: a card that only left-out arrays referred to goes with them.
    used = _method_ids({key: value for key, value in thin.items() if key != "methods"})
    thin["methods"] = {method_id: card for method_id, card in thin["methods"].items() if method_id in used}
    thin["warnings"] = list(manifest["warnings"]) + [NOTE.format(what=", ".join(names), package_id=manifest["package_id"], content_sha256=manifest["content_sha256"])]
    thin["content_sha256"] = compute_content_sha256(thin)
    return thin, removed


def _method_ids(node) -> set:
    """Every method id a manifest refers to."""
    if isinstance(node, dict):
        own = {node["method"]} if isinstance(node.get("method"), str) else set()
        return own.union(*(_method_ids(value) for value in node.values())) if node else own
    if isinstance(node, list):
        return set().union(*(_method_ids(value) for value in node)) if node else set()
    return set()


def _array_files(node) -> list:
    if isinstance(node, dict):
        own = [node["file"]] if {"file", "dtype", "shape", "sha256"} <= node.keys() else []
        return own + [name for value in node.values() for name in _array_files(value)]
    if isinstance(node, list):
        return [name for value in node for name in _array_files(value)]
    return []


def first_load(root: Path, entry: dict) -> dict:
    """What the viewer fetches to show one site at one observer height: the index, the manifest and the arrays it reads.

    ``bytes`` is the size of these files. ``bytes_json_gzip`` is the same with the two JSON files compressed by
    gzip (level 6), as a host that compresses JSON on the way sends them; the arrays are counted as they are.
    """
    folder = root / entry["path"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    files = [manifest["horizon"][key]["file"] for key in READ_BY_THE_VIEWER["horizon"] if key in manifest["horizon"]]
    for series in manifest["timeline"]["series"].values():
        files += [series[key]["file"] for key in READ_BY_THE_VIEWER["series"]]
    documents = [(root / "index.json").read_bytes(), (folder / "manifest.json").read_bytes()]
    arrays = sum((folder / name).stat().st_size for name in files)
    return {
        "bytes": sum(len(document) for document in documents) + arrays,
        "bytes_json_gzip": sum(len(gzip.compress(document, 6, mtime=0)) for document in documents) + arrays,
    }


def transfer_bytes(root: Path) -> dict:
    """Size of a package root: as files, and as a host sends it that compresses the JSON files or every file.

    Compression is gzip at level 6. Whether a host compresses the array files depends on the host; the files on
    disk are the same in every case.
    """
    plain = json_only = everything = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "README.md":
            continue
        data = path.read_bytes()
        packed = len(gzip.compress(data, 6, mtime=0))
        plain += len(data)
        everything += packed
        json_only += packed if path.suffix == ".json" else len(data)
    return {"bytes": plain, "json_gzip_bytes": json_only, "all_gzip_bytes": everything}


def build(source: Path = SOURCE, out: Path = OUT, smaller: bool = False) -> dict:
    """Write the web set from the published set. Returns what was written, in bytes."""
    index = json.loads((source / "index.json").read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    entries, sizes = [], {"smaller": smaller, "sites": {}, "left_out_bytes": 0, "direction_table_bytes": 0}
    for entry in index["packages"]:
        folder = source / entry["path"]
        if entry["kind"] == "direction_table":
            sizes["direction_table_bytes"] += sum(f.stat().st_size for f in folder.iterdir())
            continue
        target = out / entry["path"]
        target.mkdir(parents=True)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if entry["kind"] == "site":
            thin, removed = thin_manifest(manifest, smaller)
            write_json(target / "manifest.json", thin, compact=True)
            sizes["left_out_bytes"] += sum((folder / name).stat().st_size for name in removed)
        else:
            thin = manifest
            shutil.copyfile(folder / "manifest.json", target / "manifest.json")
        for name in _array_files(thin):
            shutil.copyfile(folder / name, target / name)
        validate_package(target)
        if entry["kind"] == "site":
            sizes["sites"][entry["site_id"]] = {"full_bytes": sum(f.stat().st_size for f in folder.iterdir()), "web_bytes": sum(f.stat().st_size for f in target.iterdir())}
        entries.append(entry)
    # The index of the web set is the published index without the direction table; it keeps its time stamp, so
    # that the same published set always gives the same bytes.
    web_index = {**index, "packages": entries}
    validate_document(web_index)
    write_json(out / "index.json", web_index, compact=True)
    sizes["full_total_bytes"] = sum(f.stat().st_size for f in source.rglob("*") if f.is_file() and f.name != "README.md")
    sizes["web_total_bytes"] = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    site_entries = [entry for entry in entries if entry["kind"] == "site"]
    largest = max(site_entries, key=lambda entry: sizes["sites"][entry["site_id"]]["full_bytes"])
    sizes["first_load"] = {
        label: {"site_id": entry["site_id"], "full": first_load(source, entry), "web": first_load(out, entry)}
        for label, entry in (("first site of the index", site_entries[0]), ("largest site", largest))
    }
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(SOURCE), help="published package root (default: packages)")
    parser.add_argument("--out", default=str(OUT), help="package root of the web set (default: build/packages_web, not under version control)")
    parser.add_argument("--smaller", action="store_true", help="also leave out the arrays the ground view of the web view looks for but does not fetch (it then says they are not in the package)")
    parser.add_argument("--transfer", action="store_true", help="also print the size of both sets as a host sends them that compresses with gzip")
    args = parser.parse_args()
    sizes = build(Path(args.source), Path(args.out), args.smaller)
    mb = lambda value: f"{value / 1e6:.1f} MB"
    keys = left_out(args.smaller)
    print(f"web set: {len(sizes['sites'])} site packages and the pairs package -> {args.out}")
    print(f"left out: {', '.join(keys['horizon'] + keys['series'])}; the direction table")
    print(f"published set {sizes['full_total_bytes']} bytes ({mb(sizes['full_total_bytes'])}); web set {sizes['web_total_bytes']} bytes ({mb(sizes['web_total_bytes'])}); "
          f"arrays left out {mb(sizes['left_out_bytes'])}; direction table left out {mb(sizes['direction_table_bytes'])}")
    for label, row in sizes["first_load"].items():
        print(f"first load, {label} ({row['site_id']}): {row['full']['bytes']} bytes from the published set, {row['web']['bytes']} bytes from the web set; "
              f"with JSON compressed by the host: {row['full']['bytes_json_gzip']} and {row['web']['bytes_json_gzip']} bytes")
    if args.transfer:
        for label, root in (("published set", Path(args.source)), ("web set", Path(args.out))):
            sent = transfer_bytes(root)
            print(f"{label}: {sent['bytes']} bytes as files; {sent['json_gzip_bytes']} bytes sent if the host compresses JSON only; {sent['all_gzip_bytes']} bytes if it compresses every file")


if __name__ == "__main__":
    main()
