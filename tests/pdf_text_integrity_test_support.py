"""Fixtures for the post-G17 PDF text-integrity red-team.

No production text-integrity authority is implemented here. Helpers construct
small PDFs and producer-owned selectors so tests can distinguish source-word
existence from future trusted/visible-text authority.
"""
from __future__ import annotations

from typing import Mapping

import fitz

from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "507c57db16be515e2432c695341bdea1e71b3fd7"


def pdf_bytes(objects: Mapping[int, str]) -> bytes:
    """Build a deterministic minimal PDF from literal indirect objects."""

    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    pos = len(header)
    for number in sorted(objects):
        offsets[number] = pos
        body = objects[number].encode("latin1")
        chunk = f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)

    xref_pos = pos
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        if number in offsets:
            xref.append(f"{offsets[number]:010d} 00000 n \n")
        else:
            xref.append("0000000000 00000 f \n")
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    )
    return b"".join(chunks) + "".join(xref).encode("ascii") + trailer.encode("ascii")


def simple_text_pdf_bytes(text: str = "900") -> bytes:
    """A one-page Base14 Type1 PDF with ordinary text and no explicit ToUnicode."""

    stream = f"BT /F1 12 Tf 40 120 Td ({text}) Tj ET"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    return pdf_bytes(objects)


def text_and_fill_pdf_bytes(*, fill_after_text: bool) -> bytes:
    """Text with an overlapping opaque rectangle before or after the text op."""

    text = "BT /F1 12 Tf 40 120 Td (900) Tj ET"
    # PDF y-axis origin is bottom-left. Cover the rendered text region.
    fill = "0 0 0 rg 35 112 45 18 re f"
    stream = f"{text} {fill}" if fill_after_text else f"{fill} {text}"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    return pdf_bytes(objects)


def type3_text_pdf_bytes() -> bytes:
    """Type-3 glyph whose visible geometry is supplied by the CharProc."""

    char_stream = "500 0 0 0 500 500 d1 0 0 500 500 re S 0 0 m 500 500 l S"
    page_stream = "BT /F3 20 Tf 40 100 Td (A) Tj ET"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F3 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream.encode('latin1'))} >>\nstream\n{page_stream}\nendstream",
        5: (
            "<< /Type /Font /Subtype /Type3 /Name /F3 /FontBBox [0 0 500 500] "
            "/FontMatrix [0.001 0 0 0.001 0 0] /CharProcs << /A 6 0 R >> "
            "/Encoding << /Type /Encoding /Differences [65 /A] >> "
            "/FirstChar 65 /LastChar 65 /Widths [500] /Resources << >> >>"
        ),
        6: f"<< /Length {len(char_stream.encode('latin1'))} >>\nstream\n{char_stream}\nendstream",
    }
    return pdf_bytes(objects)


def malformed_tounicode_pdf_bytes() -> bytes:
    """Font with a deliberately malformed ToUnicode stream.

    The fixture is for a future producer-side parser/integrity gate. Whether a
    PDF library happens to recover visible text is not authority evidence.
    """

    page_stream = "BT /F1 12 Tf 40 120 Td (900) Tj ET"
    cmap = "begincmap 1 beginbfchar <39> <0039> endbfchar THIS_IS_NOT_A_VALID_CMAP endcmap"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(page_stream.encode('latin1'))} >>\nstream\n{page_stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>",
        6: f"<< /Length {len(cmap.encode('latin1'))} >>\nstream\n{cmap}\nendstream",
    }
    return pdf_bytes(objects)


def control_character_pdf_bytes() -> bytes:
    """Literal string containing control bytes around dimension-looking text."""

    # Octal PDF string escapes encode control characters without corrupting the file.
    stream = r"BT /F1 12 Tf 40 120 Td (\001900\002) Tj ET"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    return pdf_bytes(objects)


def open_page(payload: bytes) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open(stream=payload, filetype="pdf")
    return doc, doc.load_page(0)


def ingest_source(payload: bytes, *, document_id: str = "text-integrity-doc"):
    producer = SourceObservationProducer(
        producer_method="pdf-text-integrity-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def ingest_visibility(payload: bytes, *, document_id: str = "text-visibility-doc"):
    producer = SourceVisibilityProducer(
        producer_method="pdf-text-integrity-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def selector_for_word(published, authority, *, text: str | None = None) -> ObservationSelector:
    """Return a selector for a producer-owned native word in the snapshot."""

    for observation_id in published.snapshot.observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = authority.resolve(selector)
        observation = result.observation
        if observation is None or observation.observation_kind != "native_pdf_word":
            continue
        if text is None or observation.raw_text == text:
            return selector
    raise AssertionError(f"native word not found: {text!r}")
