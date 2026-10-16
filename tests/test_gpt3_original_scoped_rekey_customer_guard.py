"""Read-only regression: original Lot16 V1 scope-rekey is NOT customer authority.

Uses committed SHA-retained producer receipts, not frozen V2 gold or numerical
matching. The structural comparator is only a shadow diagnostic: passing it
cannot reissue host/frame provenance, create a customer row, or grant a score.
See GPT3 tracker #2297 architecture comment 6220116116 and #2004 audit.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_customer_output_verification import (
    CustomerOutputVerificationError,
    verify_sealed_customer_output,
)
from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    sealed_source_closed_run_from_dict,
)
from tools.source_report_scoped_equality import (
    equal_modulo_snapshot_scoped_ids,
    evidence_swap_matches,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = (
    ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
)
OWNER_SESSION = (
    ROOT / "docs/engineering/four_job_runs/20261016_47c8031a"
    / "au_qld_lot16_power/outputs/au_qld_lot16_power.json"
)
OLD_RUN_FP = "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
NEW_RUN_FP = "2e8333c7ee2642d8b0a6f533e5153d8642e595b554f04de5550fc4394b7e9a5f"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _receipts():
    old = _read(ARCHIVED / "source_sealed_run.json")
    new = _read(OWNER_SESSION)
    customers = _read(ARCHIVED / "verified_customer_rows.json")
    return old, new, customers


def _by_quantity(payload):
    return {item["quantity_id"]: item for item in payload["quantities"]}


def _body_without_derived_fingerprint(row):
    return {key: val for key, val in row.items() if key != "fingerprint"}


def test_old_and_new_source_envelopes_are_both_valid_but_not_interchangeable():
    old, new, _ = _receipts()
    old_run = sealed_source_closed_run_from_dict(old)
    new_run = sealed_source_closed_run_from_dict(new)
    assert old_run.project_id == new_run.project_id == "au_qld_lot16_power"
    assert old_run.fingerprint == OLD_RUN_FP
    assert new_run.fingerprint == NEW_RUN_FP
    assert old_run.run_id != new_run.run_id
    assert old_run.fingerprint != new_run.fingerprint
    assert len(old_run.quantities) == len(new_run.quantities) == 8
    # Each single-primary-PDF envelope is NOT proof of the entire two-PDF project kit.
    assert old_run.source_sha256s == new_run.source_sha256s
    assert len(new_run.source_sha256s) == 1


def test_exact_eight_physical_ids_and_every_non_rekey_field_are_preserved():
    old, new, _ = _receipts()
    prior, fresh = _by_quantity(old), _by_quantity(new)
    assert len(prior) == len(fresh) == 8
    assert prior.keys() == fresh.keys()
    physical_claims = set()
    for key in sorted(prior):
        earlier, later = prior[key], fresh[key]
        assert earlier["fingerprint"] != later["fingerprint"]
        assert earlier["object_identity_refs"] == later["object_identity_refs"]
        assert len(earlier["object_identity_refs"]) == 1
        assert earlier["object_identity_refs"][0] not in physical_claims
        physical_claims.add(earlier["object_identity_refs"][0])
        assert earlier["value"] == later["value"]
        assert earlier["unit"] == later["unit"]
        assert earlier["family"] == later["family"] == "opening_area"
        assert earlier["semantic_key"] == later["semantic_key"]
        assert earlier["project_id"] == later["project_id"]
        differing = {
            name for name in earlier
            if earlier[name] != later[name]
        }
        assert differing == {"fingerprint", "evidence_ids", "trace_evidence_ids"}
        assert equal_modulo_snapshot_scoped_ids(
            _body_without_derived_fingerprint(earlier),
            _body_without_derived_fingerprint(later),
        )
        assert evidence_swap_matches(earlier["evidence_ids"], later["evidence_ids"])
        assert evidence_swap_matches(earlier["trace_evidence_ids"], later["trace_evidence_ids"])
    assert len(physical_claims) == 8


def test_expected_eight_host_and_five_frame_scoped_changes_only():
    old, new, _ = _receipts()
    earlier, later = _by_quantity(old), _by_quantity(new)
    host_changes = frame_changes = 0
    for ident in earlier:
        old_ids = set(earlier[ident]["evidence_ids"])
        new_ids = set(later[ident]["evidence_ids"])
        removed = old_ids - new_ids
        added = new_ids - old_ids
        for prefix, expected in (("opening_host_binding_v3_", 1), ("opening_host_frame_v2_", None)):
            before = [x for x in removed if x.startswith(prefix)]
            after = [x for x in added if x.startswith(prefix)]
            assert len(before) == len(after)
            if expected is not None:
                assert len(before) == expected
        assert all(x.startswith(("opening_host_binding_v3_", "opening_host_frame_v2_"))
                   for x in removed | added)
        host_changes += len([x for x in removed if x.startswith("opening_host_binding_v3_")])
        frame_changes += len([x for x in removed if x.startswith("opening_host_frame_v2_")])
    assert host_changes == 8
    assert frame_changes == 5


def test_old_customer_rows_verify_only_against_the_old_source_run():
    old, new, customers = _receipts()
    verified = verify_sealed_customer_output(
        sealed_source_closed_run_from_dict(old), customers
    )
    assert verified.valid_quantity_count == verified.customer_row_count == 8
    assert len(verified.verified_quantity_ids) == 8
    assert {x["quantity_id"] for x in customers} == set(_by_quantity(old))
    assert all(x["inclusion_status"] == "PROVISIONAL" for x in customers)
    with pytest.raises(CustomerOutputVerificationError):
        verify_sealed_customer_output(
            sealed_source_closed_run_from_dict(new), customers
        )


def test_customer_persisted_evidence_matches_old_rows_not_new_rows():
    old, new, customers = _receipts()
    prior, fresh = _by_quantity(old), _by_quantity(new)
    for customer in customers:
        key = customer["quantity_id"]
        provenance = customer["commercial_projection_provenance"]
        assert provenance["quantity"]["evidence_ids"] == prior[key]["evidence_ids"]
        assert provenance["source_trace"]["evidence_ids"] == prior[key]["trace_evidence_ids"]
        assert provenance["quantity"]["evidence_ids"] != fresh[key]["evidence_ids"]
        assert provenance["source_trace"]["evidence_ids"] != fresh[key]["trace_evidence_ids"]


@pytest.mark.parametrize("mutation", (
    "different_numeric_value",
    "different_physical_object",
    "changed_source_observation",
    "second_host_added",
    "foreign_semantic_key",
))
def test_scoped_pattern_never_masks_an_unrelated_mutation(mutation):
    old, new, _ = _receipts()
    earlier, later = old["quantities"][0], deepcopy(new["quantities"][0])
    if mutation == "different_numeric_value":
        later["value"] += 1.0
    elif mutation == "different_physical_object":
        later["object_identity_refs"][0] += "_foreign"
    elif mutation == "changed_source_observation":
        position = next(i for i, ev in enumerate(later["evidence_ids"])
                        if ev.startswith("source_observation_"))
        later["evidence_ids"][position] += "_mutated"
    elif mutation == "second_host_added":
        later["evidence_ids"].append("opening_host_binding_v3_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        later["trace_evidence_ids"].append("opening_host_binding_v3_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    elif mutation == "foreign_semantic_key":
        later["semantic_key"] = "unrelated_claim:physical_opening_foreign"
    if mutation == "second_host_added":
        assert not evidence_swap_matches(earlier["evidence_ids"], later["evidence_ids"])
        assert not evidence_swap_matches(earlier["trace_evidence_ids"], later["trace_evidence_ids"])
    else:
        assert not equal_modulo_snapshot_scoped_ids(
            _body_without_derived_fingerprint(earlier),
            _body_without_derived_fingerprint(later),
        )


@pytest.mark.parametrize("damage", ("quantity_value", "quantity_fingerprint", "run_fingerprint"))
def test_sealed_loader_rejects_changed_original_source_receipts(damage):
    old, _, _ = _receipts()
    broken = deepcopy(old)
    if damage == "quantity_value":
        broken["quantities"][0]["value"] += 1.0
    elif damage == "quantity_fingerprint":
        broken["quantities"][0]["fingerprint"] = "0" * 64
    else:
        broken["fingerprint"] = "0" * 64
    with pytest.raises(SourceClosedRunConflictError):
        sealed_source_closed_run_from_dict(broken)
