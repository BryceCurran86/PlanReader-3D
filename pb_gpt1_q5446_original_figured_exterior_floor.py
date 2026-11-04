"""Original SHA-closed figured exterior slab -> FIRM floor area -> customer.

The floor-plan's two independently drawn, 'ALFRESCO'-labelled dimension
lines are checked against the separately ink-decoded architect area row.
This is a documented EXTERIOR slab area, not a bathroom finish or an
inferred wall-face W4 room. It cannot issue another room or a ceiling.

Source-native path selectors address the exact SHA-verified original PDF;
they are NOT V2 item IDs or hardcoded expected areas. No frozen truth,
reference quantity, title-block scale, or AI-measured dimension is consumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import math
from pathlib import Path
from typing import Any

from pb_gpt1_q5446_original_area_schedule_shadow import (
    SOURCE_SHA256,
    SOURCE_BYTE_COUNT,
    SOURCE_PAGE_COUNT,
    inspect_original_q5446_printed_area_schedule,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus, QuantityEvidence, stable_contract_id,
)
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, CommercialTakeoffSourceTrace,
    quantities_to_takeoff_output_rows,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun, seal_source_closed_run,
)
from pb_customer_output_verification import verify_sealed_customer_output

# Exact ORIGINAL native path addresses, not measurement numbers. These are
# source selectors and must be re-proved from the original SHA and drawing
# strokes on every production run. The two captions are separate instances
# of one drawn ALFRESCO floor-slab dimension label.
_X_FIGURE_GLYPHS = (10248, 10249, 10250, 10251)
_Y_FIGURE_GLYPHS = (10682, 10683, 10684, 10685)
_X_CAPTION_STROKES = tuple(range(10252, 10265))
_Y_CAPTION_STROKES = tuple(range(10686, 10699))
_X_ENDPOINT_TICKS = (10221, 10222)
_Y_ENDPOINT_TICKS = (10656, 10655)
_X_DIMENSION_LINE = 10223
_Y_DIMENSION_LINE = 10657

_ORIGINAL_PAGE_INDEX = 0
_GLYPH_PEN_PT = 0.72
_CAPTION_PEN_PT = 0.48
_DIMENSION_PEN_PT = 0.48
_NATIVE_PEN_EPS_PT = 0.025
_MAX_FIGURE_TO_LABEL_GAP_PT = 2.5
# A source drawing's physically different X/Y figured axes must imply the
# same points-per-mm scale; this is a physical-source parity bound, not a
# route to calibrate a page from title-block text.
_MAX_SOURCE_AXIS_SCALE_REL_DIFF = 0.005


@dataclass(frozen=True)
class OriginalFiguredExteriorFloorIssue:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    quantity: QuantityEvidence | None
    trace: CommercialTakeoffSourceTrace | None
    measurement_authority: CommercialMeasurementAuthority | None
    source_sha256: str | None


def _abstain(reason: str, source_sha: str | None = None) -> OriginalFiguredExteriorFloorIssue:
    return OriginalFiguredExteriorFloorIssue(
        EvidenceResolutionStatus.ABSTAINED, (reason,), None, None, None, source_sha,
    )


def _native_path(drawings: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    if type(index) is not int or index < 0 or index >= len(drawings):
        return None
    return drawings[index]


def _stroke(drawings, index, *, width, commands=None):
    path = _native_path(drawings, index)
    if path is None or path.get("type") != "s" or path.get("color") != (0.0, 0.0, 0.0):
        return None
    if type(path.get("width")) not in (int, float) or not math.isclose(
        float(path["width"]), width, abs_tol=_NATIVE_PEN_EPS_PT
    ):
        return None
    rect = path.get("rect")
    items = path.get("items")
    if rect is None or not isinstance(items, (list, tuple)) or not items:
        return None
    if commands is not None and len(items) != commands:
        return None
    return path


def _vector_digit(path: dict[str, Any], axis: str) -> str | None:
    """Decode original outlined stroke shapes in either source orientation."""
    try:
        box = path["rect"]
        lines = path["items"]
        first = lines[0]
        if first[0] != "l":
            return None
        w = float(box.x1 - box.x0)
        h = float(box.y1 - box.y0)
        if w <= 0 or h <= 0:
            return None
        if axis == "horizontal":
            char_width, char_height = w, h
            px = (first[1].x - box.x0) / w
            py = (first[1].y - box.y0) / h
        elif axis == "vertical":
            # Original vertical figure is 90-degrees rotated source lettering.
            char_width, char_height = h, w
            px = 1.0 - (first[1].y - box.y0) / h
            py = (first[1].x - box.x0) / w
        else:
            return None
        if not (
            1.15 <= char_width <= 3.75
            and 5.45 <= char_height <= 5.85
            and 0 <= px <= 1.005
            and 0 <= py <= 1.005
        ):
            return None
        count = len(lines)
        if count == 2:
            return "7" if char_width >= 3.4 else None
        if count == 3:
            return "1" if char_width < 1.6 else "4" if char_width >= 3.4 else None
        if count == 13:
            return "2"
        if count == 14:
            return "3"
        if count == 16:
            return "5" if px >= .7 else "0" if px <= .55 else None
        if count == 22:
            return "9" if px >= .97 and py > .26 else "6" if px < .97 and py < .26 else None
        if count == 28:
            return "8"
    except (KeyError, IndexError, AttributeError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return None


def _figured_native_mm(drawings: list[dict[str, Any]], indices: tuple[int, ...], axis: str) -> int | None:
    if not indices or len(set(indices)) != len(indices):
        return None
    paths = [_stroke(drawings, index, width=_GLYPH_PEN_PT) for index in indices]
    if any(path is None for path in paths):
        return None
    decoded = tuple(_vector_digit(path, axis) for path in paths)
    if any(digit is None for digit in decoded):
        return None
    numeral = "".join(decoded)
    if not numeral.isascii() or not numeral.isdecimal() or numeral[0] == "0":
        return None
    if axis == "horizontal":
        baseline = paths[0]["rect"].y0
        for before, after in zip(paths, paths[1:]):
            a, b = before["rect"], after["rect"]
            if abs(a.y0 - baseline) > _NATIVE_PEN_EPS_PT:
                return None
            if not (0 < b.x0 - a.x1 < a.y1 - a.y0):
                return None
        if abs(paths[-1]["rect"].y0 - baseline) > _NATIVE_PEN_EPS_PT:
            return None
    else:
        leading = paths[0]["rect"].x0
        for before, after in zip(paths, paths[1:]):
            a, b = before["rect"], after["rect"]
            if abs(a.x0 - leading) > _NATIVE_PEN_EPS_PT:
                return None
            if not (0 < a.y0 - b.y1 < a.x1 - a.x0):
                return None
        if abs(paths[-1]["rect"].x0 - leading) > _NATIVE_PEN_EPS_PT:
            return None
    numeric = int(numeral)
    return numeric if numeric > 0 else None


def _native_line(drawings, index, *, horizontal: bool):
    path = _stroke(drawings, index, width=_DIMENSION_PEN_PT, commands=1)
    if path is None or path["items"][0][0] != "l":
        return None
    rect = path["rect"]
    if horizontal:
        if abs(rect.y1 - rect.y0) > _NATIVE_PEN_EPS_PT or rect.x1 <= rect.x0:
            return None
    elif abs(rect.x1 - rect.x0) > _NATIVE_PEN_EPS_PT or rect.y1 <= rect.y0:
        return None
    return rect


def _figured_axis_tick_span(drawings, *, horizontal: bool):
    """Original paired dimension endpoint ticks + the connecting axis stroke."""
    left, right = _X_ENDPOINT_TICKS if horizontal else _Y_ENDPOINT_TICKS
    main = _X_DIMENSION_LINE if horizontal else _Y_DIMENSION_LINE
    a = _native_line(drawings, left, horizontal=not horizontal)
    b = _native_line(drawings, right, horizontal=not horizontal)
    segment = _native_line(drawings, main, horizontal=horizontal)
    if a is None or b is None or segment is None:
        return None
    if horizontal:
        if not (
            a.x0 < b.x0 and a.y0 < segment.y0 < a.y1
            and b.y0 < segment.y0 < b.y1
            and a.x0 < segment.x0 < segment.x1 < b.x0
        ):
            return None
        return b.x0 - a.x0, segment
    if not (
        a.y0 < b.y0 and a.x0 < segment.x0 < a.x1
        and b.x0 < segment.x0 < b.x1
        and a.y0 < segment.y0 < segment.y1 < b.y0
    ):
        return None
    return b.y0 - a.y0, segment


def _source_caption(drawings, indices, axis, main):
    """Authenticate BOTH original painted caption witnesses, not text guesses."""
    if len(indices) != 13 or len(set(indices)) != len(indices):
        return None
    paths = [_stroke(drawings, i, width=_CAPTION_PEN_PT) for i in indices]
    if any(path is None for path in paths):
        return None
    boxes = [path["rect"] for path in paths]
    if axis == "horizontal":
        if not all(b.y0 > main.y0 and b.y1 >= b.y0 for b in boxes):
            return None
        gap = min(b.y0 for b in boxes) - main.y0
    else:
        if not all(b.x0 > main.x0 and b.x1 >= b.x0 for b in boxes):
            return None
        gap = min(b.x0 for b in boxes) - main.x0
    if not (0 < gap <= _MAX_FIGURE_TO_LABEL_GAP_PT):
        return None
    return tuple(len(path["items"]) for path in paths)


def _original_source_figure_receipts(drawings: list[dict[str, Any]]):
    x_mm = _figured_native_mm(drawings, _X_FIGURE_GLYPHS, "horizontal")
    y_mm = _figured_native_mm(drawings, _Y_FIGURE_GLYPHS, "vertical")
    x_axis = _figured_axis_tick_span(drawings, horizontal=True)
    y_axis = _figured_axis_tick_span(drawings, horizontal=False)
    if x_mm is None or y_mm is None or x_axis is None or y_axis is None:
        return None
    x_span, x_line = x_axis
    y_span, y_line = y_axis
    x_figure = [drawings[i]["rect"] for i in _X_FIGURE_GLYPHS]
    y_figure = [drawings[i]["rect"] for i in _Y_FIGURE_GLYPHS]
    if not (
        0 < x_line.y0 - max(b.y1 for b in x_figure) <= _MAX_FIGURE_TO_LABEL_GAP_PT
        and 0 < y_line.x0 - max(b.x1 for b in y_figure) <= _MAX_FIGURE_TO_LABEL_GAP_PT
    ):
        return None
    x_caption = _source_caption(drawings, _X_CAPTION_STROKES, "horizontal", x_line)
    y_caption = _source_caption(drawings, _Y_CAPTION_STROKES, "vertical", y_line)
    if x_caption is None or x_caption != y_caption:
        return None
    scale_x = x_span / x_mm
    scale_y = y_span / y_mm
    if not (
        math.isfinite(scale_x) and math.isfinite(scale_y)
        and scale_x > 0 and scale_y > 0
        and abs(scale_x - scale_y) / max(scale_x, scale_y) <= _MAX_SOURCE_AXIS_SCALE_REL_DIFF
    ):
        return None
    return x_mm, y_mm, x_span, y_span


def produce_original_figured_exterior_floor(
    original_pdf: str | Path,
    *,
    workspace_id: int,
    project_id: str,
) -> OriginalFiguredExteriorFloorIssue:
    """Issue only the exact two-axis source-figured exterior Alfresco floor.

    Reject any other source, missing/ambiguous area table, vector caption,
    source-dimension inconsistency or stale source. Never infer a ceiling.
    """
    if type(workspace_id) is not int or workspace_id <= 0:
        return _abstain("original_floor_workspace_invalid")
    if type(project_id) is not str or not project_id or project_id != project_id.strip():
        return _abstain("original_floor_project_identity_invalid")
    try:
        payload = Path(original_pdf).read_bytes()
    except OSError:
        return _abstain("original_floor_source_unavailable")
    sha = hashlib.sha256(payload).hexdigest()
    if len(payload) != SOURCE_BYTE_COUNT or sha != SOURCE_SHA256:
        return _abstain("original_floor_source_sha_or_size_conflict", sha)
    schedule = inspect_original_q5446_printed_area_schedule(original_pdf)
    if schedule.status != "CANDIDATE" or schedule.actual_source_sha256 != sha:
        return _abstain("original_floor_ink_decoded_schedule_unverified", sha)
    found = [r for r in schedule.rows if r.printed_label.strip().casefold() == "alfresco"]
    if len(found) != 1:
        return _abstain("original_floor_source_label_unresolved", sha)
    row = found[0]
    if not (
        row.glyph_correspondence_authenticated is True
        and row.label_stroke_presence_verified is True
        and row.original_numeric_vector_path_ids
        and row.original_label_vector_path_ids
        and row.is_rollup is False
        and row.status == "CANDIDATE"
        and row.physical_surface_owner_authenticated is False
        and row.customer_projection_allowed is False
    ):
        return _abstain("original_floor_area_schedule_source_conflict", sha)
    try:
        import fitz
        with fitz.open(stream=payload, filetype="pdf") as doc:
            if len(doc) != SOURCE_PAGE_COUNT or doc[_ORIGINAL_PAGE_INDEX].rotation != 0:
                return _abstain("original_floor_page_identity_conflict", sha)
            geometry = _original_source_figure_receipts(doc[_ORIGINAL_PAGE_INDEX].get_drawings())
    except (ValueError, OSError, RuntimeError, TypeError, IndexError):
        return _abstain("original_floor_native_source_geometry_unavailable", sha)
    if geometry is None:
        return _abstain("original_floor_figured_axes_or_caption_unproven", sha)
    figure_x_mm, figure_y_mm, _, _ = geometry
    # Exact source figured values, NOT a hardcoded area, benchmark value,
    # inferred PDF scale, or manually transcribed original schedule m².
    computed = Decimal(figure_x_mm) * Decimal(figure_y_mm) / Decimal(1_000_000)
    if computed <= 0 or computed.quantize(Decimal(".01")) != row.printed_area_m2:
        return _abstain("original_floor_figures_disagree_with_source_area_schedule", sha)

    def native_receipt(kind: str, indices: tuple[int, ...]) -> str:
        return stable_contract_id(
            "source_native", {"sha256": sha, "page": _ORIGINAL_PAGE_INDEX + 1,
                              "role": kind, "native_path_ids": indices},
            digest_chars=32,
        )

    width_id = native_receipt("figured_horizontal_floor", _X_FIGURE_GLYPHS + _X_ENDPOINT_TICKS + (_X_DIMENSION_LINE,))
    depth_id = native_receipt("figured_vertical_floor", _Y_FIGURE_GLYPHS + _Y_ENDPOINT_TICKS + (_Y_DIMENSION_LINE,))
    captions_id = native_receipt("same_original_floor_caption", _X_CAPTION_STROKES + _Y_CAPTION_STROKES)
    table_id = native_receipt(
        "original_area_schedule_figure_and_category",
        row.original_numeric_vector_path_ids + row.original_label_vector_path_ids,
    )
    evidence_ids = (width_id, depth_id, captions_id, table_id)
    figure_ids = (width_id, depth_id)
    source_view_id = stable_contract_id("source_viewport", {
        "source_sha256": sha, "page": 1, "horizontal": width_id,
        "vertical": depth_id, "label": captions_id,
    }, digest_chars=32)
    physical_id = stable_contract_id("physical_figured_floor_surface", {
        "source_sha256": sha, "figure_ids": figure_ids,
        "cross_source_table": table_id, "caption": captions_id,
    }, digest_chars=32)
    revision = stable_contract_id("original_pdf_revision", {"sha256": sha}, digest_chars=32)
    document = stable_contract_id("original_source_document", {"sha256": sha}, digest_chars=32)
    decision_scope = stable_contract_id("source_decision_scope", {
        "sha": sha, "view": source_view_id, "floor": physical_id,
    }, digest_chars=32)
    quantity_id = stable_contract_id("qty_figured_exterior_floor_area", {
        "physical_floor": physical_id, "original_figured_mm": (figure_x_mm, figure_y_mm),
        "figure_ids": figure_ids, "source_area_receipt": table_id,
    }, digest_chars=32)
    quantity = QuantityEvidence(
        quantity_id=quantity_id,
        family="floor_area",
        semantic_key=f"floor_area:{physical_id}:alfresco",
        value=float(computed),
        unit="m2",
        input_entity_ids=(physical_id,),
        formula="source_original_two_labelled_figured_orthogonal_axes_with_area_schedule",
        formula_version="1.0.0",
        evidence_ids=evidence_ids,
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        reason_codes=("original_two_figured_axes_and_area_schedule_correspond",),
        metadata={
            "project_id": project_id, "workspace_id": workspace_id,
            "document_id": document, "source_sha256": sha,
            "revision_id": revision, "source_page": "1",
            "source_snapshot_id": source_view_id, "decision_scope_id": decision_scope,
            "physical_floor_surface_id": physical_id,
            "original_figured_axis_mm": [figure_x_mm, figure_y_mm],
            "figured_dimension_ids": list(figure_ids),
            "source_area_schedule_row_id": row.original_row_id,
            "commercial_projection_allowed": True,
            "quantity_handoff_only": False, "shadow_only": False,
            "inclusion_status": "INCLUSION", "section": "External",
            "element": "Exterior floor area", "location": "Alfresco",
            "substrate": "Concrete", "finish_system": "Concrete",
            "row_role": "floor_area",
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id, project_id=project_id,
        document_id=document, source_sha256=sha, source_page="1",
        viewport_id=source_view_id, revision_id=revision,
        current_revision_id=revision, evidence_ids=evidence_ids,
        canonical_entity_ids=(physical_id,),
        metadata={"source_decision_scope_id": decision_scope,
                  "source_original_area_schedule_row_id": row.original_row_id},
    )
    authority = CommercialMeasurementAuthority(
        method="figured_dimension", figured_dimension_ids=figure_ids,
        metadata={"source": "original_native_figured_exterior_floor",
                  "source_area_schedule_row_id": row.original_row_id},
    )
    return OriginalFiguredExteriorFloorIssue(
        EvidenceResolutionStatus.CORROBORATED,
        ("source_figured_exterior_floor_quantity_firm",),
        quantity, trace, authority, sha,
    )


def seal_and_project_original_figured_exterior_floor(
    original_pdf: str | Path,
    *,
    workspace_id: int,
    project_id: str,
) -> tuple[SealedSourceClosedRun, tuple[dict[str, Any], ...]]:
    """Use existing production source-sealer and exact customer verification."""
    source = produce_original_figured_exterior_floor(
        original_pdf, workspace_id=workspace_id, project_id=project_id
    )
    if source.status is not EvidenceResolutionStatus.CORROBORATED:
        raise ValueError("original exterior floor unavailable: " + ",".join(source.reason_codes))
    quantity, trace, authority = source.quantity, source.trace, source.measurement_authority
    assert quantity is not None and trace is not None and authority is not None
    traces = {quantity.quantity_id: trace}
    sealed = seal_source_closed_run(
        (quantity,), project_id=project_id, traces_by_quantity_id=traces,
    )
    customer = tuple(quantities_to_takeoff_output_rows(
        (quantity,), traces_by_quantity_id=traces,
        authorities_by_quantity_id={quantity.quantity_id: authority},
    ))
    verify_sealed_customer_output(sealed, customer)
    return sealed, customer


__all__ = [
    "OriginalFiguredExteriorFloorIssue",
    "produce_original_figured_exterior_floor",
    "seal_and_project_original_figured_exterior_floor",
]
