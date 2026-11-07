"""Raster-only host reads retain full source proof without native alias work."""
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT, SourceVisibilityAuthority, SourceVisibilityProducer,
)
from test_raster_source_visibility_v1 import _hybrid_pdf


def _source():
    with fitz.open(stream=_hybrid_pdf(), filetype="pdf") as doc:
        with fitz.open(stream=_hybrid_pdf(), filetype="pdf") as other:
            doc.insert_pdf(other)
        payload = doc.tobytes()
    source = SourceVisibilityProducer(producer_method="raster-host-address-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="mixed-raster-host", source_bytes=payload,
        source_locator="memory://mixed-raster-host.pdf")
    published = source.augment_with_raster_visible_segments(
        revision_id=published.revision.revision_id, page_ids=("1", "2"))
    opening = SimpleNamespace(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1")
    return source, published, opening


def _unfiltered(monkeypatch, source, opening, ids):
    with monkeypatch.context() as patch:
        # Exercise the old full-resolution path, including its post-proof
        # kind/page rejection, while retaining the real source authority.
        if hasattr(SourceVisibilityAuthority, "raster_visible_observation_ids_for_page"):
            patch.setattr(SourceVisibilityAuthority, "raster_visible_observation_ids_for_page",
                          lambda self, snapshot_id, page_id: frozenset(ids))
        return host._authenticated_raster_source_lines(source.physical_opening_authority(), opening, ids)


def test_raster_host_line_reader_resolves_only_its_raster_page(monkeypatch):
    source, published, opening = _source()
    ids = tuple(reversed(published.visible_observation_ids))
    expected = _unfiltered(monkeypatch, source, opening, ids)
    assert expected
    visibility = source.authority()
    expected_calls = []
    for oid in ids:
        result = visibility.resolve_visible(ObservationSelector(
            document_id=opening.document_id, revision_id=opening.revision_id,
            source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
            observation_id=oid))
        obs = result.observation
        if (result.status is EvidenceResolutionStatus.CORROBORATED and obs is not None
                and obs.observation_kind == RASTER_PDF_VISIBLE_SEGMENT and obs.page_id == "1"):
            expected_calls.append(oid)
    assert expected_calls and len(expected_calls) < len(ids)
    visited = []
    original = SourceVisibilityAuthority.resolve_visible

    def resolve(self, selector):
        visited.append(selector.observation_id)
        return original(self, selector)

    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", resolve)
    actual = host._authenticated_raster_source_lines(source.physical_opening_authority(), opening, ids)
    assert actual == expected
    assert visited == expected_calls


@pytest.mark.parametrize("damage", ["missing_receipt", "foreign_page", "source_hash",
                                  "missing_parent", "changed_geometry", "foreign_snapshot"])
def test_raster_addressing_preserves_full_proof_rejections(monkeypatch, damage):
    source, published, opening = _source()
    ids = published.visible_observation_ids
    visibility = source.authority()
    table = visibility._raster_visibility_receipts
    key, receipt = next((key, receipt) for key, receipt in table.items()
                        if key[0] == opening.snapshot_id and receipt.page_id == "1")
    original = visibility.resolve_visible(ObservationSelector(
        document_id=opening.document_id, revision_id=opening.revision_id,
        source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
        observation_id=key[1]))
    assert original.observation is not None
    damaged_primitive_id = original.observation.source_primitive_ref.removeprefix("visible:")
    if damage == "missing_receipt":
        del table[key]
    elif damage == "foreign_page":
        table[key] = replace(receipt, page_id="2")
    elif damage == "source_hash":
        opening.source_sha256 = "0" * 64
    elif damage == "missing_parent":
        table[key] = replace(receipt, parent_observation_id="missing-original-parent")
    elif damage == "changed_geometry":
        table[key] = replace(receipt, geometry=(0.0, 0.0, 1.0, 1.0))
    else:
        opening.snapshot_id = "foreign-snapshot"
    expected = _unfiltered(monkeypatch, source, opening, ids)
    actual = host._authenticated_raster_source_lines(source.physical_opening_authority(), opening, ids)
    assert actual == expected
    if damage in {"source_hash", "foreign_snapshot"}:
        assert actual == {}
    else:
        assert damaged_primitive_id not in actual


def test_native_receipt_keeps_precedence_over_a_raster_address(monkeypatch):
    source, published, opening = _source()
    visibility = source.authority()
    native_key = next(key for key in visibility._visibility_receipts if key[0] == opening.snapshot_id)
    raster_receipt = next(receipt for key, receipt in visibility._raster_visibility_receipts.items()
                          if key[0] == opening.snapshot_id and receipt.page_id == "1")
    visibility._raster_visibility_receipts[native_key] = raster_receipt
    ids = (native_key[1], *published.visible_observation_ids)
    assert host._authenticated_raster_source_lines(source.physical_opening_authority(), opening, ids) == _unfiltered(monkeypatch, source, opening, ids)
