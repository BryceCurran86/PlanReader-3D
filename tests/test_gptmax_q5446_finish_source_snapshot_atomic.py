"""No original PDFs: test the authenticated-byte/PDF-parser identity invariant."""
from __future__ import annotations

from hashlib import sha256

import fitz
import pytest

import pb_gptmax_q5446_finish_support_shadow as module


INCLUSIONS = (
    "BATHROOM & ENSUITE\n"
    "Ceramic floor tiles and skirting tiles throughout.\n"
    "LAUNDRY\n"
    "Ceramic floor tiles and skirting tiles throughout.\n"
    "WINDOWS & EXTERNAL DOORS"
)
SALES = (
    "47 - 3\n"
    "600mm x 600mm porcelain floor tiles to entry kitchen and living.\n"
    "Wet area ceramic floor tiles to match.\n"
    "48 - 1"
)


def _synthetic_originals(tmp_path, monkeypatch):
    documents = []
    sha_by_role = {}
    for role, count, text in (
        ("standard_inclusions", 2, INCLUSIONS),
        ("scope_and_allowance_reference", 6, SALES),
    ):
        path = tmp_path / (role + ".pdf")
        with fitz.open() as document:
            for index in range(count):
                page = document.new_page()
                if (role == "standard_inclusions" and index == 0) or (
                    role == "scope_and_allowance_reference" and index == 5
                ):
                    page.insert_text((30, 50), text, fontsize=9)
            document.save(path)
        digest = sha256(path.read_bytes()).hexdigest()
        sha_by_role[role] = digest
        documents.append({"role": role, "path": path, "sha256": digest, "page_count": count})
    monkeypatch.setattr(module, "SOURCE_IDS", sha_by_role)
    return documents


def test_parser_consumes_only_exact_authenticated_bytes(tmp_path, monkeypatch):
    roster = _synthetic_originals(tmp_path, monkeypatch)
    actual_open = module.fitz.open
    parsed_bytes = []

    def record_open(*args, **kwargs):
        assert not args, "parsing a second file path reintroduces a hash/open race"
        assert kwargs.get("filetype") == "pdf"
        assert isinstance(kwargs.get("stream"), bytes)
        parsed_bytes.append(kwargs["stream"])
        return actual_open(*args, **kwargs)

    monkeypatch.setattr(module.fitz, "open", record_open)
    result = module.inspect_q5446_finish_support(roster)
    assert result.status == "SUPPORTING_SOURCE_CORROBORATED_NO_QUANTITY"
    assert len(parsed_bytes) == 2
    assert parsed_bytes == [row["path"].read_bytes() for row in roster]
    assert result.authentic_finished_face_area is False
    assert result.authenticated_customer_quantity is False
    assert result.benchmark_score_granted is False


def test_file_swapped_between_verification_and_parse_fails_closed(tmp_path, monkeypatch):
    roster = _synthetic_originals(tmp_path, monkeypatch)
    first_path = roster[0]["path"]
    original_bytes = first_path.read_bytes()
    actual_open = module.fitz.open
    seen = []

    def malicious_replacement(*args, **kwargs):
        # Replaces the file just before PDF parsing. Parsing must still use
        # the authenticated original bytes, then reject changed disk custody.
        seen.append(kwargs.get("stream"))
        if len(seen) == 1:
            first_path.write_bytes(b"attacker replacement is not a PDF")
        return actual_open(*args, **kwargs)

    monkeypatch.setattr(module.fitz, "open", malicious_replacement)
    result = module.inspect_q5446_finish_support(roster)
    assert seen == [original_bytes]
    assert result.status == "ABSTAIN"
    assert result.reason_code == "support_source_changed_during_read"
    assert result.public_summary()["benchmark_score_granted"] is False


def test_read_failure_abstains_without_writing_source_text(tmp_path, monkeypatch):
    roster = _synthetic_originals(tmp_path, monkeypatch)
    path_to_fail = roster[0]["path"]
    original = type(path_to_fail).read_bytes

    def denied(self):
        if self == path_to_fail:
            raise OSError("private path details must never be returned")
        return original(self)

    monkeypatch.setattr(type(path_to_fail), "read_bytes", denied)
    result = module.inspect_q5446_finish_support(roster)
    assert result.status == "ABSTAIN"
    assert result.reason_code == "support_source_identity_invalid"
    assert "private path" not in str(result.public_summary())


def test_non_original_and_changed_sha_fail_even_with_plausible_material_words(tmp_path, monkeypatch):
    roster = _synthetic_originals(tmp_path, monkeypatch)
    roster[0]["sha256"] = "0" * 64
    result = module.inspect_q5446_finish_support(roster)
    assert result.status == "ABSTAIN"
    assert result.reason_code == "support_source_identity_invalid"
