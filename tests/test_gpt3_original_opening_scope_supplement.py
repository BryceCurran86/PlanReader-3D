"""Producer-scoped GPT3 sidecar protects snapshot and decision authority v1 misses."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from hashlib import sha256
import json

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_gpt3_original_opening_scope_supplement import (
    ProducerScopeLineageConflict,
    source_owned_opening_scope_supplement,
    verify_source_owned_opening_scope_supplement,
    scope_supplement_from_live_source_producer,
)
from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_source_traces, seal_live_opening_area_run,
)
from pb_live_wall_opening_authority_composition import (
    LiveOpeningHostTrace, LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingRecord, OpeningHostBindingSelector,
)
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, quantities_to_takeoff_output_rows,
)
from tests.test_live_opening_area_quantity_publication import (
    _composition, _opening,
)


def _issued_original_source(*, two=False):
    source_members = [_opening(canonical_id="opening-1")]
    if two:
        second = _opening(canonical_id="opening-2", kind="door",
                          area_m2=2.16, figured_area_record_id="figured-2")
        source_members.append(replace(
            second,
            representative_observation_id="observation-2",
            source_observation_ids=("observation-2",),
            host_wall_id="wall-2",
            host_binding_record_id="binding-2",
            host_frame_record_id="frame-2",
            evidence_ids=("opening-2", "observation-2", "binding-2",
                          "frame-2", "figured-2"),
        ))
    comp = _composition(*source_members)
    quantities = publish_live_opening_area_quantities(comp)
    traces = build_live_opening_area_source_traces(
        comp, workspace_id=2, project_id="scope-synthetic"
    )
    authorities = {
        q.quantity_id: CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=(q.metadata["measurement_record_id"],),
        ) for q in quantities
    }
    customer = quantities_to_takeoff_output_rows(
        quantities, traces_by_quantity_id=traces,
        authorities_by_quantity_id=authorities,
    )
    run = seal_live_opening_area_run(
        comp, workspace_id=2, project_id="scope-synthetic"
    )
    verified = verify_sealed_customer_output(run, customer)
    assert len(verified.verified_quantity_ids) == len(quantities)
    selectors = {
        item.physical_opening_id: OpeningHostBindingSelector(
            document_id=item.document_id,
            revision_id=item.revision_id,
            source_sha256=item.source_sha256,
            snapshot_id=item.snapshot_id,
            page_id=item.page_id,
            decision_scope_id=f"original-producer-scope:page-{item.page_id}",
            opening_identity_id=item.physical_opening_id,
        ) for item in source_members
    }
    hosts = tuple(
        LiveOpeningHostTrace(
            opening_identity_id=item.physical_opening_id,
            representative_observation_id=item.representative_observation_id,
            page_id=item.page_id,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("source_host_binding_corroborated",),
            record_id=item.host_binding_record_id,
            host_wall_id=item.host_wall_id,
            member_wall_candidate_ids=("owned-wall-1",),
        ) for item in source_members
    )
    return {
        "composition": comp, "producer_binding_selectors": selectors,
        "producer_host_traces": hosts, "sealed_run": run,
        "customer_rows": customer,
    }


def _issue(ctx):
    return source_owned_opening_scope_supplement(**ctx)


def test_single_original_source_scope_sidecar_signs_without_v1_mutation():
    ctx = _issued_original_source()
    original_v1 = ctx["sealed_run"].to_dict()
    original_customer = deepcopy(ctx["customer_rows"])
    original = _issue(ctx)
    assert original["schema_version"] == "gpt3.opening_producer_scope.v1"
    assert original["parent_v1_source_closed_fingerprint"] == original_v1["fingerprint"]
    assert original["producer_scope_entries"][0]["snapshot_id"] == "snap-1"
    assert original["producer_scope_entries"][0][
        "v1_customer_projection_fingerprint"
    ] == original_customer[0]["commercial_projection_fingerprint"]
    assert original["producer_scope_entries"][0]["decision_scope_id"] == (
        "original-producer-scope:page-3"
    )
    assert original["benchmark_identity_mapping_authorized"] is False
    assert original["customer_release_authorized"] is False
    assert ctx["sealed_run"].to_dict() == original_v1
    assert ctx["customer_rows"] == original_customer
    verify_source_owned_opening_scope_supplement(original, **ctx)
    assert original == _issue(ctx)


def test_two_real_source_quantities_can_share_page_scope_without_identity_alias():
    ctx = _issued_original_source(two=True)
    sidecar = _issue(ctx)
    assert len(sidecar["producer_scope_entries"]) == 2
    assert len(set(item["quantity_id"] for item in sidecar["producer_scope_entries"])) == 2
    assert len(set(item["physical_opening_id"] for item in sidecar["producer_scope_entries"])) == 2
    assert {item["decision_scope_id"] for item in sidecar["producer_scope_entries"]} == {
        "original-producer-scope:page-3"
    }
    verify_source_owned_opening_scope_supplement(sidecar, **ctx)


@pytest.mark.parametrize("mutate", [
    lambda x: x["producer_scope_entries"][0].update(snapshot_id="old-snapshot"),
    lambda x: x["producer_scope_entries"][0].update(
        decision_scope_id="wall-source:foreign-scope"),
    lambda x: x["producer_scope_entries"][0].update(
        representative_observation_id="unrelated-original-word"),
    lambda x: x.update(parent_v1_source_closed_fingerprint="0" * 64),
    lambda x: x.update(customer_release_authorized=True),
    lambda x: x["producer_scope_entries"][0].update(host_binding_record_id="borrowed-host"),
    lambda x: x["producer_scope_entries"][0].update(
        v1_customer_projection_fingerprint="a" * 64),
    lambda x: x["producer_scope_entries"][0].update(
        v1_signed_quantity_fingerprint="f" * 64),
    lambda x: x["producer_scope_entries"].append(
        deepcopy(x["producer_scope_entries"][0])),
    lambda x: x["producer_scope_entries"].clear(),
    lambda x: x.update(original_verified_customer_quantity_ids=[]),
])
def test_forged_source_scope_sidecar_rejected_even_with_recomputed_fingerprint(mutate):
    ctx = _issued_original_source()
    sidecar = _issue(ctx)
    mutate(sidecar)
    payload = {k: v for k, v in sidecar.items() if k != "fingerprint"}
    # An adversary can recompute a digest, but not re-create the producer's
    # exact selectors, signed v1 quantity receipts or verified customer rows.
    from pb_migration_contracts import canonical_contract_json
    sidecar["fingerprint"] = sha256(
        canonical_contract_json(payload).encode()
    ).hexdigest()
    with pytest.raises(ProducerScopeLineageConflict):
        verify_source_owned_opening_scope_supplement(sidecar, **ctx)


@pytest.mark.parametrize("mutate", [
    lambda ctx: ctx["producer_binding_selectors"].pop("opening-1"),
    lambda ctx: ctx["producer_binding_selectors"].update(
        {"foreign-opening": next(iter(ctx["producer_binding_selectors"].values()))}
    ),
    lambda ctx: ctx["producer_binding_selectors"].update({
        "opening-1": replace(
            ctx["producer_binding_selectors"]["opening-1"],
            snapshot_id="source_snapshot_older"),
    }),
    lambda ctx: ctx["producer_binding_selectors"].update({
        "opening-1": replace(
            ctx["producer_binding_selectors"]["opening-1"],
            decision_scope_id=""),
    }),
    lambda ctx: ctx["producer_binding_selectors"].update({
        "opening-1": replace(
            ctx["producer_binding_selectors"]["opening-1"],
            opening_identity_id="foreign-opening"),
    }),
    lambda ctx: ctx.update(producer_host_traces=()),
    lambda ctx: ctx.update(producer_host_traces=ctx["producer_host_traces"] * 2),
    lambda ctx: ctx.update(producer_host_traces=(
        replace(ctx["producer_host_traces"][0], record_id="foreign-host"),)),
    lambda ctx: ctx.update(producer_host_traces=(
        replace(ctx["producer_host_traces"][0],
                status=EvidenceResolutionStatus.ABSTAINED),)),
])
def test_invalid_producer_scope_or_host_authority_fails_closed(mutate):
    ctx = _issued_original_source()
    with pytest.raises((ProducerScopeLineageConflict, ValueError)):
        mutate(ctx)
        _issue(ctx)


def test_customer_change_without_new_v1_seal_never_becomes_scope_proof():
    ctx = _issued_original_source()
    ctx["customer_rows"][0]["quantity"] = 55.0
    with pytest.raises((ValueError, RuntimeError)):
        _issue(ctx)


def test_altered_canonical_snapshot_with_old_selector_rejected():
    ctx = _issued_original_source()
    member = ctx["composition"].canonical_openings[0]
    ctx["composition"] = replace(
        ctx["composition"],
        canonical_openings=(replace(member, snapshot_id="snap-stale"),)
    )
    with pytest.raises(ProducerScopeLineageConflict):
        _issue(ctx)


def test_reject_canonical_duplicate_source_opening_even_when_one_is_unissued():
    ctx = _issued_original_source()
    member = ctx["composition"].canonical_openings[0]
    unresolved = replace(member, opening_kind=None, area_m2=None)
    ctx["composition"] = replace(
        ctx["composition"], canonical_openings=(member, unresolved)
    )
    with pytest.raises((ValueError, ProducerScopeLineageConflict)):
        _issue(ctx)


def test_sidecar_syntax_cannot_escape_source_owner_through_string_json():
    ctx = _issued_original_source()
    original = _issue(ctx)
    with pytest.raises(ProducerScopeLineageConflict):
        verify_source_owned_opening_scope_supplement(
            json.dumps(original), **ctx,
        )


def test_original_customer_projection_fingerprint_cannot_be_forged_or_reused():
    ctx = _issued_original_source(two=True)
    supplement = _issue(ctx)
    by_id = {
        row["quantity_id"]: row["v1_customer_projection_fingerprint"]
        for row in supplement["producer_scope_entries"]
    }
    assert len(by_id) == 2
    assert set(by_id.values()) == {
        row["commercial_projection_fingerprint"] for row in ctx["customer_rows"]
    }
    # Customer mutation must fail even if another valid signed customer row
    # exists; exact provenance is bound to its own physical quantity ID.
    ctx["customer_rows"][0]["commercial_projection_fingerprint"] = (
        ctx["customer_rows"][1]["commercial_projection_fingerprint"]
    )
    with pytest.raises((ValueError, RuntimeError)):
        _issue(ctx)



def _live_producer_composition(ctx, *, wrong: str | None = None):
    """Source-neutral typed test doubles, NOT original client PDF authority."""
    receipts = {}
    for physical_id, selector in ctx["producer_binding_selectors"].items():
        member = next(
            x for x in ctx["composition"].canonical_openings
            if x.physical_opening_id == physical_id
        )
        receipts[physical_id] = OpeningHostBindingRecord(
            record_id=member.host_binding_record_id,
            document_id=member.document_id,
            revision_id=member.revision_id,
            source_sha256=member.source_sha256,
            snapshot_id=member.snapshot_id,
            page_id=member.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=member.physical_opening_id,
            host_wall_id=member.host_wall_id,
            member_wall_candidate_ids=(f"candidate-{physical_id}",),
            member_candidate_identity_ids=(f"wall-member-{physical_id}",),
            member_equivalence_groups=((f"wall-member-{physical_id}",),),
            source_observation_ids=member.source_observation_ids,
        )
    if wrong == "foreign_scope":
        first = next(iter(receipts))
        receipts[first] = replace(
            receipts[first], decision_scope_id="foreign-w4-source")
    if wrong == "foreign_host":
        first = next(iter(receipts))
        receipts[first] = replace(
            receipts[first], host_wall_id="borrowed-wall")
    if wrong == "source_snapshot":
        first = next(iter(receipts))
        receipts[first] = replace(
            receipts[first], snapshot_id="old-source-snapshot")

    class OriginalHostAuthority:
        def resolve(self, selector):
            if wrong == "host_abstain":
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED, record=None
                )
            if wrong == "resolver_exception":
                raise ValueError("issuer refuses forged selector")
            return SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                record=receipts[selector.opening_identity_id],
            )

    return LiveWallOpeningAuthorityComposition(
        revision_id=ctx["composition"].revision_id,
        page_ids=("3",),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(),
        semantic_enumeration_result=None,
        opening_universe_result=None,
        opening_universe_results={},
        wall_scopes=(),
        opening_bindings=ctx["producer_host_traces"],
        host_frames=(),
        physical_wall_candidate_authority=None,
        physical_opening_authority=None,
        semantic_opening_enumeration_authority=None,
        opening_universe_completeness_authority=None,
        opening_universe_completeness_authorities={},
        opening_host_binding_authority=OriginalHostAuthority(),
        opening_host_frame_authority=None,
        binding_selectors=ctx["producer_binding_selectors"],
        host_frame_selectors={},
    )


def test_original_host_producer_reproves_scope_before_signed_sidecar():
    ctx = _issued_original_source(two=True)
    wall_producer = _live_producer_composition(ctx)
    sidecar = scope_supplement_from_live_source_producer(
        opening_composition=ctx["composition"],
        wall_composition=wall_producer,
        sealed_run=ctx["sealed_run"],
        customer_rows=ctx["customer_rows"],
    )
    assert sidecar == _issue(ctx)
    assert len(sidecar["producer_scope_entries"]) == 2


@pytest.mark.parametrize("wrong", [
    "foreign_scope", "foreign_host", "source_snapshot",
    "host_abstain", "resolver_exception",
])
def test_actual_host_binding_issuer_disagreement_never_issues_scope_sidecar(wrong):
    ctx = _issued_original_source()
    wall_producer = _live_producer_composition(ctx, wrong=wrong)
    with pytest.raises((ValueError, RuntimeError)):
        scope_supplement_from_live_source_producer(
            opening_composition=ctx["composition"],
            wall_composition=wall_producer,
            sealed_run=ctx["sealed_run"],
            customer_rows=ctx["customer_rows"],
        )


def test_source_producer_revision_change_cannot_rebind_signed_quantity():
    ctx = _issued_original_source()
    wall_producer = replace(
        _live_producer_composition(ctx), revision_id="foreign-revision",
    )
    with pytest.raises(ProducerScopeLineageConflict, match="revision"):
        scope_supplement_from_live_source_producer(
            opening_composition=ctx["composition"],
            wall_composition=wall_producer,
            sealed_run=ctx["sealed_run"],
            customer_rows=ctx["customer_rows"],
        )


def test_caller_plain_json_cannot_stand_in_for_the_original_source_producer():
    ctx = _issued_original_source()
    fake_producer = SimpleNamespace(
        binding_selectors=ctx["producer_binding_selectors"],
        opening_bindings=ctx["producer_host_traces"],
        revision_id=ctx["composition"].revision_id,
    )
    with pytest.raises(TypeError, match="original live wall"):
        scope_supplement_from_live_source_producer(
            opening_composition=ctx["composition"],
            wall_composition=fake_producer,
            sealed_run=ctx["sealed_run"],
            customer_rows=ctx["customer_rows"],
        )
