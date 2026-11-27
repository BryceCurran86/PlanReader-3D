"""A05 tests: default-off generic dimension-witness + title-scale ratio corroboration shadow."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_source_dimension_witness_scale_shadow import (
    FiguredDimensionScaleWitness,
    corroborate_dimension_witness_scale_shadow,
    extract_dimension_witnesses_from_native_components,
)
from pb_source_vector_outlined_text_ocr_shadow import (
    AgreedOutlinedTextToken,
    classify_outlined_caption_view_type,
)

_SHA = "f" * 64
_PTS_PER_MM_1_100 = (POINTS_PER_METRE_AT_1_1 / 1000.0) / 100.0


def test_a05_two_agreeing_dimension_witnesses_corroborate_1_to_100_scale() -> None:
    w1 = FiguredDimensionScaleWitness(
        "w1", "doc-1", "rev-1", _SHA, "7", "vp-1",
        pdf_span_pts=3570.0 * _PTS_PER_MM_1_100, figured_mm=3570.0, axis="horizontal",
    )
    w2 = FiguredDimensionScaleWitness(
        "w2", "doc-1", "rev-1", _SHA, "7", "vp-1",
        pdf_span_pts=2536.0 * _PTS_PER_MM_1_100, figured_mm=2536.0, axis="vertical",
    )
    res = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=_SHA,
        page_id="7",
        viewport_id="vp-1",
        dimension_witnesses=(w1, w2),
    )
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.implied_scale_denominator == pytest.approx(100.0, rel=1e-4)
    assert res.requires_typed_negative_ink_guard is True
    assert res.shadow_only is True
    assert res.commercial_authority_granted is False


def test_a05_single_witness_corroborated_by_explicit_ratio_passes_but_ratio_alone_abstains() -> None:
    w1 = FiguredDimensionScaleWitness(
        "w1", "doc-1", "rev-1", _SHA, "7", "vp-1",
        pdf_span_pts=5000.0 * _PTS_PER_MM_1_100, figured_mm=5000.0, axis="horizontal",
    )
    ok = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w1,), explicit_scale_ratios=(100.0,),
    )
    assert ok.status == EvidenceResolutionStatus.CORROBORATED
    assert ok.implied_scale_denominator == pytest.approx(100.0, rel=1e-4)

    # Ratio alone (no dimension witnesses) MUST abstain
    ratio_only = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(), explicit_scale_ratios=(100.0,),
    )
    assert ratio_only.status == EvidenceResolutionStatus.ABSTAINED
    assert ratio_only.mm_per_point is None

    # Single witness without corroborating ratio MUST abstain
    single_only = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w1,), explicit_scale_ratios=(),
    )
    assert single_only.status == EvidenceResolutionStatus.ABSTAINED


def test_a05_conflicting_witnesses_ratios_or_revisions_veto_with_conflict() -> None:
    w_100 = FiguredDimensionScaleWitness(
        "w1", "doc-1", "rev-1", _SHA, "7", "vp-1",
        pdf_span_pts=3000.0 * _PTS_PER_MM_1_100, figured_mm=3000.0,
    )
    w_50 = FiguredDimensionScaleWitness(
        "w2", "doc-1", "rev-1", _SHA, "7", "vp-1",
        pdf_span_pts=3000.0 * _PTS_PER_MM_1_100 * 2.0, figured_mm=3000.0,
    )
    # Disagreement between witnesses -> CONFLICT
    c1 = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w_100, w_50),
    )
    assert c1.status == EvidenceResolutionStatus.CONFLICT

    # Witness (1:100) vs explicit ratio (1:50) -> CONFLICT
    c2 = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w_100,), explicit_scale_ratios=(50.0,),
    )
    assert c2.status == EvidenceResolutionStatus.CONFLICT

    # Conflicting explicit ratios (1:50 & 1:100) -> CONFLICT
    c3 = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w_100,), explicit_scale_ratios=(50.0, 100.0),
    )
    assert c3.status == EvidenceResolutionStatus.CONFLICT

    # Cross-revision witness -> CONFLICT
    w_wrong_rev = FiguredDimensionScaleWitness(
        "w-bad", "doc-1", "rev-2", _SHA, "7", "vp-1",
        pdf_span_pts=3000.0 * _PTS_PER_MM_1_100, figured_mm=3000.0,
    )
    c4 = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1", revision_id="rev-1", source_sha256=_SHA,
        page_id="7", viewport_id="vp-1",
        dimension_witnesses=(w_100, w_wrong_rev),
    )
    assert c4.status == EvidenceResolutionStatus.CONFLICT


def test_a05_extract_dimension_witnesses_from_native_components_end_to_end() -> None:
    # Build two orthogonal synthetic native dimension cap chains at 1:100
    span_h = 3000.0 * _PTS_PER_MM_1_100
    span_v = 2400.0 * _PTS_PER_MM_1_100
    segments = {
        # Horizontal dim line + left/right ticks + left/right witness caps
        "h_line": (100.0, 100.0, 100.0 + span_h, 100.0),
        "h_t0a": (98.0, 98.0, 100.0, 100.0),
        "h_t0b": (100.0, 100.0, 102.0, 102.0),
        "h_t1a": (100.0 + span_h - 2.0, 98.0, 100.0 + span_h, 100.0),
        "h_t1b": (100.0 + span_h, 100.0, 100.0 + span_h + 2.0, 102.0),
        "h_c0": (100.0, 100.0, 100.0, 120.0),
        "h_c1": (100.0 + span_h, 100.0, 100.0 + span_h, 120.0),
        # Vertical dim line + top/bottom ticks + witness caps
        "v_line": (60.0, 200.0, 60.0, 200.0 + span_v),
        "v_t0a": (58.0, 198.0, 60.0, 200.0),
        "v_t0b": (60.0, 200.0, 62.0, 202.0),
        "v_t1a": (58.0, 200.0 + span_v - 2.0, 60.0, 200.0 + span_v),
        "v_t1b": (60.0, 200.0 + span_v, 62.0, 200.0 + span_v + 2.0),
        "v_c0": (60.0, 200.0, 80.0, 200.0),
        "v_c1": (60.0, 200.0 + span_v, 80.0, 200.0 + span_v),
    }
    words = [
        {
            "id": "w_h",
            "text": "3000",
            "bbox": (100.0 + span_h * 0.4, 90.0, 100.0 + span_h * 0.6, 98.0),
            "center": (100.0 + span_h * 0.5, 94.0),
            "axis": (1.0, 0.0),
        },
        {
            "id": "w_v",
            "text": "2400",
            "bbox": (48.0, 200.0 + span_v * 0.4, 58.0, 200.0 + span_v * 0.6),
            "center": (53.0, 200.0 + span_v * 0.5),
            "axis": (0.0, 1.0),
        },
    ]
    witnesses = extract_dimension_witnesses_from_native_components(
        segments=segments,
        words=words,
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=_SHA,
        page_id="7",
        viewport_id="vp-1",
    )
    assert len(witnesses) == 2
    assert {w.axis for w in witnesses} == {"horizontal", "vertical"}
    scale = corroborate_dimension_witness_scale_shadow(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=_SHA,
        page_id="7",
        viewport_id="vp-1",
        dimension_witnesses=witnesses,
    )
    assert scale.status == EvidenceResolutionStatus.CORROBORATED
    assert scale.implied_scale_denominator == pytest.approx(100.0, rel=1e-3)


def test_a06_outlined_caption_view_classifier_separates_floor_from_roof_and_rejects_conflict() -> None:
    def _tok(text: str, x: float, y: float, dpis: tuple[int, ...] = (216, 288)) -> AgreedOutlinedTextToken:
        return AgreedOutlinedTextToken(
            normalized_text=text,
            raw_texts=(text,),
            source_sha256=_SHA,
            page_index=0,
            bbox_pdf_pts=(x, y, x + 40.0, y + 12.0),
            agreement_dpis=dpis,
            agreement_ratio=1.0,
            mean_confidence=0.95,
        )

    fp = classify_outlined_caption_view_type([_tok("GROUND", 100, 700), _tok("FLOOR", 150, 701), _tok("PLAN", 200, 700)])
    assert fp.status == "CORROBORATED" and fp.view_type == "floor_plan"
    assert fp.shadow_only is True and fp.commercial_projection_allowed is False

    roof = classify_outlined_caption_view_type([_tok("ROOF", 100, 700), _tok("PLAN", 150, 700)])
    assert roof.status == "CORROBORATED" and roof.view_type == "roof_plan"

    # Single-DPI token must abstain
    single_dpi = classify_outlined_caption_view_type([_tok("FLOOR PLAN", 100, 700, dpis=(216,))])
    assert single_dpi.status == "ABSTAINED" and single_dpi.view_type == "unproven"

    # Conflicting view types on same sheet must fail closed with CONFLICT
    conflict = classify_outlined_caption_view_type([_tok("FLOOR PLAN", 100, 700), _tok("ROOF PLAN", 100, 750)])
    assert conflict.status == "CONFLICT" and conflict.view_type == "unproven"
