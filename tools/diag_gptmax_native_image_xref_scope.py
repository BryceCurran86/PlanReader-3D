"""Source-only native image XObject registration of original G17/W4 line candidates.

A shared image placement and native pixel interval are only necessary
registration observations. They do NOT establish source primitive ancestry,
physical wall identity, structural role, host, frame, or quantity.
Caller-owned edge IDs and geometry are diagnostics, NOT an authority grant.
"""
from __future__ import annotations

from hashlib import sha256
import math
from collections.abc import Mapping, Sequence

import fitz

from pb_g17_dual_dpi_source_correspondence_shadow import _pixel_grid_candidate


def _line(value: object):
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in value):
        return None
    x0, y0, x1, y1 = (float(x) for x in value)
    if y0 == y1 and x0 != x1:
        return "horizontal", (x0, y0, x1, y1)
    if x0 == x1 and y0 != y1:
        return "vertical", (x0, y0, x1, y1)
    return None


def _placement(row: Mapping[str, object]):
    """Strictly reject transforms without a trustworthy native pixel lattice."""
    try:
        xref, width, height = (row[x] for x in ("xref", "width", "height"))
        box = tuple(float(x) for x in row["bbox"])
        a, b, c, d, e, f = (float(x) for x in row["transform"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if (any(type(v) is not int or v <= 0 for v in (xref, width, height))
            or len(box) != 4
            or not all(math.isfinite(x) for x in (*box, a, b, c, d, e, f))
            or a <= 0 or d <= 0 or abs(b) > 1e-6 or abs(c) > 1e-6
            or box[2] <= box[0] or box[3] <= box[1]
            or not math.isclose(a, box[2]-box[0], rel_tol=0, abs_tol=1e-3)
            or not math.isclose(d, box[3]-box[1], rel_tol=0, abs_tol=1e-3)
            or not math.isclose(e, box[0], rel_tol=0, abs_tol=1e-3)
            or not math.isclose(f, box[1], rel_tol=0, abs_tol=1e-3)):
        return None
    return {"xref": xref, "bbox": box, "width": width, "height": height,
            "pixel_scales_pt": (a/width, d/height)}


def _inside(line, placement) -> bool:
    _, coords = line
    x0, y0, x1, y1 = coords
    a, b, c, d = placement["bbox"]
    # Strict coordinate inclusion is an exact native image ownership test,
    # not a page-wide image-union test or nearest/first placement election.
    return all((a <= x <= c and b <= y <= d) for x, y in ((x0, y0), (x1, y1)))


def _pixel_span(line, p):
    orientation, (x0, y0, x1, y1) = line
    a, b, _, _ = p["bbox"]
    sx, sy = p["pixel_scales_pt"]
    if orientation == "horizontal":
        return (min((x0-a)/sx, (x1-a)/sx),
                max((x0-a)/sx, (x1-a)/sx), (y0-b)/sy)
    return (min((y0-b)/sy, (y1-b)/sy),
            max((y0-b)/sy, (y1-b)/sy), (x0-a)/sx)


def _rows(rows: Sequence[Mapping[str, object]]):
    if not isinstance(rows, (tuple, list)):
        raise TypeError("source edge inventory must be a complete sequence supplied by the caller")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid source edge record")
        edge_id = row.get("edge_id")
        line = _line(row.get("geometry_pdf_pts"))
        if type(edge_id) is not str or not edge_id or edge_id in seen or line is None:
            raise ValueError("invalid, duplicated or non-axis original source edge")
        seen.add(edge_id)
        result.append((edge_id, line))
    return tuple(sorted(result))


def native_g17_w4_pixel_registration_shadow(
    original_pdf: bytes, *, expected_sha256: str, page_id: str,
    g17_edges: Sequence[Mapping[str, object]],
    w4_edges: Sequence[Mapping[str, object]],
) -> dict:
    """Re-read original XObjects for every candidate, retaining all competitors.

    Authenticates source PDF BYTES but not the caller's G17/W4 edge claims.
    A later producer must independently prove both edge families, the complete
    candidate universe, their source parents and structural wall equivalence.
    """
    if (type(original_pdf) is not bytes or not original_pdf
            or type(expected_sha256) is not str
            or sha256(original_pdf).hexdigest() != expected_sha256
            or type(page_id) is not str or not page_id.isdecimal()):
        raise ValueError("original immutable source SHA/page required")
    source = _rows(g17_edges)
    ordinary = _rows(w4_edges)
    with fitz.open(stream=original_pdf, filetype="pdf") as document:
        n = int(page_id)
        if n < 1 or n > len(document):
            raise ValueError("original page out of range")
        page = document[n-1]
        if page.rotation != 0:
            raise ValueError("rotated native PDF page has no supported registration")
        raw = tuple(page.get_image_info(xrefs=True))
    placements = tuple(sorted(
        (p for item in raw if (p := _placement(item)) is not None),
        key=lambda x: (x["bbox"], x["xref"], x["width"], x["height"]),
    ))

    def owner(line):
        matches = tuple(p for p in placements if _inside(line, p))
        # An overlapping/tiled image may not borrow its neighbour's pixels.
        return matches[0] if len(matches) == 1 else None, len(matches)

    w4 = tuple((edge_id, line, *owner(line)) for edge_id, line in ordinary)
    results = []
    for edge_id, line in source:
        own, n_owners = owner(line)
        candidates = []
        foreign = []
        if own is not None:
            for other_id, other_line, other_own, other_owners in w4:
                if not _pixel_grid_candidate(line[1], other_line[1]):
                    continue
                if other_own is None:
                    foreign.append({"w4_edge_id": other_id,
                                    "reason": "w4_native_image_ownership_ambiguous_or_missing"})
                    continue
                if (own["xref"], own["bbox"], own["width"], own["height"]) != (
                        other_own["xref"], other_own["bbox"],
                        other_own["width"], other_own["height"]):
                    foreign.append({"w4_edge_id": other_id,
                                    "reason": "different_original_image_placement_or_pixel_grid"})
                    continue
                a, b = _pixel_span(line, own), _pixel_span(other_line, own)
                if min(a[1], b[1]) - max(a[0], b[0]) <= 0:
                    continue
                candidates.append({
                    "w4_edge_id": other_id,
                    "original_image_xref": own["xref"],
                    "native_g17_pixel_span": list(a),
                    "native_w4_pixel_span": list(b),
                    "native_cross_pixel_separation": abs(a[2]-b[2]),
                    "source_parent_equivalence_proven": False,
                    "structural_wall_role_proven": False,
                })
        results.append({
            "g17_edge_id": edge_id,
            "source_image_placement_count": n_owners,
            "source_native_image_xref": own["xref"] if own else None,
            "original_pixel_placement_unique": own is not None,
            "same_image_pixel_lattice_candidates": sorted(
                candidates, key=lambda x: x["w4_edge_id"]),
            "foreign_image_or_ambiguous_lattice_candidates": sorted(
                foreign, key=lambda x: x["w4_edge_id"]),
            "first_blocker": (
                "original_g17_single_image_placement_unproven" if own is None
                else "source_parent_and_structural_w4_equivalence_unproven"
            ),
            "host_binding_granted": False,
        })
    return {
        "status": "native_image_registration_shadow",
        "source_sha256": expected_sha256, "page_id": page_id,
        "source_image_placements_examined": len(placements),
        "g17_edges": results,
        "w4_edges_examined": len(ordinary),
        "caller_edge_authority_verified": False,
        "complete_w4_universe_proven": False,
        "source_parent_equivalence_granted": False,
        "physical_wall_equivalence_granted": False,
        "opening_host_granted": False,
        "opening_frame_granted": False,
        "firm_opening_area_granted": False,
        "opening_count_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }
