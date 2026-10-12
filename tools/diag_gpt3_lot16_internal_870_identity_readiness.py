"""Benchmark-side pending-identity ledger for source-authenticated Lot16 870 openings.

Diagnostic only. It matches independently reauthenticated original-source label
locations to frozen internal-room-access opening locations at the frozen recorded
precision. It never uses quantity values, names, descriptions, order, nearest
geometry, or the evaluator. A binding remains pending until the production
physical object appears in a real sealed run.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT = "au_qld_lot16_power"
SOURCE_SHA256 = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)
FROZEN_LOCATION_DECIMAL_PLACES = 1


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _bbox(value: object, *, name: str) -> tuple[float, float, float, float]:
    if type(value) not in (list, tuple) or len(value) != 4:
        raise ValueError(f"{name} must contain four coordinates")
    if any(type(item) not in (int, float) for item in value):
        raise ValueError(f"{name} must contain typed numeric coordinates")
    box = tuple(float(item) for item in value)
    if (
        not all(math.isfinite(item) for item in box)
        or box[2] <= box[0]
        or box[3] <= box[1]
    ):
        raise ValueError(f"{name} must be a finite positive box")
    return box


def _rounded(box: Sequence[float]) -> tuple[float, float, float, float]:
    return tuple(
        round(float(value), FROZEN_LOCATION_DECIMAL_PLACES) for value in box
    )


def _trusted_source_receipts(
    source_report: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if source_report.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("source report does not belong to the immutable Lot16 PDF")
    rows = source_report.get("opening_identity_text_receipts")
    if not isinstance(rows, list):
        raise ValueError("source report lacks opening identity text receipts")

    accepted: list[Mapping[str, Any]] = []
    seen_physical: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("source identity receipt must be a mapping")
        physical_id = row.get("opening_identity_id")
        if type(physical_id) is not str or not physical_id or physical_id != physical_id.strip():
            raise ValueError("source identity receipt has malformed physical ID")
        if physical_id in seen_physical:
            raise ValueError("source identity receipt physical IDs must be unique")
        seen_physical.add(physical_id)

        if row.get("location_is_reauthenticated_source_receipt") is not True:
            raise ValueError("source identity location is not independently reauthenticated")
        _bbox(row.get("label_bbox_pdf_pt"), name=f"source label bbox for {physical_id}")

        observations = row.get("source_text_observation_ids")
        text_receipts = row.get("source_text_integrity_receipts")
        if (
            not isinstance(observations, list)
            or not observations
            or any(type(item) is not str or not item or item != item.strip() for item in observations)
            or len(observations) != len(set(observations))
            or not isinstance(text_receipts, list)
            or not text_receipts
        ):
            raise ValueError("source identity text ancestry is incomplete or malformed")
        parents: list[str] = []
        for receipt in text_receipts:
            if (
                not isinstance(receipt, Mapping)
                or receipt.get("trusted") is not True
                or receipt.get("source_sha256") != SOURCE_SHA256
                or str(receipt.get("page_id")) != "3"
            ):
                raise ValueError("source identity text receipt is untrusted or foreign")
            parent = receipt.get("parent_observation_id")
            if type(parent) is not str or not parent or parent != parent.strip():
                raise ValueError("source identity text receipt parent is malformed")
            parents.append(parent)
        if len(parents) != len(set(parents)) or set(parents) != set(observations):
            raise ValueError("source identity text ancestry is duplicated or inconsistent")
        accepted.append(row)
    return tuple(accepted)


def _frozen_internal_locations(
    object_universe: Mapping[str, Any],
) -> dict[tuple[float, float, float, float], Mapping[str, Any]]:
    if object_universe.get("project_id") != PROJECT:
        raise ValueError("wrong frozen object-universe project")
    rows = object_universe.get("internal_room_access_openings")
    if not isinstance(rows, list):
        raise ValueError("frozen internal-room-access opening inventory unavailable")

    locations: dict[tuple[float, float, float, float], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("frozen internal opening must be a mapping")
        object_ref = row.get("object_ref")
        if type(object_ref) is not str or not object_ref or object_ref != object_ref.strip():
            raise ValueError("frozen internal opening has malformed object ref")
        attributes = row.get("attributes")
        if not isinstance(attributes, Mapping):
            raise ValueError(f"{object_ref} lacks frozen source attributes")
        box = _bbox(
            attributes.get("source_bbox_pdf_pt"),
            name=f"frozen source bbox for {object_ref}",
        )
        key = _rounded(box)
        if key in locations:
            raise ValueError("frozen internal source locations are not unique")
        locations[key] = row
    return locations


def _manifest_items_by_object(
    source_manifest: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if source_manifest.get("project_id") != PROJECT:
        raise ValueError("wrong source-manifest project")
    source_hashes = {
        row.get("sha256")
        for row in source_manifest.get("source_documents", ())
        if isinstance(row, Mapping)
    }
    if SOURCE_SHA256 not in source_hashes:
        raise ValueError("immutable Lot16 architecture SHA missing from manifest")

    items = source_manifest.get("verified_takeoff_items")
    if not isinstance(items, list):
        raise ValueError("verified takeoff inventory unavailable")
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping) or item.get("denominator_eligible") is not True:
            continue
        refs = item.get("expected_object_refs")
        if type(refs) is not list or len(refs) != 1:
            continue
        object_ref = refs[0]
        if type(object_ref) is not str or not object_ref:
            continue
        if object_ref in result:
            raise ValueError("frozen object has multiple denominator items")
        result[object_ref] = item
    return result


def _active_physical_ids(
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> tuple[set[str], set[str], set[str]]:
    if sealed_run.get("project_id") != PROJECT:
        raise ValueError("wrong sealed-run project")
    if set(sealed_run.get("source_sha256s") or ()) != {SOURCE_SHA256}:
        raise ValueError("sealed-run source envelope drifted")
    quantities = sealed_run.get("quantities")
    if not isinstance(quantities, list):
        raise ValueError("sealed-run quantity inventory malformed")
    sealed_physical: set[str] = set()
    for row in quantities:
        if not isinstance(row, Mapping):
            raise ValueError("sealed quantity must be a mapping")
        refs = row.get("object_identity_refs")
        if type(refs) not in (list, tuple):
            raise ValueError("sealed quantity identity refs malformed")
        for ref in refs:
            if type(ref) is not str or not ref or ref != ref.strip():
                raise ValueError("sealed quantity identity ref malformed")
            sealed_physical.add(ref)

    if active_identity_map.get("project_id") != PROJECT:
        raise ValueError("wrong active identity-map project")
    bindings = active_identity_map.get("bindings")
    if not isinstance(bindings, list):
        raise ValueError("active identity-map bindings malformed")
    mapped_physical: set[str] = set()
    mapped_items: set[str] = set()
    for row in bindings:
        if not isinstance(row, Mapping):
            raise ValueError("active identity-map binding must be a mapping")
        item_id = row.get("benchmark_item_id")
        if type(item_id) is not str or not item_id:
            raise ValueError("active identity-map item ID malformed")
        mapped_items.add(item_id)
        refs = row.get("production_object_identity_refs")
        if type(refs) not in (list, tuple):
            raise ValueError("active identity-map production refs malformed")
        for ref in refs:
            if type(ref) is not str or not ref or ref != ref.strip():
                raise ValueError("active identity-map production ref malformed")
            mapped_physical.add(ref)
    return sealed_physical, mapped_physical, mapped_items


def _canonical_by_physical(
    source_report: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows = source_report.get("canonical_openings")
    if not isinstance(rows, list):
        raise ValueError("source report lacks canonical opening inventory")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical opening must be a mapping")
        physical_id = row.get("physical_opening_id")
        if type(physical_id) is not str or not physical_id:
            raise ValueError("canonical opening physical ID malformed")
        if physical_id in result:
            raise ValueError("canonical opening physical IDs must be unique")
        result[physical_id] = row
    return result


def build_pending_identity_ledger(
    *,
    source_report: Mapping[str, Any],
    object_universe: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> dict[str, Any]:
    source_rows = _trusted_source_receipts(source_report)
    frozen_by_location = _frozen_internal_locations(object_universe)
    manifest_by_object = _manifest_items_by_object(source_manifest)
    canonical_by_physical = _canonical_by_physical(source_report)
    sealed_physical, mapped_physical, mapped_items = _active_physical_ids(
        sealed_run,
        active_identity_map,
    )

    pending: list[dict[str, Any]] = []
    seen_frozen: set[str] = set()
    for source in source_rows:
        source_box = _bbox(
            source.get("label_bbox_pdf_pt"),
            name="source label bbox",
        )
        frozen = frozen_by_location.get(_rounded(source_box))
        if frozen is None:
            continue
        object_ref = frozen.get("object_ref")
        if object_ref in seen_frozen:
            raise ValueError("multiple source physical openings claim one frozen location")
        seen_frozen.add(object_ref)

        item = manifest_by_object.get(object_ref)
        if item is None:
            raise ValueError("matched frozen internal opening lacks denominator item")
        item_id = item.get("item_id")
        if type(item_id) is not str or not item_id:
            raise ValueError("matched frozen denominator item ID malformed")
        physical_id = source.get("opening_identity_id")
        if physical_id in sealed_physical or physical_id in mapped_physical or item_id in mapped_items:
            raise ValueError(
                "pending identity became active; ledger is stale and must be reconciled"
            )

        canonical = canonical_by_physical.get(physical_id)
        if canonical is None:
            raise ValueError("source physical identity lacks canonical opening")
        label_evidence = source.get("figured_label_evidence_id")
        if (
            type(label_evidence) is not str
            or not label_evidence
            or canonical.get("figured_area_record_id") != label_evidence
        ):
            raise ValueError("canonical opening does not preserve source label evidence")

        frozen_box = _bbox(
            frozen.get("attributes", {}).get("source_bbox_pdf_pt"),
            name=f"frozen source bbox for {object_ref}",
        )
        if _rounded(source_box) != _rounded(frozen_box):
            raise AssertionError("internal location index returned unequal source location")

        pending.append({
            "physical_opening_id": physical_id,
            "benchmark_item_id": item_id,
            "benchmark_object_ref": object_ref,
            "source_label_bbox_pdf_pt": list(source_box),
            "frozen_source_bbox_pdf_pt": list(frozen_box),
            "source_text_observation_ids": list(
                source.get("source_text_observation_ids") or ()
            ),
            "figured_label_evidence_id": label_evidence,
            "host_binding_present": bool(canonical.get("host_binding_record_id")),
            "host_frame_present": bool(canonical.get("host_frame_record_id")),
            "width_authority_present": bool(canonical.get("width_record_id")),
            "height_authority_present": bool(canonical.get("height_record_id")),
            "matching_basis": (
                "EXACT_ORIGINAL_NATIVE_LABEL_OBSERVATION_LOCATION_"
                "AT_FROZEN_RECORDED_PRECISION"
            ),
            "status": "IDENTITY_READY_QUANTITY_UNSEALED",
        })

    pending.sort(key=lambda row: row["benchmark_object_ref"])
    return {
        "project_id": PROJECT,
        "source_sha256": SOURCE_SHA256,
        "frozen_location_decimal_places": FROZEN_LOCATION_DECIMAL_PLACES,
        "pending_identity_count": len(pending),
        "pending_identities": pending,
        "all_pending_absent_from_current_sealed_run": True,
        "all_pending_absent_from_active_identity_map": True,
        "active_identity_map_modified": False,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "numeric_quantity_similarity_used": False,
        "name_or_description_similarity_used": False,
        "ordinal_or_nearest_matching_used": False,
        "status": "PENDING_IDENTITIES_READY_QUANTITIES_UNSEALED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--object-universe", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--active-identity-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_pending_identity_ledger(
        source_report=_object(args.source_report),
        object_universe=_object(args.object_universe),
        source_manifest=_object(args.source_manifest),
        sealed_run=_object(args.sealed_run),
        active_identity_map=_object(args.active_identity_map),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
