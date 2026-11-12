"""Unique native jambs and wall-end contact for topology openings.

Ports the original unique-or-abstain rules from
``pb_source_doorway_jamb_authority`` (wall fragments terminate on perpendicular
jambs) and ``pb_hosted_opening_wall_binding`` (both jambs required; never pick
the nearest host). Adapted onto ``NativePage`` segments. Two flanking wall
ends are the two endpoints of one opening, not two competing walls.

This is not a W4 host, finished-face authority, FIRM width or customer row.
"""
from __future__ import annotations

from typing import Any, Sequence

from shapely.geometry import LineString

from .engine import NativePage, NativeSegment
from .hash_chain import _FACE_PT, _along_perp
from .topology_faces import _path_index_from_segment_ref


def _axis(segment: NativeSegment) -> str | None:
    if abs(segment.y1 - segment.y2) <= _FACE_PT and abs(segment.x2 - segment.x1) > _FACE_PT:
        return "horizontal"
    if abs(segment.x1 - segment.x2) <= _FACE_PT and abs(segment.y2 - segment.y1) > _FACE_PT:
        return "vertical"
    return None


def _gap(fill: dict[str, Any]) -> tuple[bool, float, float, float, float] | None:
    interval = fill.get("gap_interval") or []
    band = fill.get("band") or []
    if len(interval) == 2 and len(band) == 2:
        lo, hi = sorted(float(value) for value in interval)
        band_lo, band_hi = sorted(float(value) for value in band)
        if hi - lo <= _FACE_PT or band_hi - band_lo <= _FACE_PT:
            return None
        if "horizontal" in fill:
            return bool(fill["horizontal"]), lo, hi, band_lo, band_hi
        box = fill.get("bbox_pdf_pts") or []
        if len(box) != 4:
            return None
        width, height = abs(float(box[2]) - float(box[0])), abs(float(box[3]) - float(box[1]))
        return width >= height, lo, hi, band_lo, band_hi
    box = fill.get("bbox_pdf_pts") or []
    if len(box) != 4:
        return None
    x0, y0, x1, y1 = (float(value) for value in box)
    width, height = abs(x1 - x0), abs(y1 - y0)
    if width <= _FACE_PT or height <= _FACE_PT:
        return None
    if width >= height:
        return True, min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    return False, min(y0, y1), max(y0, y1), min(x0, x1), max(x0, x1)


def _unique_segment(hits: Sequence[NativeSegment]) -> NativeSegment | None:
    refs = list(dict.fromkeys(item.ref for item in hits))
    if len(refs) != 1:
        return None
    return next(item for item in hits if item.ref == refs[0])


def _inner_outer_pair(
    hits: Sequence[NativeSegment],
    *,
    wall_horizontal: bool,
    band_lo: float,
    band_hi: float,
) -> list[NativeSegment] | None:
    refs = list(dict.fromkeys(item.ref for item in hits))
    if not refs or len(refs) > 2:
        return None
    chosen = [next(item for item in hits if item.ref == ref) for ref in refs]
    perps = []
    for item in chosen:
        _along, perp = _along_perp(wall_horizontal, item.x1, item.y1)
        perps.append(perp)
        if perp < band_lo - _FACE_PT or perp > band_hi + _FACE_PT:
            return None
    if len(chosen) == 2 and abs(perps[0] - perps[1]) <= _FACE_PT:
        return None
    return chosen


def _jamb_cap(
    segments: Sequence[NativeSegment],
    *,
    wall_horizontal: bool,
    station: float,
    band_lo: float,
    band_hi: float,
    paths: set[int] | None,
) -> NativeSegment | None:
    wanted = "vertical" if wall_horizontal else "horizontal"
    hits: list[NativeSegment] = []
    thickness = band_hi - band_lo
    for segment in segments:
        path = _path_index_from_segment_ref(segment.ref)
        if paths is not None and path not in paths:
            continue
        if _axis(segment) != wanted:
            continue
        along1, perp1 = _along_perp(wall_horizontal, segment.x1, segment.y1)
        along2, perp2 = _along_perp(wall_horizontal, segment.x2, segment.y2)
        if abs(along1 - along2) > _FACE_PT or abs(along1 - station) > _FACE_PT:
            continue
        lo, hi = sorted((perp1, perp2))
        if lo - _FACE_PT > band_lo or hi + _FACE_PT < band_hi:
            continue
        if (hi - lo) > thickness + 2.0 * _FACE_PT:
            continue
        hits.append(segment)
    return _unique_segment(hits)


def _wall_ends(
    segments: Sequence[NativeSegment],
    *,
    wall_horizontal: bool,
    station: float,
    band_lo: float,
    band_hi: float,
    paths: set[int],
    toward_lo: bool,
) -> list[NativeSegment] | None:
    wanted = "horizontal" if wall_horizontal else "vertical"
    hits: list[NativeSegment] = []
    for segment in segments:
        path = _path_index_from_segment_ref(segment.ref)
        if path not in paths or _axis(segment) != wanted:
            continue
        along1, perp1 = _along_perp(wall_horizontal, segment.x1, segment.y1)
        along2, perp2 = _along_perp(wall_horizontal, segment.x2, segment.y2)
        if abs(perp1 - perp2) > _FACE_PT:
            continue
        if perp1 < band_lo - _FACE_PT or perp1 > band_hi + _FACE_PT:
            continue
        contact = [
            along for along in (along1, along2) if abs(along - station) <= _FACE_PT
        ]
        if len(contact) != 1:
            continue
        other = along2 if abs(along1 - station) <= _FACE_PT else along1
        if toward_lo:
            if other > station + _FACE_PT:
                continue
        elif other < station - _FACE_PT:
            continue
        hits.append(segment)
    return _inner_outer_pair(
        hits, wall_horizontal=wall_horizontal, band_lo=band_lo, band_hi=band_hi,
    )


def _segment_by_ref(page: NativePage, ref: str) -> NativeSegment | None:
    hits = [item for item in page.segments if item.ref == ref]
    return hits[0] if len(hits) == 1 else None


def native_face_endpoints(page: NativePage, face_segment_ref: str) -> dict[str, Any]:
    """Exact native ink ends of one topology face, or abstain."""
    segment = _segment_by_ref(page, face_segment_ref)
    if segment is None:
        return {
            "face_segment_ref": face_segment_ref,
            "endpoint_a_pdf_pts": None,
            "endpoint_b_pdf_pts": None,
            "endpoint_status": "ABSTAIN",
            "endpoint_reason": "native_face_segment_not_unique",
        }
    return {
        "face_segment_ref": face_segment_ref,
        "endpoint_a_pdf_pts": [segment.x1, segment.y1],
        "endpoint_b_pdf_pts": [segment.x2, segment.y2],
        "endpoint_status": "UNIQUE",
        "endpoint_reason": "native_segment_ends",
    }


def native_face_cut_witnesses(
    page: NativePage,
    faces: Sequence[dict[str, Any]],
    cut_axis_pdf_pts: Sequence[float],
) -> dict[str, Any]:
    """Intersect GPT's source cut axis with native face ink, never a region polygon."""
    if len(cut_axis_pdf_pts) != 4:
        return {
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "witnesses": [],
            "witness_count": 0,
            "reason": "cut_axis_invalid",
            "physical_wall_authenticated": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
            "official_score": None,
        }
    cut = LineString([
        (float(cut_axis_pdf_pts[0]), float(cut_axis_pdf_pts[1])),
        (float(cut_axis_pdf_pts[2]), float(cut_axis_pdf_pts[3])),
    ])
    witnesses: list[dict[str, Any]] = []
    for face in faces:
        ref = face.get("face_segment_ref")
        segment = _segment_by_ref(page, ref) if isinstance(ref, str) else None
        if segment is None:
            continue
        ink = LineString([(segment.x1, segment.y1), (segment.x2, segment.y2)])
        if ink.length <= _FACE_PT or not ink.is_valid:
            continue
        crossing = ink.intersection(cut)
        if crossing.is_empty:
            continue
        geometry = crossing.geom_type
        if geometry == "Point":
            kind, length = "point", 0.0
        elif geometry in {"LineString", "MultiLineString"}:
            kind, length = "span", float(crossing.length)
        else:
            kind, length = "ABSTAIN", None
        witnesses.append({
            "item_id": face.get("item_id"),
            "region_id": face.get("region_id"),
            "face_segment_ref": segment.ref,
            "native_path_index": _path_index_from_segment_ref(segment.ref),
            "cut_intersection_kind": kind,
            "cut_intersection_pdf_pts_not_metric": length,
            "endpoint_a_pdf_pts": [segment.x1, segment.y1],
            "endpoint_b_pdf_pts": [segment.x2, segment.y2],
            "physical_wall_authenticated": False,
            "height_applied_to_room": False,
            "commercial_publishable": False,
        })
    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "witnesses": witnesses,
        "witness_count": len(witnesses),
        "reason": "native_face_ink_vs_source_cut",
        "physical_wall_authenticated": False,
        "height_applied_to_any_room": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def pair_opening_hosts(
    page: NativePage,
    fills: Sequence[dict[str, Any]],
    faces: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Unique jamb pair plus unique wall-end contact, or abstain."""
    pairs: list[dict[str, Any]] = []
    for fill in fills:
        payload = {
            "closure_id": fill["closure_id"],
            "jamb_segment_refs": [],
            "wall_end_segment_refs": [],
            "jamb_hosted_face_item_ids": [],
            "jamb_stations_pdf_pts": [],
            "host_status": "NONE",
            "host_reason": "no_unique_jamb_pair",
            "host_wall_authenticated": False,
            "physical_opening_authenticated": False,
            "commercial_publishable": False,
        }
        gap = _gap(fill)
        wall_paths = {
            int(index) for index in (fill.get("native_wall_path_indices") or [])
            if type(index) is int
        }
        if gap is None or not wall_paths:
            pairs.append(payload)
            continue
        wall_horizontal, lo, hi, band_lo, band_hi = gap
        cap_lo = _jamb_cap(
            page.segments, wall_horizontal=wall_horizontal, station=lo,
            band_lo=band_lo, band_hi=band_hi, paths=None,
        )
        cap_hi = _jamb_cap(
            page.segments, wall_horizontal=wall_horizontal, station=hi,
            band_lo=band_lo, band_hi=band_hi, paths=None,
        )
        if cap_lo is None or cap_hi is None or cap_lo.ref == cap_hi.ref:
            payload["host_status"] = "ABSTAIN" if cap_lo or cap_hi else "NONE"
            payload["host_reason"] = (
                "competing_or_missing_jamb_caps"
                if cap_lo or cap_hi else "no_unique_jamb_pair"
            )
            pairs.append(payload)
            continue
        ends_lo = _wall_ends(
            page.segments, wall_horizontal=wall_horizontal, station=lo,
            band_lo=band_lo, band_hi=band_hi, paths=wall_paths, toward_lo=True,
        )
        ends_hi = _wall_ends(
            page.segments, wall_horizontal=wall_horizontal, station=hi,
            band_lo=band_lo, band_hi=band_hi, paths=wall_paths, toward_lo=False,
        )
        if not ends_lo or not ends_hi:
            payload["host_status"] = "ABSTAIN"
            payload["host_reason"] = "wall_ends_not_unique_at_both_jambs"
            payload["jamb_segment_refs"] = [cap_lo.ref, cap_hi.ref]
            pairs.append(payload)
            continue
        end_refs = list(dict.fromkeys(
            item.ref for item in (*ends_lo, *ends_hi)
        ))
        hosted = [
            face["item_id"]
            for face in faces
            if face.get("face_segment_ref") in end_refs
        ]
        payload["host_status"] = "UNIQUE"
        payload["host_reason"] = "unique_jamb_pair_and_wall_ends"
        payload["jamb_segment_refs"] = [cap_lo.ref, cap_hi.ref]
        payload["wall_end_segment_refs"] = end_refs
        payload["jamb_hosted_face_item_ids"] = hosted
        payload["jamb_stations_pdf_pts"] = [lo, hi]
        pairs.append(payload)
    return pairs
