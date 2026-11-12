"""Shadow association of inventoried printed dimensions to native physical faces.

A figure, a hash interval and a physical face are three different authorities.
This module only suggests a source-supported mapping when all three have exact
native geometry receipts. It never authenticates a finished face, door schedule,
metric floor area, customer row or frozen benchmark item.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence
import math

from .dimension_index import (
    PageDimensionIndex,
    STATUS_UNIQUE,
    inventory_page_dimensions,
)
from .engine import NativePage, NativeSegment, SourceConflict
from .hash_chain import _DIM_OFFSET_MAX_PT, _FACE_PT

_ALLOWED_KINDS = frozenset({
    "room_finished_face", "wall_face", "opening_frame", "ceiling_edge",
})


def _face_axis(segment: NativeSegment) -> str | None:
    dx, dy = segment.x2 - segment.x1, segment.y2 - segment.y1
    if abs(dy) <= _FACE_PT and abs(dx) > _FACE_PT:
        return "horizontal"
    if abs(dx) <= _FACE_PT and abs(dy) > _FACE_PT:
        return "vertical"
    return None


def _face_stations(segment: NativeSegment, axis: str) -> tuple[float, float]:
    return tuple(sorted((segment.x1, segment.x2) if axis == "horizontal"
                        else (segment.y1, segment.y2)))


def _face_perp(segment: NativeSegment, axis: str) -> float:
    return (segment.y1 + segment.y2) / 2 if axis == "horizontal" else (
        segment.x1 + segment.x2
    ) / 2


def _crossing_refs(
    segments: Mapping[str, NativeSegment],
    evidence_refs: tuple[str, ...],
    *,
    axis: str,
    stations: tuple[float, float],
    line_perp: float,
    face_perp: float,
) -> tuple[str, ...] | None:
    """Distinct original ink must bridge BOTH stations and both planes."""
    perp_axis = "vertical" if axis == "horizontal" else "horizontal"
    receipts: list[str] = []
    for station in stations:
        hits = []
        for ref in evidence_refs:
            segment = segments.get(ref)
            if segment is None or _face_axis(segment) != perp_axis:
                continue
            along = _face_perp(segment, perp_axis)
            if abs(along - station) > _FACE_PT:
                continue
            p0, p1 = _face_stations(segment, perp_axis)
            if p0 - _FACE_PT <= min(line_perp, face_perp) and (
                p1 + _FACE_PT >= max(line_perp, face_perp)
            ):
                hits.append(ref)
        if not hits:
            return None
        receipts.append(sorted(set(hits))[0])
    if len(set(receipts)) != 2:
        return None
    return tuple(receipts)


def associate_dimension_inventory_to_native_faces(
    page: NativePage,
    index: PageDimensionIndex,
    item_faces: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Match source-owned figure hash stations to unique exact native face edges.

    Item kinds are hypotheses supplied by the reviewer, NOT an authenticated
    physical classification. Every successful result is still only a shadow
    candidate requiring finished-face, item, schedule and quantity authority.
    """
    if (
        index.source_sha256 != page.source_sha256
        or index.page_index != page.page_index
    ):
        raise SourceConflict("dimension_inventory_source_mismatch")
    if index != inventory_page_dimensions(page):
        raise SourceConflict("dimension_inventory_not_source_owned")
    segments = {seg.ref: seg for seg in page.segments}
    if len(segments) != len(page.segments):
        raise SourceConflict("duplicate_native_segment_identity")

    validated: list[tuple[str, str, NativeSegment]] = []
    for item in item_faces:
        if not isinstance(item, Mapping):
            raise SourceConflict("item_face_candidate_invalid")
        item_id = item.get("item_id")
        kind = item.get("item_kind")
        face_ref = item.get("face_segment_ref")
        if (
            type(item_id) is not str or not item_id.strip() or item_id != item_id.strip()
            or type(kind) is not str or kind not in _ALLOWED_KINDS
            or type(face_ref) is not str or face_ref not in segments
        ):
            raise SourceConflict("item_face_source_receipt_invalid")
        face = segments[face_ref]
        if _face_axis(face) is None or face.kind not in {"line", "rect_edge"}:
            raise SourceConflict("item_face_source_edge_not_axis_aligned")
        validated.append((item_id, kind, face))
    identity = [(item_id, face.ref) for item_id, _, face in validated]
    if len(set(identity)) != len(identity):
        raise SourceConflict("duplicate_item_face_candidate")

    tentative: dict[str, list[dict[str, Any]]] = {}
    for figure in index.unique_geometry():
        if (
            figure.endpoint_stations is None
            or len(figure.dimension_line_refs) != 1
            or len(figure.hash_segment_refs) < 2
            or figure.orientation not in ("horizontal", "vertical")
        ):
            tentative[figure.word_ref] = []
            continue
        source_line = segments.get(figure.dimension_line_refs[0])
        if source_line is None or _face_axis(source_line) != figure.orientation:
            tentative[figure.word_ref] = []
            continue
        matches = []
        stations = tuple(figure.endpoint_stations)
        if len(stations) != 2 or not all(math.isfinite(v) for v in stations):
            tentative[figure.word_ref] = []
            continue
        line_perp = _face_perp(source_line, figure.orientation)
        links = tuple(sorted(set(
            figure.hash_segment_refs + figure.extension_segment_refs
        )))
        for item_id, kind, face in validated:
            if _face_axis(face) != figure.orientation:
                continue
            face_stations = _face_stations(face, figure.orientation)
            if any(abs(left - right) > _FACE_PT
                   for left, right in zip(stations, face_stations)):
                continue
            face_perp = _face_perp(face, figure.orientation)
            offset = abs(face_perp - line_perp)
            if not (_FACE_PT < offset <= _DIM_OFFSET_MAX_PT):
                continue
            receipts = _crossing_refs(
                segments, links, axis=figure.orientation, stations=stations,
                line_perp=line_perp, face_perp=face_perp,
            )
            if receipts is None:
                continue
            matches.append({
                "item_id": item_id,
                "item_kind_claimed": kind,
                "face_segment_ref": face.ref,
                "dimension_word_ref": figure.word_ref,
                "printed_length_mm": format(figure.millimetres.normalize(), "f"),
                "orientation": figure.orientation,
                "dimension_line_ref": source_line.ref,
                "connector_segment_refs": list(receipts),
                "hash_segment_refs": list(figure.hash_segment_refs),
                "endpoint_stations_pdf_pts": list(stations),
                "status": "SOURCE_GEOMETRY_MATCH_REVIEW_REQUIRED",
                "physical_item_authenticated": False,
                "finished_face_authenticated": False,
                "commercial_publishable": False,
                "benchmark_credit": False,
            })
        tentative[figure.word_ref] = matches

    # A dimension with two possible physical owners is ambiguous; equally a
    # proposed physical edge with two competing printed values is ambiguous.
    counts: dict[str, int] = defaultdict(int)
    for matches in tentative.values():
        for match in matches:
            counts[match["face_segment_ref"]] += 1
    bindings = []
    abstentions = []
    for figure in index.unique_geometry():
        candidates = tentative[figure.word_ref]
        if len(candidates) == 1 and counts[candidates[0]["face_segment_ref"]] == 1:
            bindings.append(candidates[0])
        else:
            abstentions.append({
                "dimension_word_ref": figure.word_ref,
                "reason_code": (
                    "physical_face_owner_ambiguous" if len(candidates) > 1
                    else "competing_dimension_for_physical_face" if candidates
                    else "no_source_connected_item_face"
                ),
            })
    return {
        "schema_version": "0.1.0-shadow",
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "unique_geometry_figures": len(index.unique_geometry()),
        "shadow_face_bindings": bindings,
        "abstentions": abstentions,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
