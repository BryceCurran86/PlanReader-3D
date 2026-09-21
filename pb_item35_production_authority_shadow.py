"""Diagnostic-only Item 35 authority execution for the live PDF extractor.

This module makes the source-authenticated Item 35 chain execute on production
PDF bytes without changing any commercial prediction.  It intentionally
reports the current fail-closed state:

source PDF bytes
-> SourceVisibilityProducer
-> SemanticOpeningEnumerationAuthority
-> semantic inventory completeness adapter
-> GenericOpeningCountAuthority diagnostic resolve

The semantic completeness adapter is intentionally unsealed until a stronger
authority proves exhaustive physical-opening-universe coverage, so commercial
count publication remains blocked.  This module must never modify extractor
predictions, benchmark gold, or expected quantities.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import fitz

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
)
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_page_view_class_source_adapter import (
    build_source_page_view_class_authority,
    page_viewport_id,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_opening_candidate_authority import authenticate_viewport_decision
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassSelector,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION = "1.0.0"


def empty_item35_authority_shadow(*, reason: str) -> dict[str, Any]:
    return {
        "schema_version": ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION,
        "status": "abstained",
        "reason": str(reason or "unavailable"),
        "document_id": None,
        "revision_id": None,
        "source_sha256": None,
        "snapshot_id": None,
        "visible_observation_count": 0,
        "semantic_opening_count": 0,
        "support_observation_count": 0,
        "residual_visible_observation_count": 0,
        "structural_enumeration_complete": False,
        "physical_opening_universe_complete": False,
        "semantic_reason_codes": [],
        "semantic_record_id": None,
        "semantic_opening_record_ids": [],
        "representative_observation_ids": [],
        "generic_count_status": "abstained",
        "generic_count_reason_codes": [],
        "generic_count": None,
        "commercial_count_unlocked": False,
        "ocr_tag_observation_count": 0,
        "schedule_binding_statuses": [],
        "classified_opening_count": 0,
        "opening_family_counts": {},
        "opening_mark_counts": {},
        "opening_mark_predictions": {},
    }



def _augment_floor_plan_ocr_tags(
    *,
    source: SourceVisibilityProducer,
    revision_id: str,
    payload: bytes,
    page_ids: Sequence[str],
) -> int:
    """Run producer-owned OCR only on source-authenticated floor-plan pages."""

    tag_count = 0
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        for raw_page_id in page_ids:
            page_id = str(raw_page_id)
            published = source.published_snapshot_for_revision(revision_id)
            if published is None:
                break

            view_authority = build_source_page_view_class_authority(
                source_visibility_producer=source,
                revision_id=revision_id,
                page_ids=(page_id,),
            )
            viewport_id = page_viewport_id(page_id)
            selector = ViewportViewClassSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                viewport_id=viewport_id,
            )
            try:
                page_index = int(page_id) - 1
            except (TypeError, ValueError):
                continue
            if page_index < 0 or page_index >= int(pdf.page_count):
                continue
            page = pdf.load_page(page_index)
            rect = page.rect
            viewport = SegmentedViewport(
                view_id=viewport_id,
                page_number=page_index + 1,
                view_type=VIEW_KIND_FLOOR_PLAN,
                label="SOURCE FLOOR PLAN PAGE",
                title_bbox=(0.0, 0.0, 0.0, 0.0),
                bounding_box=(0.0, 0.0, float(rect.width), float(rect.height)),
                status="resolved",
                boundary_source="producer_page_scope",
                confidence=1.0,
            )
            decision = authenticate_viewport_decision(
                viewport=viewport,
                view_class_authority=view_authority,
                selector=selector,
            )
            tags, _updated = source.augment_with_raster_ocr_tags(
                revision_id,
                viewport_decision=decision,
            )
            tag_count += len(tags)
    finally:
        pdf.close()
    return tag_count


def _publish_schedule_bindings(
    *,
    source: SourceVisibilityProducer,
    semantic_record,
    decision_scope_id: str,
) -> tuple[object, tuple[dict[str, Any], ...]]:
    """Resolve source-owned opening->tag->schedule bindings for semantic members."""

    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    published = source.published_snapshot_for_revision(semantic_record.revision_id)
    if published is None:
        return binder.authority(), ()

    statuses: list[dict[str, Any]] = []
    seen_opening_records: set[str] = set()
    for observation_id in semantic_record.representative_observation_ids:
        result = binder.publish_scope(
            opening_selector=ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            ),
            decision_scope_id=decision_scope_id,
        )
        record = result.record
        opening_record_id = (
            str(record.opening_record_id)
            if record is not None
            else ""
        )
        if opening_record_id and opening_record_id in seen_opening_records:
            continue
        if opening_record_id:
            seen_opening_records.add(opening_record_id)
        statuses.append(
            {
                "status": str(result.status.value),
                "reason_codes": list(result.reason_codes),
                "opening_record_id": opening_record_id or None,
                "tag_mark": (str(record.tag_mark) if record is not None else None),
                "schedule_page_id": (
                    str(record.schedule_page_id) if record is not None else None
                ),
                "schedule_row_width_mm": (
                    int(record.schedule_row_width_mm)
                    if record is not None and record.schedule_row_width_mm is not None
                    else None
                ),
                "schedule_row_height_mm": (
                    int(record.schedule_row_height_mm)
                    if record is not None and record.schedule_row_height_mm is not None
                    else None
                ),
            }
        )
    return binder.authority(), tuple(statuses)


def collect_item35_authority_shadow(
    pdf_path: Path | str,
    *,
    document_id: str | None = None,
    pages: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Execute Item 35 authority infrastructure without publishing quantities."""

    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return empty_item35_authority_shadow(reason="source_unavailable")

    payload = path.read_bytes()
    if not payload:
        return empty_item35_authority_shadow(reason="source_unavailable")

    doc_id = str(document_id or f"file:{path.name}").strip()
    if not doc_id:
        return empty_item35_authority_shadow(reason="document_id_unavailable")

    source = SourceVisibilityProducer(
        producer_method="planreader_live_item35_shadow",
        producer_version=ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=doc_id,
        source_bytes=payload,
        source_locator=str(path),
    )

    if pages is None:
        scoped_page_ids = None
        decision_scope_id = f"item35:document:{published.revision.revision_id}"
        scoped_page_ids = tuple(str(page) for page in published.coverage.decoded_pages)
    else:
        scoped_page_ids = tuple(
            str(int(page_index) + 1)
            for page_index in sorted({int(value) for value in pages})
        )
        if not scoped_page_ids:
            return empty_item35_authority_shadow(reason="page_scope_unavailable")
        decision_scope_id = (
            f"item35:pages:{published.revision.revision_id}:"
            + ",".join(scoped_page_ids)
        )
        published = source.augment_with_raster_visible_segments(
            published.revision.revision_id,
            page_ids=scoped_page_ids,
        )
    # OCR tags must enter the same immutable source snapshot before semantic
    # opening and commercial-binding authorities are composed.
    ocr_tag_count = _augment_floor_plan_ocr_tags(
        source=source,
        revision_id=published.revision.revision_id,
        payload=payload,
        page_ids=scoped_page_ids,
    )
    published = source.published_snapshot_for_revision(
        published.revision.revision_id
    ) or published

    semantic_producer = (
        SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    )
    if pages is None:
        semantic = semantic_producer.publish_document_scope(
            revision_id=published.revision.revision_id,
            decision_scope_id=decision_scope_id,
        )
    else:
        semantic = semantic_producer.publish_page_scope(
            revision_id=published.revision.revision_id,
            decision_scope_id=decision_scope_id,
            page_ids=scoped_page_ids,
        )

    shadow = empty_item35_authority_shadow(reason="semantic_inventory_unavailable")
    shadow.update(
        {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "visible_observation_count": (
                len(semantic.record.visible_observation_ids)
                if semantic.record is not None
                else 0
            ),
            "ocr_tag_observation_count": int(ocr_tag_count),
        }
    )

    if semantic.record is not None:
        record = semantic.record
        shadow.update(
            {
                "status": (
                    "conflict"
                    if str(semantic.status.value) == "conflict"
                    else "evidence_present"
                ),
                "reason": "semantic_inventory_resolved",
                "semantic_opening_count": len(record.physical_opening_record_ids),
                "support_observation_count": len(
                    record.opening_support_observation_ids
                ),
                "residual_visible_observation_count": len(
                    record.residual_visible_observation_ids
                ),
                "structural_enumeration_complete": bool(
                    record.structural_enumeration_complete
                ),
                "physical_opening_universe_complete": bool(
                    record.physical_opening_universe_complete
                ),
                "semantic_reason_codes": list(record.reason_codes),
                "semantic_record_id": record.record_id,
                "semantic_opening_record_ids": list(
                    record.physical_opening_record_ids
                ),
                "representative_observation_ids": list(
                    record.representative_observation_ids
                ),
            }
        )
    else:
        shadow["semantic_reason_codes"] = list(semantic.reason_codes)

    # Exercise the commercial count gate against the same real source-derived
    # evidence. The semantic adapter intentionally remains commercially
    # unsealed today, so the expected safe outcome is ABSTAINED.
    completeness = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        decision_scope_id=decision_scope_id,
        page_ids=scoped_page_ids,
        optional_content_known_visible=False,
    )
    view_authority = build_source_page_view_class_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(
            scoped_page_ids
            if scoped_page_ids is not None
            else tuple(str(page) for page in published.coverage.decoded_pages)
        ),
    )
    binding_authority = None
    binding_statuses: tuple[dict[str, Any], ...] = ()
    if semantic.record is not None:
        binding_authority, binding_statuses = _publish_schedule_bindings(
            source=source,
            semantic_record=semantic.record,
            decision_scope_id=decision_scope_id,
        )
    shadow["schedule_binding_statuses"] = list(binding_statuses)
    shadow["classified_opening_count"] = sum(
        1 for item in binding_statuses if item.get("status") == "corroborated"
    )

    generic = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=completeness,
        physical_opening_authority=PhysicalOpeningAuthority(source.authority()),
        viewport_view_class_authority=view_authority,
        schedule_binding_authority=binding_authority,
    )
    generic_result = generic.publish(
        GenericOpeningCountSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=decision_scope_id,
        )
    )
    shadow["generic_count_status"] = str(generic_result.status.value)
    shadow["generic_count_reason_codes"] = list(generic_result.reason_codes)
    shadow["generic_count"] = (
        int(generic_result.record.count)
        if generic_result.record is not None
        else None
    )
    shadow["commercial_count_unlocked"] = bool(generic_result.record is not None)

    family_counts: dict[str, int] = {}
    for family in ("window", "door"):
        result = generic.publish(
            GenericOpeningCountSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                decision_scope_id=decision_scope_id,
                opening_family=family,
            )
        )
        if result.record is not None:
            family_counts[family] = int(result.record.count)
    shadow["opening_family_counts"] = family_counts

    mark_counts: dict[str, int] = {}
    marks = sorted(
        {
            str(item.get("tag_mark") or "").strip().upper()
            for item in binding_statuses
            if item.get("status") == "corroborated"
            and str(item.get("tag_mark") or "").strip()
        }
    )
    for mark in marks:
        result = generic.publish(
            GenericOpeningCountSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                decision_scope_id=decision_scope_id,
                opening_mark=mark,
            )
        )
        if result.record is not None:
            mark_counts[mark] = int(result.record.count)
    shadow["opening_mark_counts"] = mark_counts

    mark_predictions: dict[str, dict[str, Any]] = {}
    for mark, count in mark_counts.items():
        material = [
            item
            for item in binding_statuses
            if item.get("status") == "corroborated"
            and str(item.get("tag_mark") or "").strip().upper() == mark
        ]
        dimensions = {
            (
                int(item["schedule_row_width_mm"]),
                int(item["schedule_row_height_mm"]),
            )
            for item in material
            if item.get("schedule_row_width_mm") is not None
            and item.get("schedule_row_height_mm") is not None
        }
        # A classified mark with missing or competing schedule dimensions is
        # not a fully measurable opening type; keep the count diagnostic only.
        if len(dimensions) != 1:
            continue
        width_mm, height_mm = next(iter(dimensions))
        normalized = mark.upper()
        if normalized.startswith("W"):
            trade_type = "windows"
        elif normalized.startswith("D") and not normalized.startswith("DW"):
            trade_type = "doors"
        else:
            continue
        mark_predictions[mark] = {
            "quantity": int(count),
            "unit": "NO",
            "trade_type": trade_type,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "authority": "item35_generic_opening_count",
        }
    shadow["opening_mark_predictions"] = mark_predictions
    return shadow


__all__ = [
    "ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION",
    "collect_item35_authority_shadow",
    "empty_item35_authority_shadow",
]
