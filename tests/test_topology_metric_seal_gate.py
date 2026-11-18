"""Fail-closed topology metric seal gate — title-block scale never seals."""

from __future__ import annotations

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleCalibrationStatus,
    ScaleSourceType,
)
from pb_topology_metric_seal_gate import (
    assess_acacia_p2_title_block_only_gate,
    assess_topology_metric_seal_gate,
    summarize_gate_batch,
)


def _scale_bar_firm(*, page_no: int = 1) -> ScaleCalibration:
    return ScaleCalibration(
        page_no=page_no,
        ratio_str="1:100",
        px_per_m=POINTS_PER_METRE_AT_1_1 / 100.0,
        method="GRAPHIC_SCALE_BAR",
        is_verified=True,
        confidence=1.0,
        sheet_label="p1",
        scale_text="1:100",
        source_type=ScaleSourceType.SCALE_BAR.value,
        status=ScaleCalibrationStatus.VALID.value,
        issues=[],
    )


def test_title_block_only_blocks_acacia_p2_metric_seal():
    result = assess_acacia_p2_title_block_only_gate(topology_candidate_count=33)
    assert result.seal_eligible is False
    assert result.measurement_published is False
    assert result.customer_rows_mutated is False
    assert result.shadow_only is True
    assert result.measurement_authority == AuthorityStatus.PROVISIONAL.value
    assert result.first_remaining_gate == "seal_blocked_title_block_scale_not_firm"


def test_missing_topology_candidates_is_first_gate():
    result = assess_topology_metric_seal_gate(
        page_no=2,
        calibration=_scale_bar_firm(page_no=2),
        topology_candidates_present=False,
        source_lineage_complete=True,
    )
    assert result.first_remaining_gate == "seal_blocked_no_topology_candidates"
    assert result.seal_eligible is False


def test_scale_bar_firm_reaches_review_only_never_self_seals():
    result = assess_topology_metric_seal_gate(
        page_no=1,
        calibration=_scale_bar_firm(),
        topology_candidates_present=True,
        source_lineage_complete=True,
    )
    assert result.measurement_authority == AuthorityStatus.FIRM.value
    assert result.first_remaining_gate == "topology_metric_seal_review_only"
    assert result.seal_eligible is False
    assert result.measurement_published is False


def test_unknown_calibration_blocks():
    result = assess_topology_metric_seal_gate(
        page_no=3,
        calibration=None,
        topology_candidates_present=True,
        source_lineage_complete=True,
    )
    assert result.first_remaining_gate == "seal_blocked_page_scale_not_firm"
    assert result.measurement_authority == AuthorityStatus.BLOCKED.value


def test_batch_summary_never_marks_seal_eligible():
    rows = [
        assess_acacia_p2_title_block_only_gate(topology_candidate_count=1),
        assess_topology_metric_seal_gate(
            page_no=1,
            calibration=_scale_bar_firm(),
            topology_candidates_present=True,
            source_lineage_complete=True,
        ),
    ]
    summary = summarize_gate_batch(rows)
    assert summary["any_seal_eligible"] is False
    assert summary["shadow_only"] is True
    assert summary["count"] == 2
