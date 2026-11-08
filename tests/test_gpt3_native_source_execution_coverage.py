"""Native-input proof is independently replayed, never quantity authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import gc
import hashlib
import json
from pathlib import Path
import weakref

import fitz
import pytest

from pb_migration_contracts import canonical_contract_json
from tools import gpt3_native_source_execution_coverage as module


def _pdf(tmp_path, name="source.pdf", pages=3):
    path = tmp_path / name
    with fitz.open() as doc:
        for index in range(pages):
            page = doc.new_page()
            if index == 1:
                page.insert_text((72, 72), "PRIVATE SYNTHETIC SOURCE TEXT")
            if index == 2:
                page.draw_rect(fitz.Rect(30, 30, 100, 90))
        doc.save(path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _build(path, sha, pages=3):
    return module.build_native_source_execution_coverage(
        pdf_path=path, expected_sha256=sha, expected_page_count=pages,
    )


def _verify(receipt, path, sha, pages=3):
    return module.verify_native_source_execution_coverage(
        receipt, pdf_path=path, expected_sha256=sha, expected_page_count=pages,
    )


@pytest.mark.parametrize("pages", (1, 3, 7))
def test_every_blank_text_and_vector_page_is_independently_reproved(tmp_path, pages):
    path, sha = _pdf(tmp_path, pages=pages)
    original = path.read_bytes()
    receipt = _build(path, sha, pages)
    assert receipt["coverage"]["state"] == "complete"
    assert receipt["coverage"]["decoded_pages"] == list(range(1, pages + 1))
    assert receipt["coverage"]["failed_pages"] == []
    assert [r["page_number"] for r in receipt["page_snapshots"]] == list(range(1, pages + 1))
    assert all(r["observation_count"] > 0 for r in receipt["page_snapshots"])
    assert len({r["snapshot_id"] for r in receipt["page_snapshots"]}) == pages
    before = deepcopy(receipt)
    assert _verify(json.loads(json.dumps(receipt)), path, sha, pages) == receipt
    assert receipt == before and path.read_bytes() == original
    encoded = json.dumps(receipt)
    assert str(path) not in encoded and "PRIVATE SYNTHETIC SOURCE TEXT" not in encoded


def test_native_input_never_grants_physical_semantic_or_commercial_authority(tmp_path):
    path, sha = _pdf(tmp_path)
    receipt = _build(path, sha)
    for key in ("measurement_authority_granted", "commercial_projection_allowed",
                "takeoff_eligible", "benchmark_score_granted"):
        assert receipt[key] is False
    assert receipt["semantic_enumeration_complete"] is None
    assert receipt["decision_scope_complete"] is None
    assert not {"quantity", "quantities", "value", "canonical_walls", "customer_rows"} & set(receipt)


def test_replay_is_deterministic_without_reusing_a_producer_store(tmp_path):
    path, sha = _pdf(tmp_path)
    assert _build(path, sha) == _build(path, sha)


@pytest.mark.parametrize("rotation", (90, 180, 270))
def test_valid_rotated_originals_remain_input_only(tmp_path, rotation):
    path, _sha = _pdf(tmp_path)
    rotated = tmp_path / "rotated.pdf"
    with fitz.open(path) as doc:
        for page in doc:
            page.set_rotation(rotation)
        doc.save(rotated)
    sha = hashlib.sha256(rotated.read_bytes()).hexdigest()
    receipt = _build(rotated, sha)
    assert receipt["coverage"]["decoded_pages"] == [1, 2, 3]
    assert receipt["measurement_authority_granted"] is False
    assert _verify(receipt, rotated, sha) == receipt


def test_image_only_page_coverage_never_claims_semantic_interpretation(tmp_path):
    path = tmp_path / "image-only.pdf"
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
    image.clear_with(220)
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_image(fitz.Rect(50, 50, 150, 150), pixmap=image)
        doc.save(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = _build(path, sha, 1)
    assert receipt["coverage"]["state"] == "complete"
    assert receipt["semantic_enumeration_complete"] is None
    assert receipt["decision_scope_complete"] is None
    assert receipt["measurement_authority_granted"] is False


@pytest.mark.parametrize("change", (
    lambda r: r["page_snapshots"].pop(),
    lambda r: r["page_snapshots"].reverse(),
    lambda r: r["page_snapshots"].__setitem__(1, deepcopy(r["page_snapshots"][0])),
    lambda r: r["page_snapshots"][1].__setitem__("snapshot_id", "borrowed-source-snapshot"),
    lambda r: r["page_snapshots"][0].__setitem__("page_number", True),
    lambda r: r["page_snapshots"][0].__setitem__("observation_count", 100),
    lambda r: r["coverage"].__setitem__("decoded_pages", [1, 2]),
    lambda r: r["coverage"].__setitem__("failed_pages", [2]),
    lambda r: r["coverage"].__setitem__("revision_id", "foreign-revision"),
    lambda r: r.__setitem__("producer_version", "foreign-version"),
    lambda r: r.__setitem__("source_sha256", "0" * 64),
    lambda r: r.__setitem__("commercial_projection_allowed", True),
    lambda r: r.__setitem__("measurement_authority_granted", True),
    lambda r: r.__setitem__("takeoff_eligible", True),
    lambda r: r.__setitem__("benchmark_score_granted", True),
    lambda r: r.__setitem__("semantic_enumeration_complete", True),
    lambda r: r.__setitem__("decision_scope_complete", True),
    lambda r: r.__setitem__("quantity", 123.45),
))
def test_coordinated_tamper_with_recomputed_public_fingerprint_still_rejects(tmp_path, change):
    path, sha = _pdf(tmp_path)
    receipt = _build(path, sha)
    change(receipt)
    receipt.pop("fingerprint")
    receipt["fingerprint"] = hashlib.sha256(canonical_contract_json(receipt).encode()).hexdigest()
    with pytest.raises(ValueError, match="original-page reproof"):
        _verify(receipt, path, sha)


@pytest.mark.parametrize("count", (True, 0, -1, 1.5, "3"))
def test_page_count_aliases_reject_before_any_native_ingestion(tmp_path, monkeypatch, count):
    path, sha = _pdf(tmp_path)
    monkeypatch.setattr(module, "SourceObservationProducer", lambda **kw: pytest.fail("ingestion started"))
    with pytest.raises(ValueError, match="page count"):
        _build(path, sha, count)


@pytest.mark.parametrize("digest", ("0" * 64, "A" * 64, " malformed ", True))
def test_wrong_or_noncanonical_source_digest_cannot_start_ingestion(tmp_path, monkeypatch, digest):
    path, _sha = _pdf(tmp_path)
    monkeypatch.setattr(module, "SourceObservationProducer", lambda **kw: pytest.fail("ingestion started"))
    with pytest.raises(ValueError, match="digest"):
        _build(path, digest)


@pytest.mark.parametrize("count", (1, 2, 4))
def test_declaring_a_partial_or_oversized_page_universe_rejects(tmp_path, count):
    path, sha = _pdf(tmp_path)
    with pytest.raises(ValueError, match="incomplete"):
        _build(path, sha, count)


def test_foreign_source_cannot_borrow_an_intact_receipt(tmp_path):
    path, sha = _pdf(tmp_path)
    receipt = _build(path, sha)
    other, other_sha = _pdf(tmp_path, "foreign.pdf", pages=1)
    with pytest.raises(ValueError, match="original-page reproof"):
        _verify(receipt, other, other_sha, 1)
    with pytest.raises(ValueError, match="digest mismatch"):
        _verify(receipt, other, sha, 1)


def test_missing_and_symlinked_inputs_are_not_native_coverage(tmp_path):
    path, sha = _pdf(tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        _build(tmp_path / "missing.pdf", sha)
    alias = tmp_path / "source-alias.pdf"
    try:
        alias.symlink_to(path)
    except OSError:
        pytest.skip("filesystem does not support symlinks")
    with pytest.raises(ValueError, match="regular file"):
        _build(alias, sha)


@pytest.mark.parametrize("same_bytes", (True, False))
def test_original_namespace_or_content_change_during_decode_rejects(tmp_path, monkeypatch, same_bytes):
    path, sha = _pdf(tmp_path)
    original = module._page_receipt
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs["page"] == 1:
            replacement = tmp_path / "replacement.pdf"
            replacement.write_bytes(path.read_bytes() if same_bytes else b"changed source")
            replacement.replace(path)
        return result
    monkeypatch.setattr(module, "_page_receipt", changed)
    with pytest.raises(ValueError, match="changed during decode"):
        _build(path, sha)


def test_failed_native_page_is_not_complete_input_coverage(tmp_path, monkeypatch):
    import pb_source_observation_authority as authority
    path, sha = _pdf(tmp_path)
    original = authority._decode_native_page_for_cache
    def failed(pdf, page):
        result = original(pdf, page)
        return replace(result, failed=True, pending_items=()) if page == 2 else result
    monkeypatch.setattr(authority, "_decode_native_page_for_cache", failed)
    with pytest.raises(ValueError, match="incomplete"):
        _build(path, sha)


def test_borrowing_the_first_page_decode_for_another_page_rejects(tmp_path, monkeypatch):
    path, sha = _pdf(tmp_path)
    original = module.SourceObservationProducer
    class BorrowedPageProducer(original):
        def ingest_native_pdf_bytes(self, **kwargs):
            kwargs["page_ids"] = ("1",)
            return super().ingest_native_pdf_bytes(**kwargs)
    monkeypatch.setattr(module, "SourceObservationProducer", BorrowedPageProducer)
    with pytest.raises(ValueError, match="incomplete"):
        _build(path, sha)


def test_native_observations_without_the_original_page_marker_reject(tmp_path, monkeypatch):
    path = tmp_path / "text-page.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), "Synthetic page marker test")
        doc.save(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    original = module.SourceObservationProducer
    class MissingPageMarkerProducer(original):
        def ingest_native_pdf_bytes(self, **kwargs):
            published = super().ingest_native_pdf_bytes(**kwargs)
            snapshot = published.snapshot
            authority = self.authority()
            retained = tuple(oid for oid in snapshot.observation_ids if
                authority.resolve(module.ObservationSelector(
                    document_id=snapshot.document_id, revision_id=snapshot.revision_id,
                    source_sha256=snapshot.source_sha256, snapshot_id=snapshot.snapshot_id,
                    observation_id=oid)).observation.observation_kind != "native_pdf_page")
            assert retained
            return replace(published, snapshot=replace(snapshot, observation_ids=retained))
    monkeypatch.setattr(module, "SourceObservationProducer", MissingPageMarkerProducer)
    with pytest.raises(ValueError, match="page marker unavailable"):
        _build(path, sha, 1)


def test_corrupted_committed_observation_lineage_rejects(tmp_path, monkeypatch):
    path, sha = _pdf(tmp_path)
    original = module.SourceObservationProducer
    class CorruptProducer(original):
        def ingest_native_pdf_bytes(self, **kwargs):
            published = super().ingest_native_pdf_bytes(**kwargs)
            snapshot = published.snapshot
            key = (snapshot.snapshot_id, snapshot.observation_ids[-1])
            self._store.record_fingerprints[key] = "0" * 64
            return published
    monkeypatch.setattr(module, "SourceObservationProducer", CorruptProducer)
    with pytest.raises(ValueError, match="observation lineage unavailable"):
        _build(path, sha)


def test_different_native_revisions_cannot_be_combined(tmp_path, monkeypatch):
    path, sha = _pdf(tmp_path)
    original = module._page_receipt
    def foreign(*args, **kwargs):
        revision, receipt = original(*args, **kwargs)
        return ("foreign-revision" if kwargs["page"] == 2 else revision), receipt
    monkeypatch.setattr(module, "_page_receipt", foreign)
    with pytest.raises(ValueError, match="mixed source revisions"):
        _build(path, sha)


def test_only_one_page_producer_and_store_are_retained_at_a_time(tmp_path, monkeypatch):
    path, sha = _pdf(tmp_path, pages=12)
    original = module.SourceObservationProducer
    live = []
    gc.collect()
    class TrackedProducer(original):
        def __init__(self, **kwargs):
            assert not any(ref() is not None for pair in live for ref in pair)
            super().__init__(**kwargs)
            live.append((weakref.ref(self), weakref.ref(self._store)))
    monkeypatch.setattr(module, "SourceObservationProducer", TrackedProducer)
    receipt = _build(path, sha, 12)
    assert len(live) == 12 and len(receipt["page_snapshots"]) == 12
    assert not any(ref() is not None for pair in live for ref in pair)


def test_nonobject_receipts_reject_without_decoding(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "build_native_source_execution_coverage", lambda **kw: pytest.fail("decoded"))
    with pytest.raises(TypeError, match="JSON object"):
        _verify([], tmp_path / "unused.pdf", "0" * 64)
