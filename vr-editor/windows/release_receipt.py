"""Offline unsigned-preview checksum receipt; NOT a trusted release attestation."""
import argparse
import hashlib
import json
from pathlib import Path

INSTALLER_NAME = "PlanReader-VR-Desktop-Preview-Setup.exe"

def checked(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("invalid, missing, oversized or symlinked release input")
    return path

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def receipt(installer, inventory):
    installer = checked(installer, 2 * 1024**3)
    inventory = checked(inventory, 4 * 1024**2)
    if installer.name != INSTALLER_NAME:
        raise ValueError("unexpected installer filename")
    data = json.loads(inventory.read_text(encoding="utf-8"))
    if type(data) is not dict or set(data) != {"schema", "release_type", "files"}:
        raise ValueError("invalid inventory structure")
    if type(data["schema"]) is not int or data["schema"] != 1 or data["release_type"] != "unsigned-review-only":
        raise ValueError("inventory not unsigned preview")
    entries = data["files"]
    if type(entries) is not list or not 0 < len(entries) <= 20000:
        raise ValueError("invalid inventory entries")
    seen = set()
    for item in entries:
        if type(item) is not dict or set(item) != {"path", "bytes", "sha256"}:
            raise ValueError("invalid inventory entry")
        name, size, digest = item["path"], item["bytes"], item["sha256"]
        if type(name) is not str or not name or name.startswith("/") or "\\" in name or any(p in ("", ".", "..") for p in name.split("/")) or name in seen:
            raise ValueError("invalid or repeated inventory path")
        if type(size) is not int or not 0 <= size <= 512 * 1024**2:
            raise ValueError("invalid inventory size")
        if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid inventory digest")
        seen.add(name)
    if not {"PlanReaderDesktop.exe", "web/index.html"} <= seen:
        raise ValueError("missing required preview assets")
    return {"schema": 1, "channel": "unsigned-preview",
            "installer_sha256": sha256(installer), "inventory_sha256": sha256(inventory),
            "inventory_file_count": len(entries), "signed": False,
            "trusted_attestation": False, "hardware_verified": False,
            "unity_player_verified": False, "production_authorized": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("receipt output already exists; refusing overwrite")
    try:
        result = receipt(args.installer, args.inventory)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

if __name__ == "__main__":
    main()
