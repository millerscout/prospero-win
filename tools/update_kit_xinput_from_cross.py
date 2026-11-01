#!/usr/bin/env python3
"""Graft xinput cross-build artifacts onto a copy of official Playden kit 0.17.

Replaces ntdll.prx, xinput1_3.prx, xinput PE modules in the runtime and template,
and optionally the any-title shell eboot.bin.  Rewrites manifest.json hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PREFIX = "runtime/wine-wow64/3926b27-kit-0.17/lib/wine"
TEMPLATE_SYS32 = "template/bottle/drive_c/windows/system32"
TEMPLATE_SYSWOW64 = "template/bottle/drive_c/windows/syswow64"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path, mode: int) -> dict:
    data = path.read_bytes()
    return {
        "path": None,  # filled by caller
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mode": oct(mode)[2:].zfill(4),
    }


def files_digest(entries: list[dict]) -> str:
    lines = [
        f"{e['path']}\t{e['size']}\t{e['sha256']}\t{e['mode']}\n" for e in entries
    ]
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def refresh_runtime_inventory(out_kit: Path, manifest: dict) -> None:
    """Rewrite runtime-inventory.json and manifest entries after grafting PE/PRX."""
    runtime_rel = manifest["runtime"]["path"]
    runtime_root = out_kit / runtime_rel
    bundle_id = manifest["runtime"]["bundle_id"]
    artifact_revision = manifest["runtime"]["artifact_revision"]
    inventory_rel = f"runtime/{bundle_id}/{artifact_revision}/runtime-inventory.json"
    manifest["runtime"]["inventory_manifest"] = inventory_rel

    inventory: dict[str, str] = {}
    for path in sorted(runtime_root.rglob("*")):
        if not path.is_file() or path.name == "runtime-inventory.json":
            continue
        rel = path.relative_to(runtime_root).as_posix()
        inventory[rel] = sha256(path)

    inv_path = out_kit / inventory_rel
    inv_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inv_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    mode = inv_path.stat().st_mode & 0o7777
    entry = file_entry(inv_path, mode)
    entry["path"] = inventory_rel
    path_to_entry = {e["path"]: e for e in manifest["files"]}
    if inventory_rel in path_to_entry:
        path_to_entry[inventory_rel].update(entry)
    else:
        manifest["files"].append(entry)


def copy_mode(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    mode = src.stat().st_mode
    if dst.suffix == ".prx":
        mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    dst.chmod(mode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-kit", type=Path, required=True, help="unpacked playden-kit dir")
    parser.add_argument("--out", type=Path, required=True, help="output kit directory")
    parser.add_argument(
        "--cross",
        type=Path,
        default=ROOT / ".deps/wine-ps5",
        help="build_wine_ps5 work directory",
    )
    parser.add_argument(
        "--title-eboot",
        type=Path,
        default=None,
        help="optional rebuilt any-title eboot.bin",
    )
    parser.add_argument(
        "--artifact-revision",
        default="6d2a7c6-kit-xinput-dev1",
        help="runtime artifact_revision written into manifest",
    )
    args = parser.parse_args()

    src_kit = args.from_kit.resolve()
    out_kit = args.out.resolve()
    cross = args.cross.resolve()
    prx = cross / "prx/sce_module"
    pe_i386 = cross / "pe/i386-windows"
    pe_amd64 = cross / "pe/x86_64-windows"

    if out_kit.exists():
        raise SystemExit(f"refusing to overwrite existing {out_kit}")
    shutil.copytree(src_kit, out_kit)

    manifest_path = out_kit / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    rel_paths: dict[str, Path] = {}

    def stage(rel: str, src: Path) -> None:
        dst = out_kit / rel
        copy_mode(src, dst)
        rel_paths[rel] = dst

    stage(f"{RUNTIME_PREFIX}/x86_64-unix/ntdll.prx", prx / "ntdll.prx")
    stage(f"{RUNTIME_PREFIX}/x86_64-unix/xinput1_3.prx", prx / "xinput1_3.prx")

    xinput_pe = (
        "xinput1_1.dll",
        "xinput1_2.dll",
        "xinput1_3.dll",
        "xinput1_4.dll",
        "xinputuap.dll",
        "xinput9_1_0.dll",
        "winexinput.sys",
    )
    for name in xinput_pe:
        if (pe_i386 / name).is_file():
            stage(f"{RUNTIME_PREFIX}/i386-windows/{name}", pe_i386 / name)
        if (pe_amd64 / name).is_file():
            stage(f"{RUNTIME_PREFIX}/x86_64-windows/{name}", pe_amd64 / name)
        if name.endswith(".dll"):
            if (pe_i386 / name).is_file():
                stage(f"{TEMPLATE_SYSWOW64}/{name}", pe_i386 / name)
            if (pe_amd64 / name).is_file():
                stage(f"{TEMPLATE_SYS32}/{name}", pe_amd64 / name)

    title_rel = manifest["variants"][0]["path"]
    if args.title_eboot:
        stage(f"{title_rel}/eboot.bin", args.title_eboot.resolve())

    path_to_entry = {e["path"]: e for e in manifest["files"]}
    for rel, path in rel_paths.items():
        mode = path.stat().st_mode & 0o7777
        entry = file_entry(path, mode)
        entry["path"] = rel
        if rel in path_to_entry:
            path_to_entry[rel].update(entry)
        else:
            manifest["files"].append(entry)
            path_to_entry[rel] = entry

    manifest["files"].sort(key=lambda e: e["path"])
    manifest["runtime"]["artifact_revision"] = args.artifact_revision
    manifest["runtime"]["path"] = f"runtime/wine-wow64/{args.artifact_revision}"
    old_runtime = f"runtime/wine-wow64/3926b27-kit-0.17"
    new_runtime = manifest["runtime"]["path"]
    if old_runtime != new_runtime:
        new_files = []
        for entry in manifest["files"]:
            if entry["path"].startswith(old_runtime + "/"):
                entry = dict(entry)
                entry["path"] = new_runtime + entry["path"][len(old_runtime) :]
            new_files.append(entry)
        manifest["files"] = new_files
        runtime_dir = out_kit / new_runtime
        runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out_kit / old_runtime), str(runtime_dir))

    refresh_runtime_inventory(out_kit, manifest)
    manifest["files"].sort(key=lambda e: e["path"])
    manifest["files_sha256"] = files_digest(manifest["files"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n")
    print(f"kit written to {out_kit}")
    print(f"artifact_revision={args.artifact_revision}")
    print(f"files_sha256={manifest['files_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
