"""Source-classified floor-plan pages for physical wall/opening topology scope.

The live physical net-wall chain needs two different kinds of page:

* topology pages: sheets whose linework may be turned into wall candidates,
  openings, rooms and canonical objects; and
* evidence pages: sheets (typically elevations) that only supply cross-sheet
  registration and wall-height evidence.

Replaying the opening detector and canonical-object composition over every
selected sheet puts elevation, section, roof and detail linework into the same
object universe as the floor plan. This module classifies pages from SOURCE
evidence only, so a caller can name the topology pages without using filenames,
page numbers, coordinates, project names or database page labels:

* a title-block title bound to an explicit drawing-title field by the page-title
  authority, classified by the existing view classifier / page-type rules; or
* where a page has no bound title, an authoritative F.07 floor-plan viewport.

It never raises authority and publishes nothing. It narrows the topology scope
only with positive evidence on both sides: at least one selected page is
positively a floor plan AND at least one other selected page is positively
titled as a different drawing (that page is then evidence-only). A page with no
title or viewport evidence is never removed, and an unreadable source is never
narrowed, so the default remains the CURRENT behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Optional, Sequence

import pb_page_title_authority as title_authority
from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType
from pb_page_registration_v1225 import weighted_page_type
from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports


SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION = "1.0.0"

FLOOR_PLAN_PAGE_BOUND_TITLE = "floor_plan_bound_title"
FLOOR_PLAN_PAGE_F07_VIEWPORT = "floor_plan_f07_viewport"
NOT_FLOOR_PLAN_PAGE_BOUND_TITLE = "not_floor_plan_bound_title"
UNPROVEN_FLOOR_PLAN_PAGE = "floor_plan_page_unproven"
UNREADABLE_FLOOR_PLAN_PAGE = "floor_plan_page_unreadable"

FLOOR_PLAN = "floor_plan"
NOT_FLOOR_PLAN = "not_floor_plan"
UNPROVEN = "unproven"

_MIN_TITLE_SCORE = 60.0
_MIN_PAGE_TYPE_CONFIDENCE = 60
_TITLE_SPLIT_RE = re.compile(r"\s*(?:&|/|\+|,|;|\band\b)\s*", re.IGNORECASE)

# Room-area cross-view support must be plan-like source evidence rather than
# every positively non-floor-plan sheet. These roles are generic architectural
# drawing titles: they commonly repeat room labels and plan dimensions while
# schedules/specifications/roof/details/elevations do not establish horizontal
# room extents. Missing/unknown titles remain fail-closed and are not promoted.
_ROOM_AREA_SUPPORT_TITLE_PATTERNS = (
    re.compile(r"\breflected\s+ceiling\s+plan\b", re.IGNORECASE),
    re.compile(r"\bceiling\s+plan\b", re.IGNORECASE),
    re.compile(
        r"\b(?:floor\s+)?finish(?:es)?\s*(?:(?:&|and|/|\+)\s*)?"
        r"partition(?:s)?\s+plan\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bfloor\s+finish(?:es)?\s+plan\b", re.IGNORECASE),
    re.compile(r"\bpartition(?:s)?\s+plan\b", re.IGNORECASE),
)


def _is_room_area_support_title(title: object) -> bool:
    clean = " ".join(str(title or "").strip().split())
    return bool(
        clean
        and any(pattern.search(clean) for pattern in _ROOM_AREA_SUPPORT_TITLE_PATTERNS)
    )


@dataclass(frozen=True)
class SourceFloorPlanPageDecision:
    page_index: int
    classification: str
    reason_code: str
    title: Optional[str] = None
    view_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceFloorPlanPageScope:
    decisions: tuple[SourceFloorPlanPageDecision, ...]
    selected_page_indices: tuple[int, ...]
    floor_plan_page_indices: tuple[int, ...]
    other_drawing_page_indices: tuple[int, ...] = ()
    schema_version: str = SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION

    @property
    def restricts(self) -> bool:
        """True only with positive evidence on both sides.

        At least one page must be positively a floor plan, and at least one page
        must positively be titled as a different drawing. A page with no title
        or viewport evidence is never removed.
        """
        return bool(self.floor_plan_page_indices) and bool(self.other_drawing_page_indices)

    @property
    def evidence_page_indices(self) -> tuple[int, ...]:
        """Pages that only supply cross-sheet evidence (empty unless ``restricts``)."""
        return self.other_drawing_page_indices if self.restricts else ()

    @property
    def room_area_support_page_indices(self) -> tuple[int, ...]:
        """Plan-like evidence pages eligible for cross-view room-area support.

        This is deliberately narrower than `evidence_page_indices`. It never
        changes topology classification and never removes evidence from other
        families; it only prevents room-area measurement from replaying every
        positively non-floor-plan sheet.
        """
        if not self.restricts:
            return ()
        other = set(self.other_drawing_page_indices)
        return tuple(
            decision.page_index
            for decision in self.decisions
            if decision.page_index in other
            and decision.classification == NOT_FLOOR_PLAN
            and _is_room_area_support_title(decision.title)
        )

    def topology_page_indices(self) -> Optional[tuple[int, ...]]:
        """Pages to use as topology scope, or ``None`` meaning "no restriction"."""
        if not self.restricts:
            return None
        other = set(self.other_drawing_page_indices)
        return tuple(index for index in self.selected_page_indices if index not in other)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "selected_page_indices": list(self.selected_page_indices),
            "floor_plan_page_indices": list(self.floor_plan_page_indices),
            "other_drawing_page_indices": list(self.other_drawing_page_indices),
            "evidence_page_indices": list(self.evidence_page_indices),
            "room_area_support_page_indices": list(
                self.room_area_support_page_indices
            ),
            "restricts": self.restricts,
            "decisions": [
                {
                    "page_index": d.page_index,
                    "classification": d.classification,
                    "reason_code": d.reason_code,
                    "title": d.title,
                    "view_types": list(d.view_types),
                }
                for d in self.decisions
            ],
        }


def _title_view_types(text: str) -> frozenset[str]:
    types: set[str] = set()
    for part in _TITLE_SPLIT_RE.split(str(text or "")):
        if not part.strip():
            continue
        view_type = DrawingViewClassifier.classify_text(part).value
        if view_type != DrawingViewType.UNKNOWN.value:
            types.add(view_type)
        page_type, confidence, _evidence = weighted_page_type("", "", part)
        if page_type == "Floor Plan" and confidence >= _MIN_PAGE_TYPE_CONFIDENCE:
            types.add(DrawingViewType.FLOOR_PLAN.value)
    return frozenset(types)


def _bound_titles(page: Any, page_number: int) -> list[str]:
    width = float(page.rect.width)
    height = float(page.rect.height)
    analysis = title_authority.analyse_cells(
        title_authority.page_cells(page), width, height, int(page_number), "native"
    )
    return [
        str(candidate.text)
        for candidate in analysis.candidates
        if candidate.kind == "label"
        and candidate.label_strength == "title_explicit"
        and not candidate.rejected
        and candidate.text
        and float(candidate.score) >= _MIN_TITLE_SCORE
    ]


def _has_f07_floor_plan_viewport(page: Any, page_number: int) -> bool:
    return any(
        viewport.view_type == DrawingViewType.FLOOR_PLAN.value
        and viewport.bounding_box is not None
        and viewport.status
        in (
            ViewportSegmentationStatus.RESOLVED.value,
            ViewportSegmentationStatus.DERIVED.value,
        )
        for viewport in segment_page_viewports(page, page_number=page_number)
    )


def _classify_page(page: Any, page_index: int) -> SourceFloorPlanPageDecision:
    page_number = page_index + 1
    try:
        titles = _bound_titles(page, page_number)
    except Exception:  # noqa: BLE001 - unreadable evidence never removes a page
        return SourceFloorPlanPageDecision(
            page_index, UNPROVEN, UNREADABLE_FLOOR_PLAN_PAGE
        )
    if titles:
        types = frozenset().union(*(_title_view_types(title) for title in titles))
        title = titles[0]
        if DrawingViewType.FLOOR_PLAN.value in types:
            return SourceFloorPlanPageDecision(
                page_index, FLOOR_PLAN, FLOOR_PLAN_PAGE_BOUND_TITLE, title, tuple(sorted(types))
            )
        return SourceFloorPlanPageDecision(
            page_index, NOT_FLOOR_PLAN, NOT_FLOOR_PLAN_PAGE_BOUND_TITLE, title, tuple(sorted(types))
        )
    try:
        if _has_f07_floor_plan_viewport(page, page_number):
            return SourceFloorPlanPageDecision(
                page_index, FLOOR_PLAN, FLOOR_PLAN_PAGE_F07_VIEWPORT
            )
    except Exception:  # noqa: BLE001
        return SourceFloorPlanPageDecision(
            page_index, UNPROVEN, UNREADABLE_FLOOR_PLAN_PAGE
        )
    return SourceFloorPlanPageDecision(page_index, UNPROVEN, UNPROVEN_FLOOR_PLAN_PAGE)


def classify_source_floor_plan_pages(
    doc: Any,
    page_indices: Iterable[int],
) -> SourceFloorPlanPageScope:
    """Classify the selected pages of one open PDF from source evidence only."""
    selected = tuple(
        sorted({int(i) for i in page_indices if isinstance(i, int) and 0 <= int(i) < len(doc)})
    )
    decisions = tuple(_classify_page(doc[index], index) for index in selected)
    floor = tuple(d.page_index for d in decisions if d.classification == FLOOR_PLAN)
    other = tuple(d.page_index for d in decisions if d.classification == NOT_FLOOR_PLAN)
    return SourceFloorPlanPageScope(
        decisions=decisions,
        selected_page_indices=selected,
        floor_plan_page_indices=floor,
        other_drawing_page_indices=other,
    )


def source_floor_plan_topology_scope(
    pdf_path: Any,
    page_indices: Sequence[int],
) -> Optional[SourceFloorPlanPageScope]:
    """Classify a PDF on disk; ``None`` when it cannot be read (no restriction)."""
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:  # noqa: BLE001
        return None
    try:
        return classify_source_floor_plan_pages(doc, page_indices)
    finally:
        doc.close()


__all__ = [
    "FLOOR_PLAN",
    "FLOOR_PLAN_PAGE_BOUND_TITLE",
    "FLOOR_PLAN_PAGE_F07_VIEWPORT",
    "NOT_FLOOR_PLAN",
    "NOT_FLOOR_PLAN_PAGE_BOUND_TITLE",
    "SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION",
    "SourceFloorPlanPageDecision",
    "SourceFloorPlanPageScope",
    "UNPROVEN",
    "UNPROVEN_FLOOR_PLAN_PAGE",
    "UNREADABLE_FLOOR_PLAN_PAGE",
    "classify_source_floor_plan_pages",
    "source_floor_plan_topology_scope",
]
