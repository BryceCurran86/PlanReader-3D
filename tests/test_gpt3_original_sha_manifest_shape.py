"""Original PDF SHA shape is verified before any private source byte scan."""
import hashlib
import pytest
from tools import run_gpt3_original_byte_gated_exact_project as exact


def manifest(sha, size):
    return {"source_documents": [{"name": "original.pdf", "sha256": sha, "size_bytes": size}]}


@pytest.mark.parametrize("digest", ["g" * 64, "A" * 64, "0" * 63, None, False, "  " + "a"*62])
def test_invalid_sha_declaration_does_not_read_private_pdf(tmp_path, monkeypatch, digest):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-source-neutral")
    monkeypatch.setattr(exact, "_sha256", lambda _: (_ for _ in ()).throw(AssertionError("read before declaration validated")))
    verified, reasons, hashes = exact._original_sha_gate(manifest(digest, source.stat().st_size), [source])
    assert verified is False and reasons == ["source_manifest_document_universe_invalid"]
    assert hashes == []


def test_zero_byte_original_document_declaration_is_never_firm(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"")
    ok, reasons, hashes = exact._original_sha_gate(manifest(hashlib.sha256(b"").hexdigest(), 0), [source])
    assert ok is False and reasons == ["source_manifest_document_universe_invalid"]
    assert hashes == []


def test_actual_synthetic_original_sha_is_still_accepted(tmp_path):
    source = tmp_path / "original.pdf"
    payload = b"%PDF-source-neutral-original-bytes"
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    ok, reasons, hashes = exact._original_sha_gate(manifest(digest, len(payload)), [source])
    assert ok is True and reasons == [] and hashes == [digest]
