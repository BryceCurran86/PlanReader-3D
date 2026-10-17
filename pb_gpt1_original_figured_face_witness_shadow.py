"""Source-native figured dimension endpoint to wall-face candidate binding.

Separate inner and outer wall-face primitives are preserved; geometry never
elects one just because the annotation endpoints happen to touch it. Genuine
authority needs a prior source-owned physical wall and finished-face role.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceFiguredAxis:
    source_dimension_id: str
    figure_value_mm: float
    axis: str
    first_terminal_pdf_pt: tuple[float, float]
    second_terminal_pdf_pt: tuple[float, float]
    terminal_witness_source_ids: tuple[str, ...]
    page_id: str


@dataclass(frozen=True)
class SourceStructuralFaceStroke:
    original_stroke_id: str
    first_pdf_pt: tuple[float, float]
    second_pdf_pt: tuple[float, float]
    classified_physical_wall_id: str
    physical_face_role: str
    source_style_id: str


@dataclass(frozen=True)
class FiguredTerminalFaceBindingShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    terminal_competitor_ids: tuple[tuple[str, ...], tuple[str, ...]]
    uniquely_bound_face_ids: tuple[str, ...]
    original_figure_id: str
    original_face_ids_considered: tuple[str, ...]
    diagnostic_only: bool = True


def _point(v):
    if type(v) not in (tuple, list) or len(v) != 2:
        return None
    if any(type(x) not in (int, float) for x in v):
        return None
    try:
        p = (float(v[0]), float(v[1]))
    except (ValueError, TypeError, OverflowError):
        return None
    return p if all(math.isfinite(x) for x in p) else None


def source_figured_terminal_wall_faces_shadow(
    axis: SourceFiguredAxis,
    original_face_strokes: Sequence[SourceStructuralFaceStroke],
    *,
    native_precision_pt: float = 0.0,
    finished_face_role_required: bool = True,
) -> FiguredTerminalFaceBindingShadow:
    """Preserve all original terminal face claims and require unique role.

    A matched original face must be orthogonal to the figured dimension and
    have exact source-coordinate contact on that terminal. Caller cannot
    choose a 'best' wall, and a PDF image crop cannot replace source IDs.
    """
    def block(reason, rivals=((),())):
        return FiguredTerminalFaceBindingShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,), rivals, (),
            str(getattr(axis, "source_dimension_id", "")), (),
        )
    if type(axis) is not SourceFiguredAxis or type(original_face_strokes) not in (tuple, list):
        return block("source_figured_terminal_inputs_untrusted")
    a, b = _point(axis.first_terminal_pdf_pt), _point(axis.second_terminal_pdf_pt)
    if (
        a is None or b is None or a == b
        or type(axis.source_dimension_id) is not str
        or not axis.source_dimension_id
        or type(axis.page_id) is not str or not axis.page_id
        or axis.axis not in ("horizontal", "vertical")
        or type(axis.figure_value_mm) not in (int, float)
        or not math.isfinite(float(axis.figure_value_mm))
        or axis.figure_value_mm <= 0
        or type(axis.terminal_witness_source_ids) not in (tuple, list)
        or len(axis.terminal_witness_source_ids) < 2
        or len(set(axis.terminal_witness_source_ids)) != len(axis.terminal_witness_source_ids)
        or any(type(v) is not str or not v for v in axis.terminal_witness_source_ids)
        or type(native_precision_pt) not in (float, int)
        or native_precision_pt < 0 or native_precision_pt > 0.1
    ):
        return block("source_figured_terminal_dimension_invalid")
    if axis.axis == "horizontal":
        if abs(a[1]-b[1]) > 1e-8 or a[0] == b[0]:
            return block("source_figured_terminal_axis_conflict")
    elif abs(a[0]-b[0]) > 1e-8 or a[1] == b[1]:
        return block("source_figured_terminal_axis_conflict")

    seen, candidates = set(), [[], []]
    for face in original_face_strokes:
        if type(face) is not SourceStructuralFaceStroke:
            return block("source_figured_original_wall_record_untrusted")
        fa, fb = _point(face.first_pdf_pt), _point(face.second_pdf_pt)
        if (fa is None or fb is None or fa == fb
            or type(face.original_stroke_id) is not str
            or not face.original_stroke_id or face.original_stroke_id in seen
            or type(face.classified_physical_wall_id) is not str
            or not face.classified_physical_wall_id
            or face.physical_face_role not in (
                "finished_inner_face", "structural_outer_face", "unresolved_face"
            )
            or type(face.source_style_id) is not str or not face.source_style_id):
            return block("source_figured_original_wall_record_invalid")
        seen.add(face.original_stroke_id)
        if axis.axis == "horizontal":
            if abs(fa[1]-fb[1]) > 1e-8:
                continue
            endpoint_coord = (fa[0]+fb[0]) / 2
            for i, terminal in enumerate((a,b)):
                if abs(fa[0]-terminal[0]) <= native_precision_pt + 1e-9 and abs(fb[0]-terminal[0]) <= native_precision_pt + 1e-9:
                    candidates[i].append(face.original_stroke_id)
                elif abs(fa[0]-fb[0]) <= native_precision_pt + 1e-9 and abs(fa[0]-terminal[0]) <= native_precision_pt + 1e-9:
                    candidates[i].append(face.original_stroke_id)
        else:
            if abs(fa[0]-fb[0]) > 1e-8:
                continue
            for i, terminal in enumerate((a,b)):
                if abs(fa[1]-fb[1]) <= native_precision_pt + 1e-9 and abs(fa[1]-terminal[1]) <= native_precision_pt + 1e-9:
                    candidates[i].append(face.original_stroke_id)
    rivals = tuple(tuple(sorted(ids)) for ids in candidates)
    if any(not ids for ids in rivals):
        return block("source_figured_terminal_wall_face_unavailable", rivals)
    if any(len(ids) != 1 for ids in rivals):
        return block("source_figured_terminal_competing_wall_faces", rivals)
    selected = [f for f in original_face_strokes
                if f.original_stroke_id in (rivals[0][0],rivals[1][0])]
    if finished_face_role_required and any(
        f.physical_face_role != "finished_inner_face" for f in selected
    ):
        return block("source_figured_terminal_inner_face_unproved", rivals)
    if len(set(f.classified_physical_wall_id for f in selected)) != 2:
        return block("source_figured_terminal_physical_wall_identity_conflict", rivals)
    return FiguredTerminalFaceBindingShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_source_dimensional_terminal_wall_binding_shadow_only",),
        rivals, (rivals[0][0], rivals[1][0]),
        axis.source_dimension_id, tuple(sorted(seen)),
    )
