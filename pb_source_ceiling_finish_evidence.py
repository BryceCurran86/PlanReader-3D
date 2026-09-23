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

        # Reject the WHOLE native line if any word is not trusted. Otherwise
        # omission of an unsafe word could fabricate a semantic phrase.
        if any(
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or not _clean(result.trusted_text)
            for _, result, _ in ordered
        ):
            continue

        boxes = [_bbox(receipt.geometry) for _, _, receipt in ordered]
        if any(box is None for box in boxes):
            continue
        trusted_boxes = tuple(box for box in boxes if box is not None)
        if any(not _inside(box, viewport_bbox) for box in trusted_boxes):
            continue

        texts = [_clean(result.trusted_text) for _, result, _ in ordered]
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
                ordered[index][2].parent_observation_id
                for index in selected_indexes
            )
            receipt_ids = tuple(
                ordered[index][2].receipt_id
                for index in selected_indexes
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
