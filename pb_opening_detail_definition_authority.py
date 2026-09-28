"""Producer-owned authority for unmarked opening detail definitions.

This authority proves TYPE METADATA ONLY from trusted native source execution.
It cannot mint a physical opening, host wall, quantity, deduction, or count.

Supported generic proposition:
  one compact source-execution run
  + exactly one trusted, unit-bearing WxH dimension proposition
  + exactly one opening family (window or door)
  -> one opening detail definition.

Optional material/subtype tokens are retained when uniquely evidenced.
Duplicate source definitions remain separate provenance records but share a
stable semantic_identity_id so downstream consumers may collapse identical
TYPE definitions without turning repeated details into physical instances.

No project id, benchmark value, coordinates, nearest-instance selection, or
schedule default count participates.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import TEXT_GLYPH_MAPPING_UNVERIFIED
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_execution_callout_authority import _Word, _execution_clusters, _receipt_interval
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


OPENING_DETAIL_DEFINITION_SCHEMA_VERSION = "1.0.0"
OPENING_DETAIL_DEFINITION_RESOLVED = "opening_detail_definition_resolved"
OPENING_DETAIL_DEFINITION_UNAVAILABLE = "opening_detail_definition_unavailable"
OPENING_DETAIL_DEFINITION_AMBIGUOUS = "opening_detail_definition_ambiguous"
OPENING_DETAIL_DEFINITION_UNTRUSTED = "opening_detail_definition_untrusted"

MAX_DETAIL_EXECUTION_SPAN = 32
_MIN_DIMENSION_MM = 200
_MAX_DIMENSION_MM = 6000

_RECORD_SEAL = object()
_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_DIM_TOKEN = re.compile(r"^(\d{1,2}(?:,\d{3})?|\d{2,5})(?:mm)?$", re.IGNORECASE)
_COMBINED_DIM = re.compile(
    r"^(\d{1,2}(?:,\d{3})?|\d{2,5})\s*mm\s*[x×]\s*"
    r"(\d{1,2}(?:,\d{3})?|\d{2,5})\s*mm$",
    re.IGNORECASE,
)

_WINDOW_TOKENS = {"window", "windows"}
_DOOR_TOKENS = {"door", "doors"}
_MATERIALS = {
    "steel": "steel",
    "timber": "timber",
    "wood": "timber",
    "aluminium": "aluminium",
    "aluminum": "aluminium",
    "upvc": "upvc",
    "pvc": "pvc",
}
_WINDOW_SUBTYPES = {
    "casement": "casement",
    "fixed": "fixed",
    "sliding": "sliding",
    "louvre": "louvre",
    "louver": "louvre",
}
_DOOR_SUBTYPES = {
    "batten": "batten",
    "panelled": "panelled",
    "paneled": "panelled",
    "flush": "flush",
    "sliding": "sliding",
    "glazed": "glazed",
}


@dataclass(frozen=True)
class OpeningDetailWordEvidence:
    observation_id: str
    receipt_id: str
    trusted_text: str
    authority_kind: str
    authority_record_id: str
    sequence_start: int
    sequence_end: int
    geometry: tuple[float, float, float, float]


@dataclass(frozen=True)
class OpeningDetailDefinitionRecord:
    record_id: str
    semantic_identity_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    source_partition_id: str
    sequence_start: int
    sequence_end: int
    source_bbox: tuple[float, float, float, float]
    family: str
    subtype: str
    material: str
    width_mm: int
    height_mm: int
    dimension_basis: str
    source_observation_ids: tuple[str, ...]
    required_observation_ids: tuple[str, ...]
    word_evidence: tuple[OpeningDetailWordEvidence, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_DETAIL_DEFINITION_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("OpeningDetailDefinitionRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive opening detail record must be CORROBORATED")
        if self.family not in {"window", "door"}:
            raise ValueError("family must be window or door")
        if not (_MIN_DIMENSION_MM <= self.width_mm <= _MAX_DIMENSION_MM):
            raise ValueError("width outside plausible opening range")
        if not (_MIN_DIMENSION_MM <= self.height_mm <= _MAX_DIMENSION_MM):
            raise ValueError("height outside plausible opening range")
        if self.dimension_basis != "detail_unspecified":
            raise ValueError("unmarked detail dimensions must not invent a deduction basis")


@dataclass(frozen=True)
class OpeningDetailDefinitionPageResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[OpeningDetailDefinitionRecord, ...] = ()
    schema_version: str = OPENING_DETAIL_DEFINITION_SCHEMA_VERSION


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9,]+", "", str(value or "").lower())


def _claim_norm(value: str) -> str:
    """Normalize only presentation differences for authority agreement.

    Thousands separators, punctuation and case are not semantic changes to an
    opening-detail token. Every alphanumeric character remains significant.
    """
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _number_mm(value: str) -> Optional[int]:
    token = str(value or "").strip().lower().replace(" ", "")
    m = _DIM_TOKEN.fullmatch(token)
    if not m:
        return None
    try:
        number = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if _MIN_DIMENSION_MM <= number <= _MAX_DIMENSION_MM:
        return number
    return None


def _same_line_dimension_pair(first: _Word, second: _Word) -> bool:
    if first.source_partition_id != second.source_partition_id:
        return False
    first_value = _number_mm(first.raw_text)
    second_value = _number_mm(second.raw_text)
    if first_value is None or second_value is None:
        return False
    if second.sequence_start < first.sequence_end:
        return False
    if second.sequence_start - first.sequence_end > 2:
        return False

    fx0, fy0, fx1, fy1 = first.geometry
    sx0, sy0, sx1, sy1 = second.geometry
    first_h = max(0.0, fy1 - fy0)
    second_h = max(0.0, sy1 - sy0)
    if first_h <= 0.0 or second_h <= 0.0:
        return False
    overlap_y = min(fy1, sy1) - max(fy0, sy0)
    if overlap_y < 0.8 * min(first_h, second_h):
        return False
    # Source execution and geometry both establish left-to-right adjacency.
    if sx0 < fx1:
        return False
    gap = sx0 - fx1
    if gap > 1.5 * max(first_h, second_h):
        return False
    return True


def _dimension_candidates(words: Sequence[_Word]):
    ordered = sorted(
        words,
        key=lambda w: (w.sequence_start, w.sequence_end, w.observation_id),
    )
    out = []

    # Combined single-word form, if present. The entire token must later be
    # independently authorised by text-integrity/raster authority.
    for word in ordered:
        raw = str(word.raw_text or "").strip()
        m = _COMBINED_DIM.fullmatch(raw.replace("×", "x"))
        if m:
            a, b = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            if (
                _MIN_DIMENSION_MM <= a <= _MAX_DIMENSION_MM
                and _MIN_DIMENSION_MM <= b <= _MAX_DIMENSION_MM
            ):
                out.append((a, b, (word,)))

    # Two adjacent numbers do not establish a WxH proposition. Require a
    # separately trusted multiplication/dimension separator in the same
    # execution partition. Its observation participates in required evidence,
    # so an unmappable glyph cannot silently acquire dimension authority.
    for first, separator, second in zip(ordered, ordered[1:], ordered[2:]):
        if str(separator.raw_text).strip().lower() not in {"x", "×"}:
            continue
        if not (
            first.source_partition_id
            == separator.source_partition_id
            == second.source_partition_id
        ):
            continue
        if not (
            str(first.raw_text).strip().lower().endswith("mm")
            and str(second.raw_text).strip().lower().endswith("mm")
        ):
            continue
        if not _same_line_dimension_pair(first, second):
            continue
        if not (
            first.sequence_end <= separator.sequence_start
            and separator.sequence_end <= second.sequence_start
            and first.geometry[2] <= separator.geometry[0]
            and separator.geometry[2] <= second.geometry[0]
        ):
            continue
        a = _number_mm(first.raw_text)
        b = _number_mm(second.raw_text)
        assert a is not None and b is not None
        out.append((a, b, (first, separator, second)))

    # De-duplicate the same semantic dimension proposition. Prefer the source
    # form with fewer required observations when combined and layout forms
    # happen to express the same pair.
    by_pair = {}
    for a, b, members in out:
        key = (a, b)
        prior = by_pair.get(key)
        if prior is None or len(members) < len(prior):
            by_pair[key] = members
    return tuple(
        (a, b, by_pair[(a, b)])
        for a, b in sorted(by_pair)
    )


def _token_words(words: Sequence[_Word], accepted: set[str]) -> tuple[_Word, ...]:
    return tuple(
        word
        for word in words
        if _norm(word.raw_text) in accepted
    )


def _candidate(cluster: Sequence[_Word]):
    if not cluster:
        return None
    span = max(w.sequence_end for w in cluster) - min(w.sequence_start for w in cluster) + 1
    if span > MAX_DETAIL_EXECUTION_SPAN:
        return None

    dims = _dimension_candidates(cluster)
    if len(dims) != 1:
        return None
    width, height, dim_words = dims[0]

    window_words = _token_words(cluster, _WINDOW_TOKENS)
    door_words = _token_words(cluster, _DOOR_TOKENS)
    has_window, has_door = bool(window_words), bool(door_words)
    if has_window == has_door:
        return None
    family = "window" if has_window else "door"
    family_words = window_words if has_window else door_words

    subtype_map = _WINDOW_SUBTYPES if family == "window" else _DOOR_SUBTYPES
    subtype_words = tuple(
        word for word in cluster if _norm(word.raw_text) in subtype_map
    )
    subtype_values = {subtype_map[_norm(word.raw_text)] for word in subtype_words}
    if len(subtype_values) > 1:
        return None
    subtype = next(iter(subtype_values), "")

    material_words = tuple(
        word for word in cluster if _norm(word.raw_text) in _MATERIALS
    )
    material_values = {_MATERIALS[_norm(word.raw_text)] for word in material_words}
    if len(material_values) > 1:
        return None
    material = next(iter(material_values), "")

    required = tuple(dict.fromkeys(
        (*dim_words, *family_words, *subtype_words, *material_words)
    ))
    return {
        "family": family,
        "subtype": subtype,
        "material": material,
        "width_mm": width,
        "height_mm": height,
        "required_words": required,
    }


def _glyph_only_separator_receipt(native, word: _Word) -> bool:
    """Allow a native x/× receipt only as dimension-separator structure.

    The separator never authorizes a number, family, material or subtype.
    This narrow fallback exists because a tiny standalone multiplication glyph
    can be producer-visible yet too small for exact-word raster OCR.  Every
    surrounding semantic token remains independently text-integrity/raster
    corroborated.

    Fail closed unless glyph mapping is the *only* unresolved integrity
    condition and the receipt exactly replays the producer-owned word,
    partition, geometry and execution interval.
    """
    raw = str(word.raw_text or "").strip().lower()
    if raw not in {"x", "×"}:
        return False
    receipt = getattr(native, "receipt", None)
    if (
        native.status is not EvidenceResolutionStatus.ABSTAINED
        or receipt is None
        or tuple(native.reason_codes) != (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        or tuple(receipt.reason_codes) != (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        or str(receipt.raw_text or "").strip().lower() != raw
        or str(receipt.source_partition_id) != str(word.source_partition_id)
    ):
        return False
    try:
        geometry = tuple(float(value) for value in receipt.geometry)
    except (TypeError, ValueError):
        return False
    if geometry != tuple(float(value) for value in word.geometry):
        return False
    return _receipt_interval(receipt) == (
        word.sequence_start,
        word.sequence_end,
    )


def _bbox_union(words: Sequence[_Word]):
    return (
        min(w.geometry[0] for w in words),
        min(w.geometry[1] for w in words),
        max(w.geometry[2] for w in words),
        max(w.geometry[3] for w in words),
    )


def _page_key(published, page_id: str):
    return (
        published.revision.document_id,
        published.revision.revision_id,
        published.revision.source_sha256,
        published.snapshot.snapshot_id,
        str(page_id),
    )


class OpeningDetailDefinitionAuthority:
    def __init__(self, results: Mapping[tuple[str, ...], OpeningDetailDefinitionPageResult], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningDetailDefinitionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_page(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
    ) -> OpeningDetailDefinitionPageResult:
        return self._results.get(
            (document_id, revision_id, source_sha256, snapshot_id, str(page_id)),
            OpeningDetailDefinitionPageResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OPENING_DETAIL_DEFINITION_UNAVAILABLE,),
            ),
        )


class OpeningDetailDefinitionProducer:
    def __init__(
        self,
        source: SourceVisibilityProducer,
        raster_producer: RasterTextCorroborationProducer,
        *,
        _seal=None,
    ):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("use from_source_visibility_producer()")
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be an actual SourceVisibilityProducer")
        if type(raster_producer) is not RasterTextCorroborationProducer:
            raise TypeError("raster_producer must be producer-owned")
        self._source = source
        self._raster = raster_producer
        self._results = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ):
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
    ):
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

    def _trusted_word(self, published, word: _Word) -> Optional[OpeningDetailWordEvidence]:
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
            and _claim_norm(native.trusted_text) == _claim_norm(word.raw_text)
        ):
            return OpeningDetailWordEvidence(
                observation_id=word.observation_id,
                receipt_id=native.receipt.receipt_id,
                trusted_text=str(native.trusted_text),
                authority_kind="native_text_integrity",
                authority_record_id=native.receipt.receipt_id,
                sequence_start=word.sequence_start,
                sequence_end=word.sequence_end,
                geometry=word.geometry,
            )

        # A standalone multiplication glyph is syntax, not semantic text.
        # Permit its producer-owned receipt as separator structure only when
        # glyph mapping is the sole unresolved integrity condition.  The two
        # unit-bearing dimensions and all opening semantics are still required
        # to pass the normal trusted-word path below/above.
        if _glyph_only_separator_receipt(native, word):
            assert native.receipt is not None
            return OpeningDetailWordEvidence(
                observation_id=word.observation_id,
                receipt_id=native.receipt.receipt_id,
                trusted_text=str(native.receipt.raw_text),
                authority_kind="native_dimension_separator_structure",
                authority_record_id=native.receipt.receipt_id,
                sequence_start=word.sequence_start,
                sequence_end=word.sequence_end,
                geometry=word.geometry,
            )

        # Reuse the already-reviewed glyph-only corroboration authority.  It
        # independently decides whether this observation is eligible for
        # raster corroboration; ordinary callers cannot relax that gate.
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
            and _claim_norm(raster.corroborated_text) == _claim_norm(word.raw_text)
        ):
            return OpeningDetailWordEvidence(
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
            str(v).strip() for v in page_ids if str(v).strip()
        }
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one page")

        text_authority = self._source.text_integrity_authority()
        for revision_id, published in sorted(self._source._published_by_revision.items()):
            if self._source._producer.current_revision_id(published.revision.document_id) != revision_id:
                continue
            words_by_page = {}
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
                    continue
                geometry = tuple(float(v) for v in receipt.geometry)
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
                        geometry=geometry,
                        sequence_start=interval[0],
                        sequence_end=interval[1],
                    )
                )

            for page_id, words in sorted(words_by_page.items(), key=lambda item: int(item[0])):
                records = []
                saw_candidate_untrusted = False
                for cluster in _execution_clusters(words):
                    candidate = _candidate(cluster)
                    if candidate is None:
                        continue
                    evidence = []
                    for word in candidate["required_words"]:
                        trusted = self._trusted_word(published, word)
                        if trusted is None:
                            saw_candidate_untrusted = True
                            evidence = []
                            break
                        evidence.append(trusted)
                    if not evidence:
                        continue

                    source_ids = tuple(
                        word.observation_id
                        for word in sorted(
                            cluster,
                            key=lambda w: (w.sequence_start, w.sequence_end, w.observation_id),
                        )
                    )
                    required_ids = tuple(sorted(e.observation_id for e in evidence))
                    semantic_payload = {
                        "family": candidate["family"],
                        "subtype": candidate["subtype"],
                        "material": candidate["material"],
                        "width_mm": candidate["width_mm"],
                        "height_mm": candidate["height_mm"],
                        "dimension_basis": "detail_unspecified",
                    }
                    semantic_id = stable_contract_id(
                        "opening_detail_semantic_identity",
                        semantic_payload,
                        digest_chars=32,
                    )
                    payload = {
                        **semantic_payload,
                        "document_id": published.revision.document_id,
                        "revision_id": published.revision.revision_id,
                        "source_sha256": published.revision.source_sha256,
                        "snapshot_id": published.snapshot.snapshot_id,
                        "page_id": page_id,
                        "source_partition_id": cluster[0].source_partition_id,
                        "sequence_start": min(w.sequence_start for w in cluster),
                        "sequence_end": max(w.sequence_end for w in cluster),
                        "source_observation_ids": source_ids,
                        "required_observation_ids": required_ids,
                    }
                    records.append(
                        OpeningDetailDefinitionRecord(
                            record_id=stable_contract_id(
                                "opening_detail_definition", payload, digest_chars=32
                            ),
                            semantic_identity_id=semantic_id,
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            source_partition_id=cluster[0].source_partition_id,
                            sequence_start=payload["sequence_start"],
                            sequence_end=payload["sequence_end"],
                            source_bbox=_bbox_union(cluster),
                            family=candidate["family"],
                            subtype=candidate["subtype"],
                            material=candidate["material"],
                            width_mm=candidate["width_mm"],
                            height_mm=candidate["height_mm"],
                            dimension_basis="detail_unspecified",
                            source_observation_ids=source_ids,
                            required_observation_ids=required_ids,
                            word_evidence=tuple(sorted(
                                evidence,
                                key=lambda e: (e.sequence_start, e.sequence_end, e.observation_id),
                            )),
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(OPENING_DETAIL_DEFINITION_RESOLVED,),
                            _seal=_RECORD_SEAL,
                        )
                    )
                key = _page_key(published, page_id)
                if records:
                    reasons = [OPENING_DETAIL_DEFINITION_RESOLVED]
                    if saw_candidate_untrusted:
                        reasons.append(OPENING_DETAIL_DEFINITION_UNTRUSTED)
                    self._results[key] = OpeningDetailDefinitionPageResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=tuple(reasons),
                        records=tuple(sorted(records, key=lambda r: r.record_id)),
                    )
                else:
                    self._results[key] = OpeningDetailDefinitionPageResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(
                            OPENING_DETAIL_DEFINITION_UNTRUSTED
                            if saw_candidate_untrusted
                            else OPENING_DETAIL_DEFINITION_UNAVAILABLE,
                        ),
                    )

    def authority(self):
        return OpeningDetailDefinitionAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def published_results(self):
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "MAX_DETAIL_EXECUTION_SPAN",
    "OPENING_DETAIL_DEFINITION_AMBIGUOUS",
    "OPENING_DETAIL_DEFINITION_RESOLVED",
    "OPENING_DETAIL_DEFINITION_SCHEMA_VERSION",
    "OPENING_DETAIL_DEFINITION_UNAVAILABLE",
    "OPENING_DETAIL_DEFINITION_UNTRUSTED",
    "OpeningDetailDefinitionAuthority",
    "OpeningDetailDefinitionPageResult",
    "OpeningDetailDefinitionProducer",
    "OpeningDetailDefinitionRecord",
    "OpeningDetailWordEvidence",
    "_candidate",
    "_claim_norm",
    "_dimension_candidates",
]
