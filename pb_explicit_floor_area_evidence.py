"""Declared drawing floor-area claims for PlanReader.

This module reads only drawing text. It deliberately knows nothing about
benchmarks, projects, BOQs, expected quantities, or downstream score targets.

A printed ``FLOOR AREA`` annotation is a declared source quantity claim. By
itself it is NOT physical geometry authority and is NOT a bound floor/slab
quantity authority. The claim may be retained for reconciliation, validation,
and discrepancy reporting until a separate producer-owned binding proves that
it belongs to a specific physical entity.

The parser remains intentionally narrow and fail-closed:

* the page must identify itself as a floor-plan / floor-layout drawing;
* the value must be explicitly labelled ``FLOOR AREA`` and carry square-metre
  units (``m2``, ``m²``, ``sqm`` or ``sq m``);
* multiple materially different floor-area annotations on one page are
  ambiguous and yield no resolved page claim;
* multiple pages may corroborate the same declared value, but disagreeing
  pages make the document-level claim unresolved.

Room-area labels, drawing scales, unlabelled numbers, schedules and BOQ text do
not satisfy this contract. This module never chooses length/width, manufactures
a footprint, or promotes a declared aggregate into physical take-off authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import hashlib
import math
import re
from typing import Iterable, Optional, Tuple


DECLARED_FLOOR_AREA_AUTHORITY = "declared_floor_area_reconciliation_only"
DECLARED_FLOOR_AREA_BINDING = "unbound"

_PLAN_CONTEXT_RE = re.compile(
    r"\b(?:floor\s+plan|floor\s+layout|ground\s+floor\s+plan|"
    r"design\s+scheme\s*\(\s*plan\s*\)|general\s+[^\n]{0,40}\s+floor\s+plan)\b",
    re.IGNORECASE,
)

# Keep the label-to-value window deliberately short. It is long enough for
# line-broken title-block formatting such as ``AREA in M2 / FLOOR AREA / - /
# 162.69M2`` but short enough not to wander into unrelated schedule values.
_FLOOR_AREA_RE = re.compile(
    r"\bfloor\s+area\b[^\d]{0,48}"
    r"(?P<value>\d{1,6}(?:[.,]\d{1,3})?)\s*"
    r"(?P<unit>m\s*(?:2|²)|sq\.?\s*m|sqm)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExplicitFloorAreaEvidence:
    """Resolved declared overall floor-area claim from one or more pages.

    The class name is retained for compatibility with existing callers. Its
    authority and binding fields intentionally make the new boundary explicit:
    this record is reconciliation evidence only until another authority binds a
    scoped explicit area to a proven physical entity.
    """

    area_m2: float
    source_pages: Tuple[int, ...]
    raw_evidence: Tuple[str, ...]
    authority: str = DECLARED_FLOOR_AREA_AUTHORITY
    binding: str = DECLARED_FLOOR_AREA_BINDING
    source_sha256: Optional[str] = None
    revision_id: Optional[str] = None
    # Optional original native area-table block address. Legacy page-wide
    # declared totals remain unbound with no asserted block identity.
    source_block_id: Optional[str] = None


def _normalise_text(text: str) -> str:
    return " ".join(str(text or "").replace("\u00a0", " ").split())


def extract_explicit_floor_area_evidence(
    page_text: str,
    *,
    source_page: int,
    source_sha256: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> Optional[ExplicitFloorAreaEvidence]:
    """Extract one unambiguous declared floor-area claim from a plan page."""

    normalized = _normalise_text(page_text)
    if not normalized or not _PLAN_CONTEXT_RE.search(normalized):
        return None

    matches = []
    for match in _FLOOR_AREA_RE.finditer(normalized):
        try:
            value = float(match.group("value").replace(",", "."))
        except ValueError:
            continue
        # Only reject physically impossible / parser-noise values. These are
        # broad domain sanity bounds, not project-specific tuning constants.
        if not (0.1 <= value <= 1_000_000.0):
            continue
        matches.append((round(value, 3), match.group(0).strip()))

    if not matches:
        return None

    distinct = {value for value, _raw in matches}
    if len(distinct) != 1:
        return None

    area = next(iter(distinct))
    raw = tuple(dict.fromkeys(raw_text for _value, raw_text in matches))
    return ExplicitFloorAreaEvidence(
        area_m2=area,
        source_pages=(int(source_page),),
        raw_evidence=raw,
        source_sha256=source_sha256,
        revision_id=revision_id,
    )


def resolve_explicit_floor_area_evidence(
    evidence: Iterable[ExplicitFloorAreaEvidence],
) -> Optional[ExplicitFloorAreaEvidence]:
    """Resolve corroborating declared claims; disagreement fails closed.

    Resolution here means only that the source repeats the same declared
    quantity. It does not bind the claim to geometry or promote quantity
    authority.
    """

    items = list(evidence)
    if not items:
        return None

    # Reconciling identical *numbers* must never fill a missing source
    # address from a different PDF or revision. An explicitly unbound legacy
    # set remains unbound; a mixture of bound and unbound claims abstains.
    def _typed_original(value: object) -> bool:
        if type(value) not in (int, float):
            return False
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(numeric) and 0.0 < numeric <= 1_000_000.0

    for item in items:
        if (
            type(item) is not ExplicitFloorAreaEvidence
            or item.authority != DECLARED_FLOOR_AREA_AUTHORITY
            or item.binding != DECLARED_FLOOR_AREA_BINDING
            or not _typed_original(item.area_m2)
            or type(item.source_pages) not in (tuple, list)
            or not item.source_pages
            or any(type(p) is not int or p <= 0 for p in item.source_pages)
            or type(item.raw_evidence) not in (tuple, list)
            or any(type(t) is not str or not t.strip() for t in item.raw_evidence)
            or (
                item.source_sha256 is not None
                and (
                    type(item.source_sha256) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", item.source_sha256) is None
                )
            )
            or (
                item.revision_id is not None
                and (
                    type(item.revision_id) is not str
                    or not item.revision_id
                    or item.revision_id != item.revision_id.strip()
                )
            )
        ):
            return None

    for field in ("source_sha256", "revision_id"):
        all_values = tuple(getattr(item, field) for item in items)
        if any(v is None for v in all_values) and any(
            v is not None for v in all_values
        ):
            return None

    distinct = {round(item.area_m2, 3) for item in items}
    if len(distinct) != 1:
        return None

    source_hashes = {item.source_sha256 for item in items if item.source_sha256}
    revisions = {item.revision_id for item in items if item.revision_id}
    if len(source_hashes) > 1 or len(revisions) > 1:
        return None

    pages = tuple(sorted({p for item in items for p in item.source_pages}))
    raw = tuple(dict.fromkeys(raw for item in items for raw in item.raw_evidence))
    return ExplicitFloorAreaEvidence(
        area_m2=next(iter(distinct)),
        source_pages=pages,
        raw_evidence=raw,
        source_sha256=next(iter(source_hashes)) if source_hashes else None,
        revision_id=next(iter(revisions)) if revisions else None,
    )


# Component rows are not the same claim as an aggregate "TOTAL FLOOR AREA".
# This narrow parser is reconciliation *input* only, never a source-authenticated
# physical floor measurement and never QuantityEvidence.
_COMPONENT_AREA_LABEL_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9&/()+. -]{0,79}?)\s+AREA\s*:\s*(?P<inline>.*)$",
    re.IGNORECASE,
)
_COMPONENT_AREA_VALUE_RE = re.compile(
    r"^(?P<value>\d{1,6}(?:\.\d{1,3})?)\s*"
    r"(?P<unit>m(?:2|²)|sq\.?\s*m|sqm)$",
    re.IGNORECASE,
)
_COMPONENT_AGGREGATE_PREFIXES = ("TOTAL", "SUBTOTAL", "GRAND TOTAL")


@dataclass(frozen=True)
class DeclaredComponentFloorAreaEvidence:
    """One printed, unbound area row from a caller-isolated text block.

    The source text is NOT presumed glyph-, clip- or paint-authenticated.
    A complete original source identity and geometric physical binding must
    be independently issued before any commercial quantity can exist.
    """

    label: str
    area_m2: float
    source_page: int
    source_block_id: str
    raw_evidence: str
    authority: str = DECLARED_FLOOR_AREA_AUTHORITY
    binding: str = DECLARED_FLOOR_AREA_BINDING
    source_sha256: Optional[str] = None
    revision_id: Optional[str] = None
    # Original native *text* bounding box, never the physical floor polygon.
    source_text_bbox_pdf_pts: Optional[tuple[float, float, float, float]] = None
    # Original nonblank line offset *within the native text block*. Neither
    # a room index nor a user-selected benchmark item identity.
    source_block_line_index: Optional[int] = None
    source_label_word_addresses: Tuple[Tuple[int, int, int], ...] = ()
    source_value_word_addresses: Tuple[Tuple[int, int, int], ...] = ()


def extract_declared_component_floor_areas(
    source_block_text: str,
    *,
    source_page: int,
    source_block_id: str,
    source_sha256: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> Tuple[DeclaredComponentFloorAreaEvidence, ...]:
    """Read independent printed component-area rows without inventing m².

    The caller supplies one exact source-native text block (not a flattened
    multi-page text dump). Each area label is paired with a value on its SAME
    text line or the immediately next nonblank line, never the closest match
    across unrelated blocks. Duplicated labels are withheld even when their
    numbers agree: the original physical owners could still be distinct.

    This is intentionally unbound evidence only. It does not change the
    existing aggregate floor-area parser or issue FIRM QuantityEvidence.
    """
    if type(source_page) is not int or source_page <= 0:
        raise ValueError("source_page must be an exact positive page number")
    if (
        type(source_block_id) is not str
        or not source_block_id
        or source_block_id != source_block_id.strip()
    ):
        raise ValueError("source_block_id must be a typed original block address")
    if source_sha256 is not None and (
        type(source_sha256) is not str
        or len(source_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in source_sha256)
    ):
        raise ValueError("source_sha256 must be a 64-hex source address")
    if revision_id is not None and (
        type(revision_id) is not str or not revision_id
        or revision_id != revision_id.strip()
    ):
        raise ValueError("revision_id must be an exact source revision")
    if type(source_block_text) is not str:
        raise TypeError("source_block_text must be one original text block")

    # Blank native PDF line breaks between labels and values are allowed;
    # another substantive text row terminates the pending value window.
    lines = tuple(line.strip() for line in source_block_text.splitlines()
                  if line.strip())
    candidates: list[DeclaredComponentFloorAreaEvidence] = []
    for index, raw_line in enumerate(lines):
        label_match = _COMPONENT_AREA_LABEL_RE.fullmatch(raw_line)
        if label_match is None:
            continue
        label = " ".join(label_match.group("label").split())
        if not label or label.upper().startswith(_COMPONENT_AGGREGATE_PREFIXES):
            continue
        inline = label_match.group("inline").strip()
        if inline:
            candidate_line = inline
        elif index + 1 < len(lines):
            candidate_line = lines[index + 1]
        else:
            continue
        value_match = _COMPONENT_AREA_VALUE_RE.fullmatch(candidate_line)
        if value_match is None:
            continue
        try:
            value = float(value_match.group("value"))
        except (ValueError, OverflowError):
            continue
        if not (0.0 < value <= 1_000_000.0):
            continue
        candidates.append(
            DeclaredComponentFloorAreaEvidence(
                label=label,
                area_m2=value,
                source_page=source_page,
                source_block_id=source_block_id,
                raw_evidence=raw_line + (" " + candidate_line if not inline else ""),
                source_block_line_index=index,
                source_sha256=source_sha256,
                revision_id=revision_id,
            )
        )

    counts: dict[str, int] = {}
    for row in candidates:
        key = " ".join(row.label.casefold().split())
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        row for row in candidates
        if counts[" ".join(row.label.casefold().split())] == 1
    )



def reconcile_declared_component_area_total(
    components: Iterable[DeclaredComponentFloorAreaEvidence],
    total: ExplicitFloorAreaEvidence,
) -> Tuple[DeclaredComponentFloorAreaEvidence, ...]:
    """Reconcile one exact printed source-area schedule; grant no m² authority.

    A total is an aggregate ledger observation, not another physical zone.
    Do not reconcile separate original text blocks/pages, inferred category
    names, mixed revisions, duplicate row labels, missing receipts or rounded
    numeric approximations. The result remains unbound source text evidence.
    """
    if type(total) is not ExplicitFloorAreaEvidence:
        raise TypeError("total must be original declared floor-area evidence")
    records = tuple(components)
    if (
        not records
        or total.authority != DECLARED_FLOOR_AREA_AUTHORITY
        or total.binding != DECLARED_FLOOR_AREA_BINDING
        or len(total.source_pages) != 1
        or type(total.source_pages[0]) is not int
        or total.source_pages[0] <= 0
        or any(type(row) is not DeclaredComponentFloorAreaEvidence for row in records)
    ):
        return ()

    row_labels: set[str] = set()
    block_ids: set[str] = set()
    values: list[Decimal] = []
    for row in records:
        if (
            row.source_page != total.source_pages[0]
            or row.source_sha256 != total.source_sha256
            or row.revision_id != total.revision_id
            or row.authority != DECLARED_FLOOR_AREA_AUTHORITY
            or row.binding != DECLARED_FLOOR_AREA_BINDING
            or type(row.label) is not str
            or not row.label
            or row.label != row.label.strip()
            or type(row.source_block_id) is not str
            or not row.source_block_id
            or row.source_block_id != row.source_block_id.strip()
            or type(row.area_m2) not in (int, float)
        ):
            return ()
        key = " ".join(row.label.casefold().split())
        if key in row_labels:
            return ()
        row_labels.add(key)
        block_ids.add(row.source_block_id)
        try:
            value = Decimal(str(row.area_m2))
        except InvalidOperation:
            return ()
        if not value.is_finite() or value <= 0:
            return ()
        values.append(value)
    if len(block_ids) != 1 or type(total.area_m2) not in (int, float):
        return ()
    # A native area-table total must be issued from the SAME original block
    # as the component set; a matching number from a neighboring table is
    # not a corroborating source checksum.
    if total.source_block_id is not None and (
        type(total.source_block_id) is not str
        or not total.source_block_id
        or total.source_block_id != total.source_block_id.strip()
        or total.source_block_id not in block_ids
    ):
        return ()
    try:
        expected = Decimal(str(total.area_m2))
    except InvalidOperation:
        return ()
    if not expected.is_finite() or expected <= 0 or sum(values, Decimal("0")) != expected:
        return ()

    return tuple(sorted(records, key=lambda row: row.label.casefold()))




def _native_area_word_addresses(native_words, block_no, row, source_block_bbox=None):
    """Find exact lexical source words for one unbound area claim."""
    by_line: dict[int, list[tuple[int, str]]] = {}
    for word in native_words:
        if len(word) < 8 or word[5] != block_no or type(word[4]) is not str:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in word[:4])
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                continue
            if source_block_bbox is not None and (
                x0 < source_block_bbox[0] - 1e-3
                or y0 < source_block_bbox[1] - 1e-3
                or x1 > source_block_bbox[2] + 1e-3
                or y1 > source_block_bbox[3] + 1e-3
            ):
                continue
            line_id, word_id = int(word[6]), int(word[7])
            if line_id < 0 or word_id < 0:
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        by_line.setdefault(line_id, []).append((word_id, word[4]))
    lines = tuple(
        (number, tuple(sorted(words)))
        for number, words in sorted(by_line.items())
    )
    target = tuple((row.label + " AREA:").split())
    candidates = []
    for index, (line_id, words) in enumerate(lines):
        tokens = tuple(w for _n, w in words)
        if tuple(token.casefold() for token in tokens[:len(target)]) != tuple(
            token.casefold() for token in target
        ):
            continue
        remaining = words[len(target):]
        if remaining:
            value_line, value_words = line_id, remaining
        elif index + 1 < len(lines):
            value_line, value_words = lines[index + 1]
        else:
            continue
        match = _COMPONENT_AREA_VALUE_RE.fullmatch(
            " ".join(text for _n, text in value_words)
        )
        if match is None or float(match.group("value")) != row.area_m2:
            continue
        candidates.append((
            tuple((block_no, line_id, n) for n, _ in words[:len(target)]),
            tuple((block_no, value_line, n) for n, _ in value_words),
        ))
    return candidates[0] if len(candidates) == 1 else None


def extract_unbound_component_areas_from_original_pdf(
    source_pdf_bytes: bytes,
    *,
    expected_source_sha256: str,
    revision_id: str,
) -> Tuple[DeclaredComponentFloorAreaEvidence, ...]:
    """Read original PDF native text blocks, never caller-selected area text.

    The source bytes are SHA verified here. Native text is NOT by itself
    visibility/glyph/clip trusted: every returned area is explicitly UNBOUND
    and requires independent producer-owned text and physical zone proof.
    Raster-only pages produce no candidate rows, not guessed OCR results.
    """
    if type(source_pdf_bytes) is not bytes or not source_pdf_bytes:
        raise ValueError("original source must be nonempty immutable PDF bytes")
    if (
        type(expected_source_sha256) is not str
        or len(expected_source_sha256) != 64
        or any(c not in "0123456789abcdefABCDEF"
               for c in expected_source_sha256)
        or hashlib.sha256(source_pdf_bytes).hexdigest()
        != expected_source_sha256.lower()
    ):
        raise ValueError("original PDF bytes do not match expected source SHA")
    if type(revision_id) is not str or not revision_id or revision_id != revision_id.strip():
        raise ValueError("original PDF revision ID must be a typed source receipt")

    # Import only when native-PDF extraction is requested; ordinary printed
    # area reconciliation has no PyMuPDF runtime dependency.
    try:
        import fitz
        document = fitz.open(stream=source_pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("original source is not a readable PDF") from exc
    candidates: list[DeclaredComponentFloorAreaEvidence] = []
    try:
        if document.is_encrypted:
            raise ValueError("original PDF is encrypted and not decoded")
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            # get_text('blocks') is in the unrotated native text frame; the
            # cropbox, not the rotated display page.rect, bounds visible
            # source text. This remains only a negative eligibility check.
            cropbox = page.cropbox
            original_words = tuple(page.get_text("words"))
            for block_index, block in enumerate(page.get_text("blocks")):
                if (
                    not isinstance(block, (tuple, list))
                    or len(block) < 7
                    or block[6] != 0
                    or type(block[4]) is not str
                    or not block[4].strip()
                ):
                    continue
                try:
                    bbox = tuple(float(v) for v in block[:4])
                except (TypeError, ValueError, OverflowError):
                    continue
                if (
                    len(bbox) != 4
                    or not all(math.isfinite(v) for v in bbox)
                    or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]
                    or bbox[0] < float(cropbox.x0) - 1e-3
                    or bbox[1] < float(cropbox.y0) - 1e-3
                    or bbox[2] > float(cropbox.x1) + 1e-3
                    or bbox[3] > float(cropbox.y1) + 1e-3
                ):
                    continue
                block_id = f"original-pdf-page-{page_index + 1}-text-block-{block_index}"
                rows = extract_declared_component_floor_areas(
                    block[4],
                    source_page=page_index + 1,
                    source_block_id=block_id,
                    source_sha256=expected_source_sha256.lower(),
                    revision_id=revision_id,
                )
                for row in rows:
                    addresses = _native_area_word_addresses(original_words, block_index, row, bbox)
                    if addresses is None:
                        continue
                    labels, values = addresses
                    candidates.append(replace(
                        row, source_text_bbox_pdf_pts=bbox,
                        source_label_word_addresses=labels,
                        source_value_word_addresses=values,
                    ))
    finally:
        document.close()
    return tuple(candidates)



_NATIVE_COMPONENT_TOTAL_RE = re.compile(
    r"^TOTAL\s+FLOOR\s+AREA\s*:\s*"
    r"(?P<value>\d{1,6}(?:\.\d{1,3})?)\s*"
    r"(?P<unit>m(?:2|²)|sq\.?\s*m|sqm)$",
    re.IGNORECASE,
)


def extract_unbound_total_from_component_area_text_block(
    source_block_text: str,
    *,
    source_page: int,
    source_block_id: str,
    source_sha256: str,
    revision_id: str,
) -> Optional[ExplicitFloorAreaEvidence]:
    """Read only an exact printed total from one original native table block.

    The source's original glyph/clip/visibility remains unverified here.
    Duplicate (even identical) printed TOTAL lines in the same block abstain.
    This number is an aggregate control, never a physical floor surface.
    """
    # Reuse existing source-block and source-digest input safety on the same
    # native text, rather than accepting arbitrary page metadata.
    extract_declared_component_floor_areas(
        source_block_text,
        source_page=source_page,
        source_block_id=source_block_id,
        source_sha256=source_sha256,
        revision_id=revision_id,
    )
    lines = [line.strip() for line in source_block_text.splitlines() if line.strip()]
    totals = [_NATIVE_COMPONENT_TOTAL_RE.fullmatch(line) for line in lines]
    matches = [match for match in totals if match is not None]
    if len(matches) != 1:
        return None
    match = matches[0]
    try:
        value = float(match.group("value"))
    except (TypeError, ValueError, OverflowError):
        return None
    if not (0.0 < value <= 1_000_000.0):
        return None
    return ExplicitFloorAreaEvidence(
        area_m2=value,
        source_pages=(source_page,),
        raw_evidence=(match.group(0),),
        authority=DECLARED_FLOOR_AREA_AUTHORITY,
        binding=DECLARED_FLOOR_AREA_BINDING,
        source_sha256=source_sha256,
        revision_id=revision_id,
        source_block_id=source_block_id,
    )
