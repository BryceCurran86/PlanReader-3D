"""Unpublished diagnostics may never overwrite their authenticated inputs."""
from __future__ import annotations

from pathlib import Path
import pytest
import scripts.report_full_plan_v2_readiness as readiness


@pytest.mark.parametrize("family", [
    "frozen", "produced", "original-pdfs", "sealed", "customer",
])
def test_diagnostic_output_must_not_mutate_any_protected_input_family(tmp_path, family):
    roots = {name: tmp_path / name for name in (
        "frozen", "produced", "original-pdfs", "sealed", "customer",
    )}
    for path in roots.values():
        path.mkdir()
    input_file = roots[family] / "project" / "authenticated.json"
    input_file.parent.mkdir()
    input_file.write_bytes(b"verified-unmodified-source-receipt")
    original = input_file.read_bytes()
    with pytest.raises(ValueError, match="may not overwrite"):
        readiness._write_readiness_report(
            input_file, '{"score_claim":false}\n',
            protected_roots=tuple(roots.values()),
        )
    assert input_file.read_bytes() == original


def test_source_symlink_alias_is_not_a_reporting_destination(tmp_path):
    original_root = tmp_path / "frozen"
    original_root.mkdir()
    input_file = original_root / "manifest.json"
    input_file.write_bytes(b"original-frozen-manifest")
    alias = tmp_path / "readonly-alias.json"
    try:
        alias.symlink_to(input_file)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="may not overwrite"):
        readiness._write_readiness_report(
            alias, '{"diagnostic":true}\n',
            protected_roots=(original_root,),
        )
    assert alias.is_symlink()
    assert input_file.read_bytes() == b"original-frozen-manifest"


def test_safe_readiness_report_writes_outside_protected_roots(tmp_path):
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    destination = tmp_path / "safe-reports" / "v2-readiness.json"
    encoded = '{"publication_status":"UNPUBLISHED","score_claim":false}\n'
    readiness._write_readiness_report(
        destination, encoded, protected_roots=(frozen, None),
    )
    assert destination.read_text(encoding="utf-8") == encoded
    assert not list(destination.parent.glob(".v2-readiness.json.*.tmp"))


def test_failed_atomic_rename_preserves_previous_report_and_source(tmp_path, monkeypatch):
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    source = frozen / "manifest.json"
    source.write_bytes(b"immutable-truth")
    destination = tmp_path / "reports" / "v2.json"
    destination.parent.mkdir()
    destination.write_bytes(b"existing-report-verified")
    def fail_rename(_src, _dst):
        raise OSError("simulated publication failure")
    monkeypatch.setattr(readiness.os, "replace", fail_rename)
    with pytest.raises(OSError, match="simulated publication failure"):
        readiness._write_readiness_report(
            destination, '{"publication_status":"UNPUBLISHED"}\n',
            protected_roots=(frozen,),
        )
    assert destination.read_bytes() == b"existing-report-verified"
    assert source.read_bytes() == b"immutable-truth"
    assert not list(destination.parent.glob(".v2.json.*.tmp"))
