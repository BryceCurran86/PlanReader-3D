"""Glyph-ledger text trust: decide which glyph-only-untrusted native words may become trusted text.

``PdfTextIntegrityAuthority`` cannot trust a word set in a font whose program cannot answer the glyph question (CID-keyed subsets without a Unicode
cmap): the only blocker is ``text_glyph_mapping_unverified``. ``pb_raster_text_corroboration_authority`` can corroborate one word at a time by
rendering the exact region at two scales and requiring the reading to equal the native claim. That is slow, so this module spends a limited number of
such readings where they settle the most glyphs, and lets a verified (font program, glyph id) -> character mapping authenticate the words that were
not read: a mapping is verified only when at least ``min_words`` independently corroborated words support it and no corroborated word disagrees.

This module is pure decision logic. It performs no recognition, reads no image and no PDF, and knows no project, file name, page number or expected
value. The corroboration outcome is an injected function that must return a real ``bool``; production wires it to a sealed ``CORROBORATED``
``RasterTextCorroborationRecord`` (never to a caller assertion). Nothing here changes a receipt in place: ``upgraded_text_integrity_receipt`` mints a
new receipt for a word whose ONLY blocker was the glyph proof, and refuses any word that has another blocker (clip, paint, trace, font binding,
Unicode, visibility).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence

from pb_font_glyph_mapping_corroboration_shadow import (
    ALL_GLYPHS_VERIFIED,
    DEFAULT_MIN_WORDS,
    GLYPH_CONTRADICTED,
    GlyphMappingLedger,
    WordGlyphs,
    classify_word,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    NativeTextIntegrityDecision,
    PdfTextIntegrityReceipt,
    build_pdf_text_integrity_receipt,
)

GLYPH_LEDGER_TEXT_TRUST_SCHEMA_VERSION = "1.0.0"

DECODE_STATUS_DIRECT_RASTER = "raster_corroborated_direct"
DECODE_STATUS_AMORTIZED_GLYPH = "amortized_glyph_verified"

METHOD_DIRECT_RASTER = "direct_raster"
METHOD_AMORTIZED_GLYPH = "amortized_glyph"

REASON_DIRECT_RASTER_CORROBORATED = "direct_raster_corroborated"
REASON_AMORTIZED_GLYPH_VERIFIED = "amortized_glyph_verified"
REASON_GLYPH_MAPPING_UNDER_SUPPORTED = "glyph_mapping_under_supported"
REASON_GLYPH_CONTRADICTED = "glyph_contradicted"
REASON_GLYPHS_NOT_RECOVERED = "glyphs_not_recovered"

_PROVEN_VISIBLE = "proven_visible"


@dataclass(frozen=True)
class GlyphTextCandidate:
    """One glyph-only-untrusted native word. ``word`` is None when its glyphs could not be recovered from the PDF's own trace."""

    observation_id: str
    word: Optional[WordGlyphs]


@dataclass(frozen=True)
class GlyphTextTrustDecision:
    observation_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    method: str = ""
    corroborating_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GlyphTextTrustResult:
    decisions: Mapping[str, GlyphTextTrustDecision]
    attempted_observation_ids: tuple[str, ...]
    corroborated_observation_ids: tuple[str, ...]
    verified_glyph_count: int
    contradicted_glyph_count: int
    min_words: int
    schema_version: str = GLYPH_LEDGER_TEXT_TRUST_SCHEMA_VERSION


def is_glyph_only_untrusted(receipt: object) -> bool:
    """True only for an untrusted receipt whose SOLE blocker is the glyph proof and whose visibility is proven."""
    return (
        type(receipt) is PdfTextIntegrityReceipt
        and receipt.trusted is False
        and tuple(receipt.reason_codes) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        and receipt.visibility_status == _PROVEN_VISIBLE
    )


def _validated_candidates(candidates: Sequence[GlyphTextCandidate]) -> list[GlyphTextCandidate]:
    seen: set[str] = set()
    for candidate in candidates:
        if type(candidate) is not GlyphTextCandidate:
            raise TypeError("candidates must be GlyphTextCandidate")
        if type(candidate.observation_id) is not str or not candidate.observation_id:
            raise ValueError("candidate observation_id must be a non-empty string")
        if candidate.observation_id in seen:
            raise ValueError(f"duplicate candidate observation {candidate.observation_id}")
        seen.add(candidate.observation_id)
        if candidate.word is not None and (
            type(candidate.word) is not WordGlyphs
            or candidate.word.observation_id != candidate.observation_id
        ):
            raise ValueError("candidate word glyph evidence belongs to another observation")
    return sorted(candidates, key=lambda candidate: candidate.observation_id)


def decide_glyph_text_trust(
    candidates: Sequence[GlyphTextCandidate],
    corroborate: Callable[[str], bool],
    *,
    min_words: int = DEFAULT_MIN_WORDS,
    max_attempts: Optional[int] = None,
) -> GlyphTextTrustResult:
    """Spend corroboration attempts where they settle the most glyphs, then decide every candidate.

    ``corroborate(observation_id)`` must return a real ``bool``: True only when the raster corroboration authority itself corroborated that word.
    A failed attempt casts no vote. A word is trusted when it was corroborated itself, or when every glyph in it is verified by at least
    ``min_words`` corroborated words and none contradicts it. A contradicted glyph makes every word that uses it a CONFLICT.
    """
    if type(min_words) is not int or min_words < 2:
        raise ValueError("min_words must be an integer >= 2; one word cannot verify a glyph")
    if max_attempts is not None and (type(max_attempts) is not int or max_attempts < 0):
        raise ValueError("max_attempts must be a non-negative integer or None")
    ordered = _validated_candidates(candidates)
    recovered = [candidate.word for candidate in ordered if candidate.word is not None]

    ledger = GlyphMappingLedger(min_words=min_words)
    attempted: list[str] = []
    corroborated: dict[str, WordGlyphs] = {}
    while max_attempts is None or len(attempted) < max_attempts:
        chosen = ledger.next_candidate(recovered)
        if chosen is None:
            break
        outcome = corroborate(chosen.observation_id)
        if type(outcome) is not bool:
            raise TypeError("corroborate must return a real bool")
        ledger.record(chosen, outcome)
        attempted.append(chosen.observation_id)
        if outcome:
            corroborated[chosen.observation_id] = chosen

    verification = ledger.verification()
    decisions: dict[str, GlyphTextTrustDecision] = {}
    for candidate in ordered:
        oid = candidate.observation_id
        word = candidate.word
        if word is None:
            decisions[oid] = GlyphTextTrustDecision(
                oid, EvidenceResolutionStatus.ABSTAINED, (REASON_GLYPHS_NOT_RECOVERED,))
            continue
        state = classify_word(word, verification)
        if state == GLYPH_CONTRADICTED:
            decisions[oid] = GlyphTextTrustDecision(
                oid, EvidenceResolutionStatus.CONFLICT, (REASON_GLYPH_CONTRADICTED,))
        elif oid in corroborated:
            decisions[oid] = GlyphTextTrustDecision(
                oid, EvidenceResolutionStatus.CORROBORATED, (REASON_DIRECT_RASTER_CORROBORATED,),
                METHOD_DIRECT_RASTER, (oid,))
        elif state == ALL_GLYPHS_VERIFIED:
            pairs = {pair for pair, _char in word.pairs()}
            supporters = tuple(sorted(
                other_id for other_id, other in corroborated.items()
                if pairs & {pair for pair, _char in other.pairs()}))
            decisions[oid] = GlyphTextTrustDecision(
                oid, EvidenceResolutionStatus.CORROBORATED, (REASON_AMORTIZED_GLYPH_VERIFIED,),
                METHOD_AMORTIZED_GLYPH, supporters)
        else:
            decisions[oid] = GlyphTextTrustDecision(
                oid, EvidenceResolutionStatus.ABSTAINED, (REASON_GLYPH_MAPPING_UNDER_SUPPORTED,))
    return GlyphTextTrustResult(
        decisions=MappingProxyType(decisions),
        attempted_observation_ids=tuple(attempted),
        corroborated_observation_ids=tuple(sorted(corroborated)),
        verified_glyph_count=len(verification.verified),
        contradicted_glyph_count=len(verification.contradicted),
        min_words=min_words,
    )


def upgraded_text_integrity_receipt(
    base: PdfTextIntegrityReceipt, decision: GlyphTextTrustDecision,
) -> PdfTextIntegrityReceipt:
    """Mint a NEW trusted receipt for a word whose only blocker was the glyph proof. The base receipt is not changed."""
    if not is_glyph_only_untrusted(base):
        raise ValueError("only a receipt whose sole blocker is the glyph proof can be upgraded")
    if type(decision) is not GlyphTextTrustDecision:
        raise TypeError("decision must be GlyphTextTrustDecision")
    if decision.observation_id != base.parent_observation_id:
        raise ValueError("decision belongs to another word")
    if decision.status is not EvidenceResolutionStatus.CORROBORATED or decision.method not in {
        METHOD_DIRECT_RASTER, METHOD_AMORTIZED_GLYPH,
    }:
        raise ValueError("only a corroborated decision can upgrade a receipt")
    status = (
        DECODE_STATUS_DIRECT_RASTER
        if decision.method == METHOD_DIRECT_RASTER
        else DECODE_STATUS_AMORTIZED_GLYPH
    )
    return build_pdf_text_integrity_receipt(
        parent_observation_id=base.parent_observation_id,
        document_id=base.document_id,
        revision_id=base.revision_id,
        source_sha256=base.source_sha256,
        page_id=base.page_id,
        source_partition_id=base.source_partition_id,
        geometry=base.geometry,
        decision=NativeTextIntegrityDecision(
            trusted=True,
            raw_text=base.raw_text,
            decode_status=status,
            visibility_status=base.visibility_status,
            reason_codes=(),
            font_xref=base.font_xref,
            font_subtype=base.font_subtype,
            font_name=base.font_name,
            sequence_number=base.sequence_number,
            trace_sequence_numbers=tuple(base.trace_sequence_numbers),
        ),
        block_no=base.block_no,
        line_no=base.line_no,
        word_no=base.word_no,
    )


__all__ = [
    "DECODE_STATUS_AMORTIZED_GLYPH",
    "DECODE_STATUS_DIRECT_RASTER",
    "GLYPH_LEDGER_TEXT_TRUST_SCHEMA_VERSION",
    "GlyphTextCandidate",
    "GlyphTextTrustDecision",
    "GlyphTextTrustResult",
    "decide_glyph_text_trust",
    "is_glyph_only_untrusted",
    "upgraded_text_integrity_receipt",
]
