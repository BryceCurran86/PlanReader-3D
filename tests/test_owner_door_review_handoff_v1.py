"""Owner-approved door review, handoff library (default off): approvals file loader, claim identity cross-check, verified outcome.

The approvals file is an explicit owner input.  Every record it produces is re-verified by the existing layer A/B validators, so nothing here
adds authority: it only refuses malformed input early and keeps a review row from outliving the standard claim it must agree with.
Synthetic numbers only; no project width, height, area or name is used anywhere in this file.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_owner_door_review_handoff as handoff_lib
from pb_customer_output_verification import verify_sealed_customer_output
from pb_owner_door_review_handoff import (
    OwnerDoorHeightApprovalsError,
    assess_owner_door_review,
    claim_page_scope,
    load_owner_door_height_approvals,
)
from pb_quantity_takeoff_adapter import existing_commercial_gate_results
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tests.symlink_test_support import symlink_or_skip
from tests.test_live_opening_area_quantity_publication import SHA, _composition
from tests.test_owner_approved_door_review_promotion_v1 import HEIGHT, STAMP, _approval, _owner_opening

PROJECT = "proj-1"


def _entry(**overrides) -> dict:
    entry = {
        "physical_opening_id": "opening-1", "page": 3, "height_mm": HEIGHT,
        "approved_by": "Test Approver", "approved_at": STAMP,
    }
    entry.update(overrides)
    return entry


def _payload(*entries, **top) -> dict:
    payload = {"schema_version": "1.0.0", "source_sha256": SHA, "approvals": list(entries) if entries else [_entry()]}
    payload.update(top)
    return payload


def _write(tmp_path, payload) -> pathlib.Path:
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _load(tmp_path, payload):
    return load_owner_door_height_approvals(_write(tmp_path, payload), source_sha256=SHA)


# ------------------------------------------------------------------ loader: positive

def test_a_valid_file_becomes_exactly_the_record_the_validators_expect(tmp_path):
    loaded = _load(tmp_path, _payload())
    assert loaded.records == (_approval(),)
    assert loaded.pages == (3,)
    assert re.fullmatch(r"[0-9a-f]{64}", loaded.file_sha256)


def test_a_loaded_record_is_accepted_by_the_existing_layer_b_validators():
    from tests.test_owner_approved_door_review_promotion_v1 import _build

    record = _approval(geometry_ref="opening-1")
    collection = _build([_owner_opening(record)], approvals=[record])
    assert len(collection.candidates) == 1 and collection.withheld == ()


def test_the_file_hash_is_the_hash_of_its_bytes(tmp_path):
    import hashlib

    path = _write(tmp_path, _payload())
    assert load_owner_door_height_approvals(path, source_sha256=SHA).file_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_an_empty_approvals_list_is_valid_and_grants_nothing(tmp_path):
    payload = _payload()
    payload["approvals"] = []
    loaded = _load(tmp_path, payload)
    assert loaded.records == () and loaded.pages == ()


def test_pages_are_the_sorted_unique_pages_named(tmp_path):
    loaded = _load(tmp_path, _payload(_entry(page=9), _entry(physical_opening_id="o2", page=3), _entry(physical_opening_id="o3", page=9)))
    assert loaded.pages == (3, 9) and len(loaded.records) == 3


def test_entry_order_is_kept_and_the_load_is_repeatable(tmp_path):
    payload = _payload(_entry(physical_opening_id="b"), _entry(physical_opening_id="a"))
    first, second = _load(tmp_path, payload), _load(tmp_path, payload)
    assert [r.geometry_ref for r in first.records] == ["b", "a"] and first == second


def test_duplicates_are_passed_through_for_the_existing_validators_to_decide(tmp_path):
    loaded = _load(tmp_path, _payload(_entry(), _entry(height_mm=HEIGHT + 100)))
    assert len(loaded.records) == 2          # conflicting approvals are withheld downstream, never resolved by the loader


def test_an_integer_height_is_accepted_and_stored_as_a_float(tmp_path):
    loaded = _load(tmp_path, _payload(_entry(height_mm=2100)))
    assert loaded.records[0].value == 2100.0 and type(loaded.records[0].value) is float


# ------------------------------------------------------------------ loader: negatives

def test_the_error_is_a_value_error():
    assert issubclass(OwnerDoorHeightApprovalsError, ValueError)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(OwnerDoorHeightApprovalsError):
        load_owner_door_height_approvals(tmp_path / "absent.json", source_sha256=SHA)


def test_a_directory_is_refused(tmp_path):
    with pytest.raises(OwnerDoorHeightApprovalsError):
        load_owner_door_height_approvals(tmp_path, source_sha256=SHA)


def test_a_symlink_is_refused(tmp_path):
    real = _write(tmp_path, _payload())
    link = tmp_path / "link.json"
    symlink_or_skip(link, real)
    with pytest.raises(OwnerDoorHeightApprovalsError, match="symlink"):
        load_owner_door_height_approvals(link, source_sha256=SHA)


def test_an_oversize_file_is_refused(tmp_path):
    path = tmp_path / "big.json"
    path.write_bytes(b" " * (handoff_lib.MAX_APPROVALS_FILE_BYTES + 1))
    with pytest.raises(OwnerDoorHeightApprovalsError, match="size"):
        load_owner_door_height_approvals(path, source_sha256=SHA)


def test_a_file_exactly_at_the_size_cap_is_not_refused_for_size(tmp_path):
    body = json.dumps(_payload()).encode("utf-8")
    path = tmp_path / "cap.json"
    path.write_bytes(body + b" " * (handoff_lib.MAX_APPROVALS_FILE_BYTES - len(body)))
    assert len(load_owner_door_height_approvals(path, source_sha256=SHA).records) == 1


@pytest.mark.parametrize("raw", [b"\xff\xfe\x00", b"\xef\xbb\xbf" + b'{"a": 1}', b"", b"{", b"[1, 2]", b"null", b'"text"'])
def test_undecodable_or_unparseable_or_wrong_shape_bytes_are_refused(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(OwnerDoorHeightApprovalsError):
        load_owner_door_height_approvals(path, source_sha256=SHA)


def test_a_duplicate_json_key_is_refused(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text(
        '{"schema_version": "1.0.0", "schema_version": "1.0.0", "source_sha256": "%s", "approvals": []}' % SHA, encoding="utf-8")
    with pytest.raises(OwnerDoorHeightApprovalsError, match="duplicate"):
        load_owner_door_height_approvals(path, source_sha256=SHA)


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("schema_version"), lambda p: p.pop("source_sha256"), lambda p: p.pop("approvals"),
    lambda p: p.update(extra=1), lambda p: p.update(schema_version="2.0.0"), lambda p: p.update(schema_version=1),
    lambda p: p.update(source_sha256="b" * 64), lambda p: p.update(source_sha256=SHA.upper()), lambda p: p.update(source_sha256=None),
    lambda p: p.update(approvals={}), lambda p: p.update(approvals="x"), lambda p: p.update(approvals=[1]), lambda p: p.update(approvals=[[]]),
])
def test_top_level_shape_and_binding_violations_are_refused(tmp_path, mutate):
    payload = copy.deepcopy(_payload())
    mutate(payload)
    with pytest.raises(OwnerDoorHeightApprovalsError):
        _load(tmp_path, payload)


@pytest.mark.parametrize("key", ["physical_opening_id", "page", "height_mm", "approved_by", "approved_at"])
def test_a_missing_entry_key_is_refused(tmp_path, key):
    entry = _entry()
    del entry[key]
    with pytest.raises(OwnerDoorHeightApprovalsError):
        _load(tmp_path, _payload(entry))


@pytest.mark.parametrize("extra", ["second_axis", "single_figure_axis", "source_sha256", "unit", "width_mm", "anything"])
def test_an_unknown_entry_key_is_refused_so_the_file_cannot_choose_axes_or_units(tmp_path, extra):
    with pytest.raises(OwnerDoorHeightApprovalsError):
        _load(tmp_path, _payload(_entry(**{extra: "height"})))


@pytest.mark.parametrize("overrides", [
    dict(physical_opening_id=""), dict(physical_opening_id="  "), dict(physical_opening_id=" opening-1"), dict(physical_opening_id=7),
    dict(physical_opening_id=None),
    dict(page=0), dict(page=-1), dict(page=True), dict(page=3.0), dict(page="3"), dict(page=None),
    dict(height_mm=0), dict(height_mm=-5), dict(height_mm=True), dict(height_mm="2100"), dict(height_mm=None), dict(height_mm=[2100]),
    dict(approved_by=""), dict(approved_by="   "), dict(approved_by=" X"), dict(approved_by=7), dict(approved_by=None),
    dict(approved_at="2026-11-05T07:10:00"), dict(approved_at="yesterday"), dict(approved_at=""), dict(approved_at=1), dict(approved_at=None),
])
def test_every_malformed_entry_value_is_refused(tmp_path, overrides):
    with pytest.raises(OwnerDoorHeightApprovalsError):
        _load(tmp_path, _payload(_entry(**overrides)))


def test_one_bad_entry_refuses_the_whole_file(tmp_path):
    with pytest.raises(OwnerDoorHeightApprovalsError):
        _load(tmp_path, _payload(_entry(), _entry(physical_opening_id="o2", page=0)))


def test_the_expected_hash_argument_must_itself_be_a_lowercase_sha256(tmp_path):
    path = _write(tmp_path, _payload())
    for bad in (None, 7, "", "abc", SHA.upper(), "g" * 64):
        with pytest.raises(OwnerDoorHeightApprovalsError):
            load_owner_door_height_approvals(path, source_sha256=bad)


def test_loading_never_modifies_the_file(tmp_path):
    path = _write(tmp_path, _payload())
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    load_owner_door_height_approvals(path, source_sha256=SHA)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


# ------------------------------------------------------------------ assessment against the standard claim

def _two_doors():
    openings = [_owner_opening(canonical_id="opening-1"), _owner_opening(canonical_id="opening-2")]
    approvals = [_approval(geometry_ref="opening-1"), _approval(geometry_ref="opening-2")]
    return openings, approvals


def _claim(*openings):
    return SimpleNamespace(canonical_openings=tuple(openings))


def _assess(openings, approvals, claim, **kwargs):
    arguments = dict(approvals=tuple(approvals), claim=claim, workspace_id=7, project_id=PROJECT, source_sha256=SHA)
    arguments.update(kwargs)
    return assess_owner_door_review(_composition(*openings), **arguments)


def test_openings_present_in_the_standard_claim_become_a_verified_review_run():
    openings, approvals = _two_doors()
    outcome = _assess(openings, approvals, _claim(*openings))
    assert outcome.gate == "OWNER_DOOR_REVIEW_VERIFIED"
    assert outcome.candidate_count == 2 and len(outcome.rows) == 2 and outcome.withheld_counts == {} and outcome.unused_approval_count == 0
    assert {q.status for q in outcome.run.quantities} == {"review_required"} and all(q.lineage_ok for q in outcome.run.quantities)
    verified = verify_sealed_customer_output(outcome.run, list(outcome.rows))
    assert set(verified.verified_quantity_ids) == {q.quantity_id for q in outcome.run.quantities}
    assert all(row["origin"] == "AI" and row["quantity_status"] == "To review" for row in outcome.rows)
    assert not any(result[0] for row in outcome.rows for result in existing_commercial_gate_results(row).values())


def test_the_run_round_trips_through_the_sealed_run_parser():
    openings, approvals = _two_doors()
    run = _assess(openings, approvals, _claim(*openings)).run
    assert sealed_source_closed_run_from_dict(json.loads(run.to_json())).run_id == run.run_id


def test_an_opening_the_standard_claim_does_not_know_is_withheld_with_a_typed_reason():
    openings, approvals = _two_doors()
    outcome = _assess(openings, approvals, _claim(openings[0]))
    assert outcome.candidate_count == 1 and outcome.withheld_counts == {"opening_not_in_standard_claim": 1}
    assert outcome.run.quantities[0].object_identity_refs == ("opening-1",)


@pytest.mark.parametrize("claim", [
    SimpleNamespace(canonical_openings=()), SimpleNamespace(), SimpleNamespace(canonical_openings=None),
    SimpleNamespace(canonical_openings=(1, 2, None)), SimpleNamespace(canonical_openings=("opening-1",)),
    SimpleNamespace(canonical_openings=(SimpleNamespace(canonical_opening_id=7),)),
    SimpleNamespace(canonical_openings=(SimpleNamespace(canonical_opening_id=" opening-1"),)),
])
def test_a_claim_that_does_not_prove_the_openings_withholds_all_of_them(claim):
    openings, approvals = _two_doors()
    outcome = _assess(openings, approvals, claim)
    assert outcome.gate == "NO_REVIEW_CANDIDATES" and outcome.run is None and outcome.rows == () and outcome.candidate_count == 0
    assert outcome.withheld_counts == {"opening_not_in_standard_claim": 2}


def test_a_foreign_claim_opening_id_never_unlocks_a_candidate():
    openings, approvals = _two_doors()
    foreign = replace(openings[0], canonical_opening_id="opening-9", physical_opening_id="opening-9")
    assert _assess(openings, approvals, _claim(foreign)).candidate_count == 0


def test_promotion_withholds_and_claim_withholds_are_counted_together_without_collision():
    openings, approvals = _two_doors()
    outcome = _assess(openings, approvals[:1], _claim(openings[0]))      # opening-2 has no approval; it is also absent from the claim
    assert outcome.candidate_count == 1
    assert outcome.withheld_counts == {"owner_approval_absent": 1}       # the typed promotion reason wins; one reason per opening


def test_unused_approvals_are_counted_not_guessed_at():
    openings, approvals = _two_doors()
    stray = _approval(geometry_ref="opening-77")
    outcome = _assess(openings, [*approvals, stray], _claim(*openings))
    assert outcome.unused_approval_count == 1 and outcome.candidate_count == 2


def test_no_approvals_means_no_candidates_and_no_default_height():
    openings, _ = _two_doors()
    outcome = _assess(openings, [], _claim(*openings))
    assert outcome.candidate_count == 0 and outcome.run is None and outcome.rows == ()


def test_a_composition_without_owner_basis_openings_yields_nothing():
    from tests.test_live_opening_area_quantity_publication import _opening

    outcome = _assess([_opening(canonical_id="d1", kind="door")], [], _claim())
    assert outcome.gate == "NO_REVIEW_CANDIDATES" and outcome.withheld_counts == {}


def test_a_source_hash_that_is_not_the_runs_source_is_a_hard_failure():
    openings, approvals = _two_doors()
    with pytest.raises(RuntimeError, match="source"):
        _assess(openings, approvals, _claim(*openings), source_sha256="b" * 64)


def test_outcome_is_independent_of_input_order_and_repeatable():
    openings, approvals = _two_doors()
    forward = _assess(openings, approvals, _claim(*openings))
    backward = _assess(list(reversed(openings)), list(reversed(approvals)), _claim(*reversed(openings)))
    assert forward.run.run_id == backward.run.run_id and forward.rows == backward.rows
    assert _assess(openings, approvals, _claim(*openings)).run.run_id == forward.run.run_id


def test_unrelated_claim_content_does_not_change_the_outcome():
    openings, approvals = _two_doors()
    base = _assess(openings, approvals, _claim(*openings))
    extra = replace(openings[0], canonical_opening_id="opening-5", physical_opening_id="opening-5")
    assert _assess(openings, approvals, _claim(*openings, extra)).run.run_id == base.run.run_id


def test_inputs_are_not_mutated():
    openings, approvals = _two_doors()
    claim = _claim(*openings)
    composition = _composition(*openings)
    snapshot = (copy.deepcopy(approvals), repr(claim), repr(composition))
    assess_owner_door_review(composition, approvals=tuple(approvals), claim=claim, workspace_id=7, project_id=PROJECT, source_sha256=SHA)
    assert (approvals, repr(claim), repr(composition)) == snapshot


def test_argument_types_are_enforced():
    openings, approvals = _two_doors()
    composition = _composition(*openings)
    base = dict(approvals=tuple(approvals), claim=_claim(*openings), workspace_id=7, project_id=PROJECT, source_sha256=SHA)
    for bad in (dict(approvals="x"), dict(approvals=[1]), dict(workspace_id=True), dict(workspace_id=0), dict(project_id=""), dict(project_id=3)):
        with pytest.raises((TypeError, ValueError)):
            assess_owner_door_review(composition, **{**base, **bad})
    with pytest.raises(TypeError):
        assess_owner_door_review("not a composition", **base)
    for bad_sha in (None, 7, "", "abc", "A" * 64):
        with pytest.raises((TypeError, ValueError, RuntimeError)):
            assess_owner_door_review(composition, **{**base, "source_sha256": bad_sha})


def test_a_symlink_is_refused_even_where_the_os_cannot_create_one(tmp_path, monkeypatch):
    path = _write(tmp_path, _payload())
    real = pathlib.Path.is_symlink
    monkeypatch.setattr(pathlib.Path, "is_symlink", lambda self: True if self == path else real(self))
    with pytest.raises(OwnerDoorHeightApprovalsError, match="symlink"):
        load_owner_door_height_approvals(path, source_sha256=SHA)


def test_an_overflowing_height_literal_is_refused_as_non_finite(tmp_path):
    body = '{"schema_version": "1.0.0", "source_sha256": "%s", "approvals": [{"physical_opening_id": "o", "page": 3, "height_mm": 1e999, ' \
           '"approved_by": "A", "approved_at": "%s"}]}' % (SHA, STAMP)
    path = tmp_path / "overflow.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(OwnerDoorHeightApprovalsError, match="finite"):
        load_owner_door_height_approvals(path, source_sha256=SHA)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_literals_are_named_as_such(tmp_path, literal):
    body = '{"schema_version": "1.0.0", "source_sha256": "%s", "approvals": [{"physical_opening_id": "o", "page": 3, "height_mm": %s, ' \
           '"approved_by": "A", "approved_at": "%s"}]}' % (SHA, literal, STAMP)
    path = tmp_path / "nan.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(OwnerDoorHeightApprovalsError, match="non-finite JSON literal"):
        load_owner_door_height_approvals(path, source_sha256=SHA)


def _sealed_outcome_inputs():
    openings, approvals = _two_doors()
    return openings, approvals, _claim(*openings)


def test_the_assessment_refuses_a_verification_that_does_not_cover_exactly_the_sealed_ids(monkeypatch):
    openings, approvals, claim = _sealed_outcome_inputs()
    monkeypatch.setattr(handoff_lib, "verify_sealed_customer_output",
                        lambda run, rows: SimpleNamespace(verified_quantity_ids=("someone-else",), customer_row_count=2))
    with pytest.raises(RuntimeError, match="disagree"):
        _assess(openings, approvals, claim)
    monkeypatch.setattr(handoff_lib, "verify_sealed_customer_output",
                        lambda run, rows: SimpleNamespace(
                            verified_quantity_ids=tuple(q.quantity_id for q in run.quantities), customer_row_count=1))
    with pytest.raises(RuntimeError, match="disagree"):
        _assess(openings, approvals, claim)


def test_the_assessment_refuses_a_sealed_quantity_without_exact_lineage(monkeypatch):
    openings, approvals, claim = _sealed_outcome_inputs()
    real_seal = handoff_lib.seal_owner_approved_door_review_run

    def broken(candidates, *, project_id):
        run = real_seal(candidates, project_id=project_id)
        return replace(run, quantities=(replace(run.quantities[0], lineage_ok=False), *run.quantities[1:]))

    monkeypatch.setattr(handoff_lib, "seal_owner_approved_door_review_run", broken)
    monkeypatch.setattr(handoff_lib, "verify_sealed_customer_output",
                        lambda run, rows: SimpleNamespace(
                            verified_quantity_ids=tuple(q.quantity_id for q in run.quantities), customer_row_count=len(run.quantities)))
    with pytest.raises(RuntimeError, match="lineage"):
        _assess(openings, approvals, claim)


def test_the_assessment_refuses_a_row_that_any_commercial_gate_would_accept(monkeypatch):
    openings, approvals, claim = _sealed_outcome_inputs()
    monkeypatch.setattr(handoff_lib, "existing_commercial_gate_results", lambda row: {"gate": (True, "open")})
    with pytest.raises(RuntimeError, match="commercially"):
        _assess(openings, approvals, claim)


# ------------------------------------------------------------------ page scope mirrors the claim collector

@pytest.mark.parametrize("page_count, pages, topology, support, decoded, topo_ids, evidence", [
    (3, (2,), (2,), None, ("3",), ("3",), ()),
    (5, tuple(range(5)), None, None, ("1", "2", "3", "4", "5"), ("1", "2", "3", "4", "5"), ()),
    (5, tuple(range(5)), (1, 2), None, ("1", "2", "3", "4", "5"), ("2", "3"), ("1", "4", "5")),
    (5, (0, 1), (1,), (4,), ("1", "2", "5"), ("2",), ("1",)),
    (5, (3, 1), (1,), (4, 1), ("2", "4", "5"), ("2",), ("4",)),
])
def test_page_scope_arithmetic_matches_the_claim_collector(page_count, pages, topology, support, decoded, topo_ids, evidence):
    assert claim_page_scope(page_count, pages, topology, support) == (decoded, topo_ids, evidence)


def test_page_scope_rejects_what_the_claim_collector_rejects():
    with pytest.raises(ValueError):
        claim_page_scope(3, (0, 1), (2,), None)        # topology must be a subset of pages
    with pytest.raises(ValueError):
        claim_page_scope(3, (7,), None, None)          # not an original page


# ------------------------------------------------------------------ the source step (composition stubbed; the real chain is run separately)

def _step_inputs(tmp_path, *, records=None, pages=(2,), topology=(2,), support=None, page_count=3, **overrides):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"synthetic-source-bytes")
    import hashlib

    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    records = tuple(records if records is not None else (_approval(geometry_ref="opening-1"),))
    approvals = handoff_lib.OwnerDoorHeightApprovals(
        records=records, pages=tuple(sorted({int(r.page) for r in records})), file_sha256="c" * 64)
    arguments = dict(
        approvals=approvals, claim=_claim(), workspace_id=7, project_id=PROJECT, source_sha256=sha,
        page_count=page_count, pages=pages, topology_pages=topology, room_area_support_pages=support, native_text_kwargs={})
    arguments.update(overrides)
    return pdf, arguments


def _stub_compose(monkeypatch, composition=None):
    calls = []

    def fake(pdf_bytes, **kwargs):
        calls.append((pdf_bytes, kwargs))
        return composition if composition is not None else _composition()

    monkeypatch.setattr(handoff_lib, "compose_owner_approved_opening_voids", fake)
    return calls


def test_the_step_composes_with_the_claims_own_page_scope_and_text_options(tmp_path, monkeypatch):
    calls = _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path, pages=(0, 2), topology=(2,), support=(1,), page_count=3,
                                  native_text_kwargs={"source_glyph_ledger_text_trust": True})
    handoff_lib.run_owner_door_review_step(pdf, **arguments)
    assert len(calls) == 1
    pdf_bytes, kwargs = calls[0]
    assert pdf_bytes == pdf.read_bytes() and kwargs["source_sha256"] == arguments["source_sha256"]
    assert kwargs["decoded_page_ids"] == ("1", "2", "3") and kwargs["topology_page_ids"] == ("3",) and kwargs["evidence_page_ids"] == ("1",)
    assert kwargs["native_text_kwargs"] == {"source_glyph_ledger_text_trust": True}
    assert [r.geometry_ref for r in kwargs["approvals"]] == ["opening-1"]
    assert kwargs["single_width_uniform_page_door_height_shadow"] is False


def test_the_step_forwards_the_claims_uniform_page_door_height_option(tmp_path, monkeypatch):
    """A door the claim measured from a printed uniform page door height must not look unmeasured to the review composition."""
    calls = _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path, pages=(0, 2), topology=(2,), support=(1,), page_count=3, native_text_kwargs={})
    handoff_lib.run_owner_door_review_step(pdf, single_width_uniform_page_door_height_shadow=True, **arguments)
    assert calls[0][1]["single_width_uniform_page_door_height_shadow"] is True


def test_only_approvals_on_topology_pages_reach_the_composition_and_the_rest_are_reported(tmp_path, monkeypatch):
    calls = _stub_compose(monkeypatch)
    records = (_approval(geometry_ref="opening-1", page=3), _approval(geometry_ref="opening-2", page=1), _approval(geometry_ref="opening-3", page=2))
    pdf, arguments = _step_inputs(tmp_path, records=records, pages=(0, 1, 2), topology=(2,), page_count=3)
    outcome = handoff_lib.run_owner_door_review_step(pdf, **arguments)
    assert [r.geometry_ref for r in calls[0][1]["approvals"]] == ["opening-1"]
    assert outcome.approval_pages_out_of_scope == (1, 2) and outcome.unused_approval_count == 3   # 2 out of scope + the one that matched nothing


def test_when_no_approval_is_in_scope_nothing_is_composed(tmp_path, monkeypatch):
    calls = _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path, records=(_approval(page=1),), pages=(2,), topology=(2,), page_count=3)
    outcome = handoff_lib.run_owner_door_review_step(pdf, **arguments)
    assert calls == [] and outcome.gate == "NO_REVIEW_CANDIDATES" and outcome.run is None
    assert outcome.approval_pages_out_of_scope == (1,) and outcome.unused_approval_count == 1


def test_an_empty_approvals_file_composes_nothing(tmp_path, monkeypatch):
    calls = _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path, records=())
    outcome = handoff_lib.run_owner_door_review_step(pdf, **arguments)
    assert calls == [] and outcome.gate == "NO_REVIEW_CANDIDATES" and outcome.candidate_count == 0 and outcome.unused_approval_count == 0


def test_a_source_that_changed_since_the_run_began_is_a_hard_failure_before_any_composition(tmp_path, monkeypatch):
    calls = _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path)
    pdf.write_bytes(b"replaced-after-the-hash-was-taken")
    with pytest.raises(RuntimeError, match="source"):
        handoff_lib.run_owner_door_review_step(pdf, **arguments)
    assert calls == []


def _bound_composition(arguments):
    sha = arguments["source_sha256"]
    approval = _approval(geometry_ref="opening-1", metadata={**_approval().metadata, "source_sha256": sha})
    opening = replace(_owner_opening(approval, canonical_id="opening-1"), source_sha256=sha)
    arguments["approvals"] = handoff_lib.OwnerDoorHeightApprovals(records=(approval,), pages=(3,), file_sha256="c" * 64)
    return opening, _composition(opening)


def test_the_step_returns_a_verified_run_for_an_opening_the_claim_proves(tmp_path, monkeypatch):
    pdf, arguments = _step_inputs(tmp_path)
    opening, composition = _bound_composition(arguments)
    _stub_compose(monkeypatch, composition)
    outcome = handoff_lib.run_owner_door_review_step(pdf, **{**arguments, "claim": _claim(opening)})
    assert outcome.gate == "OWNER_DOOR_REVIEW_VERIFIED" and outcome.candidate_count == 1 and set(outcome.run.source_sha256s) == {arguments["source_sha256"]}


def test_the_step_withholds_an_opening_the_claim_does_not_prove(tmp_path, monkeypatch):
    pdf, arguments = _step_inputs(tmp_path)
    _, composition = _bound_composition(arguments)
    _stub_compose(monkeypatch, composition)
    outcome = handoff_lib.run_owner_door_review_step(pdf, **{**arguments, "claim": _claim()})
    assert outcome.gate == "NO_REVIEW_CANDIDATES" and outcome.withheld_counts == {"opening_not_in_standard_claim": 1}


def test_native_text_options_are_restricted_to_the_claims_two_explicit_switches(tmp_path, monkeypatch):
    _stub_compose(monkeypatch)
    pdf, arguments = _step_inputs(tmp_path)
    for bad in ({"anything": True}, {"source_glyph_ledger_text_trust": False}, {"source_native_finish_text_shadow": 1}, None):
        with pytest.raises((TypeError, ValueError)):
            handoff_lib.run_owner_door_review_step(pdf, **{**arguments, "native_text_kwargs": bad})


# ------------------------------------------------------------------ default-off proof

def test_only_the_handoff_tool_imports_the_new_module_and_only_lazily():
    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"^\s*(from|import)\s+pb_owner_door_review_handoff\b", re.M)
    top_level = re.compile(r"^(from|import)\s+pb_owner_door_review_handoff\b", re.M)
    sources = list(root.glob("*.py")) + list((root / "tools").glob("*.py"))
    offenders = [
        path.relative_to(root).as_posix() for path in sources
        if path.name != "pb_owner_door_review_handoff.py" and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert offenders == ["tools/run_source_closed_project_handoff.py"]
    tool = (root / "tools" / "run_source_closed_project_handoff.py").read_text(encoding="utf-8")
    assert not top_level.search(tool)


def test_only_the_handoff_library_imports_the_promotion_module():
    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"^\s*(from|import)\s+pb_owner_approved_door_review_promotion\b", re.M)
    offenders = [
        path.relative_to(root).as_posix() for path in list(root.glob("*.py")) + list((root / "tools").glob("*.py"))
        if path.name != "pb_owner_approved_door_review_promotion.py" and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert offenders == ["pb_owner_door_review_handoff.py"]
