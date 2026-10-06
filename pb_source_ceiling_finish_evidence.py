"""Producer-owned ceiling-finish evidence from trusted native PDF text.

This adapter removes caller-supplied page text and text bboxes from the C15
ceiling-finish path. It consumes only the complete text-observation universe
retained by SourceVisibilityProducer and only words independently resolved by
PdfTextIntegrityAuthority.

Phrase reconstruction is intentionally narrow and fail-closed:
- words may combine only when producer receipts share exact page/block/line;
- every word in the reconstructed native line must resolve as trusted text;
- word_no values must be unique and contiguous;
- every participating word must lie fully inside the trusted viewport bbox;
- no proximity or nearest-neighbour grouping is used.

The output remains unscoped EvidenceAtom candidates. Room ownership is still
resolved separately by pb_ceiling_lining_scope_binder.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from pb_ceiling_lining_finish_evidence import (
    collect_unscoped_ceiling_finish_candidates,
)
from pb_ceiling_lining_quantity import iter_explicit_ceiling_finish_matches
from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE_CEILING_FINISH_METHOD = "producer_owned_pdf_text_integrity"


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _inside(
    bbox: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        bbox[0] >= outer[0] - tolerance
        and bbox[1] >= outer[1] - tolerance
        and bbox[2] <= outer[2] + tolerance
        and bbox[3] <= outer[3] + tolerance
    )


def _bbox(value: object) -> Optional[tuple[float, float, float, float]]:
    try:
        values = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if len(values) != 4:
        return None
    x0, y0, x1, y1 = values
    if x1 < x0 or y1 < y0:
        return None
    return (x0, y0, x1, y1)


def collect_source_owned_ceiling_finish_candidates(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[EvidenceAtom, ...]:
    """Collect explicit ceiling-finish candidates from producer-owned text only."""

    revision_id = _clean(context.current_revision_id)
    if (
        not revision_id
        or context.revision_id != context.current_revision_id
        or viewport.document_id != context.document_id
        or viewport.viewport_id not in context.trusted_viewport_ids()
        or viewport.status
        not in (ViewportResolutionStatus.RESOLVED, ViewportResolutionStatus.DERIVED)
        or int(page_no) not in context.trusted_page_numbers()
    ):
        return ()

    mapped_page = context.page_for_viewport(viewport.viewport_id)
    if mapped_page is not None and int(mapped_page) != int(page_no):
        return ()
    if _clean(viewport.page_id) != str(int(page_no)):
        return ()

    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is None:
        return ()
    if (
        published.revision.document_id != context.document_id
        or published.revision.revision_id != revision_id
        or published.revision.source_sha256 != context.source_sha256
        or int(page_no) not in set(published.coverage.decoded_pages)
    ):
        return ()

    authority = source_visibility_producer.text_integrity_authority()
    raster = None
    line_results: dict[
        tuple[str, int, int],
        list[tuple[int, object, object]],
    ] = {}

    # Iterate the complete producer-owned text universe. We deliberately do
    # not accept an observation-id subset from the caller.
    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = authority.resolve_text(selector)
        receipt = result.receipt
        if receipt is None or receipt.page_id != viewport.page_id:
            continue
        if (
            receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        key = (receipt.page_id, int(receipt.block_no), int(receipt.line_no))
        line_results.setdefault(key, []).append(
            (int(receipt.word_no), result, receipt)
        )

    atoms: list[EvidenceAtom] = []
    viewport_bbox = tuple(float(value) for value in viewport.bbox)

    for key in sorted(line_results):
        entries = line_results[key]
        word_numbers = [item[0] for item in entries]
        if len(word_numbers) != len(set(word_numbers)):
            continue
        ordered = sorted(entries, key=lambda item: item[0])
        ordered_numbers = [item[0] for item in ordered]
        if ordered_numbers != list(
            range(ordered_numbers[0], ordered_numbers[-1] + 1)
        ):
            continue

        # Reject the WHOLE native line unless every word is independently
        # source-authenticated. Native text remains preferred. For the same
        # narrow glyph/clip failures already admitted by room-label authority,
        # reuse producer-owned RasterTextCorroborationAuthority; arbitrary
        # integrity failures remain fail-closed.
        trusted_entries: list[tuple[str, object, object, Optional[str]]] = []
        line_failed = False
        admissible = {
            TEXT_GLYPH_MAPPING_UNVERIFIED,
            TEXT_CLIP_STATE_UNRESOLVED,
        }
        for _, result, receipt in ordered:
            trusted_text = (
                _clean(result.trusted_text)
                if (
                    result.status is EvidenceResolutionStatus.CORROBORATED
                    and _clean(result.trusted_text)
                )
                else ""
            )
            raster_record_id: Optional[str] = None
            if not trusted_text:
                reasons = tuple(result.reason_codes or ())
                reason_set = set(reasons)
                parent_observation_id = _clean(receipt.parent_observation_id)
                if not (
                    result.status is EvidenceResolutionStatus.ABSTAINED
                    and not bool(receipt.trusted)
                    and parent_observation_id
                    and TEXT_GLYPH_MAPPING_UNVERIFIED in reason_set
                    and reason_set.issubset(admissible)
                    and tuple(receipt.reason_codes or ()) == reasons
                ):
                    line_failed = True
                    break
                if raster is None:
                    raster = RasterTextCorroborationProducer.from_source_visibility_producer(
                        source_visibility_producer
                    )
                raster_result = raster.publish(
                    RasterTextCorroborationSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        observation_id=parent_observation_id,
                    )
                )
                if (
                    raster_result.status is not EvidenceResolutionStatus.CORROBORATED
                    or raster_result.record is None
                    or not _clean(raster_result.corroborated_text)
                ):
                    line_failed = True
                    break
                trusted_text = _clean(raster_result.corroborated_text)
                raster_record_id = _clean(raster_result.record.record_id)
            trusted_entries.append(
                (trusted_text, result, receipt, raster_record_id)
            )
        if line_failed or len(trusted_entries) != len(ordered):
            continue

        boxes = [_bbox(receipt.geometry) for _, _, receipt, _ in trusted_entries]
        if any(box is None for box in boxes):
            continue
        trusted_boxes = tuple(box for box in boxes if box is not None)
        if any(not _inside(box, viewport_bbox) for box in trusted_boxes):
            continue

        texts = [text for text, _, _, _ in trusted_entries]
        line_text = " ".join(texts)
        matches = iter_explicit_ceiling_finish_matches(line_text)
        if not matches:
            continue

        # Character offsets let each semantic match retain only its native word
        # geometry rather than the bbox of unrelated words on the same line.
        spans: list[tuple[int, int]] = []
        cursor = 0
        for text in texts:
            start = cursor
            end = start + len(text)
            spans.append((start, end))
            cursor = end + 1

        lower_line = line_text.casefold()
        for raw_match in matches:
            match_start = lower_line.find(raw_match.casefold())
            if match_start < 0:
                continue
            match_end = match_start + len(raw_match)
            selected_indexes = [
                index
                for index, (start, end) in enumerate(spans)
                if end > match_start and start < match_end
            ]
            if not selected_indexes:
                continue
            selected_boxes = [trusted_boxes[index] for index in selected_indexes]
            match_bbox = (
                min(box[0] for box in selected_boxes),
                min(box[1] for box in selected_boxes),
                max(box[2] for box in selected_boxes),
                max(box[3] for box in selected_boxes),
            )
            parent_ids = tuple(
                trusted_entries[index][2].parent_observation_id
                for index in selected_indexes
            )
            receipt_ids = tuple(
                trusted_entries[index][2].receipt_id
                for index in selected_indexes
            )
            raster_record_ids = tuple(
                record_id
                for index in selected_indexes
                for record_id in (trusted_entries[index][3],)
                if record_id
            )
            candidates = collect_unscoped_ceiling_finish_candidates(
                page_text=raw_match,
                document_id=published.revision.document_id,
                source_sha256=published.revision.source_sha256,
                revision_id=published.revision.revision_id,
                page_id=viewport.page_id,
                page_no=int(page_no),
                viewport_id=viewport.viewport_id,
                text_geometry=({"raw_text": raw_match, "bbox": match_bbox},),
                method=SOURCE_CEILING_FINISH_METHOD,
                confidence=1.0,
            )
            for candidate in candidates:
                metadata = dict(candidate.metadata or {})
                metadata.update(
                    {
                        "producer_owned_text_line": True,
                        "native_block_no": key[1],
                        "native_line_no": key[2],
                        "source_text_observation_ids": parent_ids,
                        "text_integrity_receipt_ids": receipt_ids,
                        "raster_text_corroboration_record_ids": raster_record_ids,
                    }
                )
                evidence_id = stable_contract_id(
                    "ev",
                    {
                        "kind": candidate.kind,
                        "method": SOURCE_CEILING_FINISH_METHOD,
                        "document_id": candidate.document_id,
                        "source_sha256": published.revision.source_sha256,
                        "revision_id": published.revision.revision_id,
                        "page_id": candidate.page_id,
                        "page_no": int(page_no),
                        "viewport_id": candidate.viewport_id,
                        "raw_text": candidate.raw_text,
                        "bbox": candidate.bbox,
                        "parent_observation_ids": parent_ids,
                        "receipt_ids": receipt_ids,
                        "raster_record_ids": raster_record_ids,
                    },
                )
                atoms.append(
                    replace(
                        candidate,
                        evidence_id=evidence_id,
                        metadata=metadata,
                    )
                )

    unique = {atom.evidence_id: atom for atom in atoms}
    return tuple(unique[key] for key in sorted(unique))


__all__ = [
    "SOURCE_CEILING_FINISH_METHOD",
    "collect_source_owned_ceiling_finish_candidates",
]
