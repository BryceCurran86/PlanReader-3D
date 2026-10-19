from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report
from pb_four_project_lane_row_adapters import (
    lot16_handoff_to_four_project_rows,
    maryborough_room_scopes_to_four_project_rows,
)


def test_combined_lot16_maryborough_leaves_other_two_missing():
    lot16 = lot16_handoff_to_four_project_rows([{
        "physical_opening_id": "op-1",
        "first_remaining_gate": "structural_host_unavailable",
        "source_sha256": "a" * 64,
        "snapshot_id": "snap-l16",
        "source_decision_scope_id": "wall-source:page-3",
    }])
    mary = maryborough_room_scopes_to_four_project_rows(
        [{
            "decision_scope_id": "wall-source:page-7",
            "first_unproved_authority": "SOURCE_ROOM_FACE_SCOPE_NOT_AUTHENTICATED",
            "snapshot_id": "snap-mary",
            "source_sha256": "b" * 64,
        }],
        source_sha256="b" * 64,
    )
    report = build_four_project_first_gate_report(
        [*lot16, *mary],
        required_project_keys=(
            "au_qld_lot16_power",
            "au_qld_maryborough_service_station",
            "au_qld_3laurel",
            "au_qld_q5446",
        ),
    )
    assert report["missing_project_keys"] == ["au_qld_3laurel", "au_qld_q5446"]
    assert report["first_gate_counts_by_project"]["au_qld_lot16_power"] == {
        "structural_host_unavailable": 1,
    }
    assert report["first_gate_counts_by_project"][
        "au_qld_maryborough_service_station"
    ] == {"SOURCE_ROOM_FACE_SCOPE_NOT_AUTHENTICATED": 1}
    assert report["evaluator_invoked"] is False
    assert report["gold_values_consumed"] is False
