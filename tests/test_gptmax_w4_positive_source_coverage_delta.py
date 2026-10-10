"""Original physical W4 source coverage is independent of host receipt rekeys."""
from copy import deepcopy

import pytest

from tools.gptmax_w4_positive_source_coverage_delta import (
    audit_positive_w4_coverage_delta as audit,
)


PRIMITIVE="raster_segment:real-original-sha:1.0.0:1585"
OID="physical_opening_existence_source_owned"
SHA="a"*64


def report(source_edges, *, source_primitive=PRIMITIVE):
    return {
        "source_sha256": SHA,
        "selected_geometry_page_ids": ["3"],
        "primitive_safety_cap": 20_000,
        "opening_bindings": [{
            "opening_identity_id": OID,
            "page_id": "3",
            "host_wall_id": "host_receipt_group",
            "record_id": "host_receipt",
            "member_wall_candidate_ids": ["wall_a"],
        }],
        "source_owned_wall_scope_results": [{
            "page_id": "3",
            "source_sha256": SHA,
            "scope_complete": True,
            "status": "corroborated",
            "records": [{
                "wall_candidate_id": "wall_a",
                "physical_identity": {
                    "status": "corroborated",
                    "blocking_reasons": [],
                    "source_primitive_ids": [source_primitive],
                },
                "source_edge_fragments": [
                    {"geometry": list(edge),
                     "source_primitive_ids": [source_primitive]}
                    for edge in source_edges
                ],
            }],
        }],
    }


def test_original_positive_1585_1point22_fragment_loss_precisely_observed():
    before=report([[410.25,341.50,410.25,349.00]])
    after=report([[410.25,342.72,410.25,349.00]])
    result=audit(before,after)
    assert result["absent_original_w4_source_fragment_count"]==1
    row=result["missing_source_coverage_rows"][0]
    assert row["absent_original_coverage_pdf_pt"]==[
        410.25,341.50,410.25,342.72
    ]
    assert row["positive_source_primitive_id"]==PRIMITIVE
    assert not result["physical_host_or_receipt_equivalence_allowed"]
    assert not result["opening_count_or_metric_quantity_allowed"]
    assert result["benchmark_accuracy"] is None


def test_original_positive_324_1point90_terminal_fragment_loss():
    primitive="raster_segment:real-original-sha:1.0.0:324"
    before=report([[414.0,531.25,584.5,531.25]],
                  source_primitive=primitive)
    after=report([[414.0,531.25,582.6,531.25]],
                 source_primitive=primitive)
    row=audit(before,after)["missing_source_coverage_rows"][0]
    assert row["absent_original_coverage_pdf_pt"]==[
        582.6,531.25,584.5,531.25
    ]


def test_re_split_1567_retains_original_coverage_without_inventing_unpainted_gap():
    primitive="raster_segment:real-original-sha:1.0.0:1567"
    before=report([
        [381.0,297.0,381.0,336.75],
        [381.0,338.75,381.0,349.0],
    ],source_primitive=primitive)
    after=report([
        [381.0,297.0,381.0,336.75],
        [381.0,338.75,381.0,342.72],
        [381.0,342.72,381.0,349.0],
    ],source_primitive=primitive)
    result=audit(before,after)
    assert result["missing_source_coverage_rows"]==[]
    assert result["source_gap_closure_allowed"] is False


def test_split_and_reversed_candidate_edges_cover_exact_original_segment():
    before=report([[10.,10.,30.,10.]])
    after=report([[20.,10.,10.,10.],[30.,10.,20.,10.]])
    assert audit(before,after)["missing_source_coverage_rows"]==[]


def test_unrelated_offset_source_does_not_manufacture_positive_coverage():
    before=report([[10.,10.,20.,10.]])
    after=report([[10.,10.1,20.,10.1]])
    assert audit(before,after)["missing_source_coverage_rows"][0][
        "absent_original_coverage_pdf_pt"] == [10.,10.,20.,10.]


def test_candidate_host_absent_requires_abstain_not_claimed_wall_loss():
    before=report([[10.,10.,20.,10.]])
    after=deepcopy(before)
    after["opening_bindings"][0]["host_wall_id"]=None
    after["opening_bindings"][0]["record_id"]=None
    result=audit(before,after)
    assert result["missing_source_coverage_rows"]==[]
    assert result["candidate_host_absent_abstentions"]==[OID]


@pytest.mark.parametrize("breakage",[
    "wrong_source_sha","wrong_page","wrong_cap","duplicate_opening",
    "duplicate_wall","incomplete_scope","no_source_fragment",
    "foreign_primitive","nonfinite_coords",
])
def test_unverified_original_source_fails_closed(breakage):
    before=report([[10.,10.,20.,10.]])
    after=deepcopy(before)
    if breakage=="wrong_source_sha":
        after["source_sha256"]="b"*64
        after["source_owned_wall_scope_results"][0]["source_sha256"]="b"*64
    elif breakage=="wrong_page":
        after["selected_geometry_page_ids"]=["4"]
        after["opening_bindings"][0]["page_id"]="4"
        after["source_owned_wall_scope_results"][0]["page_id"]="4"
    elif breakage=="wrong_cap":
        after["primitive_safety_cap"]=19999
    elif breakage=="duplicate_opening":
        after["opening_bindings"].append(deepcopy(after["opening_bindings"][0]))
    elif breakage=="duplicate_wall":
        after["source_owned_wall_scope_results"][0]["records"].append(
            deepcopy(after["source_owned_wall_scope_results"][0]["records"][0]))
    elif breakage=="incomplete_scope":
        after["source_owned_wall_scope_results"][0]["scope_complete"]=False
    elif breakage=="no_source_fragment":
        after["source_owned_wall_scope_results"][0]["records"][0]["source_edge_fragments"]=[]
    elif breakage=="foreign_primitive":
        after["source_owned_wall_scope_results"][0]["records"][0][
            "source_edge_fragments"][0]["source_primitive_ids"]=["not_owned"]
    else:
        after["source_owned_wall_scope_results"][0]["records"][0][
            "source_edge_fragments"][0]["geometry"][0]=float("nan")
    with pytest.raises(ValueError):
        audit(before,after)
