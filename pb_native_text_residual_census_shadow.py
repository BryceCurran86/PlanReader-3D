"""Default-off, read-only census of the RESIDUAL untrusted native words of a published revision, strictly SHADOW.

The producer-owned text-integrity authority trusts most native words of a drawing and leaves the rest untrusted
for typed reasons. Every downstream chain that reads a label, a tag, a dimension or a schedule sees only the
trusted words, and the plan callout shadow has to treat a ring around an untrusted word as an unverified rival.
This module answers one narrow question: for each requested page of a published revision, which words remain
untrusted, with which typed reason set, set in which font program class, under which clip state, and where?

It re-derives everything from the producer itself: the published revision, the current-revision check, the
immutable source bytes (SHA checked), and one `resolve_text` call per native word through the producer's own
text-integrity authority. A word is trusted only when that authority corroborates it as trusted text; every other
word keeps the reason codes the authority issued. The font of an untrusted word is read from the same immutable
bytes: the span of the page whose box contains the centre of the word's box names the font, the page's own font
list names the font program class, and the authority's receipt keeps whatever font binding it made itself. The
join never chooses between candidates: a word whose centre lies in no span is `font_unresolved`, one whose
containing spans carry different fonts is `font_ambiguous`, and every candidate font stays on the record.

The census is a count and a list of locations. It decides no text, no trust, no tag, no host, no scale, no count
and no quantity. An untrusted word's text is NEVER an identity: no word text is stored, only the receipt's text
length and one boolean, whether that raw text matches the generic opening tag syntax, kept solely as a census
counter. It never produces a `PhysicalOpeningExistenceRecord`, never writes any cache of any opening authority,
and imports nothing from the live issuer, the schedule binder, the host binder or the count producer.

What the census does write: reading a word through `resolve_text` refills the producer's verified-read memo
(`verified_resolution_cache`), a disposable acceleration hint that every consumer of the text authority refills in
the same way; no answer of any authority depends on it. Nothing else of the producer is assigned, deleted or
replaced (an AST guard and a state-comparison test pin this).

What the authority exposes about a word's clip state is only its two clip reason codes, and the census reports
exactly those; the only transform information it adds is the direction of the line holding the word, read from the
same source bytes. A receipt of another document, revision or source, or one whose box or fields cannot be read,
is never censused as this page's word: the page ABSTAINS with a typed reason.

Untrusted-word records are capped by a work bound; a page that exceeds it ABSTAINS with a typed reason rather
than returning a partial census.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, fields
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_opening_tag_normalization import normalize_opening_tag
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_CLIPPED_BY_CLIP_REGION,
    TEXT_TRACE_AMBIGUOUS,
    TEXT_TRACE_UNAVAILABLE,
    TRUSTED_PDF_TEXT,
)
from pb_physical_opening_authority import SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, VISIBLE_SOURCE_AUTHORITY_REQUIRED
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

NATIVE_TEXT_RESIDUAL_CENSUS_SCHEMA_VERSION = "1.0.0"
RESIDUAL_CENSUS_METHOD = "native_text_residual_census_shadow"

# census-local reason codes (the only new strings besides the standing limits and the font labels)
CENSUS_DISABLED = "native_text_residual_census_disabled"
CENSUS_PRODUCED = "native_text_residual_census_produced"
CENSUS_PAGE_HAS_NO_NATIVE_TEXT_RECEIPTS = "native_text_residual_census_page_has_no_native_text_receipts"
CENSUS_BUDGET_EXCEEDED = "native_text_residual_census_budget_exceeded"
CENSUS_FOREIGN_RECORD = "native_text_residual_census_foreign_record"
CENSUS_DUPLICATE_OBSERVATION = "native_text_residual_census_duplicate_observation"
CENSUS_WORD_UNPLACEABLE = "native_text_residual_census_word_unplaceable"
CENSUS_TEXT_RECEIPT_UNAVAILABLE = "native_text_residual_census_text_receipt_unavailable"
CENSUS_PAGE_INCOMPLETE = "native_text_residual_census_page_incomplete"
CENSUS_UNTYPED_UNTRUSTED_WORD = "native_text_residual_census_untrusted_word_without_typed_reason"

# standing capability limits, never atom kinds
CENSUS_IS_NOT_TEXT_AUTHORITY = "census_counts_are_not_text_authority"
UNTRUSTED_WORD_TEXT_NEVER_AN_IDENTITY = "untrusted_word_text_is_never_an_identity"
STANDING_LIMITS = (CENSUS_IS_NOT_TEXT_AUTHORITY, UNTRUSTED_WORD_TEXT_NEVER_AN_IDENTITY)

# font join outcomes and labels
SPAN_FONT_RESOLVED = "span_font_resolved"
FONT_UNRESOLVED = "font_unresolved"
FONT_AMBIGUOUS = "font_ambiguous"
FONT_CLASS_UNRESOLVED = "font_class_unresolved"
FONT_CLASS_AMBIGUOUS = "font_class_ambiguous"
FONT_CLASS_CONFLICT = "font_class_conflict"
FONT_NOT_IN_PAGE_FONT_LIST = "font_not_in_page_font_list"
CLASS_BASIS_RECEIPT_XREF = "receipt_font_xref"
CLASS_BASIS_SPAN_FONT_NAME = "span_font_name"
CLASS_BASIS_NONE = "none"
PROGRAM_NOT_EMBEDDED = "not_embedded"
PROGRAM_TYPE3_GLYPH_PROCEDURES = "type3_glyph_procedures"

# clip states, derived only from the reason codes the authority itself issued
CLIP_STATE_UNRESOLVED = "clip_state_unresolved"
CLIP_CLIPPED = "clipped_by_clip_region"
CLIP_UNRESOLVED_AND_CLIPPED = "clip_state_unresolved_and_clipped"
CLIP_NOT_EVALUATED_NO_TRACE = "clip_not_evaluated_no_trace"
NO_CLIP_REASON = "no_clip_reason"

# baseline directions of the line holding the word (page y grows downwards)
BASELINE_EAST = "baseline_east"
BASELINE_NORTH = "baseline_north"
BASELINE_WEST = "baseline_west"
BASELINE_SOUTH = "baseline_south"
BASELINE_OBLIQUE = "baseline_oblique"
DIRECTION_UNRESOLVED = "direction_unresolved"

# Work bounds only: they stop a pathological page from being analysed, they decide nothing.
DEFAULT_MAX_UNTRUSTED_RECORDS = 100_000
_MAX_WORDS_PER_PAGE = 250_000
_MAX_PAGES_PER_CALL = 64
_GRID_CELL_PT = 32.0              # acceleration only: the containment test applied afterwards is exact
_MAX_CELLS_PER_SPAN = 4096
_DIRECTION_NOISE = 1e-3           # float noise on a unit direction vector, a label boundary and nothing else

_STATUSES = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED)

_GRANT_FLAGS = (
    "trusted_text_granted", "text_identity_granted", "text_trust_changed", "physical_opening_granted",
    "scale_granted", "metric_granted", "count_granted", "quantity_granted", "commercial_projection_allowed",
    "customer_publication_granted", "takeoff_eligible", "deduction_authority", "existence_record_issued",
)


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CensusRoot:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str


@dataclass(frozen=True)
class CensusOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str

    def root(self) -> CensusRoot:
        return CensusRoot(self.document_id, self.revision_id, self.snapshot_id, self.source_sha256)

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (self.document_id, self.revision_id, self.snapshot_id, self.source_sha256, self.page_id)


@dataclass(frozen=True)
class PageFont:
    """One entry of the page's own font list, read from the immutable source bytes."""

    xref: int
    subtype: str
    base_font: str              # the subset tag is removed
    encoding: str
    program: str                # "not_embedded" | "embedded_<format>"
    has_to_unicode: Optional[bool]
    font_class: str


@dataclass(frozen=True)
class SpanRecord:
    """One text span of the page: its box, bare font name, style flags and the direction of its line."""

    bbox: tuple[float, float, float, float]
    font_name: str
    flags: int
    direction: tuple[float, float]


@dataclass(frozen=True)
class FontJoin:
    join_status: str
    font_label: str                       # the bare font name, or `font_unresolved` / `font_ambiguous`
    candidate_fonts: tuple[str, ...]      # every distinct font of the containing spans, never reduced to one
    containing_span_count: int
    span_flags: Optional[int]
    line_direction: str
    font_class: str
    font_class_basis: str
    font_sources_agree: Optional[bool]    # receipt binding vs span font; None when only one source exists


@dataclass(frozen=True)
class WordIntegrityRecord:
    """What the text-integrity authority said about ONE native word (an input of the pure core).

    `text_length` and `matches_opening_tag_syntax` exist for untrusted words only: they are census counters,
    and an untrusted word's text is never kept."""

    ownership: CensusOwnership
    observation_id: str
    bbox: tuple[float, float, float, float]
    trusted: bool
    authority_status: EvidenceResolutionStatus   # the text authority's own status for the word, not a census verdict
    reason_codes: tuple[str, ...]            # as issued by the authority's result
    receipt_reason_codes: tuple[str, ...]    # as issued by the producer's receipt
    decode_status: str
    visibility_status: str
    receipt_font_xref: Optional[int]
    receipt_font_subtype: str
    receipt_font_name: str
    sequence_number: Optional[int]
    text_length: Optional[int]
    matches_opening_tag_syntax: Optional[bool]

    def __post_init__(self) -> None:
        if (len(self.bbox) != 4 or not all(type(v) in (int, float) and math.isfinite(v) for v in self.bbox)):
            raise ValueError("a word record needs a finite four number box")
        object.__setattr__(self, "bbox", tuple(float(v) for v in self.bbox))
        if not self.observation_id:
            raise ValueError("a word record needs an observation id")
        if self.trusted:
            if (self.authority_status is not EvidenceResolutionStatus.CORROBORATED or self.text_length is not None
                    or self.matches_opening_tag_syntax is not None):
                raise ValueError("a trusted word is CORROBORATED and carries no text counters")
        elif (type(self.text_length) is not int or self.text_length < 0
                or type(self.matches_opening_tag_syntax) is not bool):
            raise ValueError("an untrusted word carries its text length and the tag syntax boolean")


@dataclass(frozen=True)
class UntrustedWord:
    ownership: CensusOwnership
    record_id: str
    observation_id: str
    bbox: tuple[float, float, float, float]
    authority_status: EvidenceResolutionStatus     # as issued by the text authority (ABSTAINED or CONFLICT)
    reason_codes: tuple[str, ...]
    reason_set: tuple[str, ...]              # sorted, unique, never empty
    decode_status: str
    visibility_status: str
    clip_state: str
    clip_reason_codes: tuple[str, ...]
    font: FontJoin
    receipt_font_xref: Optional[int]
    receipt_font_subtype: str
    receipt_font_name: str
    sequence_number: Optional[int]
    text_length: int
    matches_opening_tag_syntax: bool


def _check_grants(record) -> None:
    if record.shadow_only is not True:
        raise ValueError("a native text residual census cannot leave shadow mode")
    for name in _GRANT_FLAGS:
        if getattr(record, name) is not False:
            raise ValueError(f"a native text residual census cannot grant {name}")
    if not set(_GRANT_FLAGS) <= {f.name for f in fields(record)}:
        raise ValueError("grant flag set is out of date")


@dataclass(frozen=True)
class PageResidualCensus:
    ownership: CensusOwnership
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    total_count: int
    trusted_count: int
    untrusted_count: int
    page_fonts: tuple[PageFont, ...]
    reason_set_histogram: tuple[tuple[tuple[str, ...], int], ...]
    font_reason_histogram: tuple[tuple[tuple[str, tuple[str, ...]], int], ...]
    font_class_reason_histogram: tuple[tuple[tuple[str, tuple[str, ...]], int], ...]
    clip_state_histogram: tuple[tuple[str, int], ...]
    untrusted_matching_opening_tag_syntax: int
    untrusted_words: tuple[UntrustedWord, ...]
    evidence_atoms: tuple[EvidenceAtom, ...]
    record_id: str
    shadow_only: bool = True
    trusted_text_granted: bool = False
    text_identity_granted: bool = False
    text_trust_changed: bool = False
    physical_opening_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    existence_record_issued: bool = False
    schema_version: str = NATIVE_TEXT_RESIDUAL_CENSUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_grants(self)
        if self.status not in _STATUSES:
            raise ValueError("a page census is CANDIDATE or ABSTAINED only")
        if any(atom.status not in _STATUSES for atom in self.evidence_atoms):
            raise ValueError("evidence atoms are CANDIDATE or ABSTAINED only")
        if self.status is EvidenceResolutionStatus.ABSTAINED:
            if (self.total_count or self.trusted_count or self.untrusted_count or self.untrusted_words
                    or self.reason_set_histogram or self.font_reason_histogram or self.font_class_reason_histogram
                    or self.clip_state_histogram or self.untrusted_matching_opening_tag_syntax):
                raise ValueError("an abstained page census carries no census data")
            return
        words = self.untrusted_words
        if (self.trusted_count < 0 or self.total_count != self.trusted_count + self.untrusted_count
                or self.untrusted_count != len(words)
                or any(w.ownership != self.ownership or not w.reason_set for w in words)
                or [w.observation_id for w in words] != sorted({w.observation_id for w in words})
                or self.untrusted_matching_opening_tag_syntax != sum(w.matches_opening_tag_syntax for w in words)
                # every histogram is the exact tally of the word list, not merely a list with the right total
                or self.reason_set_histogram != _histogram(w.reason_set for w in words)
                or self.font_reason_histogram != _histogram((w.font.font_label, w.reason_set) for w in words)
                or self.font_class_reason_histogram != _histogram((w.font.font_class, w.reason_set) for w in words)
                or self.clip_state_histogram != _histogram(w.clip_state for w in words)):
            raise ValueError("a CANDIDATE page census must account for every word it counts")


@dataclass(frozen=True)
class NativeTextResidualCensus:
    root: Optional[CensusRoot]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    requested_page_ids: tuple[int, ...]
    pages: tuple[PageResidualCensus, ...]
    text_ids_without_receipt: int
    record_id: Optional[str]
    shadow_only: bool = True
    trusted_text_granted: bool = False
    text_identity_granted: bool = False
    text_trust_changed: bool = False
    physical_opening_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    existence_record_issued: bool = False
    schema_version: str = NATIVE_TEXT_RESIDUAL_CENSUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _check_grants(self)
        if self.status not in _STATUSES:
            raise ValueError("a native text residual census is CANDIDATE or ABSTAINED only")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            if (self.root is None or not self.pages or self.text_ids_without_receipt
                    or any(p.status is not EvidenceResolutionStatus.CANDIDATE for p in self.pages)
                    or tuple(int(p.ownership.page_id) for p in self.pages) != self.requested_page_ids
                    or any(p.ownership.root() != self.root for p in self.pages)):
                raise ValueError("a CANDIDATE census needs a CANDIDATE census of every requested page")


# --------------------------------------------------------------------------------------
# pure core
# --------------------------------------------------------------------------------------


def bare_font_name(name: object) -> str:
    """A font name without its subset tag (`ABCDEF+Name` becomes `Name`)."""
    text = str(name or "")
    if len(text) > 7 and text[6] == "+" and text[:6].isalpha() and text[:6].isupper():
        return text[7:]
    return text


def font_class_of(subtype: str, program: str, encoding: str, has_to_unicode: Optional[bool]) -> str:
    """The structural class of a font program: subtype, embedded format, encoding and ToUnicode presence."""
    unicode_map = "tounicode_unreadable" if has_to_unicode is None else ("tounicode" if has_to_unicode else "no_tounicode")
    return "/".join((subtype or "subtype_unknown", program, encoding or "no_encoding", unicode_map))


def program_class(extension: object, subtype: object = "") -> str:
    """The font program class: a Type3 font has glyph procedures instead of a font program (not 'not embedded')."""
    if str(subtype or "").strip().lower() == "type3":
        return PROGRAM_TYPE3_GLYPH_PROCEDURES
    text = str(extension or "").strip().lower()
    return PROGRAM_NOT_EMBEDDED if text in ("", "n/a") else f"embedded_{text}"


def direction_class(direction: Sequence[float]) -> str:
    try:
        dx, dy = float(direction[0]), float(direction[1])
    except (TypeError, ValueError, IndexError):
        return DIRECTION_UNRESOLVED
    if not (math.isfinite(dx) and math.isfinite(dy)) or (dx == 0.0 and dy == 0.0):
        return DIRECTION_UNRESOLVED
    norm = math.hypot(dx, dy)
    dx, dy = dx / norm, dy / norm
    if abs(dy) <= _DIRECTION_NOISE:
        return BASELINE_EAST if dx > 0 else BASELINE_WEST
    if abs(dx) <= _DIRECTION_NOISE:
        return BASELINE_SOUTH if dy > 0 else BASELINE_NORTH
    return BASELINE_OBLIQUE


class SpanIndex:
    """A uniform grid over span boxes. It only narrows the candidates; membership is decided exactly."""

    def __init__(self, spans: Sequence[SpanRecord]):
        self._cells: dict[tuple[int, int], list[SpanRecord]] = {}
        self._wide: list[SpanRecord] = []
        for span in spans:
            x0, y0, x1, y1 = span.bbox
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 < x0 or y1 < y0:
                continue
            ix0, ix1 = math.floor(x0 / _GRID_CELL_PT), math.floor(x1 / _GRID_CELL_PT)
            iy0, iy1 = math.floor(y0 / _GRID_CELL_PT), math.floor(y1 / _GRID_CELL_PT)
            if (ix1 - ix0 + 1) * (iy1 - iy0 + 1) > _MAX_CELLS_PER_SPAN:
                self._wide.append(span)
                continue
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    self._cells.setdefault((ix, iy), []).append(span)

    def containing(self, x: float, y: float) -> tuple[SpanRecord, ...]:
        key = (math.floor(x / _GRID_CELL_PT), math.floor(y / _GRID_CELL_PT))
        candidates = (*self._cells.get(key, ()), *self._wide)
        return tuple(s for s in candidates if s.bbox[0] <= x <= s.bbox[2] and s.bbox[1] <= y <= s.bbox[3])


def join_word_font(
    bbox: Sequence[float], index: SpanIndex, fonts_by_xref: dict, fonts_by_name: dict,
    receipt_font_xref: Optional[int],
) -> FontJoin:
    """Name the font of one word, retaining every candidate and choosing none."""
    spans = index.containing(bbox[0] * 0.5 + bbox[2] * 0.5, bbox[1] * 0.5 + bbox[3] * 0.5)   # no overflow near the float limit
    names = tuple(sorted({s.font_name for s in spans}))
    if not spans:
        status, label = FONT_UNRESOLVED, FONT_UNRESOLVED
    elif len(names) > 1:
        status, label = FONT_AMBIGUOUS, FONT_AMBIGUOUS
    else:
        status, label = SPAN_FONT_RESOLVED, names[0]
    flags = {s.flags for s in spans}
    span_flags = next(iter(flags)) if status == SPAN_FONT_RESOLVED and len(flags) == 1 else None
    directions = {direction_class(s.direction) for s in spans}
    line_direction = next(iter(directions)) if len(directions) == 1 else DIRECTION_UNRESOLVED

    agree: Optional[bool] = None
    receipt_entry = fonts_by_xref.get(receipt_font_xref) if receipt_font_xref is not None else None
    if receipt_font_xref is not None:
        if receipt_entry is None:
            font_class, basis = FONT_NOT_IN_PAGE_FONT_LIST, CLASS_BASIS_RECEIPT_XREF
        else:
            basis = CLASS_BASIS_RECEIPT_XREF
            font_class = receipt_entry.font_class
            if spans:
                agree = receipt_entry.base_font in names
                if not agree:
                    font_class = FONT_CLASS_CONFLICT
    elif status == SPAN_FONT_RESOLVED:
        classes = {f.font_class for f in fonts_by_name.get(label, ())}
        basis = CLASS_BASIS_SPAN_FONT_NAME
        font_class = (FONT_NOT_IN_PAGE_FONT_LIST if not classes
                      else next(iter(classes)) if len(classes) == 1 else FONT_CLASS_AMBIGUOUS)
    else:
        font_class, basis = FONT_CLASS_UNRESOLVED, CLASS_BASIS_NONE
    return FontJoin(
        join_status=status, font_label=label, candidate_fonts=names, containing_span_count=len(spans),
        span_flags=span_flags, line_direction=line_direction, font_class=font_class, font_class_basis=basis,
        font_sources_agree=agree)


def clip_state_of(receipt_reason_codes: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    """The clip state, from the reason codes the producer's own receipt issued (never recomputed)."""
    reasons = set(receipt_reason_codes)
    unresolved, clipped = TEXT_CLIP_STATE_UNRESOLVED in reasons, TEXT_CLIPPED_BY_CLIP_REGION in reasons
    clip_codes = tuple(c for c in (TEXT_CLIP_STATE_UNRESOLVED, TEXT_CLIPPED_BY_CLIP_REGION) if c in reasons)
    if unresolved and clipped:
        return CLIP_UNRESOLVED_AND_CLIPPED, clip_codes
    if unresolved:
        return CLIP_STATE_UNRESOLVED, clip_codes
    if clipped:
        return CLIP_CLIPPED, clip_codes
    if TEXT_TRACE_UNAVAILABLE in reasons or TEXT_TRACE_AMBIGUOUS in reasons:
        return CLIP_NOT_EVALUATED_NO_TRACE, ()
    return NO_CLIP_REASON, ()


def _atom_for(ownership: CensusOwnership, status: EvidenceResolutionStatus, reasons: tuple[str, ...],
              record_id: str, counts: dict) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=stable_contract_id("shadow_native_text_residual_atom", {"record": record_id}),
        document_id=ownership.document_id, page_id=ownership.page_id, kind=KIND_UNKNOWN,
        method=RESIDUAL_CENSUS_METHOD, viewport_id=None, bbox=None, status=status, reason_codes=reasons,
        metadata={
            "revision_id": ownership.revision_id, "source_sha256": ownership.source_sha256,
            "snapshot_id": ownership.snapshot_id, "polarity": POLARITY_UNKNOWN, **counts,
            **{flag: False for flag in _GRANT_FLAGS}})


def _page_record(ownership: CensusOwnership, status: EvidenceResolutionStatus, reasons: tuple[str, ...],
                 *, total: int = 0, trusted: int = 0, page_fonts: tuple[PageFont, ...] = (),
                 untrusted: tuple[UntrustedWord, ...] = (), reason_hist=(), font_hist=(), class_hist=(),
                 clip_hist=(), tag_matches: int = 0) -> PageResidualCensus:
    record_id = stable_contract_id("shadow_native_text_residual_census_page", {
        "root": ownership.as_tuple(), "status": status.value, "reasons": reasons, "total": total, "trusted": trusted,
        "words": tuple(w.record_id for w in untrusted), "reason_hist": reason_hist, "font_hist": font_hist,
        "class_hist": class_hist, "clip_hist": clip_hist, "tag_matches": tag_matches})
    atom = _atom_for(ownership, status, reasons, record_id,
                     {"total_count": total, "trusted_count": trusted, "untrusted_count": len(untrusted)})
    return PageResidualCensus(
        ownership=ownership, status=status, reason_codes=reasons, standing_limits=STANDING_LIMITS,
        total_count=total, trusted_count=trusted, untrusted_count=len(untrusted), page_fonts=page_fonts,
        reason_set_histogram=reason_hist, font_reason_histogram=font_hist, font_class_reason_histogram=class_hist,
        clip_state_histogram=clip_hist, untrusted_matching_opening_tag_syntax=tag_matches,
        untrusted_words=untrusted, evidence_atoms=(atom,), record_id=record_id)


def abstained_page(ownership: CensusOwnership, reason: str) -> PageResidualCensus:
    return _page_record(ownership, EvidenceResolutionStatus.ABSTAINED, (reason,))


def _histogram(keys) -> tuple:
    return tuple(sorted(Counter(keys).items()))


def classify_residuals(
    records: Sequence[WordIntegrityRecord], *, ownership: CensusOwnership,
    page_fonts: Sequence[PageFont] = (), spans: Sequence[SpanRecord] = (),
    max_untrusted_records: int = DEFAULT_MAX_UNTRUSTED_RECORDS,
) -> PageResidualCensus:
    """Pure core over records the adapter has already re-derived from the producer.

    Counts every word, and for every untrusted one keeps the authority's reason set, the font join, the clip
    state and the location. A foreign or duplicated record, or too many untrusted words, ABSTAIN."""
    if type(max_untrusted_records) is not int or max_untrusted_records <= 0:
        raise ValueError("the untrusted record bound must be a positive integer")
    records = tuple(records)
    if any(type(r) is not WordIntegrityRecord for r in records):
        raise TypeError("records must be WordIntegrityRecord instances")
    if any(r.ownership != ownership for r in records):
        return abstained_page(ownership, CENSUS_FOREIGN_RECORD)
    if len({r.observation_id for r in records}) != len(records):
        return abstained_page(ownership, CENSUS_DUPLICATE_OBSERVATION)
    untrusted_records = sorted((r for r in records if not r.trusted), key=lambda r: r.observation_id)
    if len(untrusted_records) > max_untrusted_records:
        return abstained_page(ownership, CENSUS_BUDGET_EXCEEDED)

    fonts_by_xref = {f.xref: f for f in page_fonts}
    fonts_by_name: dict[str, list[PageFont]] = {}
    for font in fonts_by_xref.values():
        fonts_by_name.setdefault(font.base_font, []).append(font)
    index = SpanIndex(spans) if untrusted_records else SpanIndex(())
    words: list[UntrustedWord] = []
    for r in untrusted_records:
        reason_set = tuple(sorted(set(r.reason_codes))) or (CENSUS_UNTYPED_UNTRUSTED_WORD,)
        clip_state, clip_codes = clip_state_of(r.receipt_reason_codes)
        join = join_word_font(r.bbox, index, fonts_by_xref, fonts_by_name, r.receipt_font_xref)
        record_id = stable_contract_id("shadow_untrusted_native_word", {
            "root": ownership.as_tuple(), "id": r.observation_id, "status": r.authority_status.value,
            "reasons": reason_set, "issued": tuple(r.reason_codes), "receipt_reasons": tuple(r.receipt_reason_codes),
            "bbox": r.bbox, "font": join.font_label, "candidates": join.candidate_fonts, "class": join.font_class,
            "basis": join.font_class_basis, "direction": join.line_direction, "clip": clip_state,
            "decode": r.decode_status, "visibility": r.visibility_status, "xref": r.receipt_font_xref,
            "sequence": r.sequence_number, "length": r.text_length, "tag_syntax": r.matches_opening_tag_syntax})
        words.append(UntrustedWord(
            ownership=ownership, record_id=record_id, observation_id=r.observation_id, bbox=r.bbox, authority_status=r.authority_status,
            reason_codes=tuple(r.reason_codes), reason_set=reason_set, decode_status=r.decode_status,
            visibility_status=r.visibility_status, clip_state=clip_state, clip_reason_codes=clip_codes, font=join,
            receipt_font_xref=r.receipt_font_xref, receipt_font_subtype=r.receipt_font_subtype,
            receipt_font_name=r.receipt_font_name, sequence_number=r.sequence_number,
            text_length=int(r.text_length), matches_opening_tag_syntax=bool(r.matches_opening_tag_syntax)))
    reasons = (CENSUS_PRODUCED,) if records else (CENSUS_PRODUCED, CENSUS_PAGE_HAS_NO_NATIVE_TEXT_RECEIPTS)
    return _page_record(
        ownership, EvidenceResolutionStatus.CANDIDATE, reasons, total=len(records),
        trusted=len(records) - len(words), page_fonts=tuple(sorted(fonts_by_xref.values(), key=lambda f: f.xref)),
        untrusted=tuple(words), reason_hist=_histogram(w.reason_set for w in words),
        font_hist=_histogram((w.font.font_label, w.reason_set) for w in words),
        class_hist=_histogram((w.font.font_class, w.reason_set) for w in words),
        clip_hist=_histogram(w.clip_state for w in words),
        tag_matches=sum(w.matches_opening_tag_syntax for w in words))


def assemble_census(
    root: Optional[CensusRoot], requested_page_ids: Sequence[int], pages: Sequence[PageResidualCensus],
    text_ids_without_receipt: int,
) -> NativeTextResidualCensus:
    """The roll-up: CANDIDATE only when every requested page has a CANDIDATE census of this root and no text id lacks a receipt."""
    requested = tuple(sorted(requested_page_ids))
    ordered = tuple(sorted(pages, key=lambda p: int(p.ownership.page_id)))
    if root is None or not ordered:
        status, reasons = EvidenceResolutionStatus.ABSTAINED, (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    elif any(p.ownership.root() != root for p in ordered):
        status, reasons = EvidenceResolutionStatus.ABSTAINED, (CENSUS_FOREIGN_RECORD,)
    elif text_ids_without_receipt:
        status, reasons = EvidenceResolutionStatus.ABSTAINED, (CENSUS_TEXT_RECEIPT_UNAVAILABLE,)
    elif (tuple(int(p.ownership.page_id) for p in ordered) != requested
            or any(p.status is not EvidenceResolutionStatus.CANDIDATE for p in ordered)):
        status, reasons = EvidenceResolutionStatus.ABSTAINED, (CENSUS_PAGE_INCOMPLETE,)
    else:
        status, reasons = EvidenceResolutionStatus.CANDIDATE, (CENSUS_PRODUCED,)
    record_id = None
    if root is not None:
        record_id = stable_contract_id("shadow_native_text_residual_census", {
            "root": (root.document_id, root.revision_id, root.snapshot_id, root.source_sha256),
            "requested": requested, "status": status.value, "reasons": reasons,
            "pages": tuple(p.record_id for p in ordered), "without_receipt": text_ids_without_receipt})
    return NativeTextResidualCensus(
        root=root, status=status, reason_codes=reasons, standing_limits=STANDING_LIMITS,
        requested_page_ids=requested, pages=ordered, text_ids_without_receipt=text_ids_without_receipt,
        record_id=record_id)


# --------------------------------------------------------------------------------------
# producer adapter
# --------------------------------------------------------------------------------------


def _page_fonts(document, page) -> tuple[PageFont, ...]:
    out: dict[int, PageFont] = {}
    for entry in page.get_fonts(full=True) or ():
        if len(entry) < 6:
            continue
        xref, extension, subtype, base_font, _alias, encoding = entry[:6]
        try:
            has_to_unicode: Optional[bool] = document.xref_get_key(int(xref), "ToUnicode")[0] == "xref"
        except Exception:
            has_to_unicode = None
        program = program_class(extension, subtype)
        encoding = str(encoding or "")
        subtype = str(subtype or "")
        out.setdefault(int(xref), PageFont(
            xref=int(xref), subtype=subtype, base_font=bare_font_name(base_font), encoding=encoding,
            program=program, has_to_unicode=has_to_unicode,
            font_class=font_class_of(subtype, program, encoding, has_to_unicode)))
    return tuple(sorted(out.values(), key=lambda f: f.xref))


def _page_spans(page) -> tuple[SpanRecord, ...]:
    import fitz

    spans: list[SpanRecord] = []
    for block in page.get_text("dict", flags=fitz.TEXTFLAGS_WORDS).get("blocks", ()):
        for line in block.get("lines", ()):
            direction = tuple(line.get("dir") or (0.0, 0.0))
            for span in line.get("spans", ()):
                box = tuple(float(v) for v in span.get("bbox") or ())
                if len(box) != 4:
                    continue
                spans.append(SpanRecord(box, bare_font_name(span.get("font")), int(span.get("flags") or 0), direction))
    return tuple(spans)


def _word_record(result, ownership: CensusOwnership, observation_id: str):
    """One native word as the producer's text authority answered it: `(record, None)` or `(None, typed failure)`.

    A receipt of another document, revision or source, or one that cannot be placed on this page as a finite box,
    is never censused as if it were this page's word. An untrusted word keeps only its text length and one syntax
    boolean (computed by the generic opening tag normaliser), never the text."""
    receipt = result.receipt
    if receipt is None:
        return None, CENSUS_WORD_UNPLACEABLE
    if (receipt.document_id, receipt.revision_id, receipt.source_sha256) != (
            ownership.document_id, ownership.revision_id, ownership.source_sha256):
        return None, CENSUS_FOREIGN_RECORD
    try:
        geometry = tuple(float(v) for v in receipt.geometry)
    except (TypeError, ValueError, OverflowError):
        return None, CENSUS_WORD_UNPLACEABLE
    if (str(receipt.page_id) != ownership.page_id or len(geometry) != 4 or not all(math.isfinite(v) for v in geometry)
            or receipt.parent_observation_id != observation_id or type(receipt.raw_text) is not str
            or any(v is not None and type(v) is not int for v in (receipt.font_xref, receipt.sequence_number))):
        return None, CENSUS_WORD_UNPLACEABLE
    trusted = result.status is EvidenceResolutionStatus.CORROBORATED and result.proposition == TRUSTED_PDF_TEXT
    return WordIntegrityRecord(
        ownership=ownership, observation_id=observation_id, bbox=geometry, trusted=trusted,
        authority_status=result.status, reason_codes=tuple(result.reason_codes),
        receipt_reason_codes=tuple(receipt.reason_codes), decode_status=str(receipt.decode_status),
        visibility_status=str(receipt.visibility_status), receipt_font_xref=receipt.font_xref,
        receipt_font_subtype=str(receipt.font_subtype), receipt_font_name=str(receipt.font_name),
        sequence_number=receipt.sequence_number,
        # an untrusted word's text is never kept: only its length and one syntax boolean
        text_length=None if trusted else len(receipt.raw_text),
        matches_opening_tag_syntax=None if trusted else normalize_opening_tag(receipt.raw_text) is not None), None


class NativeTextResidualCensusShadow:
    """Read-only census bound to one `SourceVisibilityProducer`; default OFF."""

    def __init__(self, source, *, enabled: bool = False, max_untrusted_records: int = DEFAULT_MAX_UNTRUSTED_RECORDS):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("native text residual census gate must be an explicit boolean")
        if type(max_untrusted_records) is not int or max_untrusted_records <= 0:
            raise ValueError("the untrusted record bound must be a positive integer")
        self._source = source
        self._enabled = enabled
        self._max_untrusted_records = max_untrusted_records

    @staticmethod
    def _failure(*codes: str) -> NativeTextResidualCensus:
        return NativeTextResidualCensus(
            root=None, status=EvidenceResolutionStatus.ABSTAINED, reason_codes=tuple(codes),
            standing_limits=STANDING_LIMITS, requested_page_ids=(), pages=(), text_ids_without_receipt=0,
            record_id=None)

    def census(self, *, revision_id: str, page_ids: Sequence[int]) -> NativeTextResidualCensus:
        if not self._enabled:
            return self._failure(CENSUS_DISABLED)
        if (type(revision_id) is not str or not revision_id or isinstance(page_ids, (str, bytes, set, frozenset, dict))
                or not hasattr(page_ids, "__iter__")):
            raise ValueError("a revision id and a sequence of integer page ids are required")
        requested = tuple(page_ids)
        if (not requested or len(requested) > _MAX_PAGES_PER_CALL
                or any(type(p) is not int or p < 1 for p in requested) or len(set(requested)) != len(requested)):
            raise ValueError("page ids must be distinct positive integers, at most %d" % _MAX_PAGES_PER_CALL)
        requested = tuple(sorted(requested))

        from pb_source_observation_authority import ObservationSelector

        import fitz

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return self._failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        if source._producer.current_revision_id(document_id) != revision_id:
            return self._failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return self._failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
        root = CensusRoot(document_id, revision_id, published.snapshot.snapshot_id, published.revision.source_sha256)
        decoded = {int(v) for v in published.coverage.decoded_pages}
        failed = {int(v) for v in published.coverage.failed_pages}

        text_authority = source.text_integrity_authority()
        with_receipt = text_authority.observation_ids_for_snapshot(root.snapshot_id)
        without_receipt = sum(1 for oid in published.text_observation_ids if oid not in with_receipt)

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(document_id, revision_id, root.source_sha256, root.snapshot_id, observation_id)

        pages: list[PageResidualCensus] = []
        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            for page_id in requested:
                ownership = CensusOwnership(document_id, revision_id, root.snapshot_id, root.source_sha256, str(page_id))
                if page_id not in decoded or page_id in failed:
                    pages.append(abstained_page(ownership, VISIBLE_SOURCE_AUTHORITY_REQUIRED))
                    continue
                # sorted, so which typed failure a page reports never depends on the producer's id order
                ids = tuple(sorted(text_authority.observation_ids_with_receipt_page(
                    root.snapshot_id, published.text_observation_ids, str(page_id))))
                if len(ids) > _MAX_WORDS_PER_PAGE:
                    pages.append(abstained_page(ownership, CENSUS_BUDGET_EXCEEDED))
                    continue
                records: list[WordIntegrityRecord] = []
                failure: Optional[str] = None
                untrusted = 0
                for observation_id in ids:
                    record, failure = _word_record(
                        text_authority.resolve_text(selector(observation_id)), ownership, str(observation_id))
                    if record is None:
                        break
                    untrusted += not record.trusted
                    if untrusted > self._max_untrusted_records:
                        failure = CENSUS_BUDGET_EXCEEDED
                        break
                    records.append(record)
                if failure is not None:
                    pages.append(abstained_page(ownership, failure))
                    continue
                # the page's own font list is read for every page; the (costlier) spans only when a word needs them
                try:
                    page = document[page_id - 1]
                    fonts = _page_fonts(document, page)
                    spans = _page_spans(page) if untrusted else ()
                except (ValueError, IndexError, RuntimeError):
                    pages.append(abstained_page(ownership, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE))
                    continue
                pages.append(classify_residuals(
                    records, ownership=ownership, page_fonts=fonts, spans=spans,
                    max_untrusted_records=self._max_untrusted_records))
        return assemble_census(root, requested, pages, without_receipt)


__all__ = [
    "CENSUS_DISABLED", "CENSUS_PRODUCED", "CensusOwnership", "CensusRoot", "FontJoin",
    "NATIVE_TEXT_RESIDUAL_CENSUS_SCHEMA_VERSION", "NativeTextResidualCensus", "NativeTextResidualCensusShadow",
    "PageFont", "PageResidualCensus", "STANDING_LIMITS", "SpanIndex", "SpanRecord", "UntrustedWord",
    "WordIntegrityRecord", "abstained_page", "assemble_census", "classify_residuals", "clip_state_of",
    "direction_class", "join_word_font",
]
