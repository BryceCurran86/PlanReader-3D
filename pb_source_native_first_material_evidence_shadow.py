"""Default-off generic native-first material evidence with bounded targeted OCR fallback.

Implements an auditable, fail-closed routing and fail-fast corroboration helper
for material schedule / finish blocks across both native-vector and scanned
drawings without changing any OCR threshold or dropping scanned evidence:

- ``NATIVE_TRUSTED``: all words are already producer-trusted -> zero OCR calls.
- ``NATIVE_UNVERIFIED_TARGETED_OCR``: native words exist with admissible
  unverified glyph/clip reasons -> runs targeted OCR corroboration with
  mathematically equivalent fail-fast early exit on all-or-nothing blocks
  (stop corroborating remaining words once a required word fails).
- ``SCANNED_OR_CORRUPTED_OCR_REQUIRED``: no native words (scanned/image-only
  page) or corrupted/garbled glyph stream (U+FFFD / control characters) ->
  always routes to OCR fallback, never trusts native text naively.

Shadow-only (``shadow_only=True``, ``commercial_authority_granted=False``).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus


SCHEMA_VERSION = "1.0.0"

ADMISSIBLE_UNVERIFIED_NATIVE_REASONS = frozenset(
    {
        "text_glyph_mapping_unverified",
        "text_clip_state_unresolved",
    }
)


class MaterialEvidenceRoute(str, Enum):
    """Auditable native-first vs OCR routing decision for one material block."""

    NATIVE_TRUSTED = "native_trusted"
    NATIVE_UNVERIFIED_TARGETED_OCR = "native_unverified_targeted_ocr"
    SCANNED_OR_CORRUPTED_OCR_REQUIRED = "scanned_or_corrupted_ocr_required"


@dataclass(frozen=True)
class MaterialBlockWord:
    """Minimal producer-owned word record for native-first routing."""

    observation_id: str
    page_id: str
    text: str
    trusted: bool
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BoundedMaterialBlockResult:
    """Shadow-only result of native-first routing + bounded targeted OCR."""

    route: MaterialEvidenceRoute
    status: EvidenceResolutionStatus
    resolved_words: tuple[MaterialBlockWord, ...]
    ocr_calls_attempted: int
    ocr_calls_corroborated: int
    ocr_calls_skipped_fail_fast: int
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _has_corrupted_glyphs(text: str) -> bool:
    """Detect replacement characters or non-whitespace control characters."""
    for ch in text:
        if ch == "\ufffd":
            return True
        code = ord(ch)
        if code < 32 and ch not in ("\t", "\n", "\r"):
            return True
    return False


def classify_material_block_route(
    words: Sequence[MaterialBlockWord],
) -> MaterialEvidenceRoute:
    """Classify a material block into native-trusted, targeted-OCR, or scanned-OCR."""
    if not words:
        return MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED
    if any(_has_corrupted_glyphs(str(w.text)) for w in words):
        return MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED
    if all(bool(w.trusted) for w in words):
        return MaterialEvidenceRoute.NATIVE_TRUSTED
    for w in words:
        if w.trusted:
            continue
        reasons = {str(r).strip().lower() for r in w.reason_codes if str(r).strip()}
        if not reasons or not reasons.issubset(ADMISSIBLE_UNVERIFIED_NATIVE_REASONS):
            return MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED
    return MaterialEvidenceRoute.NATIVE_UNVERIFIED_TARGETED_OCR


def resolve_material_block_native_first_shadow(
    words: Sequence[MaterialBlockWord],
    *,
    corroborate_word: Callable[[MaterialBlockWord], Optional[str]],
    require_all_words_trusted: bool = True,
    max_ocr_calls: Optional[int] = None,
) -> BoundedMaterialBlockResult:
    """Resolve one material block with native-first trust and bounded targeted OCR.

    When ``require_all_words_trusted=True`` (matching all-or-nothing schedule
    title/row authentication), failing to corroborate any required unverified
    word immediately aborts remaining OCR calls in that block, producing the
    exact same abstention outcome without wasting clipped OCR renders.
    """
    if max_ocr_calls is not None and (isinstance(max_ocr_calls, bool) or max_ocr_calls < 0):
        raise ValueError("max_ocr_calls must be a non-negative integer or None")

    word_tuple = tuple(words)
    route = classify_material_block_route(word_tuple)

    if route is MaterialEvidenceRoute.NATIVE_TRUSTED:
        return BoundedMaterialBlockResult(
            route=route,
            status=EvidenceResolutionStatus.CORROBORATED,
            resolved_words=word_tuple,
            ocr_calls_attempted=0,
            ocr_calls_corroborated=0,
            ocr_calls_skipped_fail_fast=0,
            reason_codes=("native_text_already_trusted",),
        )

    if route is MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED:
        return BoundedMaterialBlockResult(
            route=route,
            status=EvidenceResolutionStatus.ABSTAINED,
            resolved_words=(),
            ocr_calls_attempted=0,
            ocr_calls_corroborated=0,
            ocr_calls_skipped_fail_fast=0,
            reason_codes=("scanned_or_corrupted_native_ocr_fallback_required",),
        )

    unverified_indices = [i for i, w in enumerate(word_tuple) if not w.trusted]
    resolved: list[MaterialBlockWord] = list(word_tuple)
    attempted = 0
    corroborated = 0

    for pos, idx in enumerate(unverified_indices):
        if max_ocr_calls is not None and attempted >= max_ocr_calls:
            skipped = len(unverified_indices) - pos
            return BoundedMaterialBlockResult(
                route=route,
                status=EvidenceResolutionStatus.ABSTAINED,
                resolved_words=tuple(resolved),
                ocr_calls_attempted=attempted,
                ocr_calls_corroborated=corroborated,
                ocr_calls_skipped_fail_fast=skipped,
                reason_codes=("targeted_ocr_budget_exhausted",),
            )
        word = word_tuple[idx]
        attempted += 1
        reading = corroborate_word(word)
        clean_reading = str(reading).strip() if reading is not None else ""
        if clean_reading and not _has_corrupted_glyphs(clean_reading):
            corroborated += 1
            resolved[idx] = MaterialBlockWord(
                observation_id=word.observation_id,
                page_id=word.page_id,
                text=clean_reading,
                trusted=True,
                reason_codes=tuple(dict.fromkeys((*word.reason_codes, "raster_text_corroborated"))),
            )
        elif require_all_words_trusted:
            skipped = len(unverified_indices) - (pos + 1)
            return BoundedMaterialBlockResult(
                route=route,
                status=EvidenceResolutionStatus.ABSTAINED,
                resolved_words=tuple(resolved),
                ocr_calls_attempted=attempted,
                ocr_calls_corroborated=corroborated,
                ocr_calls_skipped_fail_fast=skipped,
                reason_codes=("targeted_ocr_word_uncorroborated_fail_fast",),
            )

    all_trusted = all(w.trusted for w in resolved)
    return BoundedMaterialBlockResult(
        route=route,
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if all_trusted
            else EvidenceResolutionStatus.ABSTAINED
        ),
        resolved_words=tuple(resolved),
        ocr_calls_attempted=attempted,
        ocr_calls_corroborated=corroborated,
        ocr_calls_skipped_fail_fast=0,
        reason_codes=(
            ("targeted_ocr_corroborated",)
            if all_trusted
            else ("targeted_ocr_incomplete",)
        ),
    )


__all__ = [
    "ADMISSIBLE_UNVERIFIED_NATIVE_REASONS",
    "BoundedMaterialBlockResult",
    "MaterialBlockWord",
    "MaterialEvidenceRoute",
    "SCHEMA_VERSION",
    "classify_material_block_route",
    "resolve_material_block_native_first_shadow",
]
