"""Read-only original-source room-area word/plan-scope FIRST-FAILURE census.

A literal source PDF '12.64 m²' text line is neither source room-area
measurement authority nor proof that a nearby wall ring owns that text.
This diagnostic never creates a physical room, EvidenceAtom, QuantityEvidence,
canonical floor, finish occurrence, customer row or benchmark mapping.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

_AREA_LINE = re.compile(r"^([0-9]{1,6}(?:\.[0-9]{1,6})?)\s*(m²|m2)$", re.IGNORECASE)


def _bbox(value):
    if type(value) not in (list, tuple) or len(value) != 4:
        raise ValueError("source_text_bbox_malformed")
    if any(type(v) not in (float, int) for v in value):
        raise ValueError("source_text_bbox_malformed")
    a = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in a) or a[2] <= a[0] or a[3] <= a[1]:
        raise ValueError("source_text_bbox_malformed")
    return a


def _contains(box, child):
    return box[0] <= child[0] and box[1] <= child[1] and child[2] <= box[2] and child[3] <= box[3]


def inspect_source_area_lines(words, viewports, *, source_sha256, revision_id, snapshot_id, page_id):
    """Retain ALL original candidate lines; do not elect a room/measurement.

    Input rows must come from the SAME producer's text-integrity and F.07
    receipts. Classification never seals inputs; replay verifies ownership.
    """
    if not (type(source_sha256) is str and len(source_sha256) == 64
            and all(c in "0123456789abcdefABCDEF" for c in source_sha256)
            and all(type(x) is str and x for x in (revision_id, snapshot_id, page_id))):
        raise ValueError("source_identity_missing_or_invalid")
    by_line = defaultdict(list)
    original_ids = set()
    for word in tuple(words):
        oid = getattr(word, "observation_id", None)
        if type(oid) is not str or not oid or oid != oid.strip() or oid in original_ids:
            raise ValueError("source_word_duplicate_or_invalid_identity")
        original_ids.add(oid)
        if getattr(word, "page_id", None) != page_id:
            raise ValueError("source_word_foreign_page")
        _bbox(getattr(word, "bbox", None))
        key = (getattr(word, "source_partition_id", None),
               getattr(word, "block_no", None), getattr(word, "line_no", None))
        if (type(key[0]) is not str or not key[0]
                or type(key[1]) is not int or key[1] < 0
                or type(key[2]) is not int or key[2] < 0
                or type(getattr(word, "word_no", None)) is not int
                or word.word_no < 0 or type(getattr(word, "text", None)) is not str):
            raise ValueError("source_word_profile_incomplete")
        by_line[key].append(word)
    scopes = []
    view_ids = set()
    for view in tuple(viewports):
        vid = getattr(view, "view_id", None)
        if type(vid) is not str or not vid or vid in view_ids:
            raise ValueError("source_viewport_id_duplicate_or_invalid")
        view_ids.add(vid)
        bbox = getattr(view, "bounding_box", None)
        # An unresolved F.07 view may have no bounds; do not invent a box.
        if bbox is None:
            continue
        scopes.append((vid, getattr(view, "view_type", None), _bbox(bbox)))

    candidates = []
    for (part, block, line), tokens in sorted(by_line.items()):
        ordered = sorted(tokens, key=lambda w: (w.word_no, w.observation_id))
        raw = " ".join(w.text.strip() for w in ordered)
        match = _AREA_LINE.fullmatch(raw)
        if match is None:
            continue
        numer = float(match.group(1))
        if not math.isfinite(numer) or numer <= 0.0:
            continue
        ordinals = [w.word_no for w in ordered]
        unique_order = len(set(ordinals)) == len(ordinals) and ordinals == list(
            range(ordinals[0], ordinals[-1] + 1))
        trusted = all(w.trusted is True for w in ordered)
        boxes = [_bbox(w.bbox) for w in ordered]
        bbox = (min(x[0] for x in boxes), min(x[1] for x in boxes),
                max(x[2] for x in boxes), max(x[3] for x in boxes))
        within = sorted(vid for vid, kind, box in scopes
                        if kind == "floor_plan" and _contains(box, bbox))
        nonplan = sorted(vid for vid, kind, box in scopes
                         if kind != "floor_plan" and _contains(box, bbox))
        first_failure = (
            "source_native_word_ordinal_conflict"
            if not unique_order else
            "source_area_literal_word_integrity_unavailable"
            if not trusted else
            "source_floor_plan_viewport_unavailable_or_ambiguous"
            if len(within) != 1 or nonplan else
            "source_physical_room_face_and_exact_area_line_owner_unproven"
        )
        candidates.append({
            "source_page_id": page_id,
            "source_partition_id": part,
            "block_no": block,
            "line_no": line,
            "source_word_numbers": ordinals,
            "source_text_observation_ids": [w.observation_id for w in ordered],
            "literal_original_text": raw,
            "original_line_bbox_pdf_pts": list(bbox),
            "candidate_printed_area_m2_not_measurement": numer,
            "source_text_integrity_all_words": trusted,
            "source_text_reason_codes": sorted({str(reason)
                for w in ordered for reason in (w.reason_codes or ())}),
            "containing_source_floor_plan_viewport_ids": within,
            "containing_competing_nonplan_viewport_ids": nonplan,
            "first_unclosed_gate": first_failure,
            "source_physical_room_face_authenticated": False,
            "room_area_measurement_authority_granted": False,
            "canonical_floor_metric_authority_granted": False,
            "quantity_evidence_published": False,
        })
    # Reuse the existing generic whole-line recognizer. A label is a source
    # candidate even when no SourceRoomFace exists; never attach by proximity
    # to a nearby area line, picture box or apparent wall.
    from pb_source_room_label_authority import _normalized_room_line
    label_candidates = []
    for (part, block, line), tokens in sorted(by_line.items()):
        ordered = sorted(tokens, key=lambda w: (w.word_no, w.observation_id))
        raw = " ".join(w.text.strip() for w in ordered)
        if _normalized_room_line(raw) is None:
            continue
        ordinals = [w.word_no for w in ordered]
        ordinal_complete = len(set(ordinals)) == len(ordinals) and (
            ordinals == list(range(ordinals[0], ordinals[-1] + 1)))
        trusted = all(w.trusted is True for w in ordered)
        boxes = [_bbox(w.bbox) for w in ordered]
        bbox = (min(x[0] for x in boxes), min(x[1] for x in boxes),
                max(x[2] for x in boxes), max(x[3] for x in boxes))
        plan_ids = sorted(vid for vid, kind, box in scopes
                          if kind == "floor_plan" and _contains(box, bbox))
        competing_ids = sorted(vid for vid, kind, box in scopes
                               if kind != "floor_plan" and _contains(box, bbox))
        gate = (
            "source_room_label_word_ordinal_conflict" if not ordinal_complete else
            "source_room_label_text_integrity_unavailable" if not trusted else
            "source_room_label_plan_viewport_unavailable_or_ambiguous"
            if len(plan_ids) != 1 or competing_ids else
            "source_room_face_and_exact_label_owner_unproven"
        )
        label_candidates.append({
            "source_page_id": page_id,
            "source_partition_id": part,
            "block_no": block,
            "line_no": line,
            "source_word_numbers": ordinals,
            "source_text_observation_ids": [w.observation_id for w in ordered],
            "literal_original_room_label": raw,
            "original_line_bbox_pdf_pts": list(bbox),
            "source_text_integrity_all_words": trusted,
            "source_text_reason_codes": sorted({str(reason)
                for w in ordered for reason in (w.reason_codes or ())}),
            "containing_source_floor_plan_viewport_ids": plan_ids,
            "containing_competing_nonplan_viewport_ids": competing_ids,
            "first_unclosed_gate": gate,
            "source_physical_room_face_authenticated": False,
            "area_annotation_to_label_binding_granted": False,
            "quantity_evidence_published": False,
        })
    return {
        "original_source_sha256": source_sha256,
        "source_revision_id": revision_id,
        "source_snapshot_id": snapshot_id,
        "source_page_id": page_id,
        "original_source_word_count": len(original_ids),
        "source_plan_viewport_count": sum(k == "floor_plan" for _, k, _ in scopes),
        "literal_area_candidate_count": len(candidates),
        "first_failure_counts": dict(sorted(Counter(row["first_unclosed_gate"] for row in candidates).items())),
        "literal_area_candidates": candidates,
        "literal_room_label_candidate_count": len(label_candidates),
        "literal_room_label_candidates": label_candidates,
        "label_first_failure_counts": dict(sorted(Counter(row["first_unclosed_gate"] for row in label_candidates).items())),
        "diagnostic_only": True,
        "published_quantities": [],
        "customer_rows": [],
        "benchmark_scored": False,
    }


def replay(source_bytes: bytes, *, page_number: int, raster_supports: bool = False):
    """Get text integrity and F.07 view receipts from one immutable source root."""
    if type(source_bytes) is not bytes or type(page_number) is not int or page_number < 1:
        raise ValueError("original_pdf_bytes_and_positive_page_required")
    from pb_source_material_semantic_authority import _trusted_words_by_page
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_viewport_segmentation import (
        ViewportSegmentationStatus, is_authoritative_derived_viewport,
        segment_source_page_viewports, validate_non_overlapping_viewports,
    )
    from pb_drawing_evidence_binding import DrawingViewType

    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1")
    original = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://original-source-view.pdf",
        page_ids=(str(page_number),),
    )
    revision_id = original.revision.revision_id
    if raster_supports:
        original = source.augment_with_raster_opening_primitives(
            revision_id, page_ids=(str(page_number),)
        )
    before = source.published_snapshot_for_revision(revision_id)
    if before is None or before != original or before.revision.source_sha256 != sha:
        raise ValueError("original_source_snapshot_unauthenticated")
    words = _trusted_words_by_page(source, before).get(str(page_number), ())
    raw_views = tuple(segment_source_page_viewports(
        source, revision_id=revision_id, page_id=str(page_number),
        physical_plan_view_shadow=True,
    ))
    nonoverlap = validate_non_overlapping_viewports(raw_views)
    all_reported_views = raw_views
    if not nonoverlap:
        # Do not pick first/smallest when two drawing views overlap.
        raw_views = ()
    safe_views = tuple(v for v in raw_views if
        v.view_type == DrawingViewType.FLOOR_PLAN.value and (
            v.status == ViewportSegmentationStatus.RESOLVED.value or
            (v.status == ViewportSegmentationStatus.DERIVED.value
             and is_authoritative_derived_viewport(v))))
    # Nonplan views remain as negative contenders, not positive plan.
    negative_views = tuple(v for v in raw_views if v.view_type != DrawingViewType.FLOOR_PLAN.value)
    output = inspect_source_area_lines(
        words, safe_views + negative_views, source_sha256=sha,
        revision_id=revision_id, snapshot_id=before.snapshot.snapshot_id,
        page_id=str(page_number),
    )
    if source.published_snapshot_for_revision(revision_id) != before:
        raise RuntimeError("original_source_snapshot_mutated_by_shadow")
    output["source_viewport_nonoverlap"] = bool(nonoverlap)
    output["source_raw_viewport_census_diagnostic_only"] = [
        {"view_id": v.view_id, "view_type": v.view_type, "status": v.status,
         "has_bbox": v.bounding_box is not None}
        for v in all_reported_views
    ]
    output["source_original_snapshot_unchanged"] = True
    output["source_plan_positive_viewport_ids"] = sorted(v.view_id for v in safe_views)
    output["foreign_or_ambiguous_viewport_used"] = False
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--raster-supports", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    original = args.pdf.read_bytes()
    if hashlib.sha256(original).hexdigest() != args.sha:
        raise ValueError("original_source_sha_mismatch")
    result = replay(original, page_number=args.page, raster_supports=args.raster_supports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "literal_area_candidate_count": result["literal_area_candidate_count"],
        "first_failure_counts": result["first_failure_counts"],
        "new_FIRM_quantity_count": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
