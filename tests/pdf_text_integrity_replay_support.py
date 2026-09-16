"""Executable fixtures for the PDF text-integrity validator successor.

This module is test-only. It builds deterministic PDFs and producer-owned
selectors without importing the future/production text-integrity module.
"""
from __future__ import annotations

from typing import Mapping

import fitz

from pb_source_observation_authority import ObservationSelector, SourceObservationProducer


BASE_SHA = "e27ffad284b05123ffacbbe123c69823c5367dee"


def pdf_bytes(objects: Mapping[int, str]) -> bytes:
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


def simple_text_pdf_bytes(text: str = "900", *, color: str = "0 0 0 rg") -> bytes:
    stream = f"{color} BT /F1 12 Tf 40 120 Td ({text}) Tj ET"
    return pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def text_and_fill_pdf_bytes(*, fill_after_text: bool) -> bytes:
    text = "0 0 0 rg BT /F1 12 Tf 40 120 Td (900) Tj ET"
    fill = "1 1 1 rg 35 112 45 18 re f"
    stream = f"{text} {fill}" if fill_after_text else f"{fill} {text}"
    return pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def clipped_text_pdf_bytes() -> bytes:
    stream = "q 0 0 160 160 re W n 0 0 0 rg BT /F1 12 Tf 40 120 Td (900) Tj ET Q"
    return pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def type3_text_pdf_bytes() -> bytes:
    char_stream = "500 0 0 0 500 500 d1 0 0 500 500 re S 0 0 m 500 500 l S"
    page_stream = "BT /F3 20 Tf 40 100 Td (A) Tj ET"
    return pdf_bytes(
        {
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
    )


def malformed_tounicode_pdf_bytes() -> bytes:
    page_stream = "BT /F1 12 Tf 40 120 Td (900) Tj ET"
    cmap = (
        "begincmap /CMapType 2 def 1 begincodespacerange <00> <FF> "
        "endcodespacerange 1 beginbfchar <39> <0039> endbfchar GARBAGE endcmap"
    )
    return pdf_bytes(
        {
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
    )


def control_character_pdf_bytes() -> bytes:
    stream = r"BT /F1 12 Tf 40 120 Td (\001900\002) Tj ET"
    return pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def open_page(payload: bytes) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open(stream=payload, filetype="pdf")
    return doc, doc.load_page(0)


def ingest_source(payload: bytes, *, document_id: str):
    producer = SourceObservationProducer(
        producer_method="pdf-text-integrity-executable-validator",
        producer_version="2.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published, producer.authority()


def selector_for_word(published, authority, *, text: str | None = None) -> ObservationSelector:
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
