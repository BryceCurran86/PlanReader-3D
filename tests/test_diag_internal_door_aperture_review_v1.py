"""The aperture review diagnostic refuses a wrong source, keeps private output out of the repo, and prints counts only."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import diag_internal_door_aperture_review as tool

SHA = "a" * 64


def _write_pdf(tmp_path: Path) -> tuple[Path, str]:
    import fitz

    path = tmp_path / "one.pdf"
    document = fitz.open()
    document.new_page(width=200, height=200)
    document.save(path)
    document.close()
    import hashlib

    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_wrong_source_digest_is_refused_before_anything_runs(tmp_path, capsys):
    pdf, _ = _write_pdf(tmp_path)
    code = tool.main([
        "--pdf", str(pdf), "--page-index", "0", "--expected-source-sha256", SHA,
        "--output", str(tmp_path / "out.json"),
    ])
    assert code == 2
    assert "original_source_sha256_mismatch" in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_private_output_inside_the_repository_is_refused(tmp_path, capsys):
    pdf, sha = _write_pdf(tmp_path)
    inside = tool.REPO_ROOT / "docs" / "should_not_exist_private_review.json"
    code = tool.main([
        "--pdf", str(pdf), "--page-index", "0", "--expected-source-sha256", sha,
        "--output", str(tmp_path / "out.json"), "--private-output", str(inside),
    ])
    assert code == 2 and not inside.exists()
    assert "outside the repository" in capsys.readouterr().err


def test_a_run_writes_counts_only_and_the_private_review_only_where_asked(tmp_path, monkeypatch, capsys):
    pdf, sha = _write_pdf(tmp_path)
    claim = SimpleNamespace(canonical_openings=(), opening_quantity_evidence=(), status=SimpleNamespace(value="abstained"))
    monkeypatch.setattr(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        lambda *a, **k: claim,
    )
    out, private = tmp_path / "counts.json", tmp_path / "private.json"
    code = tool.main([
        "--pdf", str(pdf), "--page-index", "0", "--expected-source-sha256", sha,
        "--output", str(out), "--private-output", str(private),
    ])
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["review"]["aperture_count"] == 0
    assert payload["review"]["physical_opening_authenticated"] is False
    assert payload["issuer_census"]["canonical_opening_count"] == 0
    assert payload["issuer_census"]["claim_status"] == "abstained"
    assert "entries" not in payload["review"] and "native_path_ids" not in json.dumps(payload)
    assert json.loads(private.read_text(encoding="utf-8"))["entries"] == []
    assert "refused" not in capsys.readouterr().err


def test_a_failing_issuer_audit_is_reported_not_raised():
    census = tool.issuer_census([], [object()])  # an untyped published quantity makes the audit raise
    assert census["status"] == "UNAVAILABLE" and "reason" in census


@pytest.mark.parametrize("bad", ["", "xyz", "A" * 64])
def test_review_requires_the_exact_lowercase_digest(tmp_path, bad):
    pdf, _ = _write_pdf(tmp_path)
    with pytest.raises(ValueError):
        tool.run(pdf, page_index=0, expected_source_sha256=bad)
