"""Original and commercial inputs cannot reuse a single resolved file."""
import pytest
from tools import report_gpt3_selected_two_project_original_evidence as selected


def entry(tmp_path):
    result = {field: str(tmp_path / (field + ".json"))
              for field in ("manifest", "sealed", "customer", "identity_map", "exact_report")}
    result["original_files"] = [str(tmp_path / "original.pdf")]
    return result


@pytest.mark.parametrize("first,second", [
    ("sealed", "customer"), ("customer", "identity_map"),
    ("manifest", "exact_report"), ("sealed", "identity_map"),
])
def test_selected_two_refuses_aliased_role_before_original_byte_io(tmp_path, monkeypatch, first, second):
    raw = entry(tmp_path)
    raw[second] = raw[first]
    monkeypatch.setattr(selected, "_json_object", lambda _: (_ for _ in ()).throw(
        AssertionError("must reject aliased inputs before parsing private data")))
    with pytest.raises(ValueError, match="roles alias"):
        selected._checked_one(raw)


def test_selected_two_refuses_original_pdf_alias_of_sealed_source(tmp_path, monkeypatch):
    raw = entry(tmp_path)
    raw["original_files"] = [raw["sealed"]]
    monkeypatch.setattr(selected, "_json_object", lambda _: (_ for _ in ()).throw(
        AssertionError("source role alias was not rejected")))
    with pytest.raises(ValueError, match="roles alias"):
        selected._checked_one(raw)

def test_selected_two_refuses_hardlinked_signed_and_customer_roles_before_io(tmp_path, monkeypatch):
    import os
    raw = entry(tmp_path)
    source = tmp_path / "sealed.json"
    source.write_text('{"synthetic":"independent-proof-required"}', encoding="utf-8")
    target = tmp_path / "customer.json"
    try:
        os.link(source, target)
    except (OSError, NotImplementedError):
        pytest.skip("hardlinks unavailable on this filesystem")
    monkeypatch.setattr(selected, "_json_object", lambda _: (_ for _ in ()).throw(
        AssertionError("hardlink alias was not rejected before reading any evidence")))
    with pytest.raises(ValueError, match="roles alias"):
        selected._checked_one(raw)
