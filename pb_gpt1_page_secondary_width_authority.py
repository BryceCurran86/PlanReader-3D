"""Original-page secondary-space width parsing without cross-sheet guessing.

This is an intermediate dimension witness, not a physical source viewport,
polygon, wall, finish material or commercial quantity issuer. A page carrying
contradictory figured widths cannot use whichever happens to be read first.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class SecondaryWidthTextEvidence:
    status: str
    width_m: float | None
    witnessed_widths_m: tuple[float, ...]


_NUMBER = r"(?:\\d{1,3}(?:,\\d{3})+|\\d+(?:[.,]\\d+)?)"
_BEFORE = re.compile(
    rf"\\b(?P<value>{_NUMBER})\\s*(?P<unit>mm|m)\\s+wide\\s+veranda(?:h)?\\b",
    re.IGNORECASE,
)
_AFTER = re.compile(
    rf"\\bveranda(?:h)?\\s*[:\\-\\(]?\\s*(?P<value>{_NUMBER})\\s*(?P<unit>mm|m)\\b",
    re.IGNORECASE,
)


def _number_in_metres(raw: str, unit: str) -> float | None:
    # Only explicitly printed units authorize a metric width; no "200" ->
    # 200mm or "2" -> 2m interpretation from the raw number's magnitude.
    try:
        if re.fullmatch(r"\\d{1,3}(?:,\\d{3})+", raw):
            number = float(raw.replace(",", ""))
        else:
            number = float(raw.replace(",", "."))
        result = number / 1000.0 if unit.lower() == "mm" else number
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(result) or not 0.0 < result <= 20.0:
        return None
    return result


def resolve_original_page_secondary_width_text(text: str) -> SecondaryWidthTextEvidence:
    """Identify ONE explicit metric dimension on ONE already-selected page.

    Ambiguity means ABSENT, never first match, largest match or rounding to a
    target quantity. Multiple identical printed occurrences remain one width.
    """
    if type(text) is not str:
        return SecondaryWidthTextEvidence("invalid_source_text", None, ())
    values: list[float] = []
    invalid_witness = False
    seen_spans: set[tuple[int, int]] = set()
    for pattern in (_BEFORE, _AFTER):
        for match in pattern.finditer(text):
            if match.span() in seen_spans:
                continue
            seen_spans.add(match.span())
            value = _number_in_metres(match.group("value"), match.group("unit"))
            if value is None:
                invalid_witness = True
            else:
                values.append(value)
    distinct = tuple(sorted(set(round(value, 9) for value in values)))
    if invalid_witness:
        return SecondaryWidthTextEvidence("invalid_dimension", None, distinct)
    if len(distinct) > 1:
        return SecondaryWidthTextEvidence("conflicting_dimensions", None, distinct)
    if len(distinct) == 1:
        return SecondaryWidthTextEvidence("one_explicit_dimension", distinct[0], distinct)
    return SecondaryWidthTextEvidence("no_explicit_dimension", None, ())


def bind_page_secondary_width(
    text: str,
    spatial_width_m: float | None,
) -> SecondaryWidthTextEvidence:
    """Reconcile independent viewport and same-page printed evidence.

    A spatial witness is already validated upstream by the F.23 viewport
    producer; this gate refuses disagreement instead of overwriting it with
    whichever parser ran first.
    """
    words = resolve_original_page_secondary_width_text(text)
    if words.status in ("conflicting_dimensions", "invalid_dimension", "invalid_source_text"):
        return words
    if spatial_width_m is None:
        return words
    if type(spatial_width_m) not in (int, float):
        return SecondaryWidthTextEvidence("invalid_spatial_dimension", None, words.witnessed_widths_m)
    spatial = float(spatial_width_m)
    if not math.isfinite(spatial) or not 0.0 < spatial <= 20.0:
        return SecondaryWidthTextEvidence("invalid_spatial_dimension", None, words.witnessed_widths_m)
    if words.width_m is not None and not math.isclose(
        spatial, words.width_m, rel_tol=0.0, abs_tol=1e-6
    ):
        return SecondaryWidthTextEvidence(
            "spatial_text_dimension_conflict", None,
            tuple(sorted(set((*words.witnessed_widths_m, spatial)))),
        )
    return SecondaryWidthTextEvidence(
        "source_page_spatial_correspondence" if words.width_m is None else "corroborated",
        spatial,
        tuple(sorted(set((*words.witnessed_widths_m, spatial)))),
    )
