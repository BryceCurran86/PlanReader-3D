"""Activate pre-certified benchmark identities only from a newly verified sealed run.

This is benchmark-side integration. It never scores. It cryptographically
rehydrates the sealed source-closed run, verifies exact customer-row bijection,
revalidates each pending benchmark item/object relationship against the frozen
source manifest, then adds only pre-certified physical identities genuinely
present in that sealed run. Existing active bindings are preserved.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
# tests/benchmarks is also a top-level package named "benchmarks". Load the
# actual frozen full_plan_v2 package under a private alias, matching the
# repository's exact reconciliation runner, so pytest collection cannot resolve
# the wrong package.
_PACKAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/frozen_holdout/full_plan_v2"
)
_PACKAGE_NAME = "_planreader_full_plan_v2_pending_activation"
_PACKAGE_SPEC = importlib.util.spec_from_file_location(
    _PACKAGE_NAME,
    _PACKAGE_DIR / "__init__.py",
    submodule_search_locations=[str(_PACKAGE_DIR)],
)
assert _PACKAGE_SPEC is not None and _PACKAGE_SPEC.loader is not None
_PACKAGE = sys.modules.get(_PACKAGE_NAME)
if _PACKAGE is None:
    _PACKAGE = importlib.util.module_from_spec(_PACKAGE_SPEC)
    sys.modules[_PACKAGE_NAME] = _PACKAGE
    _PACKAGE_SPEC.loader.exec_module(_PACKAGE)
_RECONCILIATION = importlib.import_module(
    f"{_PACKAGE_NAME}.sealed_reconciliation"
)
identity_map_from_dict = _RECONCILIATION.identity_map_from_dict

SCHEMA_VERSION = "1.0.0"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(
        not isinstance(row, dict) for row in value
    ):
        raise TypeError(f"{path} must contain an array of objects")
    return value


def _pending_rows(
    ledger: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if ledger.get("status") == "IDENTITY_READY_QUANTITY_UNSEALED":
        rows = [{
            "physical_opening_id": ledger.get("physical_opening_id"),
            "benchmark_item_id": ledger.get("benchmark_item_id"),
            "benchmark_object_ref": ledger.get("benchmark_object_ref"),
            "status": ledger.get("status"),
        }]
    else:
        rows = ledger.get("pending_identities")
    if not isinstance(rows, list) or not rows:
        raise ValueError("pending identity ledger has no candidate rows")

    accepted = []
    seen_physical = set()
    seen_items = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("pending identity row must be a mapping")
        if row.get("status") != "IDENTITY_READY_QUANTITY_UNSEALED":
            raise ValueError("pending identity row is not pre-certified")
        physical = row.get("physical_opening_id")
        item = row.get("benchmark_item_id")
        object_ref = row.get("benchmark_object_ref")
        for name, value in (
            ("physical_opening_id", physical),
            ("benchmark_item_id", item),
            ("benchmark_object_ref", object_ref),
        ):
            if (
                type(value) is not str
                or not value
                or value != value.strip()
            ):
                raise ValueError(f"pending identity {name} is malformed")
        if physical in seen_physical or item in seen_items:
            raise ValueError(
                "pending identity ledger contains duplicate identities"
            )
        seen_physical.add(physical)
        seen_items.add(item)
        accepted.append(row)
    return tuple(accepted)


def _validate_pending_manifest(
    pending: tuple[Mapping[str, Any], ...],
    source_manifest: Mapping[str, Any],
    *,
    project_id: str,
    source_sha256s: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    if source_manifest.get("project_id") != project_id:
        raise ValueError("source manifest project mismatch")

    source_hashes = {
        row.get("sha256")
        for row in source_manifest.get("source_documents", ())
        if isinstance(row, Mapping)
    }
    if not set(source_sha256s).issubset(source_hashes):
        raise ValueError(
            "source manifest does not cover sealed source envelope"
        )

    items = source_manifest.get("verified_takeoff_items")
    if not isinstance(items, list):
        raise ValueError(
            "source manifest verified item inventory unavailable"
        )

    by_id: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if (
            not isinstance(item, Mapping)
            or item.get("denominator_eligible") is not True
        ):
            continue
        item_id = item.get("item_id")
        if type(item_id) is not str or not item_id:
            continue
        if item_id in by_id:
            raise ValueError(
                "source manifest denominator item IDs are not unique"
            )
        by_id[item_id] = item

    for row in pending:
        item = by_id.get(row["benchmark_item_id"])
        if item is None:
            raise ValueError(
                "pending benchmark item is not denominator eligible"
            )
        if item.get("expected_object_refs") != [
            row["benchmark_object_ref"]
        ]:
            raise ValueError(
                "pending benchmark item/object relationship is not "
                "frozen-authorized"
            )
        unit = item.get("unit")
        if type(unit) is not str or not unit or unit != unit.strip():
            raise ValueError("pending benchmark item has malformed frozen unit")
    return by_id


def build_activation(
    *,
    pending_ledger: Mapping[str, Any],
    sealed_run_payload: Mapping[str, Any],
    customer_rows: list[Mapping[str, Any]],
    active_identity_map_payload: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = _pending_rows(pending_ledger)
    sealed = sealed_source_closed_run_from_dict(sealed_run_payload)
    verified = verify_sealed_customer_output(sealed, customer_rows)
    active = identity_map_from_dict(active_identity_map_payload)
    authorized_items = _validate_pending_manifest(
        pending,
        source_manifest,
        project_id=sealed.project_id,
        source_sha256s=sealed.source_sha256s,
    )

    if sealed.project_id != active.project_id:
        raise ValueError(
            "sealed run and active identity map project mismatch"
        )
    if set(sealed.source_sha256s) != set(active.source_sha256s):
        raise ValueError(
            "sealed run and active identity map source envelope mismatch"
        )
    if pending_ledger.get("project_id") not in (
        None,
        sealed.project_id,
    ):
        raise ValueError("pending ledger project mismatch")
    if pending_ledger.get("source_sha256") not in (
        None,
        *sealed.source_sha256s,
    ):
        raise ValueError("pending ledger source mismatch")

    active_items = {
        binding.benchmark_item_id for binding in active.bindings
    }
    active_physical = {
        ref
        for binding in active.bindings
        for ref in binding.production_object_identity_refs
    }

    sealed_by_physical = {}
    for quantity in sealed.quantities:
        if quantity.abstained or not quantity.lineage_ok:
            continue
        refs = tuple(quantity.object_identity_refs)
        if len(refs) != 1:
            continue
        physical = refs[0]
        if physical in sealed_by_physical:
            raise ValueError(
                "multiple sealed quantities claim one physical identity"
            )
        sealed_by_physical[physical] = quantity

    additions = []
    activated = []
    verified_ids = set(verified.verified_quantity_ids)
    for row in pending:
        physical = row["physical_opening_id"]
        item = row["benchmark_item_id"]
        if physical in active_physical or item in active_items:
            raise ValueError(
                "pre-certified identity is already active"
            )

        quantity = sealed_by_physical.get(physical)
        if quantity is None:
            continue
        if quantity.quantity_id not in verified_ids:
            raise ValueError(
                "sealed pending quantity lacks verified customer row"
            )
        frozen_item = authorized_items[item]
        if quantity.unit != frozen_item["unit"]:
            raise ValueError(
                "sealed pending quantity unit does not match frozen item"
            )

        additions.append({
            "benchmark_item_id": item,
            "production_family": quantity.family,
            "production_object_identity_refs": [physical],
        })
        activated.append({
            "benchmark_item_id": item,
            "benchmark_object_ref": row["benchmark_object_ref"],
            "physical_opening_id": physical,
            "quantity_id": quantity.quantity_id,
            "production_family": quantity.family,
            "sealed_quantity_fingerprint": quantity.fingerprint,
        })

    if not additions:
        raise ValueError(
            "no pre-certified identity is newly sealed"
        )

    output = {
        "schema_version": SCHEMA_VERSION,
        "project_id": active.project_id,
        "source_sha256s": list(active.source_sha256s),
        "bindings": [
            {
                "benchmark_item_id": binding.benchmark_item_id,
                "production_family": binding.production_family,
                "production_object_identity_refs": list(
                    binding.production_object_identity_refs
                ),
            }
            for binding in active.bindings
        ] + additions,
    }

    # Reparse to enforce identity-map schema and uniqueness before publish.
    identity_map_from_dict(output)

    receipt = {
        "project_id": sealed.project_id,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "customer_verified_quantity_ids": list(
            verified.verified_quantity_ids
        ),
        "activated_count": len(activated),
        "activated": activated,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "evaluator_invoked": False,
    }
    return output, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pending-ledger",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--sealed-run",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--customer-rows",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--active-identity-map",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-map",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-receipt",
        type=Path,
        required=True,
    )
    args = parser.parse_args(argv)

    output, receipt = build_activation(
        pending_ledger=_object(args.pending_ledger),
        sealed_run_payload=_object(args.sealed_run),
        customer_rows=_rows(args.customer_rows),
        active_identity_map_payload=_object(
            args.active_identity_map
        ),
        source_manifest=_object(args.source_manifest),
    )

    args.output_map.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output_receipt.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output_map.write_text(
        json.dumps(output, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_receipt.write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
