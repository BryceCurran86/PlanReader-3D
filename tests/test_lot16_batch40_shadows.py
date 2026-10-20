from pb_g17_segment_parent_line_shadow import _finite_line
from pb_segment_line_w4_id_intersection_shadow import (
    assess_segment_line_w4_id_intersection_shadow,
)
from pb_signed_eight_id_retention import assert_signed_quantity_ids_retained
from pb_three_laurel_q5446_first_gate_stub_shadow import (
    build_three_laurel_q5446_missing_stub_report,
)


def test_signed_eight_retention_detects_missing():
    report = assert_signed_quantity_ids_retained(
        required_quantity_ids=("q1", "q2"),
        observed_quantity_ids=("q1",),
    )
    assert report["status"] == "SIGNED_QUANTITY_IDS_MISSING"
    assert report["missing_quantity_ids"] == ["q2"]
    assert report["boq_values_read"] is False


def test_signed_eight_retention_ok():
    report = assert_signed_quantity_ids_retained(
        required_quantity_ids=("q1", "q2"),
        observed_quantity_ids=("q2", "q1", "q3"),
    )
    assert report["status"] == "SIGNED_QUANTITY_IDS_RETAINED"


def test_segment_w4_intersection_disjoint():
    r = assess_segment_line_w4_id_intersection_shadow(
        physical_opening_id="o1",
        segment_line_raw_ids=("a", "b"),
        usable_w4_source_primitive_ids=("c", "d"),
    )
    assert r["first_remaining_gate"] == "segment_line_ids_disjoint_from_w4_primitives"
    assert r["host_granted"] is False


def test_segment_w4_intersection_after_strip():
    r = assess_segment_line_w4_id_intersection_shadow(
        physical_opening_id="o1",
        segment_line_raw_ids=("seg:1",),
        usable_w4_source_primitive_ids=("visible:seg:1",),
    )
    assert r["first_remaining_gate"] == (
        "segment_line_ids_intersect_w4_after_visible_strip_only"
    )


def test_three_laurel_q5446_stub_marks_missing():
    report = build_three_laurel_q5446_missing_stub_report(
        lot16_and_maryborough_rows=[{
            "project_key": "au_qld_lot16_power",
            "physical_object_id": "op-1",
            "first_remaining_gate": "structural_host_unavailable",
            "source_sha256": "a" * 64,
            "snapshot_id": "s",
        }],
    )
    assert "au_qld_3laurel" in report["missing_project_keys"]
    assert "au_qld_q5446" in report["missing_project_keys"]
    assert report["benchmark_score_granted"] is False


def test_finite_line_ok():
    assert _finite_line((0.0, 1.0, 2.0, 1.0)) == (0.0, 1.0, 2.0, 1.0)
