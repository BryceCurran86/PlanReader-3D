"""Source-only A110/A600 door receipt tests; private original stays local."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fitz
import pytest

from pb_gpt2_maryborough_door_schedule_source import (
    audit_original_maryborough_door_schedule,
    census_native_a600_door_words,
)

SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def word(text, block, line, token, y, x=1000.0):
    return (x, y, x + 12, y + 12, text, block, line, token)


def sample():
    codes = ("D07", "D13")
    schedule = []
    plan = []
    for block, code, room in ((104, "D07", "WC & SHOWER"), (110, "D13", "PWD")):
        plan.append(word(code, block, 0, 0, 100.0, x=15.0))
        schedule.append(word(code, block, 0, 0, 2280.0))
        tokens = (room.split(" ") + ["SINGLE", "SWING"])
        for i, token in enumerate(tokens):
            schedule.append(word(token, block, 1, i, 2250.0 - i*25.0))
        for i, (v, y) in enumerate((("920",2055.0),("2040",2008.0),("40",1973.0)), start=2):
            schedule.append(word(v, block, i, 0, y))
    return schedule, plan, codes


def test_two_distinct_source_rows_and_noncommercial_receipts():
    schedule, plan, codes = sample()
    rows = census_native_a600_door_words(schedule, plan, codes)
    assert set(rows) == set(codes)
    assert rows["D13"]["status"] == "source_schedule_and_plan_words_only"
    assert rows["D13"]["source_room_name_printed"] == "PWD"
    assert rows["D07"]["source_room_name_printed"] == "WC & SHOWER"
    assert all(v["new_firm_quantities"] == 0 and not v["measurement_authorized"] for v in rows.values())


def test_room_split_across_old_2200pt_boundary_still_read_as_full_original_room():
    schedule, plan, codes = sample()
    # In D07, third room token SHOWER extends over the previous hardcoded
    # room/type boundary; source token sequence keeps the room name intact.
    rows = census_native_a600_door_words(schedule, plan, codes)
    assert rows["D07"]["source_room_name_printed"] == "WC & SHOWER"


@pytest.mark.parametrize("corruption", [
    "missing_plan", "duplicate_plan", "duplicate_schedule", "wrong_height",
    "missing_room_word", "competing_type", "bad_word_bbox", "duplicate_address",
])
def test_fail_closed_on_source_ambiguity(corruption):
    schedule, plan, codes = sample()
    if corruption == "missing_plan":
        plan = [w for w in plan if w[4] != "D13"]
    elif corruption == "duplicate_plan":
        plan.append(word("D13", 999, 0, 0, 120.0, x=15.0))
    elif corruption == "duplicate_schedule":
        schedule.append(word("D13", 400, 0, 0, 2285.0))
    elif corruption == "wrong_height":
        schedule = [(*w[:4], "TWO THOUSAND", *w[5:]) if w[5]==110 and w[4]=="2040" else w for w in schedule]
    elif corruption == "missing_room_word":
        schedule = [w for w in schedule if not (w[5]==110 and w[4]=="PWD")]
    elif corruption == "competing_type":
        schedule = [(*w[:4], "SLIDING", *w[5:]) if w[5]==110 and w[4]=="SINGLE" else w for w in schedule]
    elif corruption == "bad_word_bbox":
        schedule = [(*w[:1], float("nan"), *w[2:]) if w[5]==110 and w[4]=="D13" else w for w in schedule]
    elif corruption == "duplicate_address":
        schedule.append(schedule[0])
    if corruption in ("bad_word_bbox", "duplicate_address"):
        with pytest.raises(ValueError):
            census_native_a600_door_words(schedule, plan, codes)
    else:
        rows = census_native_a600_door_words(schedule, plan, codes)
        assert rows["D13"]["status"] == "ABSTAIN"
        assert rows["D13"]["new_firm_quantities"] == 0


def test_requested_door_codes_are_typed_unique():
    schedule, plan, _ = sample()
    for codes in ((), ("D13","D13"), ("D13",True), ("foo",)):
        with pytest.raises(ValueError):
            census_native_a600_door_words(schedule, plan, codes)


def test_sha_tamper_rejected_before_pdf_decode():
    with pytest.raises(ValueError, match="source_sha256_required"):
        audit_original_maryborough_door_schedule(b"not a PDF", expected_sha256=SHA)


def test_original_maryborough_source_page_and_door_schedule_noncommercial():
    path = Path(os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH", "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"))
    if not path.is_file():
        pytest.skip("owner-private original required; never fabricated in CI")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = audit_original_maryborough_door_schedule(raw, expected_sha256=SHA)
    rows = result["source_door_receipts"]
    assert result["new_firm_quantities"] == 0
    assert all(not row["measurement_authorized"] for row in rows.values())
    assert all(rows[code]["status"] == "source_schedule_and_plan_words_only"
               for code in ("D07","D08","D13","D14","D15"))
    assert rows["D07"]["source_room_name_printed"] == "WC & SHOWER"
    assert rows["D08"]["source_room_name_printed"] == "WC & SHOWER"
    assert rows["D13"]["source_room_name_printed"] == "PWD"
    assert rows["D14"]["source_room_name_printed"] == "DRY STORE"
    assert rows["D15"]["source_room_name_printed"] == "OFFICE"
    for row in rows.values():
        assert row["source_scheduled_width_mm_printed"] == 920
        assert row["source_scheduled_height_mm_printed"] == 2040
        assert row["source_scheduled_thickness_mm_printed"] == 40


def test_original_maryborough_wrong_source_page_abstains_before_words():
    path = Path(os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH", "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"))
    if not path.is_file():
        pytest.skip("owner-private original required")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    for wrong in (0, 9, True, 7.0):
        with pytest.raises(ValueError, match="page_scope_required"):
            audit_original_maryborough_door_schedule(raw, expected_sha256=SHA,
                plan_page_1_based=wrong)
