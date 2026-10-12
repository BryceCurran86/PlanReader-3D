"""Scan Lot16 external openings for exact original-source identity readiness.

Benchmark-side diagnostic only. Original trusted opening-label locations are
compared with unique frozen external-opening source locations at the frozen
recording precision. No quantity value, description/name similarity, ordinal,
nearest geometry or evaluator result participates in the identity decision.

Already-active bindings are audited for parity with the signed run. Exact
unsealed matches remain pending. An exact physical identity that later appears
in the sealed run without an active map binding is surfaced separately for
guarded reconciliation; this tool never activates a binding or grants a score.
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
        raise ValueError(f"{name} must contain numeric coordinates")
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
        raise ValueError("source report does not belong to immutable Lot16 PDF")
    rows = source_report.get("opening_identity_text_receipts")
    if not isinstance(rows, list):
        raise ValueError("source report lacks opening identity text receipts")

    accepted: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("source identity receipt must be a mapping")
        physical = row.get("opening_identity_id")
        if (
            type(physical) is not str
            or not physical
            or physical != physical.strip()
            or physical in seen
        ):
            raise ValueError("source identity physical IDs must be unique and typed")
        seen.add(physical)
        if row.get("location_is_reauthenticated_source_receipt") is not True:
            raise ValueError("source identity location is not reauthenticated")
        _bbox(row.get("label_bbox_pdf_pt"), name=f"source bbox for {physical}")

        observations = row.get("source_text_observation_ids")
        receipts = row.get("source_text_integrity_receipts")
        if (
            not isinstance(observations, list)
            or not observations
            or any(
                type(value) is not str or not value or value != value.strip()
                for value in observations
            )
            or len(observations) != len(set(observations))
            or not isinstance(receipts, list)
            or not receipts
        ):
            raise ValueError("source identity text ancestry is incomplete")
        parents: list[str] = []
        for receipt in receipts:
            if (
                not isinstance(receipt, Mapping)
                or receipt.get("trusted") is not True
                or receipt.get("source_sha256") != SOURCE_SHA256
                or str(receipt.get("page_id")) != "3"
            ):
                raise ValueError("source identity text receipt is untrusted or foreign")
            parent = receipt.get("parent_observation_id")
            if type(parent) is not str or not parent or parent != parent.strip():
                raise ValueError("source text parent observation is malformed")
            parents.append(parent)
        if len(parents) != len(set(parents)) or set(parents) != set(observations):
            raise ValueError("source identity text ancestry is inconsistent")
        accepted.append(row)
    return tuple(accepted)


def _frozen_external_locations(
    object_universe: Mapping[str, Any],
) -> tuple[
    dict[tuple[float, float, float, float], Mapping[str, Any]],
    tuple[str, ...],
]:
    if object_universe.get("project_id") != PROJECT:
        raise ValueError("wrong frozen object-universe project")
    rows = object_universe.get("external_openings")
    if not isinstance(rows, list):
        raise ValueError("frozen external-opening inventory unavailable")
    locations: dict[tuple[float, float, float, float], Mapping[str, Any]] = {}
    unlocated: list[str] = []
    seen_refs: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("frozen external opening must be a mapping")
        object_ref = row.get("object_ref")
        attrs = row.get("attributes")
        if (
            type(object_ref) is not str
            or not object_ref
            or not isinstance(attrs, Mapping)
        ):
            raise ValueError("frozen external opening source identity malformed")
        if object_ref in seen_refs:
            raise ValueError("frozen external opening object refs are not unique")
        seen_refs.add(object_ref)
        # Without an original PDF-coordinate bbox, identity must abstain.
        # Never substitute object names, widths, item order or nearest geometry.
        if "source_bbox_pdf_pt" not in attrs:
            unlocated.append(object_ref)
            continue
        box = _bbox(
            attrs.get("source_bbox_pdf_pt"),
            name=f"frozen bbox for {object_ref}",
        )
        key = _rounded(box)
        if key in locations:
            raise ValueError("frozen external source locations are not unique")
        locations[key] = row
    return locations, tuple(sorted(unlocated))


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

    by_object: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping) or item.get("denominator_eligible") is not True:
            continue
        refs = item.get("expected_object_refs")
        if type(refs) is not list or len(refs) != 1:
            continue
        object_ref = refs[0]
        if type(object_ref) is not str or not object_ref:
            continue
        if object_ref in by_object:
            raise ValueError("frozen object has multiple denominator items")
        by_object[object_ref] = item
    return by_object


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
        physical = row.get("physical_opening_id")
        if type(physical) is not str or not physical or physical in result:
            raise ValueError("canonical opening physical IDs must be unique")
        result[physical] = row
    return result


def _signed_state(
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> tuple[set[str], dict[str, str], dict[str, str]]:
    if sealed_run.get("project_id") != PROJECT:
        raise ValueError("wrong sealed-run project")
    if set(sealed_run.get("source_sha256s") or ()) != {SOURCE_SHA256}:
        raise ValueError("sealed-run source envelope drifted")
    quantities = sealed_run.get("quantities")
    if not isinstance(quantities, list):
        raise ValueError("sealed quantity inventory malformed")
    sealed_physical: set[str] = set()
    for row in quantities:
        if not isinstance(row, Mapping):
            raise ValueError("sealed quantity must be a mapping")
        refs = row.get("object_identity_refs")
        if type(refs) not in (list, tuple) or len(refs) != 1:
            raise ValueError("sealed opening quantity must own one physical identity")
        ref = refs[0]
        if type(ref) is not str or not ref or ref in sealed_physical:
            raise ValueError("sealed physical opening identities must be unique")
        sealed_physical.add(ref)

    if active_identity_map.get("project_id") != PROJECT:
        raise ValueError("wrong active identity-map project")
    bindings = active_identity_map.get("bindings")
    if not isinstance(bindings, list):
        raise ValueError("active identity-map bindings malformed")
    item_to_physical: dict[str, str] = {}
    physical_to_item: dict[str, str] = {}
    for row in bindings:
        if not isinstance(row, Mapping):
            raise ValueError("identity binding must be a mapping")
        item = row.get("benchmark_item_id")
        refs = row.get("production_object_identity_refs")
        if (
            type(item) is not str or not item
            or type(refs) not in (list, tuple) or len(refs) != 1
            or type(refs[0]) is not str or not refs[0]
        ):
            raise ValueError("active opening identity binding malformed")
        physical = refs[0]
        if item in item_to_physical or physical in physical_to_item:
            raise ValueError("active identity map contains duplicate ownership")
        item_to_physical[item] = physical
        physical_to_item[physical] = item
    if not set(physical_to_item).issubset(sealed_physical):
        raise ValueError(
            "active identity map contains a physical identity absent from signed run"
        )
    return sealed_physical, item_to_physical, physical_to_item


def scan_external_identity_readiness(
    *,
    source_report: Mapping[str, Any],
    object_universe: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> dict[str, Any]:
    source_rows = _trusted_source_receipts(source_report)
    frozen_by_location, unlocated = _frozen_external_locations(object_universe)
    items_by_object = _manifest_items_by_object(source_manifest)
    canonical_by_physical = _canonical_by_physical(source_report)
    sealed_physical, item_to_physical, physical_to_item = _signed_state(
        sealed_run, active_identity_map
    )

    active: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    newly_sealed_unmapped: list[dict[str, Any]] = []
    seen_objects: set[str] = set()

    for source in source_rows:
        source_box = _bbox(source.get("label_bbox_pdf_pt"), name="source label bbox")
        frozen = frozen_by_location.get(_rounded(source_box))
        if frozen is None:
            continue
        object_ref = frozen.get("object_ref")
        if object_ref in seen_objects:
            raise ValueError("multiple source physical openings claim one frozen location")
        seen_objects.add(object_ref)
        item = items_by_object.get(object_ref)
        if item is None:
            raise ValueError("matched external opening lacks denominator item")
        item_id = item.get("item_id")
        if type(item_id) is not str or not item_id:
            raise ValueError("matched denominator item ID malformed")

        physical = source.get("opening_identity_id")
        canonical = canonical_by_physical.get(physical)
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
            name=f"frozen bbox for {object_ref}",
        )
        if _rounded(source_box) != _rounded(frozen_box):
            raise AssertionError("external location index returned unequal locations")

        row = {
            "physical_opening_id": physical,
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
        }

        mapped_physical = item_to_physical.get(item_id)
        mapped_item = physical_to_item.get(physical)
        is_sealed = physical in sealed_physical
        if mapped_physical is not None or mapped_item is not None:
            if (
                mapped_physical != physical
                or mapped_item != item_id
                or not is_sealed
            ):
                raise ValueError("active frozen/source identity contradicts signed state")
            active.append({**row, "status": "ACTIVE_SIGNED_IDENTITY"})
        elif is_sealed:
            newly_sealed_unmapped.append(
                {**row, "status": "SEALED_UNMAPPED_IDENTITY_READY"}
            )
        else:
            pending.append({**row, "status": "IDENTITY_READY_QUANTITY_UNSEALED"})

    for rows in (active, pending, newly_sealed_unmapped):
        rows.sort(key=lambda row: row["benchmark_object_ref"])

    # Active signed bindings require independently verified source-location
    # parity; absent or shifted receipts must not silently vanish from audit.
    active_physical = {row["physical_opening_id"] for row in active}
    if active_physical != set(physical_to_item):
        missing = sorted(set(physical_to_item) - active_physical)
        raise ValueError(
            "active identity lacks independently verified exact source-location parity: "
            + ", ".join(missing)
        )

    return {
        "project_id": PROJECT,
        "source_sha256": SOURCE_SHA256,
        "frozen_location_decimal_places": FROZEN_LOCATION_DECIMAL_PLACES,
        "frozen_unlocated_object_count": len(unlocated),
        "frozen_unlocated_object_refs": list(unlocated),
        "active_exact_identity_count": len(active),
        "active_exact_identities": active,
        "pending_identity_count": len(pending),
        "pending_identities": pending,
        "newly_sealed_unmapped_count": len(newly_sealed_unmapped),
        "newly_sealed_unmapped_identities": newly_sealed_unmapped,
        "active_identity_map_modified": False,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "evaluator_invoked": False,
        "numeric_quantity_similarity_used": False,
        "name_or_description_similarity_used": False,
        "ordinal_or_nearest_matching_used": False,
        "status": "EXTERNAL_IDENTITY_READINESS_AUDIT_COMPLETE",
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
    report = scan_external_identity_readiness(
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
