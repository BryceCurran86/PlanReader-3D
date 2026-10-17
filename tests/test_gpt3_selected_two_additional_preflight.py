"""Additional paths rejected before hashing confidential originals or writing truth."""

from pathlib import Path

import pytest

from tools import report_gpt3_selected_two_project_original_evidence as selected


@pytest.mark.parametrize("project_id", [
    "../escape", "a/b", "a\\b", ".", "..", " bad", "bad ", "a..b",
    "", True, None, "a%2fb", "a:b",
])
def test_malicious_selected_project_id_never_reaches_source_hashing(
    tmp_path, monkeypatch, project_id,
):
    paths = {
        name: str(tmp_path / (name + ".json"))
        for name in ("manifest", "sealed", "customer", "identity_map", "exact_report")
    }
    raw = {**paths, "original_files": [str(tmp_path / "original.pdf")]}
    monkeypatch.setattr(selected, "_json_object", lambda _: {"project_id": project_id})
    monkeypatch.setattr(selected, "_original_source_subset_gate", lambda *_: (
        (_ for _ in ()).throw(AssertionError("untrusted project ID scanned source"))
    ))
    with pytest.raises(ValueError, match="frozen project identity is invalid"):
        selected._checked_one(raw)


def test_selected_output_cannot_write_new_file_in_frozen_benchmark_tree(
    tmp_path, monkeypatch,
):
    entry = tmp_path / "input.json"
    entry.write_text("{}", encoding="utf-8")
    output = selected.FROZEN_ROOT / "untracked-selected-report.json"
    monkeypatch.setattr(selected, "build_selected_two_project_development_evidence",
                        lambda *_: (_ for _ in ()).throw(
                            AssertionError("source scanned before output preflight")
                        ))
    with pytest.raises(FileExistsError, match="outside frozen inputs"):
        selected.main(["--entry", str(entry), "--entry", str(entry),
                       "--output", str(output)])
