"""Protected Maryborough original: detail plans are door/wall evidence too.

This is source census only, not a Maryborough-specific production selector or
an automatic cross-page host grant. A110 is the parent plan; A500-A503 are
enlarged inset plans/elevations; A600 is a schedule, not extra installed doors.
Run against the exact owner-private architectural PDF on an isolated runner.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import fitz
import pytest

# Immutable ORIGINAL PDF source authority; not a benchmark quantity or geometry.
SOURCE_SHA256 = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
SOURCE_PATH_ENV = "PLANREADER_MARYBOROUGH_ORIGINAL_PDF"

# Fixture-only cross-view inventory, never imported by production.
_DETAIL_DOOR_CODES = {
    24: ("D07", "D08", "D09"),  # A500 WC/shower plan + elevations
    25: ("D10",),               # A501 laundry/airlock plan + elevations
    26: ("D13",),               # A502 PWD plan + elevations
    27: ("D11", "D12"),         # A503 ambulant plan + elevations
}


def _original_bytes() -> bytes:
    original = Path(os.environ.get(
        SOURCE_PATH_ENV, "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
    ))
    if not original.is_file():
        pytest.skip("private original Maryborough PDF not provisioned on this runner")
    data = original.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256, (
        "wrong_source_revision_cannot_supply_cross_sheet_opening_evidence"
    )
    return data


def _native_door_codes(page: fitz.Page) -> set[str]:
    # Real PDF native source word addresses, no OCR/label guessing or FIRM grant.
    return {str(word[4]).strip() for word in page.get_text("words", sort=False)
            if re.fullmatch(r"D[0-9]{2}", str(word[4]).strip())}


def test_original_enlarged_room_plan_insets_preserve_cross_sheet_door_evidence():
    data = _original_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert doc.page_count == 31
        parent = _native_door_codes(doc[6])  # A110 main architectural floor plan
        for page_1_based, door_codes in _DETAIL_DOOR_CODES.items():
            detail_page = doc[page_1_based - 1]
            detail = _native_door_codes(detail_page)
            assert set(door_codes) <= detail, (
                f"source detail plan page {page_1_based} lost its native door marks"
            )
            assert set(door_codes) <= parent, (
                "a referenced detail must not fabricate a new installed plan door"
            )
            assert len(detail_page.get_drawings()) > 0, (
                "text-only reference is not physical wall/jamb geometry"
            )

        # Door schedule is one independent source, not 28 additional installed
        # openings, and its repeated labels are not new physical aperture IDs.
        schedule = _native_door_codes(doc[27])
        assert set().union(*map(set, _DETAIL_DOOR_CODES.values())) <= schedule


def test_details_do_not_prove_unique_main_plan_wall_host_by_label_alone():
    # Same door code can occur on an enlarged plan, multiple elevations and
    # the A600 schedule. Repeated native labels are cross-view witnesses;
    # without unique physical source registration, they issue no host ID.
    data = _original_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert sum(
            sum(word[4] == "D11" for word in doc[page - 1].get_text("words", sort=False))
            for page in (7, 27, 28)
        ) >= 3
        assert sum(
            sum(word[4] == "D13" for word in doc[page - 1].get_text("words", sort=False))
            for page in (7, 26, 28)
        ) >= 3
