from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_source_execution_callout_authority import (
    MAX_EXECUTION_SPAN,
    SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED,
    SourceExecutionCalloutProducer,
    SourceExecutionWordEvidence,
    _Word,
    _execution_clusters,
    _receipt_interval,
    _semantic_candidate,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _word(
    observation_id: str,
    text: str,
    seq_start: int,
    seq_end: int | None = None,
    *,
    x: float = 0.0,
    y: float = 0.0,
    partition: str = "partition-1",
) -> _Word:
    return _Word(
        observation_id=observation_id,
        receipt_id=f"receipt-{observation_id}",
        source_partition_id=partition,
        raw_text=text,
        geometry=(x, y, x + max(5.0, len(text) * 3.0), y + 10.0),
        sequence_start=seq_start,
        sequence_end=seq_start if seq_end is None else seq_end,
    )


def test_receipt_interval_uses_source_execution_trace_not_adapter_order() -> None:
    receipt = SimpleNamespace(
        sequence_number=100,
        trace_sequence_numbers=(100, 101, 102),
        block_no=999,
        line_no=888,
        word_no=777,
    )
    assert _receipt_interval(receipt) == (100, 102)


def test_execution_clusters_join_overlapping_and_consecutive_source_sequences() -> None:
    words = (
        _word("a", "walling", 10, 11, x=0),
        _word("b", "plaster", 11, x=30),
        _word("c", "paint", 12, x=60),
        _word("d", "finish", 13, x=90),
        _word("e", "internally.", 14, 15, x=120),
        _word("later", "unrelated", 20, x=0),
    )
    clusters = _execution_clusters(words)
    assert [[word.observation_id for word in cluster] for cluster in clusters] == [
        ["a", "b", "c", "d", "e"],
        ["later"],
    ]


def test_execution_clusters_never_cross_source_partition() -> None:
    clusters = _execution_clusters(
        (
            _word("left", "walling", 10, partition="A"),
            _word("right", "finish", 10, partition="B"),
        )
    )
    assert len(clusters) == 2


def test_internal_semantics_require_only_semantically_essential_words() -> None:
    cluster = (
        _word("wall", "walling", 100),
        _word("concrete", "concrete", 101),
        _word("plaster", "plaster", 102),
        _word("and", "and", 102, x=30),
        _word("paint", "paint", 103),
        _word("finish", "finish", 104),
        _word("direction", "internally.", 105, 106),
    )
    candidate = _semantic_candidate(cluster)
    assert candidate is not None
    semantics, required = candidate
    assert {semantic.trade_scope_id for semantic in semantics} == {
        "internal_plaster",
        "internal_paint",
    }
    assert set(required) == {"wall", "plaster", "paint", "finish", "internally"}
    assert "concrete" not in {word.observation_id for word in required.values()}


def test_external_semantics_require_direction_word() -> None:
    assert _semantic_candidate(
        (
            _word("wall", "walling", 1),
            _word("key", "key", 2),
            _word("finish", "finish", 3),
        )
    ) is None


def test_duplicate_required_token_is_ambiguous_not_ranked() -> None:
    assert _semantic_candidate(
        (
            _word("wall-1", "wall", 1),
            _word("wall-2", "walling", 1, x=20),
            _word("key", "key", 2),
            _word("finish", "finish", 3),
            _word("direction", "externally.", 4),
        )
    ) is None


def test_competing_internal_and_external_semantics_abstain() -> None:
    assert _semantic_candidate(
        (
            _word("wall", "walling", 1),
            _word("key", "key", 2),
            _word("plaster", "plaster", 3),
            _word("paint", "paint", 4),
            _word("finish", "finish", 5),
            _word("external", "externally.", 6),
            _word("internal", "internally.", 7),
        )
    ) is None


def test_oversized_execution_run_is_not_sliced_into_convenient_callout() -> None:
    cluster = (
        _word("wall", "walling", 1),
        _word("key", "key", 2),
        _word("finish", "finish", 3),
        _word("direction", "externally.", MAX_EXECUTION_SPAN + 2),
    )
    assert _semantic_candidate(cluster) is None


def _write_internal_callout(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=360, height=180)
    page.insert_text(
        (40, 80),
        "walling blocks plaster and paint to finish internally.",
        fontsize=10,
    )
    doc.save(path)
    doc.close()


def _ingest(path: Path) -> SourceVisibilityProducer:
    source = SourceVisibilityProducer(
        producer_method="source-execution-callout-test",
        producer_version="1.0",
    )
    source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
        page_ids=("1",),
    )
    return source


def _fake_authorized_word(published, word: _Word, category: str):
    del published
    return SourceExecutionWordEvidence(
        observation_id=word.observation_id,
        receipt_id=word.receipt_id,
        trusted_text=word.raw_text,
        authority_kind="test_proven_word",
        authority_record_id=f"test:{word.observation_id}",
        sequence_start=word.sequence_start,
        sequence_end=word.sequence_end,
        geometry=word.geometry,
    )


def test_end_to_end_source_execution_record_ignores_block_line_word_adapter_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "internal.pdf"
    _write_internal_callout(path)
    source = _ingest(path)

    monkeypatch.setattr(
        SourceExecutionCalloutProducer,
        "_authorize_word",
        lambda self, published, word, category: _fake_authorized_word(
            published, word, category
        ),
    )
    producer = SourceExecutionCalloutProducer.from_source_visibility_producer_for_tests(
        source,
        MockOCRBackend(),
        page_ids=("1",),
    )
    records = [
        record
        for result in producer.published_results()
        for record in result.records
    ]
    assert len(records) == 1
    record = records[0]
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert {semantic.trade_scope_id for semantic in record.semantics} == {
        "internal_plaster",
        "internal_paint",
    }
    assert record.sequence_start <= record.sequence_end
    assert record.source_bbox[2] > record.source_bbox[0]


def test_essential_word_failure_blocks_end_to_end_callout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "essential-failure.pdf"
    _write_internal_callout(path)
    source = _ingest(path)

    def authorize(self, published, word, category):
        if category == "internally":
            return None
        return _fake_authorized_word(published, word, category)

    monkeypatch.setattr(
        SourceExecutionCalloutProducer,
        "_authorize_word",
        authorize,
    )
    producer = SourceExecutionCalloutProducer.from_source_visibility_producer_for_tests(
        source,
        MockOCRBackend(),
        page_ids=("1",),
    )
    results = producer.published_results()
    assert all(not result.records for result in results)
    assert any(
        SOURCE_EXECUTION_CALLOUT_REQUIRED_WORD_UNRESOLVED in result.reason_codes
        for result in results
    )
