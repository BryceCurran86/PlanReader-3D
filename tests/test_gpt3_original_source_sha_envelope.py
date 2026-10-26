"""Hash matching source bytes is genuine but not full source/quantity authority."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from tools import gpt3_original_source_preflight as source_preflight
from tools import gpt3_safe_original_report_output as publication
from tools import gpt3_verify_original_source_sha_envelope as envelope

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

def test_multi_document_signed_sha_envelope_requires_exact_complete_set(tmp_path):
    pdf_a = tmp_path / "architectural-original-synthetic.pdf"
    pdf_b = tmp_path / "structural-original-synthetic.pdf"
    pdf_a.write_bytes(b"%PDF-1.7\\nsynthetic architectural bytes\\n")
    pdf_b.write_bytes(b"%PDF-1.7\\nsynthetic structural bytes\\n")
    sha_a = sha256(pdf_a.read_bytes()).hexdigest()
    sha_b = sha256(pdf_b.read_bytes()).hexdigest()
    records = []
    traces = {}
    for index, digest in ((1, sha_a), (2, sha_b)):
        q = quantity(f"multi-{index}", f"floor-{index}")
        q = replace(q, metadata={
            **q.metadata, "source_sha256": digest,
            "document_id": f"doc-{index}",
        })
        t = replace(
            trace(q), document_id=f"doc-{index}", source_sha256=digest,
        )
        records.append(q)
        traces[q.quantity_id] = t
    sealed = seal_source_closed_run(
        records, project_id="project-7", traces_by_quantity_id=traces,
    )
    result = verify_original_source_sha_envelope(sealed, [pdf_b, pdf_a])
    assert result["original_source_sha256s"] == sorted([sha_a, sha_b])
    assert result["sealed_quantity_count"] == 2
    with pytest.raises(ValueError, match="one original source file"):
        verify_original_source_sha_envelope(sealed, [pdf_a])
    with pytest.raises(ValueError, match="do not match|duplicate"):
        verify_original_source_sha_envelope(sealed, [pdf_a, pdf_a])


def _sealed_cli_args(tmp_path):
    pdf, sealed = _synthetic_source(tmp_path)
    sealed_file = tmp_path / "sealed.json"
    sealed_file.write_text(json.dumps(sealed.to_dict()), encoding="utf-8")
    output = tmp_path / "verified-audit.json"
    args = [
        "--sealed-run", str(sealed_file),
        "--original-source", str(pdf),
        "--output", str(output),
    ]
    return pdf, sealed_file, output, args


def test_raced_original_symlink_during_descriptor_open_abstains(tmp_path, monkeypatch):
    """The old is_file then path.open could follow a substituted symlink."""
    pdf, sealed = _synthetic_source(tmp_path)
    original_bytes = pdf.read_bytes()
    moved = tmp_path / "real-original.pdf"
    real_open = source_preflight.os.open
    swapped = False

    def race(path, flags, *args, **kwargs):
        nonlocal swapped
        if not swapped and str(path) == str(pdf):
            swapped = True
            pdf.replace(moved)
            pdf.symlink_to(moved)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(source_preflight.os, "open", race)
    with pytest.raises(ValueError, match="source changed|not a regular"):
        verify_original_source_sha_envelope(sealed, [pdf])
    assert swapped
    assert moved.read_bytes() == original_bytes


def test_same_byte_original_swap_before_publication_refuses_audit(tmp_path, monkeypatch):
    """Source SHA equality does not grant authority after an inode swap."""
    pdf, sealed_file, output, args = _sealed_cli_args(tmp_path)
    original_bytes = pdf.read_bytes()
    sealed_bytes = sealed_file.read_bytes()
    real_write = envelope.write_new_diagnostic
    called = False

    def swap_before_publish(*a, **kw):
        nonlocal called
        called = True
        replacement = tmp_path / "same-byte-other-inode.pdf"
        replacement.write_bytes(original_bytes)
        replacement.replace(pdf)
        return real_write(*a, **kw)

    monkeypatch.setattr(envelope, "write_new_diagnostic", swap_before_publish)
    with pytest.raises(ValueError, match="original source changed during audit"):
        main(args)
    assert called
    assert not output.exists()
    assert pdf.read_bytes() == original_bytes
    assert sealed_file.read_bytes() == sealed_bytes
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_same_byte_signed_seal_swap_after_link_rolls_back(tmp_path, monkeypatch):
    """Revalidate the signed seal even after the report is exclusively linked."""
    pdf, sealed_file, output, args = _sealed_cli_args(tmp_path)
    original_bytes = pdf.read_bytes()
    sealed_bytes = sealed_file.read_bytes()
    real_link = publication.os.link
    called = False

    def swap_after_link(staged, destination):
        nonlocal called
        real_link(staged, destination)
        called = True
        replacement = tmp_path / "same-byte-other-seal.json"
        replacement.write_bytes(sealed_bytes)
        replacement.replace(sealed_file)

    monkeypatch.setattr(publication.os, "link", swap_after_link)
    with pytest.raises(ValueError, match="original source changed during audit"):
        main(args)
    assert called
    assert not output.exists()
    assert pdf.read_bytes() == original_bytes
    assert sealed_file.read_bytes() == sealed_bytes
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_uncontested_sha_envelope_keeps_schema_without_inode_receipts(tmp_path):
    pdf, sealed_file, output, args = _sealed_cli_args(tmp_path)
    assert main(args) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["original_source_bytes_sha_verified"] is True
    assert report["sealed_v1_file_sha256"] == sha256(sealed_file.read_bytes()).hexdigest()
    assert report["original_source_sha256s"] == [sha256(pdf.read_bytes()).hexdigest()]
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["official_v2_accuracy"] is None
    assert not any("inode" in key or "identity" in key for key in report)
