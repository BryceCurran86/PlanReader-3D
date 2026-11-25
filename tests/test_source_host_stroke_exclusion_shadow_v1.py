"""Unit tests for Item 24: opening host-stroke annotation/rail/cross-layer rejection."""

from __future__ import annotations

import math
from pathlib import Path

from pb_source_host_stroke_exclusion_shadow import (
    ApertureHostCandidateContext,
    SourceMarkerPrimitive,
    SourceTextBox,
    SourceVectorStroke,
    StrokeLineageRef,
    filter_opening_host_wall_strokes_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lineage(page: str = "page_01", vp: str = "vp_main") -> StrokeLineageRef:
    return StrokeLineageRef(
        document_id="doc_01",
        revision_id="rev_01",
        source_sha256="b" * 64,
        page_id=page,
        viewport_id=vp,
    )


def _rot_pt(pt: tuple[float, float], deg: float, tx: float, ty: float) -> tuple[float, float]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return (pt[0] * c - pt[1] * s + tx, pt[0] * s + pt[1] * c + ty)


def _rot_bbox(
    bbox: tuple[float, float, float, float], deg: float, tx: float, ty: float
) -> tuple[float, float, float, float]:
    corners = [
        _rot_pt((bbox[0], bbox[1]), deg, tx, ty),
        _rot_pt((bbox[2], bbox[1]), deg, tx, ty),
        _rot_pt((bbox[2], bbox[3]), deg, tx, ty),
        _rot_pt((bbox[0], bbox[3]), deg, tx, ty),
    ]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def _build_scene(deg: float = 0.0, tx: float = 0.0, ty: float = 0.0):
    lin = _lineage()
    rad = math.radians(deg)
    axis = (math.cos(rad), math.sin(rad))
    ctx = ApertureHostCandidateContext(
        opening_id="open_w01",
        lineage=lin,
        aperture_center=_rot_pt((100.0, 50.0), deg, tx, ty),
        aperture_axis_unit=axis,
        aperture_half_span_pts=20.0,
        wall_thickness_pts=8.0,
        expected_host_layers=("A-WALL-EXTR",),
        structural_wall_min_stroke_pts=0.6,
    )
    strokes = (
        # Genuine host wall face left of opening
        SourceVectorStroke(
            stroke_id="host_wall_left_top",
            p0=_rot_pt((30.0, 46.0), deg, tx, ty),
            p1=_rot_pt((80.0, 46.0), deg, tx, ty),
            stroke_width_pts=1.0,
            layer="A-WALL-EXTR",
            lineage=lin,
        ),
        # Genuine jamb return at right jamb (x=120, y=46..54)
        SourceVectorStroke(
            stroke_id="host_jamb_right",
            p0=_rot_pt((120.0, 46.0), deg, tx, ty),
            p1=_rot_pt((120.0, 54.0), deg, tx, ty),
            stroke_width_pts=0.9,
            layer="A-WALL-EXTR",
            lineage=lin,
        ),
        # Annotation leader angled from opening to callout box (even if mis-layered on A-WALL-EXTR!)
        SourceVectorStroke(
            stroke_id="leader_diag",
            p0=_rot_pt((100.0, 50.0), deg, tx, ty),
            p1=_rot_pt((135.0, 75.0), deg, tx, ty),
            stroke_width_pts=0.7,
            layer="A-WALL-EXTR",
            lineage=lin,
        ),
        # Leader landing shelf connected to leader_diag touching callout text
        SourceVectorStroke(
            stroke_id="leader_shelf",
            p0=_rot_pt((135.0, 75.0), deg, tx, ty),
            p1=_rot_pt((150.0, 75.0), deg, tx, ty),
            stroke_width_pts=0.7,
            layer="A-ANNO-NOTE",
            lineage=lin,
        ),
        # Dimension rail parallel to opening, offset by 24 pts (even if on A-WALL-EXTR!)
        SourceVectorStroke(
            stroke_id="dim_rail_main",
            p0=_rot_pt((80.0, 26.0), deg, tx, ty),
            p1=_rot_pt((120.0, 26.0), deg, tx, ty),
            stroke_width_pts=0.25,
            layer="A-WALL-EXTR",
            lineage=lin,
        ),
        # Dimension extension witness line perpendicular to rail
        SourceVectorStroke(
            stroke_id="dim_ext_left",
            p0=_rot_pt((80.0, 22.0), deg, tx, ty),
            p1=_rot_pt((80.0, 44.0), deg, tx, ty),
            stroke_width_pts=0.25,
            layer="A-WALL-EXTR",
            lineage=lin,
        ),
        # Cross-layer furniture stroke sitting right along the wall face
        SourceVectorStroke(
            stroke_id="furn_counter_edge",
            p0=_rot_pt((40.0, 54.0), deg, tx, ty),
            p1=_rot_pt((78.0, 54.0), deg, tx, ty),
            stroke_width_pts=0.8,
            layer="A-FURN-CASEWORK",
            lineage=lin,
        ),
        # Dashed overhead lintel projection along the opening
        SourceVectorStroke(
            stroke_id="dashed_lintel",
            p0=_rot_pt((80.0, 50.0), deg, tx, ty),
            p1=_rot_pt((120.0, 50.0), deg, tx, ty),
            stroke_width_pts=0.8,
            layer="A-WALL-EXTR",
            lineage=lin,
            dashed=True,
        ),
        # Cross-viewport stroke with identical geometry
        SourceVectorStroke(
            stroke_id="other_viewport_wall",
            p0=_rot_pt((30.0, 46.0), deg, tx, ty),
            p1=_rot_pt((80.0, 46.0), deg, tx, ty),
            stroke_width_pts=1.0,
            layer="A-WALL-EXTR",
            lineage=_lineage(vp="vp_inset_detail"),
        ),
    )
    texts = (
        SourceTextBox(
            text_id="txt_dim_1800",
            text="1800",
            bbox_pdf_pts=_rot_bbox((92.0, 18.0, 108.0, 25.0), deg, tx, ty),
            layer="A-ANNO-DIMS",
            lineage=lin,
        ),
        SourceTextBox(
            text_id="txt_callout_w01",
            text="W01",
            bbox_pdf_pts=_rot_bbox((151.0, 71.0, 165.0, 79.0), deg, tx, ty),
            layer="A-ANNO-NOTE",
            lineage=lin,
        ),
    )
    markers = (
        SourceMarkerPrimitive(
            marker_id="mk_arrow_leader",
            kind="arrow",
            tip_pt=_rot_pt((100.0, 50.0), deg, tx, ty),
            layer="A-ANNO-NOTE",
            lineage=lin,
        ),
        SourceMarkerPrimitive(
            marker_id="mk_tick_left",
            kind="slash",
            tip_pt=_rot_pt((80.0, 26.0), deg, tx, ty),
            layer="A-ANNO-DIMS",
            lineage=lin,
        ),
        SourceMarkerPrimitive(
            marker_id="mk_tick_right",
            kind="slash",
            tip_pt=_rot_pt((120.0, 26.0), deg, tx, ty),
            layer="A-ANNO-DIMS",
            lineage=lin,
        ),
    )
    return ctx, strokes, texts, markers


def test_rejects_leaders_dim_rails_extensions_dashed_and_cross_layer_with_rotation_invariance() -> None:
    baseline_digest = None
    for deg, tx, ty in ((0.0, 0.0, 0.0), (90.0, 310.0, -45.0), (180.0, -120.0, 88.0), (270.0, 42.0, 512.0), (37.0, 15.0, 25.0)):
        ctx, strokes, texts, markers = _build_scene(deg, tx, ty)
        res = filter_opening_host_wall_strokes_shadow(ctx, strokes, text_boxes=texts, markers=markers)
        assert res.accepted_stroke_ids == ("host_jamb_right", "host_wall_left_top")
        assert res.commercial_authority_granted is False
        assert res.shadow_only is True

        by_id = {ev.stroke_id: ev for ev in res.evaluations}
        assert "annotation_leader_stroke_rejected" in by_id["leader_diag"].rejection_reasons
        assert "annotation_leader_stroke_rejected" in by_id["leader_shelf"].rejection_reasons
        assert "non_wall_layer_stroke_rejected" in by_id["leader_shelf"].rejection_reasons
        assert "dimension_rail_stroke_rejected" in by_id["dim_rail_main"].rejection_reasons
        assert "dimension_extension_line_rejected" in by_id["dim_ext_left"].rejection_reasons
        assert "non_wall_layer_stroke_rejected" in by_id["furn_counter_edge"].rejection_reasons
        assert "cross_layer_host_mismatch" in by_id["furn_counter_edge"].rejection_reasons
        assert "dashed_non_host_projection_rejected" in by_id["dashed_lintel"].rejection_reasons
        assert "cross_lineage_or_viewport_stroke_rejected" in by_id["other_viewport_wall"].rejection_reasons

        if baseline_digest is None:
            baseline_digest = res.digest_sha256
        else:
            assert res.digest_sha256 == baseline_digest


def test_shared_source_audit_is_clean() -> None:
    module_path = Path(__file__).resolve().parent.parent / "pb_source_host_stroke_exclusion_shadow.py"
    assert audit_shared_source(module_path.read_text(encoding="utf-8"), filename=module_path.name) == ()
