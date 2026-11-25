"""Unit tests for Item 22: unmarked opening native figure-line witness shadow."""

from __future__ import annotations

import math
from pathlib import Path

from pb_source_unmarked_opening_figure_witness_shadow import (
    FigureLineageRef,
    NativeVectorSegment,
    TrustedFigureText,
    UnmarkedOpeningTarget,
    prove_unmarked_opening_figure_witness_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lin(vp: str = "vp_plan") -> FigureLineageRef:
    return FigureLineageRef(
        document_id="doc_01",
        revision_id="rev_01",
        source_sha256="e" * 64,
        page_id="page_02",
        viewport_id=vp,
    )


def _rot(pt: tuple[float, float], deg: float, tx: float, ty: float) -> tuple[float, float]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return (pt[0] * c - pt[1] * s + tx, pt[0] * s + pt[1] * c + ty)


def test_proves_unmarked_opening_from_native_figure_line_with_rotation_invariance() -> None:
    baseline_digest = None
    for deg, tx, ty in ((0.0, 0.0, 0.0), (90.0, 80.0, 40.0), (180.0, -30.0, 100.0), (270.0, 12.0, -55.0), (41.0, 7.0, 9.0)):
        lin = _lin()
        target = UnmarkedOpeningTarget(
            opening_id="unmarked_open_01",
            lineage=lin,
            jamb_a_pt=_rot((80.0, 50.0), deg, tx, ty),
            jamb_b_pt=_rot((120.0, 50.0), deg, tx, ty),
        )
        segs = (
            # Dimension rail spanning exactly jamb_a -> jamb_b at y=25
            NativeVectorSegment("rail_01", _rot((80.0, 25.0), deg, tx, ty), _rot((120.0, 25.0), deg, tx, ty), lin),
            # Dual perpendicular witness lines connecting rail endpoints to jambs
            NativeVectorSegment("wit_a", _rot((80.0, 22.0), deg, tx, ty), _rot((80.0, 50.0), deg, tx, ty), lin),
            NativeVectorSegment("wit_b", _rot((120.0, 22.0), deg, tx, ty), _rot((120.0, 50.0), deg, tx, ty), lin),
            # Overall wall chain rail spanning x=10..200 (must be ignored/rejected, not steal witness)
            NativeVectorSegment("rail_overall_wall", _rot((10.0, 10.0), deg, tx, ty), _rot((200.0, 10.0), deg, tx, ty), lin),
        )
        texts = (
            TrustedFigureText("txt_920", "920", _rot((100.0, 20.0), deg, tx, ty), lin),
            TrustedFigureText("txt_overall", "4500", _rot((100.0, 5.0), deg, tx, ty), lin),
        )
        res = prove_unmarked_opening_figure_witness_shadow(target, segs, texts)
        assert res.proven is True
        assert res.abstained is False
        assert res.value_mm == 920.0
        assert res.rail_segment_id == "rail_01"
        assert res.witness_segment_ids == ("wit_a", "wit_b")
        assert res.text_observation_id == "txt_920"
        assert res.gap_scale_conversion_forbidden is True
        assert res.commercial_authority_granted is False
        if baseline_digest is None:
            baseline_digest = res.digest_sha256
        else:
            assert res.digest_sha256 == baseline_digest


def test_abstains_on_proximity_only_overall_chain_ambiguous_text_and_conflicting_rails() -> None:
    lin = _lin()
    target = UnmarkedOpeningTarget("unmarked_open_02", lin, (80.0, 50.0), (120.0, 50.0))

    # 1. Floating proximity-only text with no rails -> forbidden
    res_prox = prove_unmarked_opening_figure_witness_shadow(
        target, (), (TrustedFigureText("txt_float", "870", (100.0, 42.0), lin),)
    )
    assert res_prox.abstained is True
    assert "proximity_only_dimension_forbidden" in res_prox.blocking_reasons

    # 2. Overall wall chain rail only -> rejected
    res_chain = prove_unmarked_opening_figure_witness_shadow(
        target,
        (NativeVectorSegment("rail_wall", (10.0, 25.0), (200.0, 25.0), lin),),
        (TrustedFigureText("txt_wall", "3600", (100.0, 20.0), lin),),
    )
    assert res_chain.abstained is True
    assert "overall_chain_dimension_not_opening_scoped" in res_chain.blocking_reasons

    # 3. Ambiguous text ("820/870" or "900 approx") -> abstains
    segs_one = (
        NativeVectorSegment("r1", (80.0, 25.0), (120.0, 25.0), lin),
        NativeVectorSegment("wa", (80.0, 23.0), (80.0, 50.0), lin),
        NativeVectorSegment("wb", (120.0, 23.0), (120.0, 50.0), lin),
    )
    res_ambig = prove_unmarked_opening_figure_witness_shadow(
        target, segs_one, (TrustedFigureText("t_amb", "820/870", (100.0, 20.0), lin),)
    )
    assert res_ambig.abstained is True
    assert "ambiguous_figure_text" in res_ambig.blocking_reasons

    # 4. Two competing parallel rails with conflicting values (820 vs 920) -> abstains
    segs_two = segs_one + (
        NativeVectorSegment("r2", (80.0, 75.0), (120.0, 75.0), lin),
        NativeVectorSegment("wa2", (80.0, 50.0), (80.0, 77.0), lin),
        NativeVectorSegment("wb2", (120.0, 50.0), (120.0, 77.0), lin),
    )
    res_conflict = prove_unmarked_opening_figure_witness_shadow(
        target,
        segs_two,
        (
            TrustedFigureText("t1", "820", (100.0, 20.0), lin),
            TrustedFigureText("t2", "920", (100.0, 80.0), lin),
        ),
    )
    assert res_conflict.abstained is True
    assert "conflicting_figure_line_dimensions" in res_conflict.blocking_reasons


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_unmarked_opening_figure_witness_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
