"""Original source packet must never silently mix Acacia regional variants."""
from __future__ import annotations

from pathlib import Path
import os

import pytest

from pb_gpt1_acacia_source_packet import (
    ACACIA_ALL_TITLES, ACACIA_ORIGINAL_SHA256,
    ACACIA_REQUIRED_ROLES, _title_block,
    inspect_acacia_original_bytes, inspect_acacia_original_file,
)

_REGION_FILES = {
    "Sydney": "01_acacia_sydney.pdf",
    "Melbourne": "02_acacia_melbourne.pdf",
    "Brisbane": "03_acacia_brisbane.pdf",
}


def _fake_sheet(page: int, *, region="Brisbane", title=None,
                number=None, scale=None, stage="Preliminary", paper="A3"):
    sheet_name = title or ACACIA_ALL_TITLES[page]
    scale = scale or ("1:50" if page == 9 else "1:100")
    return (
        "PROJECT DESIGN Acacia House DESIGNED FOR " + region +
        " Technical drawings should be read with Acacia House " + region +
        " 'Design Options' document. DETAILS Drawing title: " +
        sheet_name + " Scale: " + scale + " Paper size: " + paper +
        " Drawing number: " + (number or str(page + 1) + "/10") +
        " Date issued: June 2023 Project stage: " + stage +
        " DISCLAIMER This is a guide only."
    )


@pytest.mark.parametrize("page,name,scale", ACACIA_REQUIRED_ROLES)
def test_role_title_block_uses_actual_sheet_metadata(page, name, scale):
    text = _fake_sheet(page, title=name)
    if page == 9:
        text = text.replace("Window and Door", "Window \nand Door")
    title, number, real_scale = _title_block(text, page, "Brisbane")
    assert (title, number, real_scale) == (name, f"{page + 1}/10", scale)


@pytest.mark.parametrize("page", range(10))
def test_all_true_original_sheet_indices_have_unique_title_and_number(page):
    title, number, _ = _title_block(_fake_sheet(page), page, "Brisbane")
    assert title == ACACIA_ALL_TITLES[page]
    assert number == f"{page + 1}/10"


@pytest.mark.parametrize("value", (
    _fake_sheet(0) + " A0.3 Floor Plan",
    _fake_sheet(1, title="Site Plan"),
    _fake_sheet(1, number="1/10"),
    _fake_sheet(9, scale="1:100"),
    _fake_sheet(8, paper="A4"),
    _fake_sheet(1, region="Sydney"),
    _fake_sheet(7, stage="Issued for construction"),
    _fake_sheet(1).replace("Drawing title: Floor Plan ", ""),
    _fake_sheet(1) + " Drawing title: Floor Plan Scale: 1:100",
))
def test_forged_wrong_or_ambiguous_source_page_never_verifies(value):
    with pytest.raises(ValueError):
        _title_block(value, 1, "Brisbane")


def test_sha_gate_precedes_any_pdf_decode_or_geometry(monkeypatch):
    import pb_gpt1_acacia_source_packet as acceptance

    def cannot_open(*_args, **_kwargs):
        raise AssertionError("cannot decode wrong SHA/PDF")
    monkeypatch.setattr(acceptance.fitz, "open", cannot_open)
    wrong = acceptance.inspect_acacia_original_bytes(
        b"tampered-looking-pdf-bytes", expected_region="Brisbane"
    )
    assert wrong.status == "ABSTAINED"
    assert wrong.reason == "acacia_original_sha256_or_region_mismatch"
    assert wrong.customer_quantities_authorized is False


@pytest.mark.parametrize("region", ("Sydney", "Melbourne", "Brisbane"))
def test_regional_hashes_distinct_and_none_can_be_a_customer_quantity(region):
    assert len(ACACIA_ORIGINAL_SHA256[region]) == 64
    assert len(set(ACACIA_ORIGINAL_SHA256.values())) == 3
    report = inspect_acacia_original_bytes(b"%PDF-foreign-original",
                                           expected_region=region)
    assert report.status == "ABSTAINED"
    assert report.to_dict()["finish_material_authorized"] is False
    assert report.to_dict()["frozen120_score_authorized"] is False


@pytest.mark.parametrize("region", ("Sydney", "Melbourne", "Brisbane"))
def test_private_original_all_four_pages_authenticate(region):
    private = os.environ.get("PLANREADER_ACACIA_ORIGINAL_DIR", "")
    if not private:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN in public CI: original private Acacia PDFs absent")
    source = Path(private) / _REGION_FILES[region]
    result = inspect_acacia_original_file(source, expected_region=region)
    assert result.status == "ORIGINAL_ROLES_AUTHENTICATED_REVIEW_ONLY"
    assert result.original_byte_roles_verified is True
    assert result.source_sha256 == ACACIA_ORIGINAL_SHA256[region]
    assert len(result.sheets) == 4
    assert [x.page_index for x in result.sheets] == [1, 7, 8, 9]
    assert result.to_dict()["missing_original_design_options_specification"] is True
    assert result.customer_quantities_authorized is False
    assert result.frozen120_score_authorized is False
    for wrong in set(_REGION_FILES).difference({region}):
        unrelated = inspect_acacia_original_file(
            source, expected_region=wrong
        )
        assert unrelated.status == "ABSTAINED"
        assert unrelated.original_byte_roles_verified is False


def test_directory_or_symlink_original_abstains(tmp_path):
    folder = inspect_acacia_original_file(tmp_path, expected_region="Brisbane")
    assert folder.status == "ABSTAINED"
    dummy = tmp_path / "dummy.pdf"
    dummy.write_bytes(b"fake")
    alias = tmp_path / "linked.pdf"
    alias.symlink_to(dummy)
    linked = inspect_acacia_original_file(alias, expected_region="Brisbane")
    assert linked.status == "ABSTAINED"
