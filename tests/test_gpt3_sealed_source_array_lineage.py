"""Sealed-run physical claims must be disjoint, not merely unequal sets."""
import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run, combine_source_closed_runs,
)
from test_source_closed_run_export import quantity, trace


def source_run(qid, identities, *, family="room_area", semantic="room.area", value=13.0):
    evidence=(f"evidence-{qid}",)
    qty=quantity(
        quantity_id=qid, family=family, semantic_key=semantic,
        value=value, input_entity_ids=identities, evidence_ids=evidence,
    )
    evidence_trace=trace(canonical_entity_ids=identities, evidence_ids=evidence)
    return seal_source_closed_run(
        [qty], project_id="project-a", traces_by_quantity_id={qid:evidence_trace}
    )


def test_ordinary_original_signed_source_remains_valid():
    original = source_run("qty-firm", ("physical-a", "physical-b"))
    assert original.quantities[0].lineage_ok
    combined = combine_source_closed_runs([original])
    assert combined.fingerprint == original.fingerprint


@pytest.mark.parametrize("field", [
    "object_identity_refs","trace_canonical_entity_ids",
    "evidence_ids","trace_evidence_ids",
])
def test_resigned_duplicate_source_receipts_cannot_enter_combined_seal(field):
    from dataclasses import replace
    good=source_run("qty-good",("physical-a",))
    row=good.quantities[0]
    original=getattr(row,field)
    bad=replace(row,**{field:(original[0],original[0])})
    recomputed=replace(good,quantities=(bad,))
    with pytest.raises(SourceClosedRunConflictError,match="noncanonical sealed source identity array"):
        combine_source_closed_runs([recomputed])


@pytest.mark.parametrize("field", [
    "object_identity_refs","trace_canonical_entity_ids",
    "evidence_ids","trace_evidence_ids",
])
def test_unsorted_recomputed_source_receipts_cannot_create_another_seal(field):
    from dataclasses import replace
    good=source_run("qty-good",("physical-a","physical-b"))
    row=good.quantities[0]
    values=getattr(row,field)
    # Evidence may have a single member; add a second source ID to prove
    # import-order canonicalization independently from the original producer.
    bad=replace(row,**{field:("source-z","source-a")})
    with pytest.raises(SourceClosedRunConflictError,match="noncanonical sealed source identity array"):
        combine_source_closed_runs([replace(good,quantities=(bad,))])


def test_exact_original_signed_receipt_arrays_preserve_sealed_run_fingerprint():
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    original=source_run("qty-firm",("physical-a","physical-b"))
    loaded=sealed_source_closed_run_from_dict(original.to_dict())
    assert loaded.fingerprint==original.fingerprint
    assert loaded.to_dict()==original.to_dict()


@pytest.mark.parametrize("new_ok,new_reasons", [
    (True, ("source_conflict",)),
    (False, ()),
])
def test_imported_seal_cannot_claim_contradictory_lineage_validity(new_ok,new_reasons):
    from dataclasses import replace
    original=source_run("qty-firm",("floor-a",))
    bad=replace(original.quantities[0],lineage_ok=new_ok,
                lineage_reason_codes=new_reasons)
    changed=replace(original,quantities=(bad,))
    with pytest.raises(SourceClosedRunConflictError,match="contradictory lineage validity receipt"):
        combine_source_closed_runs([changed])


def test_missing_physical_identity_cannot_be_resigned_as_complete_lineage():
    from dataclasses import replace
    original=source_run("qty-firm",("floor-a",))
    bad=replace(original.quantities[0],object_identity_refs=(),lineage_ok=True)
    changed=replace(original,quantities=(bad,))
    with pytest.raises(SourceClosedRunConflictError,match="falsely authenticates a missing physical identity"):
        combine_source_closed_runs([changed])
