"""Original-source raster solid-flank reconstruction for GPT MAX (shadow).

Consumes ONLY an already producer-authenticated GPT2 source-parent handoff.
Two truly distinct raster wall-band FACE source chains must terminate at the
opposite endpoints of one original raster wall-band END. Preserve the entire
chain of exact source IDs; never select nearest line, discard a competitor, or
infer structural W4 identity from similarly drawn ink.

This is a source *geometry candidate*, not a host wall, physical wall, whole-
wall frame, dimension, opening count, deduction, or customer quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pb_gpt2_raster_opening_parent_source_shadow import (
    AuthenticatedRasterOpeningParentLine,
    RasterOpeningParentSourceHandoff,
)
from pb_source_visibility_authority import RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS

# Producer's reviewed original raster geometry quantization, not W2 snap.
_SOURCE_QUANT_PT = 0.0001


@dataclass(frozen=True)
class RasterSourceFlankBandCandidate:
    page_id: str
    face_parent_chains: tuple[tuple[str, ...], tuple[str, ...]]
    end_parent_id: str
    near_center_pdf_pt: tuple[float, float]
    far_center_pdf_pt: tuple[float, float]
    original_source_visible_ids: tuple[str, ...]
    structural_wall_granted: bool = False
    whole_wall_frame_granted: bool = False
    host_binding_granted: bool = False


@dataclass(frozen=True)
class RasterSourceFlankBandResult:
    status: str
    source_sha256: str
    candidates: tuple[RasterSourceFlankBandCandidate, ...]
    unresolved_source_parent_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    physical_wall_granted: bool = False
    opening_host_granted: bool = False
    opening_count_granted: bool = False
    firm_quantity_granted: bool = False


def _point_equal(a, b) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= _SOURCE_QUANT_PT


def _line_points(line):
    x0, y0, x1, y1 = line.geometry_pdf_points
    return ((x0, y0), (x1, y1))


def _normalised(v):
    mag = math.hypot(*v)
    return (v[0] / mag, v[1] / mag) if mag > _SOURCE_QUANT_PT else None


def _extend_face_chain(
    attached: AuthenticatedRasterOpeningParentLine,
    near: tuple[float, float],
    faces: Sequence[AuthenticatedRasterOpeningParentLine],
):
    """Reassemble only uniquely connected collinear source fragments.

    Contiguity is EXACT original-page point geometry (0.0001-pt producer
    quantization), never the 2.5pt structural snapping rule.
    """
    ends = _line_points(attached)
    if _point_equal(ends[0], near) == _point_equal(ends[1], near):
        return None
    current = ends[1] if _point_equal(ends[0], near) else ends[0]
    axis = _normalised((current[0] - near[0], current[1] - near[1]))
    if axis is None:
        return None
    path = [attached]
    consumed = {attached.parent_observation_id}
    while True:
        continuations = []
        for other in faces:
            if other.parent_observation_id in consumed:
                continue
            a, b = _line_points(other)
            touches = [_point_equal(a, current), _point_equal(b, current)]
            if touches.count(True) != 1:
                continue
            far = b if touches[0] else a
            vec = (far[0] - current[0], far[1] - current[1])
            forward = vec[0] * axis[0] + vec[1] * axis[1]
            transverse = abs(vec[0] * axis[1] - vec[1] * axis[0])
            if forward > _SOURCE_QUANT_PT and transverse <= _SOURCE_QUANT_PT:
                continuations.append((other, far))
        if len(continuations) > 1:
            return None
        if not continuations:
            break
        nxt, current = continuations[0]
        consumed.add(nxt.parent_observation_id)
        path.append(nxt)
    return (current, tuple(item.parent_observation_id for item in path),
            tuple(item.visible_observation_id for item in path), axis)


def _one_end_candidates(end, faces):
    a, b = _line_points(end)
    if _point_equal(a, b):
        return ()
    # Never choose first among source lines at an endpoint. Different line
    # segments sharing the endpoint must be assessed as competing evidence.
    candidates = []
    for first, second in ((a, b), (b, a)):
        left = [line for line in faces
                if _point_equal(_line_points(line)[0], first)
                != _point_equal(_line_points(line)[1], first)]
        right = [line for line in faces
                 if _point_equal(_line_points(line)[0], second)
                 != _point_equal(_line_points(line)[1], second)]
        if len(left) != 1 or len(right) != 1 or left[0] == right[0]:
            continue
        first_path = _extend_face_chain(left[0], first, faces)
        second_path = _extend_face_chain(right[0], second, faces)
        if first_path is None or second_path is None:
            continue
        far1, ids1, visible1, axis1 = first_path
        far2, ids2, visible2, axis2 = second_path
        if set(ids1).intersection(ids2):
            continue
        end_unit = _normalised((second[0] - first[0], second[1] - first[1]))
        if end_unit is None:
            continue
        # Two parallel FACE chains must continue in the SAME direction away
        # from the source END. The END must join them perpendicularly; faces
        # may have split source ancestry, but neither may end early.
        if (abs(axis1[0]*end_unit[0] + axis1[1]*end_unit[1]) > 1e-5
                or abs(axis2[0]*end_unit[0] + axis2[1]*end_unit[1]) > 1e-5
                or abs(axis1[0]*axis2[1] - axis1[1]*axis2[0]) > 1e-5
                or axis1[0]*axis2[0]+axis1[1]*axis2[1] < 1-1e-5):
            continue
        d1 = math.hypot(far1[0]-first[0], far1[1]-first[1])
        d2 = math.hypot(far2[0]-second[0], far2[1]-second[1])
        if abs(d1-d2) > _SOURCE_QUANT_PT:
            continue
        pairs = sorted((ids1, ids2))
        candidates.append(RasterSourceFlankBandCandidate(
            page_id=end.page_id,
            face_parent_chains=tuple(pairs),
            end_parent_id=end.parent_observation_id,
            near_center_pdf_pt=((first[0]+second[0])/2,
                                (first[1]+second[1])/2),
            far_center_pdf_pt=((far1[0]+far2[0])/2,
                               (far1[1]+far2[1])/2),
            original_source_visible_ids=tuple(sorted((
                *visible1, *visible2, end.visible_observation_id,
            ))),
        ))
    # Reversing an END may enumerate the same physical evidence twice.
    unique = {(
        candidate.face_parent_chains, candidate.end_parent_id
    ): candidate for candidate in candidates}
    return tuple(unique[k] for k in sorted(unique))


def reconstruct_raster_source_flank_bands_shadow(
    source: RasterOpeningParentSourceHandoff,
) -> RasterSourceFlankBandResult:
    if type(source) is not RasterOpeningParentSourceHandoff:
        raise TypeError("producer-authenticated parent source handoff required")
    if (source.status != "SOURCE_ONLY_CANDIDATE"
            or source.unresolved_parent_ids or not source.lines
            or not source.shadow_only or source.structural_host_granted):
        return RasterSourceFlankBandResult(
            "ABSTAIN", source.source_sha256, (),
            tuple(source.requested_parent_ids),
            ("original_source_parent_inventory_not_complete",),
        )
    rows = source.lines
    pages = {item.page_id for item in rows}
    ids = [item.parent_observation_id for item in rows]
    visible_ids = [item.visible_observation_id for item in rows]
    if (len(pages) != 1 or len(ids) != len(set(ids))
            or len(visible_ids) != len(set(visible_ids))
            or set(source.requested_parent_ids) != set(ids)
            or any(item.observation_kind not in RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS
                   or item.w4_wall_identity_granted or item.host_binding_granted
                   or item.opening_count_granted for item in rows)):
        return RasterSourceFlankBandResult(
            "ABSTAIN", source.source_sha256, (),
            tuple(sorted(set(ids))),
            ("source_face_end_identity_or_scope_conflict",),
        )
    face_rows = [row for row in rows if row.observation_kind == "raster_wall_band_face"]
    end_rows = [row for row in rows if row.observation_kind == "raster_wall_band_end"]
    proposals = []
    for end in end_rows:
        proposals.extend(_one_end_candidates(end, face_rows))
    # No positive source line may belong to multiple independent flank bands.
    owners = {}
    for candidate in proposals:
        for item_id in (
            *candidate.face_parent_chains[0],
            *candidate.face_parent_chains[1], candidate.end_parent_id,
        ):
            owners.setdefault(item_id, set()).add(candidate.end_parent_id)
    contested = {id for id, owner_ids in owners.items() if len(owner_ids) > 1}
    if contested:
        # Do not silently pick one of two claimants to a source face.
        proposals = [
            row for row in proposals if not
            set((*row.face_parent_chains[0], *row.face_parent_chains[1],
                 row.end_parent_id)).intersection(contested)
        ]
    proposals.sort(key=lambda row: (
        row.page_id, row.end_parent_id, row.face_parent_chains,
    ))
    used = set()
    for row in proposals:
        used.update((*row.face_parent_chains[0], *row.face_parent_chains[1],
                     row.end_parent_id))
    missing = tuple(sorted(set(ids) - used))
    return RasterSourceFlankBandResult(
        "SOURCE_BAND_GEOMETRY_CANDIDATE" if proposals else "ABSTAIN",
        source.source_sha256, tuple(proposals), missing,
        ("source_flank_geometry_only_structural_w4_unproven",)
        if proposals else ("closed_source_wall_band_faces_ends_unavailable",),
    )
