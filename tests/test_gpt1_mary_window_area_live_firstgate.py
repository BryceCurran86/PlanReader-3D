"""Only actual live publisher output counts; original words are not authority."""
from hashlib import sha256
from dataclasses import replace
import json
import sys

import fitz
import pytest

from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_gpt1_opening_area_actual_issuer_preflight_shadow import _typed
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture
from pb_migration_contracts import EvidenceResolutionStatus
from tools.diag_gpt1_mary_window_area_live_firstgate import (
    TARGETS, diagnose_actual_window_area_gates, main,
)


def _pdf(*, duplicate=False, missing_elevation=False):
    d = fitz.open()
    try:
        for i in range(29):
            page = d.new_page()
            if i == 6:
                for j, mark in enumerate(TARGETS):
                    page.insert_text((40, 80 + j*30), mark)
                if duplicate:
                    page.insert_text((40, 225), "W01")
            if i == 28 and not missing_elevation:
                for j, mark in enumerate(TARGETS):
                    page.insert_text((40, 80 + j*30), mark)
        return d.tobytes()
    finally:
        d.close()


def _claim(canonical=(), quantities=()):
    # Construct an actual typed claim without authority or signed publication.
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(), quantity_m2=None,
        source_pages=(), canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(), canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=tuple(canonical), canonical_rooms=(),
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(), canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(), canonical_room_source_pages=(),
        external_wall_ids=(), evidence_ids=(), quantity_id=None,
        confidence=0.0, publication=object(),
        opening_quantity_evidence=tuple(quantities),
    )


def _run(pdf, claim):
    return diagnose_actual_window_area_gates(pdf, sha256(pdf).hexdigest(), claim)


def test_native_words_with_no_real_opening_do_not_issue_window_area():
    report = _run(_pdf(), _claim())
    assert report["benchmark_score_granted"] is False
    assert report["customer_seal_granted"] is False
    assert report["real_issuer_quantity_inventory"] == 0
    assert all(w["first_missing_gate"] == "physical_type_mark_binding_unavailable"
               for w in report["windows"])


def test_duplicate_or_missing_mark_cannot_select_physical_window():
    for kwargs in ({"duplicate":True}, {"missing_elevation":True}):
        report = _run(_pdf(**kwargs), _claim())
        assert report["windows"][0]["first_missing_gate"] == (
            "original_native_mark_unavailable_or_ambiguous"
        )


def test_source_sha_mismatch_fails_closed():
    pdf = _pdf()
    with pytest.raises(ValueError, match="source sha256 mismatch"):
        diagnose_actual_window_area_gates(pdf, "0"*64, _claim())


def test_issuer_report_never_uses_original_measurements_as_quantity():
    report = _run(_pdf(), _claim())
    assert report["not_source_authority"] is True
    assert report["measurement_published_by_this_tool"] is False
    assert all(w["quantity_id"] is None for w in report["windows"])


def test_untrusted_claim_shape_refused():
    pdf = _pdf()
    with pytest.raises(TypeError, match="actual LivePhysicalNetWallClaim"):
        _run(pdf, object())

def _source_issued_window_case():
    pdf = _pdf()
    _rows, canonical = fixture()
    original = _typed(canonical).canonical_openings[2]
    tag = "original-plan-W01-word"
    typed = replace(
        original,
        source_sha256=sha256(pdf).hexdigest(),
        page_id="7", viewport_id="page:7",
        type_mark="W01", opening_kind="window",
        tag_observation_id=tag,
        area_basis="authenticated_elevation_frame",
        evidence_ids=original.evidence_ids + (tag,),
    )
    quantity = _opening_quantity(typed)
    assert quantity is not None
    return pdf, typed, quantity


def test_real_typed_issuer_w01_observed_only_not_sealed():
    pdf, opening, quantity = _source_issued_window_case()
    report = _run(pdf, _claim((opening,), (quantity,)))
    w01 = report["windows"][0]
    assert w01["first_missing_gate"] == "LIVE_QUANTITY_OBSERVED_NOT_CUSTOMER_SEALED"
    assert w01["quantity_id"] == quantity.quantity_id
    assert report["benchmark_score_granted"] is False
    assert report["customer_seal_granted"] is False


@pytest.mark.parametrize("alter", [
    lambda o: replace(o, tag_observation_id=None),
    lambda o: replace(o, tag_observation_id="unowned-source-tag"),
    lambda o: replace(o, evidence_ids=tuple(
        x for x in o.evidence_ids if x != o.tag_observation_id
    )),
])
def test_original_native_wxx_word_cannot_replace_producer_tag_receipt(alter):
    pdf, opening, quantity = _source_issued_window_case()
    changed = alter(opening)
    report = _run(pdf, _claim((changed,), (quantity,)))
    assert report["windows"][0]["first_missing_gate"] == (
        "source_owned_plan_tag_receipt_unavailable"
    )
    assert report["windows"][0]["quantity_id"] is None


@pytest.mark.parametrize("field,value", [
    ("host_wall_id", "foreign-wall"),
    ("host_binding_record_id", "foreign-binding"),
    ("revision_id", "foreign-revision"),
    ("page_no", "29"),
    ("viewport_id", "page:29"),
    ("opening_kind", "door"),
])
def test_foreign_issuer_owner_receipt_cannot_be_diagnostic_positive(field, value):
    pdf, opening, quantity = _source_issued_window_case()
    forged = replace(quantity, metadata={**quantity.metadata, field:value})
    report = _run(pdf, _claim((opening,), (forged,)))
    assert report["windows"][0]["first_missing_gate"] == (
        "issued_area_source_owner_mismatch"
    )
    assert report["windows"][0]["quantity_id"] is None


def test_complete_original_handoff_semantic_page_universe(monkeypatch, tmp_path, capsys):
    pdf = _pdf()
    path = tmp_path / "original.pdf"
    path.write_bytes(pdf)
    seen = {}
    def collect(_path, **kwargs):
        seen.update(kwargs)
        return _claim()
    monkeypatch.setattr(
        "tools.diag_gpt1_mary_window_area_live_firstgate.collect_live_physical_net_wall_claim",
        collect,
    )
    monkeypatch.setattr(
        "tools.run_source_closed_project_handoff._source_page_scopes",
        lambda _path: ((6,), (28,), 29),
    )
    monkeypatch.setattr(sys, "argv", [
        "firstgate", "--pdf", str(path), "--expected-sha256",
        sha256(pdf).hexdigest(),
    ])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "SOURCE_ONLY_LIVE_ISSUER_FIRST_GATE_DIAGNOSTIC"
    assert seen == {
        "pages": tuple(range(29)),
        "topology_pages": (6,),
        "room_area_support_pages": (28,),
        "surface_semantic_pages": tuple(range(29)),
    }

def _two_source_issued_distinct_window_case():
    pdf, w01, q01 = _source_issued_window_case()
    # Two real issuer-positive physical windows, each with separately owned
    # original plan tag, representative, structural host and type-frame ID.
    w02 = replace(
        w01,
        canonical_opening_id="physical-window-2",
        physical_opening_id="physical-window-2",
        type_mark="W02",
        host_wall_id="different-original-wall",
        host_binding_record_id="different-original-binding",
        host_frame_record_id="different-original-frame",
        tag_observation_id="original-plan-W02-word",
        representative_observation_id="original-opening-observation-2",
        source_observation_ids=("original-opening-observation-2",),
        figured_area_record_id="source-elevation-frame-W02",
        evidence_ids=(
            "original-opening-observation-2",
            "original-plan-W02-word",
            "source-elevation-frame-W02",
            "different-original-binding",
            "different-original-frame",
        ),
    )
    q02 = _opening_quantity(w02)
    assert q02 is not None
    assert q02.semantic_key == "window_area:physical-window-2"
    return pdf, w01, q01, w02, q02


def test_two_distinct_original_window_marks_stay_issuer_compatible_review_only():
    pdf, w01, q01, w02, q02 = _two_source_issued_distinct_window_case()
    output = _run(pdf, _claim((w01, w02), (q01, q02)))
    assert [w["type_mark"] for w in output["windows"][:2]] == ["W01", "W02"]
    assert [w["first_missing_gate"] for w in output["windows"][:2]] == [
        "LIVE_QUANTITY_OBSERVED_NOT_CUSTOMER_SEALED",
        "LIVE_QUANTITY_OBSERVED_NOT_CUSTOMER_SEALED",
    ]
    assert [w["quantity_id"] for w in output["windows"][:2]] == [
        q01.quantity_id, q02.quantity_id,
    ]
    assert output["customer_seal_granted"] is False
    assert output["benchmark_score_granted"] is False


@pytest.mark.parametrize("stolen_field,expected", [
    ("tag_observation_id", "original_plan_tag_shared_across_physical_openings"),
    ("representative_observation_id", "original_representative_shared_across_physical_openings"),
    ("figured_area_record_id", "original_elevation_frame_shared_across_different_window_types"),
])
def test_original_cross_window_source_receipt_rivals_never_count_as_distinct(
    stolen_field, expected,
):
    pdf, w01, q01, w02, _q02 = _two_source_issued_distinct_window_case()
    stolen_id = getattr(w01, stolen_field)
    new_evidence = tuple(dict.fromkeys((*w02.evidence_ids, stolen_id)))
    mutation = {stolen_field: stolen_id, "evidence_ids": new_evidence}
    if stolen_field == "representative_observation_id":
        mutation["source_observation_ids"] = (stolen_id,)
    forged = replace(w02, **mutation)
    q02 = _opening_quantity(forged)
    assert q02 is not None, "both individual issuers must be positive"
    output = _run(pdf, _claim((w01, forged), (q01, q02)))
    assert [w["first_missing_gate"] for w in output["windows"][:2]] == [
        expected, expected,
    ]
    assert all(w["quantity_id"] is None for w in output["windows"][:2])
    assert output["benchmark_score_granted"] is False
