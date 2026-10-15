"""Read-only same-view H/V witness census from an existing authentic producer.

No source pixels, thresholds, topology, quantities, scale authority or commercial
publication are changed. All candidate numbers are diagnostic, NEVER FIRM.
Select by exact producer-issued source face IDs, never names/benchmark values.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Sequence

from pb_cross_view_room_area_authority import (
    _dimension_is_immediate_label_annotation,
    _figured_pair_scale_consistent,
    _line_inside_dimension_pair,
    _norm_label,
    _trusted_lines_for_page,
    _trusted_native_dimensions_for_page,
    _witness_systems_intersect,
)
from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_source_visibility_authority import SourceVisibilityProducer

# Audit boundedness is not opening-primitive authority. When exceeded, keep
# all authenticated input receipts and ABSTAIN rather than silently truncating.
_MAX_AUDITED_PAIRS = 20000


def _dimension_row(dimension: object) -> dict:
    first, second = dimension.endpoints_pt
    span_pt = math.hypot(second[0] - first[0], second[1] - first[1])
    metres = float(dimension.value_mm) / 1000.0
    diagnostic_ratio = (
        POINTS_PER_METRE_AT_1_1 * metres / span_pt
        if span_pt > 0 and metres > 0 and math.isfinite(span_pt)
        and math.isfinite(metres) else None
    )
    return {
        "dimension_id": dimension.dimension_id,
        "orientation": dimension.orientation,
        "value_mm": dimension.value_mm,
        "text_observation_id": dimension.text_observation_id,
        "text_receipt_id": dimension.text_receipt_id,
        "text_source_partition_id": dimension.text_source_partition_id,
        "text_block_no": dimension.text_block_no,
        "text_line_no": dimension.text_line_no,
        "text_word_no": dimension.text_word_no,
        "text_bbox_pdf_pts": dimension.text_bbox,
        "endpoints_pdf_pts": dimension.endpoints_pt,
        "dimension_line_observation_ids": dimension.dimension_line_observation_ids,
        "witness_observation_ids": dimension.witness_observation_ids,
        "witness_geometries_pdf_pts": dimension.witness_geometries,
        "inferred_ratio_diagnostic_only": diagnostic_ratio,
    }


def _pair_row(page_id: str, line: object, horizontal: object, vertical: object) -> dict:
    in_box = _line_inside_dimension_pair(line, horizontal, vertical)
    consistent = _figured_pair_scale_consistent(
        page_id=page_id, horizontal=horizontal, vertical=vertical,
    )
    witnessed = _witness_systems_intersect(horizontal, vertical)
    immediate = (
        _dimension_is_immediate_label_annotation(line, horizontal)
        and _dimension_is_immediate_label_annotation(line, vertical)
    )
    return {
        "horizontal_dimension_id": horizontal.dimension_id,
        "vertical_dimension_id": vertical.dimension_id,
        "label_inside_source_dimension_box": in_box,
        "existing_scale_consistency_gate": consistent,
        "existing_witness_intersection_gate": witnessed,
        "existing_immediate_native_label_ownership": immediate,
        "normal_path_eligible_diagnostic_only": in_box and consistent and witnessed,
        "fallback_path_eligible_diagnostic_only": immediate and consistent,
        "relative_ratio_difference_diagnostic_only": _ratio_difference(
            horizontal, vertical,
        ),
    }


def _ratio_difference(horizontal: object, vertical: object) -> float | None:
    left = _dimension_row(horizontal)["inferred_ratio_diagnostic_only"]
    right = _dimension_row(vertical)["inferred_ratio_diagnostic_only"]
    if left is None or right is None:
        return None
    lower = min(left, right)
    return (max(left, right) - lower) / lower if lower > 0 else None


def report_same_view_witness_census(
    *, source: SourceVisibilityProducer,
    rooms: LiveCanonicalRoomComposition,
    target_source_face_ids: Sequence[str],
) -> dict:
    """Report existing authenticated candidates, without minting a claim.

    The source/room producer identity must match before extracting any witnesses.
    A caller's target IDs only select report rows; they cannot create labels,
    rooms, dimensions, evidence, a source snapshot, or metric area authority.
    """
    if type(source) is not SourceVisibilityProducer or type(rooms) is not LiveCanonicalRoomComposition:
        raise TypeError("original source and canonical composition required")
    if (
        type(target_source_face_ids) not in (tuple, list)
        or not target_source_face_ids
        or any(type(x) is not str or not x or x != x.strip() for x in target_source_face_ids)
        or len(set(target_source_face_ids)) != len(target_source_face_ids)
    ):
        raise ValueError("unique original source-face receipt selectors required")

    universe = tuple(rooms.rooms)
    if not universe:
        return {"status": "ABSTAINED", "reason": "canonical_room_universe_empty", "rows": []}
    scopes = {
        (room.document_id, room.revision_id, room.source_sha256.lower(), room.snapshot_id)
        for room in universe
    }
    if len(scopes) != 1:
        return {"status": "ABSTAINED", "reason": "mixed_room_source_lineage", "rows": []}
    document_id, revision_id, source_sha, snapshot_id = next(iter(scopes))
    published = source.published_snapshot_for_revision(revision_id)
    if (
        published is None
        or published.revision.document_id != document_id
        or published.revision.revision_id != revision_id
        or published.revision.source_sha256.lower() != source_sha
        or published.snapshot.snapshot_id != snapshot_id
    ):
        return {"status": "ABSTAINED", "reason": "producer_source_lineage_mismatch", "rows": []}

    faces = Counter(room.source_room_face_record_id for room in universe)
    physicals = Counter(room.physical_room_id for room in universe)
    labels = Counter(
        (room.page_id, _norm_label(room.room_label))
        for room in universe
        if room.room_label and room.geometry_complete
    )
    rows: list[dict] = []
    for face_id in sorted(target_source_face_ids):
        owned = [r for r in universe if r.source_room_face_record_id == face_id]
        base = {"source_room_face_record_id": face_id,
                "document_id": document_id, "revision_id": revision_id,
                "source_sha256": source_sha, "snapshot_id": snapshot_id,
                "diagnostic_only": True, "quantity_published": False}
        if len(owned) != 1:
            rows.append({**base, "status": "ABSTAINED",
                         "reason": "source_face_owner_not_unique", "owner_count": len(owned)})
            continue
        room = owned[0]
        base.update({
            "physical_room_id": room.physical_room_id,
            "canonical_room_id": room.canonical_room_id,
            "room_label": room.room_label,
            "page_id": room.page_id,
            "viewport_id": room.viewport_id,
            "decision_scope_id": room.decision_scope_id,
            "room_label_evidence_ids": room.room_label_evidence_ids,
        })
        if (
            not room.geometry_complete
            or not room.physical_room_id
            or physicals[room.physical_room_id] != 1
            or faces[face_id] != 1
            or not room.room_label_binding_record_id
            or not room.room_label_evidence_ids
            or labels[(room.page_id, _norm_label(room.room_label))] != 1
        ):
            rows.append({**base, "status": "ABSTAINED",
                         "reason": "canonical_source_label_or_room_owner_ambiguous"})
            continue
        trusted_lines = tuple(
            line for line in _trusted_lines_for_page(
                source, revision_id=revision_id, page_id=room.page_id,
                candidate_labels=(room.room_label,),
            ) if _norm_label(line.text) == _norm_label(room.room_label)
        )
        if len(trusted_lines) != 1:
            rows.append({**base, "status": "ABSTAINED",
                         "reason": "original_trusted_label_line_not_unique",
                         "trusted_label_line_count": len(trusted_lines)})
            continue
        line = trusted_lines[0]
        dimensions = _trusted_native_dimensions_for_page(
            source, revision_id=revision_id, page_id=room.page_id,
            candidate_lines=(line,), view_type=DrawingViewType.FLOOR_PLAN.value,
        )
        horizontal = sorted(
            (d for d in dimensions if d.orientation == DimensionOrientation.HORIZONTAL.value),
            key=lambda d: d.dimension_id,
        )
        vertical = sorted(
            (d for d in dimensions if d.orientation == DimensionOrientation.VERTICAL.value),
            key=lambda d: d.dimension_id,
        )
        result = {
            **base, "status": "DIAGNOSTIC_ONLY",
            "trusted_label_line_observation_ids": line.observation_ids,
            "trusted_label_line_receipt_ids": line.receipt_ids,
            "trusted_label_line_bbox_pdf_pts": line.bbox,
            "trusted_label_source_partition_id": line.source_partition_id,
            "horizontal_dimensions": [_dimension_row(d) for d in horizontal],
            "vertical_dimensions": [_dimension_row(d) for d in vertical],
        }
        if len(horizontal) * len(vertical) > _MAX_AUDITED_PAIRS:
            rows.append({**result, "reason": "source_pair_audit_safety_bound",
                         "pair_count_possible": len(horizontal) * len(vertical),
                         "pairs": [], "producer_area_authority_proven": False})
            continue
        pairs = [
            _pair_row(room.page_id, line, h, v)
            for h in horizontal for v in vertical
        ]
        normal = [p for p in pairs if p["normal_path_eligible_diagnostic_only"]]
        eligible = normal if normal else [
            p for p in pairs if p["fallback_path_eligible_diagnostic_only"]
        ]
        # Local pair count is NOT global source-owner uniqueness, nor commercial
        # authority; the production producer still owns all admissibility gates.
        rows.append({
            **result, "pairs": pairs,
            "normal_source_pair_count": len(normal),
            "fallback_source_pair_count": sum(
                bool(p["fallback_path_eligible_diagnostic_only"]) for p in pairs
            ),
            "local_eligible_pair_count_diagnostic_only": len(eligible),
            "reason": (
                "local_unique_source_pair_candidate_NOT_FIRM" if len(eligible) == 1
                else "source_pair_ambiguous" if len(eligible) > 1
                else "source_pair_unavailable"
            ),
            "producer_area_authority_proven": False,
        })
    return {"status": "DIAGNOSTIC_ONLY", "reason": "read_only_source_witness_census",
            "source_sha256": source_sha, "snapshot_id": snapshot_id,
            "rows": rows}


__all__ = ["report_same_view_witness_census"]
