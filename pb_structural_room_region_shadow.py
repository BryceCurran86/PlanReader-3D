"""Shadow-only room-region evidence from structural wall ink, attached partitions and typed opening gaps.

Why this exists. The wall chain publishes bounded room faces only from authenticated physical wall scopes
(``pb_source_room_face_authority``) and has no notion of a doorway: a room whose door is a gap in its wall is not a bounded
face, so a plan can have its walls traced and still yield no room at all. This module answers a narrower, earlier question with
evidence only: given the wall linework that the structural-ink shadow proved (and, optionally, the attached partitions) and the
interruptions it typed as opening gaps, which areas of the page are enclosed, which printed room-name candidates stand in them,
and which wall faces look onto the page exterior?

What it does. It treats every structural candidate and every typed opening-gap chord as a barrier of one closure half-width,
takes the free space around the building, and reports each enclosed region with

* its polygon (page points, native frame), net and gross area in square points and its inscribed radius;
* its ancestry: the structural/partition primitive ids that run along its boundary with their tiers and the kind of ink evidence each is
  (paired face, single heavy stroke, attached partition: a single heavy line cannot be told from a floor-level or zone outline drawn in
  wall-weight ink), and the typed opening-gap chords that close it. A region closed only because of a chord says so; nothing is closed without one;
* the label candidates whose centre stands inside it: caller-supplied printed-name candidates (with the producer text-integrity
  verdict passed through unread) and the source-native outlined-lettering runs (ancestry only, not text). Two or more label
  candidates in one region are reported as an open or merged area; a region is never split to separate them;
* which structural primitives are adjacent to the exterior free space, to enclosed regions only, or to neither (the inside of a wall
  body).

What it deliberately does not do. It is not a room authority: it publishes no ``SourceRoomFaceRecord``, area quantity, scale or
room use, and its areas are in square points of the sheet, with no scale attached. It never infers a wall, closes a gap that was
not typed, snaps, merges or splits geometry beyond the closure half-width, and never chooses between competing labels. The closure
half-width is half the face-gap bound of the structural pairing rule, so every wall that rule can pair (two faces up to that bound
apart) is one barrier and the wall body between its faces is never a room. It is not called by a live path and raises no authority.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from pb_migration_contracts import stable_contract_id
from pb_structural_partition_ink_shadow import PARTITION_INK_CANDIDATE, PartitionInkReport
from pb_structural_wall_ink_shadow import (
    MAX_FACE_GAP_PT,
    REASON_HEAVIEST_SINGLE_STROKE_NETWORK,
    WALL_NETWORK_INK_CANDIDATE,
    OpeningGapCandidate,
    StructuralWallInkReport,
    _endpoints,
)

STRUCTURAL_ROOM_REGION_SCHEMA_VERSION = "1.0.0"

CLOSURE_HALF_WIDTH_PT = 0.5 * MAX_FACE_GAP_PT   # two faces the pairing rule can pair merge into one barrier
MIN_REGION_AREA_IN_CLOSURE_SQUARES = 25.0       # smaller free cells are counted, not listed (no silent caps: see the report)
MAX_REGION_INPUT_PRIMITIVES = 50_000
SHARED_BOUNDARY_FRACTION = 0.25                 # a face looks onto a cell when this share of it runs along the cell's boundary
_EPS_PT = 1e-3

REASON_NO_STRUCTURAL_INK = "no_structural_wall_ink"
REASON_SCOPE_TOO_LARGE = "structural_room_region_scope_too_large"

TIER_STRUCTURAL = 0
TIER_PARTITION = 1

# Which kind of ink evidence stands on a region's boundary. A heavy line that is only ONE stroke of its class (no paired face)
# cannot be told from a floor-level or zone outline drawn in wall-weight ink, so it is reported apart from paired faces.
KIND_PAIRED_FACE = "paired_face_network"
KIND_SINGLE_STROKE = "heaviest_single_stroke_network"
KIND_PARTITION = "attached_partition_paired_face"


@dataclass(frozen=True)
class RegionLabelInput:
    """A printed-name candidate offered by the caller. ``trust`` is the producer text-integrity verdict, passed through unread."""

    label_id: str
    text: str
    bbox: Tuple[float, float, float, float]
    trust: str = "not_supplied"
    source_word_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RegionLabelCandidate:
    label_id: str
    text: str
    trust: str
    centre: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    bbox_crosses_boundary: bool
    source_word_ids: Tuple[str, ...]


@dataclass(frozen=True)
class RegionGlyphRunRef:
    """A source-native outlined-lettering run whose centre stands in the region (ancestry only, not its text)."""

    index: int                              # position in ``StructuralWallInkReport.glyph_runs``
    centre: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    path_count: int
    touches_wall_network: bool
    bbox_crosses_boundary: bool


@dataclass(frozen=True)
class RoomRegion:
    region_id: str
    polygon: Tuple[Tuple[float, float], ...]          # exterior ring, native frame, rounded to 0.01 pt
    hole_count: int
    area_pt2: float                                   # net of holes
    gross_area_pt2: float
    bbox: Tuple[float, float, float, float]
    inradius_pt: float
    boundary_primitive_ids: Tuple[str, ...]
    boundary_tier_counts: Tuple[int, int]             # (structural, attached partition)
    boundary_evidence_kinds: Tuple[Tuple[str, int], ...]   # (kind, primitive count): paired face / single stroke / partition
    closure_chord_ids: Tuple[str, ...]
    labels: Tuple[RegionLabelCandidate, ...]
    glyph_runs: Tuple[RegionGlyphRunRef, ...]
    multi_label: bool


@dataclass(frozen=True)
class StructuralRoomRegionReport:
    regions: Tuple[RoomRegion, ...]
    closure_half_width_pt: float
    exterior_adjacent_primitive_ids: Tuple[str, ...]
    interior_only_primitive_ids: Tuple[str, ...]
    within_wall_body_primitive_ids: Tuple[str, ...]
    chord_ids: Tuple[str, ...]
    discarded_fragment_count: int
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = STRUCTURAL_ROOM_REGION_SCHEMA_VERSION
    shadow_only: bool = True
    live_effect: bool = False
    room_authority_granted: bool = False
    scale_authority_granted: bool = False


def chord_id(gap: OpeningGapCandidate) -> str:
    ends = sorted([(round(float(gap.end_a[0]), 4), round(float(gap.end_a[1]), 4)),
                   (round(float(gap.end_b[0]), 4), round(float(gap.end_b[1]), 4))])
    return stable_contract_id("structural_gap_chord", [list(ends[0]), list(ends[1])])


def _round_ring(ring: Iterable[Tuple[float, float]]) -> Tuple[Tuple[float, float], ...]:
    return tuple((round(float(x), 2), round(float(y), 2)) for x, y in ring)


def _chords(*gap_sets: Iterable[OpeningGapCandidate]) -> Dict[str, OpeningGapCandidate]:
    out: Dict[str, OpeningGapCandidate] = {}
    for gaps in gap_sets:
        for gap in gaps:
            out.setdefault(chord_id(gap), gap)
    return dict(sorted(out.items()))


def derive_structural_room_regions(
    segments: Sequence[Mapping[str, Any]],
    report: StructuralWallInkReport,
    partition: Optional[PartitionInkReport] = None,
    *,
    labels: Sequence[RegionLabelInput] = (),
) -> StructuralRoomRegionReport:
    """See the module docstring. Pure, deterministic, input-order invariant; never mutates its inputs."""
    geometry: Dict[str, Tuple[float, float, float, float]] = {}
    seen: set = set()
    for position, segment in enumerate(segments):
        ident = str(segment.get("id") if segment.get("id") not in (None, "") else f"anon:{position}")
        if ident in seen:
            raise ValueError("source primitive ids must be unique")
        seen.add(ident)
        p = _endpoints(segment)
        if p is not None:
            geometry[ident] = p

    single_stroke = {d.source_primitive_id for d in report.decisions if REASON_HEAVIEST_SINGLE_STROKE_NETWORK in d.reason_codes}
    named = set(report.ids_with(WALL_NETWORK_INK_CANDIDATE)) | (set(partition.ids_with(PARTITION_INK_CANDIDATE)) if partition is not None else set())
    if not named <= seen:
        raise ValueError("the structural reports name primitives that are not in these segments")
    tiers: Dict[str, int] = {i: TIER_STRUCTURAL for i in report.ids_with(WALL_NETWORK_INK_CANDIDATE) if i in geometry}
    if partition is not None:
        for ident in partition.ids_with(PARTITION_INK_CANDIDATE):
            if ident in geometry and ident not in tiers:
                tiers[ident] = TIER_PARTITION
    members = {i: geometry[i] for i in sorted(tiers) if math.hypot(geometry[i][2] - geometry[i][0], geometry[i][3] - geometry[i][1]) > 0.0}
    chords = _chords(report.opening_gaps, partition.opening_gaps if partition is not None else ())
    if not members:
        return StructuralRoomRegionReport((), CLOSURE_HALF_WIDTH_PT, (), (), (), (), 0, (REASON_NO_STRUCTURAL_INK,))
    if len(members) + len(chords) > MAX_REGION_INPUT_PRIMITIVES:
        return StructuralRoomRegionReport((), CLOSURE_HALF_WIDTH_PT, (), (), (), (), 0, (REASON_SCOPE_TOO_LARGE,))

    half = CLOSURE_HALF_WIDTH_PT

    barrier_keys: List[Tuple[str, str]] = []                  # (kind, id)
    lines: List[LineString] = []
    for ident, p in members.items():
        barrier_keys.append(("primitive", ident))
        lines.append(LineString([(p[0], p[1]), (p[2], p[3])]))
    for cid, gap in chords.items():
        if (gap.end_a[0], gap.end_a[1]) == (gap.end_b[0], gap.end_b[1]):
            continue
        barrier_keys.append(("chord", cid))
        lines.append(LineString([gap.end_a, gap.end_b]))
    buffers = [ln.buffer(half, cap_style="square", join_style="mitre") for ln in lines]
    barrier = unary_union(buffers)
    minx, miny, maxx, maxy = barrier.bounds
    margin = 10.0 * half
    frame = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
    free = frame.difference(barrier)
    pieces: List[Polygon] = list(free.geoms) if hasattr(free, "geoms") else [free]
    exterior_piece: Optional[Polygon] = None
    enclosed: List[Polygon] = []
    fb = frame.bounds
    for piece in pieces:
        if all(abs(a - b) <= 1e-6 for a, b in zip(piece.bounds, fb)):
            exterior_piece = piece
        else:
            enclosed.append(piece)

    min_area = MIN_REGION_AREA_IN_CLOSURE_SQUARES * half * half
    line_tree = STRtree(lines)
    listed: List[Tuple[Polygon, Polygon]] = []                 # (free cell, region polygon = cell grown back to the faces)
    discarded = 0
    for cell in enclosed:
        grown = cell.buffer(half, join_style="mitre")
        if grown.area < min_area:
            discarded += 1
            continue
        listed.append((cell, grown))

    def touching(cell: Polygon) -> List[int]:
        """Barrier lines that run along the cell's boundary (not lines that merely end near one of its corners)."""
        out = []
        boundary = cell.boundary
        for k in line_tree.query(cell.buffer(half + _EPS_PT), predicate="intersects"):
            line = lines[int(k)]
            shared = boundary.intersection(line.buffer(half + _EPS_PT)).length
            if shared >= SHARED_BOUNDARY_FRACTION * line.length:
                out.append(int(k))
        return sorted(out)

    label_boxes = [(lab, box(*lab.bbox), Point((lab.bbox[0] + lab.bbox[2]) / 2.0, (lab.bbox[1] + lab.bbox[3]) / 2.0))
                   for lab in sorted(labels, key=lambda x: x.label_id)]
    glyph_boxes = [(k, g, box(*g.bbox), Point((g.bbox[0] + g.bbox[2]) / 2.0, (g.bbox[1] + g.bbox[3]) / 2.0))
                   for k, g in enumerate(report.glyph_runs)]

    regions: List[RoomRegion] = []
    for cell, grown in listed:
        poly = shapely.normalize(grown) if isinstance(grown, Polygon) else grown
        if not isinstance(poly, Polygon):
            poly = max(list(poly.geoms), key=lambda g: g.area)
        touched = touching(cell)
        prim_ids = tuple(sorted(barrier_keys[k][1] for k in touched if barrier_keys[k][0] == "primitive"))
        chord_ids = tuple(sorted(barrier_keys[k][1] for k in touched if barrier_keys[k][0] == "chord"))
        tier_counts = (sum(1 for i in prim_ids if tiers[i] == TIER_STRUCTURAL), sum(1 for i in prim_ids if tiers[i] == TIER_PARTITION))
        kinds: Dict[str, int] = defaultdict(int)
        for i in prim_ids:
            kinds[KIND_PARTITION if tiers[i] == TIER_PARTITION else KIND_SINGLE_STROKE if i in single_stroke else KIND_PAIRED_FACE] += 1
        try:
            inradius = float(shapely.maximum_inscribed_circle(poly, tolerance=max(half / 4.0, 0.05)).length)
        except Exception:
            inradius = 0.0
        found: List[RegionLabelCandidate] = []
        for lab, lbox, centre in label_boxes:
            if poly.contains(centre):
                found.append(RegionLabelCandidate(
                    lab.label_id, lab.text, lab.trust, (round(centre.x, 2), round(centre.y, 2)),
                    tuple(round(float(v), 2) for v in lab.bbox), not poly.contains(lbox), tuple(lab.source_word_ids)))
        runs: List[RegionGlyphRunRef] = []
        for k, g, gbox, centre in glyph_boxes:
            if poly.contains(centre):
                runs.append(RegionGlyphRunRef(k, (round(centre.x, 2), round(centre.y, 2)), tuple(round(float(v), 2) for v in g.bbox),
                                              g.path_count, g.touches_wall_network, not poly.contains(gbox)))
        exterior_ring = _round_ring(poly.exterior.coords)
        region_id = stable_contract_id("structural_room_region", {
            "ring": exterior_ring, "holes": [list(_round_ring(r.coords)) for r in poly.interiors]})
        regions.append(RoomRegion(
            region_id=region_id, polygon=exterior_ring, hole_count=len(poly.interiors),
            area_pt2=round(poly.area, 3), gross_area_pt2=round(Polygon(poly.exterior).area, 3),
            bbox=tuple(round(float(v), 2) for v in poly.bounds), inradius_pt=round(inradius, 3),
            boundary_primitive_ids=prim_ids, boundary_tier_counts=tier_counts, boundary_evidence_kinds=tuple(sorted(kinds.items())),
            closure_chord_ids=chord_ids,
            labels=tuple(found), glyph_runs=tuple(runs),
            multi_label=len({f.label_id for f in found}) >= 2))
    regions.sort(key=lambda r: (-r.area_pt2, r.bbox, r.region_id))

    exterior_ids: set = set()
    if exterior_piece is not None:
        exterior_ids = {barrier_keys[k][1] for k in touching(exterior_piece) if barrier_keys[k][0] == "primitive"}
    enclosed_ids: set = set()
    for cell in enclosed:
        enclosed_ids |= {barrier_keys[k][1] for k in touching(cell) if barrier_keys[k][0] == "primitive"}
    interior_only = sorted(enclosed_ids - exterior_ids)
    within = sorted(i for i in members if i not in exterior_ids and i not in enclosed_ids)
    return StructuralRoomRegionReport(
        regions=tuple(regions), closure_half_width_pt=half, exterior_adjacent_primitive_ids=tuple(sorted(exterior_ids)),
        interior_only_primitive_ids=tuple(interior_only), within_wall_body_primitive_ids=tuple(within),
        chord_ids=tuple(chords), discarded_fragment_count=discarded)
