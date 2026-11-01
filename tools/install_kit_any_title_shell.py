#!/usr/bin/env python3
"""Install a freshly built any-title dist tree into a staged kit + fix manifest."""
from __future__ import annotations

import argparse
import json
import shutil
import stat
from pathlib import Path

from update_kit_xinput_from_cross import file_entry, files_digest, refresh_runtime_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True, help="dist/FAKE78000-* title folder")
    parser.add_argument("--wrapper-revision", required=True)
    args = parser.parse_args()

    kit = args.kit.resolve()
    dist = args.dist.resolve()
    manifest_path = kit / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    variant = manifest["variants"][0]
    title_rel = variant["path"]
    title_dir = kit / title_rel

    for name in ("eboot.bin", "native-title-build.json"):
        src = dist / name
        dst = title_dir / name
        shutil.copy2(src, dst)
        if name == "eboot.bin":
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    manifest["sources"]["wrapper"]["revision"] = args.wrapper_revision
    variant["wrapper_revision"] = args.wrapper_revision

    path_to_entry = {e["path"]: e for e in manifest["files"]}
    for name in ("eboot.bin", "native-title-build.json"):
        rel = f"{title_rel}/{name}"
        path = title_dir / name
        mode = path.stat().st_mode & 0o7777
        entry = file_entry(path, mode)
        entry["path"] = rel
        path_to_entry[rel].update(entry)

    refresh_runtime_inventory(kit, manifest)
    manifest["files"].sort(key=lambda e: e["path"])
    manifest["files_sha256"] = files_digest(manifest["files"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"title eboot sha256={path_to_entry[f'{title_rel}/eboot.bin']['sha256']}")
    print(f"wrapper_revision={args.wrapper_revision}")
    print(f"files_sha256={manifest['files_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
