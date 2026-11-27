"""A05 tests: default-off generic dimension-witness + title-scale ratio corroboration shadow."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_source_dimension_witness_scale_shadow import (
    FiguredDimensionScaleWitness,
    corroborate_dimension_witness_scale_shadow,
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
