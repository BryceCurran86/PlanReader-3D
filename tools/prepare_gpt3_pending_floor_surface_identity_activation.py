"""Activate pre-certified source-authenticated floor-finish identities.

Benchmark-side integration only. This module never discovers a mapping from
quantity values, room-name similarity, item order, or expected benchmark area.
A floor binding must already be independently pre-certified, then be present in
one cryptographically verified source-closed run and its verified customer row.
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

_PACKAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/frozen_holdout/full_plan_v2"
)
_PACKAGE_NAME = "_planreader_full_plan_v2_floor_surface_activation"
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
READY = "IDENTITY_READY_QUANTITY_UNSEALED"
PROOF_READY = "INDEPENDENT_ORIGINAL_SOURCE_VERIFIED"


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


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


def _string(value: object, *, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} is malformed")
    return value


def _string_array(
    value: object,
    *,
    name: str,
    nonempty: bool = True,
    require_sorted: bool = True,
) -> tuple[str, ...]:
    if type(value) not in (list, tuple):
        raise ValueError(f"{name} must be an array")
    rows = tuple(value)
    if nonempty and not rows:
        raise ValueError(f"{name} must not be empty")
    if any(
        type(item) is not str or not item or item != item.strip()
        for item in rows
    ):
        raise ValueError(f"{name} contains malformed identity")
    if len(rows) != len(set(rows)):
        raise ValueError(f"{name} must be unique")
    if require_sorted and rows != tuple(sorted(rows)):
        raise ValueError(f"{name} must be sorted")
    return rows


def _pending_rows(
    ledger: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    raw = ledger.get("pending_identities")
    if not isinstance(raw, list) or not raw:
        raise ValueError("pending floor identity ledger has no candidate rows")

    out = []
    seen_canonical: set[str] = set()
    seen_physical: set[str] = set()
    seen_items: set[str] = set()
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError("pending floor identity row must be a mapping")
        if row.get("status") != READY:
            raise ValueError("pending floor identity row is not pre-certified")
        canonical = _string(
            row.get("canonical_floor_id"),
            name="canonical_floor_id",
        )
        physical = _string(
            row.get("physical_floor_surface_id"),
            name="physical_floor_surface_id",
        )
        item = _string(
            row.get("benchmark_item_id"),
            name="benchmark_item_id",
        )
        _string(
            row.get("benchmark_object_ref"),
            name="benchmark_object_ref",
        )
        if (
            canonical in seen_canonical
            or physical in seen_physical
            or item in seen_items
        ):
            raise ValueError("pending floor identities are not one-to-one")
        seen_canonical.add(canonical)
        seen_physical.add(physical)
        seen_items.add(item)
        out.append(row)
    return tuple(out)


def _verified_items(
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
        raise ValueError("source manifest does not cover sealed source envelope")
    raw = source_manifest.get("verified_takeoff_items")
    if not isinstance(raw, list):
        raise ValueError("source manifest verified item inventory unavailable")
    items: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        if (
            not isinstance(item, Mapping)
            or item.get("denominator_eligible") is not True
        ):
            continue
        item_id = item.get("item_id")
        if type(item_id) is not str or not item_id:
            continue
        if item_id in items:
            raise ValueError("source manifest item IDs are not unique")
        items[item_id] = item
    return items


def _object_rows(value: object):
    if isinstance(value, Mapping):
        if type(value.get("object_ref")) is str:
            yield value
        for child in value.values():
            yield from _object_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from _object_rows(child)


def _frozen_surface_objects(
    object_universe: Mapping[str, Any],
    *,
    project_id: str,
) -> dict[str, Mapping[str, Any]]:
    if object_universe.get("project_id") != project_id:
        raise ValueError("object universe project mismatch")
    result: dict[str, Mapping[str, Any]] = {}
    for row in _object_rows(object_universe):
        object_ref = _string(row.get("object_ref"), name="frozen object_ref")
        if object_ref in result:
            raise ValueError("frozen object refs are not unique")
        result[object_ref] = row
    return result


def _proof_bindings(
    source_identity_proof: Mapping[str, Any],
    *,
    source_sha256s: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    source_sha = _string(
        source_identity_proof.get("source_sha256"),
        name="source identity proof SHA",
    ).lower()
    if source_sha not in {value.lower() for value in source_sha256s}:
        raise ValueError("surface identity proof is outside sealed source envelope")
    raw = source_identity_proof.get("bindings")
    if not isinstance(raw, list):
        raise ValueError("surface identity proof binding inventory unavailable")
    by_canonical: dict[str, Mapping[str, Any]] = {}
    for proof in raw:
        if not isinstance(proof, Mapping):
            raise ValueError("surface identity proof row must be a mapping")
        if proof.get("proof_status") != PROOF_READY:
            raise ValueError("surface identity proof is not independently certified")
        if proof.get("production_family") != "floor_finish_area":
            raise ValueError("surface identity proof family must be floor_finish_area")
        canonical = _string(
            proof.get("canonical_floor_id"),
            name="proof canonical_floor_id",
        )
        _string(
            proof.get("physical_floor_surface_id"),
            name="proof physical_floor_surface_id",
        )
        _string(
            proof.get("benchmark_item_id"),
            name="proof benchmark_item_id",
        )
        _string(
            proof.get("benchmark_object_ref"),
            name="proof benchmark_object_ref",
        )
        _string_array(
            proof.get("required_trace_canonical_entity_ids"),
            name="proof required trace canonical identities",
        )
        _string_array(
            proof.get("required_trace_evidence_ids"),
            name="proof required trace evidence",
        )
        _string_array(
            proof.get("frozen_source_evidence_refs"),
            name="proof frozen source evidence refs",
            require_sorted=False,
        )
        if canonical in by_canonical:
            raise ValueError("surface identity proof canonical floors are not unique")
        by_canonical[canonical] = proof
    return by_canonical


def build_floor_surface_activation(
    *,
    pending_ledger: Mapping[str, Any],
    sealed_run_payload: Mapping[str, Any],
    customer_rows: list[Mapping[str, Any]],
    active_identity_map_payload: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    source_identity_proof: Mapping[str, Any],
    object_universe: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = _pending_rows(pending_ledger)
    sealed = sealed_source_closed_run_from_dict(sealed_run_payload)
    verified = verify_sealed_customer_output(sealed, customer_rows)
    active = identity_map_from_dict(active_identity_map_payload)

    if sealed.project_id != active.project_id:
        raise ValueError("sealed run and active identity map project mismatch")
    if set(sealed.source_sha256s) != set(active.source_sha256s):
        raise ValueError("sealed run and active identity map source envelope mismatch")
    if pending_ledger.get("project_id") not in (None, sealed.project_id):
        raise ValueError("pending floor identity project mismatch")
    if pending_ledger.get("source_sha256") not in (
        None, *sealed.source_sha256s
    ):
        raise ValueError("pending floor identity source mismatch")

    items = _verified_items(
        source_manifest,
        project_id=sealed.project_id,
        source_sha256s=sealed.source_sha256s,
    )
    frozen = _frozen_surface_objects(
        object_universe,
        project_id=sealed.project_id,
    )
    proofs = _proof_bindings(
        source_identity_proof,
        source_sha256s=sealed.source_sha256s,
    )

    active_items = {binding.benchmark_item_id for binding in active.bindings}
    active_entities = {
        ref
        for binding in active.bindings
        for ref in binding.production_object_identity_refs
    }
    sealed_by_canonical = {}
    for quantity in sealed.quantities:
        if quantity.abstained or not quantity.lineage_ok:
            continue
        if quantity.family != "floor_finish_area":
            continue
        refs = tuple(quantity.object_identity_refs)
        if len(refs) != 1:
            raise ValueError(
                "sealed floor-finish quantity must own one canonical floor"
            )
        canonical = refs[0]
        if canonical in sealed_by_canonical:
            raise ValueError(
                "multiple sealed floor-finish quantities claim one canonical floor"
            )
        sealed_by_canonical[canonical] = quantity

    verified_ids = set(verified.verified_quantity_ids)
    additions = []
    activated = []
    for row in pending:
        canonical = row["canonical_floor_id"]
        physical = row["physical_floor_surface_id"]
        item_id = row["benchmark_item_id"]
        object_ref = row["benchmark_object_ref"]

        if canonical in active_entities or item_id in active_items:
            raise ValueError("pre-certified floor identity is already active")

        quantity = sealed_by_canonical.get(canonical)
        if quantity is None:
            continue
        if quantity.quantity_id not in verified_ids:
            raise ValueError("sealed floor quantity lacks verified customer row")

        frozen_item = items.get(item_id)
        if frozen_item is None:
            raise ValueError("pending floor benchmark item is not denominator eligible")
        if frozen_item.get("expected_object_refs") != [object_ref]:
            raise ValueError(
                "pending floor item/object relationship is not frozen-authorized"
            )
        unit = frozen_item.get("unit")
        if type(unit) is not str or quantity.unit != unit:
            raise ValueError("sealed floor quantity unit does not match frozen item")

        frozen_object = frozen.get(object_ref)
        if frozen_object is None:
            raise ValueError("pending frozen floor object is not in object universe")
        if frozen_object.get("physical_kind") != "floor_finish_surface":
            raise ValueError("pending frozen object is not a floor-finish surface")
        verification = frozen_object.get("verification")
        if (
            not isinstance(verification, Mapping)
            or verification.get("fully_source_closed") is not True
        ):
            raise ValueError("pending frozen floor object is not source closed")
        provenance = frozen_object.get("provenance")
        if not isinstance(provenance, Mapping):
            raise ValueError("pending frozen floor object lacks provenance")
        frozen_evidence = _string_array(
            provenance.get("source_evidence_refs"),
            name="frozen floor source evidence refs",
            require_sorted=False,
        )

        proof = proofs.get(canonical)
        if proof is None:
            raise ValueError("pending floor lacks independent source identity proof")
        if (
            proof["physical_floor_surface_id"] != physical
            or proof["benchmark_item_id"] != item_id
            or proof["benchmark_object_ref"] != object_ref
        ):
            raise ValueError("surface proof does not authorize pending identity")
        proof_source_refs = tuple(proof["frozen_source_evidence_refs"])
        if proof_source_refs != frozen_evidence:
            raise ValueError("surface proof source ancestry differs from frozen object")

        required_entities = set(proof["required_trace_canonical_entity_ids"])
        required_evidence = set(proof["required_trace_evidence_ids"])
        if canonical not in required_entities or physical not in required_entities:
            raise ValueError(
                "surface proof must require canonical and physical floor identities"
            )
        if not required_entities.issubset(set(quantity.trace_canonical_entity_ids)):
            raise ValueError("sealed floor trace does not contain source-proven identities")
        if not required_evidence.issubset(set(quantity.trace_evidence_ids)):
            raise ValueError("sealed floor trace does not contain source-proven evidence")
        if not set(quantity.evidence_ids).issubset(
            set(quantity.trace_evidence_ids)
        ):
            raise ValueError("sealed floor quantity evidence is outside signed trace")

        additions.append({
            "benchmark_item_id": item_id,
            "production_family": "floor_finish_area",
            "production_object_identity_refs": [canonical],
        })
        activated.append({
            "benchmark_item_id": item_id,
            "benchmark_object_ref": object_ref,
            "canonical_floor_id": canonical,
            "physical_floor_surface_id": physical,
            "quantity_id": quantity.quantity_id,
            "sealed_quantity_fingerprint": quantity.fingerprint,
            "production_family": quantity.family,
        })

    if not additions:
        raise ValueError("no pre-certified floor identity is newly sealed")

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
    identity_map_from_dict(output)

    receipt = {
        "project_id": sealed.project_id,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "customer_verified_quantity_ids": list(verified.verified_quantity_ids),
        "activated_count": len(activated),
        "activated": activated,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "evaluator_invoked": False,
    }
    return output, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-ledger", type=Path, required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customer-rows", type=Path, required=True)
    parser.add_argument("--active-identity-map", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-identity-proof", type=Path, required=True)
    parser.add_argument("--object-universe", type=Path, required=True)
    parser.add_argument("--output-map", type=Path, required=True)
    parser.add_argument("--output-receipt", type=Path, required=True)
    args = parser.parse_args(argv)

    output, receipt = build_floor_surface_activation(
        pending_ledger=_object(args.pending_ledger),
        sealed_run_payload=_object(args.sealed_run),
        customer_rows=_rows(args.customer_rows),
        active_identity_map_payload=_object(args.active_identity_map),
        source_manifest=_object(args.source_manifest),
        source_identity_proof=_object(args.source_identity_proof),
        object_universe=_object(args.object_universe),
    )
    args.output_map.parent.mkdir(parents=True, exist_ok=True)
    args.output_receipt.parent.mkdir(parents=True, exist_ok=True)
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
