"""Finalize split source-closed project handoffs into one verified project run.

This is a benchmark-neutral convenience layer over the strict sealed-run loader
and combiner. It discovers the standard <project>.core.json and
<project>.surfaces.json files, verifies every present run, combines the
available groups deterministically, and emits <project>.json plus a small
handoff summary.

Missing groups are reported, not manufactured. No benchmark truth, expected
quantities, tolerances, identity maps, or scoring logic are read here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pb_combine_source_closed_runs import combine_sealed_run_files


GROUPS = ("core", "surfaces")


def _receipt_sha256(path: Path) -> str:
    """Read source-signed JSON bytes without parsing gold or trusting mtime."""
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_complete(path: Path, contents: str) -> None:
    """Write full verified output before publishing the final pathname."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as writer:
            temporary = Path(writer.name)
            writer.write(contents)
            writer.flush()
            os.fsync(writer.fileno())
        # The caller holds a per-output-directory exclusive finalizer lock.
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"existing final customer artifact: {path}")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def finalize_split_project_handoff(
    *,
    project_id: str,
    input_dir: Path | str,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    if type(project_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", project_id):
        raise ValueError("project_id must be a single canonical filename-safe token")
    clean_project_id = project_id

    source_dir = Path(input_dir)
    target_dir = Path(output_dir) if output_dir is not None else source_dir

    available: list[tuple[str, Path]] = []
    missing: list[str] = []
    for group in GROUPS:
        path = source_dir / f"{clean_project_id}.{group}.json"
        if path.is_file():
            available.append((group, path))
        else:
            missing.append(group)

    if not available:
        raise FileNotFoundError(
            f"no split sealed runs found for project {clean_project_id!r}"
        )

    # A producer receipt is an immutable signed source input. If it is
    # replaced while finalizing, never publish an aggregate from mixed bytes.
    input_hashes = {group: _receipt_sha256(path) for group, path in available}
    combined = combine_sealed_run_files(
        [path for _, path in available],
        project_id=clean_project_id,
    )
    if any(_receipt_sha256(path) != input_hashes[group] for group, path in available):
        raise ValueError("signed source group changed during finalization")
    # Reusing a finalizer destination must never mutate an earlier sealed
    # customer run or source group. A symlinked directory can redirect signed
    # output to another workspace without a visible filename collision.
    if target_dir.is_symlink():
        raise FileExistsError("finalized customer directory cannot be a symlink")
    output_path = target_dir / f"{clean_project_id}.json"
    summary_path = target_dir / f"{clean_project_id}.handoff-summary.json"
    if any(path.exists() or path.is_symlink() for path in (output_path, summary_path)):
        raise FileExistsError("existing finalized customer run: use a new output directory")

    summary = {
        "schema_version": "1.0.0",
        "project_id": clean_project_id,
        "available_groups": [group for group, _ in available],
        "missing_groups": missing,
        "complete_group_set": not missing,
        # Signed group availability does not prove four-project frozen V2
        # reconciliation or a benchmark accuracy numerator.
        "publication_status": (
            "SOURCE_GROUPS_SEALED_BENCHMARK_UNPUBLISHED"
            if not missing else "PARTIAL_GROUPS_SEALED_BENCHMARK_UNPUBLISHED"
        ),
        "benchmark_score_granted": False,
        "frozen_v2_reconciliation_complete": False,
        "input_files": {group: str(path) for group, path in available},
        "output_file": str(output_path),
        "run_id": combined.run_id,
        "source_sha256s": list(combined.source_sha256s),
        "revision_ids": list(combined.revision_ids),
        "quantity_count": len(combined.quantities),
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    lock = target_dir / ".source_closed_finalizer.lock"
    # Per-folder O_EXCL rejects overlapping finalizers or crash-stale locks;
    # a crash never grants permission to overwrite the previous sealed run.
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if any(path.exists() or path.is_symlink() for path in (output_path, summary_path)):
            raise FileExistsError("existing finalized customer run: use a new output directory")
        _atomic_write_complete(output_path, combined.to_json())
        _atomic_write_complete(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify and finalize core/surfaces source-closed project handoffs "
            "into the exact <project_id>.json shape consumed by V2 scoring."
        )
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = finalize_split_project_handoff(
        project_id=args.project_id,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
