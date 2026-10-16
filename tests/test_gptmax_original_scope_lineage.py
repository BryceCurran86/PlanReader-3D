"""Original bytes, rather than equal area/receipt text, must issue scope lineage."""
from copy import deepcopy
from types import MappingProxyType

import fitz
import pytest

import tools.diag_gptmax_original_scope_lineage as module
from tests.test_opening_label_dimension_authority import _pdf


@pytest.fixture(scope="module")
def original():
    doc = fitz.open(stream=_pdf(labels=((88.0, 124.0, "900 - 1200 asw"),)), filetype="pdf")
    doc.new_page().insert_text((60, 60), "Independent unrelated source note")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def result(original):
    return module.original_scope_lineage_report(
        original, page_ids=("1",), baseline_decoded_page_ids=("1",),
        candidate_decoded_page_ids=("1", "2"), project_id="synthetic-review")


def test_actual_two_roots_have_real_host_and_frame_records(result):
    old, new = result["baseline"], result["candidate"]
    assert old["snapshot_id"] != new["snapshot_id"]
    assert old["source_sha256"] == new["source_sha256"]
    assert len(result["opening_lineage_rows"]) == 1
    row = result["opening_lineage_rows"][0]
    for side, replay in (("baseline", old), ("candidate", new)):
        proof = row[side]
        assert proof["snapshot_id"] == replay["snapshot_id"]
        assert proof["decision_scope_id"] == proof["host_record"]["decision_scope_id"]
        assert proof["frame_record"]["selector"]["snapshot_id"] == replay["snapshot_id"]
        assert proof["host_record"]["record_id"] in proof["sealed_quantity"]["evidence_ids"]
        assert proof["frame_record"]["record_id"] in proof["sealed_quantity"]["evidence_ids"]
        assert proof["sealed_quantity"]["fingerprint"]
        assert proof["host_candidate_source_records"]
        assert proof["source_competitors"]
        assert replay["source_and_signed_receipts_unchanged"]
    assert not result["cross_snapshot_identity_granted"]
    assert not result["customer_approval_granted"]
    assert not result["new_firm_quantity_granted"]
    assert not result["opening_count_granted"]
    assert not result["benchmark_score_granted"]


def test_replay_is_deterministic_and_inputs_stay_unchanged(original, result):
    before = original[:]
    again = module.original_scope_lineage_report(
        original, page_ids=("1",), baseline_decoded_page_ids=("1",),
        candidate_decoded_page_ids=("1", "2"), project_id="synthetic-review")
    assert again == result
    assert original == before


@pytest.mark.parametrize("damaged", ["snapshot_id", "decision_scope_id", "host_record", "frame_record", "quantity_id"])
def test_foreign_or_missing_source_scope_cannot_attach_to_sealed_quantity(original, monkeypatch, damaged):
    observe = module._observe
    def corrupt(*args):
        rows = deepcopy(observe(*args))
        if damaged in ("host_record", "frame_record"):
            rows[0][damaged] = None
        else:
            rows[0][damaged] = "foreign"
        return rows
    monkeypatch.setattr(module, "_observe", corrupt)
    with pytest.raises((ValueError, RuntimeError)):
        module.original_scope_lineage_report(
            original, page_ids=("1",), baseline_decoded_page_ids=("1",),
            candidate_decoded_page_ids=("1", "2"), project_id="test")


def test_missing_competing_wall_scope_is_not_complete_lineage(original, monkeypatch):
    observe = module._observe
    def corrupt(source, published, composition, voids):
        rows = observe(source, published, composition, voids)
        composition.physical_wall_candidate_authority._scopes = MappingProxyType({})
        return rows
    monkeypatch.setattr(module, "_observe", corrupt)
    with pytest.raises((ValueError, RuntimeError)):
        module.original_scope_lineage_report(
            original, page_ids=("1",), baseline_decoded_page_ids=("1",),
            candidate_decoded_page_ids=("1", "2"), project_id="test")


@pytest.mark.parametrize("pages", [(), ("01",), ("0",), ("1", "1"), (1,), "12"])
def test_bad_scope_selector_does_not_get_normalized_into_proof(original, pages):
    with pytest.raises(ValueError):
        module.original_scope_lineage_report(
            original, page_ids=("1",), baseline_decoded_page_ids=pages,
            candidate_decoded_page_ids=("1", "2"), project_id="test")


def test_supplied_json_is_not_source(original):
    with pytest.raises(TypeError):
        module.original_scope_lineage_report(
            {"pdf": original}, page_ids=("1",), baseline_decoded_page_ids=("1",),
            candidate_decoded_page_ids=("1", "2"), project_id="test")


def test_missing_original_identity_is_not_hidden_by_equal_area(original, monkeypatch):
    def corrupt(*args):
        return []
    monkeypatch.setattr(module, "_observe", corrupt)
    with pytest.raises(RuntimeError, match="missing original physical scope"):
        module.original_scope_lineage_report(
            original, page_ids=("1",), baseline_decoded_page_ids=("1",),
            candidate_decoded_page_ids=("1", "2"), project_id="test")


def test_source_mutation_during_read_never_returns_scope_evidence(original, monkeypatch):
    observe = module._observe
    def corrupt(source, pub, *args):
        rows = observe(source, pub, *args)
        source._producer._store.source_bytes_by_revision[pub.revision.revision_id] = b"different source"
        return rows
    monkeypatch.setattr(module, "_observe", corrupt)
    with pytest.raises((RuntimeError, ValueError)):
        module.original_scope_lineage_report(
            original, page_ids=("1",), baseline_decoded_page_ids=("1",),
            candidate_decoded_page_ids=("1", "2"), project_id="test")


def test_unmeasured_source_opening_stays_explicit_without_default_quantity():
    doc = fitz.open(stream=_pdf(labels=()), filetype="pdf")
    doc.new_page().insert_text((60, 60), "No opening dimension here")
    raw = doc.tobytes()
    doc.close()
    r = module.original_scope_lineage_report(
        raw, page_ids=("1",), baseline_decoded_page_ids=("1",),
        candidate_decoded_page_ids=("1", "2"), project_id="unmeasured")
    assert len(r["opening_lineage_rows"]) == 1
    for side in ("baseline", "candidate"):
        assert r["opening_lineage_rows"][0][side]["sealed_quantity"] is None
        assert r[side]["source_closed_run"]["quantities"] == []
    assert r["opening_count_granted"] is False


def test_other_original_sheets_are_explicit_evidence_pages_not_topology(original):
    r = module.original_scope_lineage_report(original, page_ids=("1",),
        baseline_decoded_page_ids=("1",), candidate_decoded_page_ids=("1", "2"),
        candidate_evidence_page_ids=("2",), project_id="evidence-scope")
    assert r["candidate"]["evidence_page_ids"] == ["2"]
    assert r["candidate"]["topology_page_ids"] == ["1"]
    assert len(r["opening_lineage_rows"]) == 1
    assert {x["page_id"] for x in r["candidate"]["wall_source_scopes"]} == {"1", "2"}
    assert not r["cross_snapshot_identity_granted"]


@pytest.mark.parametrize("pages", [("1",), ("3",), ("02",), "2", ("2", "2")])
def test_evidence_scope_cannot_include_topology_or_undecoded_or_malformed_pages(original, pages):
    with pytest.raises(ValueError):
        module.original_scope_lineage_report(original, page_ids=("1",),
            baseline_decoded_page_ids=("1",), candidate_decoded_page_ids=("1", "2"),
            candidate_evidence_page_ids=pages, project_id="test")
