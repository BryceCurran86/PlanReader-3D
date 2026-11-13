"""Doorway-closed room rings as a ``SourceRoomFaceScopeResult`` (SHADOW ONLY, default-off).

``pb_layered_wall_doorway_room_ring_shadow`` finds rooms enclosed by layered native wall ink
plus source-attested doorway closures. This module only re-expresses those rings in the
EXISTING room-face vocabulary so the unchanged downstream chain (room labels, canonical
rooms and floors, the area bridge) can consume them:

* a CANDIDATE ring becomes a ``SourceRoomFaceRecord`` whose wall edges are owned by wall strips
  (native path index). A doorway closure is a planarization chord only: it is NEVER listed as a
  wall owner (not in ``bounding_wall_ids``, not in ``boundary_wall_edges``), so it cannot become
  wall length, a host or an opening deduction. A chord edge is exactly a polygon edge that has no
  wall owner; its identity is bound into the record id. In the live
  path a ring is a record only if EXACTLY ONE authenticated figured (horizontal, vertical)
  pair has the ring's bounding box as its witness box: a closed ring that no printed figure
  corroborates (for example a region that leaks through openings with no closure evidence)
  stays an abstention and can never be measured as a room;
* a ring that stays open, or is not so corroborated, becomes a ``SourceRoomFaceAbstention``;
* the scope is always partial (``source_room_face_universe_partial``): a ring scope never
  claims the face universe, and it carries ``LAYERED_RING_SCOPE_REASON`` so a consumer can
  tell the provenance.

It never reads or changes the W2/W4 wall scope that walls and openings use. It issues no
scale, area, finish or quantity.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from shapely.geometry import Polygon
from shapely.geometry import box as shapely_box

from pb_layered_wall_doorway_partition_witness_shadow import partition_groups
from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    LayeredRoomRingRecord,
    LayeredRoomRingResult,
    build_from_pdf_bytes,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_room_face_authority import (
    SCOPE_OVERRIDE_SEAL,
    SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    SourceRoomFaceAbstention,
    SourceRoomFaceRecord,
    SourceRoomFaceScopeOverride,
    SourceRoomFaceScopeResult,
    _canonical_polygon,
    _edge,
    _polygon_area,
    scope_override_digest,
)

LAYERED_RING_SCOPE_REASON = "layered_wall_doorway_room_ring_scope"
# Per-record token: the face is not its own bounding rectangle (a wall return, an alcove split off by a
# closure). A bounding box may corroborate the topology; it can never set such a face's metric area.
RING_NOT_A_RECTANGLE_PREFIX = "layered_ring_not_a_rectangle:"
# Distinct provenance for the opt-in sliding-leaf partition witness: the scope still never claims the face
# universe, and a part is corroborated only by its group's union envelope, never by its own box.
LAYERED_RING_PARTITION_REASON = "layered_wall_doorway_room_ring_partition_witness"
RING_PARTITION_PART_PREFIX = "layered_ring_partition_part:"
# Opt-in finished-face gate: a ring follows the DRAWN wall face. Unless the original establishes that this is the
# exposed finished face, the face is a noncommercial candidate: no documented area, no room-area quantity.
LAYERED_RING_FINISHED_FACE_GATE_REASON = "layered_wall_doorway_room_ring_finished_face_gate"
RING_FINISHED_FACE_REQUIRED_PREFIX = "layered_ring_finished_face_required:"
# Witness line to drawn face: representation noise, far below the 2.5 pt production snap, a hard bound.
RING_FIGURED_BOX_TOLERANCE_PT = 0.5
# The decision scope the live room composition resolves per page (``wall-source:page-N``).
_PAGE_DECISION_SCOPE = "wall-source:page-{page_id}"
_CLOSURE_OWNER_PREFIX = "layered_doorway_closure:"


def _face_ids(ring: LayeredRoomRingRecord, polygon: tuple, *, scope: Sequence[str]) -> tuple[str, dict]:
    payload = {
        "document_id": scope[0], "revision_id": scope[1], "source_sha256": scope[2],
        "snapshot_id": scope[3], "page_id": scope[4], "decision_scope_id": scope[5],
        "polygon": polygon,
    }
    return stable_contract_id("layered_ring_source_room_face", payload, digest_chars=32), payload


def _boundary_edges(ring: LayeredRoomRingRecord) -> tuple[tuple[str, tuple], ...]:
    points = ring.polygon_pdf_pts
    edges = [(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    owners = ring.edge_owner_ids if len(ring.edge_owner_ids) == len(edges) else tuple(() for _ in edges)
    pairs: list[tuple[str, tuple]] = []
    for (first, second), edge_owners in zip(edges, owners):
        for owner in edge_owners:
            if owner.startswith(_CLOSURE_OWNER_PREFIX):
                continue  # a doorway chord is not a wall: no wall owner is ever recorded for it
            pairs.append((owner, _edge(first, second)))
    return tuple(pairs)


def figured_box_pair_count(
    bounding_box: Sequence[float], dimensions: Sequence[object], *,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
) -> int:
    """How many authenticated (horizontal, vertical) figured pairs have exactly this witness box."""
    x0, y0, x1, y1 = bounding_box
    horizontal = set()
    vertical = set()
    for dimension in dimensions:
        (ax, ay), (bx, by) = dimension.endpoints_pt  # type: ignore[attr-defined]
        if dimension.orientation == "horizontal":  # type: ignore[attr-defined]
            span = tuple(sorted((float(ax), float(bx))))
            if abs(span[0] - x0) <= tolerance_pt and abs(span[1] - x1) <= tolerance_pt:
                horizontal.add(getattr(dimension, "dimension_id", span))
        elif dimension.orientation == "vertical":  # type: ignore[attr-defined]
            span = tuple(sorted((float(ay), float(by))))
            if abs(span[0] - y0) <= tolerance_pt and abs(span[1] - y1) <= tolerance_pt:
                vertical.add(getattr(dimension, "dimension_id", span))
    return len(horizontal) * len(vertical)


def _fills_its_bounding_rectangle(polygon: Sequence[Sequence[float]]) -> bool:
    """True only when the face IS its bounding rectangle, tested in space and not by an aggregate area.

    Every point of the box must lie within the representation noise (``NOISE_PT``) of the face. A wall return,
    a recess or a jamb offset is spatial content: however small its area against the box, a notch wider than
    twice the noise bound leaves box points farther than that from the face, so it is never absorbed. Extra
    collinear vertices change nothing.
    """
    face = Polygon([(float(p[0]), float(p[1])) for p in polygon])
    if not face.is_valid or face.is_empty:
        return False
    rectangle = shapely_box(*face.bounds)
    return rectangle.difference(face.buffer(NOISE_PT, join_style=2)).area <= 1e-9


def layered_ring_room_face_scope(
    ring_result: LayeredRoomRingResult,
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    decision_scope_id: str,
    corroborating_dimensions: Optional[Sequence[object]] = None,
    partition_witness: bool = False,
    finished_face_gate: bool = False,
) -> Optional[SourceRoomFaceScopeResult]:
    """The ring scope for one page, or None when no ring closed (nothing is overridden).

    ``corroborating_dimensions`` (authenticated native figured dimensions of the page): when
    given, a CANDIDATE ring becomes a record only if exactly one figured pair has its bounding
    box as witness box; otherwise it is kept as an abstention. When None every CANDIDATE ring
    is a record (direct converter use and tests).

    ``partition_witness`` (default False, its own control): rings joined by real sliding-leaf chords form
    a partition group (see ``pb_layered_wall_doorway_partition_witness_shadow``). Every ring of such a group
    is judged ONLY by the group: the whole group becomes records when its membership is exact and the
    union's outer envelope is the witness box of exactly one authenticated figured pair; otherwise every
    member is an abstention. The shared pair is topology corroboration of the union; it is never a part's
    area. Without ``corroborating_dimensions`` a partition group cannot be corroborated and abstains.
    """
    if type(partition_witness) is not bool:
        raise ValueError("partition_witness must be an explicit boolean")
    if type(finished_face_gate) is not bool:
        raise ValueError("finished_face_gate must be an explicit boolean")
    if not any(r.status is EvidenceResolutionStatus.CANDIDATE for r in ring_result.rings):
        return None
    scope = (document_id, revision_id, source_sha256, snapshot_id, page_id, decision_scope_id)
    records: list[SourceRoomFaceRecord] = []
    abstained: list[SourceRoomFaceAbstention] = []
    not_rectangle_tokens: list[str] = []
    partition_tokens: list[str] = []
    finished_face_tokens: list[str] = []
    # ring record id -> (group ring ids, whole group corroborated)
    partition_of: dict[str, tuple[tuple[str, ...], bool]] = {}
    if partition_witness:
        page_index = int(page_id) - 1 if page_id.isascii() and page_id.isdecimal() else -1
        for group in partition_groups(ring_result, source_sha256=source_sha256, page_index=page_index):
            corroborated_group = (
                group.valid
                and corroborating_dimensions is not None
                and figured_box_pair_count(group.envelope, corroborating_dimensions) == 1
            )
            for ring_record_id in group.ring_record_ids:
                partition_of[ring_record_id] = (group.ring_record_ids, corroborated_group)
    for ring in ring_result.rings:
        polygon = _canonical_polygon(ring.polygon_pdf_pts)
        if not polygon:
            continue
        face_id, payload = _face_ids(ring, polygon, scope=scope)
        owner_ids = tuple(sorted({
            owner for owners in ring.edge_owner_ids for owner in owners
            if not owner.startswith(_CLOSURE_OWNER_PREFIX)
        }))
        boundary = _boundary_edges(ring)
        area = _polygon_area(polygon)
        common = dict(
            face_id=face_id, document_id=document_id, revision_id=revision_id, source_sha256=source_sha256,
            snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=decision_scope_id,
            polygon_pdf_pts=polygon, bounding_wall_ids=owner_ids, area_page_pts2=area,
            boundary_wall_edges=boundary,
        )
        group_of = partition_of.get(ring.record_id)
        if group_of is not None:
            corroborated = group_of[1]  # a group member is judged by its group's union envelope only
        else:
            corroborated = (
                corroborating_dimensions is None
                or figured_box_pair_count(ring.bbox_pdf_pts, corroborating_dimensions) == 1
            )
        if ring.status is EvidenceResolutionStatus.CANDIDATE and corroborated:
            record_payload = {
                **payload, "owners": owner_ids, "ring_record_id": ring.record_id,
                "closure_ids": list(ring.bounding_closure_ids),
            }
            if group_of is not None:
                record_payload["partition_group"] = list(group_of[0])
            record_id = stable_contract_id("layered_ring_source_room_face_record", record_payload, digest_chars=32)
            records.append(SourceRoomFaceRecord(record_id=record_id, **common))
            if group_of is not None:
                partition_tokens.append(f"{RING_PARTITION_PART_PREFIX}{record_id}")
            if finished_face_gate:
                finished_face_tokens.append(f"{RING_FINISHED_FACE_REQUIRED_PREFIX}{record_id}")
            if not _fills_its_bounding_rectangle(polygon):
                not_rectangle_tokens.append(f"{RING_NOT_A_RECTANGLE_PREFIX}{record_id}")
        else:
            abstained.append(SourceRoomFaceAbstention(reason=SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED, **common))
    if not records:
        return None
    records.sort(key=lambda r: r.record_id)
    abstained.sort(key=lambda r: r.face_id)
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        reason_codes=(
            SOURCE_ROOM_FACE_SCOPE_RESOLVED, SOURCE_ROOM_FACE_UNIVERSE_PARTIAL, LAYERED_RING_SCOPE_REASON,
            *((LAYERED_RING_PARTITION_REASON,) if partition_tokens else ()),
            *((LAYERED_RING_FINISHED_FACE_GATE_REASON,) if finished_face_tokens else ()),
            *sorted(not_rectangle_tokens),
            *sorted(partition_tokens),
            *sorted(finished_face_tokens),
        ),
        document_id=document_id, revision_id=revision_id, source_sha256=source_sha256,
        snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=decision_scope_id,
        abstained_faces=tuple(abstained),
    )


def layered_ring_scope_overrides(
    source_producer: object,
    *,
    revision_id: str,
    page_ids: Sequence[str],
    require_figured_box: bool = True,
    sliding_leaf_frame_closure: bool = False,
    partition_witness: bool = False,
    finished_face_gate: bool = False,
    dark_painted_wall_source: bool = False,
) -> Mapping[tuple[str, str, str, str, str, str], SourceRoomFaceScopeOverride]:
    """Issued ring scopes keyed like the room-face authority, read from the SHA-pinned native bytes.

    With ``require_figured_box`` (the live default) only rings corroborated by exactly one
    authenticated figured pair become records; the rest are abstentions.

    ``partition_witness`` (default False; requires ``sliding_leaf_frame_closure`` and ``require_figured_box``)
    additionally judges sliding-leaf partition groups by their union envelope (see the converter).
    """
    if type(partition_witness) is not bool:
        raise ValueError("partition_witness must be an explicit boolean")
    if type(finished_face_gate) is not bool:
        raise ValueError("finished_face_gate must be an explicit boolean")
    if type(dark_painted_wall_source) is not bool:
        raise ValueError("dark_painted_wall_source must be an explicit boolean")
    if dark_painted_wall_source and not finished_face_gate:
        raise ValueError("dark_painted_wall_source requires finished_face_gate")
    if partition_witness and not (sliding_leaf_frame_closure and require_figured_box):
        raise ValueError("partition_witness requires sliding_leaf_frame_closure and require_figured_box")
    from pb_cross_view_ceiling_finish_authority import _source_bytes
    from pb_cross_view_room_area_authority import _trusted_native_dimensions_for_page
    from pb_drawing_evidence_binding import DrawingViewType

    published = source_producer.published_snapshot_for_revision(revision_id)  # type: ignore[attr-defined]
    payload = _source_bytes(source_producer, revision_id)  # type: ignore[arg-type]
    if published is None or payload is None:
        return {}
    overrides = {}
    for page_id in page_ids:
        page = str(page_id)
        if not page.isascii() or not page.isdecimal() or page.startswith("0"):
            continue
        ring_result = build_from_pdf_bytes(
            payload, source_sha256=published.revision.source_sha256, page_index=int(page) - 1,
            sliding_leaf_frame_closure=sliding_leaf_frame_closure,
            dark_painted_wall_source=dark_painted_wall_source,
        )
        decision_scope_id = _PAGE_DECISION_SCOPE.format(page_id=page)
        dimensions = None
        if require_figured_box and any(r.status is EvidenceResolutionStatus.CANDIDATE for r in ring_result.rings):
            dimensions = _trusted_native_dimensions_for_page(
                source_producer, revision_id=published.revision.revision_id, page_id=page,  # type: ignore[arg-type]
                candidate_lines=(), view_type=DrawingViewType.FLOOR_PLAN.value,
            )
        scope = layered_ring_room_face_scope(
            ring_result,
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            page_id=page, decision_scope_id=decision_scope_id, corroborating_dimensions=dimensions,
            partition_witness=partition_witness, finished_face_gate=finished_face_gate,
        )
        if scope is not None:
            key = (
                published.revision.document_id, published.revision.revision_id,
                published.revision.source_sha256, published.snapshot.snapshot_id, page, decision_scope_id,
            )
            overrides[key] = SourceRoomFaceScopeOverride(
                scope=scope, receipt_digest=scope_override_digest(scope), _seal=SCOPE_OVERRIDE_SEAL,
            )
    return overrides


def ring_face_bounding_box(record: SourceRoomFaceRecord) -> tuple[float, float, float, float]:
    xs = [p[0] for p in record.polygon_pdf_pts]
    ys = [p[1] for p in record.polygon_pdf_pts]
    return min(xs), min(ys), max(xs), max(ys)


__all__ = [
    "LAYERED_RING_FINISHED_FACE_GATE_REASON",
    "LAYERED_RING_PARTITION_REASON",
    "LAYERED_RING_SCOPE_REASON",
    "RING_FIGURED_BOX_TOLERANCE_PT",
    "RING_FINISHED_FACE_REQUIRED_PREFIX",
    "RING_NOT_A_RECTANGLE_PREFIX",
    "RING_PARTITION_PART_PREFIX",
    "figured_box_pair_count",
    "layered_ring_room_face_scope",
    "layered_ring_scope_overrides",
    "ring_face_bounding_box",
]
