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
            and isinstance(metric_area, (int, float))
            and math.isfinite(float(metric_area))
            and float(metric_area) > 0
        )
        floor_quantity_id = _clean(
            getattr(floor, "metric_area_quantity_id", "") if floor else ""
        )
        linked_receipts = published_area_by_id.get(floor_quantity_id, [])
        linked_metadata = dict(getattr(linked_receipts[0], "metadata", {}) or {}) if len(linked_receipts) == 1 else {}
        declared_face = _clean(linked_metadata.get("source_room_face_record_id"))
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
            and not tuple(getattr(linked_receipts[0], "blocking_reasons", ()) or ())
            and not bool(getattr(linked_receipts[0], "abstained", True))
            and _clean(getattr(linked_receipts[0], "status", "")).casefold() == "firm"
            and _clean(getattr(linked_receipts[0], "unit", "")).casefold() in {"m2", "m²"}
            and getattr(linked_receipts[0], "value", None) is not None
            and math.isfinite(float(linked_receipts[0].value))
            and abs(float(linked_receipts[0].value) - float(metric_area)) <= 1e-9
            and bool(tuple(getattr(linked_receipts[0], "evidence_ids", ()) or ()))
            and _clean(
                dict(getattr(linked_receipts[0], "metadata", {}) or {}).get("source_sha256")
            ).lower() == _clean(getattr(floor, "source_sha256", "")).lower()
            and _clean(
                dict(getattr(linked_receipts[0], "metadata", {}) or {}).get("revision_id")
            ) == _clean(getattr(floor, "revision_id", ""))
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
        if not room.geometry_complete or not room.source_room_face_record_id:
            gate = "SOURCE_ROOM_FACE"
        elif not label_trusted:
            gate = "ROOM_LABEL_BINDING"
        elif len(matching_floors) != 1:
            gate = "CANONICAL_FLOOR_OWNERSHIP"
        elif not metric_valid:
            gate = "METRIC_MEASUREMENT"
        elif not (
            getattr(floor, "metric_area_quantity_id", None)
            and getattr(floor, "commercial_quantity_authority", False)
        ):
            gate = "FLOOR_QUANTITY_PUBLICATION"
        else:
            gate = "ROOM_FLOOR_QUANTITY_READY"
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
