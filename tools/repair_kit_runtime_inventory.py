#!/usr/bin/env python3
"""Fix runtime inventory_manifest + hashes on an already-staged xinput dev kit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from update_kit_xinput_from_cross import files_digest, refresh_runtime_inventory  # noqa: E402


def main() -> int:
    kit = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / ".deps/playden-kit-xinput-dev/playden-kit")
    manifest_path = kit / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    refresh_runtime_inventory(kit, manifest)
    manifest["files"].sort(key=lambda e: e["path"])
    manifest["files_sha256"] = files_digest(manifest["files"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"inventory_manifest={manifest['runtime']['inventory_manifest']}")
    print(f"files_sha256={manifest['files_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
