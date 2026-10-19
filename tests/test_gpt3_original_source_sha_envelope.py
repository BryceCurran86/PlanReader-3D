"""Hash matching source bytes is genuine but not full source/quantity authority."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from pb_source_closed_run_export import seal_source_closed_run
from test_customer_output_verification import quantity, trace
from tools.gpt3_verify_original_source_sha_envelope import (
    verify_original_source_sha_envelope, build_original_source_sha_report, main,
)


def _synthetic_source(tmp_path):
    pdf = tmp_path / "synthetic-not-an-original-drawing.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%synthetic non-original test only\n")
    digest = sha256(pdf.read_bytes()).hexdigest()
    q = quantity("quantity-one", "floor-one")
    q = replace(q, metadata={**q.metadata, "source_sha256": digest})
    t = replace(trace(q), source_sha256=digest)
    sealed = seal_source_closed_run(
        [q], project_id="project-7", traces_by_quantity_id={q.quantity_id: t},
    )
    return pdf, sealed


def test_synthetic_matching_pdf_bytes_verify_only_sha_not_original_geometry(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    result = verify_original_source_sha_envelope(sealed, [pdf])
    assert result["original_source_bytes_sha_verified"] is True
    assert result["original_source_sha256s"] == [sha256(pdf.read_bytes()).hexdigest()]
    assert result["sealed_quantity_count"] == 1
    assert result["source_authenticated"] is False
    assert result["physical_geometry_source_authenticated"] is False
    assert result["official_v2_accuracy"] is None
    assert result["file_contents_exported"] is False


def test_correct_document_name_but_wrong_original_bytes_cannot_verify(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    pdf.write_bytes(b"%PDF-1.7\nforged client source bytes")
    with pytest.raises(ValueError, match="do not match"):
        verify_original_source_sha_envelope(sealed, [pdf])


def test_missing_or_duplicate_original_pdfs_do_not_claim_complete_source(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    with pytest.raises(ValueError, match="one original source file"):
        verify_original_source_sha_envelope(sealed, [])
    with pytest.raises(ValueError, match="one original source file"):
        verify_original_source_sha_envelope(sealed, [pdf, pdf])


def test_empty_valid_signature_does_not_authenticate_source(tmp_path):
    pdf, _ = _synthetic_source(tmp_path)
    sealed = seal_source_closed_run(
        [], project_id="project-7", traces_by_quantity_id={},
    )
    with pytest.raises(ValueError, match="nonempty sealed sources"):
        verify_original_source_sha_envelope(sealed, [pdf])


def test_original_source_symlink_is_refused_without_reading_target(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    link = tmp_path / "shortcut.pdf"
    link.symlink_to(pdf)
    with pytest.raises(ValueError, match="non-symlink"):
        verify_original_source_sha_envelope(sealed, [link])


def test_create_only_cli_never_overwrites_original_pdf_or_v1_seal(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    sealed_file = tmp_path / "sealed.json"
    sealed_file.write_text(json.dumps(sealed.to_dict()), encoding="utf-8")
    originals = (sha256(pdf.read_bytes()).hexdigest(),
                 sha256(sealed_file.read_bytes()).hexdigest())
    output = tmp_path / "audit.json"
    args = ["--sealed-run", str(sealed_file),
            "--original-source", str(pdf), "--output", str(output)]
    assert main(args) == 0
    assert json.loads(output.read_text())["publication_status"] == "UNPUBLISHED"
    assert originals == (sha256(pdf.read_bytes()).hexdigest(),
                         sha256(sealed_file.read_bytes()).hexdigest())
    with pytest.raises(FileExistsError):
        main(args)
    args[-1] = str(pdf)
    with pytest.raises(ValueError, match="protected evidence"):
        main(args)

def test_audit_rejects_symlink_before_hashing_original(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    seal_file = tmp_path / "signed-v1.json"
    seal_file.write_text(json.dumps(sealed.to_dict()), encoding="utf-8")
    alias = tmp_path / "original-alias.pdf"
    alias.symlink_to(pdf)
    with pytest.raises(ValueError, match="non-symlink"):
        build_original_source_sha_report(
            sealed_path=seal_file, original_paths=[alias],
        )
