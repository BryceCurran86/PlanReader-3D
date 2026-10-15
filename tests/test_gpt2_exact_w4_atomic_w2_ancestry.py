"""Exact original W4->W2 ancestry cannot mint a source wall or room."""
from types import SimpleNamespace as N

from tools.diag_gpt2_exact_w4_atomic_w2_ancestry import (
    inspect_original_w4_atomic_w2_ancestry as inspect,
)

ATOM=((0.,0.),(10.,0.))


def frag(edge_id, geometry=(0.,0.,10.,0.), parents=("native_1",)):
    return N(edge_id=edge_id, geometry=geometry, source_primitive_ids=parents)


def record(*, wall_id="wall_a", fragments=None, parents=("native_1",)):
    if fragments is None:
        fragments=(frag("w2_1"),)
    identity=N(usable=True,wall_candidate_id=wall_id,
               edge_ids=tuple(f.edge_id for f in fragments),
               source_primitive_ids=parents)
    return N(wall_candidate_id=wall_id,source_edge_fragments=fragments,
             physical_identity=identity)


def run(records):
    return inspect(N(records=records),
                   original_w4_wall_id="wall_a",atomic_edge=ATOM)


def test_single_exact_source_lineage_is_observation_not_wall_authority():
    row=run((record(),))
    assert row["status"]=="one_original_w2_source_fragment_observed"
    assert row["matched_source_w2_edge_count"]==1
    receipt=row["w2_source_fragment_full_edge_receipts"][0]
    assert receipt["original_native_source_primitive_ids"]==["native_1"]
    assert receipt["original_atomic_edge_fully_covered_by_w2"] is True
    assert row["candidate_only_no_wall_or_room_authority"] is True
    assert row["physical_wall_role_or_w4_equivalence_proven"] is False
    assert row["physical_room_closed_or_metric_quantity_published"] is False


def test_same_w4_address_collision_abstains_instead_of_first_candidate():
    a=record()
    assert run((a,a))["status"]=="original_w4_candidate_collision"


def test_multiple_source_edges_are_reported_without_election():
    f=(frag("w2_left",(0.,0.,6.,0.),("native_1",)),
       frag("w2_right",(6.,0.,10.,0.),("native_2",)))
    row=run((record(fragments=f,parents=("native_1","native_2")),))
    assert row["status"]=="plural_original_w2_source_fragments_observed"
    assert row["matched_source_w2_edge_count"]==2
    assert not row["w2_source_fragment_full_edge_receipts"]
    assert len(row["w2_source_fragment_partial_overlap_receipts"])==2
    assert row["original_source_primitive_universe_proven_complete"] is False


def test_invalid_parent_claim_and_duplicate_w2_identity_fail_closed():
    wrong=record(fragments=(frag("w2_1",parents=("foreign",)),))
    assert run((wrong,))["status"]=="original_w2_source_ancestry_conflict"
    one=frag("duplicate")
    two=frag("duplicate",(0.,0.,8.,0.))
    assert run((record(fragments=(one,two)),))["status"]==(
        "duplicate_surviving_w2_source_identity"
    )


def test_reject_nonfinite_or_zero_length_source_fragments():
    bad=record(fragments=(frag("w2_1",(0.,0.,float("nan"),0.)),))
    assert run((bad,))["status"]=="original_w2_source_ancestry_conflict"
    short=record(fragments=(frag("w2_1",(1.,0.,1.,0.)),))
    assert run((short,))["status"]=="original_w2_source_ancestry_conflict"


def test_unowned_w4_and_empty_source_fragment_never_publish():
    assert run(())["status"]=="original_w4_candidate_missing"
    assert run((record(fragments=()),))["status"]==(
        "original_w4_physical_identity_unverified"
    )
    assert inspect(N(records=(record(),)),original_w4_wall_id="wall_a",
                   atomic_edge=((0.,0.),(0.,0.)))["status"]==(
        "invalid_exact_original_w4_query"
    )
