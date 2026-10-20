"""Original source revision/selector must own every host and claimed frame."""
from copy import deepcopy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def test_source_owned_complete_host_and_frame_can_reach_diagnostic_review():
    rows, canonical = fixture()
    before=deepcopy((rows, canonical))
    r=run(rows,canonical)
    record=r["opening_decisions"][2]
    assert record["authenticated_host_record_id"] == "binding-3"
    assert record["authenticated_frame_record_id"] == "frame-3"
    assert record["new_gpt1_area_candidate_handoff"]
    assert record["measurement_published"] is False
    assert (rows,canonical)==before


@pytest.mark.parametrize("change", [
    lambda r,c: r[2]["physical_existence_record"].update(snapshot_id="foreign"),
    lambda r,c: r[2]["physical_existence_record"].update(
        status=EvidenceResolutionStatus.CANDIDATE),
    lambda r,c: r[2]["physical_existence_record"].update(proposition="guess"),
    lambda r,c: r[2]["physical_existence_record"].update(source_observation_ids=[]),
    lambda r,c: r[2]["attempted_host_selector"].update(revision_id="stale"),
    lambda r,c: r[2]["attempted_host_selector"].update(page_id="4"),
    lambda r,c: r[2]["attempted_host_selector"].update(opening_identity_id="other"),
    lambda r,c: r[2]["host_record"].update(source_sha256="0"*64),
    lambda r,c: r[2]["host_record"].update(document_id="foreign-document"),
    lambda r,c: r[2]["host_record"].update(decision_scope_id="other"),
    lambda r,c: r[2]["host_record"].update(page_id="9"),
    lambda r,c: r[2]["host_record"].update(source_observation_ids=[]),
    lambda r,c: r[2]["frame_record"]["selector"].update(source_sha256="0"*64),
    lambda r,c: r[2]["frame_record"]["selector"].update(snapshot_id="old"),
    lambda r,c: r[2]["frame_record"]["selector"].update(decision_scope_id="other"),
    lambda r,c: r[2]["frame_record"]["selector"].update(opening_identity_id="other"),
])
def test_stale_issuer_host_frame_or_original_existence_fails_closed(change):
    rows,canonical=fixture()
    change(rows,canonical)
    with pytest.raises(ValueError):
        run(rows,canonical)


def test_hostless_original_physical_opening_remains_abstained_not_deleted():
    rows,canonical=fixture()
    r=run(rows,canonical)
    entry=r["opening_decisions"][0]
    assert entry["first_remaining_gate"] == "structural_host_unavailable"
    assert entry["authenticated_host_record_id"] is None
    assert entry["authenticated_frame_record_id"] is None
    assert entry["new_gpt1_area_candidate_handoff"] is False


def test_host_only_original_figure_still_does_not_require_3d_frame():
    rows,canonical=fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    r=run(rows,canonical)
    d=r["opening_decisions"][2]
    assert d["new_gpt1_area_candidate_handoff"]
    assert d["first_remaining_gate"] == "whole_wall_frame_unavailable"
    assert not d["measurement_published"] and not d["opening_count_granted"]


def test_independent_source_scope_validation_keeps_order_invariance():
    rows,canonical=fixture()
    before=deepcopy((rows,canonical))
    a=run(rows,canonical)
    b=run(list(reversed(rows)),list(reversed(canonical)))
    assert a==b and before==(rows,canonical)
