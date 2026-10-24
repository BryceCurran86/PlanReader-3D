"""Cached G17 proofs must revalidate source outside the selected seed."""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_raster_framed_opening_g17_contract import _prepare, _selector, _corroborated_records
from tests.test_g17_terminal_flank_source_shadow import _prepare as _two_page_source


@pytest.mark.parametrize("damage", ["receipt", "render", "pixels", "parent", "fingerprint"])
def test_nonseed_support_damage_invalidates_warmed_physical_proof_and_recovers(damage):
    source, published = _prepare(frame_lines=2)
    record = _corroborated_records(source, published)[0]
    selector = _selector(published, record.source_observation_ids[0])
    authority = source.physical_opening_authority()
    baseline = authority.prove_existence(selector)
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    other = record.source_observation_ids[1]
    key = (published.snapshot.snapshot_id, other)
    store = source._producer._store
    receipt = source._raster_opening_primitive_receipts[key]
    if damage in ("receipt", "render", "pixels"):
        if damage == "receipt":
            source._raster_opening_primitive_receipts.pop(key)
        else:
            change = {"render_sha256": "0" * 64} if damage == "render" else {"pixel_geometry": (1., 2., 3., 4.)}
            source._raster_opening_primitive_receipts[key] = replace(receipt, **change)
        restore = lambda: source._raster_opening_primitive_receipts.__setitem__(key, receipt)
    else:
        if damage == "parent":
            key = (published.snapshot.snapshot_id, receipt.parent_observation_id)
            table = store.observations
        else:
            table = store.record_fingerprints
        original = table.pop(key)
        restore = lambda: table.__setitem__(key, original)
    broken = authority.prove_existence(selector)
    assert broken.status is not EvidenceResolutionStatus.CORROBORATED
    assert broken.existence_record is None
    restore()
    assert authority.prove_existence(selector) == baseline


def test_other_page_damage_cannot_hide_behind_warmed_opening():
    source, published, selector = _two_page_source(pages=2)
    authority = source.physical_opening_authority()
    baseline = authority.prove_existence(selector)
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    store = source._producer._store
    other = next(oid for oid in published.raster_opening_primitive_observation_ids
                 if store.observations[(published.snapshot.snapshot_id, oid)].page_id == "2")
    key = (published.snapshot.snapshot_id, other)
    receipt = source._raster_opening_primitive_receipts.pop(key)
    assert authority.prove_existence(selector).status is not EvidenceResolutionStatus.CORROBORATED
    source._raster_opening_primitive_receipts[key] = receipt
    assert authority.prove_existence(selector) == baseline


def test_healthy_cache_reuses_detection_and_authentication_inventory(monkeypatch):
    source, published = _prepare(frame_lines=2)
    record = _corroborated_records(source, published)[0]
    authority = source.physical_opening_authority()
    selector = _selector(published, record.source_observation_ids[0])
    baseline = authority.prove_existence(selector)
    def no_detection(*args, **kwargs):
        raise AssertionError("healthy immutable source must reuse raster detection")
    monkeypatch.setattr(authority, "_raster_framed_candidates_for", no_detection)
    visibility = authority.source_visibility_authority()
    original = visibility.resolve_raster_opening_primitive
    calls = []
    def counted(address):
        calls.append(address.observation_id)
        return original(address)
    monkeypatch.setattr(visibility, "resolve_raster_opening_primitive", counted)
    assert authority.prove_existence(selector) == baseline
    assert calls == [selector.observation_id]


def test_mid_inventory_read_receipt_change_cannot_issue_positive(monkeypatch):
    source, published = _prepare(frame_lines=2)
    record = _corroborated_records(source, published)[0]
    authority = source.physical_opening_authority()
    selector = _selector(published, record.source_observation_ids[0])
    other = record.source_observation_ids[1]
    key = (published.snapshot.snapshot_id, other)
    receipt = source._raster_opening_primitive_receipts[key]
    # A changed object forces independent inventory authentication even when
    # the newly installed receipt currently has the same valid field values.
    source._raster_opening_primitive_receipts[key] = replace(receipt)
    visibility = authority.source_visibility_authority()
    original = visibility.resolve_raster_opening_primitive
    last = published.raster_opening_primitive_observation_ids[-1]
    def change_at_exit(address):
        result = original(address)
        if address.observation_id == last:
            source._raster_opening_primitive_receipts[key] = replace(receipt, render_sha256="0" * 64)
        return result
    monkeypatch.setattr(visibility, "resolve_raster_opening_primitive", change_at_exit)
    broken = authority.prove_existence(selector)
    assert broken.status is EvidenceResolutionStatus.CONFLICT
    assert broken.existence_record is None
    monkeypatch.setattr(visibility, "resolve_raster_opening_primitive", original)
    source._raster_opening_primitive_receipts[key] = receipt
    assert authority.prove_existence(selector).status is EvidenceResolutionStatus.CORROBORATED


def test_replaced_source_table_uses_fresh_scalar_authentication():
    source, published = _prepare(frame_lines=2)
    record = _corroborated_records(source, published)[0]
    authority = source.physical_opening_authority()
    selector = _selector(published, record.source_observation_ids[0])
    baseline = authority.prove_existence(selector)
    store = source._producer._store
    store.observations = dict(store.observations)
    assert authority.prove_existence(selector) == baseline
    other = record.source_observation_ids[1]
    key = (published.snapshot.snapshot_id, other)
    original = store.observations.pop(key)
    assert authority.prove_existence(selector).status is not EvidenceResolutionStatus.CORROBORATED
    store.observations[key] = original
    assert authority.prove_existence(selector) == baseline
