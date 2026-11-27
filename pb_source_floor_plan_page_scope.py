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


SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION = "1.1.0"

FLOOR_PLAN_PAGE_BOUND_TITLE = "floor_plan_bound_title"
FLOOR_PLAN_PAGE_F07_VIEWPORT = "floor_plan_f07_viewport"
FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE = "floor_plan_corroborated_ocr_title"
NOT_FLOOR_PLAN_PAGE_BOUND_TITLE = "not_floor_plan_bound_title"
NOT_FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE = "not_floor_plan_corroborated_ocr_title"
NOT_FLOOR_PLAN_PAGE_DOCUMENT_HEADER = "not_floor_plan_document_header"
NOT_FLOOR_PLAN_PAGE_SCHEDULE_VIEWPORT = "not_floor_plan_schedule_viewport"
UNPROVEN_FLOOR_PLAN_PAGE = "floor_plan_page_unproven"
UNREADABLE_FLOOR_PLAN_PAGE = "floor_plan_page_unreadable"

FLOOR_PLAN = "floor_plan"
NOT_FLOOR_PLAN = "not_floor_plan"
UNPROVEN = "unproven"

_MIN_TITLE_SCORE = 60.0
_MIN_PAGE_TYPE_CONFIDENCE = 60
_TITLE_SPLIT_RE = re.compile(r"\s*(?:&|/|\+|,|;|\band\b)\s*", re.IGNORECASE)
_HEADER_TOP_FRACTION = 0.25

# Generic administrative register / transmittal document headers that appear at
# the top of standalone non-plan sheets lacking an architectural title block.
_NON_PLAN_REGISTER_HEADER_PATTERNS = (
    re.compile(r"\b(?:document|drawing)\s+transmittal\b", re.IGNORECASE),
    re.compile(r"\btransmittal\b", re.IGNORECASE),
    re.compile(
        r"\b(?:drawing|document|sheet|issue)\s+(?:register|list|index|schedule)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btable\s+of\s+contents\b", re.IGNORECASE),
)
_FLOOR_PLAN_HEADER_GUARD_RE = re.compile(r"\bfloor\s+plan\b", re.IGNORECASE)

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
    sheet_role: str = UNPROVEN
    authenticated_floor_plan_viewport_count: int = 0
    viewport_types: tuple[str, ...] = ()
    is_mixed_sheet: bool = False


@dataclass(frozen=True)
class SourceSetAdmissionPacket:
    """Generic multi-sheet drawing-set admission summary (A25).

    Summarizes authenticated sheet roles across floor, section, elevation,
    setout/detail, schedule, RCP, floor-finish, specification, and register
    sheets, and explicitly abstains on finish specifications when no finish
    specification / finish plan / RCP source sheet exists in the set.
    """

    floor_plan_pages: tuple[int, ...]
    section_pages: tuple[int, ...]
    elevation_pages: tuple[int, ...]
    setout_or_detail_pages: tuple[int, ...]
    schedule_pages: tuple[int, ...]
    rcp_pages: tuple[int, ...]
    floor_finish_plan_pages: tuple[int, ...]
    specification_pages: tuple[int, ...]
    register_pages: tuple[int, ...]
    unproven_pages: tuple[int, ...]
    has_finish_specification_source: bool
    finish_specification_status: str
    commercial_quantity_authority: bool = False
    schema_version: str = SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "floor_plan_pages": list(self.floor_plan_pages),
            "section_pages": list(self.section_pages),
            "elevation_pages": list(self.elevation_pages),
            "setout_or_detail_pages": list(self.setout_or_detail_pages),
            "schedule_pages": list(self.schedule_pages),
            "rcp_pages": list(self.rcp_pages),
            "floor_finish_plan_pages": list(self.floor_finish_plan_pages),
            "specification_pages": list(self.specification_pages),
            "register_pages": list(self.register_pages),
            "unproven_pages": list(self.unproven_pages),
            "has_finish_specification_source": self.has_finish_specification_source,
            "finish_specification_status": self.finish_specification_status,
            "commercial_quantity_authority": False,
        }


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

    def build_source_set_admission_packet(self) -> SourceSetAdmissionPacket:
        """Assemble a fail-closed generic multi-sheet admission packet (A25)."""
        floor_pages = tuple(
            d.page_index for d in self.decisions if d.classification == FLOOR_PLAN
        )
        section_pages = tuple(
            d.page_index for d in self.decisions if d.sheet_role == DrawingViewType.SECTION.value
        )
        elevation_pages = tuple(
            d.page_index for d in self.decisions if d.sheet_role == DrawingViewType.ELEVATION.value
        )
        setout_or_detail_pages = tuple(
            d.page_index
            for d in self.decisions
            if d.sheet_role in (DrawingViewType.DETAIL.value, "setout")
        )
        schedule_pages = tuple(
            d.page_index for d in self.decisions if d.sheet_role == DrawingViewType.SCHEDULE.value
        )
        rcp_pages = tuple(
            d.page_index
            for d in self.decisions
            if d.sheet_role == DrawingViewType.REFLECTED_CEILING_PLAN.value
        )
        floor_finish_pages = tuple(
            d.page_index
            for d in self.decisions
            if d.sheet_role == DrawingViewType.FLOOR_FINISH_PLAN.value
        )
        specification_pages = tuple(
            d.page_index
            for d in self.decisions
            if d.sheet_role == DrawingViewType.SPECIFICATION.value
        )
        register_pages = tuple(
            d.page_index for d in self.decisions if d.sheet_role == "register"
        )
        unproven_pages = tuple(
            d.page_index for d in self.decisions if d.classification == UNPROVEN
        )
        has_finish_spec = bool(floor_finish_pages or specification_pages or rcp_pages)
        status = (
            "finish_specification_source_present"
            if has_finish_spec
            else "abstained_no_finish_specification_source"
        )
        return SourceSetAdmissionPacket(
            floor_plan_pages=floor_pages,
            section_pages=section_pages,
            elevation_pages=elevation_pages,
            setout_or_detail_pages=setout_or_detail_pages,
            schedule_pages=schedule_pages,
            rcp_pages=rcp_pages,
            floor_finish_plan_pages=floor_finish_pages,
            specification_pages=specification_pages,
            register_pages=register_pages,
            unproven_pages=unproven_pages,
            has_finish_specification_source=has_finish_spec,
            finish_specification_status=status,
        )

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
                    "sheet_role": d.sheet_role,
                    "authenticated_floor_plan_viewport_count": int(
                        d.authenticated_floor_plan_viewport_count
                    ),
                    "viewport_types": list(d.viewport_types),
                    "is_mixed_sheet": bool(d.is_mixed_sheet),
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


def _viewport_scope_signals(
    page: Any, page_number: int
) -> tuple[int, tuple[str, ...], bool]:
    """Return (authenticated_floor_plan_vp_count, unique_viewport_types, schedule_only)."""
    viewports = tuple(segment_page_viewports(page, page_number=page_number))
    auth_fp_count = sum(
        1
        for viewport in viewports
        if viewport.view_type == DrawingViewType.FLOOR_PLAN.value
        and viewport.bounding_box is not None
        and viewport.status
        in (
            ViewportSegmentationStatus.RESOLVED.value,
            ViewportSegmentationStatus.DERIVED.value,
        )
    )
    vp_types = tuple(
        sorted(
            {
                str(viewport.view_type)
                for viewport in viewports
                if getattr(viewport, "view_type", None)
                and str(viewport.view_type) != DrawingViewType.UNKNOWN.value
            }
        )
    )
    schedule_only = bool(viewports) and all(
        str(getattr(viewport, "view_type", "")) == DrawingViewType.SCHEDULE.value
        for viewport in viewports
    )
    return auth_fp_count, vp_types, schedule_only


def _has_f07_floor_plan_viewport(page: Any, page_number: int) -> bool:
    auth_fp_count, _vp_types, _schedule_only = _viewport_scope_signals(
        page, page_number
    )
    return auth_fp_count > 0


def _document_header_non_plan_role(page: Any) -> Optional[tuple[str, str]]:
    """Detect an explicit standalone non-plan document header in the top band.

    Only fires when a page has no bound architectural title block and no
    authoritative floor-plan viewport. Rejects any top band mentioning a floor
    plan so mixed sheets are never silently excluded.
    """
    height = float(getattr(getattr(page, "rect", None), "height", 0.0) or 0.0)
    if height <= 0.0:
        return None
    top_limit = height * _HEADER_TOP_FRACTION
    blocks = page.get_text("blocks") or ()
    header_lines: list[str] = []
    for block in blocks:
        if len(block) < 5:
            continue
        y0 = float(block[1])
        if y0 > top_limit:
            continue
        text = " ".join(str(block[4] or "").strip().split())
        if text:
            header_lines.append(text)
    if not header_lines:
        return None
    header_blob = " ".join(header_lines)
    if _FLOOR_PLAN_HEADER_GUARD_RE.search(header_blob):
        return None
    for line in header_lines:
        if any(pattern.search(line) for pattern in _NON_PLAN_REGISTER_HEADER_PATTERNS):
            return ("register", line)
    return None


def _infer_sheet_role(
    classification: str,
    view_types: tuple[str, ...],
    *,
    is_mixed: bool,
    title: Optional[str] = None,
) -> str:
    if classification == UNPROVEN:
        return UNPROVEN
    if classification == FLOOR_PLAN:
        return "mixed_floor_plan" if is_mixed else FLOOR_PLAN
    for candidate in (
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
        DrawingViewType.REFLECTED_CEILING_PLAN.value,
        DrawingViewType.FLOOR_FINISH_PLAN.value,
        DrawingViewType.ELEVATION.value,
        DrawingViewType.SECTION.value,
        DrawingViewType.ROOF_PLAN.value,
        DrawingViewType.DETAIL.value,
    ):
        if candidate in view_types:
            return candidate
    if "register" in view_types:
        return "register"
    if title and re.search(r"\bset[\s-]?out\b", str(title), re.IGNORECASE):
        return "setout"
    return "other_drawing"


def _classify_page(page: Any, page_index: int) -> SourceFloorPlanPageDecision:
    page_number = page_index + 1
    try:
        titles = _bound_titles(page, page_number)
    except Exception:  # noqa: BLE001 - unreadable evidence never removes a page
        return SourceFloorPlanPageDecision(
            page_index, UNPROVEN, UNREADABLE_FLOOR_PLAN_PAGE, sheet_role=UNPROVEN
        )
    if titles:
        types = tuple(sorted(frozenset().union(*(_title_view_types(title) for title in titles))))
        title = titles[0]
        if DrawingViewType.FLOOR_PLAN.value in types:
            auth_fp_count = 0
            vp_types: tuple[str, ...] = ()
            try:
                auth_fp_count, vp_types, _schedule_only = _viewport_scope_signals(
                    page, page_number
                )
            except Exception:  # noqa: BLE001
                auth_fp_count = 0
                vp_types = ()
            distinct_views = set(types) | set(vp_types)
            is_mixed = len(distinct_views) > 1
            return SourceFloorPlanPageDecision(
                page_index,
                FLOOR_PLAN,
                FLOOR_PLAN_PAGE_BOUND_TITLE,
                title,
                types,
                sheet_role=_infer_sheet_role(FLOOR_PLAN, types, is_mixed=is_mixed),
                authenticated_floor_plan_viewport_count=auth_fp_count,
                viewport_types=vp_types,
                is_mixed_sheet=is_mixed,
            )
        is_mixed = len(types) > 1
        return SourceFloorPlanPageDecision(
            page_index,
            NOT_FLOOR_PLAN,
            NOT_FLOOR_PLAN_PAGE_BOUND_TITLE,
            title,
            types,
            sheet_role=_infer_sheet_role(
                NOT_FLOOR_PLAN, types, is_mixed=is_mixed, title=title
            ),
            is_mixed_sheet=is_mixed,
        )
    try:
        auth_fp_count, vp_types, schedule_only = _viewport_scope_signals(
            page, page_number
        )
    except Exception:  # noqa: BLE001
        return SourceFloorPlanPageDecision(
            page_index, UNPROVEN, UNREADABLE_FLOOR_PLAN_PAGE, sheet_role=UNPROVEN
        )
    if auth_fp_count > 0:
        is_mixed = len(vp_types) > 1
        return SourceFloorPlanPageDecision(
            page_index,
            FLOOR_PLAN,
            FLOOR_PLAN_PAGE_F07_VIEWPORT,
            view_types=vp_types,
            sheet_role=_infer_sheet_role(FLOOR_PLAN, vp_types, is_mixed=is_mixed),
            authenticated_floor_plan_viewport_count=auth_fp_count,
            viewport_types=vp_types,
            is_mixed_sheet=is_mixed,
        )
    try:
        header_hit = _document_header_non_plan_role(page)
    except Exception:  # noqa: BLE001
        header_hit = None
    if header_hit is not None:
        role, header_title = header_hit
        return SourceFloorPlanPageDecision(
            page_index,
            NOT_FLOOR_PLAN,
            NOT_FLOOR_PLAN_PAGE_DOCUMENT_HEADER,
            title=header_title,
            view_types=(role,),
            sheet_role=role,
            authenticated_floor_plan_viewport_count=0,
            viewport_types=vp_types,
            is_mixed_sheet=False,
        )
    if schedule_only:
        return SourceFloorPlanPageDecision(
            page_index,
            NOT_FLOOR_PLAN,
            NOT_FLOOR_PLAN_PAGE_SCHEDULE_VIEWPORT,
            view_types=(DrawingViewType.SCHEDULE.value,),
            sheet_role=DrawingViewType.SCHEDULE.value,
            authenticated_floor_plan_viewport_count=0,
            viewport_types=vp_types,
            is_mixed_sheet=False,
        )
    return SourceFloorPlanPageDecision(
        page_index,
        UNPROVEN,
        UNPROVEN_FLOOR_PLAN_PAGE,
        sheet_role=UNPROVEN,
        authenticated_floor_plan_viewport_count=0,
        viewport_types=vp_types,
        is_mixed_sheet=len(vp_types) > 1,
    )


def _apply_corroborated_ocr_title_fallback(
    doc: Any,
    selected: tuple[int, ...],
    decisions: tuple[SourceFloorPlanPageDecision, ...],
) -> tuple[SourceFloorPlanPageDecision, ...]:
    """Use pb_page_title_authority's corroborated OCR title-block reader on outlined-text sets.

    Only accepts titles bound to an explicit title-block field label
    (``source == "label"``) with confidence >= ``_MIN_TITLE_SCORE``. Never
    accepts bare OCR headings and never mutates already-classified pages.
    """
    try:
        analyses = [
            title_authority.analyse_page(doc[index], index + 1)
            for index in selected
        ]
        resolved = title_authority.resolve_document(analyses)
    except Exception:  # noqa: BLE001
        return decisions
    by_page_no = {int(pt.page_no): pt for pt in resolved}
    updated: list[SourceFloorPlanPageDecision] = []
    for decision in decisions:
        if decision.classification != UNPROVEN:
            updated.append(decision)
            continue
        pt = by_page_no.get(decision.page_index + 1)
        if (
            pt is None
            or not pt.title
            or pt.source != "label"
            or float(pt.confidence) < _MIN_TITLE_SCORE
        ):
            updated.append(decision)
            continue
        types = tuple(sorted(_title_view_types(pt.title)))
        if DrawingViewType.FLOOR_PLAN.value in types:
            is_mixed = len(set(types) | set(decision.viewport_types)) > 1
            updated.append(
                SourceFloorPlanPageDecision(
                    decision.page_index,
                    FLOOR_PLAN,
                    FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE,
                    title=str(pt.title),
                    view_types=types,
                    sheet_role=_infer_sheet_role(
                        FLOOR_PLAN, types, is_mixed=is_mixed, title=str(pt.title)
                    ),
                    authenticated_floor_plan_viewport_count=decision.authenticated_floor_plan_viewport_count,
                    viewport_types=decision.viewport_types,
                    is_mixed_sheet=is_mixed,
                )
            )
        else:
            is_mixed = len(types) > 1
            updated.append(
                SourceFloorPlanPageDecision(
                    decision.page_index,
                    NOT_FLOOR_PLAN,
                    NOT_FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE,
                    title=str(pt.title),
                    view_types=types,
                    sheet_role=_infer_sheet_role(
                        NOT_FLOOR_PLAN, types, is_mixed=is_mixed, title=str(pt.title)
                    ),
                    authenticated_floor_plan_viewport_count=decision.authenticated_floor_plan_viewport_count,
                    viewport_types=decision.viewport_types,
                    is_mixed_sheet=is_mixed,
                )
            )
    return tuple(updated)


def classify_source_floor_plan_pages(
    doc: Any,
    page_indices: Iterable[int],
    *,
    allow_corroborated_ocr_titles: bool = False,
) -> SourceFloorPlanPageScope:
    """Classify the selected pages of one open PDF from source evidence only."""
    if type(allow_corroborated_ocr_titles) is not bool:
        raise TypeError("allow_corroborated_ocr_titles must be a bool")
    selected = tuple(
        sorted({int(i) for i in page_indices if isinstance(i, int) and 0 <= int(i) < len(doc)})
    )
    decisions = tuple(_classify_page(doc[index], index) for index in selected)
    if (
        allow_corroborated_ocr_titles
        and decisions
        and all(d.classification == UNPROVEN for d in decisions)
    ):
        decisions = _apply_corroborated_ocr_title_fallback(doc, selected, decisions)
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
    *,
    allow_corroborated_ocr_titles: bool = False,
) -> Optional[SourceFloorPlanPageScope]:
    """Classify a PDF on disk; ``None`` when it cannot be read (no restriction)."""
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:  # noqa: BLE001
        return None
    try:
        return classify_source_floor_plan_pages(
            doc,
            page_indices,
            allow_corroborated_ocr_titles=allow_corroborated_ocr_titles,
        )
    finally:
        doc.close()


__all__ = [
    "FLOOR_PLAN",
    "FLOOR_PLAN_PAGE_BOUND_TITLE",
    "FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE",
    "FLOOR_PLAN_PAGE_F07_VIEWPORT",
    "NOT_FLOOR_PLAN",
    "NOT_FLOOR_PLAN_PAGE_BOUND_TITLE",
    "NOT_FLOOR_PLAN_PAGE_CORROBORATED_OCR_TITLE",
    "NOT_FLOOR_PLAN_PAGE_DOCUMENT_HEADER",
    "NOT_FLOOR_PLAN_PAGE_SCHEDULE_VIEWPORT",
    "SOURCE_FLOOR_PLAN_PAGE_SCOPE_SCHEMA_VERSION",
    "SourceFloorPlanPageDecision",
    "SourceFloorPlanPageScope",
    "SourceSetAdmissionPacket",
    "UNPROVEN",
    "UNPROVEN_FLOOR_PLAN_PAGE",
    "UNREADABLE_FLOOR_PLAN_PAGE",
    "classify_source_floor_plan_pages",
    "source_floor_plan_topology_scope",
]
