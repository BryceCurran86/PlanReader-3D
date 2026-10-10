"""Only real producer-owned room IDs can receive source measurement first gates."""
from types import SimpleNamespace as N

from tools.diag_gpt2_named_room_metric_first_gates import (
    summarize_named_room_metric_first_gates as summarize,
)


def claim(rooms, *, same=(), cross=(), scale=()):
    return N(
        canonical_rooms=tuple(rooms),
        same_view_room_area_first_failure_codes=tuple(same),
        cross_view_room_area_first_failure_codes=tuple(cross),
        physical_scale_first_failure_codes=tuple(scale),
    )


def room(owner, label):
    return N(physical_room_id=owner, room_label=label)


def test_named_room_gates_preserve_exact_source_owned_failure_codes():
    got = summarize(claim(
        (room("source-1", " Freezer "), room("source-2", "Pwd")),
        same=(("source-1", "missing_figured_pair"), ("unlabelled", "reason")),
        cross=(("source-2", "source_cross_view_unavailable"),),
        scale=(("source-1", ("no_scale", "no_documented_dimensions")),),
    ))
    assert got["source_named_room_count"] == 2
    assert got["uniquely_attributable_named_room_count"] == 2
    assert got["named_room_metric_first_failure_codes"]["same_view"] == [{
        "physical_room_id": "source-1", "label": "FREEZER",
        "first_gate": "missing_figured_pair",
    }]
    assert got["named_room_metric_first_failure_codes"]["physical_scale"] == [{
        "physical_room_id": "source-1", "label": "FREEZER",
        "first_gates": ["no_scale", "no_documented_dimensions"],
    }]
    assert got["all_source_first_failure_receipt_counts"] == {
        "same_view": 2, "cross_view": 1, "physical_scale": 1,
    }
    assert got["metric_quantity_published"] is False


def test_named_room_gates_abstain_on_duplicate_or_missing_physical_owner():
    got = summarize(claim(
        (room("source-shared", "FREEZER"),
         room("source-shared", "COLD ROOM"),
         room("", "LAUNDRY"),
         room("source-unique", "OFFICE")),
        same=(("source-shared", "ambiguous"), ("source-unique", "source_ok")),
    ))
    assert got["ambiguous_named_physical_room_ids"] == ["", "source-shared"]
    assert got["uniquely_attributable_named_room_count"] == 1
    assert got["named_room_metric_first_failure_codes"]["same_view"] == [{
        "physical_room_id": "source-unique", "label": "OFFICE",
        "first_gate": "source_ok",
    }]
    assert got["all_source_first_failure_receipt_counts"]["same_view"] == 2
