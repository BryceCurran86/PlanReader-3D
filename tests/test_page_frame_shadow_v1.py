"""Page-frame descriptor (pb_page_frame_shadow): shadow-only provenance record.

Synthetic fixtures only (see the PROMOTION GATE in the module docstring). Fixtures
come from tests/page_frame_test_support.py; PyMuPDF behaviour is pinned to 1.28.0
(requirements.txt), because /Rotate 45/91 handling is MuPDF's own rounding.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import fitz
import pytest

import pb_page_frame_shadow as pf
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from page_frame_test_support import (
    VH,
    VW,
    FakePage,
    build_sheet,
    describe_bytes,
    ownership_for,
    set_page_key,
    set_pages_node_key,
    to_native,
)

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
ROTATIONS = (0, 90, 180, 270)
RAW = EvidenceResolutionStatus.RAW
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT

needs_pymupdf_1_28 = pytest.mark.skipif(
    fitz.VersionBind != "1.28.0", reason="/Rotate spelling behaviour is MuPDF's own and pinned to PyMuPDF 1.28.0"
)


def _ulp_tol(*values: float, k: int = 4) -> float:
    return k * pf.float32_ulp(max(abs(v) for v in values))


def _fake_descriptor(page=None, **overrides):
    own = {"document_id": "doc-1", "source_sha256": "ab" * 32, "page_no": 1}
    own["revision"] = pf.revision_id_for(own["document_id"], own["source_sha256"])
    own.update(overrides)
    return pf.describe_page_frame(page if page is not None else FakePage(), **own)


# ---- descriptor facts: 0/90/180/270 x UserUnit x CropBox x non-integer sizes ----------
@pytest.mark.parametrize("rotation", ROTATIONS)
@pytest.mark.parametrize("user_unit", [1, 2, 1.5])
@pytest.mark.parametrize("size", [(842, 595), (VW, VH), (2383.94, 1683.78), (595.276, 841.89)])
@pytest.mark.parametrize("crop", ["none", "inset_offset"])
def test_coherent_frame_matrix(rotation, user_unit, size, crop):
    vw, vh = size
    kwargs = {}
    if crop == "inset_offset":
        kwargs = {"crop_margins": (10.5, 20.25, 15.0, 5.75), "origin": (100.0, 50.0)}
    data = build_sheet(rotation, user_unit=user_unit, vw=vw, vh=vh, walls=False, **kwargs)
    desc = describe_bytes(data)
    assert desc.status is RAW and desc.is_coherent and desc.reason_codes == ()
    assert desc.rotation == rotation and desc.rotation_reported == rotation
    assert desc.declared_coordinate_space is pf.FrameSpace.NATIVE_PAGE_USER_SPACE
    assert desc.unit == pf.UNIT_PDF_POINTS
    assert desc.extent_source == pf.EXTENT_SOURCE_PAGE_RECT_SWAPPED_FOR_ROTATION
    assert desc.user_unit == float(user_unit)
    nw, nh = (vw, vh) if rotation in (0, 180) else (vh, vw)
    native = desc.native_extent
    assert isinstance(native, pf.NativePageExtent) and isinstance(desc.display_extent, pf.DisplayPageExtent)
    tol = _ulp_tol(nw * user_unit, nh * user_unit)
    assert abs(native.width - nw * user_unit) <= tol and abs(native.height - nh * user_unit) <= tol
    # display extent is page.rect as reported; native is the same box swapped for 90/270
    doc = fitz.open(stream=data, filetype="pdf")
    rect = doc[0].rect
    assert (desc.display_extent.width, desc.display_extent.height) == (rect.width, rect.height)
    swapped = rotation in (90, 270)
    assert (native.width, native.height) == ((rect.height, rect.width) if swapped else (rect.width, rect.height))
    assert (pf.PAGE_FRAME_NOTE_ROTATED_DISPLAY_DIFFERS_FROM_NATIVE in desc.note_codes) is swapped
    assert desc.edge_quantisation_pt > 0.0


def test_native_extent_is_the_same_box_for_all_four_rotations_of_one_sheet():
    frames = {rot: describe_bytes(build_sheet(rot, walls=False)) for rot in ROTATIONS}
    assert {(f.display_extent.width, f.display_extent.height) for f in frames.values()} == {(frames[0].display_extent.width, frames[0].display_extent.height)}
    assert frames[0].native_extent.width == frames[180].native_extent.width == frames[90].native_extent.height == frames[270].native_extent.height
    assert len({f.frame_id for f in frames.values()}) == 4  # rotation is part of the frame facts


def test_cropbox_larger_than_mediabox_is_a_note_not_a_conflict():
    base = build_sheet(0, vw=842, vh=595, walls=False)
    data = set_page_key(base, "CropBox", "[-50 -50 900 650]")
    desc = describe_bytes(data)
    assert desc.status is RAW
    assert pf.PAGE_FRAME_NOTE_CROPBOX_EXCEEDS_MEDIABOX in desc.note_codes
    assert (desc.native_extent.width, desc.native_extent.height) == (842.0, 595.0)  # effective box = intersection


def test_boxes_are_recorded_with_their_frame_named_in_the_field():
    plain = describe_bytes(build_sheet(0, vw=842, vh=595, walls=False, crop_margins=(10, 20, 30, 40), origin=(100.0, 50.0))).to_plain()
    assert plain["mediabox_pdf_y_up"] == [100.0, 50.0, 100.0 + 842 + 40, 50.0 + 595 + 60]
    assert "cropbox_pymupdf_y_down_from_mediabox_top" in plain


# ---- /Rotate spellings --------------------------------------------------------------
@pytest.mark.parametrize("key,canonical", [(450, 90), (-90, 270), (360, 0)])
def test_rotate_spellings_normalise(key, canonical):
    desc = describe_bytes(build_sheet(canonical, rotate_key=key, walls=False))
    assert desc.status is RAW and desc.rotation == canonical
    assert desc.rotate_entry == str(key)


def test_absent_and_inherited_rotate_resolve():
    absent = describe_bytes(build_sheet(0, rotate_key="absent", walls=False))
    assert absent.status is RAW and absent.rotation == 0 and absent.rotate_entry is None
    for rotation in (90, 180, 270):
        inherited = describe_bytes(build_sheet(rotation, rotate_key="inherit", walls=False))
        assert inherited.status is RAW and inherited.rotation == rotation
        assert inherited.rotate_entry is None  # page dict has no /Rotate; value comes from the Pages node


@needs_pymupdf_1_28
@pytest.mark.parametrize("authored", [0, 90])
@pytest.mark.parametrize("key", [45, 91, 90.5])
def test_library_rounded_rotate_spellings_are_conflict(key, authored):
    """MuPDF reads page.rotation 0 for these while page.rect is still swapped: fail closed."""
    desc = describe_bytes(build_sheet(authored, rotate_key=key, walls=False))
    assert desc.status is CONFLICT
    assert desc.reason_codes == (pf.PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT,)
    assert desc.native_extent is None and desc.display_extent is not None  # conflicting state preserved, no extent offered
    assert desc.rotation_reported == 0 and desc.rotate_entry == str(key)
    assert pf.PAGE_FRAME_NOTE_NONSTANDARD_ROTATE_ENTRY in desc.note_codes
    with pytest.raises(ValueError):
        desc.require_native_extent()


@needs_pymupdf_1_28
@pytest.mark.parametrize("key", [135, 136, 179, 181, 224, -136, -1, 1])
def test_non_orthogonal_rotate_entry_is_conflict_even_when_page_rect_and_rotation_look_fine(key):
    """MuPDF rounds these its own way (135 renders as 180) yet page.rotation reads 0 and the rect keeps
    its size, so rotation and orientation cross-check alone would publish a wrong-by-180 RAW frame."""
    desc = describe_bytes(build_sheet(0, rotate_key=key, walls=False))
    assert desc.status is CONFLICT
    assert desc.reason_codes == (pf.PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL,)
    assert desc.native_extent is None and desc.display_extent is not None
    assert desc.rotate_entry == str(key) and pf.PAGE_FRAME_NOTE_NONSTANDARD_ROTATE_ENTRY in desc.note_codes
    with pytest.raises(ValueError):
        desc.require_native_extent()


@needs_pymupdf_1_28
@pytest.mark.parametrize("key", [91, 89, 135])
def test_non_orthogonal_rotate_entry_on_a_square_page_is_conflict(key):
    """A square page hides the rect swap, so the orientation cross-check cannot see /Rotate 91."""
    desc = describe_bytes(build_sheet(0, rotate_key=key, walls=False, vw=600.0, vh=600.0))
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL,)


@needs_pymupdf_1_28
@pytest.mark.parametrize("key", [135, 91, 1, -1, 45])
def test_non_orthogonal_inherited_rotate_entry_is_conflict(key):
    data = set_pages_node_key(build_sheet(0, rotate_key="absent", walls=False), "Rotate", str(key))
    desc = describe_bytes(data)
    assert desc.status is CONFLICT and desc.native_extent is None
    assert desc.rotate_entry is None  # the page dictionary has no /Rotate of its own
    assert pf.PAGE_FRAME_NOTE_NONSTANDARD_ROTATE_ENTRY in desc.note_codes
    assert desc.reason_codes in ((pf.PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL,), (pf.PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT,))


@needs_pymupdf_1_28
def test_orthogonal_spellings_stay_coherent_own_and_inherited():
    for key, expected in (("90.0", 90), ("+90", 90), ("0090", 90), ("270.0", 270), ("-0", 0), ("720", 0)):
        desc = describe_bytes(build_sheet(0, rotate_key=key, walls=False))
        assert desc.status is RAW and desc.rotation == expected, key
    inherited = describe_bytes(set_pages_node_key(build_sheet(0, rotate_key="absent", walls=False), "Rotate", "450"))
    assert inherited.status is RAW and inherited.rotation == 90 and inherited.rotate_entry is None


@needs_pymupdf_1_28
def test_own_orthogonal_rotate_overrides_a_non_orthogonal_inherited_one():
    data = set_pages_node_key(build_sheet(90, walls=False), "Rotate", "135")
    desc = describe_bytes(data)
    assert desc.status is RAW and desc.rotation == 90 and desc.rotate_entry == "90"


@pytest.mark.parametrize("text", ["inf", "-inf", "nan", "1e400", "/abc", "5 0 R", ""])
def test_unparseable_or_non_finite_rotate_entries_conflict_without_raising(text):
    desc = _fake_descriptor(FakePage(keys={"Rotate": ("name", text)}))
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL,)


def test_inherited_rotate_walk_is_read_only_bounded_and_cycle_safe():
    # FakeParent answers every xref with the same keys, so a Parent entry loops back on itself.
    assert pf._read_inherited_rotate_entry(FakePage(keys={"Parent": ("xref", "7 0 R")})) is None
    assert pf._read_inherited_rotate_entry(FakePage(keys={"Parent": ("xref", "8 0 R")})) is None
    assert pf._read_inherited_rotate_entry(FakePage(keys={"Rotate": ("int", "90"), "Parent": ("xref", "8 0 R")})) is None
    no_parent = FakePage()
    no_parent.parent = None
    assert pf._read_inherited_rotate_entry(no_parent) is None
    # distinct nodes with no /Rotate anywhere: the walk is bounded by depth
    class Chain:
        def __init__(self):
            self.calls = 0

        def xref_get_key(self, xref, key):
            self.calls += 1
            return ("xref", f"{xref + 1} 0 R") if key == "Parent" else ("null", "null")

    class SelfLoop:
        def __init__(self):
            self.calls = 0

        def xref_get_key(self, xref, key):
            self.calls += 1
            return ("xref", "7 0 R") if key == "Parent" else ("null", "null")

    looped = FakePage()
    looped.parent = SelfLoop()
    assert pf._read_inherited_rotate_entry(looped) is None
    assert looped.parent.calls <= 3  # stops at the first repeated node instead of exhausting the depth bound

    page = FakePage()
    page.parent = Chain()
    assert pf._read_inherited_rotate_entry(page) is None
    assert page.parent.calls <= 2 * pf._MAX_PARENT_DEPTH + 2
    page.parent = type("P", (), {"xref_get_key": lambda self, x, k: ("null", "null") if k == "Parent" else ("null", "null")})()
    assert pf._read_inherited_rotate_entry(page) is None


def test_sideways_rotate_zero_sheet_is_a_coherent_rotation_zero_frame_with_no_orientation_claim():
    """Adversarial negative: rotation metadata alone says nothing about text direction."""
    sideways = build_sheet(0, sideways_from=90)
    rot90 = build_sheet(90)
    desc = describe_bytes(sideways)
    assert desc.status is RAW and desc.rotation == 0 and desc.rotate_entry == "0"
    assert desc.native_extent.width < desc.native_extent.height  # portrait, like the rot-90 native box
    assert (desc.native_extent.width, desc.native_extent.height) == (desc.display_extent.width, desc.display_extent.height)
    plain = desc.to_plain()
    assert not [k for k in plain if "orient" in k or "text" in k or "direction" in k]
    # same raw content as the genuinely rotated sheet, but the text reads sideways on the sideways sheet
    doc_s, doc_r = fitz.open(stream=sideways, filetype="pdf"), fitz.open(stream=rot90, filetype="pdf")
    assert doc_s[0].read_contents() == doc_r[0].read_contents()

    def first_line_dir(doc):
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                return line["dir"]

    raw_dir = first_line_dir(doc_s)
    assert raw_dir == first_line_dir(doc_r) and abs(raw_dir[0]) < 1e-6 and abs(abs(raw_dir[1]) - 1.0) < 1e-6
    m = doc_r[0].rotation_matrix
    display_dir = (m.a * raw_dir[0] + m.c * raw_dir[1], m.b * raw_dir[0] + m.d * raw_dir[1])
    assert abs(display_dir[0] - 1.0) < 1e-6 and abs(display_dir[1]) < 1e-6  # upright once /Rotate 90 applies ...
    assert abs(raw_dir[0]) < 1e-6  # ... and still sideways on the /Rotate 0 sheet: the frame cannot tell them apart


# ---- degenerate / unreadable / contradictory metadata (duck-typed page) --------------
def test_fake_page_default_is_coherent():
    desc = _fake_descriptor()
    assert desc.status is RAW and desc.page_id == "1"


@pytest.mark.parametrize("rect", [(0, 0, 0, 0), (0, 0, -5, 10), (0, 0, 10, 0)])
def test_degenerate_extent_abstains(rect):
    desc = _fake_descriptor(FakePage(rect=rect))
    assert desc.status is ABSTAINED and desc.reason_codes == (pf.PAGE_FRAME_DEGENERATE_EXTENT,)
    assert desc.native_extent is None


def test_unreadable_or_non_finite_rect_abstains():
    class Broken(FakePage):
        @property
        def rect(self):
            raise RuntimeError("no rect")

        @rect.setter
        def rect(self, value):
            pass

    assert _fake_descriptor(Broken()).reason_codes == (pf.PAGE_FRAME_PAGE_METADATA_UNREADABLE,)
    assert _fake_descriptor(FakePage(rect=(0, 0, float("nan"), 10))).reason_codes == (pf.PAGE_FRAME_PAGE_METADATA_UNREADABLE,)
    assert _fake_descriptor(FakePage(rect=(0, 0, float("inf"), 10))).reason_codes == (pf.PAGE_FRAME_PAGE_METADATA_UNREADABLE,)


@pytest.mark.parametrize("rotation", [45, 91, -1, None, True, 89.9, "90"])
def test_unresolvable_reported_rotation_abstains(rotation):
    desc = _fake_descriptor(FakePage(rotation=rotation))
    assert desc.status is ABSTAINED
    assert desc.reason_codes == (pf.PAGE_FRAME_ROTATION_UNRESOLVABLE,)


def test_reported_rotation_is_normalised_and_noted():
    page = FakePage(rect=(0, 0, 595, 842), rotation=450)
    desc = _fake_descriptor(page)
    assert desc.status is RAW and desc.rotation == 90 and desc.rotation_reported == 450
    assert pf.PAGE_FRAME_NOTE_ROTATION_NORMALISED in desc.note_codes
    assert (desc.native_extent.width, desc.native_extent.height) == (842.0, 595.0)
    negative = _fake_descriptor(FakePage(rect=(0, 0, 595, 842), rotation=-90))
    assert negative.rotation == 270 and negative.status is RAW


def test_rotation_disagreeing_with_rect_orientation_is_conflict():
    desc = _fake_descriptor(FakePage(rotation=90))  # rect/boxes landscape, rotation says swapped
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT,)
    assert desc.display_extent is not None and desc.native_extent is None


def test_rect_matching_no_box_orientation_is_conflict():
    desc = _fake_descriptor(FakePage(rect=(0, 0, 500, 300)))
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION,)


def test_rect_origin_not_zero_is_conflict():
    desc = _fake_descriptor(FakePage(rect=(10, 0, 852, 595)))
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_RECT_ORIGIN_NOT_ZERO,)


@pytest.mark.parametrize("raw", [("real", "0"), ("real", "-2"), ("name", "/abc"), ("real", "nan")])
def test_invalid_user_unit_abstains(raw):
    desc = _fake_descriptor(FakePage(keys={"UserUnit": raw}))
    assert desc.status is ABSTAINED and desc.reason_codes == (pf.PAGE_FRAME_USER_UNIT_INVALID,)


@needs_pymupdf_1_28
def test_real_user_unit_zero_abstains():
    data = set_page_key(build_sheet(0, walls=False), "UserUnit", "0")
    desc = describe_bytes(data)
    assert desc.status is ABSTAINED and desc.native_extent is None


def test_unreadable_user_unit_and_boxes_are_notes_not_guesses():
    page = FakePage()
    page.parent = None
    desc = _fake_descriptor(page)
    assert desc.status is RAW and desc.user_unit is None
    assert pf.PAGE_FRAME_NOTE_USER_UNIT_UNREADABLE in desc.note_codes
    assert pf.PAGE_FRAME_NOTE_ORIENTATION_CROSS_CHECK_SKIPPED in desc.note_codes

    class NoBoxes(FakePage):
        @property
        def mediabox(self):
            raise RuntimeError("boom")

        @mediabox.setter
        def mediabox(self, value):
            pass

    desc = _fake_descriptor(NoBoxes())
    assert desc.status is RAW
    assert pf.PAGE_FRAME_NOTE_BOXES_UNREADABLE in desc.note_codes
    assert desc.mediabox_pdf_y_up is None


# ---- ownership -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "override,reason",
    [
        ({"document_id": ""}, pf.PAGE_FRAME_DOCUMENT_ID_MISSING),
        ({"document_id": "   "}, pf.PAGE_FRAME_DOCUMENT_ID_MISSING),
        ({"document_id": None}, pf.PAGE_FRAME_DOCUMENT_ID_MISSING),
        ({"source_sha256": ""}, pf.PAGE_FRAME_SOURCE_SHA256_INVALID),
        ({"source_sha256": "abc"}, pf.PAGE_FRAME_SOURCE_SHA256_INVALID),
        ({"source_sha256": "g" * 64}, pf.PAGE_FRAME_SOURCE_SHA256_INVALID),
        ({"source_sha256": None}, pf.PAGE_FRAME_SOURCE_SHA256_INVALID),
        ({"revision": ""}, pf.PAGE_FRAME_REVISION_MISSING),
        ({"revision": None}, pf.PAGE_FRAME_REVISION_MISSING),
        ({"page_no": 0}, pf.PAGE_FRAME_PAGE_NO_INVALID),
        ({"page_no": -3}, pf.PAGE_FRAME_PAGE_NO_INVALID),
        ({"page_no": None}, pf.PAGE_FRAME_PAGE_NO_INVALID),
        ({"page_no": True}, pf.PAGE_FRAME_PAGE_NO_INVALID),
        ({"page_no": 1.0}, pf.PAGE_FRAME_PAGE_NO_INVALID),
    ],
)
def test_missing_or_invalid_ownership_abstains(override, reason):
    desc = _fake_descriptor(**override)
    assert desc.status is ABSTAINED
    assert reason in desc.reason_codes
    assert desc.native_extent is None and desc.display_extent is None and desc.rotation is None


def test_all_ownership_inputs_missing_lists_every_reason():
    desc = _fake_descriptor(document_id="", source_sha256="", revision="", page_no=0)
    assert set(desc.reason_codes) == {
        pf.PAGE_FRAME_DOCUMENT_ID_MISSING,
        pf.PAGE_FRAME_SOURCE_SHA256_INVALID,
        pf.PAGE_FRAME_REVISION_MISSING,
        pf.PAGE_FRAME_PAGE_NO_INVALID,
    }


def test_page_object_for_a_different_page_than_page_no_is_conflict():
    """A provenance record must not attach page 2's extent to page 1."""
    doc = fitz.open()
    doc.new_page(width=300, height=400)
    doc.new_page(width=500, height=200)
    data = doc.tobytes(no_new_id=True)
    doc.close()
    reopened = fitz.open(stream=data, filetype="pdf")
    own = ownership_for(data)
    ok = pf.describe_page_frame(reopened[1], page_no=2, **own)
    assert ok.status is RAW and (ok.native_extent.width, ok.native_extent.height) == (500.0, 200.0)
    for wrong_no in (1, 3):
        bad = pf.describe_page_frame(reopened[1], page_no=wrong_no, **own)
        assert bad.status is CONFLICT and bad.reason_codes == (pf.PAGE_FRAME_PAGE_NUMBER_MISMATCH,)
        assert bad.native_extent is None and bad.display_extent is None and bad.page_no == wrong_no
    # a duck-typed page without an integer .number cannot be checked and is not rejected
    assert _fake_descriptor(FakePage()).status is RAW


@pytest.mark.parametrize(
    "override",
    [{"document_id": "a\ud800"}, {"revision": "r\ud800"}, {"source_sha256": "\ud800" * 64}],
)
def test_ownership_text_that_cannot_be_utf8_encoded_abstains_instead_of_raising(override):
    desc = _fake_descriptor(**override)
    assert desc.status is ABSTAINED
    assert pf.PAGE_FRAME_OWNERSHIP_TEXT_NOT_UTF8 in desc.reason_codes
    text = desc.to_json()  # must not raise
    text.encode("utf-8")
    assert json.loads(text)["status"] == "abstained"
    assert desc.frame_id == desc.frame_id.encode("ascii").decode("ascii")


def test_revision_not_matching_producer_definition_is_conflict():
    desc = _fake_descriptor(revision="source_revision_" + "0" * 32)
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_REVISION_MISMATCH,)


def test_ownership_changes_the_frame_id():
    base = _fake_descriptor()
    assert _fake_descriptor(page_no=2).frame_id != base.frame_id
    other_doc = _fake_descriptor(document_id="doc-2", revision=pf.revision_id_for("doc-2", "ab" * 32))
    assert other_doc.frame_id != base.frame_id
    other_sha = _fake_descriptor(source_sha256="cd" * 32, revision=pf.revision_id_for("doc-1", "cd" * 32))
    assert other_sha.frame_id != base.frame_id


def test_document_id_and_sha_are_stripped_and_lowercased_like_the_producers():
    a = _fake_descriptor(document_id="  doc-1  ", source_sha256=("AB" * 32))
    assert a.document_id == "doc-1" and a.source_sha256 == "ab" * 32
    assert a.frame_id == _fake_descriptor().frame_id


# ---- determinism / serialisation / identity --------------------------------------------
def test_replay_is_deterministic_and_bytes_fixture_is_stable():
    data = build_sheet(90)
    assert data == build_sheet(90)  # fixture bytes are byte-stable (no_new_id)
    first, second = describe_bytes(data), describe_bytes(data)
    assert first == second and first.frame_id == second.frame_id and first.to_json() == second.to_json()


def test_identity_does_not_depend_on_wall_clock(monkeypatch):
    data = build_sheet(270, walls=False)
    own = ownership_for(data)
    doc = fitz.open(stream=data, filetype="pdf")
    before = pf.describe_page_frame(doc[0], page_no=1, **own)
    monkeypatch.setattr(time, "time", lambda: 4102444800.0)
    monkeypatch.setattr(time, "monotonic", lambda: 1.0)
    after = pf.describe_page_frame(doc[0], page_no=1, **own)
    assert before.frame_id == after.frame_id and before.to_json() == after.to_json()
    # A re-saved copy with a different (time-dependent) /ID changes the bytes, hence the
    # caller-supplied source hash; with the ownership held fixed the frame is identical.
    fresh = fitz.open(stream=doc.tobytes(), filetype="pdf")
    assert pf.describe_page_frame(fresh[0], page_no=1, **own).frame_id == before.frame_id


def test_plain_serialisation_is_sorted_json_safe_and_states_no_authority():
    desc = describe_bytes(build_sheet(90, user_unit=2))
    plain = desc.to_plain()
    assert list(plain) == sorted(plain)
    assert json.loads(desc.to_json()) == plain
    assert desc.to_json() == json.dumps(plain, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert plain["measurement_authority"] is False and pf.PageFrameDescriptor.MEASUREMENT_AUTHORITY is False
    assert plain["record_kind"] == "page_frame_provenance_record"
    assert plain["declared_coordinate_space"] == "native_page_user_space"
    assert plain["native_extent"]["coordinate_space"] == "native_page_user_space"
    assert plain["display_extent"]["coordinate_space"] == "display_rotated_space"
    assert plain["status"] == "raw" and plain["frame_id"] == desc.frame_id
    assert plain["frame_id"] == stable_contract_id("page_frame", {k: v for k, v in plain.items() if k != "frame_id"}, digest_chars=32)


def test_golden_serialisation_for_a_fixed_fake_page():
    desc = _fake_descriptor(FakePage(rect=(0, 0, 595, 842), rotation=90, mediabox=(0, 0, 842, 595), cropbox=(0, 0, 842, 595)))
    assert desc.to_json() == (
        '{"cropbox_pymupdf_y_down_from_mediabox_top":[0.0,0.0,842.0,595.0],"declared_coordinate_space":"native_page_user_space",'
        '"display_extent":{"coordinate_space":"display_rotated_space","height":842.0,"width":595.0},"document_id":"doc-1",'
        '"edge_quantisation_pt":0.00048828125,"extent_source":"pymupdf_page_rect_swapped_for_rotation",'
        '"frame_id":"' + desc.frame_id + '","measurement_authority":false,"mediabox_pdf_y_up":[0.0,0.0,842.0,595.0],'
        '"native_extent":{"coordinate_space":"native_page_user_space","height":595.0,"width":842.0},'
        '"note_codes":["page_frame_note_display_extent_differs_from_native"],"page_no":1,"reason_codes":[],'
        '"record_kind":"page_frame_provenance_record","revision":"' + desc.revision + '","rotate_entry":null,"rotation":90,'
        '"rotation_reported":90,"schema_version":"1.0.0","source_sha256":"' + "ab" * 32 + '","status":"raw","unit":"pdf_points","user_unit":1.0}'
    )


def test_float_rule_ints_and_floats_and_negative_zero_are_identical():
    assert pf.NativePageExtent(842, 595) == pf.NativePageExtent(842.0, 595.0)
    assert pf.NativePoint(-0.0, 1) == pf.NativePoint(0.0, 1.0)
    assert repr(pf.NativePoint(-0.0, 0).x) == "0.0"
    a = _fake_descriptor(FakePage(rect=(0, 0, 842, 595)))
    b = _fake_descriptor(FakePage(rect=(0.0, 0.0, 842.0, 595.0)))
    assert a.frame_id == b.frame_id
    for bad in (float("nan"), float("inf"), True, "1", None):
        with pytest.raises((TypeError, ValueError)):
            pf.NativePoint(bad, 0.0)


def test_unit_literal_matches_the_existing_coordinate_space_enum():
    from pb_figured_dimension_evidence import CoordinateSpace  # test-side import only

    assert pf.UNIT_PDF_POINTS == CoordinateSpace.PDF_POINTS.value
    assert {m.name for m in pf.FrameSpace} == {"NATIVE_PAGE_USER_SPACE", "DISPLAY_ROTATED_SPACE"}
    assert {m.value for m in pf.FrameSpace}.isdisjoint({m.value for m in CoordinateSpace})  # no competing unit vocabulary


def test_no_mutation_of_inputs():
    data = build_sheet(90, user_unit=2)
    snapshot = bytes(data)
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    facts = (page.rotation, tuple(page.rect), tuple(page.mediabox), tuple(page.cropbox), doc.xref_get_key(page.xref, "Rotate"))
    describe_bytes(data)
    pf.describe_page_frame(page, **ownership_for(data), page_no=1)
    assert data == snapshot
    assert facts == (page.rotation, tuple(page.rect), tuple(page.mediabox), tuple(page.cropbox), doc.xref_get_key(page.xref, "Rotate"))
    fake = FakePage(rect=(0, 0, 595, 842), rotation=450)
    before = copy.deepcopy(fake.__dict__["rect"].__dict__), fake.rotation, fake.parent.keys.copy()
    _fake_descriptor(fake)
    assert (fake.__dict__["rect"].__dict__, fake.rotation, fake.parent.keys) == before


def test_descriptor_is_frozen_and_self_checking():
    desc = describe_bytes(build_sheet(0, walls=False))
    with pytest.raises(dataclasses.FrozenInstanceError):
        desc.rotation = 90  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        desc.native_extent.width = 1.0  # type: ignore[misc]
    with pytest.raises(ValueError):
        dataclasses.replace(desc, rotation=90)  # frame_id no longer matches the facts
    with pytest.raises(ValueError):
        dataclasses.replace(desc, status=CONFLICT)  # a non-coherent frame must not expose an extent


def test_descriptor_ignores_drawn_content_and_unrelated_additions():
    """Frame facts come from page metadata only: adding far-away drawings changes nothing."""
    with_walls = describe_bytes(build_sheet(90))
    without = describe_bytes(build_sheet(90, walls=False))
    assert {k: v for k, v in with_walls.to_plain().items() if k not in ("frame_id", "source_sha256", "revision")} == {
        k: v for k, v in without.to_plain().items() if k not in ("frame_id", "source_sha256", "revision")
    }


def _multi_code_descriptors():
    """Descriptors carrying several reason / note codes (their order must not depend on the hash seed)."""
    many_reasons = _fake_descriptor(document_id="", source_sha256="", revision="", page_no=0)
    page = FakePage(rect=(0, 0, 595.0, 842.0), rotation=450)
    page.parent = None
    return [many_reasons, _fake_descriptor(page)]


def _seed_hash(seed: str) -> str:
    # The subprocess imports the SAME module file the parent process is testing (pf.__file__), so a
    # variant of the module placed earlier on the path is exercised in both processes.
    module_dir = str(Path(pf.__file__).resolve().parent)
    code = (
        "import sys, hashlib\n"
        f"sys.path[:0] = [{module_dir!r}, {str(ROOT)!r}, {str(TESTS)!r}]\n"
        "import page_frame_test_support as s\n"
        "import pb_page_frame_shadow as pf\n"
        "from page_frame_test_support import FakePage\n"
        "out = []\n"
        "for rot in (0, 90, 180, 270):\n"
        "    for uu in (1, 2):\n"
        "        out.append(s.describe_bytes(s.build_sheet(rot, user_unit=uu)).to_json())\n"
        "out.append(s.describe_bytes(s.build_sheet(90, rotate_key=45)).to_json())\n"
        "own = {'document_id': 'doc-1', 'source_sha256': 'ab' * 32, 'page_no': 1}\n"
        "own['revision'] = pf.revision_id_for(own['document_id'], own['source_sha256'])\n"
        "bad = dict(own, document_id='', source_sha256='', revision='', page_no=0)\n"
        "out.append(pf.describe_page_frame(FakePage(), **bad).to_json())\n"
        "page = FakePage(rect=(0, 0, 595.0, 842.0), rotation=450)\n"
        "page.parent = None\n"
        "out.append(pf.describe_page_frame(page, **own).to_json())\n"
        "print(pf.__file__)\n"
        "print(hashlib.sha256('\\n'.join(out).encode()).hexdigest())\n"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(ROOT), check=True)
    lines = proc.stdout.strip().splitlines()
    assert Path(lines[-2]).resolve() == Path(pf.__file__).resolve()  # the subprocess really used the module under test
    return lines[-1]


def test_serialisation_is_byte_stable_across_hash_seeds_and_processes():
    hashes = {seed: _seed_hash(seed) for seed in ("0", "1", "999")}
    assert len(set(hashes.values())) == 1, hashes
    in_process = [describe_bytes(build_sheet(r, user_unit=u)).to_json() for r in ROTATIONS for u in (1, 2)]
    in_process.append(describe_bytes(build_sheet(90, rotate_key=45)).to_json())
    in_process.extend(d.to_json() for d in _multi_code_descriptors())
    assert hashlib.sha256("\n".join(in_process).encode()).hexdigest() == hashes["0"]


# ---- type safety: native vs display -------------------------------------------------------
def test_display_types_cannot_reach_native_helpers():
    native = pf.NativePageExtent(842, 595)
    display = pf.DisplayPageExtent(842, 595)
    npoint, dpoint = pf.NativePoint(1, 1), pf.DisplayPoint(1, 1)
    assert pf.native_point_inside(native, npoint, tol=0.0) is True
    for extent, point in ((display, npoint), (native, dpoint), (display, dpoint)):
        with pytest.raises(TypeError):
            pf.native_point_inside(extent, point, tol=0.0)
        with pytest.raises(TypeError):
            pf.native_point_on_edge(extent, point, tol=0.0)
    with pytest.raises(TypeError):
        native.contains(dpoint, tol=0.0)
    with pytest.raises(TypeError):
        native.point_on_edge(dpoint, tol=0.0)
    for bare in ((1.0, 1.0), [1.0, 1.0]):
        with pytest.raises(TypeError):
            pf.native_point_inside(native, bare, tol=0.0)  # type: ignore[arg-type]
    # the display types have no containment / boundary helper at all
    assert not hasattr(display, "contains") and not hasattr(display, "point_on_edge")
    assert not hasattr(dpoint, "contains") and not hasattr(dpoint, "point_on_edge")
    with pytest.raises(ValueError):
        pf.native_point_inside(native, npoint, tol=-1.0)


def test_extents_and_points_are_not_iterable_unpackable_or_mutually_equal():
    for obj in (pf.NativePageExtent(3, 4), pf.DisplayPageExtent(3, 4), pf.NativePoint(3, 4), pf.DisplayPoint(3, 4)):
        with pytest.raises(TypeError):
            iter(obj)
        with pytest.raises(TypeError):
            a, b = obj  # type: ignore[misc]
        with pytest.raises(TypeError):
            len(obj)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            obj[0]  # type: ignore[index]
    assert pf.NativePageExtent(3, 4) != pf.DisplayPageExtent(3, 4)
    assert pf.DisplayPageExtent(3, 4) != pf.NativePageExtent(3, 4)
    assert pf.NativePoint(3, 4) != pf.DisplayPoint(3, 4)
    assert pf.NativePageExtent(3, 4) != (3.0, 4.0)
    assert len({pf.NativePageExtent(3, 4), pf.DisplayPageExtent(3, 4)}) == 2
    assert pf.NativePageExtent.SPACE is pf.FrameSpace.NATIVE_PAGE_USER_SPACE
    assert pf.DisplayPageExtent.SPACE is pf.FrameSpace.DISPLAY_ROTATED_SPACE
    for bad in (0, -1):
        with pytest.raises(ValueError):
            pf.NativePageExtent(bad, 5)
        with pytest.raises(ValueError):
            pf.DisplayPageExtent(5, bad)


def test_edge_helper_does_not_treat_points_outside_the_box_as_on_an_edge():
    extent = pf.NativePageExtent(400, 300)
    tol = 0.01
    assert extent.point_on_edge(pf.NativePoint(400, 150), tol=tol)
    assert extent.point_on_edge(pf.NativePoint(0, 0), tol=tol)
    assert extent.point_on_edge(pf.NativePoint(399.995, 150), tol=tol)
    assert not extent.point_on_edge(pf.NativePoint(399.9, 150), tol=tol)  # 0.1 short: interior
    assert not extent.point_on_edge(pf.NativePoint(200, 150), tol=tol)
    assert not extent.point_on_edge(pf.NativePoint(-50, 300), tol=tol)  # on the y=300 line but outside the page
    assert not extent.contains(pf.NativePoint(-50, 300), tol=tol)
    assert extent.contains(pf.NativePoint(400.005, 300), tol=tol)


def test_extent_conversions_between_spaces_are_explicit_and_consistent():
    native = pf.NativePageExtent(842, 595)
    assert pf.display_extent_for(native, 0) == pf.DisplayPageExtent(842, 595)
    assert pf.display_extent_for(native, 180) == pf.DisplayPageExtent(842, 595)
    assert pf.display_extent_for(native, 90) == pf.DisplayPageExtent(595, 842)
    assert pf.display_extent_for(native, 270) == pf.DisplayPageExtent(595, 842)
    for rotation in ROTATIONS:
        assert pf.native_extent_for(pf.display_extent_for(native, rotation), rotation) == native
    with pytest.raises(TypeError):
        pf.display_extent_for(pf.DisplayPageExtent(1, 1), 90)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pf.native_extent_for(native, 90)  # type: ignore[arg-type]
    for bad in (45, 91, -1, True, None, 90.0, "90"):
        with pytest.raises(ValueError):
            pf.display_extent_for(native, bad)  # type: ignore[arg-type]
    assert [pf.normalise_rotation(v) for v in (0, 90, 180, 270, 360, 450, -90, -180)] == [0, 90, 180, 270, 0, 90, 270, 180]
    assert [pf.normalise_rotation(v) for v in (45, 91, -1, True, 90.0, None, "90")] == [None] * 7


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_native_display_round_trip_is_exact_to_double_rounding(rotation):
    native = pf.NativePageExtent(841.8900146484375, 595.280029296875)
    display = pf.display_extent_for(native, rotation)
    tol = 8 * math.ulp(max(native.width, native.height))
    for x, y in ((0.0, 0.0), (12.5, 77.25), (841.8900146484375, 595.280029296875), (300.1, 500.9)):
        point = pf.NativePoint(x, y)
        shown = pf.native_to_display(point, native_extent=native, rotation=rotation)
        assert isinstance(shown, pf.DisplayPoint)
        back = pf.display_to_native(shown, display_extent=display, rotation=rotation)
        assert isinstance(back, pf.NativePoint)
        assert abs(back.x - x) <= tol and abs(back.y - y) <= tol
    with pytest.raises(TypeError):
        pf.native_to_display(pf.DisplayPoint(1, 1), native_extent=native, rotation=rotation)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pf.display_to_native(pf.NativePoint(1, 1), display_extent=display, rotation=rotation)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        pf.native_to_display(pf.NativePoint(1, 1), native_extent=display, rotation=rotation)  # type: ignore[arg-type]


@pytest.mark.parametrize("user_unit", [1, 2])
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_conversions_agree_with_pymupdf_rotation_matrix_within_float32_tolerance(rotation, user_unit):
    """rotation_matrix is float32 and NOT UserUnit aware: compare on unscaled points."""
    data = build_sheet(rotation, user_unit=user_unit, walls=False)
    desc = describe_bytes(data)
    page = fitz.open(stream=data, filetype="pdf")[0]
    tol = _ulp_tol(desc.display_extent.width, desc.display_extent.height)
    for x, y in ((0.0, 0.0), (100.0, 50.0), (250.5, 400.25), (500.0, 300.0)):
        via_fitz = fitz.Point(x, y) * page.rotation_matrix
        mine = desc.to_display(pf.NativePoint(x * user_unit, y * user_unit))
        assert abs(mine.x - via_fitz.x * user_unit) <= tol and abs(mine.y - via_fitz.y * user_unit) <= tol
        back = desc.to_native(mine)
        assert abs(back.x - x * user_unit) <= tol and abs(back.y - y * user_unit) <= tol


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_fixture_visual_points_map_to_native_and_back_through_the_descriptor(rotation):
    desc = describe_bytes(build_sheet(rotation, walls=False))
    tol = _ulp_tol(VW, VH)
    for dx, dy in ((0.0, 0.0), (150.0, 60.0), (VW, VH), (VW - 140, 340.0)):
        native = to_native(rotation, VW, VH, dx, dy)  # the fixture's own (authoring) map
        shown = desc.to_display(pf.NativePoint(*native))
        assert abs(shown.x - dx) <= tol and abs(shown.y - dy) <= tol


def test_rect_times_derotation_matrix_is_not_the_extent_authority():
    """Regression guard (UserUnit=2 experiment): the derotation matrix is not UserUnit aware."""
    page1 = fitz.open(stream=build_sheet(90, user_unit=1, walls=False), filetype="pdf")[0]
    page2 = fitz.open(stream=build_sheet(90, user_unit=2, walls=False), filetype="pdf")[0]
    desc2 = describe_bytes(build_sheet(90, user_unit=2, walls=False))
    rect1 = page1.rect * page1.derotation_matrix
    w1, h1 = page1.rect.height, page1.rect.width
    assert tuple(rect1) == (0.0, 0.0, w1, h1)  # happens to work at UserUnit 1
    rect2 = page2.rect * page2.derotation_matrix
    w2, h2 = desc2.native_extent.width, desc2.native_extent.height
    assert (w2, h2) == (page2.rect.height, page2.rect.width)
    # ... but at UserUnit 2 the box is anchored wrongly (it spans negative y), so it is not the native box
    assert tuple(rect2) != (0.0, 0.0, w2, h2)
    assert rect2.y0 < 0.0


def test_descriptor_helpers_refuse_a_non_coherent_frame():
    conflict = _fake_descriptor(FakePage(rect=(0, 0, 500, 300)))
    with pytest.raises(ValueError):
        conflict.to_display(pf.NativePoint(1, 1))
    with pytest.raises(ValueError):
        conflict.to_native(pf.DisplayPoint(1, 1))
    coherent = _fake_descriptor()
    with pytest.raises(TypeError):
        coherent.to_display(pf.DisplayPoint(1, 1))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        coherent.to_native(pf.NativePoint(1, 1))  # type: ignore[arg-type]


def test_float32_ulp_values():
    assert pf.float32_ulp(0.0) == 0.0
    assert pf.float32_ulp(1.0) == 2.0**-23
    assert pf.float32_ulp(1.9999999) == 2.0**-23
    assert pf.float32_ulp(2.0) == 2.0**-22
    assert pf.float32_ulp(-2500.0) == 2.0**-12
    assert pf.float32_ulp(float("inf")) == 0.0


# ---- architecture: no production importer, no authority imports ------------------------------
NON_PRODUCTION_DIRS = {"tests", "benchmarks", "scripts", "node_modules"}


def _root_python_files():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in NON_PRODUCTION_DIRS or any(p.startswith(".") for p in rel.parts):
            continue
        yield path


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value  # dynamic import strings are caught too


def test_no_production_module_imports_the_page_frame_shadow():
    offenders = []
    for path in _root_python_files():
        if path.name == "pb_page_frame_shadow.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        if any(name == "pb_page_frame_shadow" or name.startswith("pb_page_frame_shadow.") for name in _imports(tree)):
            offenders.append(path.name)
    assert offenders == []


def test_only_the_shadow_diff_script_imports_the_page_frame_shadow_outside_tests():
    importers = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if "pb_page_frame_shadow" in set(_imports(tree)):
            importers.append(path.name)
    assert importers == ["page_frame_wall_boundary_shadow_diff.py"]


FIRM_SEAM_MODULES = (
    "pb_page_scale_calibration_authority",
    "pb_viewport_scale_binding",
    "pb_measurement_input_authority",
    "pb_figured_dimension_authority",
    "pb_wall_length_quantity",
    "pb_wall_height_authority",
    "pb_physical_wall_candidate_authority",
    "pb_wall_room_topology_canonical_adapter",
    "pb_planreader_pdf_extractor",
    "pb_vector_geometry_v130",
)


def test_firm_seam_modules_do_not_import_the_page_frame_shadow():
    for name in FIRM_SEAM_MODULES:
        tree = ast.parse((ROOT / f"{name}.py").read_text(encoding="utf-8-sig"))
        assert "pb_page_frame_shadow" not in set(_imports(tree)), name


def test_the_page_frame_shadow_imports_only_stdlib_and_the_contract_module():
    tree = ast.parse((ROOT / "pb_page_frame_shadow.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    local_modules = {n for n in imported if (ROOT / f"{n}.py").exists()}
    assert local_modules == {"pb_migration_contracts"}
    assert imported - local_modules <= set(sys.stdlib_module_names) | {"__future__"}
    # the one local dependency is itself stdlib-only (so no authority module is reachable)
    contract_tree = ast.parse((ROOT / "pb_migration_contracts.py").read_text(encoding="utf-8"))
    contract_imports = set()
    for node in ast.walk(contract_tree):
        if isinstance(node, ast.Import):
            contract_imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            contract_imports.add(node.module.split(".")[0])
    assert not {n for n in contract_imports if (ROOT / f"{n}.py").exists()}


def test_the_module_does_not_import_pymupdf_or_reference_takeoff_rows():
    source = (ROOT / "pb_page_frame_shadow.py").read_text(encoding="utf-8")
    assert "import fitz" not in source and "takeoff_rows" not in source
    for fragment in ("expected_boq", "expected_project", "benchmark_rules", "item_mappings", "holdout_suite", "scoring_tolerance"):
        assert fragment not in source


def test_importing_the_module_leaves_no_authority_module_loaded():
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import pb_page_frame_shadow\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('pb_') and m not in ('pb_page_frame_shadow', 'pb_migration_contracts'))\n"
        "print(','.join(loaded))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ROOT), check=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.stdout.strip() == ""


def test_w10_adapter_authority_flags_are_still_hardcoded_false():
    source_path = ROOT / "pb_wall_room_topology_canonical_adapter.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    flags = {"takeoff_eligible": [], "deduction_authority": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in flags:
            flags[node.arg].append(isinstance(node.value, ast.Constant) and node.value.value is False)
    assert len(flags["takeoff_eligible"]) >= 3 and len(flags["deduction_authority"]) >= 3
    assert all(flags["takeoff_eligible"]) and all(flags["deduction_authority"])
