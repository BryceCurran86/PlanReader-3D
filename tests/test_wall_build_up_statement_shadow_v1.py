"""Wall build-up statements: a pure parser and an authenticated-text collector (shadow, diagnostic only)."""
from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_build_up_statement_shadow import (
    SCOPE_INTERNAL_WALLS,
    collect_wall_build_up_statements,
    parse_wall_build_up_statement,
)

NOTE = (
    "THE INTERNAL WALLS TO BE 70mm PINE STUD FRAMES UNLESS OTHERWISE NOTED AND SHALL "
    "BE LINED WITH 10mm GYPROCK AND 6mm VILLA BOARD TO THE WET AREA'S AS REQUIRED"
)


def test_parses_the_internal_wall_statement_with_its_wet_area_variant_and_scope_clause():
    parsed = parse_wall_build_up_statement(NOTE)
    assert parsed is not None
    assert (parsed.scope, parsed.frame_mm, parsed.lining_mm) == (SCOPE_INTERNAL_WALLS, 70.0, 10.0)
    assert parsed.lining_material == "GYPROCK"
    assert (parsed.wet_area_lining_mm, parsed.wet_area_lining_material) == (6.0, "VILLA BOARD")
    assert parsed.unless_otherwise_noted is True


@pytest.mark.parametrize("text, frame, lining, otherwise", [
    ("THE INTERNAL WALLS TO BE 90 MM PINE STUD FRAMES AND SHALL BE LINED WITH 13 MM PLASTERBOARD", 90.0, 13.0, False),
    ("internal wall are 70mm timber frame lined with 10mm gyprock", 70.0, 10.0, False),
    ("THE INTERNAL WALLS TO BE\n70mm   PINE STUD\nFRAMES UNLESS OTHERWISE NOTED\nBE LINED WITH 10mm GYPROCK".replace("\nBE", " AND SHALL BE"), 70.0, 10.0, True),
])
def test_accepts_equivalent_wordings_with_exact_numbers(text, frame, lining, otherwise):
    parsed = parse_wall_build_up_statement(text)
    assert parsed is not None and (parsed.frame_mm, parsed.lining_mm, parsed.unless_otherwise_noted) == (frame, lining, otherwise)
    assert parsed.wet_area_lining_mm is None


@pytest.mark.parametrize("text", [
    "THE EXTERNAL LIGHT WEIGHT CLAD WALLS TO HAVE SARKING & BATT INSULATION FITTED AS REQUIRED",
    "THE EXTERNAL WALLS TO BE 90mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK",  # not an internal-wall note
    "THE INTERNAL WALLS TO BE 70mm PINE STUD FRAMES",  # no lining thickness stated
    "THE INTERNAL WALLS TO BE PINE STUD FRAMES AND SHALL BE LINED WITH GYPROCK",  # no numbers
    "THE INTERNAL WALLS TO BE 7Omm PINE STUD FRAMES AND SHALL BE LINED WITH 1Omm GYPROCK",  # unreadable digits
    "THE INTERNAL WALLS TO BE 70mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm CARPET",  # not a board
    "THE INTERNAL WALLS TO BE 0mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK",
    "THE CEILINGS TO BE 10mm GYPROCK FITTED TO BATTENS",
    "",
    NOTE + " " + NOTE,  # two readings in one block: neither is chosen
])
def test_refuses_anything_that_is_not_exactly_one_internal_wall_statement(text):
    assert parse_wall_build_up_statement(text) is None


def _pdf(note: str = NOTE, other: str = "") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=600.0, height=400.0)
    page.insert_textbox(fitz.Rect(40, 40, 300, 160), note, fontsize=9.0)
    if other:
        page.insert_textbox(fitz.Rect(40, 220, 300, 320), other, fontsize=9.0)
    return doc.tobytes()


def _source(data: bytes):
    source = SourceVisibilityProducer(producer_method="statement-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="statement-doc", source_bytes=data, source_locator="memory://statement.pdf", page_ids=("1",))
    return source, published


def test_collects_a_statement_from_authenticated_native_text_with_its_provenance():
    source, published = _source(_pdf())
    statements = collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("1",))
    assert len(statements) == 1
    statement = statements[0]
    assert (statement.page_id, statement.frame_mm, statement.lining_mm) == ("1", 70.0, 10.0)
    assert statement.source_sha256 == published.revision.source_sha256
    assert statement.revision_id == published.revision.revision_id and statement.snapshot_id == published.snapshot.snapshot_id
    assert len(statement.observation_ids) == len(NOTE.split()) and len(statement.text_sha256) == 64
    assert statement.takeoff_eligible is False and statement.commercial_projection_allowed is False and statement.diagnostic_only
    # deterministic replay
    assert collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("1",)) == statements


def test_reads_only_the_pages_named_and_ignores_other_notes():
    data = _pdf(note="SOME UNRELATED NOTE ABOUT THE ROOF", other=NOTE)
    source, published = _source(data)
    assert len(collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("1",))) == 1
    assert collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("2",)) == ()
    assert collect_wall_build_up_statements(source, revision_id="no-such-revision", page_ids=("1",)) == ()


def test_a_note_with_no_statement_collects_nothing():
    source, published = _source(_pdf(note="THE INTERNAL WALLS TO BE 70mm PINE STUD FRAMES"))
    assert collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("1",)) == ()


def test_a_block_with_any_word_that_cannot_be_proved_collects_nothing_even_if_the_rest_parses():
    # an opaque box painted over the optional clause: the remaining words alone would still parse as a statement,
    # but the block is not authenticated word for word, so it is not a source statement at all
    doc = fitz.open()
    page = doc.new_page(width=600.0, height=400.0)
    page.insert_textbox(fitz.Rect(40, 40, 300, 160), NOTE, fontsize=9.0)
    covered = page.search_for("UNLESS OTHERWISE NOTED")
    assert covered
    for rect in covered:
        page.draw_rect(rect, color=None, fill=(1, 1, 1))
    source, published = _source(doc.tobytes())
    assert collect_wall_build_up_statements(source, revision_id=published.revision.revision_id, page_ids=("1",)) == ()


# ---- the collector's own logic against a stub of the text authorities (ordering, duplicates, corroboration)


class _StubText:
    def __init__(self, observations):
        self._observations = observations  # id -> (receipt, native_ok)

    def observation_ids_with_receipt_page(self, _snapshot, _ids, page_id):
        return tuple(oid for oid, (receipt, _ok) in self._observations.items() if receipt.page_id == page_id)

    def resolve_text(self, selector):
        receipt, native_ok = self._observations[selector.observation_id]
        return SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED if native_ok else EvidenceResolutionStatus.ABSTAINED,
            trusted_text=receipt.raw_text if native_ok else None, receipt=receipt)


class _StubSource:
    def __init__(self, observations):
        self._text = _StubText(observations)
        self._published = SimpleNamespace(
            snapshot=SimpleNamespace(snapshot_id="snapshot-1"),
            revision=SimpleNamespace(document_id="doc-1", revision_id="revision-1", source_sha256="ab" * 32),
            text_observation_ids=tuple(observations))

    def published_snapshot_for_revision(self, revision_id):
        return self._published if revision_id == "revision-1" else None

    def text_integrity_authority(self):
        return self._text


def _words(positions=None, native_ok=True):
    words = NOTE.split()
    receipts = {}
    for index, word in enumerate(words):
        line, number = (positions or {}).get(index, divmod(index, 6))
        receipts[f"obs-{index}"] = (SimpleNamespace(
            page_id="1", block_no=3, line_no=line, word_no=number, raw_text=word, source_partition_id="part-1"), native_ok)
    return receipts


def _raster(monkeypatch, *, status, text):
    import pb_raster_text_corroboration_authority as raster_module

    class _Raster:
        @staticmethod
        def from_source_visibility_producer(_source):
            return SimpleNamespace(publish=lambda selector: SimpleNamespace(
                status=status, record=object() if status is EvidenceResolutionStatus.CORROBORATED else None,
                corroborated_text=text(selector)))

    monkeypatch.setattr(raster_module, "RasterTextCorroborationProducer", _Raster)


def test_words_are_read_in_position_order_whatever_order_the_authority_lists_them(monkeypatch):
    _raster(monkeypatch, status=EvidenceResolutionStatus.ABSTAINED, text=lambda _s: None)
    observations = _words()
    shuffled = dict(reversed(list(observations.items())))
    statements = collect_wall_build_up_statements(_StubSource(shuffled), revision_id="revision-1", page_ids=("1",))
    assert len(statements) == 1 and statements[0].frame_mm == 70.0
    assert statements[0].observation_ids == tuple(f"obs-{i}" for i in range(len(NOTE.split())))


def test_a_duplicated_word_position_is_not_a_reading_order_and_collects_nothing(monkeypatch):
    _raster(monkeypatch, status=EvidenceResolutionStatus.ABSTAINED, text=lambda _s: None)
    positions = {5: (0, 4)}  # word 5 claims the position word 4 already holds
    assert collect_wall_build_up_statements(
        _StubSource(_words(positions)), revision_id="revision-1", page_ids=("1",)) == ()


def test_a_word_only_the_raster_authority_proves_counts_only_when_that_proof_is_corroborated(monkeypatch):
    texts = {f"obs-{i}": word for i, word in enumerate(NOTE.split())}
    observations = _words(native_ok=False)
    # corroborated by the independent raster authority word for word: the statement is read
    _raster(monkeypatch, status=EvidenceResolutionStatus.CORROBORATED, text=lambda s: texts[s.observation_id])
    assert len(collect_wall_build_up_statements(_StubSource(observations), revision_id="revision-1", page_ids=("1",))) == 1
    # a reading that is present but not corroborated is not proof, however parseable the claimed word is
    _raster(monkeypatch, status=EvidenceResolutionStatus.ABSTAINED, text=lambda s: texts[s.observation_id])
    assert collect_wall_build_up_statements(_StubSource(observations), revision_id="revision-1", page_ids=("1",)) == ()
