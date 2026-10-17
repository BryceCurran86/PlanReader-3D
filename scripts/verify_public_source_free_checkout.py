"""Validate PUBLIC Git archive contains benchmark CODE only, not client sources.

Never package the ten original source PDFs, private keys, or .env credentials
as downloadable artifacts. Frozen source manifests are permitted metadata.
No original source bytes or benchmark scoring is performed by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from scripts.check_private_original_source_additions import (
    blocked_source_additions,
)

BENCHMARK = "benchmarks/frozen_holdout/full_plan_v2"
PROJECTS = (
    "au_qld_lot16_power",
    "au_qld_3laurel",
    "au_qld_maryborough_service_station",
    "au_qld_q5446_armstrong32_harlequin",
)
MASTER = f"{BENCHMARK}/manifest.json"


def verify_source_free_public_archive(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError("source-free checkout archive is missing")
    names: set[str] = set()
    content_sha256s: dict[str, str] = {}
    raw_manifests: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./").rstrip("/")
            if not name:
                continue
            if member.issym() or member.islnk():
                raise ValueError("public checkout must not contain symbolic or hard links")
            if not member.isfile() and not member.isdir():
                raise ValueError("public checkout has an unsupported member type")
            if member.isfile():
                if name in names:
                    raise ValueError("duplicate tracked archive member: " + name)
                names.add(name)
                payload = archive.extractfile(member)
                if payload is None:
                    raise ValueError("unreadable tracked code archive member")
                digest = hashlib.sha256()
                metadata_chunks = [] if (name == MASTER or name.endswith("/source_manifest.json")) else None
                while True:
                    chunk = payload.read(1 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
                    if metadata_chunks is not None:
                        metadata_chunks.append(chunk)
                content_sha256s[name] = digest.hexdigest()
                if metadata_chunks is not None:
                    raw_manifests[name] = b"".join(metadata_chunks)
    if blocked_source_additions(tuple(names)):
        raise ValueError("public checkout includes forbidden original/credential path")
    if MASTER not in names:
        raise ValueError("public checkout lacks frozen Full Plan V2 suite manifest")
    expected_manifest_names = {
        f"{BENCHMARK}/projects/{p}/source_manifest.json" for p in PROJECTS
    }
    if not expected_manifest_names.issubset(names):
        raise ValueError("public checkout lacks original source SHA manifests")
    try:
        suite = json.loads(raw_manifests[MASTER])
        if suite["benchmark_id"] != "full_plan_takeoff_reconciliation_v2":
            raise ValueError("wrong frozen benchmark ID")
        if tuple(suite["projects"]) != PROJECTS:
            raise ValueError("wrong frozen project membership")
        source_names = []
        original_source_hashes = set()
        for project in PROJECTS:
            source_file = f"{BENCHMARK}/projects/{project}/source_manifest.json"
            manifest = json.loads(raw_manifests[source_file])
            if manifest["project_id"] != project:
                raise ValueError("mismatched frozen source manifest project")
            for d in manifest["source_documents"]:
                sha = d["sha256"]
                if (not isinstance(sha, str) or len(sha) != 64
                        or not all(c in "0123456789abcdef" for c in sha)):
                    raise ValueError("invalid original source SHA declaration")
                source_names.append(d["name"].casefold())
                original_source_hashes.add(sha)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid frozen source metadata") from exc
    if len(source_names) != 10 or len(set(source_names)) != 10:
        raise ValueError("frozen original source package must have ten distinct PDFs")
    if any(name.rsplit("/", 1)[-1].casefold() in source_names for name in names):
        raise ValueError("public archive contains original client filename")
    if any(sha in original_source_hashes for sha in content_sha256s.values()):
        raise ValueError("public archive contains original client PDF bytes under another name")
    return {
        "status": "CODE_ONLY_SOURCE_FREE",
        "benchmark_id": "full_plan_takeoff_reconciliation_v2",
        "project_count": 4,
        "frozen_original_source_document_count": 10,
        "original_pdf_bytes_in_archive": False,
        "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "archived_tracked_file_count": len(names),
        "benchmark_accuracy": None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    proof = verify_source_free_public_archive(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, sort_keys=True, indent=2)+"\n")
    print("PUBLIC CHECKOUT SOURCE-FREE VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
