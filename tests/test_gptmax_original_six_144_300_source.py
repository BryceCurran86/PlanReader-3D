"""144/300 DPI source overlap never authenticates a host by itself."""
from copy import deepcopy
from hashlib import sha256

import pytest

from tools.diag_gptmax_original_six_144_300_source import (
    validate_144_correspondence,original_six_crossresolution_source,
)


def raw():
    return {
        "physical_wall_role_granted":False,"cross_source_equivalence_granted":False,
        "host_granted":False,"metric_quantity_granted":False,
        "complete_wall_universe_proven":False,
        "openings":[{
            "physical_opening_id":"phys-"+str(i),"host_granted":False,
            "metric_quantity_granted":False,
            "flanks":[{"source_ink_supported":True,
                       "source_edges":[{
                           "g17_edge_id":"edge-a-"+str(i),
                           "w4_cross_source_equivalence_proven":False,
                           "structural_wall_role_proven":False,
                           "144_pixel_source_profile":{
                               "status":"evaluated",
                               "original_144_solid_and_unchanged":True},
                           "144_w4_lattice_candidates":[
                               {"wall_candidate_id":"w-"+str(i),
                                "edge_id":"edge-w-"+str(i),
                                "candidate_identity_id":"candidate-"+str(i)}
                           ],
                       }]},
                      {"source_ink_supported":False,"source_edges":[]}]}
            for i in range(6)]
    }


def test_original_six_144_positive_is_not_physical_wall_or_host():
    rows=validate_144_correspondence(raw())
    assert len(rows)==6
    assert all(r["original_300dpi_paint_supported_flanks"]==1 for r in rows)
    assert all(r["original_144dpi_paint_matched_edges"]==1 for r in rows)
    assert all(r["ordinary_W4_lattice_candidates"]==1 for r in rows)
    assert all(r["144_to_300_physical_wall_equivalence_proven"] is False for r in rows)
    assert all(r["host_or_metric_granted"] is False for r in rows)


@pytest.mark.parametrize("badfield",[
    "physical_wall_role_granted","cross_source_equivalence_granted",
    "host_granted","metric_quantity_granted","complete_wall_universe_proven",
])
def test_cross_resolution_raster_match_cannot_set_grants(badfield):
    r=raw()
    r[badfield]=True
    with pytest.raises(ValueError,match="grants"):
        validate_144_correspondence(r)


@pytest.mark.parametrize("mutate",[
    lambda r:r["openings"].pop(),
    lambda r:r["openings"][1].update(physical_opening_id="phys-0"),
    lambda r:r["openings"][0].update(host_granted=True),
    lambda r:r["openings"][0].update(metric_quantity_granted=True),
    lambda r:r["openings"][0]["flanks"].pop(),
    lambda r:r["openings"][0]["flanks"][0].update(source_ink_supported=False),
    lambda r:r["openings"][0]["flanks"][0]["source_edges"][0].update(
        structural_wall_role_proven=True),
    lambda r:r["openings"][0]["flanks"][0]["source_edges"][0].update(
        w4_cross_source_equivalence_proven=True),
    lambda r:r["openings"][0]["flanks"][0]["source_edges"].append(
        deepcopy(r["openings"][0]["flanks"][0]["source_edges"][0])),
    lambda r:r["openings"][0]["flanks"][0]["source_edges"][0][
        "144_w4_lattice_candidates"].append(
            deepcopy(r["openings"][0]["flanks"][0]["source_edges"][0][
                "144_w4_lattice_candidates"][0])),
])
def test_foreign_conflicted_or_incomplete_physical_owner_abstains(mutate):
    r=raw()
    mutate(r)
    with pytest.raises(ValueError):
        validate_144_correspondence(r)


def test_144_source_negative_is_retained_not_deleted():
    r=raw()
    sample=r["openings"][2]["flanks"][0]["source_edges"][0]["144_pixel_source_profile"]
    sample["original_144_solid_and_unchanged"]=False
    rows=validate_144_correspondence(r)
    assert rows[2]["original_144dpi_paint_matched_edges"]==0
    assert rows[2]["original_144dpi_paint_disagreed_edges"]==1
    assert rows[2]["ordinary_W4_lattice_candidates"]==1
    assert not rows[2]["structural_role_proven"]


def test_input_order_changes_neither_competitors_nor_identity():
    r=raw()
    a=validate_144_correspondence(r)
    r["openings"].reverse()
    assert validate_144_correspondence(r)==a


def test_original_pdf_hash_required_before_compilation():
    with pytest.raises(ValueError,match="SHA"):
        original_six_crossresolution_source(
            b"invalid-original",source_sha256=sha256(b"different").hexdigest())
