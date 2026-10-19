"""GPT3 independently checks MAX area review against actual opening publication."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import ROOT, fixture, run
from tests.test_live_opening_area_quantity_publication import (
    _composition, _opening,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_source_traces, seal_live_opening_area_run,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, quantities_to_takeoff_output_rows,
)
from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
import tools.diag_gpt3_max_area_review_source_issuer_bijection as issuer_audit
from tools.diag_gpt3_max_area_review_source_issuer_bijection import (
    SourceIssuerConvergenceConflict, audit_max_area_review_against_live_issuer,
)
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    verify_archived_signed_predecessors,
)


ARCHIVE = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production")
PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
ORIGINAL_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _source_opening(identifier, *, frame=None, area=None, area_receipt=None,
                    original_host=None):
    opening = _opening(
        canonical_id=identifier, kind="window" if area is not None else None,
        area_m2=area, figured_area_record_id=area_receipt,
    )
    evidence = [identifier, "source-observation-1"]
    if original_host:
        evidence.append(original_host)
    if frame:
        evidence.append(frame)
    if area_receipt:
        evidence.append(area_receipt)
    return replace(
        opening,
        document_id=ROOT["document_id"],
        revision_id=ROOT["revision_id"],
        source_sha256=ROOT["source_sha256"],
        snapshot_id=ROOT["snapshot_id"],
        page_id="3",
        host_wall_id="wall-grp" if original_host else None,
        host_binding_record_id=original_host,
        host_frame_record_id=frame,
        area_basis="figured_opening_label" if area is not None else None,
        viewport_id="source_plan_view_source_example",
        evidence_ids=tuple(evidence),
    )


def _original_review(*, frame="frame-3", issuer_positive=False):
    rows, canonical = fixture()
    if frame is None:
        rows[2]["frame_record"] = None
        canonical[2]["host_frame_record_id"] = None
    result = run(rows, canonical)
    if frame is None:
        # Equivalent to the pending MAX #3377 host-only AREA gate. This
        # fixture never claims a source-published quantity from that boolean.
        last = result["opening_decisions"][2]
        last["opening_area_first_remaining_gate"] = (
            "independent_gpt1_opening_area_measurement_validation_required"
        )
        last["new_gpt1_area_candidate_handoff"] = True
        last["figured_area_only_frame_unavailable"] = True
        result["gpt1_new_area_review_candidates"] = [deepcopy(last)]
    members = [
        _source_opening("physical-1"),
        _source_opening("physical-2", original_host="binding-2"),
        _source_opening(
            "physical-3", frame=frame, original_host="binding-3",
            area=2.16, area_receipt="figured",
        ),
    ]
    if not issuer_positive:
        # Even when the MAX advisory says "review", the publisher needs its
        # own full original observation provenance; do not infer it.
        members[2] = replace(
            members[2],
            evidence_ids=tuple(
                rid for rid in members[2].evidence_ids
                if rid != members[2].representative_observation_id
            ),
        )
    composition = replace(_composition(*members),
                          revision_id=ROOT["revision_id"])
    return result, composition


@pytest.mark.parametrize("frame", ("frame-3", None))
def test_max_unsigned_candidate_cannot_mask_real_source_issuer_disagreement(frame):
    report, composition = _original_review(frame=frame, issuer_positive=True)
    produced = publish_live_opening_area_quantities(composition)
    assert len(produced) == 1 and produced[0].value == 2.16
    assert produced[0].metadata["host_frame_record_id"] == frame
    # MAX's actual source observer would have included this quantity ID and
    # excluded its owner from the unsigned "new area review" queue. A false
    # unsigned observer must stop the release report, NOT score a ninth.
    with pytest.raises(SourceIssuerConvergenceConflict,
                       match="source issuer receipt"):
        audit_max_area_review_against_live_issuer(report, composition)


def test_advisory_source_review_without_actual_issuer_is_not_quantity():
    report, composition = _original_review(issuer_positive=False)
    assert publish_live_opening_area_quantities(composition) == ()
    result = audit_max_area_review_against_live_issuer(report, composition)
    assert result["review_candidates"][0]["status"] == (
        "REVIEW_ONLY_SOURCE_ISSUER_UNAVAILABLE"
    )
    assert result["real_producer_issued_opening_area_count"] == 0
    assert result["source_verified_new_quantity_count"] == 0


@pytest.mark.parametrize("mutate", [
    lambda r, c: r["opening_decisions"][2].update(
        authenticated_host_record_id="foreign-host"),
    lambda r, c: r["opening_decisions"][2].update(
        figured_area_receipt_bound=False),
    lambda r, c: r["opening_decisions"][2].update(
        prior_signed_quantity_id="previously-signed"),
    lambda r, c: r["opening_decisions"][2].update(
        customer_seal_granted=True),
    lambda r, c: r["opening_decisions"][2].update(
        snapshot_id="foreign-snapshot"),
    lambda r, c: r.update(original_physical_opening_count=2),
    lambda r, c: r["opening_decisions"].append(
        deepcopy(r["opening_decisions"][0])),
    lambda r, c: r["gpt1_new_area_review_candidates"].clear(),
    lambda r, c: r.update(global_opening_count_granted=True),
])
def test_forged_source_review_cannot_launder_issuer_or_firm_status(mutate):
    report, composition = _original_review()
    mutate(report, composition)
    with pytest.raises(SourceIssuerConvergenceConflict):
        audit_max_area_review_against_live_issuer(report, composition)


def _original_archive():
    sealed = json.loads((ARCHIVE / "source_sealed_run.json").read_text())
    customers = json.loads((ARCHIVE / "verified_customer_rows.json").read_text())
    return sealed, customers


def test_historical_exact_eight_signed_and_customer_bodies_are_verified():
    original, customers = _original_archive()
    assert len(original["quantities"]) == len(customers) == 8
    retention = {"sealed_run": deepcopy(original),
                 "customer_rows": deepcopy(customers)}
    verify_archived_signed_predecessors(original, customers, retention)
    assert original["fingerprint"] == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )
    original_ids = {q["quantity_id"] for q in original["quantities"]}
    assert original_ids == {q["quantity_id"] for q in customers}
    # The original REAL source-signed 1215 opening already occupies one of
    # the eight. That receipt has a host WITHOUT a 3D whole-wall frame.
    row = next(
        q for q in customers
        if q["canonical_entity_ids"] == [
            "physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9"
        ]
    )
    source_quantity = row["commercial_projection_provenance"]["quantity"]
    assert source_quantity["value"] == 1.8
    assert source_quantity["metadata"]["host_binding_record_id"]
    assert source_quantity["metadata"]["host_frame_record_id"] is None


@pytest.mark.parametrize("mutated", ("quantity_value", "customer_body", "missing_id"))
def test_original_eight_unchanged_ids_do_not_hide_body_or_customer_edits(mutated):
    signed, customers = _original_archive()
    after = {"sealed_run": deepcopy(signed),
             "customer_rows": deepcopy(customers)}
    if mutated == "quantity_value":
        after["sealed_run"]["quantities"][0]["value"] += 0.01
    elif mutated == "customer_body":
        after["customer_rows"][0]["ai_baseline_quantity"] += 0.01
    else:
        after["customer_rows"].pop()
    with pytest.raises((ValueError, RuntimeError)):
        verify_archived_signed_predecessors(signed, customers, after)


@pytest.mark.skipif(not PDF.is_file(), reason="private original source not provisioned")
def test_original_lot16_p3_source_figured_1215_and_stacker_distinct():
    import fitz

    data = PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ORIGINAL_SHA
    with fitz.open(stream=data, filetype="pdf") as pdf:
        assert len(pdf) == 13
        native = [w[4] for w in pdf[2].get_text("words")]
    assert "1215" in native
    assert "2127" in native
    assert "STACKER" in native
    # Native printed number is NOT a host, semantic role or signed ninth.
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == ORIGINAL_SHA


def _genuine_source_retention(composition):
    """Synthetic data exclusively THROUGH real production issue/seal/projection."""
    project = "au_qld_lot16_power"
    quantities = publish_live_opening_area_quantities(composition)
    traces = build_live_opening_area_source_traces(
        composition, workspace_id=1, project_id=project
    )
    authorities = {
        q.quantity_id: CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=(q.metadata["measurement_record_id"],),
        )
        for q in quantities
    }
    rows = quantities_to_takeoff_output_rows(
        quantities, traces_by_quantity_id=traces,
        authorities_by_quantity_id=authorities,
    )
    sealed = seal_live_opening_area_run(
        composition, workspace_id=1, project_id=project
    )
    verified = verify_sealed_customer_output(sealed, rows)
    return {
        "quantities": [q.to_dict() for q in quantities],
        "sealed_run": sealed.to_dict(),
        "customer_rows": rows,
        "customer_verification": verified.to_dict(),
    }


def _eight_plus_new_source_retention():
    source_openings = [
        _source_opening(
            f"physical-{index:03}", original_host=f"binding-{index:03}",
            area=2.16, area_receipt=f"figured-{index:03}",
        )
        for index in range(9)
    ]
    eight = replace(
        _composition(*source_openings[:8]),
        revision_id=ROOT["revision_id"],
    )
    nine = replace(
        _composition(*source_openings),
        revision_id=ROOT["revision_id"],
    )
    original = _genuine_source_retention(eight)
    current = _genuine_source_retention(nine)
    actual = publish_live_opening_area_quantities(nine)
    by_owner = {q.input_entity_ids[0]: q.quantity_id for q in actual}
    report = {
        "status": "UNPUBLISHED_SOURCE_REPROVED_OPENING_GPT1_QUEUE",
        "original_physical_opening_count": 9,
        "opening_decisions": [{
            "physical_opening_id": member.physical_opening_id,
            "source_sha256": member.source_sha256,
            "snapshot_id": member.snapshot_id,
            "prior_signed_quantity_id": by_owner[member.physical_opening_id],
            "new_gpt1_area_candidate_handoff": False,
            "measurement_published": False,
            "customer_seal_granted": False,
            "opening_count_granted": False,
        } for member in source_openings],
        "gpt1_new_area_review_candidates": [],
        "signed_customer_publisher_activated": False,
        "signed_source_lineage_handoff_granted": False,
        "global_opening_count_granted": False,
    }
    return report, nine, original, current


def _synthetic_predecessor_scope(monkeypatch, original):
    """Only tests may substitute a synthetic first-eight signer universe."""
    monkeypatch.setattr(
        issuer_audit, "ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT",
        original["sealed_run"]["fingerprint"],
    )
    monkeypatch.setattr(
        issuer_audit, "ORIGINAL_LOT16_SOURCE_SHA256", ROOT["source_sha256"],
    )


def test_new_source_issued_area_requires_verified_signed_and_customer_successors(monkeypatch):
    report, composition, original, current = _eight_plus_new_source_retention()
    # Product code pins the REAL eight predecessor fingerprint and source SHA;
    # test-only fixture uses an independent eight→nine synthetic signer universe.
    _synthetic_predecessor_scope(monkeypatch, original)
    outcome = audit_max_area_review_against_live_issuer(
        report, composition,
        archived_signed_run=original["sealed_run"],
        archived_customer_rows=original["customer_rows"],
        current_source_retention=current,
    )
    assert outcome["historical_full_signed_and_customer_bodies_verified"]
    assert outcome["real_producer_issued_opening_area_count"] == 9
    assert outcome["source_verified_new_quantity_count"] == 1
    new = outcome["new_source_issued_customer_verified_areas"]
    assert len(new) == 1
    assert new[0]["physical_opening_id"] == "physical-008"
    assert new[0]["value_m2"] == 2.16
    assert new[0]["area_basis"] == "figured_opening_label"
    assert new[0]["customer_output_verified"]
    assert new[0]["frozen_v2_score_granted"] is False
    assert outcome["customer_release_authorized"] is False
    assert outcome["benchmark_score_authorized"] is False
    # Without a real archived source predecessor, "ninth" is unknowable.
    unscoped = audit_max_area_review_against_live_issuer(report, composition)
    assert unscoped["source_verified_new_quantity_count"] is None
    assert unscoped["new_source_issued_customer_verified_areas"] == []


@pytest.mark.parametrize("corrupt", [
    "new_customer_value",
    "new_customer_notes",
    "new_customer_quantity_provenance",
    "new_sealed_quantity",
    "new_quantity_body",
    "new_quantity_rekey",
    "missing_customer",
    "original_customer_mutation",
    "signed_observer_mismatch",
])
def test_ninth_area_is_never_counted_without_complete_source_and_customer_parity(corrupt, monkeypatch):
    report, composition, original, current = _eight_plus_new_source_retention()
    _synthetic_predecessor_scope(monkeypatch, original)
    qid = current["quantities"][-1]["quantity_id"]
    row = next(x for x in current["customer_rows"] if x["quantity_id"] == qid)
    if corrupt == "new_customer_value":
        row["quantity"] += 0.01
    elif corrupt == "new_customer_notes":
        row["notes"] = '{"adapter":"commercial_takeoff","forged":true}'
    elif corrupt == "new_customer_quantity_provenance":
        row["commercial_projection_provenance"]["quantity"]["value"] = 500
    elif corrupt == "new_sealed_quantity":
        current["sealed_run"]["quantities"][-1]["value"] = 500
    elif corrupt == "new_quantity_body":
        current["quantities"][-1]["value"] = 500
    elif corrupt == "new_quantity_rekey":
        current["quantities"][-1]["quantity_id"] = "fake-ninth"
    elif corrupt == "missing_customer":
        current["customer_rows"].remove(row)
    elif corrupt == "original_customer_mutation":
        current["customer_rows"][0]["ai_baseline_quantity"] += 0.01
    elif corrupt == "signed_observer_mismatch":
        report["opening_decisions"][-1]["prior_signed_quantity_id"] = "fabricated-9th"
    with pytest.raises((ValueError, RuntimeError)):
        audit_max_area_review_against_live_issuer(
            report, composition,
            archived_signed_run=original["sealed_run"],
            archived_customer_rows=original["customer_rows"],
            current_source_retention=current,
        )


def test_arbitrary_eight_row_baseline_cannot_replace_pinned_original_lot16_archive():
    report, composition, original, current = _eight_plus_new_source_retention()
    with pytest.raises(SourceIssuerConvergenceConflict,
                       match="immutable original Lot16 eight"):
        audit_max_area_review_against_live_issuer(
            report, composition,
            archived_signed_run=original["sealed_run"],
            archived_customer_rows=original["customer_rows"],
            current_source_retention=current,
        )
