"""Producer-owned source view-class adapter for Item 35.

Derives page-level and exact authenticated viewport view classes only from
producer-owned PDF evidence. Caller page ids are addresses only; callers cannot
supply view names, keywords, classifications, viewport ids, or evidence ids.
"""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
import math

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import _authenticated_viewports
from pb_sheet_classification_v172 import classify_sheet_role
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_DETAIL,
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    VIEW_KIND_SECTION,
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

_VIEW_TYPE_TO_VIEW_KIND = {
    DrawingViewType.FLOOR_PLAN.value: VIEW_KIND_FLOOR_PLAN,
    DrawingViewType.ELEVATION.value: VIEW_KIND_ELEVATION,
    DrawingViewType.SECTION.value: VIEW_KIND_SECTION,
    DrawingViewType.SCHEDULE.value: VIEW_KIND_SCHEDULE,
    DrawingViewType.DETAIL.value: VIEW_KIND_DETAIL,
}

_MIN_AUTHORITATIVE_CONFIDENCE = 0.90
_TITLE_EVIDENCE_MARGIN = 2.0


def page_viewport_id(page_id: str) -> str:
    page = str(page_id or "").strip()
    if not page:
        raise ValueError("page_id must be non-empty")
    return f"page:{page}"


def _producer_source_bytes(
    source_visibility_producer: SourceVisibilityProducer,
    *,
    revision_id: str,
    source_sha256: str,
) -> bytes | None:
    store = getattr(
        getattr(source_visibility_producer, "_producer", None),
        "_store",
        None,
    )
    by_revision = getattr(store, "source_bytes_by_revision", None) or {}
    payload = by_revision.get(str(revision_id))
    if payload is None:
        return None
    payload = bytes(payload)
    if hashlib.sha256(payload).hexdigest() != str(source_sha256):
        return None
    return payload


def _geometry_bbox(geometry: Sequence[float]) -> tuple[float, float, float, float] | None:
    try:
        values = tuple(float(value) for value in geometry)
    except (TypeError, ValueError):
        return None
    if len(values) < 4 or len(values) % 2 or not all(math.isfinite(v) for v in values):
        return None
    if len(values) == 4:
        x0, y0, x1, y1 = values
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    xs = values[0::2]
    ys = values[1::2]
    return (min(xs), min(ys), max(xs), max(ys))


def _center_inside(
    bbox: tuple[float, float, float, float],
    outer: Sequence[float],
    *,
    margin: float = _TITLE_EVIDENCE_MARGIN,
) -> bool:
    if len(outer) != 4:
        return False
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    try:
        x0, y0, x1, y1 = (float(value) for value in outer)
    except (TypeError, ValueError):
        return False
    return (
        min(x0, x1) - margin <= cx <= max(x0, x1) + margin
        and min(y0, y1) - margin <= cy <= max(y0, y1) + margin
    )


def build_source_page_view_class_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    page_ids: Sequence[str],
) -> ViewportViewClassAuthority:
    """Publish exact page and authenticated viewport view classes."""

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
    words_by_page: dict[
        str,
        list[tuple[str, str, tuple[float, ...]]],
    ] = {page_id: [] for page_id in requested}

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
        try:
            geometry = tuple(float(value) for value in result.receipt.geometry)
        except (TypeError, ValueError):
            geometry = ()
        words_by_page[page_id].append(
            (str(observation_id), str(result.trusted_text), geometry)
        )

    # Page-level classification remains the conservative fallback for physical
    # openings that do not carry a finer producer-authenticated viewport id.
    for page_id in requested:
        entries = words_by_page[page_id]
        words = [text for _observation_id, text, _geometry in entries]
        evidence = tuple(sorted({obs_id for obs_id, _text, _geometry in entries}))
        if not words or not evidence:
            continue
        text = " ".join(words)
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

    # F.07 can establish finer viewport ownership than a whole-page class.
    # Reuse only its producer-authenticated eligible viewports and attach the
    # exact trusted title observations whose geometry lies on that viewport's
    # title anchor. No viewport name guessing or caller-supplied class enters.
    payload = _producer_source_bytes(
        source_visibility_producer,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
    )
    if payload is None:
        return producer.authority()

    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return producer.authority()

    try:
        for page_id in requested:
            if not page_id.isdigit():
                continue
            page_index = int(page_id) - 1
            if page_index < 0 or page_index >= int(document.page_count):
                continue
            try:
                gate = _authenticated_viewports(
                    document.load_page(page_index),
                    page_number=int(page_id),
                )
            except Exception:
                gate = None
            if gate is None:
                continue
            _all_viewports, eligible = gate
            for viewport in eligible:
                view_kind = _VIEW_TYPE_TO_VIEW_KIND.get(
                    str(getattr(viewport, "view_type", "")),
                    VIEW_KIND_UNKNOWN,
                )
                if view_kind == VIEW_KIND_UNKNOWN:
                    continue
                title_bbox = tuple(getattr(viewport, "title_bbox", ()) or ())
                title_evidence = []
                for observation_id, _text, geometry in words_by_page.get(page_id, ()):
                    bbox = _geometry_bbox(geometry)
                    if bbox is not None and _center_inside(bbox, title_bbox):
                        title_evidence.append(observation_id)
                evidence = tuple(sorted(set(title_evidence)))
                if not evidence:
                    continue
                viewport_id = str(getattr(viewport, "view_id", "") or "").strip()
                if not viewport_id:
                    continue
                producer.publish(
                    ViewportViewClassSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        viewport_id=viewport_id,
                    ),
                    view_kind=view_kind,
                    evidence_observation_ids=evidence,
                )
    finally:
        document.close()

    return producer.authority()


__all__ = [
    "build_source_page_view_class_authority",
    "page_viewport_id",
]
