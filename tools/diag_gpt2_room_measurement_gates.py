"""Benchmark-neutral per-room measurement first-failure inventory.

Reports source-produced room, face, canonical floor and measurement evidence.
A PDF page-points² area is never interpreted as m². A label-only quantity is
diagnostic context, never proof of unique physical room ownership.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _reason_map(pairs: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for room_id, reason in pairs or ():
        if isinstance(reason, (tuple, list)):
            reasons = [str(item) for item in reason]
        else:
            reasons = [str(reason)]
        out.setdefault(str(room_id), []).extend(reasons)
    return {key: sorted(set(values)) for key, values in out.items()}


def inspect_room_measurement_gates(claim: Any) -> dict[str, Any]:
    """Read the producer's own first-failure traces, without rerunning proofs."""
    floors_by_room: dict[str, list[Any]] = {}
    for floor in claim.canonical_floors:
        floors_by_room.setdefault(str(floor.room_entity_id), []).append(floor)

    # A documented dimension can establish a FIRM room area without
    # establishing a metrically scaled source polygon.  The live floor
    # bridge explicitly leaves metric_geometry_complete=False in that
    # case.  Join the exact producer-owned quantity id to its immutable
    # FIRM receipt rather than misreporting a missing measurement.
    published_area_by_id: dict[str, list[Any]] = {}
    for quantity in claim.room_area_quantity_evidence:
        quantity_id = _clean(getattr(quantity, "quantity_id", ""))
        if quantity_id:
            published_area_by_id.setdefault(quantity_id, []).append(quantity)

    # Only real producer claims can be passed to the commercial reissuers.
    # A canonical floor's commercial_quantity_authority flag is deliberately
    # False until independent review, including for source-FIRM room areas.
    # It must not substitute for running the actual fail-closed publishers.
    published_floor_by_source: dict[str, list[Any]] = {}
    published_room_by_source: dict[str, list[Any]] = {}
    from collections.abc import Mapping
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    if type(claim) is LivePhysicalNetWallClaim:
        from pb_live_floor_area_quantity_publication import (
            publish_live_floor_area_quantities,
            publish_live_canonical_room_area_quantities,
        )
        for published in publish_live_floor_area_quantities(claim):
            metadata = published.metadata
            if isinstance(metadata, Mapping):
                upstream = _clean(metadata.get("upstream_room_area_quantity_id"))
                if upstream:
                    published_floor_by_source.setdefault(upstream, []).append(published)
        for published in publish_live_canonical_room_area_quantities(claim):
            metadata = published.metadata
            if isinstance(metadata, Mapping):
                upstream = _clean(metadata.get("upstream_room_area_quantity_id"))
                if upstream:
                    published_room_by_source.setdefault(upstream, []).append(published)

    customer_handoff = {
        "published_floor_area_quantity_ids": [],
        "sealed_floor_area_quantity_ids": [],
        "customer_verified_floor_area_quantity_ids": [],
        "customer_review_row_count": 0,
        "customer_projection_failure_type": None,
    }
    if type(claim) is LivePhysicalNetWallClaim:
        from tools.diag_gpt3_maryborough_floor_customer_gate import (
            inspect_floor_customer_handoff,
        )
        customer_handoff = inspect_floor_customer_handoff(claim)

    traces = {
        "same_view": _reason_map(
            claim.same_view_room_area_first_failure_codes
        ),
        "cross_view": _reason_map(
            claim.cross_view_room_area_first_failure_codes
        ),
        "physical_scale": _reason_map(
            claim.physical_scale_first_failure_codes
        ),
    }
    rows = []
    for room in claim.canonical_rooms:
        if not _clean(room.room_label):
            continue
        physical_id = str(room.physical_room_id)
        matching_floors = floors_by_room.get(str(room.canonical_room_id), [])
        floor = matching_floors[0] if len(matching_floors) == 1 else None
        metric_area = getattr(floor, "metric_area_m2", None)
        numeric_metric = (
            metric_area is not None
            and type(metric_area) in (int, float)
            and math.isfinite(float(metric_area))
            and float(metric_area) > 0
        )
        floor_quantity_id = _clean(
            getattr(floor, "metric_area_quantity_id", "") if floor else ""
        )
        linked_receipts = published_area_by_id.get(floor_quantity_id, [])
        metadata = getattr(linked_receipts[0], "metadata", None) if len(linked_receipts) == 1 else None
        linked_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        receipt_value = getattr(linked_receipts[0], "value", None) if len(linked_receipts) == 1 else None
        receipt_numeric = (
            type(receipt_value) in (int, float)
            and math.isfinite(receipt_value)
            and receipt_value > 0
        )
        owner_sha = _clean(getattr(floor, "source_sha256", "")) if floor else ""
        owner_revision = _clean(getattr(floor, "revision_id", "")) if floor else ""
        declared_face = _clean(linked_metadata.get("source_room_face_record_id"))
        declared_page = _clean(linked_metadata.get("page_no"))
        declared_snapshot = _clean(linked_metadata.get("room_snapshot_id"))
        firm_documented_receipt = (
            numeric_metric
            and bool(floor_quantity_id)
            and len(linked_receipts) == 1
            and _clean(getattr(linked_receipts[0], "family", "")) == "room_area"
            and _clean(getattr(linked_receipts[0], "authority", "")) in {
                "documented_dimension", "pdf_scaled"
            }
            and len(tuple(getattr(linked_receipts[0], "input_entity_ids", ()) or ())) == 1
            and (not declared_face or declared_face == _clean(getattr(floor, "source_room_face_record_id", "")))
            and (not declared_page or declared_page == _clean(getattr(floor, "page_id", "")))
            and (not declared_snapshot or declared_snapshot == _clean(getattr(floor, "snapshot_id", "")))
            and not tuple(getattr(linked_receipts[0], "blocking_reasons", ()) or ())
            and not bool(getattr(linked_receipts[0], "abstained", True))
            and _clean(getattr(linked_receipts[0], "status", "")).casefold() == "firm"
            and _clean(getattr(linked_receipts[0], "unit", "")).casefold() in {"m2", "m²"}
            and receipt_numeric
            and abs(receipt_value - float(metric_area)) <= 1e-9
            and bool(tuple(getattr(linked_receipts[0], "evidence_ids", ()) or ()))
            and bool(owner_sha)
            and bool(owner_revision)
            and _clean(linked_metadata.get("source_sha256")).lower() == owner_sha.lower()
            and _clean(linked_metadata.get("revision_id")) == owner_revision
        )
        metric_valid = bool(
            numeric_metric
            and (
                bool(getattr(floor, "metric_geometry_complete", False))
                or firm_documented_receipt
            )
        )
        label_trusted = bool(
            _clean(room.room_label_binding_record_id)
            and tuple(room.room_label_evidence_ids or ())
        )
        floor_reissues = [
            item for item in published_floor_by_source.get(floor_quantity_id, ())
            if _clean(item.metadata.get("canonical_floor_id")) == _clean(
                getattr(floor, "canonical_floor_id", "") if floor else ""
            )
        ]
        room_reissues = [
            item for item in published_room_by_source.get(floor_quantity_id, ())
            if _clean(item.metadata.get("canonical_room_id")) == _clean(room.canonical_room_id)
        ]
        if not room.geometry_complete or not room.source_room_face_record_id:
            gate = "SOURCE_ROOM_FACE"
        elif not label_trusted:
            gate = "ROOM_LABEL_BINDING"
        elif len(matching_floors) != 1:
            gate = "CANONICAL_FLOOR_OWNERSHIP"
        elif not metric_valid:
            gate = "METRIC_MEASUREMENT"
        elif not floor_quantity_id or len(floor_reissues) != 1:
            gate = "FLOOR_QUANTITY_PUBLICATION"
        elif len(room_reissues) != 1:
            gate = "CANONICAL_ROOM_AREA_REISSUE"
        else:
            # Source-owned FIRM canonical reissue is NOT yet a verified sealed
            # customer export, completeness claim, or frozen V2 score.
            floor_id = floor_reissues[0].quantity_id
            if (
                floor_id in customer_handoff["sealed_floor_area_quantity_ids"]
                and floor_id in customer_handoff[
                    "customer_verified_floor_area_quantity_ids"
                ]
            ):
                # An authenticated source-sealed draft is still unreviewed,
                # and this never claims an official frozen V2 score.
                gate = "CUSTOMER_REVIEW_ROW_VERIFIED_UNSCORED"
            else:
                gate = "SEALED_CUSTOMER_PROJECTION_UNVERIFIED"
        rows.append({
            "room_label": _clean(room.room_label),
            "physical_room_id": physical_id,
            "canonical_room_id": str(room.canonical_room_id),
            "source_room_face_record_id": str(room.source_room_face_record_id),
            "room_label_binding_record_id": (
                room.room_label_binding_record_id or None
            ),
            "source_page_id": str(room.page_id),
            "source_viewport_id": room.viewport_id,
            "geometry_complete": bool(room.geometry_complete),
            "area_page_pts2": float(room.area_page_pts2),
            "area_page_pts2_is_not_metric": True,
            "floor_match_count": len(matching_floors),
            "canonical_floor_id": (
                str(floor.canonical_floor_id) if floor else None
            ),
            "metric_area_m2": float(metric_area) if metric_valid else None,
            "metric_geometry_complete": bool(
                getattr(floor, "metric_geometry_complete", False)
            ) if floor else False,
            "firm_documented_area_receipt": bool(firm_documented_receipt),
            "floor_area_reissued_quantity_id": (
                floor_reissues[0].quantity_id if len(floor_reissues) == 1 else None
            ),
            "canonical_room_area_reissued_quantity_id": (
                room_reissues[0].quantity_id if len(room_reissues) == 1 else None
            ),
            "floor_area_source_sealed": (
                len(floor_reissues) == 1 and floor_reissues[0].quantity_id
                in customer_handoff["sealed_floor_area_quantity_ids"]
            ),
            "floor_area_customer_row_verified": (
                len(floor_reissues) == 1 and floor_reissues[0].quantity_id
                in customer_handoff["customer_verified_floor_area_quantity_ids"]
            ),
            "commercial_quantity_authority_flag": bool(
                getattr(floor, "commercial_quantity_authority", False)
            ) if floor else False,
            "metric_authority": (
                getattr(floor, "metric_area_authority", None) if floor else None
            ),
            "metric_quantity_id": (
                getattr(floor, "metric_area_quantity_id", None) if floor else None
            ),
            "first_unclosed_gate": gate,
            "source_first_failure_reasons": {
                name: values.get(physical_id, [])
                for name, values in traces.items()
            },
            "source_evidence_ids": list(room.evidence_ids),
            "room_label_evidence_ids": list(room.room_label_evidence_ids),
        })
    return {
        "canonical_room_count": len(claim.canonical_rooms),
        "canonical_room_status": str(claim.canonical_room_status),
        "canonical_room_reason_codes": list(claim.canonical_room_reason_codes),
        "canonical_room_source_pages": list(claim.canonical_room_source_pages),
        "canonical_wall_status": str(claim.canonical_wall_status),
        "canonical_wall_reason_codes": list(claim.canonical_wall_reason_codes),
        "canonical_wall_source_pages": list(claim.canonical_wall_source_pages),
        "canonical_floor_count": len(claim.canonical_floors),
        "canonical_floor_status": str(claim.canonical_floor_status),
        "canonical_floor_reason_codes": list(claim.canonical_floor_reason_codes),
        "labelled_room_count": len(rows),
        "rooms": sorted(rows, key=lambda r: (r["room_label"], r["physical_room_id"])),
        "room_area_quantity_evidence_count": len(
            claim.room_area_quantity_evidence
        ),
        "reissued_floor_area_quantity_count": sum(
            len(value) for value in published_floor_by_source.values()
        ),
        "reissued_canonical_room_area_quantity_count": sum(
            len(value) for value in published_room_by_source.values()
        ),
        "source_closed_floor_seal_quantity_count": len(
            customer_handoff["sealed_floor_area_quantity_ids"]
        ),
        "verified_floor_customer_row_count": customer_handoff[
            "customer_review_row_count"
        ],
        "floor_customer_projection_failure_type": customer_handoff[
            "customer_projection_failure_type"
        ],
        "commercial_estimator_approved": False,
        "benchmark_accuracy": None,
        "floor_finish_quantity_evidence_count": len(
            claim.floor_finish_quantity_evidence
        ),
        "ceiling_lining_quantity_evidence_count": len(
            claim.ceiling_lining_quantity_evidence
        ),
        "claim_reason_codes": list(claim.reason_codes),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", type=int, nargs="+", required=True)
    parser.add_argument("--topology-pages", type=int, nargs="+", required=True)
    parser.add_argument("--support-pages", type=int, nargs="+", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_sha = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if source_sha != args.expected_sha256.lower():
        raise RuntimeError("source SHA mismatch: refusing room inventory")
    from pb_live_physical_net_wall_integration import (
        collect_live_physical_net_wall_claim,
    )
    claim = collect_live_physical_net_wall_claim(
        args.pdf,
        pages=tuple(args.pages),
        topology_pages=tuple(args.topology_pages),
        room_area_support_pages=tuple(args.support_pages),
    )
    report = inspect_room_measurement_gates(claim)
    report["source_sha256"] = source_sha
    report["scope"] = {
        "pages_zero_indexed": args.pages,
        "topology_pages_zero_indexed": args.topology_pages,
        "support_pages_zero_indexed": args.support_pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print("GPT2_B03_ROOM_GATES", json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
