"""Producer-owned source amortized glyph text corroboration shadow authority (Items 22 & 23).

Eliminates original-source extraction timeouts and excessive raster processing by
amortizing verified font glyph mappings across all word occurrences in a document:
- Evaluates native word glyph occurrences from font programs lacking Unicode cmaps.
- Uses GlyphMappingLedger to select the minimal, optimal set of words for raster OCR.
- Verifies font glyph mappings with mathematical proof (>= min_words independent agreements).
- Authenticates unread words sharing the verified glyphs in O(1) time without raster crops.
- Fails closed on contradicted, under-supported, or unrecovered glyph mappings.
- Operates strictly in shadow mode with CANDIDATE status and non-commercial flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pb_font_glyph_mapping_corroboration_shadow import (
    ALL_GLYPHS_VERIFIED,
    DEFAULT_MIN_WORDS,
    GLYPH_CONTRADICTED,
    GLYPH_NOT_YET_VERIFIED,
    GLYPHS_NOT_RECOVERED,
    GlyphMappingLedger,
    WordGlyphs,
    classify_word,
    verify_glyph_mappings,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SOURCE_AMORTIZED_GLYPH_TEXT_SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
AMORTIZED_GLYPH_CORROBORATED = "amortized_glyph_corroborated"
DIRECT_OCR_CORROBORATED = "direct_ocr_corroborated"
GLYPH_MAPPING_UNDER_SUPPORTED = "glyph_mapping_under_supported"
GLYPH_CONTRADICTED_CODE = "glyph_contradicted"
GLYPHS_NOT_RECOVERED_CODE = "glyphs_not_recovered"
OCR_CORROBORATION_FAILED = "ocr_corroboration_failed"
AMORTIZED_TEXT_RECORD_UNAVAILABLE = "amortized_text_record_unavailable"
LINEAGE_MISMATCH = "lineage_mismatch"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/obs_id


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class SourceAmortizedGlyphTextSelector:
    """Selector identifying the exact text observation for amortized corroboration."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    observation_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "observation_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.observation_id,
        )


@dataclass(frozen=True)
class SourceAmortizedGlyphTextRecord:
    """Sealed record proving authentic word text via amortized glyph mapping."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    observation_id: str
    text: str
    font_key: str
    corroboration_method: str  # "DIRECT_OCR" or "AMORTIZED_GLYPH"
    verified_glyphs_count: int
    total_glyphs_count: int
    corroborating_evidence_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    schema_version: str = SOURCE_AMORTIZED_GLYPH_TEXT_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceAmortizedGlyphTextRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class SourceAmortizedGlyphTextResult:
    """Resolution result for amortized glyph text corroboration."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SourceAmortizedGlyphTextRecord] = None
    schema_version: str = SOURCE_AMORTIZED_GLYPH_TEXT_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SourceAmortizedGlyphTextResult:
    return SourceAmortizedGlyphTextResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> SourceAmortizedGlyphTextResult:
    return SourceAmortizedGlyphTextResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class SourceAmortizedGlyphTextAuthority:
    """Sealed lookup authority for published amortized glyph text records."""

    def __init__(
        self,
        records: Mapping[_Key, SourceAmortizedGlyphTextResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceAmortizedGlyphTextAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def resolve(self, selector: SourceAmortizedGlyphTextSelector) -> SourceAmortizedGlyphTextResult:
        if type(selector) is not SourceAmortizedGlyphTextSelector:
            raise TypeError("selector must be SourceAmortizedGlyphTextSelector")
        return self._records.get(selector.key, _abstained(AMORTIZED_TEXT_RECORD_UNAVAILABLE))


class SourceAmortizedGlyphTextProducer:
    """Producer for authenticating words via amortized font glyph verification."""

    def __init__(self, *, min_words: int = DEFAULT_MIN_WORDS, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourceAmortizedGlyphTextProducer must be obtained via create()")
        self.min_words = min_words
        self._ledger = GlyphMappingLedger(min_words=min_words)
        self._words_by_id: Dict[str, WordGlyphs] = {}
        self._results: Dict[_Key, SourceAmortizedGlyphTextResult] = {}

    @classmethod
    def create(cls, *, min_words: int = DEFAULT_MIN_WORDS) -> SourceAmortizedGlyphTextProducer:
        return cls(min_words=min_words, _seal=_PRODUCER_SEAL)

    def register_word(self, word: WordGlyphs) -> None:
        """Register a traced word and its glyph mapping evidence."""
        if type(word) is not WordGlyphs:
            raise TypeError("word must be WordGlyphs")
        self._words_by_id[word.observation_id] = word

    def record_direct_ocr_result(self, observation_id: str, success: bool) -> None:
        """Record the outcome of a direct OCR reading for an observation."""
        word = self._words_by_id.get(observation_id)
        if word is None:
            raise KeyError(f"observation {observation_id} not registered")
        self._ledger.record(word, bool(success))

    def plan_optimal_ocr_sample(
        self, words: Iterable[WordGlyphs], budget: int = 50
    ) -> List[WordGlyphs]:
        """Determine minimal sequence of words to attempt with OCR to verify all glyphs."""
        sample: List[WordGlyphs] = []
        temp_ledger = GlyphMappingLedger(min_words=self.min_words)
        # Seed with already recorded attempts
        for oid, ok in self._ledger._outcomes.items():
            temp_ledger.record(self._ledger._words[oid], ok)

        word_list = list(words)
        for _ in range(budget):
            candidate = temp_ledger.next_candidate(word_list)
            if candidate is None:
                break
            sample.append(candidate)
            # Optimistically assume positive outcome to find the next complementary word
            temp_ledger.record(candidate, True)
        return sample

    def evaluate_and_publish(
        self, selector: SourceAmortizedGlyphTextSelector
    ) -> SourceAmortizedGlyphTextResult:
        """Evaluate observation text against direct OCR or amortized glyph verification."""
        if type(selector) is not SourceAmortizedGlyphTextSelector:
            raise TypeError("selector must be SourceAmortizedGlyphTextSelector")

        word = self._words_by_id.get(selector.observation_id)
        if word is None:
            res = _abstained(GLYPHS_NOT_RECOVERED_CODE)
            self._results[selector.key] = res
            return res

        verification = self._ledger.verification()

        # 1. Check if directly corroborated via OCR
        direct_outcome = self._ledger._outcomes.get(selector.observation_id)
        if direct_outcome is not None:
            if not direct_outcome:
                res = _abstained(OCR_CORROBORATION_FAILED)
                self._results[selector.key] = res
                return res
            rec_id = stable_contract_id(
                "source_amortized_glyph_text",
                {
                    "document_id": selector.document_id,
                    "revision_id": selector.revision_id,
                    "source_sha256": selector.source_sha256,
                    "snapshot_id": selector.snapshot_id,
                    "page_id": selector.page_id,
                    "observation_id": selector.observation_id,
                },
            )
            record = SourceAmortizedGlyphTextRecord(
                record_id=rec_id,
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                observation_id=selector.observation_id,
                text=word.text,
                font_key=word.font_key,
                corroboration_method="DIRECT_OCR",
                verified_glyphs_count=len(word.glyphs),
                total_glyphs_count=len(word.glyphs),
                corroborating_evidence_ids=(selector.observation_id,),
                status=EvidenceResolutionStatus.CANDIDATE,
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                _seal=_RECORD_SEAL,
            )
            res = SourceAmortizedGlyphTextResult(
                status=EvidenceResolutionStatus.CANDIDATE,
                reason_codes=(DIRECT_OCR_CORROBORATED,),
                record=record,
            )
            self._results[selector.key] = res
            return res

        # 2. Amortized verification via verified font glyph mappings
        status = classify_word(word, verification)
        if status == GLYPH_CONTRADICTED:
            res = _conflict(GLYPH_CONTRADICTED_CODE)
            self._results[selector.key] = res
            return res

        if status == GLYPH_NOT_YET_VERIFIED:
            res = _abstained(GLYPH_MAPPING_UNDER_SUPPORTED)
            self._results[selector.key] = res
            return res

        if status != ALL_GLYPHS_VERIFIED:
            res = _abstained(GLYPHS_NOT_RECOVERED_CODE)
            self._results[selector.key] = res
            return res

        # All glyphs verified: mint authentic amortized record
        rec_id = stable_contract_id(
            "source_amortized_glyph_text",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "page_id": selector.page_id,
                "observation_id": selector.observation_id,
            },
        )

        # Collect the IDs of the direct OCR words that verified these glyphs
        supporting_words = tuple(
            sorted(oid for oid, ok in self._ledger._outcomes.items() if ok)
        )

        record = SourceAmortizedGlyphTextRecord(
            record_id=rec_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            observation_id=selector.observation_id,
            text=word.text,
            font_key=word.font_key,
            corroboration_method="AMORTIZED_GLYPH",
            verified_glyphs_count=len(word.glyphs),
            total_glyphs_count=len(word.glyphs),
            corroborating_evidence_ids=supporting_words,
            status=EvidenceResolutionStatus.CANDIDATE,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECORD_SEAL,
        )

        res = SourceAmortizedGlyphTextResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(AMORTIZED_GLYPH_CORROBORATED,),
            record=record,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> SourceAmortizedGlyphTextAuthority:
        return SourceAmortizedGlyphTextAuthority(self._results, _seal=_AUTHORITY_SEAL)
