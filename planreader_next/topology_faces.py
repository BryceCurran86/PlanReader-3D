"""Native finished-face segment refs taken from topology rings.

These receipts are the room polygon's own wall-owned edges mapped onto unique
source-native segments. Doorway closure edges are skipped. A split or
multi-owner edge abstains. This is not a finished-face authority, quantity,
or customer row.
"""
from __future__ import annotations

from typing import Any, Sequence

from .engine import NativePage, NativeSegment
from .hash_chain import _FACE_PT, _along_perp


def _path_index_from_segment_ref(ref: str) -> int | None:
    if not ref.startswith("d"):
        return None
    body = ref[1:]
    path, separator, _rest = body.partition("i")
    if separator != "i" or not path.isdigit():
        return None
    return int(path)


def _path_indices_from_owners(owners: Sequence[str]) -> tuple[int, ...] | None:
    paths: list[int] = []
    for owner in owners:
        if owner.startswith("layered_doorway_closure:"):
            return None
        prefix = "layered_wall_strip:"
        if owner.startswith(prefix) and owner[len(prefix):].isdigit():
            paths.append(int(owner[len(prefix):]))
            continue
        fill = "layered_wall_fill:"
        if owner.startswith(fill) and owner[len(fill):].isdigit():
            paths.append(int(owner[len(fill):]))
            continue
        return None
    if not paths:
        return None
    return tuple(sorted(set(paths)))


def _edge_axis(x0: float, y0: float, x1: float, y1: float) -> str | None:
    if abs(y0 - y1) <= _FACE_PT and abs(x1 - x0) > _FACE_PT:
        return "horizontal"
    if abs(x0 - x1) <= _FACE_PT and abs(y1 - y0) > _FACE_PT:
        return "vertical"
    return None


def _unique_segment_on_edge(
    segments: Sequence[NativeSegment],
    *,
    axis: str,
    lo: float,
    hi: float,
    perp: float,
    path_indices: Sequence[int],
) -> NativeSegment | None:
    wanted = set(path_indices)
    hits: list[tuple[str, NativeSegment]] = []
    for segment in segments:
        if segment.kind not in {"line", "rect_edge"}:
            continue
        path = _path_index_from_segment_ref(segment.ref)
        if path not in wanted:
            continue
        horizontal = axis == "horizontal"
        along1, perp1 = _along_perp(horizontal, segment.x1, segment.y1)
        along2, perp2 = _along_perp(horizontal, segment.x2, segment.y2)
        if abs(perp1 - perp) > _FACE_PT or abs(perp2 - perp) > _FACE_PT:
            continue
        ends = sorted((along1, along2))
        exact = abs(ends[0] - lo) <= _FACE_PT and abs(ends[1] - hi) <= _FACE_PT
        covers = ends[0] - _FACE_PT <= lo and ends[1] + _FACE_PT >= hi
        if exact:
            hits.append(("exact", segment))
        elif covers:
            hits.append(("cover", segment))
    exact_hits = [segment for kind, segment in hits if kind == "exact"]
    if len(exact_hits) == 1:
        return exact_hits[0]
    cover_hits = [segment for kind, segment in hits if kind == "cover"]
    if not exact_hits and len(cover_hits) == 1:
        return cover_hits[0]
    return None


def native_finished_face_receipts(
    page: NativePage, regions: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Unique native wall-face refs for candidate room-ring edges, or abstain."""
    receipts: list[dict[str, str]] = []
    abstained_edges = 0
    for region in regions:
        if region.get("status") != "candidate" or region.get("likely_cavity_pocket"):
            continue
        polygon = region.get("boundary_polygon_pdf_pts") or []
        owners = region.get("edge_owner_ids") or []
        if len(polygon) < 3 or len(owners) != len(polygon):
            continue
        region_id = str(region["region_id"])
        for index, ((x0, y0), (x1, y1), edge_owners) in enumerate(
            zip(polygon, polygon[1:] + polygon[:1], owners)
        ):
            axis = _edge_axis(float(x0), float(y0), float(x1), float(y1))
            paths = _path_indices_from_owners(tuple(edge_owners))
            if axis is None or paths is None:
                if edge_owners and not any(
                    str(owner).startswith("layered_doorway_closure:")
                    for owner in edge_owners
                ):
                    abstained_edges += 1
                continue
            horizontal = axis == "horizontal"
            along0, perp0 = _along_perp(horizontal, float(x0), float(y0))
            along1, perp1 = _along_perp(horizontal, float(x1), float(y1))
            if abs(perp0 - perp1) > _FACE_PT:
                abstained_edges += 1
                continue
            lo, hi = sorted((along0, along1))
            if hi - lo < 8.0:
                continue
            segment = _unique_segment_on_edge(
                page.segments, axis=axis, lo=lo, hi=hi, perp=perp0, path_indices=paths,
            )
            if segment is None:
                abstained_edges += 1
                continue
            receipts.append({
                "item_id": f"{region_id}/edge/{index}",
                "item_kind": "room_finished_face",
                "face_segment_ref": segment.ref,
                "region_id": region_id,
            })
    identity = [(item["item_id"], item["face_segment_ref"]) for item in receipts]
    if len(set(identity)) != len(identity):
        receipts = []
        abstained_edges += 1
    return {
        "item_faces": receipts,
        "receipt_count": len(receipts),
        "abstained_edge_count": abstained_edges,
        "physical_item_authenticated": False,
        "finished_face_authenticated": False,
        "topology_only": True,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
