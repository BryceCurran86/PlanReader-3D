"""Producer-owned page view-class adapter for Item 35.

Derives page-level view classes only from authenticated PDF text owned by
SourceVisibilityProducer. Caller page ids are addresses only; callers cannot
supply view names, keywords, classifications, or evidence ids.
"""
from __future__ import annotations

from collections.abc import Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_sheet_classification_v172 import classify_sheet_role
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    VIEW_KIND_UNKNOWN,
    ViewportViewClassAuthority,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)


_ROLE_TO_VIEW_KIND = {
    "FLOOR_PLAN": VIEW_KIND_FLOOR_PLAN,
    "ELEVATION": VIEW_KIND_ELEVATION,
    "DOOR_WINDOW_SCHEDULE": VIEW_KIND_SCHEDULE,
    "FINISH_SCHEDULE": VIEW_KIND_SCHEDULE,
}

_MIN_AUTHORITATIVE_CONFIDENCE = 0.90


def page_viewport_id(page_id: str) -> str:
    page = str(page_id or "").strip()
    if not page:
        raise ValueError("page_id must be non-empty")
    return f"page:{page}"


def build_source_page_view_class_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    page_ids: Sequence[str],
) -> ViewportViewClassAuthority:
    """Publish exact page view classes from producer-authenticated page text."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")

    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    producer = ViewportViewClassProducer.create()
    if published is None:
        return producer.authority()

    requested = tuple(
        sorted({str(page_id).strip() for page_id in page_ids if str(page_id).strip()})
    )
    if not requested:
        return producer.authority()

    text_authority = source_visibility_producer.text_integrity_authority()
    # Preserve authenticated page reading order. Observation ids are stable
    # content hashes, not a textual sequence; iterating them in hash order can
    # scramble source phrases such as "GROUND FLOOR PLAN" and incorrectly
    # downgrade a producer-authenticated title to the low-confidence "plan"
    # fallback. Geometry and the producer-owned text receipt provide the
    # deterministic source order without caller-authored classification hints.
    words_by_page: dict[str, list[tuple[float, float, int, str, str]]] = {
        page_id: [] for page_id in requested
    }

    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = text_authority.resolve_text(selector)
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or not result.trusted_text
            or result.receipt is None
        ):
            continue
        page_id = str(result.receipt.page_id)
        if page_id not in words_by_page:
            continue
        geometry = tuple(float(value) for value in result.receipt.geometry)
        x0 = geometry[0] if len(geometry) >= 4 else 0.0
        y0 = geometry[1] if len(geometry) >= 4 else 0.0
        sequence_number = (
            int(result.receipt.sequence_number)
            if result.receipt.sequence_number is not None
            else 2**31 - 1
        )
        words_by_page[page_id].append(
            (y0, x0, sequence_number, observation_id, str(result.trusted_text))
        )

    for page_id in requested:
        ordered_words = sorted(words_by_page[page_id])
        evidence = tuple(item[3] for item in ordered_words)
        if not ordered_words or not evidence:
            continue
        text = " ".join(item[4] for item in ordered_words)
        role, confidence, _discipline, _target = classify_sheet_role(text, text)
        if float(confidence) < _MIN_AUTHORITATIVE_CONFIDENCE:
            continue
        view_kind = _ROLE_TO_VIEW_KIND.get(str(role), VIEW_KIND_UNKNOWN)
        if view_kind == VIEW_KIND_UNKNOWN:
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
            evidence_observation_ids=evidence,
        )

    return producer.authority()


__all__ = [
    "build_source_page_view_class_authority",
    "page_viewport_id",
]
