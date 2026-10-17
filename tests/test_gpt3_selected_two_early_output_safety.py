"""Unsafe destinations are detected before reading large private source packages."""
import pytest
from tools import report_gpt3_selected_two_project_original_evidence as selected


def test_existing_customer_file_rejected_before_original_pdf_rehash(tmp_path, monkeypatch):
    customer = tmp_path / "customer.json"
    customer.write_text('{"customer_row":"immutable"}', encoding="utf-8")
    entry = tmp_path / "entry.json"
    entry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(selected, "build_selected_two_project_development_evidence",
                        lambda _: (_ for _ in ()).throw(AssertionError("must not access source")))
    with pytest.raises(FileExistsError, match="must be a new file"):
        selected.main(["--entry", str(entry), "--entry", str(entry), "--output", str(customer)])
    assert customer.read_text(encoding="utf-8") == '{"customer_row":"immutable"}'


def test_output_symlink_rejected_without_source_reconciliation(tmp_path, monkeypatch):
    original = tmp_path / "private.pdf"
    original.write_bytes(b"%PDF-synthetic-not-private")
    link = tmp_path / "write-alias.json"
    link.symlink_to(original)
    entry = tmp_path / "entry.json"
    entry.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(selected, "build_selected_two_project_development_evidence",
                        lambda _: (_ for _ in ()).throw(AssertionError("must not execute")))
    with pytest.raises(FileExistsError, match="must be a new file"):
        selected.main(["--entry", str(entry), "--entry", str(entry), "--output", str(link)])
    assert original.read_bytes() == b"%PDF-synthetic-not-private"
