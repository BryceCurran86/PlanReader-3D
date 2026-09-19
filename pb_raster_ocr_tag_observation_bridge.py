"""pb_raster_ocr_tag_observation_bridge.py -- Item 35 PR 2: bridges portable
raster OCR evidence (pb_portable_raster_ocr_authority.OCRLine) into
authenticated TagObservations (pb_source_opening_candidate_authority),
via SourceObservationAuthority's existing derived-observation publish
path (pb_source_observation_authority.SourceObservationProducer.
publish_derived_observation).

This is not a new authority and does not bypass any existing seal. It
turns real OCR text into a genuine, lineage-tracked, content-addressed
SourceObservationRecord (observation_kind="ocr_text", already one of
VALID_TAG_OBSERVATION_KINDS in pb_source_opening_candidate_authority --
no change needed there), anchored to the always-published
native_pdf_page observation for its page as parent (present even on a
fully-raster page with zero other native content), and then wraps it
with TagObservation.from_source_observation() completely unmodified.

Requirements enforced structurally, not just documented:

- OCR confidence never enters this bridge's decision path at all --
  TagObservation carries no confidence field, and this module reads
  OCRLine.confidence only to break ties when deduplicating repeat
  detections of one physical mark, never to gate whether an observation
  gets published.
- Text occurrence alone never becomes physical existence: this module
  produces TagObservations only -- it creates no
  PhysicalOpeningCandidateRecord, no OpeningTagBindingResult, and calls
  no identity-resolution function. Turning a TagObservation into bound
  identity still requires the unmodified OpeningIdentityResolver /
  authenticate_tag_binding_evidence() path exactly as before this module
  existed.
- Viewport class and crop state are authenticated before any OCR text
  from that viewport can be published: the caller must supply an
  AuthenticatedViewportDecision already CORROBORATED by
  authenticate_viewport_decision(), which itself guarantees (via that
  function's own validated construction, enforced by
  AuthenticatedViewportDecision.__post_init__) view_kind ==
  VIEW_KIND_FLOOR_PLAN and an uncropped boundary. A schedule, detail, or
  elevation viewport -- or a cropped one -- cannot reach CORROBORATED
  there, so it cannot reach this bridge either; passing a non-
  CORROBORATED decision here returns no observations at all rather than
  silently publishing anyway.
- Duplicate detections of the same immutable physical mark (e.g. the
  same real "D-1" stamp recognized by two different preprocessing passes
  or backends, landing at very close but not always identical bbox
  coordinates) collapse to one observation before publishing, so they
  cannot later look like two physical instances.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Set, Tuple

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import OCRLine
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthority,
    SourceObservationProducer,
)
from pb_source_opening_candidate_authority import AuthenticatedViewportDecision, TagObservation

__all__ = [
    "OCR_TAG_OBSERVATION_KIND",
    "OCR_TAG_OBSERVATION_ORIGIN_KIND",
    "publish_ocr_lines_as_tag_observations",
]

OCR_TAG_OBSERVATION_KIND = "ocr_text"
OCR_TAG_OBSERVATION_ORIGIN_KIND = "ocr"

# A few points, not a fixed pixel constant tied to any one DPI: multiple
# preprocessing passes/backends detecting the SAME physical mark have been
# observed (this project, real source data) to land within single-digit
# points of each other in bbox_pt space, never overlapping exactly. This
# threshold recognizes repeat detections of one mark; it never merges two
# genuinely different marks, which this project's real short architectural
# tags are never closer than roughly a line-width apart even at their
# closest (confirmed empirically: nearest distinct-tag centers on a real
# source page were >10pt apart).
_DEDUPE_DISTANCE_PT = 6.0


def _centroid(line: OCRLine) -> Tuple[float, float]:
    x0, y0, x1, y1 = line.bbox_pt
    return (0.5 * (x0 + x1), 0.5 * (y0 + y1))


def _dedupe_ocr_lines(lines: Sequence[OCRLine]) -> List[OCRLine]:
    """Collapse repeat detections of one physical mark to a single
    OCRLine (highest confidence first, ties broken by input order).
    Distinct text is never merged regardless of geometric proximity --
    this recognizes re-detection of the SAME mark, not nearby marks."""
    ordered = sorted(
        enumerate(lines),
        key=lambda item: (-(item[1].confidence if item[1].confidence is not None else 1.0), item[0]),
    )
    kept: List[OCRLine] = []
    for _, line in ordered:
        text_norm = line.text.strip().upper()
        cx, cy = _centroid(line)
        if any(
            existing.text.strip().upper() == text_norm
            and math.hypot(cx - _centroid(existing)[0], cy - _centroid(existing)[1]) <= _DEDUPE_DISTANCE_PT
            for existing in kept
        ):
            continue
        kept.append(line)
    return kept


def publish_ocr_lines_as_tag_observations(
    *,
    producer: SourceObservationProducer,
    authority: SourceObservationAuthority,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    base_snapshot_id: str,
    base_snapshot_observation_ids: Sequence[str],
    page_id: str,
    page_observation_id: str,
    source_partition_id: str,
    viewport_decision: AuthenticatedViewportDecision,
    ocr_lines: Sequence[OCRLine],
) -> Tuple[Tuple[TagObservation, ...], str]:
    """Publish deduplicated OCR lines as authenticated TagObservations.

    Returns (tag_observations, final_snapshot_id). Returns ((), base_snapshot_id)
    unchanged if viewport_decision is not CORROBORATED, or if no lines
    survive filtering/deduplication -- never raises for those cases, since
    "no evidence reached the bar" is an ordinary, expected outcome here,
    not a caller error.

    `final_snapshot_id` is the snapshot every one of the returned
    TagObservations -- and any PhysicalOpeningCandidateRecord this caller
    wants to bind them against -- must be resolved/scoped against:
    publish_derived_observation clones all prior observations forward
    into each new snapshot, so the final snapshot in the chain contains
    everything (original native observations plus every published OCR
    one), but a candidate built against an EARLIER snapshot id will not
    scope-match a tag published into a LATER one.
    """
    if viewport_decision.status != EvidenceResolutionStatus.CORROBORATED:
        return (), base_snapshot_id

    deduped = _dedupe_ocr_lines([line for line in ocr_lines if line.text.strip()])
    if not deduped:
        return (), base_snapshot_id

    known_ids: Set[str] = set(base_snapshot_observation_ids)
    current_snapshot_id = base_snapshot_id
    derived_ids: List[str] = []

    for line in deduped:
        text_norm = line.text.strip()
        primitive_ref = (
            f"ocr_text:{round(line.bbox_pt[0], 3)}:{round(line.bbox_pt[1], 3)}:{text_norm}"
        )
        snapshot = producer.publish_derived_observation(
            document_id=document_id,
            revision_id=revision_id,
            base_snapshot_id=current_snapshot_id,
            page_id=page_id,
            source_partition_id=source_partition_id,
            observation_kind=OCR_TAG_OBSERVATION_KIND,
            source_primitive_ref=primitive_ref,
            origin_kind=OCR_TAG_OBSERVATION_ORIGIN_KIND,
            parent_observation_ids=(page_observation_id,),
            raw_text=text_norm,
            geometry=line.bbox_pt,
            viewport_id=viewport_decision.viewport.view_id,
        )
        current_snapshot_id = snapshot.snapshot_id
        new_ids = set(snapshot.observation_ids) - known_ids
        known_ids |= new_ids
        # Exactly one new id per publish call, except when this exact
        # (text, geometry) payload was already published earlier in this
        # same loop (a true duplicate slipped past _dedupe_ocr_lines'
        # distance tolerance by landing at an identical, not just close,
        # bbox) -- publish_derived_observation is idempotent for that
        # case and contributes zero new ids, which is correct: nothing
        # further to track for an already-published mark.
        if len(new_ids) == 1:
            derived_ids.append(next(iter(new_ids)))

    tags: List[TagObservation] = []
    for observation_id in derived_ids:
        res = authority.resolve(
            ObservationSelector(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=current_snapshot_id,
                observation_id=observation_id,
            )
        )
        if res.status == EvidenceResolutionStatus.CORROBORATED and res.observation is not None:
            tags.append(
                TagObservation.from_source_observation(
                    res.observation, viewport_id=viewport_decision.viewport.view_id
                )
            )

    return tuple(tags), current_snapshot_id
