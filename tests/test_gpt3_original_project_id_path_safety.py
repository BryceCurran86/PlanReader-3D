"""Frozen project identities may not escape their canonical source manifest root."""
from pathlib import Path
import pytest
from tools import run_gpt3_original_byte_gated_exact_project as exact


@pytest.mark.parametrize("unsafe", [
    "../real-project", "real/project", "real\\project", "./real",
    "real..project", " project", "project ", ".", "..", "",
    "project:evil", "%2e%2e/other", None, True, 47,
])
def test_original_byte_gate_rejects_untrusted_project_id_before_path_construction(
    tmp_path, monkeypatch, unsafe,
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(exact, "_strict_original_json_object",
                        lambda _: {"project_id": unsafe})
    with pytest.raises(ValueError, match="canonical project identity"):
        exact.build_original_byte_gated_project_report(
            manifest_path=manifest, sealed_run_path=tmp_path/"sealed.json",
            identity_map_path=tmp_path/"map.json", original_files=[],
        )


@pytest.mark.parametrize("legitimate", ["au_qld_lot16_power", "au_qld_3laurel", "source-project"])
def test_legitimate_source_id_shape_remains_valid_for_exact_path_binding(legitimate):
    import re
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", legitimate)
