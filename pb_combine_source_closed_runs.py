"""CLI for verified composition of benchmark-neutral sealed production runs."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Iterable

from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    combine_source_closed_runs,
    sealed_source_closed_run_from_dict,
)


def _no_duplicate_source_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Do not allow a later JSON object field to replace a signed receipt."""
    found: dict[str, object] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError(f"duplicate sealed JSON key: {key}")
        found[key] = value
    return found


def _no_nonfinite_source_constant(token: str) -> None:
    raise ValueError(f"non-finite sealed JSON number: {token}")


def _finite_sealed_json_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("out-of-range sealed JSON float")
    return value


def _finite_sealed_json_int(token: str) -> int:
    value = int(token)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("out-of-range sealed JSON integer")
    return value


def _reject_excessive_sealed_json_nesting(payload: str) -> None:
    # This is a parser complexity bound, not source evidence inference. Quoted
    # and escaped '[' or '{' text cannot inflate structural nesting depth.
    depth = 0
    inside_string = False
    escaped = False
    for character in payload:
        if inside_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                inside_string = False
        elif character == '"':
            inside_string = True
        elif character in "[{":
            depth += 1
            if depth > 512:
                raise ValueError("sealed JSON nesting exceeds safe parser depth")
        elif character in "]}":
            depth -= 1


def load_verified_sealed_run(path: Path | str) -> SealedSourceClosedRun:
    source = Path(path)
    source_text = source.read_text(encoding="utf-8")
    _reject_excessive_sealed_json_nesting(source_text)
    try:
        payload = json.loads(
            source_text,
            object_pairs_hook=_no_duplicate_source_keys,
            parse_constant=_no_nonfinite_source_constant,
            parse_float=_finite_sealed_json_float,
            parse_int=_finite_sealed_json_int,
        )
    except RecursionError as exc:
        raise ValueError("sealed JSON nesting exceeds safe parser depth") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"{source} must contain a JSON object")
    return sealed_source_closed_run_from_dict(payload)


def combine_sealed_run_files(
    input_paths: Iterable[Path | str],
    *,
    project_id: str | None = None,
) -> SealedSourceClosedRun:
    paths = tuple(Path(path) for path in input_paths)
    if not paths:
        raise ValueError("at least one sealed-run input file is required")
    runs = tuple(load_verified_sealed_run(path) for path in paths)
    return combine_source_closed_runs(runs, project_id=project_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify and combine independent benchmark-neutral source-closed "
            "production runs into one deterministic project run."
        )
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Optional exact project id. Defaults to the first verified input run.",
    )
    parser.add_argument(
        "--input",
        dest="inputs",
        action="append",
        type=Path,
        required=True,
        help="Verified sealed-run JSON input. Repeat for each production family.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    # Source-closed family receipts are immutable inputs, not disposable CLI
    # scratch files. Resolve aliases/symlinks before composition so a caller
    # cannot silently replace one authenticated producer run with its aggregate.
    output_identity = args.output.resolve()
    if any(output_identity == source.resolve() for source in args.inputs):
        raise ValueError("combined output must not overwrite a sealed source input")

    combined = combine_sealed_run_files(
        args.inputs,
        project_id=args.project_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete verified aggregate. A failed serialization,
    # filesystem write or rename must not truncate a previous sealed result.
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent,
            prefix=f".{args.output.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(combined.to_json())
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, args.output)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
