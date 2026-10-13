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


def _production_scope_samples():
    """The all-pages diagnostic IDs intentionally differ from the signed page-3 producer."""
    before, after, stage_old, stage_new = copy.deepcopy(samples())
    production_old_snapshot = "source_snapshot_production_old"
    production_new_snapshot = "source_snapshot_production_new"
    before[0] = customer(
        QOLD, OLD, production_old_snapshot, "opening_host_binding_v3_production_old",
        "opening_host_frame_v2_production_old", "opening_host_binding_group_production_old",
    )
    after[0] = customer(
        QOLD, OLD, production_new_snapshot, "opening_host_binding_v3_production_new",
        "opening_host_frame_v2_production_new", "opening_host_binding_group_production_new",
    )

    def source_opening(physical, snapshot, row=None):
        p = row["commercial_projection_provenance"]["quantity"]["metadata"] if row else {}
        return {
            "physical_opening_id": physical,
            "canonical_opening_id": physical,
            "snapshot_id": snapshot,
            "source_sha256": SHA,
            "source_geometries": [[1.0, 2.0, 3.0, 4.0]],
            "source_observation_ids": ["source_observation_original"],
            "host_binding_record_id": p.get("host_binding_record_id"),
            "host_frame_record_id": p.get("host_frame_record_id"),
            "host_wall_id": p.get("host_wall_id"),
            "evidence_ids": list(row["evidence_ids"]) if row else ["source_observation_original"],
        }

    def seal(row):
        provenance = row["commercial_projection_provenance"]
        return {
            "quantity_id": row["quantity_id"],
            "source_sha256": SHA,
            "object_identity_refs": list(row["canonical_entity_ids"]),
            "evidence_ids": list(provenance["quantity"]["evidence_ids"]),
            "trace_evidence_ids": list(provenance["source_trace"]["evidence_ids"]),
        }

    prod_old = [source_opening(OLD, production_old_snapshot, before[0]),
                source_opening(NEW, production_old_snapshot)]
    prod_new = [source_opening(OLD, production_new_snapshot, after[0]),
                source_opening(NEW, production_new_snapshot, after[1])]
    old_seal = [seal(before[0])]
    new_seal = [seal(row) for row in after]
    return before, after, stage_old, stage_new, prod_old, prod_new, old_seal, new_seal


def _check_production_scope(case):
    before, after, old, new, prod_old, prod_new, seal_old, seal_new = case
    return verify_customer_receipt_rekeys(
        before, after, old, new,
        expected_new_physical_id=NEW, expected_new_quantity_id=QNEW,
        baseline_production_openings=prod_old,
        candidate_production_openings=prod_new,
        baseline_sealed_quantities=seal_old,
        candidate_sealed_quantities=seal_new,
    )


def test_original_production_claim_receipts_may_differ_from_diagnostic_scope():
    case = _production_scope_samples()
    # The older verifier correctly refuses nonmatching all-pages diagnostic
    # receipts; accepting the actual original page-3 receipts requires extra
    # producer-owned evidence, not weakening the default-deny path.
    with pytest.raises(ValueError, match="nested commercial provenance altered"):
        before, after, old, new, *_ = case
        verify_customer_receipt_rekeys(
            before, after, old, new,
            expected_new_physical_id=NEW, expected_new_quantity_id=QNEW,
        )
    accepted = _check_production_scope(case)
    assert accepted["previous_customers_preserved_except_authenticated_receipts"] == 1


@pytest.mark.parametrize("tamper", [
    "physical_geometry", "producer_wall", "producer_binding",
    "signed_host_evidence", "changed_measurement", "producer_snapshot",
    "sealed_physical_id", "new_frame_lost",
])
def test_production_receipt_requires_exact_signed_original_source(tamper):
    case = copy.deepcopy(_production_scope_samples())
    before, after, old, new, prod_old, prod_new, seal_old, seal_new = case
    if tamper == "physical_geometry":
        prod_new[0]["source_geometries"] = [[11.0, 12.0, 13.0, 14.0]]
    elif tamper == "producer_wall":
        prod_new[0]["host_wall_id"] = "opening_host_binding_group_unverified"
    elif tamper == "producer_binding":
        prod_new[0]["host_binding_record_id"] = "opening_host_binding_v3_unverified"
    elif tamper == "signed_host_evidence":
        seal_new[0]["evidence_ids"][0] = "opening_host_binding_v3_forged"
    elif tamper == "changed_measurement":
        after[0]["commercial_projection_provenance"]["figured_dimensions"] = [1300, 1500]
        after[0]["notes"] = json.dumps(after[0]["commercial_projection_provenance"])
    elif tamper == "producer_snapshot":
        prod_new[0]["snapshot_id"] = "different-source-snapshot"
    elif tamper == "sealed_physical_id":
        seal_new[0]["object_identity_refs"] = [NEW]
    elif tamper == "new_frame_lost":
        prod_new[0]["host_frame_record_id"] = None
    with pytest.raises(ValueError, match="customer original-source retention refused"):
        _check_production_scope(case)


def test_incomplete_production_scope_evidence_fails_closed():
    case = _production_scope_samples()
    before, after, old, new, prod_old, *_ = case
    with pytest.raises(ValueError, match="incomplete production-scope"):
        verify_customer_receipt_rekeys(
            before, after, old, new,
            expected_new_physical_id=NEW, expected_new_quantity_id=QNEW,
            baseline_production_openings=prod_old,
        )


def test_production_scope_verification_is_read_only():
    case = _production_scope_samples()
    copy_original = copy.deepcopy(case)
    _check_production_scope(case)
    assert case == copy_original


def _different_stage_and_production_snapshots():
    """Model exact Lot16: all-pages and page-3 source runs hash different scopes."""
    case = copy.deepcopy(_production_scope_samples())
    before, after, _old_stage, _new_stage, prod_old, prod_new, _, _ = case
    for rows, openings, new_snapshot in (
        (before, prod_old, "source_snapshot_prod_before"),
        (after, prod_new, "source_snapshot_prod_after"),
    ):
        for opening in openings:
            opening["snapshot_id"] = new_snapshot
        for row in rows:
            provenance = row["commercial_projection_provenance"]
            provenance["quantity"]["metadata"]["snapshot_id"] = new_snapshot
            row["notes"] = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
    return case


def test_different_stage_and_original_production_snapshot_pairs_are_not_conflated():
    case = _different_stage_and_production_snapshots()
    old, new, old_stage, new_stage, prod_old, prod_new, *_ = case
    assert old_stage["snapshot_id"] != prod_old[0]["snapshot_id"]
    assert new_stage["snapshot_id"] != prod_new[0]["snapshot_id"]
    result = _check_production_scope(case)
    assert result["previous_customers_preserved_except_authenticated_receipts"] == 1


@pytest.mark.parametrize("tamper", [
    "production_universe_split_snapshot",
    "customer_stale_production_snapshot",
    "production_snapshot_reused",
    "production_snapshot_prefix",
    "physical_source_sha_changed",
])
def test_distinct_source_snapshot_scope_still_fails_closed_on_tampering(tamper):
    case = _different_stage_and_production_snapshots()
    before, after, _old_stage, _new_stage, prod_old, prod_new, *_ = case
    if tamper == "production_universe_split_snapshot":
        prod_new[1]["snapshot_id"] = "source_snapshot_unrelated"
    elif tamper == "customer_stale_production_snapshot":
        after[0]["commercial_projection_provenance"]["quantity"]["metadata"]["snapshot_id"] = prod_old[0]["snapshot_id"]
        after[0]["notes"] = json.dumps(after[0]["commercial_projection_provenance"])
    elif tamper == "production_snapshot_reused":
        for opening in prod_new:
            opening["snapshot_id"] = prod_old[0]["snapshot_id"]
    elif tamper == "production_snapshot_prefix":
        for opening in prod_old:
            opening["snapshot_id"] = "not-an-authenticated-source-snapshot"
    elif tamper == "physical_source_sha_changed":
        prod_new[0]["source_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="customer original-source retention refused"):
        _check_production_scope(case)
