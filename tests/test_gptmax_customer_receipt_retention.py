"""Customer projection receipts: positive exact-source and adverse tampering cases."""
from __future__ import annotations

import copy
import json

import pytest

from tools.verify_gptmax_customer_receipt_retention import verify_customer_receipt_rekeys

SHA = "1" * 64
OLD = "physical_opening_existence_original"
NEW = "physical_opening_existence_additive"
QOLD = "opening_area_original"
QNEW = "opening_area_additive"


def report(snapshot, *, additive=False):
    old_host = "opening_host_binding_v3_old" if not additive else "opening_host_binding_v3_new"
    old_wall = "old-wall" if not additive else "new-wall"
    old_frame = "opening_host_frame_v2_old" if not additive else "opening_host_frame_v2_new"
    bindings = [
        dict(opening_identity_id=OLD, status="corroborated",
             record_id=old_host, host_wall_id=old_wall,
             member_wall_candidate_ids=["wall-original"],
             member_candidate_identity_ids=["physical-original"],
             member_equivalence_groups=[["wall-original"]],
             reason_codes=["opening_host_binding_resolved"]),
        dict(opening_identity_id=NEW, status="corroborated" if additive else "abstained",
             record_id="new-additive-hb" if additive else None,
             host_wall_id="new-additive-wall" if additive else None,
             member_wall_candidate_ids=["left-supplement", "right-supplement"] if additive else [],
             member_candidate_identity_ids=["idleft", "idright"] if additive else [],
             member_equivalence_groups=[["left-supplement"], ["right-supplement"]] if additive else [],
             reason_codes=["opening_local_supplemental_source_band_host_resolved"] if additive else ["no_authenticated_host_wall_band"]),
    ]
    frames = [
        dict(opening_identity_id=OLD, status="corroborated",
             record_id=old_frame, host_wall_id=old_wall,
             source_geometry=[[0.0, 0.0], [10.0, 0.0]],
             reason_codes=["frame_corrob"]),
        dict(opening_identity_id=NEW, status="abstained",
             record_id=None, host_wall_id=None,
             source_geometry=[], reason_codes=["missing" if not additive else "whole_wall_unproven"]),
    ]
    return dict(
        source_sha256=SHA, primitive_safety_cap=20000,
        snapshot_id=snapshot,
        source_owned_wall_scopes=[dict(snapshot_id=snapshot, records=[
            {"wall_candidate_id": "wall-original",
             "physical_identity": {"edge_ids": ["edge-original"], "source_primitive_ids": ["s1"]}}
        ], decision_scope_id="wall-source:p3")],
        opening_bindings=bindings, host_frame_traces=frames,
    )


def customer(row_id, physical, snapshot, host, frame, wall):
    evidence = [host, *( [frame] if frame else [] ), "source_observation_original"]
    provenance = dict(
        quantity=dict(evidence_ids=evidence, quantity_id=row_id,
                      metadata=dict(host_binding_record_id=host,
                                    host_frame_record_id=frame,
                                    host_wall_id=wall, snapshot_id=snapshot,
                                    fixed_source_measurement="source-figured")),
        source_trace=dict(evidence_ids=evidence,
                          metadata=dict(host_wall_id=wall,
                                        source_kind="authentic-raster")),
        figured_dimensions=[1200, 1500],
    )
    return dict(
        quantity_id=row_id, quantity=1.8, unit="m2", source_sha256=SHA,
        canonical_entity_ids=[physical], quantity_status="To review",
        evidence_ids=evidence, commercial_projection_provenance=provenance,
        notes=json.dumps(provenance, sort_keys=True, separators=(",", ":")),
        commercial_projection_fingerprint="a" * 64,
        measurement_method="figured_dimension",
    )


def samples():
    old = report("snapshot-A")
    new = report("snapshot-B", additive=True)
    previous = customer(QOLD, OLD, "snapshot-A", "opening_host_binding_v3_old", "opening_host_frame_v2_old", "old-wall")
    changed = customer(QOLD, OLD, "snapshot-B", "opening_host_binding_v3_new", "opening_host_frame_v2_new", "new-wall")
    added = customer(QNEW, NEW, "snapshot-B", "new-additive-hb", None, "new-additive-wall")
    return [previous], [changed, added], old, new


def check(case):
    before, after, old, new = case
    return verify_customer_receipt_rekeys(
        before, after, old, new,
        expected_new_physical_id=NEW, expected_new_quantity_id=QNEW,
    )


def test_real_source_receipt_rekeys_keep_old_commercial_projection_exact():
    result = check(samples())
    assert result["previous_customers_preserved_except_authenticated_receipts"] == 1
    assert result["original_positive_frames_preserved"] == 1
    assert result["original_host_propositions_preserved"] == 1
    assert result["new_host_frame_still_abstained"] is True
    assert result["frozen_benchmark_matches_claimed"] == 0


@pytest.mark.parametrize("tamper", [
    "quantity", "unit", "source_sha", "source_observation",
    "figured_dimension", "physical_members", "lost_frame",
    "stale_notes", "archived_customer_receipt", "invented_new_frame",
    "unexpected_extra_row", "hidden_provenance_field", "safety_cap",
    "canonical_wall", "colliding_customer_id",
])
def test_any_unverified_original_source_or_customer_change_refused(tamper):
    case = copy.deepcopy(samples())
    before, after, old, new = case
    if tamper == "quantity":
        after[0]["quantity"] = 2.16
    elif tamper == "unit":
        after[0]["unit"] = "pcs"
    elif tamper == "source_sha":
        after[0]["source_sha256"] = "2" * 64
    elif tamper == "source_observation":
        after[0]["commercial_projection_provenance"]["source_trace"]["evidence_ids"][-1] = "invented-source"
        after[0]["notes"] = json.dumps(after[0]["commercial_projection_provenance"])
    elif tamper == "figured_dimension":
        after[0]["commercial_projection_provenance"]["figured_dimensions"] = [1200, 2100]
        after[0]["notes"] = json.dumps(after[0]["commercial_projection_provenance"])
    elif tamper == "physical_members":
        new["opening_bindings"][0]["member_wall_candidate_ids"] = ["invented-wall"]
    elif tamper == "lost_frame":
        new["host_frame_traces"][0]["record_id"] = None
    elif tamper == "stale_notes":
        after[0]["notes"] = before[0]["notes"]
    elif tamper == "archived_customer_receipt":
        before[0]["evidence_ids"][0] = "unmatched-old-archive-host"
    elif tamper == "invented_new_frame":
        new["host_frame_traces"][1]["record_id"] = "made-up-complete-frame"
    elif tamper == "unexpected_extra_row":
        after.append(customer("unauthorized-third", NEW, "snapshot-B", "new-additive-hb", None, "new-additive-wall"))
    elif tamper == "hidden_provenance_field":
        after[0]["commercial_projection_provenance"]["source_trace"]["metadata"]["unrelated_height"] = 2040
        after[0]["notes"] = json.dumps(after[0]["commercial_projection_provenance"])
    elif tamper == "safety_cap":
        new["primitive_safety_cap"] = 20001
    elif tamper == "canonical_wall":
        new["source_owned_wall_scopes"][0]["records"][0]["physical_identity"]["edge_ids"] = ["moved-original-wall"]
    elif tamper == "colliding_customer_id":
        after[1]["quantity_id"] = QOLD
    with pytest.raises(ValueError, match="customer original-source retention refused"):
        check(case)


def test_no_mutation_of_input_source_or_signed_rows():
    case = samples()
    before = copy.deepcopy(case)
    check(case)
    assert case == before
