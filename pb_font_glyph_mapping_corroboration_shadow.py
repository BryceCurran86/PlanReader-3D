"""Shadow-only evidence: which (font, glyph id) -> character mappings are verified by words that raster corroboration has already read?

Why this exists. ``PdfTextIntegrityAuthority`` verifies a glyph by asking the embedded font program for the glyph id of the decoded Unicode
(``_glyph_unicode_consistency_reasons``). Fonts whose program cannot answer - CID-keyed CFF subsets without names, symbolic TrueType subsets without
a Unicode cmap - give ``text_glyph_mapping_unverified`` for every word set in them, which is 1,140 of 1,215 words on one 3Laurel plan page and 1,116 of
1,246 on a Maryborough one. ``pb_raster_text_corroboration_authority`` can corroborate a word, but only one word at a time, at several seconds a word.

What it does. The shape of a glyph does not change between occurrences: glyph ``g`` of font program ``f`` looks the same in every word that uses it. So
the characters a corroborated word is read as are evidence about every glyph in it, and a glyph that is read as the same character by several
independent corroborated words, and by none as another character, has a verified mapping that applies to every other word set with that glyph.
This module holds only the bookkeeping: per-word glyph occurrences recovered from the PDF's own text trace, the vote count per (font, glyph id), the
verified / contradicted / under-supported partition, the status of any word under a verification, and a deterministic order in which to spend a limited
number of corroboration attempts so that every glyph is covered. It performs no recognition: corroboration outcomes are an input.

What it deliberately does not do. It does not call the recogniser, does not read an image, does not know any project, file name, page number or expected
value, is not called by a live path, and changes no receipt or authority verdict. A mapping is never verified by one word, by words that disagree, or by
the claim alone. ``shadow_only`` is True, ``live_effect`` and ``text_trust_granted`` are False in every result.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

GLYPH_MAPPING_SHADOW_SCHEMA_VERSION = "1.0.0"

ALL_GLYPHS_VERIFIED = "all_glyphs_verified"
GLYPH_NOT_YET_VERIFIED = "glyph_not_yet_verified"
GLYPH_CONTRADICTED = "glyph_contradicted"
GLYPHS_NOT_RECOVERED = "glyphs_not_recovered"

DEFAULT_MIN_WORDS = 2
CENTRE_TOLERANCE_PT = 0.6
DIRECTION_UNIT_TOL = 1e-3     # a trace span direction must be a unit vector to this tolerance
DIRECTION_SAME_TOL = 1e-3     # every span a word is read from must share one direction to this tolerance
ORDER_TIE_TOL_PT = 1e-6       # two characters this close along the text direction have no defined order

GlyphKey = Tuple[str, int]                        # (font program key, glyph id)


@dataclass(frozen=True)
class WordGlyphs:
    """One native word and the (glyph id, character) of each traced glyph of it, in text order."""
    observation_id: str
    text: str
    font_key: str
    glyphs: Tuple[Tuple[int, str], ...]

    def pairs(self) -> Tuple[Tuple[GlyphKey, str], ...]:
        return tuple(((self.font_key, gid), char) for gid, char in self.glyphs)


def _span_direction(span: Mapping[str, object]) -> Optional[Tuple[float, float]]:
    """The span's own text direction as a unit vector, or ``None`` when it is invalid.

    A span without a ``dir`` is read as horizontal (1, 0): that is how every word was read before direction was used, so
    horizontal words keep their baseline behaviour. A present but non-finite, mis-shaped or non-unit direction is invalid."""
    raw = span.get("dir")
    if raw is None:
        return (1.0, 0.0)
    try:
        if len(raw) != 2:
            return None
        dx, dy = float(raw[0]), float(raw[1])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(dx) and math.isfinite(dy)) or abs(math.hypot(dx, dy) - 1.0) > DIRECTION_UNIT_TOL:
        return None
    return (dx, dy)


def word_glyphs(observation_id: str, text: str, font_key: str, bbox: Sequence[float],
                spans: Iterable[Mapping[str, object]], *, tolerance: float = CENTRE_TOLERANCE_PT) -> Optional[WordGlyphs]:
    """Glyphs of ``text`` recovered from trace spans: the characters whose box centre stands in ``bbox``.

    The characters are read in the order of the trace span's OWN text direction (projection of each character centre on the
    span's unit direction), not left to right on the page, so a word printed bottom to top is read bottom to top. Exactly one
    order is defined by the trace and it is the only one tried: the recovered characters must spell exactly ``text``.

    Returns None (the word contributes no evidence in either direction) when the recovered characters do not spell exactly
    ``text`` (a ligature, a reordering, a split word); when the characters come from spans with different directions or
    different fonts, or when some of them carry a font and others do not (an unknown font is never assumed to match); when a span direction is invalid (non-finite, mis-shaped, not a unit vector); or when two characters
    have no defined order (equal position along the direction). Glyph ids below zero (continuation components) are skipped,
    as the authority skips them."""
    x0, y0, x1, y1 = (float(v) for v in tuple(bbox)[:4])
    found: List[Tuple[float, float, int, str]] = []        # (cx, cy, gid, char)
    directions: List[Tuple[float, float]] = []
    fonts = set()
    for span in spans:
        selected = False
        for char in span.get("chars") or ():
            try:
                codepoint, gid = int(char[0]), int(char[1])
                cx = (float(char[3][0]) + float(char[3][2])) / 2.0
                cy = (float(char[3][1]) + float(char[3][3])) / 2.0
            except (IndexError, TypeError, ValueError):
                return None
            if x0 - tolerance <= cx <= x1 + tolerance and y0 - tolerance <= cy <= y1 + tolerance:
                if gid >= 0:
                    found.append((cx, cy, gid, chr(codepoint)))
                    selected = True
        if selected:
            direction = _span_direction(span)
            if direction is None:
                return None
            directions.append(direction)
            font = span.get("font")
            fonts.add(None if font in (None, "") else str(font))      # an unknown font is its own membership, never ignored
    if not found:
        return None
    first = directions[0]
    if any(abs(d[0] - first[0]) > DIRECTION_SAME_TOL or abs(d[1] - first[1]) > DIRECTION_SAME_TOL for d in directions) or len(fonts) > 1:
        return None
    dx, dy = first
    ordered = sorted(found, key=lambda item: (item[0] * dx + item[1] * dy))
    positions = [item[0] * dx + item[1] * dy for item in ordered]
    if any(b - a <= ORDER_TIE_TOL_PT for a, b in zip(positions, positions[1:])):
        return None
    if "".join(c for _x, _y, _g, c in ordered) != text:
        return None
    return WordGlyphs(str(observation_id), str(text), str(font_key), tuple((gid, char) for _x, _y, gid, char in ordered))


@dataclass(frozen=True)
class GlyphMappingVerification:
    verified: Mapping[GlyphKey, str]
    contradicted: Mapping[GlyphKey, Tuple[str, ...]]
    under_supported: Mapping[GlyphKey, int]
    min_words: int
    shadow_only: bool = True
    live_effect: bool = False
    text_trust_granted: bool = False


def _validate_native_word_glyph_claim(word: WordGlyphs) -> None:
    """An OCR-corrobated word cannot cast votes for a different Unicode trace."""
    if (
        type(word) is not WordGlyphs
        or type(word.observation_id) is not str or not word.observation_id
        or type(word.font_key) is not str or not word.font_key
        or type(word.text) is not str or not word.text
        or type(word.glyphs) is not tuple or not word.glyphs
    ):
        raise ValueError("invalid native word glyph evidence")
    if any(
        type(pair) is not tuple or len(pair) != 2
        or type(pair[0]) is not int or pair[0] < 0
        or type(pair[1]) is not str or len(pair[1]) != 1
        for pair in word.glyphs
    ) or "".join(char for _gid, char in word.glyphs) != word.text:
        raise ValueError("native word glyph trace disagrees with corroborated text")


def verify_glyph_mappings(corroborated: Iterable[WordGlyphs], *, min_words: int = DEFAULT_MIN_WORDS) -> GlyphMappingVerification:
    """Partition every (font, glyph id) seen in the corroborated words.

    A word votes once for each distinct (pair, character) it carries, however often the glyph repeats inside it. A pair is verified when exactly one
    character has votes, at least ``min_words`` words voted for it, and no word voted for another; it is contradicted when two characters have votes
    (neither wins); it is under-supported when one character has fewer than ``min_words`` votes."""
    if type(min_words) is not int or min_words < 2:
        raise ValueError("min_words must be an integer >= 2; one word cannot verify a glyph")
    votes: Dict[GlyphKey, Counter] = defaultdict(Counter)
    seen: Dict[str, WordGlyphs] = {}
    for word in corroborated:
        _validate_native_word_glyph_claim(word)
        previous = seen.get(word.observation_id)
        if previous is not None:
            if previous != word:
                raise ValueError(f"conflicting glyph evidence for observation {word.observation_id}")
            continue
        seen[word.observation_id] = word
        for pair, char in set(word.pairs()):
            votes[pair][char] += 1
    verified: Dict[GlyphKey, str] = {}
    contradicted: Dict[GlyphKey, Tuple[str, ...]] = {}
    under: Dict[GlyphKey, int] = {}
    for pair in sorted(votes):
        counter = votes[pair]
        if len(counter) > 1:
            contradicted[pair] = tuple(sorted(counter))
            continue
        (char, count), = counter.items()
        if count >= min_words:
            verified[pair] = char
        else:
            under[pair] = count
    return GlyphMappingVerification(verified, contradicted, under, int(min_words))


def classify_word(word: Optional[WordGlyphs], verification: GlyphMappingVerification) -> str:
    """Status of one word under a verification.

    A glyph the corroborated words disagree about, or one whose verified character differs from the one this word is spelled with, makes the word
    contradicted and dominates everything else; a word is verified only when every one of its glyphs is verified as the character it is spelled with."""
    if word is None or not word.glyphs:
        return GLYPHS_NOT_RECOVERED
    state = ALL_GLYPHS_VERIFIED
    for pair, char in word.pairs():
        known = verification.verified.get(pair)
        if pair in verification.contradicted or (known is not None and known != char):
            return GLYPH_CONTRADICTED
        if known is None:
            state = GLYPH_NOT_YET_VERIFIED
    return state


@dataclass
class GlyphMappingLedger:
    """Votes from the attempts made so far and the deterministic choice of the next word to attempt. Attempts that failed count for nothing."""
    min_words: int = DEFAULT_MIN_WORDS
    _outcomes: Dict[str, bool] = field(default_factory=dict)
    _words: Dict[str, WordGlyphs] = field(default_factory=dict)

    def record(self, word: WordGlyphs, corroborated: bool) -> None:
        _validate_native_word_glyph_claim(word)
        prior_word = self._words.get(word.observation_id)
        if prior_word is not None and prior_word != word:
            raise ValueError(f"conflicting glyph evidence for observation {word.observation_id}")
        previous = self._outcomes.get(word.observation_id)
        if previous is not None and previous != bool(corroborated):
            raise ValueError(f"conflicting outcomes recorded for observation {word.observation_id}")
        self._outcomes[word.observation_id] = bool(corroborated)
        self._words[word.observation_id] = word

    @property
    def attempts(self) -> int:
        return len(self._outcomes)

    @property
    def corroborated_count(self) -> int:
        return sum(1 for ok in self._outcomes.values() if ok)

    def verification(self) -> GlyphMappingVerification:
        return verify_glyph_mappings((self._words[oid] for oid, ok in sorted(self._outcomes.items()) if ok), min_words=self.min_words)

    def _needs(self) -> Dict[GlyphKey, int]:
        verification = self.verification()
        counts: Counter = Counter()
        for oid, ok in self._outcomes.items():
            if ok:
                for pair in {p for p, _c in self._words[oid].pairs()}:
                    counts[pair] += 1
        needs = {pair: max(0, self.min_words - counts.get(pair, 0)) for pair in counts}
        needs.update({pair: 0 for pair in verification.contradicted})      # more votes cannot settle a disagreement
        return needs

    def next_candidate(self, words: Iterable[WordGlyphs]) -> Optional[WordGlyphs]:
        """The not-yet-attempted word that adds the most votes still needed; ties by shorter text, then observation id (independent of input order)."""
        needs = self._needs()
        best: Optional[Tuple[Tuple[int, int, str], WordGlyphs]] = None
        for word in words:
            if word.observation_id in self._outcomes or not word.glyphs:
                continue
            gain = sum(1 for pair in {p for p, _c in word.pairs()} if needs.get(pair, self.min_words) > 0)
            if gain <= 0:
                continue
            key = (-gain, len(word.text), word.observation_id)
            if best is None or key < best[0]:
                best = (key, word)
        return None if best is None else best[1]


def coverage(words: Sequence[WordGlyphs], verification: GlyphMappingVerification) -> Dict[str, int]:
    """Number of words in each status; words that could not be recovered are counted by the caller (they are not in ``words``)."""
    counts = Counter(classify_word(word, verification) for word in words)
    return {status: counts.get(status, 0) for status in (ALL_GLYPHS_VERIFIED, GLYPH_NOT_YET_VERIFIED, GLYPH_CONTRADICTED, GLYPHS_NOT_RECOVERED)}
