"""Wall build-up statements read from AUTHENTICATED page text (SHADOW ONLY, default-off, diagnostic).

A general note such as "the internal walls are N mm stud frames lined with M mm board" is a source
STATEMENT about what a drawn wall layer is. It is not a measurement and it is not a quantity: it can only
say what a strip thickness drawn on a plan means (frame only, or frame plus lining), and it only says it for
the wall kind it names. It issues no scale, area, wall length, finish or customer row, and it never infers a
thickness for a wall kind the note does not name.

Two parts:

* ``parse_wall_build_up_statement`` is a pure parser over one note's text. It accepts only an INTERNAL-wall
  statement that names a frame thickness and a lining thickness in millimetres, and refuses everything else
  (an external-wall note, a note with no lining thickness, a thickness it cannot read exactly).
* ``collect_wall_build_up_statements`` reads native text blocks of chosen pages through the existing text
  authorities: a block is used only if EVERY word of it is trusted, either by the PDF text-integrity
  authority itself or by the independent raster corroboration authority. A block that cannot be proved word
  for word produces no statement.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector

WALL_BUILD_UP_STATEMENT_SCHEMA_VERSION = "1.0.0"
SCOPE_INTERNAL_WALLS = "internal_walls"

_NUMBER = r"(\d+(?:\.\d+)?)"
_BOARD = r"(GYPROCK|PLASTERBOARD|PLASTER BOARD|GYPSUM BOARD|GYPSUM)"
_INTERNAL_STATEMENT = re.compile(
    rf"\bINTERNAL WALLS? (?:TO BE|ARE|SHALL BE) {_NUMBER} ?MM (?:[A-Z]+ )*?(?:STUD )?FRAMES?"
    rf"(?: UNLESS OTHERWISE NOTED)?(?: AND)? (?:SHALL BE |ARE )?LINED WITH {_NUMBER} ?MM {_BOARD}"
    rf"(?: AND {_NUMBER} ?MM ((?:[A-Z]+ ?)+?) TO THE WET AREA(?:'S|S)?)?\b"
)
_OTHERWISE_NOTED = re.compile(r"\bUNLESS OTHERWISE NOTED\b")


@dataclass(frozen=True)
class ParsedWallBuildUp:
    scope: str
    frame_mm: float
    lining_mm: float
    lining_material: str
    wet_area_lining_mm: Optional[float]
    wet_area_lining_material: Optional[str]
    unless_otherwise_noted: bool


@dataclass(frozen=True)
class WallBuildUpStatement:
    """One authenticated internal-wall build-up statement and where it came from. Diagnostic only."""

    page_id: str
    scope: str
    frame_mm: float
    lining_mm: float
    lining_material: str
    wet_area_lining_mm: Optional[float]
    wet_area_lining_material: Optional[str]
    unless_otherwise_noted: bool
    source_partition_id: str
    block_no: int
    observation_ids: tuple[str, ...]
    text_sha256: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    schema_version: str = WALL_BUILD_UP_STATEMENT_SCHEMA_VERSION
    takeoff_eligible: bool = False
    commercial_projection_allowed: bool = False
    diagnostic_only: bool = True


def _normalize(text: str) -> str:
    cleaned = text.upper().replace("’", "'").replace("‘", "'")
    return " ".join(cleaned.split())


def parse_wall_build_up_statement(text: str) -> Optional[ParsedWallBuildUp]:
    """The internal-wall statement in ``text``, or None. Exactly one statement or none: two readings refuse."""
    normalized = _normalize(str(text or ""))
    matches = list(_INTERNAL_STATEMENT.finditer(normalized))
    if len(matches) != 1:
        return None
    match = matches[0]
    frame_mm, lining_mm = float(match.group(1)), float(match.group(2))
    if not (0.0 < frame_mm < 1000.0 and 0.0 < lining_mm < 1000.0):
        return None
    wet_mm = float(match.group(4)) if match.group(4) else None
    wet_material = " ".join(match.group(5).split()) if match.group(5) else None
    return ParsedWallBuildUp(
        scope=SCOPE_INTERNAL_WALLS,
        frame_mm=frame_mm,
        lining_mm=lining_mm,
        lining_material=" ".join(match.group(3).split()),
        wet_area_lining_mm=wet_mm,
        wet_area_lining_material=wet_material,
        unless_otherwise_noted=bool(_OTHERWISE_NOTED.search(normalized)),
    )


def _cheap_block_filter(raw_words: Sequence[str]) -> bool:
    joined = _normalize(" ".join(raw_words))
    return "INTERNAL" in joined and "WALL" in joined and "LINED" in joined


def collect_wall_build_up_statements(
    source: object, *, revision_id: str, page_ids: Sequence[str],
) -> tuple[WallBuildUpStatement, ...]:
    """Internal-wall statements whose every word is authenticated, one per distinct trusted text block.

    Reads only the pages named. A block with any word that neither the text-integrity authority nor the
    raster corroboration authority proves produces nothing; so does a block that does not parse exactly.
    """
    from pb_raster_text_corroboration_authority import (
        RasterTextCorroborationProducer,
        RasterTextCorroborationSelector,
    )

    published = source.published_snapshot_for_revision(revision_id)  # type: ignore[attr-defined]
    if published is None:
        return ()
    text_authority = source.text_integrity_authority()  # type: ignore[attr-defined]
    raster = RasterTextCorroborationProducer.from_source_visibility_producer(source)  # type: ignore[arg-type]
    found: list[WallBuildUpStatement] = []
    for raw_page in page_ids:
        page_id = str(raw_page)
        grouped: dict[tuple[str, int], list[tuple[str, object, object]]] = {}
        for observation_id in text_authority.observation_ids_with_receipt_page(
            published.snapshot.snapshot_id, published.text_observation_ids, page_id,
        ):
            result = text_authority.resolve_text(ObservationSelector(
                document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            ))
            receipt = result.receipt
            if (
                receipt is None or str(receipt.page_id) != page_id or receipt.block_no is None
                or receipt.line_no is None or receipt.word_no is None
            ):
                continue
            grouped.setdefault((str(receipt.source_partition_id), int(receipt.block_no)), []).append(
                (str(observation_id), result, receipt)
            )
        for (partition_id, block_no), items in sorted(grouped.items()):
            ordered = sorted(items, key=lambda item: (int(item[2].line_no), int(item[2].word_no)))
            if len({(int(item[2].line_no), int(item[2].word_no)) for item in ordered}) != len(ordered):
                continue  # a duplicated word position: the block is not a clean reading order
            if not _cheap_block_filter([str(item[2].raw_text or "") for item in ordered]):
                continue
            words: list[str] = []
            for observation_id, native, _receipt in ordered:
                trusted: Optional[str] = None
                if native.status is EvidenceResolutionStatus.CORROBORATED and native.trusted_text:
                    trusted = str(native.trusted_text)
                else:
                    corroborated = raster.publish(RasterTextCorroborationSelector(
                        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id, observation_id=observation_id,
                    ))
                    if (
                        corroborated.status is EvidenceResolutionStatus.CORROBORATED
                        and corroborated.record is not None and corroborated.corroborated_text
                    ):
                        trusted = str(corroborated.corroborated_text)
                if not trusted or not trusted.strip():
                    words = []
                    break
                words.append(trusted.strip())
            if not words:
                continue
            text = " ".join(words)
            parsed = parse_wall_build_up_statement(text)
            if parsed is None:
                continue
            found.append(WallBuildUpStatement(
                page_id=page_id, scope=parsed.scope, frame_mm=parsed.frame_mm, lining_mm=parsed.lining_mm,
                lining_material=parsed.lining_material, wet_area_lining_mm=parsed.wet_area_lining_mm,
                wet_area_lining_material=parsed.wet_area_lining_material,
                unless_otherwise_noted=parsed.unless_otherwise_noted, source_partition_id=partition_id,
                block_no=block_no, observation_ids=tuple(item[0] for item in ordered),
                text_sha256=hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest(),
                document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            ))
    found.sort(key=lambda s: (s.page_id, s.block_no, s.source_partition_id))
    return tuple(found)


__all__ = [
    "SCOPE_INTERNAL_WALLS",
    "ParsedWallBuildUp",
    "WallBuildUpStatement",
    "collect_wall_build_up_statements",
    "parse_wall_build_up_statement",
]
