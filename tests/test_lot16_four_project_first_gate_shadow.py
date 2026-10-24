from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report


def test_lot16_only_leaves_other_projects_missing():
    report = build_four_project_first_gate_report(
        [{
            "project_key": "au_qld_lot16_power",
            "physical_object_id": "op-1",
            "first_remaining_gate": "structural_host_unavailable",
            "source_sha256": "abc",
            "snapshot_id": "snap",
        }],
        required_project_keys=(
            "au_qld_lot16_power",
            "au_qld_maryborough_service_station",
            "au_qld_3laurel",
            "au_qld_q5446",
        ),
    )
    assert report["missing_project_keys"] == [
        "au_qld_maryborough_service_station",
        "au_qld_3laurel",
        "au_qld_q5446",
    ]
    assert report["first_gate_counts_by_project"]["au_qld_lot16_power"] == {
        "structural_host_unavailable": 1,
    }
    assert report["evaluator_invoked"] is False
    assert report["gold_values_consumed"] is False
    assert report["benchmark_score_granted"] is False
