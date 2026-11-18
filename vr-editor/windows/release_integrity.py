"""Offline release inventory for the unsigned, review-only Windows desktop preview.

A SHA256 inventory detects accidental changes between packaging and verification.
It is NOT a signature or a trusted release attestation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

MAX_FILES = 20000
MAX_FILE_BYTES = 512 * 1024 * 1024
FORBIDDEN = {".pdf", ".pfx", ".p12", ".pem", ".key", ".env", ".sqlite", ".db"}
REQUIRED = {"PlanReaderDesktop.exe", "web/index.html"}


def inventory(root: Path):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("not a directory")
    entries = []
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            if (Path(base) / name).is_symlink():
                raise ValueError("symlink forbidden")
        for name in names:
            path = Path(base) / name
            rel = path.relative_to(root).as_posix()
            if path.suffix.lower() in FORBIDDEN or name.lower().startswith(".env"):
                raise ValueError("private/source-like file forbidden: " + rel)
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("invalid/oversized file: " + rel)
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": h.hexdigest()})
            if len(entries) > MAX_FILES:
                raise ValueError("file count exceeded")
    entries.sort(key=lambda x: x["path"])
    if not REQUIRED.issubset({e["path"] for e in entries}):
        raise ValueError("desktop executable or web index missing")
    return {"schema": 1, "release_type": "unsigned-review-only", "files": entries}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["create", "verify"])
    p.add_argument("root", type=Path)
    p.add_argument("manifest", type=Path)
    args = p.parse_args()
    # Manifest must live outside the packaged tree to avoid self-reference.
    root = args.root.resolve(strict=True)
    manifest = args.manifest.resolve()
    if manifest == root or root in manifest.parents:
        p.error("manifest must be outside package root")
    actual = inventory(root)
    if args.mode == "create":
        args.manifest.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        expected = json.loads(args.manifest.read_text(encoding="utf-8"))
        if expected != actual:
            p.error("release inventory mismatch")
    print(f"{args.mode}: {len(actual['files'])} files checked; unsigned, not authenticated")


if __name__ == "__main__":
    main()
