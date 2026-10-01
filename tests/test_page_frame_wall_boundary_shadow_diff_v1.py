"""Shadow diff: page-frame descriptor vs the existing wall page-boundary consumer.

Drives the REAL, unmodified ingest -> wall-candidate pipeline read-only. Synthetic
fixtures only: no authority promotion on the strength of these results (see the
PROMOTION GATE in pb_page_frame_shadow).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import fitz
import pytest

import pb_physical_wall_candidate_authority as pw
import pb_page_frame_shadow as pf
from page_frame_test_support import DOC_ID, VH, VW, build_sheet, expected_faces
from pb_source_visibility_authority import SourceVisibilityProducer
from scripts import page_frame_wall_boundary_shadow_diff as D

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
ROTATIONS = (0, 90, 180, 270)
TRUTH = {"E": D.DECISION_BOUNDARY, "I": D.DECISION_INTERIOR}
COLUMNS = ("current_decision", "shadow_decision_default_tol", "shadow_decision_quantised_tol")
A4_INT = (842, 595)
A4 = (VW, VH)
A1 = (2383.94, 1683.78)


@lru_cache(maxsize=None)
def _run(rot, size=A4, uu=1, crop=None, origin=(0.0, 0.0), cm=None, sideways=None):
    vw, vh = size
    data = build_sheet(rot, vw=vw, vh=vh, user_unit=uu, crop_margins=crop, origin=origin, cm_scale=cm, sideways_from=sideways)
    page = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
    faces = expected_faces(sideways if sideways is not None else rot, vw, vh, uu)
    return json.dumps(D.label_page_report(page, faces))


def _report(*args, **kwargs):
    return json.loads(_run(*args, **kwargs))


def _ends(report):
    return [e for w in report["walls"] for e in w["ends"] if e["dangling"]]


def _wrong(report, column):
    return sorted(e["label"] for e in _ends(report) if e[column] != TRUTH[e["truth_class"]])


def _decisions(report, column):
    return {e["label"]: e[column] for e in _ends(report)}


def _family(label):
    return label.split("#")[0]


# ---- harness sanity ------------------------------------------------------------------------
@pytest.mark.parametrize("size", [A4_INT, A4])
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_pipeline_runs_and_private_calls_mirror_the_public_scope_result(rotation, size):
    report = _report(rotation, size=size)
    assert report["pipeline_status"] == "ok"
    assert report["cross_check"] == "match"  # per-wall private decisions reproduce the public reason code
    assert report["summary"]["walls"] == 20 and report["summary"]["dangling_ends"] == 40
    frame = report["frame"]
    assert frame["status"] == "raw" and frame["measurement_authority"] is False
    native, display = frame["native_extent"], frame["display_extent"]
    # current consumer sees the DISPLAY extent (rotated page.rect) ...
    assert (report["consumer_width"], report["consumer_height"]) == (display["width"], display["height"])
    # ... while the declared native extent is swapped at 90/270
    swapped = rotation in (90, 270)
    assert (native["width"], native["height"]) == ((display["height"], display["width"]) if swapped else (display["width"], display["height"]))
    for end in _ends(report):
        assert {"point", "current_decision", "shadow_decision_default_tol", "shadow_decision_quantised_tol",
                "diverges_default_tol", "diverges_quantised_tol", "label", "truth_class"} <= set(end)


@pytest.mark.parametrize("size", [A4_INT, A4])
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_shadow_decision_equals_truth_for_every_end_and_current_does_not_at_90_270(rotation, size):
    report = _report(rotation, size=size)
    assert _wrong(report, "shadow_decision_default_tol") == []
    assert _wrong(report, "shadow_decision_quantised_tol") == []
    wrong_current = _wrong(report, "current_decision")
    assert (len(wrong_current) == 6) if rotation in (90, 270) else (wrong_current == [])


@pytest.mark.parametrize("size", [A4_INT, A4])
def test_shadow_classification_is_rotation_equivalent_and_current_is_not(size):
    labelled = {rot: _report(rot, size=size) for rot in ROTATIONS}
    for column in ("shadow_decision_default_tol", "shadow_decision_quantised_tol"):
        result = D.rotation_equivalence(labelled, column=column)
        assert result["equivalent"] and result["labels"] == 40 and result["mismatches"] == []
    legacy = D.rotation_equivalence(labelled, column="current_decision")
    assert not legacy["equivalent"]
    assert len(legacy["mismatches"]) == 12  # 6 ends at 90 + 6 at 270
    assert {m["label"] for m in legacy["mismatches"]} == {e["label"] for r in (90, 270) for e in _ends(labelled[r]) if e["diverges_default_tol"]}


@pytest.mark.parametrize("size", [A4_INT, A4])
def test_expected_current_vs_shadow_divergences_at_90_and_270_and_none_at_0_and_180(size):
    expected = {
        90: {
            "touches_visual_bottom#f0:1": ("interior", "at_page_boundary"),
            "touches_visual_bottom#f1:1": ("interior", "at_page_boundary"),
            "touches_visual_left#f0:0": ("interior", "at_page_boundary"),
            "touches_visual_left#f1:0": ("interior", "at_page_boundary"),
            # look-alikes: native coordinate equals the legacy (rotated) boundary, interior on the sheet
            "lookalike_x_eq_vw_minus_vh#f0:0": ("at_page_boundary", "interior"),
            "lookalike_x_eq_vw_minus_vh#f1:0": ("at_page_boundary", "interior"),
        },
        270: {
            "touches_visual_right#f0:1": ("interior", "at_page_boundary"),
            "touches_visual_right#f1:1": ("interior", "at_page_boundary"),
            "touches_visual_top#f0:0": ("interior", "at_page_boundary"),
            "touches_visual_top#f1:0": ("interior", "at_page_boundary"),
            "lookalike_x_eq_vh#f0:0": ("at_page_boundary", "interior"),
            "lookalike_x_eq_vh#f1:0": ("at_page_boundary", "interior"),
        },
        0: {},
        180: {},
    }
    for rotation, want in expected.items():
        report = _report(rotation, size=size)
        got = {e["label"]: (e["current_decision"], e["shadow_decision_default_tol"]) for e in _ends(report) if e["diverges_default_tol"]}
        assert got == want, rotation
        # the divergence flag and the decisions are consistent for every end
        for e in _ends(report):
            assert e["diverges_default_tol"] == (e["current_decision"] != e["shadow_decision_default_tol"])
            assert e["diverges_quantised_tol"] == (e["current_decision"] != e["shadow_decision_quantised_tol"])


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_interior_end_negatives_stay_interior_in_shadow_at_every_rotation_and_in_current_too(rotation):
    report = _report(rotation, size=A4)
    interior_families = {"interior_h", "interior_v", "near_edge_top_4pt", "near_edge_right_4pt"}
    rows = [e for e in _ends(report) if _family(e["label"]) in interior_families]
    assert len(rows) == 4 * 2 * 2  # 4 walls x 2 faces x 2 ends
    for e in rows:
        assert e["truth_class"] == "I"
        assert e["current_decision"] == e["shadow_decision_default_tol"] == e["shadow_decision_quantised_tol"] == D.DECISION_INTERIOR
    # near-edge ends stop 4 pt short: the quantisation bound (~1e-3 pt) must not reach them
    assert max(e["shadow_decision_quantised_tol"] == D.DECISION_BOUNDARY for e in rows) is False
    # the interior end of every edge-touching wall is also interior everywhere
    for e in _ends(report):
        if e["truth_class"] == "I":
            assert e["shadow_decision_default_tol"] == e["shadow_decision_quantised_tol"] == D.DECISION_INTERIOR


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_lookalikes_are_interior_in_shadow_and_flip_from_cropped_to_interior_at_90_270(rotation):
    report = _report(rotation, size=A4)
    looks = [e for e in _ends(report) if _family(e["label"]).startswith("lookalike")]
    assert looks and all(e["truth_class"] == "I" for e in looks)
    assert all(e["shadow_decision_default_tol"] == D.DECISION_INTERIOR for e in looks)
    flipped = [e for e in looks if e["current_decision"] == D.DECISION_BOUNDARY]
    assert len(flipped) == (2 if rotation in (90, 270) else 0)
    for e in flipped:
        assert (e["current_decision"], e["shadow_decision_default_tol"]) == (D.DECISION_BOUNDARY, D.DECISION_INTERIOR)


def test_wall_level_reason_reproduces_the_consumer_and_shadow_uses_declared_extent():
    report = _report(90, size=A4)
    by_label = {}
    for wall in report["walls"]:
        for e in wall["ends"]:
            if e["dangling"]:
                by_label[e["label"]] = wall
    wall = by_label["touches_visual_left#f0:0"]  # a true edge wall that the current consumer misses at 90
    assert wall["current_wall_reason"] is None
    assert wall["shadow_wall_reason_default_tol"] == pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
    look = by_label["lookalike_x_eq_vw_minus_vh#f0:0"]
    assert look["current_wall_reason"] == pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
    assert look["shadow_wall_reason_default_tol"] is None


# ---- UserUnit, CropBox ----------------------------------------------------------------------
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_user_unit_two_with_offset_inset_cropbox(rotation):
    kwargs = dict(size=A4, uu=2, crop=(10.5, 20.25, 15.0, 5.75), origin=(100.0, 50.0))
    report = _report(rotation, **kwargs)
    assert report["pipeline_status"] == "ok" and report["frame"]["status"] == "raw"
    assert _wrong(report, "shadow_decision_quantised_tol") == []
    assert _wrong(report, "shadow_decision_default_tol") == []
    native = report["frame"]["native_extent"]
    swapped = rotation in (90, 270)
    assert abs(native["width"] - (VH if swapped else VW) * 2) < 1e-3
    assert (len(_wrong(report, "current_decision")) == 6) == swapped


def test_user_unit_two_shadow_is_rotation_equivalent():
    kwargs = dict(size=A4, uu=2, crop=(10.5, 20.25, 15.0, 5.75), origin=(100.0, 50.0))
    labelled = {rot: _report(rot, **kwargs) for rot in ROTATIONS}
    # labels are shared across rotations and UserUnit scaling is applied to native coordinates only
    for column in ("shadow_decision_default_tol", "shadow_decision_quantised_tol"):
        assert D.rotation_equivalence(labelled, column=column)["equivalent"]


# ---- cm-authored edge ends: the extent fix alone does not cure float32 quantisation --------------
@pytest.mark.parametrize("rotation", ROTATIONS)
@pytest.mark.parametrize("size,scale", [(A4, 0.1), (A1, 0.1), (A4_INT, 0.3527777)])
def test_cm_authored_edge_ends_need_the_float32_bound_not_just_the_right_extent(rotation, size, scale):
    report = _report(rotation, size=size, cm=scale)
    assert report["pipeline_status"] == "ok"
    # extent + derived quantisation bound: every end, edge and interior, is classified correctly
    assert _wrong(report, "shadow_decision_quantised_tol") == []
    assert report["frame"]["edge_quantisation_pt"] > 1e-6
    # the bound is tiny next to any real offset: interior ends 4 pt short are untouched (asserted via `_wrong` above)
    assert report["frame"]["edge_quantisation_pt"] < 0.01


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_extent_alone_at_the_consumer_tolerance_still_misses_cm_authored_ends_even_at_rotation_zero(rotation):
    """Pre-existing limitation independent of rotation: 1e-6 is below float32 rounding of cm-authored ends."""
    report = _report(rotation, size=A4, cm=0.1)
    missed = _wrong(report, "shadow_decision_default_tol")
    assert missed, "expected the documented float32 miss; if this now passes the fixture no longer exercises it"
    assert all(e["truth_class"] == "E" for e in _ends(report) if e["label"] in missed)  # false negatives only (fail-open)
    assert _wrong(report, "shadow_decision_quantised_tol") == []


# ---- sideways rotate-0 adversarial negative -------------------------------------------------------------
def test_sideways_rotate_zero_sheet_classifies_like_the_genuinely_rotated_sheet_and_frame_is_unchanged():
    rotated = _report(90, size=A4)
    sideways = _report(0, size=A4, sideways=90)
    assert sideways["frame"]["rotation"] == 0 and rotated["frame"]["rotation"] == 90
    # rotation metadata is 0 and consistent for the sideways sheet: the current consumer is self-consistent ...
    assert _wrong(sideways, "current_decision") == []
    assert sideways["summary"]["divergent_default_tol"] == 0
    # ... and every native end gets the same shadow decision as on the /Rotate 90 sheet (same raw content)
    for column in ("shadow_decision_default_tol", "shadow_decision_quantised_tol"):
        assert _decisions(sideways, column) == _decisions(rotated, column)
    assert [e["point"] for e in _ends(sideways)] == [e["point"] for e in _ends(rotated)]
    # no orientation claim exists anywhere in the frame
    assert not [k for k in sideways["frame"] if "orient" in k or "direction" in k or "text" in k]


# ---- invariances -------------------------------------------------------------------------------------------
def test_input_order_invariance_of_labelled_decisions():
    page = json.loads(_run(90, size=A4))
    reversed_page = json.loads(json.dumps(page))
    reversed_page["walls"] = list(reversed(reversed_page["walls"]))
    for wall in reversed_page["walls"]:
        wall["ends"] = list(reversed(wall["ends"]))
    for column in COLUMNS:
        assert _decisions(page, column) == _decisions(reversed_page, column)
    assert D.rotation_equivalence({90: page}, column="shadow_decision_default_tol") == D.rotation_equivalence(
        {90: reversed_page}, column="shadow_decision_default_tol"
    )


def test_label_matching_fails_closed_on_ambiguity_and_absence():
    page = json.loads(_run(0, size=A4))
    # strip labels to get a raw report
    raw = json.loads(json.dumps(page))
    faces = expected_faces(0)
    first = next(iter(faces))
    duplicated = dict(faces)
    duplicated["dup"] = faces[first]  # two expected ends claim the same coordinates
    with pytest.raises(ValueError):
        D.label_page_report(raw, duplicated)
    del duplicated["dup"]
    del duplicated[first]
    with pytest.raises(ValueError):
        D.label_page_report(raw, duplicated)  # a wall end matches no expected end


def test_replay_is_deterministic_and_does_not_mutate_inputs_or_the_consumer():
    data = build_sheet(90)
    snapshot = bytes(data)
    predicate, tol = pw._on_rect_boundary, pw._BOUNDARY_COORD_TOL
    first = D.render_json(D.run_shadow_diff(data, document_id=DOC_ID))
    second = D.render_json(D.run_shadow_diff(data, document_id=DOC_ID))
    assert first == second and data == snapshot
    assert pw._on_rect_boundary is predicate and pw._BOUNDARY_COORD_TOL == tol == 1e-6
    report = json.loads(first)
    assert report["shadow_only"] is True and report["measurement_authority"] is False and report["commercial_output_changed"] is False
    assert report["source_sha256"] == hashlib.sha256(data).hexdigest()


def test_frame_revision_matches_the_source_producers_definition():
    data = build_sheet(180)
    src = SourceVisibilityProducer(producer_method="page_frame_revision_parity", producer_version="1")
    pub = src.ingest_native_pdf_bytes(document_id=DOC_ID, source_bytes=data, source_locator="memory://parity")
    assert pub.revision.revision_id == pf.revision_id_for(DOC_ID, hashlib.sha256(data).hexdigest())
    assert pub.revision.source_sha256 == hashlib.sha256(data).hexdigest()


def _mixed_rotation_document() -> bytes:
    out = fitz.open()
    for rotation in ROTATIONS:
        src = fitz.open(stream=build_sheet(rotation), filetype="pdf")
        out.insert_pdf(src)
        src.close()
    data = out.tobytes(no_new_id=True)
    out.close()
    return data


def test_mixed_rotation_document_gives_per_page_frames_matching_the_single_page_results():
    data = _mixed_rotation_document()
    doc = fitz.open(stream=data, filetype="pdf")
    assert [p.rotation for p in doc] == list(ROTATIONS)
    report = D.run_shadow_diff(data, document_id=DOC_ID)
    assert [p["page_no"] for p in report["pages"]] == [1, 2, 3, 4]
    for page, rotation in zip(report["pages"], ROTATIONS):
        assert page["pipeline_status"] == "ok" and page["cross_check"] == "match"
        assert page["frame"]["rotation"] == rotation and page["frame"]["page_no"] == page["page_no"]
        single = _report(rotation, size=A4)
        assert page["summary"] == single["summary"]
        # wall ids (hence row order) depend on the page within the document: compare as sorted sets
        assert sorted((tuple(e["point"]), e["shadow_decision_quantised_tol"]) for e in _ends(page)) == sorted(
            (tuple(e["point"]), e["shadow_decision_quantised_tol"]) for e in _ends(single)
        )
    assert len({p["frame"]["frame_id"] for p in report["pages"]}) == 4


def test_page_selection_and_bad_input():
    data = _mixed_rotation_document()
    report = D.run_shadow_diff(data, document_id=DOC_ID, page_numbers=[3, 9])
    assert [p["page_no"] for p in report["pages"]] == [3]
    for bad in (b"", None, "text"):
        with pytest.raises(ValueError):
            D.run_shadow_diff(bad, document_id=DOC_ID)  # type: ignore[arg-type]


# ---- CLI ----------------------------------------------------------------------------------------------------------
def _cli(pdf: Path, *extra: str, seed: str = "0"):
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "page_frame_wall_boundary_shadow_diff.py"), "--pdf", str(pdf), *extra],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )


def test_cli_prints_deterministic_json_and_writes_nothing(tmp_path):
    pdf = tmp_path / "some_project_name_rev_b.pdf"  # the file name must never reach the output
    data = build_sheet(270)
    pdf.write_bytes(data)
    before = sorted(p.name for p in tmp_path.iterdir())
    outputs = [_cli(pdf, "--document-id", DOC_ID, seed=seed) for seed in ("0", "1", "999")]
    assert all(proc.returncode == 0 for proc in outputs), [p.stderr[-500:] for p in outputs]
    assert len({proc.stdout for proc in outputs}) == 1
    report = json.loads(outputs[0].stdout)
    assert report["document_id"] == DOC_ID and "some_project_name" not in outputs[0].stdout
    assert report["pages"][0]["frame"]["rotation"] == 270
    assert report["pages"][0]["summary"] == _report(270, size=A4)["summary"]
    assert sorted(p.name for p in tmp_path.iterdir()) == before and pdf.read_bytes() == data
    assert outputs[0].stdout == D.render_json(D.run_shadow_diff(data, document_id=DOC_ID)) + "\n"


def test_cli_requires_an_explicit_document_id(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(build_sheet(0))
    proc = _cli(pdf)
    assert proc.returncode != 0 and "--document-id" in proc.stderr
    proc = _cli(pdf, "--document-id", DOC_ID, "--pages", "1")
    assert proc.returncode == 0 and [p["page_no"] for p in json.loads(proc.stdout)["pages"]] == [1]


# ---- shadow proof: nothing the pipeline produces depends on the new module being loaded ------------------------------
PROOF = r"""
import sys, json, hashlib
mode, pdfs = sys.argv[1], sys.argv[2:]
if mode == "with":
    import pb_page_frame_shadow  # imported first, before any production module
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector
out = []
for path in pdfs:
    out.append([p.to_dict() for p in GenericPlanReaderExtractor().extract_from_pdf(path)])
    data = open(path, "rb").read()
    src = SourceVisibilityProducer(producer_method="shadow_proof", producer_version="1")
    pub = src.ingest_native_pdf_bytes(document_id="proof-doc", source_bytes=data, source_locator="memory://proof")
    auth = PhysicalWallCandidateProducer.from_source_visibility_producer(src).authority()
    res = auth.resolve_scope(PhysicalWallCandidateSelector(
        document_id="proof-doc", revision_id=pub.revision.revision_id, source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id, page_id="1", decision_scope_id="wall-source:page-1"))
    out.append([res.scope_complete, sorted(map(str, res.reason_codes)), sorted(r.wall_candidate_id for r in res.records)])
blob = json.dumps(out, sort_keys=True, default=str)
print("PROOF", hashlib.sha256(blob.encode()).hexdigest(), len(out), "pb_page_frame_shadow" in sys.modules)
"""


def test_shadow_proof_extract_and_candidate_outputs_are_identical_with_and_without_the_module(tmp_path):
    paths = []
    for rotation in (0, 90):  # rot-0 control and a genuinely rotated synthetic page
        path = tmp_path / f"sheet_{rotation}.pdf"
        path.write_bytes(build_sheet(rotation))
        paths.append(str(path))

    def run(mode):
        env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT)}
        proc = subprocess.run([sys.executable, "-c", PROOF, mode, *paths], capture_output=True, text=True, env=env, cwd=str(ROOT))
        assert proc.returncode == 0, proc.stderr[-800:]
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith("PROOF ")][-1].split()
        return line[1], line[2], line[3]

    with_hash, with_n, with_loaded = run("with")
    without_hash, without_n, without_loaded = run("without")
    assert with_loaded == "True" and without_loaded == "False"  # the two fresh interpreters really differ in that one respect
    assert with_n == without_n == "4"
    assert with_hash == without_hash
