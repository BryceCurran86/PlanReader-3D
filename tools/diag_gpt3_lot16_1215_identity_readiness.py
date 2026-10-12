"""Benchmark-side readiness proof for the next Lot16 1215 opening identity.

This diagnostic deliberately separates identity readiness from quantity
readiness. It may prove that one already-authenticated production physical
opening occupies the exact frozen source location, but it must not add an
active identity-map binding or grant a score until that physical object is
present in a real sealed production run.
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
TARGET_PHYSICAL_ID = (
    "physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9"
)
TARGET_OBJECT_REF = "lot16:opening:p3:1215_sgw_obs:01"
TARGET_ITEM_ID = "lot16-1215-sgw-obs-01-area"
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
    return tuple(round(float(value), FROZEN_LOCATION_DECIMAL_PLACES) for value in box)


def _source_receipt(source_report: Mapping[str, Any]) -> Mapping[str, Any]:
    if source_report.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("source report does not belong to the immutable Lot16 PDF")
    rows = source_report.get("opening_identity_text_receipts")
    if not isinstance(rows, list):
        raise ValueError("source report lacks opening identity text receipts")
    matches = [
        row for row in rows
        if isinstance(row, Mapping)
        and row.get("opening_identity_id") == TARGET_PHYSICAL_ID
    ]
    if len(matches) != 1:
        raise ValueError("target physical opening must have one source location receipt")
    row = matches[0]
    if row.get("location_is_reauthenticated_source_receipt") is not True:
        raise ValueError("target source location is not independently reauthenticated")
    _bbox(row.get("label_bbox_pdf_pt"), name="source label bbox")
    text_receipts = row.get("source_text_integrity_receipts")
    if (
        not isinstance(text_receipts, list)
        or not text_receipts
        or any(
            not isinstance(receipt, Mapping)
            or receipt.get("trusted") is not True
            or receipt.get("source_sha256") != SOURCE_SHA256
            or str(receipt.get("page_id")) != "3"
            for receipt in text_receipts
        )
    ):
        raise ValueError("target source text receipts are incomplete or untrusted")
    parents = [receipt.get("parent_observation_id") for receipt in text_receipts]
    if (
        any(type(value) is not str or not value for value in parents)
        or len(parents) != len(set(parents))
    ):
        raise ValueError("target source text ancestry is duplicated or malformed")
    return row


def _frozen_opening(
    object_universe: Mapping[str, Any],
) -> tuple[Mapping[str, Any], tuple[float, float, float, float]]:
    if object_universe.get("project_id") != PROJECT:
        raise ValueError("wrong frozen object-universe project")
    rows = object_universe.get("external_openings")
    if not isinstance(rows, list):
        raise ValueError("frozen external opening inventory is unavailable")
    targets = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("object_ref") == TARGET_OBJECT_REF
    ]
    if len(targets) != 1:
        raise ValueError("target frozen opening must exist exactly once")
    target = targets[0]
    attributes = target.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("target frozen opening lacks source attributes")
    target_box = _bbox(
        attributes.get("source_bbox_pdf_pt"),
        name="frozen source bbox",
    )

    # Source-location identity is admissible only if this box is unique within
    # the frozen external-opening inventory at the frozen recording precision.
    target_rounded = _rounded(target_box)
    same_location = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        attrs = row.get("attributes")
        if not isinstance(attrs, Mapping) or attrs.get("source_bbox_pdf_pt") is None:
            continue
        candidate_box = _bbox(
            attrs.get("source_bbox_pdf_pt"),
            name=f"frozen bbox for {row.get('object_ref')}",
        )
        if _rounded(candidate_box) == target_rounded:
            same_location.append(row.get("object_ref"))
    if same_location != [TARGET_OBJECT_REF]:
        raise ValueError("frozen source location is not unique")
    return target, target_box


def _manifest_item(source_manifest: Mapping[str, Any]) -> Mapping[str, Any]:
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
    matches = [
        row for row in items
        if isinstance(row, Mapping) and row.get("item_id") == TARGET_ITEM_ID
    ]
    if len(matches) != 1:
        raise ValueError("target denominator item must exist exactly once")
    item = matches[0]
    if item.get("denominator_eligible") is not True:
        raise ValueError("target frozen item is not denominator eligible")
    if item.get("expected_object_refs") != [TARGET_OBJECT_REF]:
        raise ValueError("target denominator item object identity drifted")
    return item


def _assert_not_currently_sealed(
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> None:
    if sealed_run.get("project_id") != PROJECT:
        raise ValueError("wrong sealed-run project")
    if set(sealed_run.get("source_sha256s") or ()) != {SOURCE_SHA256}:
        raise ValueError("sealed-run source envelope drifted")
    quantities = sealed_run.get("quantities")
    if not isinstance(quantities, list):
        raise ValueError("sealed-run quantity inventory malformed")
    if any(
        isinstance(row, Mapping)
        and TARGET_PHYSICAL_ID in tuple(row.get("object_identity_refs") or ())
        for row in quantities
    ):
        raise ValueError(
            "target physical opening is already sealed; readiness diagnostic is stale"
        )

    if active_identity_map.get("project_id") != PROJECT:
        raise ValueError("wrong active identity-map project")
    bindings = active_identity_map.get("bindings")
    if not isinstance(bindings, list):
        raise ValueError("active identity-map bindings malformed")
    if any(
        isinstance(row, Mapping)
        and (
            row.get("benchmark_item_id") == TARGET_ITEM_ID
            or TARGET_PHYSICAL_ID
            in tuple(row.get("production_object_identity_refs") or ())
        )
        for row in bindings
    ):
        raise ValueError(
            "target identity is already active; readiness diagnostic is stale"
        )


def build_readiness_report(
    *,
    source_report: Mapping[str, Any],
    object_universe: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    sealed_run: Mapping[str, Any],
    active_identity_map: Mapping[str, Any],
) -> dict[str, Any]:
    source = _source_receipt(source_report)
    frozen, frozen_box = _frozen_opening(object_universe)
    _manifest_item(source_manifest)
    _assert_not_currently_sealed(sealed_run, active_identity_map)

    source_box = _bbox(source.get("label_bbox_pdf_pt"), name="source label bbox")
    if _rounded(source_box) != _rounded(frozen_box):
        raise ValueError(
            "source physical opening location does not equal frozen source location"
        )

    return {
        "project_id": PROJECT,
        "source_sha256": SOURCE_SHA256,
        "physical_opening_id": TARGET_PHYSICAL_ID,
        "benchmark_item_id": TARGET_ITEM_ID,
        "benchmark_object_ref": TARGET_OBJECT_REF,
        "source_label_bbox_pdf_pt": list(source_box),
        "frozen_source_bbox_pdf_pt": list(frozen_box),
        "frozen_location_decimal_places": FROZEN_LOCATION_DECIMAL_PLACES,
        "source_location_equal_at_frozen_precision": True,
        "source_location_unique_in_frozen_external_openings": True,
        "source_text_observation_ids": list(
            source.get("source_text_observation_ids") or ()
        ),
        "figured_label_evidence_id": source.get("figured_label_evidence_id"),
        "matching_basis": (
            "EXACT_ORIGINAL_NATIVE_LABEL_OBSERVATION_LOCATION_"
            "AT_FROZEN_RECORDED_PRECISION"
        ),
        "numeric_quantity_similarity_used": False,
        "name_or_description_similarity_used": False,
        "ordinal_or_nearest_matching_used": False,
        "identity_ready_for_future_sealed_quantity": True,
        "target_currently_present_in_sealed_run": False,
        "target_currently_present_in_active_identity_map": False,
        "active_identity_map_modified": False,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "status": "IDENTITY_READY_QUANTITY_UNSEALED",
        "frozen_description_for_audit_only": frozen.get("description"),
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

    report = build_readiness_report(
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
