"""Activate pre-certified identities, then run the unchanged exact V2 reconciler.

The activation step must succeed first. This tool never invents a binding and
never bypasses the existing exact project reconciler. It is intended for the
next genuinely new source-sealed quantity after GPT3 has independently
pre-certified the physical->frozen identity.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

from tools.prepare_gpt3_pending_identity_activation import build_activation
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _read_json_without_duplicate_keys,
)


def _object(path: Path) -> dict[str, Any]:
    value = _read_json_without_duplicate_keys(path)
    if type(value) is not dict:
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _rows(path: Path) -> list[dict[str, Any]]:
    value = _read_json_without_duplicate_keys(path)
    if type(value) is not list or any(
        type(row) is not dict for row in value
    ):
        raise TypeError(f"{path} must contain an array of objects")
    return value


def _exact_report_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks/frozen_holdout/full_plan_v2"
        / "run_exact_project_reconciliation.py"
    )
    name = "_planreader_gpt3_guarded_exact_project_report"
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exact project reconciliation runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_guarded_exact_report(
    *,
    pending_ledger: Mapping[str, Any],
    sealed_run_payload: Mapping[str, Any],
    customer_rows: list[Mapping[str, Any]],
    active_identity_map_payload: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    source_identity_proof: Mapping[str, Any],
    object_universe: Mapping[str, Any],
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    # The caller-supplied manifest object and path must identify the same
    # immutable frozen project manifest. Otherwise activation could authorize
    # a fabricated item against one inventory and score against another.
    project_id = sealed_run_payload.get("project_id")
    if type(project_id) is not str or not project_id or "/" in project_id:
        raise ValueError("invalid guarded reconciliation project ID")
    canonical_manifest = (
        Path(__file__).resolve().parents[1]
        / "benchmarks/frozen_holdout/full_plan_v2/projects"
        / project_id
        / "source_manifest.json"
    )
    if manifest_path.resolve() != canonical_manifest.resolve():
        raise ValueError("guarded reconciliation requires canonical frozen manifest")
    frozen_manifest = _object(canonical_manifest)
    if dict(source_manifest) != frozen_manifest:
        raise ValueError("guarded reconciliation manifest payload differs from frozen manifest")

    candidate_map, activation_receipt = build_activation(
        pending_ledger=pending_ledger,
        sealed_run_payload=sealed_run_payload,
        customer_rows=customer_rows,
        active_identity_map_payload=active_identity_map_payload,
        source_manifest=source_manifest,
        source_identity_proof=source_identity_proof,
        object_universe=object_universe,
    )
    if activation_receipt.get("activated_count", 0) < 1:
        raise ValueError("guarded reconciliation requires a real activation")
    if activation_receipt.get("benchmark_score_granted") is not False:
        raise ValueError("activation step must not grant a benchmark score")
    if activation_receipt.get("evaluator_invoked") is not False:
        raise ValueError("activation step unexpectedly invoked evaluator")

    exact = _exact_report_module()
    with tempfile.TemporaryDirectory(
        prefix="planreader-gpt3-guarded-reconcile-"
    ) as temp:
        root = Path(temp)
        sealed_path = root / "sealed.json"
        map_path = root / "identity-map.json"
        sealed_path.write_text(
            json.dumps(sealed_run_payload, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        map_path.write_text(
            json.dumps(candidate_map, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = exact.build_exact_project_report(
            manifest_path=manifest_path,
            sealed_run_path=sealed_path,
            identity_map_path=map_path,
        )

    if report.get("reconciliation_complete") is not True:
        raise ValueError("exact project reconciliation did not complete")
    if report.get("project_id") != activation_receipt.get("project_id"):
        raise ValueError("activation/reconciliation project mismatch")
    if report.get("sealed_run_id") != activation_receipt.get("sealed_run_id"):
        raise ValueError("activation/reconciliation sealed run mismatch")
    if (
        report.get("sealed_run_fingerprint")
        != activation_receipt.get("sealed_run_fingerprint")
    ):
        raise ValueError(
            "activation/reconciliation sealed fingerprint mismatch"
        )
    return candidate_map, activation_receipt, report


def _preflight_outputs(
    outputs: tuple[Path, Path, Path], inputs: tuple[Path, ...],
) -> None:
    """Refuse all collisions before reading or scoring signed data."""
    resolved = [path.resolve() for path in outputs]
    sources = {source.resolve() for source in inputs}
    if len(set(resolved)) != 3:
        raise ValueError("three guarded reconciliation output paths must be distinct")
    frozen = FROZEN_ROOT.resolve()
    for path, destination in zip(outputs, resolved):
        if path.exists() or path.is_symlink():
            raise FileExistsError("guarded reconciliation output must be new, never overwrite")
        if destination in sources or destination == frozen or destination.is_relative_to(frozen):
            raise ValueError("guarded reconciliation cannot output over source or frozen evidence")


def _write_triplet(
    outputs: tuple[Path, Path, Path], payloads: tuple[object, object, object],
    *, inputs: tuple[Path, ...],
) -> None:
    """Stage all three files then publish exclusively, with rollback on failure."""
    _preflight_outputs(outputs, inputs)
    staged: list[Path] = []
    created: list[Path] = []
    try:
        for path, value in zip(outputs, payloads):
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, encoding="utf-8", newline="",
                prefix=".gpt3-activation-", suffix=".tmp", delete=False,
            ) as out:
                temp = Path(out.name)
                staged.append(temp)
                out.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
                out.flush()
                os.fsync(out.fileno())
        # An atomic create-only hard link will fail if any external writer
        # creates the destination since preflight. Do not replace originals.
        for path, temp in zip(outputs, staged):
            os.link(temp, path)
            created.append(path)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        for temp in staged:
            temp.unlink(missing_ok=True)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-ledger", type=Path, required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customer-rows", type=Path, required=True)
    parser.add_argument("--active-identity-map", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-identity-proof", type=Path, required=True)
    parser.add_argument("--object-universe", type=Path, required=True)
    parser.add_argument("--output-map", type=Path, required=True)
    parser.add_argument(
        "--output-activation-receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args(argv)

    inputs = (
        args.pending_ledger, args.sealed_run, args.customer_rows,
        args.active_identity_map, args.manifest, args.source_identity_proof,
        args.object_universe,
    )
    outputs = (args.output_map, args.output_activation_receipt, args.output_report)
    _preflight_outputs(outputs, inputs)
    manifest = _object(args.manifest)
    candidate_map, activation, report = build_guarded_exact_report(
        pending_ledger=_object(args.pending_ledger),
        sealed_run_payload=_object(args.sealed_run),
        customer_rows=_rows(args.customer_rows),
        active_identity_map_payload=_object(args.active_identity_map),
        source_manifest=manifest,
        source_identity_proof=_object(args.source_identity_proof),
        object_universe=_object(args.object_universe),
        manifest_path=args.manifest,
    )
    _write_triplet(outputs, (candidate_map, activation, report), inputs=inputs)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
