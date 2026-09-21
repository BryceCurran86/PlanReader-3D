"""Source-authenticated page-view classification adapter for Item 35.

Builds producer-owned ViewportViewClassAuthority records from trusted PDF text
owned by SourceVisibilityProducer. A page is addressed as `page:<page_id>` only
after its source page identity and text observations are resolved by the producer.

Commercial floor-plan classification deliberately requires the strong
SheetClassification v1.7.2 FLOOR_PLAN tier (confidence >= 0.90). The generic
0.70 "contains plan" fallback is not strong enough to establish floor-plan
authority and therefore remains unclassified.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_sheet_classification_v172 import classify_sheet_role
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    ViewportViewClassAuthority,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)


def page_viewport_id(page_id: str) -> str:
    page = str(page_id or "").strip()
    if not page:
        raise ValueError("page_id must be non-empty")
    return f"page:{page}"


def build_source_page_view_class_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    page_ids: Sequence[str] | None = None,
) -> ViewportViewClassAuthority:
    """Classify producer-owned source pages from authenticated visible text."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")

    published = source_visibility_producer.published_snapshot_for_revision(
        str(revision_id)
    )
    producer = ViewportViewClassProducer.create()
    if published is None:
        return producer.authority()

    allowed_pages = None
    if page_ids is not None:
        allowed_pages = {
            str(page_id).strip()
            for page_id in page_ids
            if str(page_id).strip()
        }
        if not allowed_pages:
            return producer.authority()

    text_authority = source_visibility_producer.text_integrity_authority()
    words_by_page: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for observation_id in published.text_observation_ids:
        result = text_authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.receipt is None
            or not result.trusted_text
        ):
            continue
        page_id = str(result.receipt.page_id)
        if allowed_pages is not None and page_id not in allowed_pages:
            continue
        words_by_page[page_id].append(
            (str(observation_id), str(result.trusted_text))
        )

    for page_id in sorted(words_by_page, key=lambda value: int(value) if value.isdigit() else value):
        entries = words_by_page[page_id]
        text_content = " ".join(text for _obs_id, text in entries)
        role, confidence, _discipline, _target = classify_sheet_role(
            "",
            text_content,
        )

        view_kind = None
        if role == "FLOOR_PLAN" and float(confidence) >= 0.90:
            view_kind = VIEW_KIND_FLOOR_PLAN
        elif role == "ELEVATION" and float(confidence) >= 0.90:
            view_kind = VIEW_KIND_ELEVATION
        elif role in {"DOOR_WINDOW_SCHEDULE", "FINISH_SCHEDULE"} and float(confidence) >= 0.95:
            view_kind = VIEW_KIND_SCHEDULE

        if view_kind is None:
            continue

        producer.publish(
            ViewportViewClassSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                viewport_id=page_viewport_id(page_id),
            ),
            view_kind=view_kind,
            evidence_observation_ids=tuple(
                sorted(obs_id for obs_id, _text in entries)
            ),
        )

    return producer.authority()


__all__ = [
    "build_source_page_view_class_authority",
    "page_viewport_id",
]
