from copy import deepcopy

from pb_lot16_opening_receipt_refresh_shadow import refresh_opening_first_gate_receipt
from test_gptmax_lot16_host_frame_gpt1_handoff import ROOT, VIEW, fixture


def test_receipt_refresh_preserves_gates_and_never_publishes():
    rows, canonical = fixture()
    before = deepcopy((rows, canonical))
    report = refresh_opening_first_gate_receipt(
        rows, canonical, VIEW, source_root=ROOT
    )
    assert report["shadow_only"] is True
    assert report["pdf_bytes_consumed"] is False
    assert report["gold_values_consumed"] is False
    assert report["measurement_published"] is False
    assert report["customer_seal_granted"] is False
    assert report["opening_count_granted"] is False
    assert report["original_physical_opening_count"] == 3
    assert "structural_host_unavailable" in report["first_gate_counts"]
    assert (rows, canonical) == before


def test_refresh_accepts_source_proved_first_gate_for_missing_host_receipt():
    rows, canonical = fixture()
    canonical[2].update(
        width_record_id="width-3", height_record_id="height-3",
        width_m=1.2, height_m=1.8, geometry_complete=True,
        evidence_ids=["figured", "frame-3", "width-3", "height-3"],
    )
    r=refresh_opening_first_gate_receipt(rows, canonical, VIEW, source_root=ROOT)
    assert r["first_gate_counts"]["original_host_binding_receipt_unbound"] == 1
    assert not r["measurement_published"]


def test_refresh_accepts_source_proved_first_gate_for_missing_frame_receipt():
    rows, canonical = fixture()
    canonical[2].update(
        width_record_id="width-3", height_record_id="height-3",
        width_m=1.2, height_m=1.8, geometry_complete=True,
        evidence_ids=["figured", "binding-3", "width-3", "height-3"],
    )
    r=refresh_opening_first_gate_receipt(rows, canonical, VIEW, source_root=ROOT)
    assert r["first_gate_counts"]["original_host_frame_receipt_unbound"] == 1
    assert not r["customer_seal_granted"]
