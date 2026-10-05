"""Producer-owned material schedule and finish-semantic authority.

This module lifts material/finish schedule semantics onto the same immutable
source lineage used by physical PlanReader authorities. It does not create a
physical surface or publish a quantity.

Definitions are admitted only from authenticated SCHEDULE / LEGEND /
SPECIFICATION viewports produced by the source PDF. Drawing occurrences are
admitted only inside independently authenticated non-schedule viewports and
only for codes already confirmed by the schedule universe.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_material_schedule_v1222 import (
    _compatible_descriptions,
    _defined_codes_in_text,
    parse_schedule_text,
    semantic_finish_from_schedule_entry,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION = "1.0.0"

SOURCE_MATERIAL_DEFINITION_RESOLVED = "source_material_definition_resolved"
SOURCE_MATERIAL_DEFINITION_UNAVAILABLE = "source_material_definition_unavailable"
SOURCE_MATERIAL_DEFINITION_CONFLICT = "source_material_definition_conflict"
SOURCE_MATERIAL_SCOPE_RESOLVED = "source_material_occurrence_scope_resolved"
SOURCE_MATERIAL_SCOPE_UNAVAILABLE = "source_material_occurrence_scope_unavailable"
SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE = "source_material_source_integrity_failure"
SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED = "source_material_viewport_unauthenticated"

_SCHEDULE_VIEW_TYPES = frozenset(
    {
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
    }
)
_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class SourceMaterialDefinitionSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    code: str

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id", "code"):
            _required(getattr(self, name), name)

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.code.strip().upper(),
        )


@dataclass(frozen=True)
class SourceMaterialOccurrenceSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "viewport_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
        )


@dataclass(frozen=True)
class SourceMaterialDefinitionRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    code: str
    description: str
    substrate: str
    finish: str
    semantic_finish: str
    source_definition_ids: tuple[str, ...]
    source_page_ids: tuple[str, ...]
    source_viewport_ids: tuple[str, ...]
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialDefinitionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[SourceMaterialDefinitionRecord] = None
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialOccurrenceRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    code: str
    semantic_finish: str
    definition_record_id: str
    bbox_pdf_pts: tuple[float, float, float, float]
    raw_text: str
    source_evidence_id: str
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialOccurrenceScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope_complete: bool
    records: tuple[SourceMaterialOccurrenceRecord, ...]
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


def _definition_blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> SourceMaterialDefinitionResult:
    return SourceMaterialDefinitionResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(r for r in reasons if r)),
        record=None,
    )


def _scope_blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> SourceMaterialOccurrenceScopeResult:
    return SourceMaterialOccurrenceScopeResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(r for r in reasons if r)),
        scope_complete=False,
        records=(),
    )


def _viewport_is_authoritative(
    viewport: SegmentedViewport,
    *,
    sibling_non_overlapping: bool,
) -> bool:
    return bool(
        viewport.bounding_box is not None
        and (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            or (
                sibling_non_overlapping
                and is_authoritative_derived_viewport(viewport)
            )
        )
    )


@dataclass(frozen=True)
class _TrustedTextWord:
    observation_id: str
    page_id: str
    text: str
    bbox: tuple[float, float, float, float]
    block_no: int
    line_no: int
    word_no: int
    trusted: bool
    reason_codes: tuple[str, ...]


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _bbox_intersects(
    left: Sequence[float],
    right: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return not (
        float(left[2]) <= float(right[0]) + tolerance
        or float(right[2]) <= float(left[0]) + tolerance
        or float(left[3]) <= float(right[1]) + tolerance
        or float(right[3]) <= float(left[1]) + tolerance
    )


def _trusted_words_by_page(
    source: SourceVisibilityProducer,
    published: object,
) -> dict[str, tuple[_TrustedTextWord, ...]]:
    """Resolve the producer-owned PDF text-integrity receipt for every word."""

    authority = source.text_integrity_authority()
    rows: dict[str, list[_TrustedTextWord]] = {}
    for observation_id in tuple(
        getattr(published, "text_observation_ids", ()) or ()
    ):
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        result = authority.resolve_text(selector)
        receipt = result.receipt
        if receipt is None:
            # Published text ids are producer-owned and must always carry their
            # receipt. Treat a missing receipt as a source-integrity failure
            # rather than silently dropping a word.
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        try:
            bbox = tuple(float(value) for value in receipt.geometry)
        except (TypeError, ValueError):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        if (
            len(bbox) != 4
            or bbox[2] <= bbox[0]
            or bbox[3] <= bbox[1]
        ):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        page_id = str(receipt.page_id)
        rows.setdefault(page_id, []).append(
            _TrustedTextWord(
                observation_id=str(observation_id),
                page_id=page_id,
                text=str(result.trusted_text or receipt.raw_text or ""),
                bbox=bbox,
                block_no=int(receipt.block_no or 0),
                line_no=int(receipt.line_no or 0),
                word_no=int(receipt.word_no or 0),
                trusted=(
                    result.status is EvidenceResolutionStatus.CORROBORATED
                    and result.trusted_text is not None
                ),
                reason_codes=tuple(result.reason_codes or ()),
            )
        )
    return {
        page_id: tuple(
            sorted(
                values,
                key=lambda row: (
                    row.block_no,
                    row.line_no,
                    row.word_no,
                    row.bbox,
                    row.observation_id,
                ),
            )
        )
        for page_id, values in rows.items()
    }


def _trusted_lines_for_viewport(
    words: Sequence[_TrustedTextWord],
    viewport: SegmentedViewport,
) -> tuple[
    tuple[tuple[str, tuple[float, float, float, float], tuple[str, ...]], ...],
    bool,
    tuple[str, ...],
]:
    """Return only integrity-proven text wholly owned by one viewport.

    Any untrusted word inside the viewport, or any word crossing the viewport
    boundary, makes the text scope incomplete. This prevents corrupted text
    from becoming schedule/finish authority merely because nearby words were
    readable.
    """

    assert viewport.bounding_box is not None
    grouped: dict[
        tuple[int, int],
        list[_TrustedTextWord],
    ] = {}
    reasons: list[str] = []
    complete = True

    for word in words:
        if not _bbox_intersects(word.bbox, viewport.bounding_box):
            continue
        if not _bbox_fully_inside(word.bbox, viewport.bounding_box):
            complete = False
            reasons.append(SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED)
            reasons.append("text_crosses_viewport_boundary")
            continue
        if not word.trusted:
            complete = False
            reasons.append(SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED)
            reasons.extend(word.reason_codes)
            continue
        if not word.text.strip():
            continue
        grouped.setdefault((word.block_no, word.line_no), []).append(word)

    output = []
    for key in sorted(grouped):
        line_words = sorted(
            grouped[key],
            key=lambda row: (row.word_no, row.bbox[0], row.observation_id),
        )
        text = " ".join(row.text.strip() for row in line_words if row.text.strip()).strip()
        if not text:
            continue
        output.append(
            (
                text,
                (
                    min(row.bbox[0] for row in line_words),
                    min(row.bbox[1] for row in line_words),
                    max(row.bbox[2] for row in line_words),
                    max(row.bbox[3] for row in line_words),
                ),
                tuple(row.observation_id for row in line_words),
            )
        )
    return (
        tuple(output),
        complete,
        tuple(dict.fromkeys(reason for reason in reasons if reason)),
    )


class SourceMaterialSemanticAuthority:
    def __init__(
        self,
        definition_results: Mapping[
            tuple[str, str, str, str, str], SourceMaterialDefinitionResult
        ],
        occurrence_results: Mapping[
            tuple[str, str, str, str, str, str], SourceMaterialOccurrenceScopeResult
        ],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceMaterialSemanticAuthority is producer-owned")
        self._definition_results = MappingProxyType(dict(definition_results))
        self._occurrence_results = MappingProxyType(dict(occurrence_results))

    def resolve_definition(
        self,
        selector: SourceMaterialDefinitionSelector,
    ) -> SourceMaterialDefinitionResult:
        if type(selector) is not SourceMaterialDefinitionSelector:
            raise TypeError("selector must be SourceMaterialDefinitionSelector")
        return self._definition_results.get(
            selector.key,
            _definition_blocked(
                EvidenceResolutionStatus.ABSTAINED,
                SOURCE_MATERIAL_DEFINITION_UNAVAILABLE,
            ),
        )

    def resolve_occurrences(
        self,
        selector: SourceMaterialOccurrenceSelector,
    ) -> SourceMaterialOccurrenceScopeResult:
        if type(selector) is not SourceMaterialOccurrenceSelector:
            raise TypeError("selector must be SourceMaterialOccurrenceSelector")
        return self._occurrence_results.get(
            selector.key,
            _scope_blocked(
                EvidenceResolutionStatus.ABSTAINED,
                SOURCE_MATERIAL_SCOPE_UNAVAILABLE,
            ),
        )


class SourceMaterialSemanticProducer:
    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("Use from_source_visibility_producer()")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._definition_results: dict[
            tuple[str, str, str, str, str], SourceMaterialDefinitionResult
        ] = {}
        self._occurrence_results: dict[
            tuple[str, str, str, str, str, str], SourceMaterialOccurrenceScopeResult
        ] = {}
        self._published_revisions: set[str] = set()

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "SourceMaterialSemanticProducer":
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> SourceMaterialSemanticAuthority:
        return SourceMaterialSemanticAuthority(
            self._definition_results,
            self._occurrence_results,
            _seal=_AUTHORITY_SEAL,
        )

    def _source_bytes(self, revision_id: str) -> tuple[object, Optional[bytes]]:
        published = self._source.published_snapshot_for_revision(revision_id)
        if published is None:
            return None, None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(
            str(revision_id)
        )
        if source_bytes is None:
            return published, None
        if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        return published, bytes(source_bytes)

    def publish(self, revision_id: str) -> SourceMaterialSemanticAuthority:
        revision_id = _required(revision_id, "revision_id")
        if revision_id in self._published_revisions:
            return self.authority()

        published, source_bytes = self._source_bytes(revision_id)
        if published is None or source_bytes is None:
            self._published_revisions.add(revision_id)
            return self.authority()

        lineage = {
            "document_id": str(published.revision.document_id),
            "revision_id": str(published.revision.revision_id),
            "source_sha256": str(published.revision.source_sha256),
            "snapshot_id": str(published.snapshot.snapshot_id),
        }
        decoded_pages = {int(value) for value in published.coverage.decoded_pages}
        raw_definitions: dict[str, list[dict[str, object]]] = {}
        drawing_viewports: list[
            tuple[int, SegmentedViewport, tuple[_TrustedTextWord, ...]]
        ] = []
        schedule_universe_complete = True
        schedule_universe_reasons: list[str] = []
        trusted_words = _trusted_words_by_page(self._source, published)

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            for page_number in sorted(decoded_pages):
                if page_number < 1 or page_number > pdf.page_count:
                    continue
                page = pdf.load_page(page_number - 1)
                viewports = tuple(
                    segment_page_viewports(page, page_number=page_number)
                )
                if (
                    not viewports
                    or any(
                        not is_segment_page_viewports_product(viewport)
                        for viewport in viewports
                    )
                ):
                    continue
                sibling_non_overlapping = validate_non_overlapping_viewports(viewports)
                authoritative = tuple(
                    viewport
                    for viewport in viewports
                    if _viewport_is_authoritative(
                        viewport,
                        sibling_non_overlapping=sibling_non_overlapping,
                    )
                )
                page_words = trusted_words.get(str(page_number), ())
                for viewport in authoritative:
                    lines, text_complete, text_reasons = _trusted_lines_for_viewport(
                        page_words,
                        viewport,
                    )
                    if viewport.view_type in _SCHEDULE_VIEW_TYPES:
                        if not text_complete or not lines:
                            schedule_universe_complete = False
                            schedule_universe_reasons.append(
                                SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED
                            )
                            schedule_universe_reasons.extend(text_reasons)
                            if not lines:
                                schedule_universe_reasons.append(
                                    "schedule_viewport_has_no_trusted_text"
                                )
                            continue
                        text = "\n".join(line[0] for line in lines)
                        line_evidence = {
                            line[0]: line[2]
                            for line in lines
                        }
                        for item in parse_schedule_text(
                            text,
                            page_id=page_number,
                            page_label=f"page:{page_number}",
                        ):
                            code = str(item.get("code") or "").strip().upper()
                            if not code:
                                continue
                            raw = dict(item)
                            raw["source_viewport_id"] = viewport.view_id
                            contributing_lines = tuple(
                                item.get("source_lines")
                                or (str(item.get("source_line") or ""),)
                            )
                            raw["source_text_observation_ids"] = tuple(
                                dict.fromkeys(
                                    observation_id
                                    for source_line in contributing_lines
                                    for observation_id in line_evidence.get(
                                        str(source_line),
                                        (),
                                    )
                                )
                            )
                            raw_definitions.setdefault(code, []).append(raw)
                    else:
                        if not text_complete:
                            scope_selector = SourceMaterialOccurrenceSelector(
                                **lineage,
                                page_id=str(page_number),
                                viewport_id=viewport.view_id,
                            )
                            self._occurrence_results[scope_selector.key] = _scope_blocked(
                                EvidenceResolutionStatus.ABSTAINED,
                                SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                                *text_reasons,
                            )
                            continue
                        drawing_viewports.append(
                            (page_number, viewport, page_words)
                        )

            if not schedule_universe_complete:
                blocked_reasons = tuple(
                    dict.fromkeys(
                        (
                            SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                            *(
                                reason
                                for reason in schedule_universe_reasons
                                if reason
                            ),
                        )
                    )
                )
                for code in sorted(raw_definitions):
                    selector = SourceMaterialDefinitionSelector(
                        **lineage,
                        code=code,
                    )
                    self._definition_results[selector.key] = _definition_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        *blocked_reasons,
                    )
                for page_number, viewport, _page_words in drawing_viewports:
                    scope_selector = SourceMaterialOccurrenceSelector(
                        **lineage,
                        page_id=str(page_number),
                        viewport_id=viewport.view_id,
                    )
                    self._occurrence_results[scope_selector.key] = _scope_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_SCOPE_UNAVAILABLE,
                        *blocked_reasons,
                    )
                self._published_revisions.add(revision_id)
                return self.authority()

            confirmed_dictionary: dict[str, dict[str, object]] = {}
            for code, items in sorted(raw_definitions.items()):
                representative = items[0]
                conflicting = [
                    item
                    for item in items[1:]
                    if not _compatible_descriptions(
                        representative.get("description"),
                        item.get("description"),
                    )
                ]
                substrate_names = {
                    str(item.get("substrate") or "").strip()
                    for item in items
                    if str(item.get("substrate") or "").strip()
                }
                finish_names = {
                    str(item.get("finish") or "").strip()
                    for item in items
                    if str(item.get("finish") or "").strip()
                }
                status = (
                    EvidenceResolutionStatus.CONFLICT
                    if (
                        conflicting
                        or len(substrate_names) > 1
                        or len(finish_names) > 1
                    )
                    else EvidenceResolutionStatus.CORROBORATED
                )
                selector = SourceMaterialDefinitionSelector(
                    **lineage,
                    code=code,
                )
                if status is EvidenceResolutionStatus.CONFLICT:
                    self._definition_results[selector.key] = _definition_blocked(
                        status,
                        SOURCE_MATERIAL_DEFINITION_CONFLICT,
                    )
                    continue

                entry = {
                    "code": code,
                    "description": str(representative.get("description") or ""),
                    "substrate": next(iter(substrate_names)) if substrate_names else "",
                    "finish": next(iter(finish_names)) if finish_names else "",
                    "status": "Confirmed",
                }
                semantic_finish = semantic_finish_from_schedule_entry(entry)
                source_ids = tuple(
                    sorted(
                        stable_contract_id(
                            "source_material_definition_evidence",
                            {
                                **lineage,
                                "page_id": str(item.get("page_id") or ""),
                                "viewport_id": str(item.get("source_viewport_id") or ""),
                                "code": code,
                                "source_line": str(item.get("source_line") or ""),
                                "source_text_observation_ids": tuple(
                                    item.get("source_text_observation_ids") or ()
                                ),
                            },
                            digest_chars=32,
                        )
                        for item in items
                    )
                )
                payload = {
                    **lineage,
                    "code": code,
                    "description": entry["description"],
                    "substrate": entry["substrate"],
                    "finish": entry["finish"],
                    "semantic_finish": semantic_finish,
                    "source_definition_ids": source_ids,
                }
                record = SourceMaterialDefinitionRecord(
                    record_id=stable_contract_id(
                        "source_material_definition",
                        payload,
                        digest_chars=32,
                    ),
                    document_id=lineage["document_id"],
                    revision_id=lineage["revision_id"],
                    source_sha256=lineage["source_sha256"],
                    snapshot_id=lineage["snapshot_id"],
                    code=code,
                    description=str(entry["description"]),
                    substrate=str(entry["substrate"]),
                    finish=str(entry["finish"]),
                    semantic_finish=semantic_finish,
                    source_definition_ids=source_ids,
                    source_page_ids=tuple(
                        sorted({str(item.get("page_id") or "") for item in items})
                    ),
                    source_viewport_ids=tuple(
                        sorted(
                            {
                                str(item.get("source_viewport_id") or "")
                                for item in items
                            }
                        )
                    ),
                )
                self._definition_results[selector.key] = SourceMaterialDefinitionResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(SOURCE_MATERIAL_DEFINITION_RESOLVED,),
                    record=record,
                )
                confirmed_dictionary[code] = {
                    **entry,
                    "semantic_finish": semantic_finish,
                    "record": record,
                }

            for page_number, viewport, page_words in drawing_viewports:
                scope_selector = SourceMaterialOccurrenceSelector(
                    **lineage,
                    page_id=str(page_number),
                    viewport_id=viewport.view_id,
                )
                records: list[SourceMaterialOccurrenceRecord] = []
                seen: set[tuple[str, tuple[float, float, float, float], str]] = set()
                dictionary_for_scan = {
                    code: dict(entry)
                    for code, entry in confirmed_dictionary.items()
                }
                lines, text_complete, text_reasons = _trusted_lines_for_viewport(
                    page_words,
                    viewport,
                )
                if not text_complete:
                    self._occurrence_results[scope_selector.key] = _scope_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                        *text_reasons,
                    )
                    continue
                for raw_text, bbox, text_observation_ids in lines:
                    for code in _defined_codes_in_text(raw_text, dictionary_for_scan):
                        entry = confirmed_dictionary.get(code)
                        if entry is None:
                            continue
                        definition = entry["record"]
                        assert isinstance(definition, SourceMaterialDefinitionRecord)
                        semantic_finish = str(entry.get("semantic_finish") or "")
                        if not semantic_finish:
                            continue
                        normalized_bbox = tuple(round(float(v), 6) for v in bbox)
                        dedup_key = (code, normalized_bbox, raw_text)
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)
                        evidence_payload = {
                            **lineage,
                            "page_id": str(page_number),
                            "viewport_id": viewport.view_id,
                            "code": code,
                            "bbox": normalized_bbox,
                            "raw_text": raw_text,
                            "source_text_observation_ids": tuple(
                                text_observation_ids
                            ),
                        }
                        evidence_id = stable_contract_id(
                            "source_material_occurrence_evidence",
                            evidence_payload,
                            digest_chars=32,
                        )
                        record_payload = {
                            **evidence_payload,
                            "definition_record_id": definition.record_id,
                            "semantic_finish": semantic_finish,
                            "source_evidence_id": evidence_id,
                        }
                        records.append(
                            SourceMaterialOccurrenceRecord(
                                record_id=stable_contract_id(
                                    "source_material_occurrence",
                                    record_payload,
                                    digest_chars=32,
                                ),
                                document_id=lineage["document_id"],
                                revision_id=lineage["revision_id"],
                                source_sha256=lineage["source_sha256"],
                                snapshot_id=lineage["snapshot_id"],
                                page_id=str(page_number),
                                viewport_id=viewport.view_id,
                                code=code,
                                semantic_finish=semantic_finish,
                                definition_record_id=definition.record_id,
                                bbox_pdf_pts=normalized_bbox,
                                raw_text=raw_text,
                                source_evidence_id=evidence_id,
                            )
                        )
                records.sort(key=lambda row: row.record_id)
                self._occurrence_results[scope_selector.key] = (
                    SourceMaterialOccurrenceScopeResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(SOURCE_MATERIAL_SCOPE_RESOLVED,),
                        scope_complete=True,
                        records=tuple(records),
                    )
                )
        finally:
            pdf.close()

        self._published_revisions.add(revision_id)
        return self.authority()


__all__ = [
    "SOURCE_MATERIAL_DEFINITION_CONFLICT",
    "SOURCE_MATERIAL_DEFINITION_RESOLVED",
    "SOURCE_MATERIAL_DEFINITION_UNAVAILABLE",
    "SOURCE_MATERIAL_SCOPE_RESOLVED",
    "SOURCE_MATERIAL_SCOPE_UNAVAILABLE",
    "SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION",
    "SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE",
    "SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED",
    "SourceMaterialDefinitionRecord",
    "SourceMaterialDefinitionResult",
    "SourceMaterialDefinitionSelector",
    "SourceMaterialOccurrenceRecord",
    "SourceMaterialOccurrenceScopeResult",
    "SourceMaterialOccurrenceSelector",
    "SourceMaterialSemanticAuthority",
    "SourceMaterialSemanticProducer",
]
