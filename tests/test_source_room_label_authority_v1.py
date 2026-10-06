from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_source_room_face_authority import build_source_room_face_authority
from pb_source_room_label_authority import (
    SOURCE_ROOM_LABEL_CONFLICT,
    SOURCE_ROOM_LABEL_REQUIRED_WORD_UNRESOLVED,
    SourceRoomLabelProducer,
    SourceRoomLabelWordEvidence,
    _Word,
    _line_groups,
    _normalized_room_line,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _word(
    text: str,
    word_no: int,
    *,
    block: int = 1,
    line: int = 2,
) -> _Word:
    return _Word(
        observation_id=f"obs-{word_no}-{text}",
        receipt_id=f"receipt-{word_no}-{text}",
        source_partition_id="page:1",
        raw_text=text,
        geometry=(
            10.0 + word_no * 12.0,
            10.0,
            20.0 + word_no * 12.0,
            20.0,
        ),
        block_no=block,
        line_no=line,
        word_no=word_no,
    )


def test_whole_line_semantics_accept_room_labels_not_embedded_equipment_notes() -> None:
    assert _normalized_room_line("FOOD PREP") == "FOOD PREP"
    assert _normalized_room_line("COLD ROOM") == "COLD ROOM"
    assert _normalized_room_line("FREEZER") == "FREEZER"
    assert _normalized_room_line("PWD") == "PWD"
    assert _normalized_room_line("M-AMB") == "M-AMB"
    assert _normalized_room_line("F-AMB") == "F-AMB"
    assert _normalized_room_line("POS COUNTER") == "POS COUNTER"
    assert _normalized_room_line("WC & SHOWER") == "WC & SHOWER"
    assert (
        _normalized_room_line(
            "ICE CREAM FREEZER SUPPLIED INSTALLED BY LESSEE"
        )
        is None
    )
    assert _normalized_room_line("LAUNDRY TUB") is None
    assert _normalized_room_line("OFFICE 1") is None
    assert _normalized_room_line("M-AMB FIXTURE NOTE") is None
    assert _normalized_room_line("POS COUNTER 1") is None


def test_line_grouping_uses_exact_source_block_line_and_word_order() -> None:
    grouped = _line_groups(
        (
            _word("ROOM", 1),
            _word("COLD", 0),
            _word("OFFICE", 0, block=9, line=4),
        )
    )
    assert [
        [word.raw_text for word in group]
        for group in grouped
    ] == [
        ["COLD", "ROOM"],
        ["OFFICE"],
    ]


def test_duplicate_word_order_abstains_from_line_reconstruction() -> None:
    assert _line_groups((_word("COLD", 0), _word("ROOM", 0))) == ()


def _write_two_room_pdf(
    path: Path,
    *,
    left_lines=("FOOD PREP",),
    right_lines=("COLD ROOM",),
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300.0, height=200.0)
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
        ((150.0, 50.0), (150.0, 150.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1.0,
        )
    y = 90.0
    for text in left_lines:
        page.insert_text((75.0, y), text, fontsize=9.0)
        y += 18.0
    y = 90.0
    for text in right_lines:
        page.insert_text((175.0, y), text, fontsize=9.0)
        y += 18.0
    doc.save(path)
    doc.close()


def _setup(path: Path):
    source = SourceVisibilityProducer(
        producer_method="source-room-label-test",
        producer_version="1.0",
    )
    source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
        page_ids=("1",),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    room_faces = build_source_room_face_authority(walls)
    return source, room_faces


def _fake_authorized(
    _self,
    _published,
    word: _Word,
):
    return SourceRoomLabelWordEvidence(
        observation_id=word.observation_id,
        receipt_id=word.receipt_id,
        trusted_text=word.raw_text,
        authority_kind="test_authenticated_text",
        authority_record_id=f"authority:{word.observation_id}",
        geometry=word.geometry,
        word_no=word.word_no,
    )


def _records(producer: SourceRoomLabelProducer):
    return [
        record
        for result in producer.published_results()
        for record in result.records
    ]


def test_end_to_end_binds_complete_source_lines_to_exact_room_faces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "two-room-labels.pdf"
    _write_two_room_pdf(path)
    source, room_faces = _setup(path)
    monkeypatch.setattr(
        SourceRoomLabelProducer,
        "_authorize_word",
        _fake_authorized,
    )

    producer = SourceRoomLabelProducer.from_authorities_for_tests(
        source,
        room_faces,
        MockOCRBackend(),
        page_ids=("1",),
    )
    records = _records(producer)

    assert {record.label for record in records} == {
        "FOOD PREP",
        "COLD ROOM",
    }
    assert len({record.face_id for record in records}) == 2
    assert all(
        record.status is EvidenceResolutionStatus.CORROBORATED
        for record in records
    )
    assert all(record.observation_ids for record in records)


def test_unresolved_required_word_blocks_only_that_room_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "one-word-unresolved.pdf"
    _write_two_room_pdf(path)
    source, room_faces = _setup(path)

    def authorize(self, published, word):
        if word.raw_text == "PREP":
            return None
        return _fake_authorized(self, published, word)

    monkeypatch.setattr(
        SourceRoomLabelProducer,
        "_authorize_word",
        authorize,
    )
    producer = SourceRoomLabelProducer.from_authorities_for_tests(
        source,
        room_faces,
        MockOCRBackend(),
        page_ids=("1",),
    )
    records = _records(producer)
    assert {record.label for record in records} == {"COLD ROOM"}
    assert any(
        SOURCE_ROOM_LABEL_REQUIRED_WORD_UNRESOLVED
        in result.reason_codes
        for result in producer.published_results()
    )


def test_two_distinct_authenticated_label_lines_in_one_face_conflict_not_rank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "conflict.pdf"
    _write_two_room_pdf(
        path,
        left_lines=("OFFICE", "STUDY"),
        right_lines=("COLD ROOM",),
    )
    source, room_faces = _setup(path)
    monkeypatch.setattr(
        SourceRoomLabelProducer,
        "_authorize_word",
        _fake_authorized,
    )

    producer = SourceRoomLabelProducer.from_authorities_for_tests(
        source,
        room_faces,
        MockOCRBackend(),
        page_ids=("1",),
    )
    records = _records(producer)
    assert {record.label for record in records} == {"COLD ROOM"}
    assert any(
        SOURCE_ROOM_LABEL_CONFLICT in result.reason_codes
        for result in producer.published_results()
    )


def test_room_looking_token_inside_long_note_is_never_cherry_picked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "note.pdf"
    _write_two_room_pdf(
        path,
        left_lines=(
            "ICE CREAM FREEZER SUPPLIED INSTALLED BY LESSEE",
        ),
        right_lines=("COLD ROOM",),
    )
    source, room_faces = _setup(path)
    monkeypatch.setattr(
        SourceRoomLabelProducer,
        "_authorize_word",
        _fake_authorized,
    )

    producer = SourceRoomLabelProducer.from_authorities_for_tests(
        source,
        room_faces,
        MockOCRBackend(),
        page_ids=("1",),
    )
    assert {
        record.label for record in _records(producer)
    } == {"COLD ROOM"}
