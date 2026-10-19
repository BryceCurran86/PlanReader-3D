"""Four-project first-gate report never consumes gold or scores."""
import pytest

from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report

PROJECTS = ("lot16", "maryborough", "3laurel", "q5446")


def _row(project, oid, gate="structural_host_unavailable"):
    return {
        "project_key": project,
        "physical_object_id": oid,
        "first_remaining_gate": gate,
        "source_sha256": "a" * 64,
        "snapshot_id": "snap",
    }


def test_report_groups_gates_without_evaluator_or_gold():
    rows = [
        _row("lot16", "o2", "whole_wall_frame_unavailable"),
        _row("lot16", "o1", "structural_host_unavailable"),
        _row("maryborough", "m1", "source_owned_floor_plan_unavailable"),
    ]
    report = build_four_project_first_gate_report(rows, required_project_keys=PROJECTS)
    assert report["evaluator_invoked"] is False
    assert report["gold_values_consumed"] is False
    assert report["benchmark_score_granted"] is False
    assert report["missing_project_keys"] == ["3laurel", "q5446"]
    assert [r["physical_object_id"] for r in report["objects_by_project"]["lot16"]] == ["o1", "o2"]
    assert report["first_gate_counts_by_project"]["lot16"]["structural_host_unavailable"] == 1


def test_duplicate_object_row_fails_closed():
    rows = [_row("lot16", "o1"), _row("lot16", "o1")]
    with pytest.raises(ValueError, match="duplicate"):
        build_four_project_first_gate_report(rows, required_project_keys=("lot16",))
