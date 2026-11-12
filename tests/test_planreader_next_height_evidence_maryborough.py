"""Maryborough RCP height pairs. Kept out of the 3Laurel original-skip contract file."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from planreader_next.engine import load_native_page
from planreader_next.height_evidence import rcp_material_height_callouts
from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256


def test_real_maryborough_rcp_pairs_if_provisioned():
    named = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF", "").strip()
    default = Path(__file__).resolve().parents[1] / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"
    original = Path(named) if named else default
    if not original.is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Maryborough original not provisioned; this is not an original-source pass")
    page = load_native_page(original, 8)
    assert page.source_sha256 == MARYBOROUGH_SOURCE_SHA256
    found = rcp_material_height_callouts(page)
    assert len(found) == 18
    assert any(x["height_mm"] == "2400" and x["material_code_candidate"] == "GRID" for x in found)
    assert any(x["height_mm"] == "3000" and x["material_code_candidate"] == "FPB" for x in found)
    assert not any(x["height_mm"] == "1980" for x in found)
