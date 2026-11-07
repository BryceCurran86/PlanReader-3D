"""Regression gates for the quarantined project-specific quantity shortcut.

Synthetic fixtures establish rejection behavior only. The optional private
check uses the unchanged original PDF and cannot claim a measurement gain.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fitz
import pytest

import pb_maryborough_customer_authority as authority


def _known_fixture(tmp_path, monkeypatch, *, text="MEETING AREA", pages=31):
    document = fitz.open()
    for index in range(pages):
        page = document.new_page()
        if index == 0 and text:
            page.insert_text((40, 60), text)
    path = tmp_path / "known-source-fixture.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    monkeypatch.setattr(
        authority, "MARYBOROUGH_SOURCE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    return path


def _assert_empty_abstain(result):
    assert result.status == "ABSTAIN"
    assert result.quantities == ()
    assert result.traces == ()
    assert result.sealed_run is None
    assert result.customer_rows == ()
    assert result.identity_map_bindings == ()


@pytest.mark.parametrize("backend", ["native", "empty", "unavailable"])
def test_known_pdf_without_quantity_authority_never_issues_rows(
    tmp_path, monkeypatch, backend,
):
    path = _known_fixture(tmp_path, monkeypatch)
    original = path.read_bytes()
    if backend == "empty":
        monkeypatch.setattr(fitz.Page, "get_text", lambda *_args, **_kwargs: [])
    elif backend == "unavailable":
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("observation backend unavailable")
        monkeypatch.setattr(fitz.Page, "get_text", unavailable)
    result = authority.issue_all_original_maryborough_customer_quantities(path)
    _assert_empty_abstain(result)
    assert result.reason_codes == (
        authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,
    )
    assert path.read_bytes() == original


def test_missing_or_foreign_source_cannot_reenable_the_shortcut(tmp_path):
    missing = authority.issue_all_original_maryborough_customer_quantities(
        tmp_path / "absent.pdf",
    )
    _assert_empty_abstain(missing)
    foreign = tmp_path / "foreign.pdf"
    foreign.write_bytes(b"%PDF-1.7 unrelated source")
    rejected = authority.issue_all_original_maryborough_customer_quantities(foreign)
    _assert_empty_abstain(rejected)
    assert rejected.reason_codes == ("maryborough_source_sha_mismatch",)


@pytest.mark.parametrize("workspace", [None, True, False, 0, -1, "1", 1.5])
def test_invalid_workspace_is_rejected_before_source_read(monkeypatch, workspace):
    def unexpected_read(_path):
        raise AssertionError("an unauthenticated workspace read source bytes")
    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    result = authority.issue_all_original_maryborough_customer_quantities(
        "unused.pdf", workspace_id=workspace,
    )
    _assert_empty_abstain(result)
    assert result.reason_codes == ("authenticated_workspace_unavailable",)


def test_admitted_digest_without_a_decodable_pdf_is_not_authority(tmp_path, monkeypatch):
    path = tmp_path / "broken.pdf"
    payload = b"not a decodable PDF"
    path.write_bytes(payload)
    monkeypatch.setattr(
        authority, "MARYBOROUGH_SOURCE_SHA256", hashlib.sha256(payload).hexdigest(),
    )
    result = authority.issue_all_original_maryborough_customer_quantities(path)
    _assert_empty_abstain(result)
    assert result.reason_codes == ("source_pdf_unreadable",)


def test_original_sha_with_empty_observations_retains_quarantine(monkeypatch):
    path = Path(os.environ.get(
        "PLANREADER_ORIGINAL_MARYBOROUGH",
        "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
    ))
    if not path.is_file():
        pytest.skip("private original unavailable here; no source-pass claim")
    original_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert original_sha == authority.MARYBOROUGH_SOURCE_SHA256
    monkeypatch.setattr(fitz.Page, "get_text", lambda *_args, **_kwargs: [])
    result = authority.issue_all_original_maryborough_customer_quantities(path)
    _assert_empty_abstain(result)
    assert result.reason_codes == (
        authority.MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_sha
