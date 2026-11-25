"""Unit tests for Item 23: scale lineage audit shadow."""

from __future__ import annotations

from pathlib import Path

from pb_source_scale_lineage_audit_shadow import (
    DimensionChainScaleWitness,
    GraphicScaleBarWitness,
    MM_PER_PT_AT_1_TO_1,
    PrintedScaleNoteWitness,
    ScaleLineageRef,
    audit_viewport_scale_lineage_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lin(vp: str = "vp_plan_100") -> ScaleLineageRef:
    return ScaleLineageRef(
        document_id="doc_01",
        revision_id="rev_01",
        source_sha256="f" * 64,
        page_id="page_01",
        viewport_id=vp,
    )


def test_calibrates_viewport_from_corroborated_dimension_chains_and_scale_bar() -> None:
    lin = _lin()
    # At 1:100, 1000 mm = 1000 / (100 * 25.4/72) = 28.3464567 pts
    pts_per_m = 1000.0 / (100.0 * MM_PER_PT_AT_1_TO_1)
    chains = (
        DimensionChainScaleWitness("ch_x", lin, "x", span_pts=4.0 * pts_per_m, figured_mm=4000.0),
        DimensionChainScaleWitness("ch_y", lin, "y", span_pts=3.2 * pts_per_m, figured_mm=3200.0),
    )
    bar = GraphicScaleBarWitness("bar_1", lin, "block_bar", span_pts=10.0 * pts_per_m, physical_span_mm=10000.0)
    note = PrintedScaleNoteWitness("note_1", lin, "SCALE 1:100 @ A1")

    res = audit_viewport_scale_lineage_shadow(
        lin, dimension_chains=chains, scale_bars=(bar,), printed_notes=(note,)
    )
    assert res.calibrated is True
    assert res.abstained is False
    assert res.ratio_corroborated is True
    assert res.equivalent_ratio is not None and abs(res.equivalent_ratio - 100.0) < 0.05
    assert res.calibration_sources == ("dimension_chain", "graphic_scale_bar")
    assert res.guessed_scale_forbidden is True
    assert res.scale_authority_granted is False
    assert res.commercial_authority_granted is False
    assert res.blocking_reasons == ()


def test_rejects_ratio_only_nts_anisotropy_shrink_print_and_cross_viewport_bleed() -> None:
    lin = _lin()
    pts_per_m_100 = 1000.0 / (100.0 * MM_PER_PT_AT_1_TO_1)

    # 1. Printed ratio alone without geometric proof -> MUST fail closed
    res_ratio_only = audit_viewport_scale_lineage_shadow(
        lin, printed_notes=(PrintedScaleNoteWitness("n1", lin, "SCALE 1:100"),)
    )
    assert res_ratio_only.abstained is True
    assert "ratio_only_without_geometric_proof_rejected" in res_ratio_only.blocking_reasons

    # 2. NTS viewport overrides everything -> MUST fail closed
    bar = GraphicScaleBarWitness("b1", lin, "tick_bar", span_pts=5.0 * pts_per_m_100, physical_span_mm=5000.0)
    res_nts = audit_viewport_scale_lineage_shadow(
        lin,
        scale_bars=(bar,),
        printed_notes=(PrintedScaleNoteWitness("n_nts", lin, "NOT TO SCALE - DIAGRAMMATIC"),),
    )
    assert res_nts.abstained is True
    assert "not_to_scale_viewport_rejected" in res_nts.blocking_reasons

    # 3. Anisotropic X vs Y scale drift (5% stretch in Y) -> MUST fail closed
    res_aniso = audit_viewport_scale_lineage_shadow(
        lin,
        dimension_chains=(
            DimensionChainScaleWitness("cx", lin, "x", span_pts=4.0 * pts_per_m_100, figured_mm=4000.0),
            DimensionChainScaleWitness("cy", lin, "y", span_pts=4.2 * pts_per_m_100, figured_mm=4000.0),
        ),
    )
    assert res_aniso.abstained is True
    assert "anisotropic_axis_scale_drift_rejected" in res_aniso.blocking_reasons

    # 4. Printed 1:100 on an A3-shrunk sheet (actual 1:200 geometry) -> caught & rejected!
    bar_200 = GraphicScaleBarWitness("b200", lin, "tick_bar", span_pts=5.0 * pts_per_m_100 * 0.5, physical_span_mm=5000.0)
    res_shrink = audit_viewport_scale_lineage_shadow(
        lin,
        scale_bars=(bar_200,),
        printed_notes=(PrintedScaleNoteWitness("n100", lin, "SCALE 1:100"),),
    )
    assert res_shrink.abstained is True
    assert "printed_ratio_disagrees_with_geometric_scale" in res_shrink.blocking_reasons

    # 5. Cross-viewport scale bar bleed from 1:50 detail inset -> rejected!
    bar_other_vp = GraphicScaleBarWitness(
        "b_inset", _lin(vp="vp_detail_50"), "tick_bar", span_pts=2.0 * pts_per_m_100 * 2.0, physical_span_mm=2000.0
    )
    res_bleed = audit_viewport_scale_lineage_shadow(lin, scale_bars=(bar, bar_other_vp))
    assert res_bleed.abstained is True
    assert "cross_viewport_scale_bleed_rejected" in res_bleed.blocking_reasons


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_scale_lineage_audit_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
