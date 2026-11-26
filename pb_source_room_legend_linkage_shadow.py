"""Source-backed room legend number-to-name linkage shadow evidence.

Implements Work Order Item 25 as a pure, read-only, default-off shadow evidence
module for Claude/GPT floor consumers:
- Parses explicit Room Legend / Room Schedule tables (two-column or inline under
  an authenticated room-legend title) while rejecting door/window schedules,
  finish legends, and arbitrary notes.
- Links room-number bubbles strictly contained inside unique simple physical
  room polygons to their legend room names within the exact same
  (document_id, revision_id, source_sha256), preserving full plan and legend
  page/viewport/observation lineage.
- Fails closed (CONFLICT / ABSTAINED) on duplicate/conflicting legend numbers,
  multi-bubble rooms, overlapping room polygons, cross-revision/SHA legends,
  legend-vs-direct room-name disagreements, or non-room opening/finish codes.
- Never fabricates floor polygons, floor areas, or commercial quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Strictly exclude opening marks (D01, W01, WD01, DW01, ED01, ID01) and common
# finish codes (FT1, WT1, CT1, CL01, IPF1) from being misread as room numbers.
_EXCLUDED_NON_ROOM_CODE_RE = re.compile(
    r"^(?:[EI]?[DW]|WD|DW|FT|WT|CT|CL|FL|WL|SK|IPF|PB|FC)\d{1,4}$",
    re.IGNORECASE,
)
_ROOM_NUMBER_RE = re.compile(
    r"^(?:(RM|R|G|B|L\d+[.-]?|F\d+[.-]?)\s*[-]?\s*)?(\d{1,4})$",
    re.IGNORECASE,
)
_ROOM_LEGEND_TITLE_RE = re.compile(
    r"^(?:room|space|accommodation|area)\s+(?:legend|schedule|key|index|register)$",
    re.IGNORECASE,
)
_ROOM_NO_COL_RE = re.compile(
    r"^(?:(?:room|space)\s+(?:no\.?|number|num|id|code|ref)|no\.?|number|ref|id)$",
    re.IGNORECASE,
)
_ROOM_NAME_COL_RE = re.compile(
    r"^(?:(?:room|space|area)\s+(?:name|title|description|use|label)|room|space|name|description)$",
    re.IGNORECASE,
)
_NON_ROOM_SCHEDULE_COL_RE = re.compile(
    r"\b(?:door|window|glazing|hardware|finish|ceiling|wall\s+type|leaf|frame|width|height)\b",
    re.IGNORECASE,
)
_INLINE_LEGEND_PAIR_RE = re.compile(
    r"^\s*((?:(?:RM|R|G|B|L\d+[.-]?|F\d+[.-]?)\s*[-]?\s*)?\d{1,4})\s*(?:[:=\-–—.]\s*|\s{2,})([A-Za-z][A-Za-z0-9 &/'().-]{1,80})\s*$",
    re.IGNORECASE,
)

Point = tuple[float, float]


def _req_str(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _req_sha256(value: object, name: str) -> str:
    clean = _req_str(value, name).lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{name} must be a 64-char hex sha256")
    return clean


def _norm_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _norm_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_room_number_key(raw: object) -> tuple[str, int] | None:
    """Return canonical (prefix, positive_int) for a room number, rejecting opening/finish codes."""
    if type(raw) is not str:
        return None
    clean = _norm_space(raw).upper()
    if not clean:
        return None
    if _EXCLUDED_NON_ROOM_CODE_RE.fullmatch(clean):
        return None
    match = _ROOM_NUMBER_RE.fullmatch(clean)
    if not match:
        return None
    prefix = re.sub(r"[\s.-]+", "", (match.group(1) or "").upper())
    number = int(match.group(2))
    if number < 1 or number > 9999:
        return None
    return (prefix, number)


def canonical_room_number_label(raw: object) -> str | None:
    key = canonical_room_number_key(raw)
    if key is None:
        return None
    return f"{key[0]}{key[1]}" if key[0] else str(key[1])


def _polygon_is_simple(points: Sequence[Point]) -> bool:
    if not points:
        return False
    pts = tuple(points[:-1] if len(points) > 3 and points[0] == points[-1] else points)
    n = len(pts)
    if n < 3:
        return False
    for pt in pts:
        if type(pt) is not tuple or len(pt) != 2:
            return False
        if isinstance(pt[0], bool) or isinstance(pt[1], bool):
            return False
        if not (math.isfinite(float(pt[0])) and math.isfinite(float(pt[1]))):
            return False
    if len(set(pts)) != n:
        return False
    twice_area = sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
        for i in range(n)
    )
    if abs(twice_area) < 1e-6:
        return False

    def orient(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if orient(a, b, c) * orient(a, b, d) < 0.0 and orient(c, d, a) * orient(c, d, b) < 0.0:
                return False
    return True


def _point_in_polygon(pt: Point, polygon: Sequence[Point]) -> bool:
    pts = tuple(polygon[:-1] if len(polygon) > 3 and polygon[0] == polygon[-1] else polygon)
    x, y = pt
    inside = False
    for (x0, y0), (x1, y1) in zip(pts, (*pts[1:], pts[0])):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


@dataclass(frozen=True)
class RoomLegendTableRowInput:
    document_id: str
    revision_id: str
    source_sha256: str
    legend_page_id: str
    legend_viewport_id: str
    observation_ids: tuple[str, ...]
    cells: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "document_id", _req_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _req_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "legend_page_id", _req_str(self.legend_page_id, "legend_page_id"))
        object.__setattr__(self, "legend_viewport_id", _req_str(self.legend_viewport_id, "legend_viewport_id"))
        obs = tuple(sorted({_req_str(o, "observation_ids") for o in self.observation_ids}))
        if not obs:
            raise ValueError("observation_ids must be non-empty")
        object.__setattr__(self, "observation_ids", obs)
        object.__setattr__(self, "cells", tuple(_norm_space(c) for c in self.cells))


@dataclass(frozen=True)
class RoomLegendEntryShadow:
    entry_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    legend_page_id: str
    legend_viewport_id: str
    observation_ids: tuple[str, ...]
    printed_room_number: str
    canonical_room_number: str
    room_name: str
    parse_source: str


@dataclass(frozen=True)
class RoomLegendParseResult:
    entries: tuple[RoomLegendEntryShadow, ...]
    conflicting_canonical_numbers: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PhysicalRoomFaceCandidate:
    room_face_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    plan_page_id: str
    plan_viewport_id: str
    polygon_pdf_pts: tuple[Point, ...]
    room_face_evidence_ids: tuple[str, ...]
    direct_room_name_text: str | None = None
    direct_room_name_observation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "room_face_id", _req_str(self.room_face_id, "room_face_id"))
        object.__setattr__(self, "document_id", _req_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _req_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "plan_page_id", _req_str(self.plan_page_id, "plan_page_id"))
        object.__setattr__(self, "plan_viewport_id", _req_str(self.plan_viewport_id, "plan_viewport_id"))
        ev = tuple(sorted({_req_str(v, "room_face_evidence_ids") for v in self.room_face_evidence_ids}))
        if not ev:
            raise ValueError("room_face_evidence_ids must be non-empty")
        object.__setattr__(self, "room_face_evidence_ids", ev)
        if self.direct_room_name_text is not None:
            clean = _norm_space(self.direct_room_name_text)
            object.__setattr__(self, "direct_room_name_text", clean or None)
        if self.direct_room_name_observation_id is not None:
            clean_obs = str(self.direct_room_name_observation_id).strip()
            object.__setattr__(self, "direct_room_name_observation_id", clean_obs or None)


@dataclass(frozen=True)
class RoomNumberBubbleCandidate:
    callout_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    plan_page_id: str
    plan_viewport_id: str
    observation_id: str
    raw_text: str
    anchor_pt_pdf_pts: Point

    def __post_init__(self) -> None:
        object.__setattr__(self, "callout_id", _req_str(self.callout_id, "callout_id"))
        object.__setattr__(self, "document_id", _req_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _req_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "plan_page_id", _req_str(self.plan_page_id, "plan_page_id"))
        object.__setattr__(self, "plan_viewport_id", _req_str(self.plan_viewport_id, "plan_viewport_id"))
        object.__setattr__(self, "observation_id", _req_str(self.observation_id, "observation_id"))
        object.__setattr__(self, "raw_text", _req_str(self.raw_text, "raw_text"))
        pt = self.anchor_pt_pdf_pts
        if (
            type(pt) is not tuple
            or len(pt) != 2
            or isinstance(pt[0], bool)
            or isinstance(pt[1], bool)
            or not (math.isfinite(float(pt[0])) and math.isfinite(float(pt[1])))
        ):
            raise ValueError("anchor_pt_pdf_pts must be a finite 2-tuple")
        object.__setattr__(self, "anchor_pt_pdf_pts", (float(pt[0]), float(pt[1])))


@dataclass(frozen=True)
class RoomLegendLinkageShadow:
    record_id: str
    room_face_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    plan_page_id: str
    plan_viewport_id: str
    bubble_callout_id: str | None
    bubble_observation_id: str | None
    printed_room_number: str | None
    canonical_room_number: str | None
    linked_room_name: str | None
    legend_entry_id: str | None
    legend_page_id: str | None
    legend_viewport_id: str | None
    legend_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    floor_area_authority_granted: bool = False


@dataclass(frozen=True)
class RoomLegendLinkageReport:
    schema_version: str
    room_links: tuple[RoomLegendLinkageShadow, ...]
    unmatched_legend_entries: tuple[RoomLegendEntryShadow, ...]
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    floor_area_authority_granted: bool = False


def parse_room_legend_rows(
    rows: Sequence[RoomLegendTableRowInput],
) -> RoomLegendParseResult:
    """Extract room-number -> room-name entries under explicit room-legend headers only."""
    if not rows:
        return RoomLegendParseResult(entries=(), conflicting_canonical_numbers=(), reason_codes=())

    # Group rows by exact legend scope (doc, rev, sha, page, viewport) preserving order.
    by_scope: dict[tuple[str, str, str, str, str], list[RoomLegendTableRowInput]] = {}
    for row in rows:
        scope = (
            row.document_id, row.revision_id, row.source_sha256,
            row.legend_page_id, row.legend_viewport_id,
        )
        by_scope.setdefault(scope, []).append(row)

    raw_entries: list[RoomLegendEntryShadow] = []
    reasons: set[str] = set()

    for scope, scope_rows in sorted(by_scope.items()):
        mode: str | None = None  # "table" or "inline"
        no_col = -1
        name_col = -1
        for row in scope_rows:
            cells = row.cells
            non_empty = [c for c in cells if c]
            if not non_empty:
                continue
            joined = " ".join(non_empty)

            # Check for a non-room schedule header (e.g. DOOR NO. | ROOM NAME | DOOR LEAF):
            # resets active room-legend mode so door/window/finish tables are never read as room legends.
            if any(_NON_ROOM_SCHEDULE_COL_RE.search(c) for c in non_empty):
                if len(non_empty) >= 2 or "schedule" in joined.lower() or "legend" in joined.lower():
                    mode = None
                    no_col = -1
                    name_col = -1
                    continue

            # Explicit room-legend title enables inline pair extraction (and allows a
            # subsequent 2-column table header to upgrade to strict table mode).
            if len(non_empty) == 1 and _ROOM_LEGEND_TITLE_RE.fullmatch(non_empty[0]):
                mode = "inline"
                no_col = -1
                name_col = -1
                continue

            # Explicit 2+-column room-legend header (strictly one number col & one name col).
            if len(cells) >= 2:
                no_hits = [i for i, c in enumerate(cells) if c and _ROOM_NO_COL_RE.fullmatch(c)]
                name_hits = [
                    i for i, c in enumerate(cells)
                    if c and i not in no_hits and _ROOM_NAME_COL_RE.fullmatch(c)
                ]
                if len(no_hits) == 1 and len(name_hits) == 1:
                    mode = "table"
                    no_col = no_hits[0]
                    name_col = name_hits[0]
                    continue

            if mode == "table" and max(no_col, name_col) < len(cells):
                raw_no = cells[no_col]
                raw_name = cells[name_col]
                canon = canonical_room_number_label(raw_no)
                if canon is not None and raw_name and re.search(r"[A-Za-z]", raw_name):
                    entry_id = stable_contract_id(
                        "room_legend_entry_shadow",
                        {
                            "document_id": row.document_id,
                            "revision_id": row.revision_id,
                            "source_sha256": row.source_sha256,
                            "legend_page_id": row.legend_page_id,
                            "legend_viewport_id": row.legend_viewport_id,
                            "observation_ids": row.observation_ids,
                            "canonical_room_number": canon,
                            "room_name": raw_name,
                        },
                    )
                    raw_entries.append(
                        RoomLegendEntryShadow(
                            entry_id=entry_id,
                            document_id=row.document_id,
                            revision_id=row.revision_id,
                            source_sha256=row.source_sha256,
                            legend_page_id=row.legend_page_id,
                            legend_viewport_id=row.legend_viewport_id,
                            observation_ids=row.observation_ids,
                            printed_room_number=raw_no,
                            canonical_room_number=canon,
                            room_name=raw_name,
                            parse_source="room_legend_table",
                        )
                    )
            elif mode == "inline":
                match = _INLINE_LEGEND_PAIR_RE.fullmatch(joined)
                if match:
                    raw_no, raw_name = _norm_space(match.group(1)), _norm_space(match.group(2))
                    canon = canonical_room_number_label(raw_no)
                    if canon is not None and raw_name:
                        entry_id = stable_contract_id(
                            "room_legend_entry_shadow",
                            {
                                "document_id": row.document_id,
                                "revision_id": row.revision_id,
                                "source_sha256": row.source_sha256,
                                "legend_page_id": row.legend_page_id,
                                "legend_viewport_id": row.legend_viewport_id,
                                "observation_ids": row.observation_ids,
                                "canonical_room_number": canon,
                                "room_name": raw_name,
                            },
                        )
                        raw_entries.append(
                            RoomLegendEntryShadow(
                                entry_id=entry_id,
                                document_id=row.document_id,
                                revision_id=row.revision_id,
                                source_sha256=row.source_sha256,
                                legend_page_id=row.legend_page_id,
                                legend_viewport_id=row.legend_viewport_id,
                                observation_ids=row.observation_ids,
                                printed_room_number=raw_no,
                                canonical_room_number=canon,
                                room_name=raw_name,
                                parse_source="room_legend_inline",
                            )
                        )

    # Detect duplicate/conflicting canonical room numbers within the same (doc, rev, sha).
    by_rev_num: dict[tuple[str, str, str, str], list[RoomLegendEntryShadow]] = {}
    for entry in raw_entries:
        key = (entry.document_id, entry.revision_id, entry.source_sha256, entry.canonical_room_number)
        by_rev_num.setdefault(key, []).append(entry)

    clean_entries: list[RoomLegendEntryShadow] = []
    conflicting_nums: set[str] = set()
    for (_doc, _rev, _sha, canon_num), items in sorted(by_rev_num.items()):
        if len(items) > 1:
            conflicting_nums.add(canon_num)
            reasons.add("duplicate_room_legend_number")
        else:
            clean_entries.append(items[0])

    return RoomLegendParseResult(
        entries=tuple(sorted(clean_entries, key=lambda e: (e.document_id, e.revision_id, e.canonical_room_number, e.entry_id))),
        conflicting_canonical_numbers=tuple(sorted(conflicting_nums)),
        reason_codes=tuple(sorted(reasons)),
    )


def link_room_legend_to_physical_rooms(
    *,
    legend_result: RoomLegendParseResult,
    room_faces: Sequence[PhysicalRoomFaceCandidate],
    number_callouts: Sequence[RoomNumberBubbleCandidate],
) -> RoomLegendLinkageReport:
    """Link authenticated room-number bubbles inside unique physical room faces to legend names."""
    seen_face_ids: set[str] = set()
    for face in room_faces:
        if face.room_face_id in seen_face_ids:
            raise ValueError(f"duplicate_room_face_id:{face.room_face_id}")
        seen_face_ids.add(face.room_face_id)

    seen_callout_ids: set[str] = set()
    for callout in number_callouts:
        if callout.callout_id in seen_callout_ids:
            raise ValueError(f"duplicate_room_callout_id:{callout.callout_id}")
        seen_callout_ids.add(callout.callout_id)

    legend_by_rev_num: dict[tuple[str, str, str, str], RoomLegendEntryShadow] = {}
    for entry in legend_result.entries:
        rev_num = (entry.document_id, entry.revision_id, entry.source_sha256, entry.canonical_room_number)
        legend_by_rev_num[rev_num] = entry
    conflicting_legend_nums = set(legend_result.conflicting_canonical_numbers)

    ordered_faces = sorted(
        room_faces,
        key=lambda f: (f.document_id, f.revision_id, f.source_sha256, f.plan_page_id, f.plan_viewport_id, f.room_face_id),
    )
    valid_face_flags = {face.room_face_id: _polygon_is_simple(face.polygon_pdf_pts) for face in ordered_faces}

    # Map each room-number bubble to all valid containing room faces in the exact same
    # (doc, rev, sha, plan_page_id, plan_viewport_id).
    bubbles_by_face: dict[str, list[RoomNumberBubbleCandidate]] = {f.room_face_id: [] for f in ordered_faces}
    overlapping_bubble_faces: set[str] = set()
    report_reasons: set[str] = set(legend_result.reason_codes)

    for bubble in sorted(number_callouts, key=lambda b: b.callout_id):
        if canonical_room_number_label(bubble.raw_text) is None:
            continue
        containing: list[PhysicalRoomFaceCandidate] = []
        for face in ordered_faces:
            if not valid_face_flags[face.room_face_id]:
                continue
            if (
                face.document_id == bubble.document_id
                and face.revision_id == bubble.revision_id
                and face.source_sha256 == bubble.source_sha256
                and face.plan_page_id == bubble.plan_page_id
                and face.plan_viewport_id == bubble.plan_viewport_id
                and _point_in_polygon(bubble.anchor_pt_pdf_pts, face.polygon_pdf_pts)
            ):
                containing.append(face)
        if len(containing) > 1:
            for face in containing:
                overlapping_bubble_faces.add(face.room_face_id)
            report_reasons.add("bubble_in_multiple_room_polygons")
        elif len(containing) == 1:
            bubbles_by_face[containing[0].room_face_id].append(bubble)

    matched_entry_ids: set[str] = set()
    links_out: list[RoomLegendLinkageShadow] = []

    for face in ordered_faces:
        f_reasons: list[str] = []
        bubble_id: str | None = None
        bubble_obs: str | None = None
        printed_no: str | None = None
        canon_no: str | None = None
        linked_name: str | None = None
        entry_id: str | None = None
        legend_page: str | None = None
        legend_vp: str | None = None
        legend_obs: tuple[str, ...] = ()

        if not valid_face_flags[face.room_face_id]:
            status = EvidenceResolutionStatus.ABSTAINED
            f_reasons.append("invalid_or_degenerate_room_polygon")
        elif face.room_face_id in overlapping_bubble_faces:
            status = EvidenceResolutionStatus.CONFLICT
            f_reasons.append("bubble_in_multiple_room_polygons")
        else:
            contained = bubbles_by_face[face.room_face_id]
            distinct_canons = {canonical_room_number_label(b.raw_text) for b in contained}
            if not contained:
                status = EvidenceResolutionStatus.ABSTAINED
                f_reasons.append("no_room_number_bubble_in_room_face")
            elif len(distinct_canons) > 1:
                status = EvidenceResolutionStatus.CONFLICT
                f_reasons.append("multiple_room_numbers_in_one_room_face")
            elif len(contained) > 1:
                status = EvidenceResolutionStatus.CONFLICT
                f_reasons.append("duplicate_room_number_bubbles_in_one_room_face")
            else:
                bubble = contained[0]
                bubble_id = bubble.callout_id
                bubble_obs = bubble.observation_id
                printed_no = bubble.raw_text
                canon_no = canonical_room_number_label(bubble.raw_text)
                assert canon_no is not None
                if canon_no in conflicting_legend_nums:
                    status = EvidenceResolutionStatus.CONFLICT
                    f_reasons.append("conflicting_room_legend_definition")
                else:
                    rev_key = (face.document_id, face.revision_id, face.source_sha256, canon_no)
                    entry = legend_by_rev_num.get(rev_key)
                    if entry is None:
                        status = EvidenceResolutionStatus.ABSTAINED
                        f_reasons.append("room_number_not_in_legend")
                    elif (
                        face.direct_room_name_text is not None
                        and _norm_name_key(face.direct_room_name_text) != _norm_name_key(entry.room_name)
                    ):
                        status = EvidenceResolutionStatus.CONFLICT
                        f_reasons.append("legend_vs_direct_room_name_conflict")
                    else:
                        matched_entry_ids.add(entry.entry_id)
                        linked_name = entry.room_name
                        entry_id = entry.entry_id
                        legend_page = entry.legend_page_id
                        legend_vp = entry.legend_viewport_id
                        legend_obs = entry.observation_ids
                        status = EvidenceResolutionStatus.CORROBORATED
                        f_reasons.append("room_legend_number_to_name_linked")
                        if face.direct_room_name_text is not None:
                            f_reasons.append("corroborated_with_direct_room_name")

        record_id = stable_contract_id(
            "room_legend_linkage_shadow",
            {
                "room_face_id": face.room_face_id,
                "document_id": face.document_id,
                "revision_id": face.revision_id,
                "source_sha256": face.source_sha256,
                "plan_page_id": face.plan_page_id,
                "plan_viewport_id": face.plan_viewport_id,
                "bubble_callout_id": bubble_id,
                "legend_entry_id": entry_id,
                "status": status.value,
                "reason_codes": tuple(f_reasons),
            },
        )
        links_out.append(
            RoomLegendLinkageShadow(
                record_id=record_id,
                room_face_id=face.room_face_id,
                document_id=face.document_id,
                revision_id=face.revision_id,
                source_sha256=face.source_sha256,
                plan_page_id=face.plan_page_id,
                plan_viewport_id=face.plan_viewport_id,
                bubble_callout_id=bubble_id,
                bubble_observation_id=bubble_obs,
                printed_room_number=printed_no,
                canonical_room_number=canon_no,
                linked_room_name=linked_name,
                legend_entry_id=entry_id,
                legend_page_id=legend_page,
                legend_viewport_id=legend_vp,
                legend_observation_ids=legend_obs,
                status=status,
                reason_codes=tuple(f_reasons),
                commercial_authority_granted=False,
                floor_area_authority_granted=False,
            )
        )

    unmatched = tuple(
        entry for entry in legend_result.entries if entry.entry_id not in matched_entry_ids
    )
    return RoomLegendLinkageReport(
        schema_version=SCHEMA_VERSION,
        room_links=tuple(links_out),
        unmatched_legend_entries=unmatched,
        reason_codes=tuple(sorted(report_reasons)),
        commercial_authority_granted=False,
        floor_area_authority_granted=False,
    )


__all__ = [
    "PhysicalRoomFaceCandidate",
    "RoomLegendEntryShadow",
    "RoomLegendLinkageReport",
    "RoomLegendLinkageShadow",
    "RoomLegendParseResult",
    "RoomLegendTableRowInput",
    "RoomNumberBubbleCandidate",
    "SCHEMA_VERSION",
    "canonical_room_number_key",
    "canonical_room_number_label",
    "link_room_legend_to_physical_rooms",
    "parse_room_legend_rows",
]
