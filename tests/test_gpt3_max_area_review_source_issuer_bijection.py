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
from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
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


def _original_review(*, frame="frame-3", issuer_positive=True):
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
def test_review_only_not_firm_even_when_real_issuer_has_figured_area(frame):
    review, composition = _original_review(frame=frame)
    produced = publish_live_opening_area_quantities(composition)
    assert len(produced) == 1
    assert produced[0].value == 2.16
    assert produced[0].metadata["host_frame_record_id"] == frame
    output = audit_max_area_review_against_live_issuer(review, composition)
    assert output["complete_physical_source_inventory"] == 3
    assert output["real_producer_issued_opening_area_count"] == 1
    assert output["source_verified_new_quantity_count"] == 0
    assert output["customer_release_authorized"] is False
    assert output["benchmark_score_authorized"] is False
    assert len(output["review_candidates"]) == 1
    candidate = output["review_candidates"][0]
    assert candidate["host_only_figured_gross_area"] is (frame is None)
    assert candidate["status"] == "ISSUER_PRESENT_BUT_MAX_REPORT_UNSIGNED_CONFLICT"


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
