"""Producer-owned source-execution callout authority.

This shadow authority composes short semantic callouts from immutable native
word observations without relying on PyMuPDF block/line/word numbering.

Ordering authority:
- PdfTextIntegrityReceipt.sequence_number / trace_sequence_numbers only.

Semantic authority:
- native PdfTextIntegrity when CORROBORATED; otherwise
- producer-owned RasterTextCorroboration for the exact native word, which may
  corroborate only glyph-mapping-only abstentions and must agree with the
  native claim across the approved raster views.

Raw native text is used only to identify a bounded candidate execution run and
to decide which exact words need independent corroboration. It never becomes
trusted text by itself.

The first supported callout family is generic wall-finish semantics because it
is the current consumer. The authority is deliberately local: it proves the
semantic note, not wall identity, wall role, finish-scope completeness, or any
quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import statistics
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE_EXECUTION_CALLOUT_SCHEMA_VERSION = "1.0.0"
SOURCE_EXECUTION_CALLOUT_RESOLVED = "source_execution_callout_resolved"
SOURCE_EXECUTION_CALLOUT_UNAVAILABLE = "source_execution_callout_unavailable"
SOURCE_EXECUTION_CALLOUT_SEMANTIC_CONFLICT = "source_execution_callout_semantic_conflict"
SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED = (
    "source_execution_callout_required_word_unresolved"
)
SOURCE_EXECUTION_CALLOUT_EXECUTION_UNAVAILABLE = (
    "source_execution_callout_execution_order_unavailable"
)

MAX_EXECUTION_SPAN = 24

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class SourceExecutionWordEvidence:
    observation_id: str
    receipt_id: str
    trusted_text: str
    authority_kind: str
    authority_record_id: str
    sequence_start: int
    sequence_end: int
    geometry: tuple[float, float, float, float]


@dataclass(frozen=True)
class SourceExecutionCalloutSemantic:
    trade_scope_id: str
    finish_material: str
    direction: str
    required_categories: tuple[str, ...]


@dataclass(frozen=True)
class SourceExecutionCalloutRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    source_partition_id: str
    sequence_start: int
    sequence_end: int
    source_bbox: tuple[float, float, float, float]
    text_height: float
    observation_ids: tuple[str, ...]
    required_observation_ids: tuple[str, ...]
    word_evidence: tuple[SourceExecutionWordEvidence, ...]
    semantics: tuple[SourceExecutionCalloutSemantic, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = SOURCE_EXECUTION_CALLOUT_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceExecutionCalloutRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive callout record must be CORROBORATED")
        if not self.semantics:
            raise ValueError("positive callout record requires semantics")
        if not self.required_observation_ids:
            raise ValueError("positive callout record requires essential word evidence")


@dataclass(frozen=True)
class SourceExecutionCalloutPageResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceExecutionCalloutRecord, ...] = ()
    schema_version: str = SOURCE_EXECUTION_CALLOUT_SCHEMA_VERSION


@dataclass(frozen=True)
class _Word:
    observation_id: str
    receipt_id: str
    source_partition_id: str
    raw_text: str
    geometry: tuple[float, float, float, float]
    sequence_start: int
    sequence_end: int


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if token
    )


def _category_matches(category: str, text: str) -> bool:
    tokens = _word_tokens(text)
    if len(tokens) != 1:
        return False
    token = tokens[0]
    if category == "wall":
        return token.startswith("wall")
    return token == category


def _bbox_union(values: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    return (
        min(float(v[0]) for v in values),
        min(float(v[1]) for v in values),
        max(float(v[2]) for v in values),
        max(float(v[3]) for v in values),
    )


def _receipt_interval(receipt) -> Optional[tuple[int, int]]:
    numbers = []
    if receipt.sequence_number is not None:
        numbers.append(int(receipt.sequence_number))
    numbers.extend(int(v) for v in tuple(receipt.trace_sequence_numbers or ()))
    if not numbers:
        return None
    return (min(numbers), max(numbers))


def _execution_clusters(words: Sequence[_Word]) -> tuple[tuple[_Word, ...], ...]:
    """Group only source-execution-contiguous words.

    No block/line/word adapter metadata participates. Runs longer than the
    bounded callout window are still returned; semantic recognition later
    refuses them rather than slicing a long source operation into a convenient
    answer-shaped window.
    """
    by_partition: dict[str, list[_Word]] = {}
    for word in words:
        by_partition.setdefault(word.source_partition_id, []).append(word)

    out = []
    for partition_id in sorted(by_partition):
        ordered = sorted(
            by_partition[partition_id],
            key=lambda w: (
                w.sequence_start,
                w.sequence_end,
                round(w.geometry[1], 6),
                round(w.geometry[0], 6),
                w.observation_id,
            ),
        )
        current: list[_Word] = []
        current_end: Optional[int] = None
        for word in ordered:
            if current and current_end is not None and word.sequence_start > current_end + 1:
                out.append(tuple(current))
                current = []
                current_end = None
            current.append(word)
            current_end = max(word.sequence_end, current_end if current_end is not None else word.sequence_end)
        if current:
            out.append(tuple(current))
    return tuple(out)


def _semantic_candidate(
    cluster: Sequence[_Word],
) -> Optional[
    tuple[
        tuple[SourceExecutionCalloutSemantic, ...],
        Mapping[str, _Word],
    ]
]:
    if not cluster:
        return None
    span = max(word.sequence_end for word in cluster) - min(
        word.sequence_start for word in cluster
    ) + 1
    if span > MAX_EXECUTION_SPAN:
        return None

    category_words: dict[str, list[_Word]] = {
        name: []
        for name in (
            "wall",
            "finish",
            "key",
            "externally",
            "plaster",
            "paint",
            "internally",
        )
    }
    for word in cluster:
        for category in category_words:
            if _category_matches(category, word.raw_text):
                category_words[category].append(word)

    external_required = ("wall", "finish", "key", "externally")
    internal_required = ("wall", "finish", "plaster", "paint", "internally")
    external = all(len(category_words[name]) == 1 for name in external_required)
    internal = all(len(category_words[name]) == 1 for name in internal_required)

    # Competing direction/trade semantics inside one short execution run are
    # not resolved by ranking.
    if external and internal:
        return None
    if not external and not internal:
        return None

    required = external_required if external else internal_required
    selected = {name: category_words[name][0] for name in required}
    if external:
        semantics = (
            SourceExecutionCalloutSemantic(
                trade_scope_id="external_key_pointing",
                finish_material="key_pointing",
                direction="externally",
                required_categories=external_required,
            ),
        )
    else:
        semantics = (
            SourceExecutionCalloutSemantic(
                trade_scope_id="internal_plaster",
                finish_material="plaster",
                direction="internally",
                required_categories=internal_required,
            ),
            SourceExecutionCalloutSemantic(
                trade_scope_id="internal_paint",
                finish_material="paint",
                direction="internally",
                required_categories=internal_required,
            ),
        )
    return semantics, MappingProxyType(selected)


def _page_key(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
) -> tuple[str, str, str, str, str]:
    return (
        str(document_id),
        str(revision_id),
        str(source_sha256),
        str(snapshot_id),
        str(page_id),
    )


class SourceExecutionCalloutAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, str, str, str, str], SourceExecutionCalloutPageResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceExecutionCalloutAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_page(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
    ) -> SourceExecutionCalloutPageResult:
        return self._results.get(
            _page_key(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=snapshot_id,
                page_id=page_id,
            ),
            SourceExecutionCalloutPageResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_EXECUTION_CALLOUT_UNAVAILABLE,),
            ),
        )


class SourceExecutionCalloutProducer:
    def __init__(
        self,
        source: SourceVisibilityProducer,
        raster_producer: RasterTextCorroborationProducer,
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "SourceExecutionCalloutProducer must be obtained from a classmethod"
            )
        self._source = source
        self._raster = raster_producer
        self._results: dict[
            tuple[str, str, str, str, str],
            SourceExecutionCalloutPageResult,
        ] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "SourceExecutionCalloutProducer":
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be an actual SourceVisibilityProducer")
        producer = cls(
            source,
            RasterTextCorroborationProducer.from_source_visibility_producer(source),
            _seal=_PRODUCER_SEAL,
        )
        producer._build(page_ids=page_ids)
        return producer

    @classmethod
    def from_source_visibility_producer_for_tests(
        cls,
        source: SourceVisibilityProducer,
        backend: MockOCRBackend,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "SourceExecutionCalloutProducer":
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be an actual SourceVisibilityProducer")
        if type(backend) is not MockOCRBackend:
            raise TypeError("backend must be exact MockOCRBackend")
        producer = cls(
            source,
            RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(
                source,
                backend,
            ),
            _seal=_PRODUCER_SEAL,
        )
        producer._build(page_ids=page_ids)
        return producer

    def _authorize_word(self, published, word: _Word, category: str) -> Optional[SourceExecutionWordEvidence]:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=word.observation_id,
        )
        native = self._source.text_integrity_authority().resolve_text(selector)
        if (
            native.status is EvidenceResolutionStatus.CORROBORATED
            and native.receipt is not None
            and native.trusted_text
            and _category_matches(category, native.trusted_text)
        ):
            return SourceExecutionWordEvidence(
                observation_id=word.observation_id,
                receipt_id=native.receipt.receipt_id,
                trusted_text=str(native.trusted_text),
                authority_kind="native_text_integrity",
                authority_record_id=native.receipt.receipt_id,
                sequence_start=word.sequence_start,
                sequence_end=word.sequence_end,
                geometry=word.geometry,
            )

        raster = self._raster.publish(
            RasterTextCorroborationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=word.observation_id,
            )
        )
        if (
            raster.status is EvidenceResolutionStatus.CORROBORATED
            and raster.record is not None
            and raster.corroborated_text
            and _category_matches(category, raster.corroborated_text)
        ):
            return SourceExecutionWordEvidence(
                observation_id=word.observation_id,
                receipt_id=word.receipt_id,
                trusted_text=str(raster.corroborated_text),
                authority_kind="raster_text_corroboration",
                authority_record_id=raster.record.record_id,
                sequence_start=word.sequence_start,
                sequence_end=word.sequence_end,
                geometry=word.geometry,
            )
        return None

    def _build(self, *, page_ids: Optional[Sequence[str]]) -> None:
        selected = None if page_ids is None else {
            str(page_id).strip() for page_id in page_ids if str(page_id).strip()
        }
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one page")

        text_authority = self._source.text_integrity_authority()
        for revision_id, published in sorted(self._source._published_by_revision.items()):
            if self._source._producer.current_revision_id(published.revision.document_id) != revision_id:
                continue

            words_by_page: dict[str, list[_Word]] = {}
            pages_with_unordered_words: set[str] = set()
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
                receipt = result.receipt
                if receipt is None:
                    continue
                page_id = str(receipt.page_id)
                if selected is not None and page_id not in selected:
                    continue
                interval = _receipt_interval(receipt)
                if interval is None:
                    pages_with_unordered_words.add(page_id)
                    continue
                geometry = tuple(float(v) for v in tuple(receipt.geometry))
                if (
                    len(geometry) != 4
                    or not all(math.isfinite(v) for v in geometry)
                    or geometry[2] <= geometry[0]
                    or geometry[3] <= geometry[1]
                ):
                    continue
                words_by_page.setdefault(page_id, []).append(
                    _Word(
                        observation_id=observation_id,
                        receipt_id=receipt.receipt_id,
                        source_partition_id=str(receipt.source_partition_id),
                        raw_text=str(receipt.raw_text or ""),
                        geometry=geometry,  # type: ignore[arg-type]
                        sequence_start=interval[0],
                        sequence_end=interval[1],
                    )
                )

            for page_id, words in sorted(words_by_page.items(), key=lambda item: int(item[0])):
                records: list[SourceExecutionCalloutRecord] = []
                required_word_unresolved = False
                for cluster in _execution_clusters(words):
                    candidate = _semantic_candidate(cluster)
                    if candidate is None:
                        continue
                    semantics, required_by_category = candidate

                    evidence: list[SourceExecutionWordEvidence] = []
                    unresolved = False
                    for category, word in sorted(required_by_category.items()):
                        authorized = self._authorize_word(
                            published,
                            word,
                            category,
                        )
                        if authorized is None:
                            unresolved = True
                            break
                        evidence.append(authorized)
                    if unresolved:
                        required_word_unresolved = True
                        continue

                    seq_start = min(word.sequence_start for word in cluster)
                    seq_end = max(word.sequence_end for word in cluster)
                    bbox = _bbox_union([word.geometry for word in cluster])
                    heights = [
                        max(0.1, word.geometry[3] - word.geometry[1])
                        for word in cluster
                    ]
                    observation_ids = tuple(
                        word.observation_id
                        for word in sorted(
                            cluster,
                            key=lambda w: (
                                w.sequence_start,
                                w.sequence_end,
                                round(w.geometry[1], 6),
                                round(w.geometry[0], 6),
                                w.observation_id,
                            ),
                        )
                    )
                    required_ids = tuple(
                        sorted(item.observation_id for item in evidence)
                    )
                    payload = {
                        "document_id": published.revision.document_id,
                        "revision_id": published.revision.revision_id,
                        "source_sha256": published.revision.source_sha256,
                        "snapshot_id": published.snapshot.snapshot_id,
                        "page_id": page_id,
                        "source_partition_id": cluster[0].source_partition_id,
                        "sequence_start": seq_start,
                        "sequence_end": seq_end,
                        "observation_ids": observation_ids,
                        "required_observation_ids": required_ids,
                        "semantics": tuple(
                            (
                                semantic.trade_scope_id,
                                semantic.finish_material,
                                semantic.direction,
                                semantic.required_categories,
                            )
                            for semantic in semantics
                        ),
                    }
                    records.append(
                        SourceExecutionCalloutRecord(
                            record_id=stable_contract_id(
                                "source_execution_callout",
                                payload,
                                digest_chars=32,
                            ),
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            source_partition_id=cluster[0].source_partition_id,
                            sequence_start=seq_start,
                            sequence_end=seq_end,
                            source_bbox=bbox,
                            text_height=float(statistics.median(heights)),
                            observation_ids=observation_ids,
                            required_observation_ids=required_ids,
                            word_evidence=tuple(
                                sorted(
                                    evidence,
                                    key=lambda item: (
                                        item.sequence_start,
                                        item.sequence_end,
                                        item.observation_id,
                                    ),
                                )
                            ),
                            semantics=semantics,
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(SOURCE_EXECUTION_CALLOUT_RESOLVED,),
                            _seal=_RECORD_SEAL,
                        )
                    )

                key = _page_key(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                )
                reasons = [SOURCE_EXECUTION_CALLOUT_RESOLVED]
                if required_word_unresolved:
                    reasons.append(SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED)
                if page_id in pages_with_unordered_words:
                    reasons.append(SOURCE_EXECUTION_CALLOUT_EXECUTION_UNAVAILABLE)
                self._results[key] = SourceExecutionCalloutPageResult(
                    status=(
                        EvidenceResolutionStatus.CORROBORATED
                        if records
                        else EvidenceResolutionStatus.ABSTAINED
                    ),
                    reason_codes=tuple(dict.fromkeys(
                        reasons if records else (
                            SOURCE_EXECUTION_CALLOUT_UNAVAILABLE,
                            *(
                                (SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED,)
                                if required_word_unresolved else ()
                            ),
                            *(
                                (SOURCE_EXECUTION_CALLOUT_EXECUTION_UNAVAILABLE,)
                                if page_id in pages_with_unordered_words else ()
                            ),
                        )
                    )),
                    records=tuple(sorted(records, key=lambda record: record.record_id)),
                )

    def authority(self) -> SourceExecutionCalloutAuthority:
        return SourceExecutionCalloutAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[SourceExecutionCalloutPageResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "MAX_EXECUTION_SPAN",
    "SOURCE_EXECUTION_CALLOUT_EXECUTION_UNAVAILABLE",
    "SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED",
    "SOURCE_EXECUTION_CALLOUT_RESOLVED",
    "SOURCE_EXECUTION_CALLOUT_SCHEMA_VERSION",
    "SOURCE_EXECUTION_CALLOUT_SEMANTIC_CONFLICT",
    "SOURCE_EXECUTION_CALLOUT_UNAVAILABLE",
    "SourceExecutionCalloutAuthority",
    "SourceExecutionCalloutPageResult",
    "SourceExecutionCalloutProducer",
    "SourceExecutionCalloutRecord",
    "SourceExecutionCalloutSemantic",
    "SourceExecutionWordEvidence",
    "_Word",
    "_category_matches",
    "_execution_clusters",
    "_receipt_interval",
    "_semantic_candidate",
]
