"""Source-neutral fail-closed regression for AntiGravity's four-family customer append.

The real source-positive suite is tests/test_original_q5446_two_family_source_customer.py.
These tests deliberately use synthetic sealed fixtures and no customer PDF.
"""
from dataclasses import dataclass, replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import pb_gptmax_q5446_original_family_customer_append as m


@dataclass(frozen=True)
class Record:
    quantity_id: str
    original: str
    lineage_ok: bool = True
    abstained: bool = False

    def to_dict(self):
        return {"quantity_id": self.quantity_id, "original": self.original,
                "lineage_ok": self.lineage_ok, "abstained": self.abstained}


def _quantity(qid, family):
    q = Mock(spec=m.QuantityEvidence)
    q.quantity_id = qid
    q.family = family
    q.abstained = False
    q.input_entity_ids = ("physical_" + qid,)
    q.metadata = {"tiled_floor_finish_authorized": True,
                  "net_internal_finished_face_authorized": True}
    return q


def _source(qid, family, *, alf=False):
    cls = m.OriginalQ5446AlfrescoCustomerResult if alf else m.OriginalQ5446TiledFloorCustomerResult
    rec = Record(qid, "immutable_original_" + qid)
    run = SimpleNamespace(quantities=(rec,))
    trace = SimpleNamespace(source_sha256=m.SOURCE_SHA256,
                            project_id=m.Q5446_PROJECT_ID,
                            document_id=m.Q5446_DOCUMENT_ID)
    return cls("FIRM_SOURCE_CUSTOMER_TO_REVIEW", (), _quantity(qid, family),
               trace, run, ({"quantity_id": qid},))


def _mount(monkeypatch, *, tile_mutation=None, alf_mutation=None, combined_mutation=None):
    a = _source("alfresco", "floor_area", alf=True)
    tiles = [_source("ground_ens", "floor_finish_area"),
             _source("laundry", "floor_finish_area"),
             _source("first_ens", "floor_finish_area")]
    if alf_mutation is not None:
        a = alf_mutation(a)
    if tile_mutation is not None:
        index, mutate = tile_mutation
        tiles[index] = mutate(tiles[index])
    # Keep a variable stable for closure without touching original PDF files.
    monkeypatch.setattr(m, "issue_original_q5446_alfresco_customer_area", lambda *args, **kw: a)
    for name, tile in zip(("issue_original_q5446_ground_ensuite_tiled_floor",
                           "issue_original_q5446_ground_laundry_tiled_floor",
                           "issue_original_q5446_first_ensuite_tiled_floor"), tiles):
        monkeypatch.setattr(m, name, lambda *args, _tile=tile, **kw: _tile)

    def verify(run, rows):
        ids = tuple(rec.quantity_id for rec in run.quantities)
        if sorted(ids) != sorted(row["quantity_id"] for row in rows):
            raise ValueError("fixture quantity bijection")
        return SimpleNamespace(customer_row_count=len(rows), verified_quantity_ids=ids)

    def combine(runs, *, project_id):
        combined = SimpleNamespace(
            quantities=tuple(rec for run in runs for rec in run.quantities),
            source_sha256s=(m.SOURCE_SHA256,), revision_ids=("revision",))
        return combined_mutation(combined) if combined_mutation else combined

    monkeypatch.setattr(m, "verify_sealed_customer_output", verify)
    monkeypatch.setattr(m, "combine_source_closed_runs", combine)


def _run():
    return m.issue_original_q5446_alfresco_plus_tiled_floors_customer(
        "fake-plan.pdf", "fake-inclusions.pdf", "fake-sales.pdf")


def test_four_independently_sealed_customer_rows_retain_all_original_bodies(monkeypatch):
    _mount(monkeypatch)
    result = _run()
    assert result.status == "MULTI_ROOM_SOURCE_FAMILIES_CUSTOMER_VERIFIED"
    assert [r["quantity_id"] for r in result.customer_rows] == [
        "alfresco", "ground_ens", "laundry", "first_ens"]


@pytest.mark.parametrize("mutate", [
    lambda x: replace(x, trace=SimpleNamespace(source_sha256="wrong",
                                               project_id=m.Q5446_PROJECT_ID,
                                               document_id=m.Q5446_DOCUMENT_ID)),
    lambda x: replace(x, quantity=_quantity("ground_ens", "floor_area")),
    lambda x: replace(x, quantity=Mock(spec=m.QuantityEvidence, **{
        "quantity_id": "ground_ens", "family": "floor_finish_area",
        "abstained": True, "input_entity_ids": ("p",), "metadata": {}})),
    lambda x: replace(x, customer_rows=()),
])
def test_incorrect_tile_source_or_family_or_customer_abstains(monkeypatch, mutate):
    _mount(monkeypatch, tile_mutation=(0, mutate))
    result = _run()
    assert result.status == "ABSTAIN"
    assert result.combined_sealed_run is None
    assert result.customer_rows == ()


def test_changed_original_sealed_record_cannot_pass_four_room_merge(monkeypatch):
    def changed(run):
        return SimpleNamespace(
            **{**vars(run), "quantities": (Record("alfresco", "substituted"),)
               + run.quantities[1:]})
    _mount(monkeypatch, combined_mutation=changed)
    result = _run()
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("combined_original_family_retention_unavailable",)


def test_same_quantity_id_or_reused_physical_face_abstains(monkeypatch):
    def altered(tile):
        q = _quantity("alfresco", "floor_finish_area")
        return replace(tile, quantity=q)
    _mount(monkeypatch, tile_mutation=(1, altered))
    assert _run().status == "ABSTAIN"


def test_wrong_combined_revision_or_source_sha_abstains(monkeypatch):
    _mount(monkeypatch, combined_mutation=lambda run: SimpleNamespace(
        **{**vars(run), "source_sha256s": ("foreign",)}))
    assert _run().status == "ABSTAIN"
