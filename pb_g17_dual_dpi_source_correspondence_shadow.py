"""Producer-bound original 144/300-DPI G17 ink correspondence *shadow*.

Actual source snapshots, G17 producer receipts and ordinary W4 remain unchanged.
The 144-DPI painted stroke and resolution-bounded W4 line alternatives are
necessary evidence only; no geometric overlap is physical equivalence or host.
"""
from __future__ import annotations

from hashlib import sha256
import math

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_RENDER_DPI, RASTER_OPENING_PRIMITIVE_RENDER_DPI,
    SourceVisibilityProducer, _axis_aligned_geometry_fully_covered_by_rect_union,
)

# Both are established producer-owned render resolutions, not fitted distances.
_LATTICE_TOLERANCE_PT = 72.0 / RASTER_RENDER_DPI + 72.0 / RASTER_OPENING_PRIMITIVE_RENDER_DPI


def _axis_line(coords):
    if not isinstance(coords, (tuple, list)) or len(coords) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in coords)
    except (ValueError, TypeError, OverflowError):
        return None
    if not all(map(math.isfinite, (x1, y1, x2, y2))):
        return None
    if y1 == y2 and x1 != x2:
        return ("horizontal", min(x1, x2), max(x1, x2), y1)
    if x1 == x2 and y1 != y2:
        return ("vertical", min(y1, y2), max(y1, y2), x1)
    return None


def _pixel_grid_candidate(a, b):
    """Necessary geometry within two independently sampled original pixel cells.

    This is NOT same-source ancestry, material/structural role or equivalence.
    """
    x, y = _axis_line(a), _axis_line(b)
    if x is None or y is None or x[0] != y[0]:
        return False
    overlap = min(x[2], y[2]) - max(x[1], y[1])
    return (abs(x[3] - y[3]) <= _LATTICE_TOLERANCE_PT
            and overlap > _LATTICE_TOLERANCE_PT)


def _rgb(png):
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("immutable original renderer image unavailable")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _source_144_pixel_profile(image_rgb, full_rgb, geometry):
    """Evaluate complete interior centerline at actual 144-DPI pixel centers.

    No projected coordinates are rounded into physical wall geometry. Black ink
    can belong to annotations or another crossing; even fully solid is NOT a
    provenance or W4 match. Missing/short samples remain explicit UNKNOWN.
    """
    data = _axis_line(geometry)
    if (data is None or image_rgb.ndim != 3 or image_rgb.shape[2] != 3
            or image_rgb.dtype != np.uint8 or full_rgb.shape != image_rgb.shape
            or full_rgb.dtype != np.uint8):
        return {"status": "unsupported_geometry_or_render"}
    axis, lo, hi, cross = data
    scale = RASTER_RENDER_DPI / 72.0
    # Strict interior avoids accidentally borrowing ink at either G17 endpoint.
    start = math.ceil(lo * scale) + 1
    stop = math.floor(hi * scale) - 1
    cross_index = round(cross * scale)
    dim_cross = image_rgb.shape[0 if axis == "horizontal" else 1]
    dim_along = image_rgb.shape[1 if axis == "horizontal" else 0]
    if start > stop or cross_index < 0 or cross_index >= dim_cross or start < 0 or stop >= dim_along:
        return {"status": "no_complete_original_144_pixel_line"}
    along = np.arange(start, stop + 1)
    if axis == "horizontal":
        a = image_rgb[cross_index, along]
        b = full_rgb[cross_index, along]
    else:
        a = image_rgb[along, cross_index]
        b = full_rgb[along, cross_index]
    # Same established 300-DPI wall-source paint mass policy.
    gray = cv2.cvtColor(a.reshape(1, -1, 3), cv2.COLOR_RGB2GRAY)[0]
    source_solid = gray < MASS_THRESHOLD
    equal_rgb = np.all(a == b, axis=1)
    return {
        "status": "evaluated",
        "pixel_sample_count": int(len(along)),
        "source_solid_sample_count": int(np.count_nonzero(source_solid)),
        "unchanged_rgb_sample_count": int(np.count_nonzero(equal_rgb)),
        "original_144_solid_and_unchanged": bool(np.all(source_solid & equal_rgb)),
        "sampled_144_pixel_interval": (int(start), int(stop), int(cross_index)),
    }


def g17_144_300_source_correspondence_shadow(
    source: SourceVisibilityProducer, published, *, page_id: str,
    opening_shadows, ordinary_w4_records,
):
    """Re-authenticate 300-DPI G17 primitive parents and a fresh 144-DPI page.

    Source provider is mandatory. Call only with its own current original
    opening-local shadows. Returns no publishable construction proposition.
    """
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("actual SourceVisibilityProducer required")
    if (source.published_snapshot_for_revision(published.revision.revision_id) != published
            or not isinstance(page_id, str) or not page_id.isdecimal()):
        raise ValueError("stale or foreign original page source")
    args = {k: getattr(published.revision, k) for k in
            ("document_id", "revision_id", "source_sha256")}
    args.update(snapshot_id=published.snapshot.snapshot_id, page_id=page_id)
    original = source._producer._store.source_bytes_by_revision.get(args["revision_id"])
    if not original or sha256(original).hexdigest() != args["source_sha256"]:
        raise ValueError("immutable PDF source bytes not authentic")
    image_png, image_parent, image_frame = source._producer.render_native_page_png(
        **args, dpi=float(RASTER_RENDER_DPI), include_native_frame=True,
        images_only=True)
    full_png, full_parent, full_frame = source._producer.render_native_page_png(
        **args, dpi=float(RASTER_RENDER_DPI), include_native_frame=True)
    if image_parent != full_parent or image_frame != full_frame or image_frame.rotation != 0:
        raise ValueError("original 144-DPI render parent/frame contradiction")
    image, full = _rgb(image_png), _rgb(full_png)
    if image.shape != full.shape:
        raise ValueError("144-DPI original full/image frames differ")
    source_regions = source._producer.native_page_image_regions(**args)
    original_w4 = tuple(ordinary_w4_records)
    # Include all produced original W4 edge facts; no nearest/first election.
    w4_edges = tuple((
        str(w.wall_candidate_id), str(w.physical_identity.candidate_identity_id or ""),
        str(f.edge_id), tuple(f.geometry), tuple(f.source_primitive_ids),
    ) for w in original_w4 for f in w.source_edge_fragments)
    result = []
    seen_openings = set()
    authority = source.authority()
    for shadow in opening_shadows:
        selector = shadow.source_selector
        if (selector.source_sha256 != args["source_sha256"]
                or selector.revision_id != args["revision_id"]
                or selector.document_id != args["document_id"]
                or selector.snapshot_id != args["snapshot_id"]
                or not shadow.physical_opening_id or shadow.physical_opening_id in seen_openings):
            raise ValueError("G17 opening source scope foreign, incomplete or duplicated")
        seen_openings.add(shadow.physical_opening_id)
        if len(shadow.flanks) != 2:
            raise ValueError("incomplete original G17 flank scope")
        flank_rows = []
        for flank in shadow.flanks:
            if not flank.source_ink_supported:
                flank_rows.append({"source_ink_supported": False, "source_edges": [],
                                   "reason": "original_g17_source_ink_not_supported"})
                continue
            observations = {}
            for oid in flank.source_observation_ids:
                r = authority.resolve_raster_opening_primitive(
                    ObservationSelector(
                        document_id=args["document_id"], revision_id=args["revision_id"],
                        source_sha256=args["source_sha256"],
                        snapshot_id=args["snapshot_id"], observation_id=oid))
                o = r.observation
                if (r.status is not EvidenceResolutionStatus.CORROBORATED
                        or o is None or o.page_id != page_id
                        or not o.source_primitive_ref.startswith("visible:raster_opening_primitive:")):
                    raise ValueError("G17 source primitive no longer authenticated")
                raw = o.source_primitive_ref[len("visible:"):]
                if raw in observations:
                    raise ValueError("duplicated G17 raw source primitive")
                observations[raw] = tuple(o.geometry)
            source_edges = {}
            collision_ids = set()
            for w in flank.exact_coordinate_records:
                for f in w.source_edge_fragments:
                    if f.edge_id in source_edges:
                        collision_ids.add(str(f.edge_id))
                    if len(f.source_primitive_ids) != 1:
                        raise ValueError("G17 source edge has competing raw parents")
                    raw = f.source_primitive_ids[0]
                    original_line = observations.get(raw)
                    if (original_line is None
                            or tuple(f.geometry) not in (original_line,
                                (original_line[2], original_line[3],
                                 original_line[0], original_line[1]))):
                        raise ValueError("original G17 W2 source edge not reauthenticated")
                    source_edges[str(f.edge_id)] = (raw, original_line)
            edge_rows = []
            for edge_id, (raw, line) in sorted(source_edges.items()):
                owned = bool(_axis_aligned_geometry_fully_covered_by_rect_union(
                    line, source_regions))
                sampled = (_source_144_pixel_profile(image, full, line) if owned
                           else {"status": "original_raster_tile_ownership_unavailable"})
                matches = [{
                    "wall_candidate_id": wid, "candidate_identity_id": cid,
                    "edge_id": eid, "source_primitive_ids": sorted(pids),
                } for wid, cid, eid, geom, pids in w4_edges if _pixel_grid_candidate(line, geom)]
                matches.sort(key=lambda x:(x["wall_candidate_id"],x["candidate_identity_id"],x["edge_id"]))
                edge_rows.append({
                    "g17_edge_id": edge_id, "g17_300_source_primitive_id": raw,
                    "144_pixel_source_profile": sampled,
                    "within_original_image_region": owned,
                    "144_w4_lattice_candidates": matches,
                    "w4_cross_source_equivalence_proven": False,
                    "structural_wall_role_proven": False,
                })
            flank_rows.append({
                "source_ink_supported": True, "source_edges": edge_rows,
                "duplicate_g17_graph_edge_ids": sorted(collision_ids),
                "reason": ("g17_graph_address_collision" if collision_ids else
                           "cross_detector_physical_equivalence_unproven"),
            })
        result.append({"physical_opening_id": shadow.physical_opening_id,
                       "flanks": flank_rows, "host_granted": False,
                       "metric_quantity_granted": False})
    if source.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise RuntimeError("original source snapshot changed during correspondence")
    return {
        "original_source_sha256": args["source_sha256"],
        "original_144_image_render_sha256": sha256(image_png).hexdigest(),
        "original_144_full_render_sha256": sha256(full_png).hexdigest(),
        "original_144_render_dpi": RASTER_RENDER_DPI,
        "original_g17_render_dpi": RASTER_OPENING_PRIMITIVE_RENDER_DPI,
        "original_w4_candidates_examined": len(original_w4),
        "original_w4_source_fragments_examined": len(w4_edges),
        "openings": result,
        "physical_wall_role_granted": False,
        "cross_source_equivalence_granted": False,
        "host_granted": False, "metric_quantity_granted": False,
        "complete_wall_universe_proven": False,
    }
