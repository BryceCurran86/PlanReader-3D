"""Synthetic and adversarial native callout ownership tests."""
from hashlib import sha256

import fitz
import pytest

from tools.gptmax_original_cross_sheet_callout_shadow import original_cross_sheet_callout_shadow


def source_pdf(tmp_path, *, duplicate_plan=False, duplicate_elevation=False):
    filename = tmp_path / "source.pdf"
    with fitz.open() as doc:
        for index, title in enumerate(("FLOOR PLAN", "ELEVATIONS")):
            page = doc.new_page(width=800, height=600)
            page.insert_text((600, 550), title, fontsize=12)
            page.insert_text((120, 200), "2127 STACKER", fontsize=12)
            if (index == 0 and duplicate_plan) or (index == 1 and duplicate_elevation):
                page.insert_text((300, 300), "2127 STACKER", fontsize=12)
        doc.save(filename)
    return filename, sha256(filename.read_bytes()).hexdigest()


def request(filename, source_sha):
    return dict(pdf_path=filename, expected_sha256=source_sha,
                plan_page_index=0, elevation_page_index=1,
                plan_sheet_title="FLOOR PLAN", elevation_sheet_title="ELEVATIONS",
                plan_title_bbox=(590, 530, 720, 560),
                elevation_title_bbox=(590, 530, 720, 560),
                exact_callout="2127 STACKER")


def test_exact_native_pair_is_not_physical_authority(tmp_path):
    path, digest = source_pdf(tmp_path)
    before = path.read_bytes()
    result = original_cross_sheet_callout_shadow(**request(path, digest))
    assert result["status"] == "EXACT_NATIVE_CALLOUT_CORRESPONDENCE_ONLY"
    assert result["callout_occurrence_counts"] == (1, 1)
    assert result["same_physical_opening"] == result["opening_area"] == "ABSTAIN"
    assert result["new_firm_quantity"] is False
    assert path.read_bytes() == before


@pytest.mark.parametrize("plan,elevation", [(True, False), (False, True), (True, True)])
def test_competing_exact_occurrences_abstain(tmp_path, plan, elevation):
    path, digest = source_pdf(tmp_path, duplicate_plan=plan,
                              duplicate_elevation=elevation)
    result = original_cross_sheet_callout_shadow(**request(path, digest))
    assert result["status"] == "ABSTAIN_NONUNIQUE_OR_MISSING_EXACT_CALLOUT"


def test_wrong_title_or_title_block_rejected(tmp_path):
    path, digest = source_pdf(tmp_path)
    for changes in ({"elevation_sheet_title": "FLOOR PLAN"},
                    {"plan_title_bbox": (0, 0, 200, 200)}):
        with pytest.raises(ValueError, match="sheet-title ownership"):
            original_cross_sheet_callout_shadow(**{**request(path, digest), **changes})


def test_wrong_sha_and_modified_original_rejected(tmp_path):
    path, digest = source_pdf(tmp_path)
    with pytest.raises(ValueError, match="SHA mismatch"):
        original_cross_sheet_callout_shadow(
            **{**request(path, digest), "expected_sha256": "0" * 64})
    path.write_bytes(path.read_bytes() + b"\n% modified")
    with pytest.raises(ValueError, match="SHA mismatch"):
        original_cross_sheet_callout_shadow(**request(path, digest))


def test_missing_or_similar_callout_does_not_match(tmp_path):
    path, digest = source_pdf(tmp_path)
    result = original_cross_sheet_callout_shadow(
        **{**request(path, digest), "exact_callout": "2127 STACKERS"})
    assert result["status"] == "ABSTAIN_NONUNIQUE_OR_MISSING_EXACT_CALLOUT"


def test_bad_page_and_bbox_values_rejected(tmp_path):
    path, digest = source_pdf(tmp_path)
    for changes in ({"plan_page_index": True},
                    {"plan_title_bbox": (0, 0, 0, 1)},
                    {"elevation_title_bbox": (float("nan"), 0, 3, 4)}):
        with pytest.raises(ValueError):
            original_cross_sheet_callout_shadow(**{**request(path, digest), **changes})
