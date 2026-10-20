"""Original source must prove opening kind, not a copied canonical string."""
from copy import deepcopy

import pytest

from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
)
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _host_only():
    r,c=fixture()
    r[2]["frame_record"]=None
    c[2]["host_frame_record_id"]=None
    return r,c


def test_native_label_source_window_reproves_original_kind_without_3d_frame():
    rows,c=_host_only()
    d=run(rows,c)["opening_decisions"][2]
    assert d["original_opening_kind_source_authority_reproved"]
    assert d["filling_kind_source_supported"]
    assert d["new_gpt1_area_candidate_handoff"]
    assert not d["new_gpt1_candidate_handoff"]


def test_exact_original_structural_window_reproves_kind_when_figured_semantic_absent():
    rows,c=_host_only()
    rows[2]["original_label_dimension_result"]["evidence"]["semantic_kind"]=None
    rows[2]["physical_existence_record"]["structural_pattern"]=GAP_CORROBORATED_WINDOW_JAMB_PAIR
    c[2]["structural_pattern"]=GAP_CORROBORATED_WINDOW_JAMB_PAIR
    d=run(rows,c)["opening_decisions"][2]
    assert d["original_opening_kind_source_authority_reproved"]
    assert d["new_gpt1_area_candidate_handoff"]


def test_structural_door_opposed_to_original_native_window_label_abstains():
    rows,c=_host_only()
    rows[2]["physical_existence_record"]["structural_pattern"]=GAP_CORROBORATED_DOOR_JAMB_LEAF
    c[2]["structural_pattern"]=GAP_CORROBORATED_DOOR_JAMB_LEAF
    d=run(rows,c)["opening_decisions"][2]
    assert d["opening_area_first_remaining_gate"] == (
        "original_opening_kind_source_authority_unverified"
    )
    assert not d["original_opening_kind_source_authority_reproved"]
    assert not d["new_gpt1_area_candidate_handoff"]


def test_figure_without_semantic_or_issued_structural_kind_is_unresolved():
    rows,c=_host_only()
    rows[2]["original_label_dimension_result"]["evidence"]["semantic_kind"]=None
    d=run(rows,c)["opening_decisions"][2]
    assert d["figured_pair_area_support"]
    assert d["figured_area_receipt_bound"]
    assert d["opening_area_first_remaining_gate"] == (
        "original_opening_kind_source_authority_unverified"
    )
    assert not d["new_gpt1_area_candidate_handoff"]


def test_structural_source_pattern_cannot_be_replayed_under_different_canonical_owner():
    rows,c=_host_only()
    rows[2]["physical_existence_record"]["structural_pattern"]=GAP_CORROBORATED_WINDOW_JAMB_PAIR
    c[2]["structural_pattern"]="raster_framed_wall_band_interruption"
    d=run(rows,c)["opening_decisions"][2]
    assert not d["original_opening_kind_source_authority_reproved"]
    assert not d["new_gpt1_area_candidate_handoff"]


def test_unrelated_kind_and_label_does_not_rename_physical_door():
    rows,c=_host_only()
    c[2]["opening_kind"]="door"
    # Original figured label still says WINDOW, so neither the host nor
    # the figure's numeric area can independently support the new type.
    d=run(rows,c)["opening_decisions"][2]
    assert not d["original_opening_kind_source_authority_reproved"]
    assert not d["new_gpt1_area_candidate_handoff"]


def test_original_figured_source_kind_review_does_not_mint_a_quantity_or_count():
    rows,c=_host_only()
    before=deepcopy((rows,c))
    r=run(rows,c)
    assert before==(rows,c)
    assert not r["signed_customer_publisher_activated"]
    assert not r["global_opening_count_granted"]
    assert all(not x["measurement_published"] and not x["customer_seal_granted"]
               for x in r["opening_decisions"])


def test_previous_original_signed_area_never_reenters_review():
    rows,c=_host_only()
    rows[2]["quantity_id"]="original-already-signed"
    r=run(rows,c)
    assert r["opening_decisions"][2]["opening_area_first_remaining_gate"]==(
        "original_signed_area_already_retained"
    )
    assert not r["gpt1_new_area_review_candidates"]
