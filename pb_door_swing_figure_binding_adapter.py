"""Input path for the shadow-only door-swing figure binding (default off, authority-free).

* ``read_native_swing_arcs``: quarter-circle arcs from the native cubic Bezier drawings of one page of the SHA-pinned
  original. The visibility producer exposes straight native segments only, so arcs cannot come from its observations; the
  ids returned are native drawing path ids (``native-cubic:p<page>:<path>.<item>``), not visibility observation ids, and
  the caller must say so. A swing here is opaque, dark, stroke-only ink that is a true quarter circle: axis-aligned
  perpendicular tangents, a square bounding box and control points at the quarter-circle distance.
* ``read_figure_words``: figure-like printed words from the text-integrity receipts of one page, each tagged
  ``corroborated``, ``raw_unverified`` or empty. EVERY figure-like receipt counts, whatever its text trust: a figure that
  text integrity does not trust still sits in the swing and must make the binding ambiguous, never be skipped.
* ``opening_ends_from_composition``: the two end points and wall thickness of each plan opening from the live
  composition (same geometry source the elevation diagnostic uses).

Nothing here asserts a role or publishes a width, kind, host, frame or quantity, and nothing in production imports it.
"""
from __future__ import annotations

import hashlib
import math
from typing import Optional

from pb_door_swing_figure_binding_shadow import (
    FIGURE_RE, FigureWord, OpeningEnds, SQUARE_TOL, SwingArc, TEXT_CORROBORATED, TEXT_RAW,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector

KAPPA = 0.5522847498307936     # control-point distance of a cubic quarter circle, in radii
KAPPA_TOL = 0.05               # relative
AXIS_TOL_PT = 0.05             # a tangent is axis-aligned when its off-axis component is below this
DARK_MAX = 0.35                # stroke colour components at most this value
OPAQUE = 0.99


def _approved_raw_reasons() -> frozenset:
    from pb_pdf_text_integrity_authority import TEXT_CLIP_STATE_UNRESOLVED, TEXT_GLYPH_MAPPING_UNVERIFIED
    return frozenset({TEXT_GLYPH_MAPPING_UNVERIFIED, TEXT_CLIP_STATE_UNRESOLVED})


RAW_TEXT_APPROVED_REASONS = _approved_raw_reasons()


def quarter_circle_arc(p0, p1, p2, p3, arc_id: str, receipts: tuple[str, ...] = ()) -> Optional[SwingArc]:
    """The arc for one cubic Bezier, or ``None`` unless it is a true quarter circle. Points are (x, y) pairs."""
    pts = (p0, p1, p2, p3)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for p in pts for v in p):
        return None
    dx, dy = abs(p3[0] - p0[0]), abs(p3[1] - p0[1])
    side = max(dx, dy)
    if side <= 0 or abs(dx - dy) > SQUARE_TOL * side:
        return None
    t0 = (p1[0] - p0[0], p1[1] - p0[1])         # tangent at the start
    t1 = (p2[0] - p3[0], p2[1] - p3[1])         # tangent at the end, pointing back along the curve
    start_axis = abs(t0[0]) <= AXIS_TOL_PT or abs(t0[1]) <= AXIS_TOL_PT
    end_axis = abs(t1[0]) <= AXIS_TOL_PT or abs(t1[1]) <= AXIS_TOL_PT
    perpendicular = (abs(t0[0]) <= AXIS_TOL_PT) != (abs(t1[0]) <= AXIS_TOL_PT)
    if not (start_axis and end_axis and perpendicular):
        return None
    if abs(math.hypot(*t0) - KAPPA * side) > KAPPA_TOL * KAPPA * side or abs(math.hypot(*t1) - KAPPA * side) > KAPPA_TOL * KAPPA * side:
        return None
    mid = ((p0[0] + 3 * p1[0] + 3 * p2[0] + p3[0]) / 8.0, (p0[1] + 3 * p1[1] + 3 * p2[1] + p3[1]) / 8.0)
    return SwingArc(arc_id, p0[0], p0[1], p3[0], p3[1], mid[0], mid[1], receipts)


def _is_swing_ink(drawing) -> bool:
    color = drawing.get("color")
    opacity = drawing.get("stroke_opacity")
    return bool(
        drawing.get("fill") is None and drawing.get("type") == "s"
        and isinstance(color, (tuple, list)) and len(color) == 3 and all(isinstance(c, (int, float)) and 0 <= c <= DARK_MAX for c in color)
        and isinstance(opacity, (int, float)) and opacity >= OPAQUE
    )


def read_native_swing_arcs(pdf_bytes: bytes, *, expected_sha256: str, page_number: int) -> tuple[SwingArc, ...]:
    """Quarter-circle swing arcs of one page (1-based) of the SHA-pinned original; ``ValueError`` on a hash mismatch."""
    if hashlib.sha256(pdf_bytes).hexdigest() != str(expected_sha256).lower():
        raise ValueError("original source SHA-256 mismatch")
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[int(page_number) - 1]
        arcs = []
        for path_index, drawing in enumerate(page.get_drawings()):
            if not _is_swing_ink(drawing):
                continue
            for item_index, item in enumerate(drawing.get("items") or ()):
                if not item or item[0] != "c" or len(item) < 5:
                    continue
                pts = [(float(p.x), float(p.y)) for p in item[1:5]]
                arc_id = f"native-cubic:p{int(page_number)}:{path_index}.{item_index}"
                arc = quarter_circle_arc(*pts, arc_id, (arc_id,))
                if arc is not None:
                    arcs.append(arc)
        return tuple(sorted(arcs, key=lambda a: a.arc_id))
    finally:
        doc.close()


def read_figure_words(source, *, revision_id: str, page_id: str) -> tuple[FigureWord, ...]:
    """Every figure-like word receipt of one page for one exact revision, with its text trust (never skipped)."""
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return ()
    integrity = source.text_integrity_authority()
    out = []
    for observation_id in sorted(published.text_observation_ids):
        resolved = integrity.resolve_text(ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id))
        receipt = resolved.receipt
        if receipt is None or str(receipt.page_id) != str(page_id) or len(receipt.geometry) != 4:
            continue
        if resolved.status is EvidenceResolutionStatus.CORROBORATED and resolved.trusted_text:
            text, trust = str(resolved.trusted_text).strip(), TEXT_CORROBORATED
        else:
            text = str(receipt.raw_text or "").strip()
            reasons = set(receipt.reason_codes or ())
            trust = (TEXT_RAW if (resolved.status is EvidenceResolutionStatus.ABSTAINED and not receipt.trusted
                                  and reasons and reasons <= RAW_TEXT_APPROVED_REASONS) else "")
        if not FIGURE_RE.match(text):
            continue
        x0, y0, x1, y1 = (float(v) for v in receipt.geometry)
        out.append(FigureWord(observation_id, text, x0, y0, x1, y1, trust, (observation_id,)))
    return tuple(out)


def opening_ends_from_composition(comp, poa) -> tuple[OpeningEnds, ...]:
    """End points and wall thickness of every plan opening record of a live composition (same source as the elevation tool)."""
    import pb_opening_host_binding_authority as hb

    out = []
    for trace in comp.opening_bindings:
        selector = comp.binding_selectors.get(trace.opening_identity_id)
        if selector is None:
            continue
        record = poa.prove_existence(ObservationSelector(
            document_id=selector.document_id, revision_id=selector.revision_id, source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id, observation_id=trace.representative_observation_id)).existence_record
        if record is None:
            continue
        geometry = hb._opening_geometry(poa, record)
        if geometry is None:
            continue
        a = (float(geometry.origin[0]), float(geometry.origin[1]))
        b = (a[0] + float(geometry.axis[0]) * float(geometry.length), a[1] + float(geometry.axis[1]) * float(geometry.length))
        out.append(OpeningEnds(str(trace.opening_identity_id), a[0], a[1], b[0], b[1], float(geometry.thickness),
                               (str(trace.representative_observation_id),)))
    return tuple(sorted(out, key=lambda o: o.opening_id))


__all__ = ["opening_ends_from_composition", "quarter_circle_arc", "read_figure_words", "read_native_swing_arcs"]
