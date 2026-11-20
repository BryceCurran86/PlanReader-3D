"""Read-only Q5446 original signed scope reviewer, with private input isolation."""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from tools.diag_q5446_original_vertical_scope import write_review


def _untrusted_pdf(folder: Path, name: str) -> Path:
    p = folder / name
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 30), "FAKE ORIGINAL")
        doc.save(p)
    return p


def test_untrusted_pdf_set_writes_only_explicit_unpublished_abstention(tmp_path):
    src = tmp_path / "sources"
    dst = tmp_path / "reports"
    src.mkdir()
    dst.mkdir()
    files = tuple(
        _untrusted_pdf(src, f"untrusted-{i}.pdf")
        for i in range(3)
    )
    out = dst / "source_scope.json"
    value = write_review(*files, out)
    assert out.exists()
    assert value["source_review"]["status"] == "ABSTAINED"
    assert value["source_review"]["physical_wall_height_authorized"] is False
    assert value["original_customer_quantities_emitted"] == 0
    assert value["benchmark_score_granted"] is False
    assert value["official_four_project_accuracy"] is None
    assert json.loads(out.read_text(encoding="utf8")) == value
    for p in files:
        assert p.read_bytes().startswith(b"%PDF")


def test_existing_report_will_never_be_overwritten(tmp_path):
    sources = tmp_path / "private"
    sources.mkdir()
    files = tuple(_untrusted_pdf(sources, f"file-{i}.pdf") for i in range(3))
    existing = tmp_path / "already_exists.json"
    existing.write_text("prior recorded evidence", encoding="utf8")
    with pytest.raises(ValueError, match="vertical_scope_review_output_must_be_new"):
        write_review(*files, existing)
    assert existing.read_text() == "prior recorded evidence"


def test_source_folder_never_reused_as_report_directory(tmp_path):
    source = tmp_path / "private"
    source.mkdir()
    files = tuple(_untrusted_pdf(source, f"original-{i}.pdf") for i in range(3))
    with pytest.raises(ValueError, match="vertical_scope_review_output_inside_source_folder"):
        write_review(*files, source / "report.json")


def test_non_json_and_nonexistent_output_folder_fail_without_writes(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    files = tuple(_untrusted_pdf(sources, f"x{i}.pdf") for i in range(3))
    with pytest.raises(ValueError, match="vertical_scope_review_requires_json_destination"):
        write_review(*files, tmp_path / "output.pdf")
    with pytest.raises(ValueError, match="vertical_scope_review_output_parent_unavailable"):
        write_review(*files, tmp_path / "missing" / "new.json")


def test_original_source_positive_cli_does_not_mint_customer_quantities(tmp_path):
    from tests.original_source_q5446 import require_original_q5446_triple

    files = require_original_q5446_triple()
    report_folder = tmp_path / "reports"
    report_folder.mkdir()
    out = report_folder / "original_vertical_review.json"
    value = write_review(*files, out)
    review = value["source_review"]
    assert review["status"] == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert review["promoted_ground_dwelling_and_garage_height_mm"] == 2740
    assert review["promoted_ground_flush_panel_hinged_door_height_mm"] == 2340
    assert review["promoted_hinged_sliding_alfresco_door_height_mm"] == 2400
    assert review["roof_space_r25_glasswool_garage_ceiling_excluded"] is True
    assert review["standard_nonmaster_shower_recess_wall_tile_scope"] is True
    assert review["standard_laundry_above_tub_wall_tile_scope"] is True
    assert value["benchmark_score_granted"] is False
    assert value["original_customer_quantities_emitted"] == 0
    assert json.loads(out.read_text()) == value
