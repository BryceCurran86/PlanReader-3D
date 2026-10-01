"""Mutation-hardening tests for pb_page_frame_shadow (shadow-only descriptor).

Each test here pins behaviour that a deliberate breakage of the descriptor module
(found during independent mutation testing) previously slipped through: tolerance
scale, frame-id sensitivity to every frame fact, sorted multi-code output, the
"descriptor only reads" guarantee, per-page independence, and the promotion-gate
documentation. Synthetic fixtures only.
"""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import fitz
import pytest

import pb_page_frame_shadow as pf
from pb_migration_contracts import EvidenceResolutionStatus
from page_frame_test_support import (
    VH,
    VW,
    FakePage,
    build_sheet,
    describe_bytes,
    ownership_for,
)

ROOT = Path(__file__).resolve().parent.parent
ROTATIONS = (0, 90, 180, 270)
RAW = EvidenceResolutionStatus.RAW
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT
ULP_842 = pf.float32_ulp(842.0)


def _fake(page=None, **overrides):
    own = {"document_id": "doc-1", "source_sha256": "ab" * 32, "page_no": 1}
    own["revision"] = pf.revision_id_for(own["document_id"], own["source_sha256"])
    own.update(overrides)
    return pf.describe_page_frame(page if page is not None else FakePage(), **own)


# ---- tolerance scale: float32 rounding passes, real disagreement does not -----------------
def test_orientation_cross_check_tolerance_is_float32_scale_not_loose():
    assert _fake(FakePage(rect=(0, 0, 842.0 + ULP_842, 595.0))).status is RAW  # 1 ulp of rounding
    assert _fake(FakePage(rect=(0, 0, 842.0, 595.0 + pf.float32_ulp(595.0)))).status is RAW
    # the bound is a handful of half-ulps: 12 ulp (0.0007 pt) is already a disagreement, not rounding
    assert _fake(FakePage(rect=(0, 0, 842.0 + 12 * ULP_842, 595.0))).reason_codes == (pf.PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION,)
    assert _fake(FakePage(rect=(0, 0, 842.0, 595.0 + 12 * pf.float32_ulp(595.0)))).status is CONFLICT
    assert _fake(FakePage(rect=(0, 0, 842.0 - 12 * ULP_842, 595.0))).status is CONFLICT
    wider = _fake(FakePage(rect=(0, 0, 842.01, 595.0)))  # ~160 ulp wider
    taller = _fake(FakePage(rect=(0, 0, 842.0, 595.01)))
    for desc in (wider, taller):
        assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION,)
        assert desc.native_extent is None and desc.display_extent is not None
    # the same holds for a rotated page: rect is the swapped box +/- rounding
    assert _fake(FakePage(rect=(0, 0, 595.0 + pf.float32_ulp(595.0), 842.0), rotation=90)).status is RAW
    assert _fake(FakePage(rect=(0, 0, 595.01, 842.0), rotation=90)).status is CONFLICT
    assert _fake(FakePage(rect=(0, 0, 595.0, 842.01), rotation=90)).status is CONFLICT


def test_orientation_conflict_codes_distinguish_swapped_from_unrelated():
    swapped = _fake(FakePage(rect=(0, 0, 595.0, 842.0), rotation=0))  # rect is exactly the swapped box
    unrelated = _fake(FakePage(rect=(0, 0, 500.0, 300.0), rotation=0))
    assert swapped.reason_codes == (pf.PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT,)
    assert unrelated.reason_codes == (pf.PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION,)


@pytest.mark.parametrize(
    "rect",
    [(0.01, 0.0, 842.01, 595.0), (0.0, 0.01, 842.0, 595.01), (-0.01, 0.0, 841.99, 595.0), (0.0, -0.01, 842.0, 594.99)],
)
def test_rect_origin_guard_checks_both_axes_at_float32_scale(rect):
    desc = _fake(FakePage(rect=rect))
    assert desc.status is CONFLICT and desc.reason_codes == (pf.PAGE_FRAME_RECT_ORIGIN_NOT_ZERO,)
    assert desc.native_extent is None


def test_rect_origin_within_float32_rounding_is_not_a_conflict():
    tiny = 2 * ULP_842
    desc = _fake(FakePage(rect=(tiny, -tiny, 842.0 + tiny, 595.0 - tiny)))
    assert desc.status is RAW


@pytest.mark.parametrize("mediabox,cropbox", [
    ((0, 0, 842, 600), (0, 0, 842, 595)),      # crop is the top 595 rows (y-down) of a taller media box
    ((0, 0, 842, 600), (0, 5, 842, 600)),      # crop is the bottom 595 rows
    ((0, 0, 900, 700), (0, 0, 842, 595)),
    ((10, 20, 852, 620), (10, 25, 852, 620)),  # offset media box
])
def test_effective_box_follows_the_crop_geometry(mediabox, cropbox):
    """The cropbox is y-down from the mediabox top; a plausible rect of exactly its size is coherent,
    and a rect the size of the WHOLE mediabox (crop ignored) is not, unless the boxes coincide."""
    w, h = cropbox[2] - cropbox[0], cropbox[3] - cropbox[1]
    media_w, media_h = mediabox[2] - mediabox[0], mediabox[3] - mediabox[1]
    # the y-down cropbox coordinates PyMuPDF reports:
    top = mediabox[3]
    crop_down = (cropbox[0], top - cropbox[3], cropbox[2], top - cropbox[1])
    coherent = _fake(FakePage(rect=(0, 0, w, h), mediabox=mediabox, cropbox=crop_down))
    assert coherent.status is RAW, (coherent.reason_codes, (w, h))
    assert (coherent.native_extent.width, coherent.native_extent.height) == (float(w), float(h))
    if (media_w, media_h) != (w, h):
        ignoring_crop = _fake(FakePage(rect=(0, 0, media_w, media_h), mediabox=mediabox, cropbox=crop_down))
        assert ignoring_crop.status is CONFLICT


def test_edge_quantisation_follows_the_absolute_mediabox_magnitude():
    """The quantisation bound must scale with the largest float32 magnitude taking part, which for a
    far-from-origin MediaBox is the absolute coordinate x UserUnit, not the page size."""
    near = describe_bytes(build_sheet(0, walls=False))
    far = describe_bytes(build_sheet(0, walls=False, origin=(5000.0, 3000.0)))
    assert far.status is RAW and near.status is RAW
    assert near.edge_quantisation_pt == pf.EDGE_QUANTISATION_ULPS * pf.float32_ulp(max(VW, VH))
    far_max = max(abs(v) for v in far.mediabox_pdf_y_up)
    assert far.edge_quantisation_pt == pf.EDGE_QUANTISATION_ULPS * pf.float32_ulp(max(VW, VH, far_max))
    assert far.edge_quantisation_pt > near.edge_quantisation_pt
    scaled = describe_bytes(build_sheet(0, walls=False, user_unit=2, origin=(5000.0, 3000.0)))
    assert scaled.edge_quantisation_pt == pf.EDGE_QUANTISATION_ULPS * pf.float32_ulp(2.0 * max(abs(v) for v in scaled.mediabox_pdf_y_up))


# ---- identity: every frame fact is part of the frame id ---------------------------------------
def _no_box_page(user_unit):
    class NoBoxes(FakePage):
        @property
        def mediabox(self):
            raise RuntimeError("boom")

        @mediabox.setter
        def mediabox(self, value):
            pass

    return NoBoxes(keys={"UserUnit": ("real", str(user_unit))})


def test_each_single_frame_fact_changes_the_frame_id():
    portrait = dict(rect=(0, 0, 595.0, 842.0), mediabox=(0, 0, 842, 595), cropbox=(0, 0, 842, 595))
    variants = {
        "base": _fake(),
        "rotation_90": _fake(FakePage(rotation=90, **portrait)),
        "rotation_270": _fake(FakePage(rotation=270, **portrait)),
        "rotation_450_same_normalised": _fake(FakePage(rotation=450, **portrait)),
        "rotate_entry_only_a": _fake(FakePage(rotation=90, keys={"Rotate": ("int", "90")}, **portrait)),
        "rotate_entry_only_b": _fake(FakePage(rotation=90, keys={"Rotate": ("int", "450")}, **portrait)),
        "user_unit_only_1": _fake(_no_box_page(1)),
        "user_unit_only_2": _fake(_no_box_page(2)),
        "mediabox_only": _fake(FakePage(mediabox=(0, 0, 900, 700), cropbox=(0, 0, 842, 595))),
        "cropbox_only_a": _fake(FakePage(mediabox=(0, 0, 842, 600), cropbox=(0, 0, 842, 595))),
        "cropbox_only_b": _fake(FakePage(mediabox=(0, 0, 842, 600), cropbox=(0, 5, 842, 600))),
        "display_size": _fake(FakePage(rect=(0, 0, 841.5, 595.0), mediabox=(0, 0, 841.5, 595), cropbox=(0, 0, 841.5, 595))),
    }
    for name in ("rotation_90", "rotation_270", "rotation_450_same_normalised"):
        assert variants[name].status is RAW, name
    ids = {name: desc.frame_id for name, desc in variants.items()}
    assert len(set(ids.values())) == len(ids), ids
    # a pure replay of one variant gives the identical id
    assert _fake(_no_box_page(2)).frame_id == ids["user_unit_only_2"]


def test_ownership_fields_are_each_part_of_the_frame_id():
    base = _fake()
    assert _fake(page_no=2).frame_id != base.frame_id
    other_sha = "cd" * 32
    assert _fake(source_sha256=other_sha, revision=pf.revision_id_for("doc-1", other_sha)).frame_id != base.frame_id
    assert _fake(document_id="doc-2", revision=pf.revision_id_for("doc-2", "ab" * 32)).frame_id != base.frame_id
    # same document/source but the page number alone: ids differ, nothing else does
    a, b = _fake(page_no=1).to_plain(), _fake(page_no=2).to_plain()
    assert {k for k in a if a[k] != b[k]} == {"frame_id", "page_no"}


def test_frame_id_is_a_pure_function_of_the_frame_facts():
    """Same ownership + same facts from a differently built page object gives the same id."""
    a = _fake(FakePage(rect=(0, 0, 842, 595)))
    b = _fake(FakePage(rect=(0.0, 0.0, 842.0, 595.0), keys={}))
    assert a.frame_id == b.frame_id and a.to_json() == b.to_json()
    assert a.frame_id.startswith("page_frame_")


# ---- deterministic ordering of multi-valued fields ----------------------------------------------
def test_multi_reason_and_multi_note_outputs_are_sorted_and_json_ordered():
    many_reasons = _fake(document_id="", source_sha256="", revision="", page_no=0)
    assert len(many_reasons.reason_codes) == 4
    assert list(many_reasons.reason_codes) == sorted(many_reasons.reason_codes)
    page = FakePage(rect=(0, 0, 595.0, 842.0), rotation=450)
    page.parent = None
    many_notes = _fake(page)
    assert many_notes.status is RAW and len(many_notes.note_codes) >= 3
    assert list(many_notes.note_codes) == sorted(many_notes.note_codes)
    for desc in (many_reasons, many_notes):
        plain = desc.to_plain()
        assert plain["reason_codes"] == sorted(plain["reason_codes"]) and plain["note_codes"] == sorted(plain["note_codes"])
        assert list(plain) == sorted(plain)
        nested = [v for v in plain.values() if isinstance(v, dict)]
        assert all(list(v) == sorted(v) for v in nested)
        assert nested or desc is many_reasons
        raw_json = desc.to_json()
        assert raw_json == json.dumps(json.loads(raw_json), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def test_json_text_key_order_is_alphabetical_at_every_level():
    desc = describe_bytes(build_sheet(90, user_unit=2, walls=False))
    seen = []

    def hook(pairs):
        seen.append([k for k, _ in pairs])
        return dict(pairs)

    json.loads(desc.to_json(), object_pairs_hook=hook)
    assert seen and all(keys == sorted(keys) for keys in seen)


# ---- the descriptor only reads ---------------------------------------------------------------
class _Recorder:
    def __init__(self, wrapped, log, prefix):
        object.__setattr__(self, "_w", wrapped)
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_prefix", prefix)

    def __getattr__(self, name):
        self._log.add(f"{self._prefix}.{name}")
        return getattr(self._w, name)

    def __setattr__(self, name, value):
        self._log.add(f"SET {self._prefix}.{name}")
        setattr(self._w, name, value)


def test_descriptor_touches_only_the_read_only_page_surface():
    log: set = set()
    fake = FakePage(rect=(0, 0, 595.0, 842.0), rotation=90, mediabox=(0, 0, 842, 595), cropbox=(0, 0, 842, 595))
    fake.parent = _Recorder(fake.parent, log, "parent")
    wrapped = _Recorder(fake, log, "page")
    desc = _fake(wrapped)
    assert desc.status is RAW
    assert {"page.rect", "page.rotation", "page.mediabox", "page.cropbox", "page.xref", "page.parent", "page.number", "parent.xref_get_key"} >= log, log
    assert not [entry for entry in log if entry.startswith("SET") or "set" in entry.lower()]


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_describing_a_real_page_leaves_the_document_untouched(rotation):
    data = build_sheet(rotation, user_unit=2)
    doc = fitz.open(stream=data, filetype="pdf")
    before = doc.tobytes(no_new_id=True)
    own = ownership_for(data)
    page = doc[0]
    first = pf.describe_page_frame(page, page_no=1, **own)
    assert not doc.is_dirty and not doc.is_closed
    assert doc.tobytes(no_new_id=True) == before
    assert pf.describe_page_frame(page, page_no=1, **own) == first  # idempotent on the same open page
    assert pf.describe_page_frame(doc[0], page_no=1, **own) == first
    assert page.rotation == rotation


# ---- page independence, repetition, order ------------------------------------------------------------
def _mixed_document() -> bytes:
    out = fitz.open()
    for rotation in ROTATIONS:
        src = fitz.open(stream=build_sheet(rotation, walls=False), filetype="pdf")
        out.insert_pdf(src)
        src.close()
    data = out.tobytes(no_new_id=True)
    out.close()
    return data


def _describe_all(data: bytes, order):
    doc = fitz.open(stream=data, filetype="pdf")
    own = ownership_for(data)
    try:
        return {n: pf.describe_page_frame(doc[n - 1], page_no=n, **own) for n in order}
    finally:
        doc.close()


def test_mixed_rotation_document_gives_independent_per_page_descriptors():
    data = _mixed_document()
    frames = _describe_all(data, (1, 2, 3, 4))
    assert [frames[n].rotation for n in (1, 2, 3, 4)] == list(ROTATIONS)
    assert all(f.status is RAW for f in frames.values())
    # one visual sheet authored four ways: identical display extent, native swapped at 90/270
    display = {(f.display_extent.width, f.display_extent.height) for f in frames.values()}
    assert len(display) == 1
    for n, rotation in zip((1, 2, 3, 4), ROTATIONS):
        swapped = rotation in (90, 270)
        native = frames[n].native_extent
        assert (native.width, native.height) == ((frames[n].display_extent.height, frames[n].display_extent.width) if swapped else (frames[n].display_extent.width, frames[n].display_extent.height))
        assert frames[n].page_id == str(n)
    assert len({f.frame_id for f in frames.values()}) == 4
    # each page equals the descriptor of the same page built alone, modulo ownership
    for n, rotation in zip((1, 2, 3, 4), ROTATIONS):
        alone = describe_bytes(build_sheet(rotation, walls=False)).to_plain()
        here = frames[n].to_plain()
        drop = ("frame_id", "source_sha256", "revision", "page_no")
        assert {k: v for k, v in here.items() if k not in drop} == {k: v for k, v in alone.items() if k not in drop}


def test_descriptors_are_independent_of_the_order_pages_are_described_in():
    data = _mixed_document()
    forward = _describe_all(data, (1, 2, 3, 4))
    backward = _describe_all(data, (4, 3, 2, 1))
    shuffled = _describe_all(data, (3, 1, 4, 2))
    for n in (1, 2, 3, 4):
        assert forward[n] == backward[n] == shuffled[n]
        assert forward[n].to_json() == backward[n].to_json() == shuffled[n].to_json()
    only_three = _describe_all(data, (3,))
    assert only_three[3] == forward[3]  # describing other pages first or not at all changes nothing


def test_repeated_identical_pages_differ_only_by_page_number():
    src = fitz.open(stream=build_sheet(90), filetype="pdf")
    out = fitz.open()
    for _ in range(3):
        out.insert_pdf(src)
    data = out.tobytes(no_new_id=True)
    src.close()
    out.close()
    frames = _describe_all(data, (1, 2, 3))
    plains = [frames[n].to_plain() for n in (1, 2, 3)]
    for plain in plains:
        assert {k: v for k, v in plain.items() if k not in ("frame_id", "page_no")} == {
            k: v for k, v in plains[0].items() if k not in ("frame_id", "page_no")
        }
    assert [p["page_no"] for p in plains] == [1, 2, 3]
    assert len({p["frame_id"] for p in plains}) == 3
    assert _describe_all(data, (2,))[2] == frames[2]  # replay


def test_non_default_cropbox_extent_is_the_crop_not_the_media_box():
    data = build_sheet(90, crop_margins=(33.0, 41.0, 52.5, 17.25), origin=(120.0, 80.0), walls=False)
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    assert tuple(page.cropbox) != tuple(page.mediabox)
    desc = describe_bytes(data)
    assert desc.status is RAW
    media_w = page.mediabox.width
    assert media_w != desc.native_extent.width and abs(desc.native_extent.width - VH * 1.0) < 1e-3  # crop: swapped visual sheet
    assert abs(desc.native_extent.height - VW) < 1e-3
    assert abs((desc.mediabox_pdf_y_up[2] - desc.mediabox_pdf_y_up[0]) - (VH + 33.0 + 52.5)) < 1e-3
    assert desc.cropbox_pymupdf_y_down_from_mediabox_top is not None


@pytest.mark.parametrize("authored_for", [90, 180, 270])
def test_sideways_rotate_zero_never_carries_a_rotation_or_orientation_claim(authored_for):
    """Content authored for another rotation but declared /Rotate 0 is a rotation-0 frame, full stop."""
    data = build_sheet(0, sideways_from=authored_for)
    desc = describe_bytes(data)
    assert desc.status is RAW and desc.rotation == 0 and desc.rotation_reported == 0 and desc.rotate_entry == "0"
    clean = describe_bytes(build_sheet(0, vw=VH, vh=VW, walls=False) if authored_for in (90, 270) else build_sheet(0, walls=False))
    facts = lambda d: {k: v for k, v in d.to_plain().items() if k not in ("frame_id", "source_sha256", "revision")}
    assert facts(desc) == facts(clean)
    assert pf.PAGE_FRAME_NOTE_ROTATED_DISPLAY_DIFFERS_FROM_NATIVE not in desc.note_codes
    assert not [k for k in desc.to_plain() if any(w in k for w in ("orient", "text", "direction", "sideways"))]


# ---- documentation gate and report storage ------------------------------------------------------------
def test_promotion_gate_is_stated_in_the_module_docstring_and_the_report():
    doc = pf.__doc__ or ""
    assert "PROMOTION GATE" in doc and "real source PDF" in doc
    for rotation in ("90", "180", "270"):
        assert rotation in doc.split("PROMOTION GATE", 1)[1]
    assert "Second-hand" in doc or "second-hand" in doc
    assert "No production module may import it" in doc and "no measurement authority" in doc
    report = (ROOT / "docs" / "rotated_sheet_page_frame_architecture_report.md").read_text(encoding="utf-8")
    for heading in ("Observed repository behavior", "Inference", "Proposed change", "MUST NOT influence", "Approval record", "Implementation results (PR 1)", "Limitations"):
        assert heading in report, heading
    assert "real source PDF" in report and "second-hand" in report.lower()
    gate = (ROOT / "scripts" / "page_frame_wall_boundary_shadow_diff.py").read_text(encoding="utf-8")
    assert "PROMOTION GATE" in gate


# ---- import hygiene beyond plain import statements --------------------------------------------------------
def test_module_source_names_no_repo_module_and_uses_no_dynamic_import_machinery():
    tree = ast.parse((ROOT / "pb_page_frame_shadow.py").read_text(encoding="utf-8"))
    repo_modules = {p.stem for p in ROOT.glob("*.py")} - {"pb_migration_contracts", "pb_page_frame_shadow"}
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not (strings & repo_modules)
    assert not [s for s in strings if any(s == m or s.startswith(m + ".") for m in repo_modules)]
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not (called & {"__import__", "exec", "eval", "compile", "open", "getattr_static"})
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not (attrs & {"import_module", "reload", "find_spec", "spec_from_file_location", "exec_module"})
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "importlib" not in imported and "fitz" not in imported and "os" not in imported and "time" not in imported and "uuid" not in imported and "random" not in imported
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and any(isinstance(c, (ast.Import, ast.ImportFrom)) for c in ast.walk(n))]


def test_module_identity_inputs_contain_no_clock_random_or_path_sources():
    tree = ast.parse((ROOT / "pb_page_frame_shadow.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    forbidden = {"time", "datetime", "uuid", "random", "os", "Path", "pathlib", "hash", "id", "getpid", "__file__", "secrets", "platform", "socket"}
    assert not (names & forbidden), names & forbidden
    assert not (attrs & {"time", "now", "utcnow", "uuid4", "getpid", "random", "monotonic", "time_ns", "environ", "getcwd"}), attrs


# ---- native boundary helpers: every edge, both sides, non-square extent --------------------------------
_EDGE_CASES = [
    # (x, y, on_edge, contained) on a 400 x 300 box with tol 0.01
    (0.0, 150.0, True, True), (400.0, 150.0, True, True), (200.0, 0.0, True, True), (200.0, 300.0, True, True),
    (0.005, 150.0, True, True), (399.995, 150.0, True, True), (200.0, 0.005, True, True), (200.0, 299.995, True, True),
    (-0.005, 150.0, True, True), (400.005, 150.0, True, True), (200.0, -0.005, True, True), (200.0, 300.005, True, True),
    (0.1, 150.0, False, True), (399.9, 150.0, False, True), (200.0, 0.1, False, True), (200.0, 299.9, False, True),
    (-0.1, 150.0, False, False), (400.1, 150.0, False, False), (200.0, -0.1, False, False), (200.0, 300.1, False, False),
    (200.0, 350.0, False, False), (450.0, 150.0, False, False), (-50.0, 300.0, False, False), (400.0, 350.0, False, False),
    (0.0, 0.0, True, True), (400.0, 300.0, True, True), (0.0, 300.0, True, True), (400.0, 0.0, True, True),
    (200.0, 150.0, False, True),
]


@pytest.mark.parametrize("x,y,on_edge,contained", _EDGE_CASES)
def test_native_edge_and_containment_helpers_on_every_side(x, y, on_edge, contained):
    extent = pf.NativePageExtent(400, 300)
    point = pf.NativePoint(x, y)
    assert extent.point_on_edge(point, tol=0.01) is on_edge
    assert pf.native_point_on_edge(extent, point, tol=0.01) is on_edge
    assert extent.contains(point, tol=0.01) is contained
    assert pf.native_point_inside(extent, point, tol=0.01) is contained


def test_native_helpers_at_zero_tolerance_are_exact_and_reject_negative_tolerance():
    extent = pf.NativePageExtent(400, 300)
    assert extent.point_on_edge(pf.NativePoint(400, 150), tol=0.0) and extent.point_on_edge(pf.NativePoint(0, 150), tol=0.0)
    assert not extent.point_on_edge(pf.NativePoint(399.999, 150), tol=0.0)
    assert extent.contains(pf.NativePoint(400, 300), tol=0.0) and not extent.contains(pf.NativePoint(400.001, 300), tol=0.0)
    for bad in (-1e-9, -1.0, float("nan"), float("inf"), None, True):
        with pytest.raises((ValueError, TypeError)):
            extent.contains(pf.NativePoint(1, 1), tol=bad)  # type: ignore[arg-type]
        with pytest.raises((ValueError, TypeError)):
            extent.point_on_edge(pf.NativePoint(1, 1), tol=bad)  # type: ignore[arg-type]


def test_extent_types_reject_non_positive_non_finite_and_non_numeric_sizes():
    for make in (pf.NativePageExtent, pf.DisplayPageExtent):
        for bad in (0, 0.0, -0.0, -3, float("nan"), float("inf"), True, None, "5"):
            with pytest.raises((ValueError, TypeError)):
                make(bad, 5)
            with pytest.raises((ValueError, TypeError)):
                make(5, bad)


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_conversion_corners_map_to_the_expected_display_corners(rotation):
    """Independent, hand-derived corner table for a 300 x 200 native box (clockwise /Rotate)."""
    native = pf.NativePageExtent(300, 200)
    table = {
        0: {(0, 0): (0, 0), (300, 0): (300, 0), (0, 200): (0, 200), (300, 200): (300, 200)},
        90: {(0, 0): (200, 0), (300, 0): (200, 300), (0, 200): (0, 0), (300, 200): (0, 300)},
        180: {(0, 0): (300, 200), (300, 0): (0, 200), (0, 200): (300, 0), (300, 200): (0, 0)},
        270: {(0, 0): (0, 300), (300, 0): (0, 0), (0, 200): (200, 300), (300, 200): (200, 0)},
    }[rotation]
    display = pf.display_extent_for(native, rotation)
    for (x, y), (dx, dy) in table.items():
        shown = pf.native_to_display(pf.NativePoint(x, y), native_extent=native, rotation=rotation)
        assert (shown.x, shown.y) == (float(dx), float(dy)), (rotation, x, y)
        back = pf.display_to_native(shown, display_extent=display, rotation=rotation)
        assert (back.x, back.y) == (float(x), float(y))
    # corners of the display box are all hit (a bijection on the corner set)
    assert sorted(table.values()) == sorted({(0, 0), (display.width, 0), (0, display.height), (display.width, display.height)})


# ---- the derived float32 edge bound: upper side is pinned by the diff tests, lower side by this sweep ---------------
@pytest.mark.parametrize("size", [(841.89, 595.28), (3370.39, 2383.94), (1683.78, 1190.55)])
def test_edge_quantisation_bound_covers_cm_authored_edge_ends_with_margin(size):
    """Deterministic sweep: strokes authored through a cm scale end exactly on the page edge in the
    content stream; after the float32 parse/scale they land a few ulp off the edge. The derived bound must
    cover every one of them with at least a 3x margin over the worst observed deviation (so a bound that
    shrinks toward the observed worst case is caught) and must stay far below any real offset."""
    import random

    w, h = size
    rng = random.Random(99)
    doc = fitz.open()
    page = doc.new_page(width=w, height=h)
    strokes = []
    for _ in range(6000):
        s = 10 ** rng.uniform(-2.5, 0.6)
        y = 20 + (h - 40) * rng.random()
        strokes.append("q %.9g 0 0 %.9g 0 0 cm 1 w %.9g %.9g m %.9g %.9g l S Q\n" % (s, s, (w - 30) / s, (h - y) / s, w / s, (h - y) / s))
    xref = doc.get_new_xref()
    doc.update_object(xref, "<<>>")
    doc.update_stream(xref, "".join(strokes).encode())
    doc.xref_set_key(page.xref, "Contents", "%d 0 R" % xref)
    data = doc.tobytes(no_new_id=True)
    doc.close()
    desc = describe_bytes(data)
    assert desc.status is RAW
    extent = desc.native_extent
    bound = desc.edge_quantisation_pt
    ulp = pf.float32_ulp(max(w, h))
    worst, seen = 0.0, 0
    for drawing in fitz.open(stream=data, filetype="pdf")[0].get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            for point in (item[1], item[2]):
                deviation = abs(point.x - extent.width)
                if deviation < 0.05:  # the edge ends (the other end is 30 pt inside)
                    worst, seen = max(worst, deviation), seen + 1
                    assert extent.point_on_edge(pf.NativePoint(point.x, point.y), tol=bound)
    assert seen == 6000
    assert worst >= 1 * ulp  # the sweep really produces off-edge float32 ends (power check)
    assert bound >= 3 * worst
    assert bound < 0.001 * max(w, h)  # far below any real geometric offset (a 0.1% page-size band at most)
    # a point 2x the bound short of the edge is interior for the helper
    assert not extent.point_on_edge(pf.NativePoint(extent.width - 2 * bound, 100.0), tol=bound)


def test_non_coherent_frames_cannot_be_constructed_with_a_native_extent_or_a_coherent_frame_without_one():
    base = dict(document_id="doc-1", source_sha256="ab" * 32, revision=pf.revision_id_for("doc-1", "ab" * 32), page_no=1)
    native, display = pf.NativePageExtent(842, 595), pf.DisplayPageExtent(842, 595)
    common = dict(rotation=0, display_extent=display, **base)
    for status in (CONFLICT, ABSTAINED):
        with pytest.raises(ValueError):
            pf._make(status=status, reasons=["some_reason"], native_extent=native, **common)
    with pytest.raises(ValueError):
        pf._make(status=CONFLICT, reasons=[], **common)  # non-coherent needs a reason
    with pytest.raises(ValueError):
        pf._make(status=RAW, reasons=[], native_extent=None, **common)  # coherent needs both extents
    with pytest.raises(ValueError):
        pf._make(status=RAW, reasons=["x"], native_extent=native, **common)  # coherent carries no reason
    ok = pf._make(status=RAW, reasons=[], native_extent=native, **common)
    with pytest.raises(TypeError):
        dataclasses.replace(ok, status="raw")  # type: ignore[arg-type]  # the shared enum, not a string
    assert ok.is_coherent and ok.require_native_extent() is native
