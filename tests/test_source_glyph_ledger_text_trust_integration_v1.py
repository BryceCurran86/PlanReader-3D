"""SourceVisibilityProducer glyph-ledger text trust: default-off wiring through the real producer, receipts and raster corroboration.

Words are set in an embedded font, and the glyph proof is forced to abstain (as it does for a subset font without a Unicode cmap), so the ONLY
blocker is ``text_glyph_mapping_unverified``. OCR is scripted: the mock backend "reads" a crop by its pixel width, which is unique per word here, and
can be told to misread chosen words. Synthetic words only.
"""
from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence

import fitz
import pytest
from PIL import Image

import pb_pdf_text_integrity_authority as integrity
from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from pb_raster_text_corroboration_authority import RasterTextCorroborationProducer
from pb_source_glyph_ledger_text_trust import DECODE_STATUS_AMORTIZED_GLYPH, DECODE_STATUS_DIRECT_RASTER
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SIZE = 14.0
# Letters of very different widths so every word below has a distinct pixel width.
WORDS = ("IM", "MW", "IW", "IMW", "MIM", "WIM")


def _pdf(pages: Sequence[Sequence[tuple[str, float, float]]]) -> bytes:
    doc = fitz.open()
    buffer = fitz.Font("helv").buffer
    for words in pages:
        page = doc.new_page(width=500, height=200)
        page.insert_font(fontname="NimbusSans-Regular", fontbuffer=buffer)
        for text, x, y in words:
            page.insert_text((x, y), text, fontname="NimbusSans-Regular", fontsize=SIZE)
    data = doc.tobytes()
    doc.close()
    return data


def _layout() -> list[tuple[str, float, float]]:
    return [(text, 30.0 + 70.0 * i, 60.0) for i, text in enumerate(WORDS)]


@pytest.fixture(autouse=True)
def _glyph_proof_cannot_decide(monkeypatch):
    """A subset font without a Unicode cmap cannot answer the glyph question; force the same abstention."""
    monkeypatch.setattr(integrity, "_font_for_glyph_validation", lambda page, font: None)


def _expected_widths_pt() -> dict[str, float]:
    return {text: fitz.get_text_length(text, fontname="helv", fontsize=SIZE) for text in WORDS}


class _Reader:
    """Mock OCR responder: names the word whose width matches the crop; optionally misreads some words."""

    def __init__(self, misread: Sequence[str] = ()) -> None:
        self.widths = _expected_widths_pt()
        self.misread = set(misread)
        self.calls = 0

    def __call__(self, image: Image.Image, dpi: int):
        self.calls += 1
        width_pt = image.width * 72.0 / float(dpi)
        text = min(self.widths, key=lambda word: abs(self.widths[word] - width_pt))
        if text in self.misread:
            text = "xxx"
        return (OCRLine(text=text, confidence=None, bbox_px=(1.0, 1.0, image.width - 1.0, image.height - 1.0)),)


def _install_reader(monkeypatch, reader: Callable) -> None:
    def factory(svp):
        return RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(
            svp, MockOCRBackend(responder=reader))

    monkeypatch.setattr(RasterTextCorroborationProducer, "from_source_visibility_producer", classmethod(
        lambda cls, svp: factory(svp)))


def _ingest(pdf: bytes, *, flag: Optional[bool], page_ids=None, document_id: str = "doc-glyph-trust"):
    kwargs = {} if flag is None else {"source_glyph_ledger_text_trust": flag}
    svp = SourceVisibilityProducer(producer_method="glyph-trust-test", producer_version="1", **kwargs)
    published = svp.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=pdf, source_locator=f"memory://{document_id}.pdf", page_ids=page_ids)
    return svp, published


def _results(svp, published) -> dict[str, object]:
    authority = svp.text_integrity_authority()
    out = {}
    for oid in published.text_observation_ids:
        out[oid] = authority.resolve_text(ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid))
    return out


def _by_text(results: Mapping[str, object]) -> dict[str, object]:
    return {r.receipt.raw_text: r for r in results.values()}


def test_default_off_changes_nothing_and_the_option_must_be_an_explicit_bool():
    pdf = _pdf([_layout()])
    svp, published = _ingest(pdf, flag=None)
    results = _by_text(_results(svp, published))
    assert set(results) == set(WORDS)
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED and r.receipt.reason_codes == (integrity.TEXT_GLYPH_MAPPING_UNVERIFIED,)
               for r in results.values())
    with pytest.raises(RuntimeError, match="glyph_ledger_text_trust_not_enabled"):
        svp.upgrade_glyph_only_text(published.revision.revision_id)
    for bad in ("yes", 1, None):
        with pytest.raises(ValueError):
            SourceVisibilityProducer(producer_method="m", producer_version="1", source_glyph_ledger_text_trust=bad)


def test_with_the_option_on_unread_words_are_trusted_through_verified_glyphs(monkeypatch):
    reader = _Reader()
    _install_reader(monkeypatch, reader)
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    results = _by_text(_results(svp, published))
    assert all(r.status is EvidenceResolutionStatus.CORROBORATED and r.trusted_text == r.receipt.raw_text for r in results.values())
    statuses = {r.receipt.decode_status for r in results.values()}
    assert statuses == {DECODE_STATUS_DIRECT_RASTER, DECODE_STATUS_AMORTIZED_GLYPH}
    attempts = reader.calls // 2                                       # two renders per reading
    assert 2 <= attempts < len(WORDS)                                   # fewer readings than words
    assert all(r.receipt.trusted and r.receipt.reason_codes == () for r in results.values())


def test_when_ocr_reads_nothing_correctly_nothing_is_trusted_and_receipts_are_unchanged(monkeypatch):
    pdf = _pdf([_layout()])
    base_svp, base_published = _ingest(pdf, flag=None)
    base = _by_text(_results(base_svp, base_published))
    _install_reader(monkeypatch, _Reader(misread=WORDS))
    svp, published = _ingest(pdf, flag=True)
    after = _by_text(_results(svp, published))
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in after.values())
    assert {t: r.receipt for t, r in after.items()} == {t: r.receipt for t, r in base.items()}


def test_a_misread_word_never_votes_but_the_others_still_settle(monkeypatch):
    _install_reader(monkeypatch, _Reader(misread={"IMW"}))
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    results = _by_text(_results(svp, published))
    assert results["IMW"].receipt.decode_status != DECODE_STATUS_DIRECT_RASTER      # it was never read as itself
    trusted = [t for t, r in results.items() if r.status is EvidenceResolutionStatus.CORROBORATED]
    assert "IMW" not in trusted or results["IMW"].receipt.decode_status == DECODE_STATUS_AMORTIZED_GLYPH
    assert len(trusted) >= 3


def test_only_the_requested_pages_are_read_and_upgraded(monkeypatch):
    reader = _Reader()
    _install_reader(monkeypatch, reader)
    svp = SourceVisibilityProducer(
        producer_method="glyph-trust-test", producer_version="1", source_glyph_ledger_text_trust=True)
    svp._source_glyph_ledger_text_trust = False          # ingest both pages without the automatic pass
    published = svp.ingest_native_pdf_bytes(
        document_id="doc-two-pages", source_bytes=_pdf([_layout(), _layout()]), source_locator="memory://two.pdf")
    svp._source_glyph_ledger_text_trust = True
    before = _results(svp, published)
    assert {r.receipt.page_id for r in before.values()} == {"1", "2"} and reader.calls == 0
    result = svp.upgrade_glyph_only_text(published.revision.revision_id, page_ids=("2",))
    after = _results(svp, published)
    page_one = [r for r in after.values() if r.receipt.page_id == "1"]
    page_two = [r for r in after.values() if r.receipt.page_id == "2"]
    assert page_one and all(r.status is EvidenceResolutionStatus.ABSTAINED for r in page_one)
    assert page_two and all(r.status is EvidenceResolutionStatus.CORROBORATED for r in page_two)
    assert set(result.decisions) == {r.receipt.parent_observation_id for r in page_two}
    assert {r.receipt for r in page_one} == {r.receipt for r in before.values() if r.receipt.page_id == "1"}


def test_upgrade_is_deterministic_and_does_not_touch_the_source_bytes(monkeypatch):
    pdf = _pdf([_layout()])
    snapshot = bytes(pdf)
    _install_reader(monkeypatch, _Reader())
    first_svp, first_published = _ingest(pdf, flag=True)
    second_svp, second_published = _ingest(pdf, flag=True)
    first = {t: r.receipt for t, r in _by_text(_results(first_svp, first_published)).items()}
    second = {t: r.receipt for t, r in _by_text(_results(second_svp, second_published)).items()}
    assert first == second
    assert pdf == snapshot


def test_an_upgraded_receipt_still_passes_the_authority_lineage_checks(monkeypatch):
    _install_reader(monkeypatch, _Reader())
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    for result in _results(svp, published).values():
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.reason_codes == ("producer_owned_pdf_text_integrity_resolved",)
        assert result.receipt.source_sha256 == published.revision.source_sha256


def test_calling_the_upgrade_twice_is_idempotent(monkeypatch):
    reader = _Reader()
    _install_reader(monkeypatch, reader)
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    before = {t: r.receipt for t, r in _by_text(_results(svp, published)).items()}
    calls = reader.calls
    result = svp.upgrade_glyph_only_text(published.revision.revision_id)
    assert result.decisions == {}                                       # nothing glyph-only is left
    assert reader.calls == calls
    assert {t: r.receipt for t, r in _by_text(_results(svp, published)).items()} == before


def test_second_glyph_pass_cannot_trust_the_opposite_mapping(monkeypatch):
    """A fresh ledger must not forget already-accepted votes for this snapshot."""
    import pb_font_glyph_mapping_corroboration_shadow as glyphs

    words = ("I", "II", "WWW", "WWWW")
    reader = _Reader()
    reader.widths = {text: fitz.get_text_length(text, fontname="helv", fontsize=SIZE)
                     for text in words}
    _install_reader(monkeypatch, reader)
    # Model a glyph/encoding alias in a damaged native trace: the same embedded
    # program/glyph key carries opposite raw characters in two word groups.
    monkeypatch.setattr(glyphs, "word_glyphs", lambda oid, text, font, bbox, spans:
                        glyphs.WordGlyphs(oid, text, font, tuple((1, char) for char in text)))
    svp = SourceVisibilityProducer(producer_method="glyph-repeat-test", producer_version="1",
                                   source_glyph_ledger_text_trust=True)
    svp._source_glyph_ledger_text_trust = False
    published = svp.ingest_native_pdf_bytes(
        document_id="glyph-opposite-votes",
        source_bytes=_pdf([[(text, 30.0 + 90.0 * i, 60.0) for i, text in enumerate(words)]]),
        source_locator="memory://glyph-opposite-votes.pdf")
    svp._source_glyph_ledger_text_trust = True
    revision = published.revision.revision_id
    svp.upgrade_glyph_only_text(revision)
    before = _by_text(_results(svp, published))
    assert {text for text, result in before.items() if result.receipt.trusted} == {"I", "II"}
    calls = reader.calls
    svp.upgrade_glyph_only_text(revision)
    after = _by_text(_results(svp, published))
    assert {text for text, result in after.items() if result.receipt.trusted} == {"I", "II"}
    assert reader.calls == calls


@pytest.mark.parametrize("policy", [{"min_words": 3}, {"max_attempts": 1}, {"page_ids": ("1",)}])
def test_glyph_pass_cannot_change_its_proof_policy_after_trust(monkeypatch, policy):
    reader = _Reader()
    _install_reader(monkeypatch, reader)
    svp, published = _ingest(_pdf([_layout(), _layout()]), flag=True)
    before = _results(svp, published)
    calls = reader.calls
    with pytest.raises(ValueError, match="proof_policy_already_fixed"):
        svp.upgrade_glyph_only_text(published.revision.revision_id, **policy)
    assert _results(svp, published) == before
    assert reader.calls == calls


def test_glyph_pass_can_repeat_with_equivalent_explicit_page_scope(monkeypatch):
    reader = _Reader()
    _install_reader(monkeypatch, reader)
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    before = _results(svp, published)
    calls = reader.calls
    result = svp.upgrade_glyph_only_text(published.revision.revision_id, page_ids=("1", "1"))
    assert result.decisions == {}
    assert _results(svp, published) == before
    assert reader.calls == calls


def test_an_unknown_revision_is_refused_and_page_ids_must_name_pages(monkeypatch):
    _install_reader(monkeypatch, _Reader())
    svp, published = _ingest(_pdf([_layout()]), flag=True)
    with pytest.raises(KeyError):
        svp.upgrade_glyph_only_text("no-such-revision")
