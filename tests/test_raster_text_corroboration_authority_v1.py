"""Adversarial tests for RasterTextCorroborationProducer / Authority.

The native word is a claim. It is corroborated only when the immutable source,
rendered twice (300 and 450 DPI) over the exact producer-owned word bbox and
read by OCR with no padding or other preprocessing, yields the same single
textual reading twice and that reading equals the claim exactly.

All PDFs are hand-built and synthetic. CI has no RapidOCR, so behaviour is
scripted through the tests-only MockOCRBackend ``responder`` hook; the two real
RapidOCR tests skip when the backend is not installed.
"""
from __future__ import annotations

import inspect
from typing import Callable, Mapping, Optional, Sequence

import fitz
import pytest
from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_TRACE_AMBIGUOUS,
)
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    OCRLine,
    PortableRasterOCRProducer,
    PortableRasterOCRSelector,
    RapidOCRBackend,
)
from pb_raster_text_corroboration_authority import (
    RASTER_TEXT_ALREADY_TRUSTED,
    RASTER_TEXT_BACKEND_ERROR,
    RASTER_TEXT_BACKEND_UNAVAILABLE,
    RASTER_TEXT_COMPETING_READINGS,
    RASTER_TEXT_CORROBORATED,
    RASTER_TEXT_CORROBORATION_DPIS,
    RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY,
    RASTER_TEXT_NATIVE_MISMATCH,
    RASTER_TEXT_NO_READING,
    RASTER_TEXT_OBSERVATION_NOT_NATIVE_WORD,
    RASTER_TEXT_OCR_GEOMETRY_INVALID,
    RASTER_TEXT_PAGE_LINEAGE_MISMATCH,
    RASTER_TEXT_RECORD_UNAVAILABLE,
    RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED,
    RASTER_TEXT_VIEW_DISAGREEMENT,
    RasterTextCorroborationAuthority,
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
    normalize_reading,
)
from pb_source_observation_authority import (
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    STALE_REVISION,
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_pdf_text_integrity_source_state_v1 import (
    _SYSINFO_DUP,
    _cmap,
    _pdf,
    _stream_obj,
)

DOC = "doc-raster-corroboration"

OCR_AVAILABLE = RapidOCRBackend().is_available()
needs_real_ocr = pytest.mark.skipif(not OCR_AVAILABLE, reason="RapidOCR is not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _glyph_unverified_pdf(
    words: Sequence[tuple[str, float, float]],
    *,
    size: float = 14.0,
    code_to_unicode: Optional[Mapping[int, int]] = None,
    extra_stream: str = "",
    pages: int = 1,
) -> bytes:
    """Words in an unembedded non-Base14 font with a valid ToUnicode.

    The only text-integrity reason is ``text_glyph_mapping_unverified``: the
    font program cannot be reconstructed, so ToUnicode alone cannot be trusted.
    """

    codes = sorted({ord(ch) for text, _x, _y in words for ch in text})
    override = code_to_unicode or {}
    mappings = "\n".join(f"<{c:02X}> <{override.get(c, c):04X}>" for c in codes)
    cmap = _cmap(sysinfo=_SYSINFO_DUP, mappings=mappings, count=len(codes))
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")

    ops = "".join(f"BT /F1 {size} Tf {x} {y} Td ({esc(t)}) Tj ET " for t, x, y in words)
    return _pdf(
        ops + extra_stream,
        fonts={
            "F1": (
                5,
                "<< /Type /Font /Subtype /Type1 /BaseFont /Arial /FirstChar 32 /LastChar 126 /ToUnicode 6 0 R >>",
            )
        },
        extra={6: _stream_obj(cmap)},
    )


class _Setup:
    def __init__(self, pdf: bytes, backend: MockOCRBackend, *, document_id: str = DOC) -> None:
        self.svp = SourceVisibilityProducer(producer_method="raster-corroboration-test", producer_version="1")
        self.published = self.svp.ingest_native_pdf_bytes(
            document_id=document_id, source_bytes=pdf, source_locator=f"memory://{document_id}.pdf"
        )
        self.backend = backend
        self.producer = RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(
            self.svp, backend
        )
        self.text_authority = self.svp.text_integrity_authority()
        self._receipts: dict[str, object] = {}
        for oid in self.published.text_observation_ids:
            result = self.text_authority.resolve_text(self._observation_selector(oid))
            self._receipts[oid] = result.receipt

    def _observation_selector(self, oid: str, **overrides) -> ObservationSelector:
        args = dict(
            document_id=self.published.revision.document_id,
            revision_id=self.published.revision.revision_id,
            source_sha256=self.published.revision.source_sha256,
            snapshot_id=self.published.snapshot.snapshot_id,
            observation_id=oid,
        )
        args.update(overrides)
        return ObservationSelector(**args)

    def selector(self, oid: str, **overrides) -> RasterTextCorroborationSelector:
        s = self._observation_selector(oid, **overrides)
        return RasterTextCorroborationSelector(
            document_id=s.document_id,
            revision_id=s.revision_id,
            source_sha256=s.source_sha256,
            snapshot_id=s.snapshot_id,
            observation_id=s.observation_id,
        )

    def oid_of(self, text: str, *, index: int = 0) -> str:
        matches = [oid for oid, r in self._receipts.items() if r.raw_text == text]
        assert len(matches) > index, (text, [r.raw_text for r in self._receipts.values()])
        return sorted(matches)[index]

    def publish(self, text: str, **overrides):
        return self.producer.publish(self.selector(self.oid_of(text), **overrides))


def _line(image: Image.Image, text: str) -> OCRLine:
    return OCRLine(text=text, confidence=None, bbox_px=(2.0, 2.0, image.width - 2.0, image.height - 2.0))


def _reads(by_dpi: Mapping[int, Optional[str]]) -> Callable[[Image.Image, int], Sequence[OCRLine]]:
    def responder(image: Image.Image, dpi: int):
        text = by_dpi.get(int(dpi))
        return () if text is None else (_line(image, text),)

    return responder


def _both(text: Optional[str]) -> MockOCRBackend:
    return MockOCRBackend(responder=_reads({300: text, 450: text}))


def _corroborate(text: str = "150mm", *, backend: Optional[MockOCRBackend] = None, pdf: Optional[bytes] = None):
    setup = _Setup(pdf or _glyph_unverified_pdf([(text, 40, 120)]), backend or _both(text))
    return setup, setup.publish(text)


# ---------------------------------------------------------------------------
# Positive proof and record content
# ---------------------------------------------------------------------------

def test_agreement_at_both_dpis_with_the_native_claim_corroborates_and_retains_lineage() -> None:
    setup, result = _corroborate("150mm")
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (RASTER_TEXT_CORROBORATED,)
    assert result.corroborated_text == "150mm"
    record = result.record
    assert record is not None
    published = setup.published
    oid = setup.oid_of("150mm")
    receipt = setup._receipts[oid]
    assert (record.document_id, record.revision_id, record.source_sha256, record.snapshot_id) == (
        published.revision.document_id,
        published.revision.revision_id,
        published.revision.source_sha256,
        published.snapshot.snapshot_id,
    )
    assert record.page_id == "1"
    assert record.native_observation_id == oid
    assert record.text_integrity_receipt_id == receipt.receipt_id
    assert record.native_text_integrity_reason_codes == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
    assert record.source_bbox == tuple(receipt.geometry)
    assert record.render_dpis == RASTER_TEXT_CORROBORATION_DPIS == (300, 450)
    assert record.backend_name == "mock_ocr" and record.backend_version
    assert [(v.dpi, v.ocr_reading) for v in record.views] == [(300, "150mm"), (450, "150mm")]
    assert all(v.clip_pt == record.source_bbox for v in record.views)
    assert record.page_parent_observation_id and record.source_partition_id == "page:1"
    assert record.corroborated_text == "150mm"


@pytest.mark.parametrize("text", ["150mm", "externally.", "internally.", "1,800mm", "s/w", "r.c.", "(Lead-oxide", "W-1"])
def test_exact_readings_including_punctuation_corroborate(text: str) -> None:
    _setup, result = _corroborate(text)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.corroborated_text == text


@pytest.mark.parametrize(
    ("claim", "reading"),
    [
        ("externally.", "externally"),  # punctuation dropped
        ("externally.", "externally,"),
        ("internally.", "internally"),
        ("150mm", "150 mm"),  # inserted space is not outer whitespace
        ("150mm", "l50mm"),  # look-alike character
        ("150mm", "150MM"),  # case is semantic
        ("walling", "willing"),
        ("externally.", "exlternally."),
    ],
)
def test_strict_equality_never_forgives_near_misses(claim: str, reading: str) -> None:
    _setup, result = _corroborate(claim, backend=_both(reading))
    assert result.record is None
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes


def test_outer_whitespace_and_unicode_normalisation_are_the_only_forgiveness() -> None:
    assert normalize_reading("  150mm \n") == "150mm"
    assert normalize_reading("e\u0301xternally.") == "\u00e9xternally."
    _setup, result = _corroborate("150mm", backend=_both("  150mm  "))
    assert result.status is EvidenceResolutionStatus.CORROBORATED


# ---------------------------------------------------------------------------
# OCR-side adversaries: every one abstains, none is resolved by preference
# ---------------------------------------------------------------------------

def test_one_dpi_wrong_abstains_even_if_the_other_matches_the_claim() -> None:
    backend = MockOCRBackend(responder=_reads({300: "walling", 450: "willing"}))
    _s, result = _corroborate("walling", backend=backend)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_VIEW_DISAGREEMENT in result.reason_codes
    assert result.record is None
    backend = MockOCRBackend(responder=_reads({300: "externally.", 450: "exlternally."}))
    _s, result = _corroborate("externally.", backend=backend)
    assert RASTER_TEXT_VIEW_DISAGREEMENT in result.reason_codes


def test_both_views_agreeing_on_the_same_wrong_text_abstains() -> None:
    _s, result = _corroborate("150mm", backend=_both("160mm"))
    assert RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes


def test_views_that_disagree_with_each_other_and_the_claim_abstain() -> None:
    backend = MockOCRBackend(responder=_reads({300: "aaa", 450: "bbb"}))
    _s, result = _corroborate("150mm", backend=backend)
    assert RASTER_TEXT_VIEW_DISAGREEMENT in result.reason_codes


def test_both_views_returning_nothing_abstain() -> None:
    _s, result = _corroborate("150mm", backend=_both(None))
    assert RASTER_TEXT_NO_READING in result.reason_codes


def test_one_view_returning_nothing_abstains() -> None:
    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=_reads({300: "150mm", 450: None})))
    assert RASTER_TEXT_NO_READING in result.reason_codes


def test_duplicate_ocr_detections_of_the_same_text_are_competing_not_collapsed() -> None:
    def responder(image, dpi):
        return (_line(image, "150mm"), _line(image, "150mm"))

    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=responder))
    assert RASTER_TEXT_COMPETING_READINGS in result.reason_codes
    assert result.record is None


def test_extra_text_contamination_as_a_second_reading_abstains() -> None:
    def responder(image, dpi):
        return (_line(image, "150mm"), _line(image, "thick"))

    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=responder))
    assert RASTER_TEXT_COMPETING_READINGS in result.reason_codes


def test_extra_text_contamination_inside_the_single_reading_abstains() -> None:
    _s, result = _corroborate("150mm", backend=_both("150mm thick"))
    assert RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes


def test_no_highest_confidence_or_nearest_or_largest_choice_between_readings() -> None:
    def responder(image, dpi):
        good = OCRLine(text="150mm", confidence=0.99, bbox_px=(2.0, 2.0, image.width - 2.0, image.height - 2.0))
        bad = OCRLine(text="150rnm", confidence=0.10, bbox_px=(2.0, 2.0, 6.0, 6.0))
        return (bad, good)

    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=responder))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_COMPETING_READINGS in result.reason_codes


@pytest.mark.parametrize(
    "bbox",
    [
        (-50.0, 2.0, 30.0, 20.0),  # far outside
        (2.0, 2.0, 5000.0, 20.0),
        (float("nan"), 2.0, 30.0, 20.0),
        (10.0, 10.0, 10.0, 20.0),  # degenerate
        (30.0, 2.0, 10.0, 20.0),  # inverted
    ],
)
def test_malformed_or_out_of_bounds_ocr_geometry_abstains(bbox) -> None:
    def responder(image, dpi):
        return (OCRLine(text="150mm", confidence=None, bbox_px=bbox),)

    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=responder))
    assert RASTER_TEXT_OCR_GEOMETRY_INVALID in result.reason_codes
    assert result.record is None


def test_backend_unavailable_abstains_without_rendering(monkeypatch) -> None:
    calls: list[dict] = []
    original = SourceObservationProducer.render_native_page_png

    def spy(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(SourceObservationProducer, "render_native_page_png", spy)
    _s, result = _corroborate("150mm", backend=MockOCRBackend(is_ready=False))
    assert RASTER_TEXT_BACKEND_UNAVAILABLE in result.reason_codes
    assert result.record is None
    assert calls == []


def test_backend_exception_abstains() -> None:
    _s, result = _corroborate("150mm", backend=MockOCRBackend(fail_with=RuntimeError("boom")))
    assert RASTER_TEXT_BACKEND_ERROR in result.reason_codes


# ---------------------------------------------------------------------------
# Native-side adversaries: text-integrity reasons other than glyph mapping
# ---------------------------------------------------------------------------

def test_lying_tounicode_claim_is_contradicted_by_the_rendered_glyphs() -> None:
    # The page draws the glyph string "900" but the producer's ToUnicode says
    # code '9' is U+0038: the native claim is "800". OCR reads what is drawn.
    pdf = _glyph_unverified_pdf([("900", 40, 120)], code_to_unicode={ord("9"): ord("8")})
    setup = _Setup(pdf, _both("900"))
    receipt_texts = sorted(r.raw_text for r in setup._receipts.values())
    assert receipt_texts == ["800"], receipt_texts
    result = setup.publish("800")
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes
    assert result.record is None


def test_a_word_with_another_text_integrity_reason_never_reaches_raster_ocr(monkeypatch) -> None:
    triangle = "q 10 100 m 250 100 l 10 190 l h W n 0 0 5 5 re f "
    pdf = _pdf(
        triangle
        + "BT /F1 14 Tf 40 120 Td (150mm) Tj ET 0 0 5 5 re f Q",
        fonts={
            "F1": (
                5,
                "<< /Type /Font /Subtype /Type1 /BaseFont /Arial /FirstChar 32 /LastChar 126 /ToUnicode 6 0 R >>",
            )
        },
        extra={
            6: _stream_obj(
                _cmap(
                    sysinfo=_SYSINFO_DUP,
                    mappings="\n".join(f"<{c:02X}> <{c:04X}>" for c in sorted(set(map(ord, "150mm")))),
                    count=len(set("150mm")),
                )
            )
        },
    )
    setup = _Setup(pdf, _both("150mm"))
    receipt = setup._receipts[setup.oid_of("150mm")]
    assert TEXT_CLIP_STATE_UNRESOLVED in receipt.reason_codes
    assert TEXT_GLYPH_MAPPING_UNVERIFIED in receipt.reason_codes
    calls: list[dict] = []
    original = SourceObservationProducer.render_native_page_png
    monkeypatch.setattr(
        SourceObservationProducer,
        "render_native_page_png",
        lambda self, **kw: (calls.append(kw), original(self, **kw))[1],
    )
    result = setup.publish("150mm")
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY in result.reason_codes
    assert TEXT_CLIP_STATE_UNRESOLVED in result.reason_codes
    assert calls == []


def test_trace_ambiguity_is_not_overridden_by_raster_ocr() -> None:
    once = "BT /F1 14 Tf 40 120 Td (150mm) Tj ET "
    pdf = _glyph_unverified_pdf([("150mm", 40, 120)], extra_stream=once)  # same word painted twice
    setup = _Setup(pdf, _both("150mm"))
    for oid, receipt in setup._receipts.items():
        if receipt.raw_text == "150mm":
            assert TEXT_TRACE_AMBIGUOUS in receipt.reason_codes
            result = setup.producer.publish(setup.selector(oid))
            assert result.status is EvidenceResolutionStatus.ABSTAINED
            assert RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY in result.reason_codes
            assert result.record is None


def test_a_lying_but_glyph_verifiable_tounicode_stays_a_glyph_mismatch_not_a_raster_case() -> None:
    from test_pdf_text_integrity_source_state_v1 import _tounicode_pdf

    lying = _cmap(sysinfo=_SYSINFO_DUP, mappings="<39> <0038>\n<30> <0030>")
    setup = _Setup(_tounicode_pdf(lying), _both("800"))
    (oid, receipt), = setup._receipts.items()
    result = setup.producer.publish(setup.selector(oid))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert RASTER_TEXT_INTEGRITY_NOT_GLYPH_ONLY in result.reason_codes
    assert "text_glyph_unicode_mismatch" in result.reason_codes


def test_an_already_trusted_word_needs_no_raster_corroboration() -> None:
    from test_pdf_text_integrity_source_state_v1 import _TXT

    setup = _Setup(_pdf(_TXT), _both("900"))
    (oid, receipt), = setup._receipts.items()
    assert receipt.trusted
    result = setup.producer.publish(setup.selector(oid))
    assert RASTER_TEXT_ALREADY_TRUSTED in result.reason_codes
    assert result.record is None


def test_a_non_word_observation_is_not_corroborated() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    _png, page_parent = setup.svp._producer.render_native_page_png(
        document_id=setup.published.revision.document_id,
        revision_id=setup.published.revision.revision_id,
        source_sha256=setup.published.revision.source_sha256,
        snapshot_id=setup.published.snapshot.snapshot_id,
        page_id="1",
        dpi=72.0,
    )
    result = setup.producer.publish(setup.selector(page_parent.observation_id))
    assert RASTER_TEXT_OBSERVATION_NOT_NATIVE_WORD in result.reason_codes


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

def test_stale_revision_abstains_and_never_renders(monkeypatch) -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    old_selector = setup.selector(setup.oid_of("150mm"))
    setup.svp.ingest_native_pdf_bytes(
        document_id=DOC,
        source_bytes=_glyph_unverified_pdf([("160mm", 40, 120)]),
        source_locator="memory://newer.pdf",
    )
    result = setup.producer.publish(old_selector)
    assert RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED in result.reason_codes
    assert STALE_REVISION in result.reason_codes
    assert result.record is None


def test_wrong_sha_abstains() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    result = setup.publish("150mm", source_sha256="0" * 64)
    assert SOURCE_HASH_MISMATCH in result.reason_codes and result.record is None


def test_wrong_snapshot_abstains() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    result = setup.publish("150mm", snapshot_id="snapshot-that-does-not-exist")
    assert SNAPSHOT_MISMATCH in result.reason_codes and result.record is None


def test_unknown_observation_abstains() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    result = setup.producer.publish(setup.selector("no-such-observation"))
    assert RASTER_TEXT_SOURCE_LINEAGE_UNRESOLVED in result.reason_codes and result.record is None


def test_swapped_page_lineage_is_a_conflict_not_a_positive(monkeypatch) -> None:
    doc = fitz.open()
    doc.new_page(width=300, height=200)
    doc.new_page(width=300, height=200)
    two_pages = doc.tobytes()
    doc.close()
    # Same word at the same place on both pages, made glyph-unverifiable.
    single = _glyph_unverified_pdf([("150mm", 40, 120)])
    setup = _Setup(single, _both("150mm"))
    original = SourceObservationProducer.render_native_page_png

    def swapped(self, **kwargs):
        png, parent = original(self, **kwargs)
        from dataclasses import replace

        return png, replace(parent, page_id="2", source_partition_id="page:2")

    monkeypatch.setattr(SourceObservationProducer, "render_native_page_png", swapped)
    result = setup.publish("150mm")
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert RASTER_TEXT_PAGE_LINEAGE_MISMATCH in result.reason_codes
    assert result.record is None
    assert two_pages  # (fixture kept to document the two-page scenario)


def test_each_pages_word_is_rendered_from_its_own_page() -> None:
    doc = fitz.open()
    for label in ("150mm", "160mm"):
        page = doc.new_page(width=300, height=200)
        page.insert_text((40, 120), label, fontsize=14)
    setup_pdf = doc.tobytes()
    doc.close()
    # Native (Base14) words are already trusted; only distinct page parents matter here.
    svp = SourceVisibilityProducer(producer_method="t", producer_version="1")
    published = svp.ingest_native_pdf_bytes(document_id="two-pages", source_bytes=setup_pdf, source_locator="m://t")
    parents = set()
    for page_id in ("1", "2"):
        _png, parent = svp._producer.render_native_page_png(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            dpi=72.0,
            clip_pt=(30.0, 100.0, 90.0, 130.0),
        )
        parents.add((parent.page_id, parent.observation_id))
    assert len(parents) == 2


# ---------------------------------------------------------------------------
# What actually reaches the OCR backend
# ---------------------------------------------------------------------------

def test_ocr_sees_exactly_the_clip_render_with_no_padding_and_no_fallback_pipeline(monkeypatch) -> None:
    seen: list[tuple[int, Image.Image]] = []

    def responder(image, dpi):
        seen.append((int(dpi), image.copy()))
        return (_line(image, "150mm"),)

    # A neighbouring word 3pt away must not be pulled into the OCR image.
    pdf = _glyph_unverified_pdf([("150mm", 40, 120), ("THICK", 90, 120)])
    setup = _Setup(pdf, MockOCRBackend(responder=responder))
    calls: list[dict] = []
    original = SourceObservationProducer.render_native_page_png

    def spy(self, **kwargs):
        calls.append(dict(kwargs))
        return original(self, **kwargs)

    monkeypatch.setattr(SourceObservationProducer, "render_native_page_png", spy)
    result = setup.publish("150mm")
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    bbox = result.record.source_bbox
    # one deterministic pipeline: exactly one render and one OCR call per DPI
    assert [c["dpi"] for c in calls] == [300.0, 450.0]
    assert all(tuple(c["clip_pt"]) == bbox for c in calls)
    assert all(c["page_id"] == "1" for c in calls)
    assert [d for d, _img in seen] == [300, 450]

    import io

    for (dpi, image), view in zip(seen, result.record.views):
        png, _parent = original(
            setup.svp._producer,
            document_id=setup.published.revision.document_id,
            revision_id=setup.published.revision.revision_id,
            source_sha256=setup.published.revision.source_sha256,
            snapshot_id=setup.published.snapshot.snapshot_id,
            page_id="1",
            dpi=float(dpi),
            clip_pt=bbox,
        )
        exact = Image.open(io.BytesIO(png)).convert("RGB")
        # the OCR image IS the exact clip render: same size, same pixels, no border
        assert image.size == exact.size == view.image_size_px
        assert image.tobytes() == exact.tobytes()


def test_no_padded_or_alternative_preprocessing_fallback_exists() -> None:
    import pb_raster_text_corroboration_authority as module

    assert not hasattr(module, "padding_for")
    assert not hasattr(module, "_pad_with_white")
    fields = set(inspect.signature(module.RasterTextView).parameters)
    assert not {"padding_px", "padded_size_px"} & fields


def test_a_wrong_first_pipeline_result_is_never_rescued_by_another_preprocessing() -> None:
    calls: list[int] = []

    def responder(image, dpi):
        calls.append(int(dpi))
        return (_line(image, "wrong"),)

    _s, result = _corroborate("150mm", backend=MockOCRBackend(responder=responder))
    assert RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes
    assert calls == [300, 450]  # no retry, no second pipeline


def test_ocr_confidence_is_diagnostic_provenance_and_never_an_authority_threshold() -> None:
    def low_but_exact(image, dpi):
        return (OCRLine(text="150mm", confidence=0.01, bbox_px=(2.0, 2.0, image.width - 2.0, image.height - 2.0)),)

    def high_but_wrong(image, dpi):
        return (OCRLine(text="160mm", confidence=0.999, bbox_px=(2.0, 2.0, image.width - 2.0, image.height - 2.0)),)

    _s, exact = _corroborate("150mm", backend=MockOCRBackend(responder=low_but_exact))
    assert exact.status is EvidenceResolutionStatus.CORROBORATED
    assert [v.ocr_confidence for v in exact.record.views] == [0.01, 0.01]
    _s, wrong = _corroborate("150mm", backend=MockOCRBackend(responder=high_but_wrong))
    assert wrong.status is EvidenceResolutionStatus.ABSTAINED

    def none_conf(image, dpi):
        return (OCRLine(text="150mm", confidence=None, bbox_px=(2.0, 2.0, image.width - 2.0, image.height - 2.0)),)

    _s, absent = _corroborate("150mm", backend=MockOCRBackend(responder=none_conf))
    assert absent.status is EvidenceResolutionStatus.CORROBORATED
    # identity does not depend on confidence
    assert absent.record.record_id == exact.record.record_id


def test_the_two_views_are_materially_different_scales() -> None:
    _s, result = _corroborate("150mm")
    v300, v450 = result.record.views
    assert v450.image_size_px[0] / v300.image_size_px[0] == pytest.approx(1.5, rel=0.05)


# ---------------------------------------------------------------------------
# API surface: nothing caller-supplied can influence the proof
# ---------------------------------------------------------------------------

def test_selector_carries_only_lineage_and_a_native_observation_address() -> None:
    fields = set(inspect.signature(RasterTextCorroborationSelector).parameters)
    assert fields == {"document_id", "revision_id", "source_sha256", "snapshot_id", "observation_id"}
    with pytest.raises(TypeError):
        RasterTextCorroborationSelector(  # type: ignore[call-arg]
            document_id="d", revision_id="r", source_sha256="s", snapshot_id="n", observation_id="o", bbox=(0, 0, 1, 1)
        )
    with pytest.raises(TypeError):
        RasterTextCorroborationSelector(  # type: ignore[call-arg]
            document_id="d", revision_id="r", source_sha256="s", snapshot_id="n", observation_id="o", text="150mm"
        )


def test_publish_and_factory_signatures_admit_no_caller_pixels_ocr_bbox_or_page() -> None:
    assert list(inspect.signature(RasterTextCorroborationProducer.publish).parameters) == ["self", "selector"]
    assert list(inspect.signature(RasterTextCorroborationProducer.from_source_visibility_producer).parameters) == [
        "source_visibility_producer"
    ]
    assert list(
        inspect.signature(RasterTextCorroborationProducer.from_source_visibility_producer_for_tests).parameters
    ) == ["source_visibility_producer", "backend"]
    forbidden = {"page_images", "pixels", "image", "png", "ocr", "ocr_text", "bbox", "word_bbox", "text",
                 "confidence", "page_parent", "source_partition_id", "clip_pt", "tounicode"}
    for fn in (
        RasterTextCorroborationProducer.publish,
        RasterTextCorroborationProducer.from_source_visibility_producer,
        RasterTextCorroborationProducer.from_source_visibility_producer_for_tests,
    ):
        assert not (set(inspect.signature(fn).parameters) & forbidden)


def test_producer_and_authority_cannot_be_constructed_directly_or_with_foreign_backends() -> None:
    svp = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(TypeError):
        RasterTextCorroborationProducer(svp, MockOCRBackend())
    with pytest.raises(TypeError):
        RasterTextCorroborationAuthority({})
    with pytest.raises(TypeError):
        RasterTextCorroborationProducer.from_source_visibility_producer(object())  # type: ignore[arg-type]

    class Impostor(MockOCRBackend):
        pass

    with pytest.raises(TypeError):
        RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(svp, Impostor())
    with pytest.raises(TypeError):
        RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(svp, RapidOCRBackend())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RasterTextCorroborationProducer.from_source_visibility_producer_for_tests(  # type: ignore[call-arg]
            svp, MockOCRBackend(), page_images={"1": Image.new("RGB", (4, 4))}
        )
    prod = RasterTextCorroborationProducer.from_source_visibility_producer(svp)
    assert type(prod._backend) is RapidOCRBackend


def test_publish_rejects_anything_but_the_exact_selector_type() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    oid = setup.oid_of("150mm")
    with pytest.raises(TypeError):
        setup.producer.publish(setup._observation_selector(oid))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        setup.producer.publish({"observation_id": oid})  # type: ignore[arg-type]


def test_authority_is_read_only_and_only_serves_published_results() -> None:
    setup = _Setup(_glyph_unverified_pdf([("150mm", 40, 120)]), _both("150mm"))
    selector = setup.selector(setup.oid_of("150mm"))
    authority = setup.producer.authority()
    assert authority.resolve(selector).reason_codes == (RASTER_TEXT_RECORD_UNAVAILABLE,)
    published = setup.producer.publish(selector)
    fresh = setup.producer.authority()
    assert fresh.resolve(selector) == published
    with pytest.raises(TypeError):
        fresh.resolve(setup._observation_selector(setup.oid_of("150mm")))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        fresh._results[selector.key] = published  # type: ignore[index]


def test_generic_portable_ocr_evidence_remains_candidate_only() -> None:
    img = Image.new("RGB", (40, 20), (255, 255, 255))
    svp = SourceVisibilityProducer(producer_method="t", producer_version="1")
    published = svp.ingest_native_pdf_bytes(
        document_id="cand", source_bytes=_glyph_unverified_pdf([("150mm", 40, 120)]), source_locator="m://c"
    )
    producer = PortableRasterOCRProducer.from_backend_for_tests(
        MockOCRBackend(canned_lines=[OCRLine(text="150mm", confidence=None, bbox_px=(0, 0, 10, 10), bbox_pt=(0, 0, 5, 5))]),
        page_images={"1": img},
        snapshot=published,
    )
    out = producer.publish(
        PortableRasterOCRSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
        )
    )
    assert out.status is EvidenceResolutionStatus.CANDIDATE


# ---------------------------------------------------------------------------
# Determinism and invariance
# ---------------------------------------------------------------------------

def test_replay_is_deterministic_within_and_across_producers() -> None:
    pdf = _glyph_unverified_pdf([("150mm", 40, 120)])
    a = _Setup(pdf, _both("150mm"))
    first = a.publish("150mm")
    second = a.publish("150mm")
    assert first == second
    b = _Setup(pdf, _both("150mm"))
    third = b.publish("150mm")
    assert third.record.record_id == first.record.record_id
    assert third == first


def test_translation_invariance_of_the_proof() -> None:
    a = _Setup(_glyph_unverified_pdf([("externally.", 40, 120)]), _both("externally."))
    b = _Setup(_glyph_unverified_pdf([("externally.", 137, 61)]), _both("externally."))
    ra, rb = a.publish("externally."), b.publish("externally.")
    assert ra.status is rb.status is EvidenceResolutionStatus.CORROBORATED
    for va, vb in zip(ra.record.views, rb.record.views):  # sub-pixel phase may shift a size by one pixel
        assert abs(va.image_size_px[0] - vb.image_size_px[0]) <= 1
        assert abs(va.image_size_px[1] - vb.image_size_px[1]) <= 1
    assert [v.ocr_reading for v in ra.record.views] == [v.ocr_reading for v in rb.record.views]
    assert ra.record.source_bbox != rb.record.source_bbox


def test_scale_invariance_of_the_proof() -> None:
    small = _Setup(_glyph_unverified_pdf([("internally.", 40, 120)], size=10), _both("internally."))
    large = _Setup(_glyph_unverified_pdf([("internally.", 40, 120)], size=24), _both("internally."))
    assert small.publish("internally.").status is EvidenceResolutionStatus.CORROBORATED
    assert large.publish("internally.").status is EvidenceResolutionStatus.CORROBORATED


# ---------------------------------------------------------------------------
# Real RapidOCR (skipped where the backend is not installed)
# ---------------------------------------------------------------------------

@needs_real_ocr
@pytest.mark.parametrize("text", ["150mm", "externally.", "internally."])
def test_real_rapidocr_corroborates_clean_rendered_text(text: str) -> None:
    svp = SourceVisibilityProducer(producer_method="real-ocr", producer_version="1")
    published = svp.ingest_native_pdf_bytes(
        document_id="real-" + text.strip("."),
        source_bytes=_glyph_unverified_pdf([(text, 40, 120)], size=24),
        source_locator="m://real",
    )
    producer = RasterTextCorroborationProducer.from_source_visibility_producer(svp)
    authority = svp.text_integrity_authority()
    (oid,) = published.text_observation_ids
    selector = RasterTextCorroborationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=oid,
    )
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record.backend_name == "rapid_ocr"
    assert result.corroborated_text == text
    # and the generic authority still refuses to trust the same word on its own
    assert authority.resolve_text(
        ObservationSelector(
            selector.document_id, selector.revision_id, selector.source_sha256, selector.snapshot_id, oid
        )
    ).trusted_text is None


@needs_real_ocr
def test_real_rapidocr_contradicts_a_lying_tounicode() -> None:
    svp = SourceVisibilityProducer(producer_method="real-ocr-lie", producer_version="1")
    published = svp.ingest_native_pdf_bytes(
        document_id="real-lie",
        source_bytes=_glyph_unverified_pdf([("900", 40, 120)], size=24, code_to_unicode={ord("9"): ord("8")}),
        source_locator="m://real-lie",
    )
    producer = RasterTextCorroborationProducer.from_source_visibility_producer(svp)
    (oid,) = published.text_observation_ids
    result = producer.publish(
        RasterTextCorroborationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
