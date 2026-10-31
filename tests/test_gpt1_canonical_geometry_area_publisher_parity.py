"""An authenticated geometric opening is not a figured-gross-area opening.

Review must preserve both valid production area authority bases.
"""
from pb_live_opening_area_quantity_publication import (
    _opening_quantity,
    LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY,
)
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run
from tests.test_gpt1_opening_area_actual_issuer_preflight_shadow import _typed


def _geometric_source():
    rows, canonical=fixture()
    canonical[2].update(
        area_basis="resolved_opening_geometry",
        area_m2=2.16,
        opening_void_record_id="original-void-3",
        width_record_id="source-width-3",
        height_record_id="source-height-3",
        width_m=1.2, height_m=1.8, geometry_complete=True,
    )
    canonical[2]["evidence_ids"].extend(
        ("original-void-3","source-width-3","source-height-3")
    )
    return rows, canonical


def test_original_complete_geometry_can_review_even_when_figured_gross_area_cannot():
    rows,c=_geometric_source()
    r=run(rows,c)
    x=r["opening_decisions"][2]
    assert x["canonical_3d_area_publication_basis_bound"]
    assert x["canonical_3d_area_value_bound"]
    assert x["opening_area_first_remaining_gate"]==(
        "canonical_figured_area_publication_basis_unproven"
    )
    assert not x["new_gpt1_area_candidate_handoff"]
    assert x["new_gpt1_candidate_handoff"]
    assert x["first_remaining_gate"]==(
        "independent_gpt1_measurement_validation_required"
    )
    assert not x["measurement_published"]
    typed=_typed(c).canonical_openings[2]
    q=_opening_quantity(typed)
    assert q is not None
    assert q.authority==LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY
    assert q.value==2.16


def test_geometry_based_area_cannot_be_claimed_without_original_void_receipt():
    rows,c=_geometric_source()
    c[2]["evidence_ids"].remove("original-void-3")
    r=run(rows,c)
    x=r["opening_decisions"][2]
    assert not x["canonical_3d_area_publication_basis_bound"]
    assert x["first_remaining_gate"]=="canonical_geometry_area_publication_basis_unproven"
    assert not x["new_gpt1_candidate_handoff"]
    assert _opening_quantity(_typed(c).canonical_openings[2]) is None


def test_geometry_area_cannot_be_rekeyed_without_its_measurement():
    rows,c=_geometric_source()
    c[2]["area_m2"]=7.65
    r=run(rows,c)
    x=r["opening_decisions"][2]
    assert x["canonical_3d_area_publication_basis_bound"]
    assert not x["canonical_3d_area_value_bound"]
    assert x["first_remaining_gate"]=="canonical_geometry_area_value_unproven"
    assert not x["new_gpt1_candidate_handoff"]
    assert _opening_quantity(_typed(c).canonical_openings[2]) is None


def test_source_geometry_does_not_invent_count_or_alter_figured_source_pair():
    rows,c=_geometric_source()
    source_figured_before=rows[2]["original_label_dimension_result"]["evidence"].copy()
    r=run(rows,c)
    assert r["opening_decisions"][2]["figured_pair_area_support"]
    assert source_figured_before==rows[2]["original_label_dimension_result"]["evidence"]
    assert r["global_opening_count_granted"] is False
    assert not r["signed_customer_publisher_activated"]
