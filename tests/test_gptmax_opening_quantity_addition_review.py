"""Additive area review follows the actual area seam, never a 3D-frame proxy."""
from copy import deepcopy
from dataclasses import replace

import pytest

from test_live_opening_area_quantity_publication import _opening, _composition
from tools.recover_source_preserving_openings_shadow import opening_quantity_addition_review


def packet(opening, *, support="source-a", closed=True):
    scope = {k: getattr(opening, k) for k in (
        "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")}
    return {
        "packet_id": "packet-" + opening.physical_opening_id,
        "opening_identity_id": opening.physical_opening_id,
        "page_id": opening.page_id,
        "physical_opening": {**scope, "record_id": opening.physical_opening_id,
            "source_observation_ids": [support]},
        "source_lineage": {"source_proof_closed": closed,
            "unresolved_parent_ids": [] if closed else ["missing-parent"],
            "observations": [{**scope, "observation_id": support,
                "observation_kind": "raster_wall_band", "source_primitive_ref": support,
                "geometry": [0, 0, 1, 0]}]},
        "whole_wall_frame": {"record_id": opening.host_frame_record_id},
        "next_required_evidence": ["connected_whole_wall_frame", "metric_wall_placement"],
    }


def run(old, new, old_packets=None, new_packets=None):
    return opening_quantity_addition_review(_composition(*old), _composition(*new),
        original_packets=[packet(o) for o in old] if old_packets is None else old_packets,
        alternate_packets=[packet(o, support="new-"+o.physical_opening_id) for o in new]
        if new_packets is None else new_packets)


def test_figured_area_without_whole_frame_reaches_separate_authority_review():
    old = _opening()
    new = replace(_opening(canonical_id="opening-2", figured_area_record_id="figured-2"),
        host_frame_record_id=None)
    before = (deepcopy(old), deepcopy(new))
    result = run([old], [old, new])
    row, = result["additional_area_reviews"]
    assert row["first_remaining_gate"] == "independent_additive_area_authority_review_required"
    assert row["value"] == new.area_m2
    assert row["complete_frame_required_by_area_basis"] is False
    assert row["complete_frame_available"] is False
    assert row["status"] == "candidate"
    assert row["append_authority_granted"] is False
    assert row["commercial_projection_allowed"] is False
    assert row["opening_count_granted"] is False
    assert row["benchmark_match_granted"] is False
    assert result["original_signed_rows_reissued"] is False
    assert (old, new) == before


def test_snapshot_reissued_old_quantity_is_excluded_even_with_new_metadata():
    old = _opening()
    reissued = replace(old, snapshot_id="alternate-snapshot")
    result = run([old], [reissued])
    assert result["additional_area_reviews"] == []
    assert result["excluded_reissued_quantity_ids"] == result["original_quantity_ids_retained_separately"]


def test_rekeyed_measurement_of_existing_physical_opening_is_not_a_new_area():
    old = _opening()
    reissued = _opening(figured_area_record_id="new-measurement")
    row, = run([old], [reissued])["additional_area_reviews"]
    assert row["existing_physical_identity"] is True
    assert row["first_remaining_gate"] == "existing_physical_identity_continuation_review_required"


def test_new_id_with_exact_original_source_support_cannot_imply_distinct_opening():
    old, new = _opening(), _opening(canonical_id="new-id")
    row, = run([old], [new], new_packets=[packet(new)])["additional_area_reviews"]
    assert row["exact_source_support_original_ids"] == [old.physical_opening_id]
    assert row["first_remaining_gate"] == "existing_physical_identity_continuation_review_required"


@pytest.mark.parametrize("damage", ["missing", "contradictory-closed", "foreign-parent", "duplicate-parent", "truthy-closed"])
def test_unproven_original_source_packet_is_first_gate(damage):
    old, new = _opening(), _opening(canonical_id="new-id")
    p = packet(new, support="new-source", closed=damage != "missing")
    if damage == "contradictory-closed": p["source_lineage"]["unresolved_parent_ids"] = ["missing"]
    if damage == "foreign-parent": p["source_lineage"]["observations"][0]["revision_id"] = "foreign"
    if damage == "duplicate-parent": p["source_lineage"]["observations"] *= 2
    if damage == "truthy-closed": p["source_lineage"]["source_proof_closed"] = 1
    row, = run([old], [new], new_packets=[p])["additional_area_reviews"]
    assert row["source_parent_dag_closed"] is False
    assert row["first_remaining_gate"] == "original_source_parent_dag_required"


@pytest.mark.parametrize("field,value", [("document_id", "foreign"), ("source_sha256", "b"*64)])
def test_alternate_drawing_cannot_borrow_original_issuer(field, value):
    with pytest.raises(ValueError, match="retain the original"):
        run([_opening()], [replace(_opening(canonical_id="new-id"), **{field:value})])


def test_missing_or_foreign_packet_cannot_review_a_valid_quantity():
    old, new = _opening(), _opening(canonical_id="new-id")
    with pytest.raises(ValueError, match="lacks"):
        run([old], [new], new_packets=[])
    p = packet(new)
    p["physical_opening"]["snapshot_id"] = "foreign"
    with pytest.raises(ValueError, match="disagree"):
        run([old], [new], new_packets=[p])


def test_input_order_is_stable_and_missing_host_or_kind_never_nominates_area():
    old = _opening()
    a = _opening(canonical_id="new-a")
    b = _opening(canonical_id="new-b", kind=None)
    c = replace(_opening(canonical_id="new-c"), host_wall_id=None)
    first = run([old], [a, b, c])
    assert first == run([old], [c, b, a])
    assert len(first["additional_area_reviews"]) == 1


def test_unresolved_metric_geometry_is_not_replaced_by_label_area():
    old = _opening()
    new = _opening(canonical_id="new-geometry", area_basis="resolved_opening_geometry",
        figured_area_record_id=None, opening_void_record_id="void-source")
    assert run([old], [new])["additional_area_reviews"] == []
