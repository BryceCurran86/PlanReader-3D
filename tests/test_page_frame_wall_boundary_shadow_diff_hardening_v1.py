"""Mutation-hardening tests for the page-frame wall-boundary shadow diff (shadow-only).

Pins behaviour that deliberate breakages of the diff script, found during independent
mutation testing, previously slipped through: a tolerance band that is wider than the
float32 bound (ends just short of the edge must stay interior), absolute summary counts,
a cross-check that can actually report a mismatch, pipeline-error reporting, ordering,
and the label / equivalence helpers' negative paths. Synthetic fixtures only.
"""
from __future__ import annotations

import json
from functools import lru_cache
from unittest import mock

import pytest

import page_frame_test_support as support
import pb_physical_wall_candidate_authority as pw
from page_frame_test_support import DOC_ID, VH, VW, build_sheet, expected_faces
from scripts import page_frame_wall_boundary_shadow_diff as D

ROTATIONS = (0, 90, 180, 270)
TRUTH = {"E": D.DECISION_BOUNDARY, "I": D.DECISION_INTERIOR}
SHORT_BY = (0.0, 0.002, 0.05, 0.25, 1.0)  # how far short of the visual page edge an end stops (pt)


def fine_specs(vw=VW, vh=VH):
    """Walls whose end stops d points short of each visual page edge; d == 0 touches the edge."""
    out = []
    for i, d in enumerate(SHORT_BY):
        x, y = 150 + 100 * i, 200 + 50 * i
        first = "E" if d == 0.0 else "I"
        out.append((f"top_d{d}", (x, d, x, d + 140), first + "I"))
        out.append((f"bottom_d{d}", (x, vh - 140 - d, x, vh - d), "I" + first))
        out.append((f"left_d{d}", (d, y, d + 140, y), first + "I"))
        out.append((f"right_d{d}", (vw - 140 - d, y, vw - d, y), "I" + first))
    return out


def interior_only_specs(vw=VW, vh=VH):
    return [("interior_h", (330, 420, 470, 420), "II"), ("interior_v", (520, 180, 520, 320), "II")]


@lru_cache(maxsize=None)
def _run_with(spec_name, rotation):
    specs = {"fine": fine_specs, "interior": interior_only_specs}[spec_name]
    with mock.patch.object(support, "wall_specs", specs):
        data = build_sheet(rotation)
        page = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
        return json.dumps(D.label_page_report(page, expected_faces(rotation)))


def _fine(rotation):
    return json.loads(_run_with("fine", rotation))


def _ends(report):
    return [e for w in report["walls"] for e in w["ends"] if e["dangling"]]


def _wrong(report, column):
    return sorted(e["label"] for e in _ends(report) if e[column] != TRUTH[e["truth_class"]])


# ---- the tolerance band is the float32 bound, not a generous margin ---------------------------------
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_ends_a_few_thousandths_short_of_the_edge_stay_interior_and_touching_ends_stay_boundary(rotation):
    report = _fine(rotation)
    assert report["pipeline_status"] == "ok" and report["cross_check"] == "match"
    assert report["summary"]["walls"] == 40 and report["summary"]["dangling_ends"] == 80
    ends = _ends(report)
    assert {e["truth_class"] for e in ends} == {"E", "I"}
    assert sum(1 for e in ends if e["truth_class"] == "E") == 8  # the d == 0 walls only
    bound = report["frame"]["edge_quantisation_pt"]
    # the smallest offset under test is several times the derived bound, so it is unambiguous
    assert 3 * bound < min(d for d in SHORT_BY if d > 0)
    for column in ("shadow_decision_default_tol", "shadow_decision_quantised_tol"):
        assert _wrong(report, column) == [], column
    # every end that stops short by any d > 0 is interior in both shadow columns
    short = [e for e in ends if e["truth_class"] == "I"]
    assert all(e["shadow_decision_quantised_tol"] == D.DECISION_INTERIOR == e["shadow_decision_default_tol"] for e in short)


def test_fine_offset_shadow_is_rotation_equivalent():
    labelled = {rot: _fine(rot) for rot in ROTATIONS}
    for column in ("shadow_decision_default_tol", "shadow_decision_quantised_tol"):
        result = D.rotation_equivalence(labelled, column=column)
        assert result["equivalent"] and result["labels"] == 80, column


# ---- absolute summary counts (independent of the summary code) ---------------------------------------------
def _standard(rotation):
    data = build_sheet(rotation)
    page = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
    return D.label_page_report(page, expected_faces(rotation))


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_summary_counts_equal_an_independent_recount_and_known_absolutes(rotation):
    report = _standard(rotation)
    ends = _ends(report)
    summary = report["summary"]
    truth_edge = sum(1 for e in ends if e["truth_class"] == "E")
    assert truth_edge == 8 and len(ends) == 40
    assert summary["dangling_ends"] == 40 and summary["walls"] == 20
    assert summary["shadow_default_tol_at_boundary"] == 8
    assert summary["shadow_quantised_tol_at_boundary"] == 8
    assert summary["current_at_boundary"] == sum(1 for e in ends if e["current_decision"] == D.DECISION_BOUNDARY)
    assert summary["divergent_default_tol"] == sum(1 for e in ends if e["current_decision"] != e["shadow_decision_default_tol"])
    assert summary["divergent_quantised_tol"] == sum(1 for e in ends if e["current_decision"] != e["shadow_decision_quantised_tol"])
    if rotation in (90, 270):  # 4 true edge ends missed, 2 look-alike interior ends cropped
        assert summary["current_at_boundary"] == 6
        assert summary["divergent_default_tol"] == summary["divergent_quantised_tol"] == 6
    else:
        assert summary["current_at_boundary"] == 8
        assert summary["divergent_default_tol"] == summary["divergent_quantised_tol"] == 0


# ---- the public-result cross-check can really report a mismatch ---------------------------------------------
class _PwProxy:
    """Stands in for the consumer module inside the diff script only (the pipeline keeps the real one)."""

    def __init__(self, **overrides):
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(pw, name)


def test_cross_check_reports_mismatch_when_private_decisions_disagree_with_the_public_reason(monkeypatch):
    data = build_sheet(0)
    honest = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
    assert honest["cross_check"] == "match"
    assert pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY in honest["scope_reason_codes"]
    # private decisions say "never cropped" while the public result says cropped
    monkeypatch.setattr(D, "pw", _PwProxy(_scope_boundary_reason_from_viewports=lambda *a, **k: None))
    deaf = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
    assert deaf["cross_check"] == "mismatch"
    # and the opposite direction: private decisions say cropped, the public result (interior-only sheet) does not
    monkeypatch.setattr(D, "pw", pw)
    with mock.patch.object(support, "wall_specs", interior_only_specs):
        interior_data = build_sheet(0)
    quiet = D.run_shadow_diff(interior_data, document_id=DOC_ID)["pages"][0]
    assert quiet["cross_check"] == "match"
    assert pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY not in quiet["scope_reason_codes"]
    monkeypatch.setattr(
        D,
        "pw",
        _PwProxy(_scope_boundary_reason_from_viewports=lambda *a, **k: pw.PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY),
    )
    loud = D.run_shadow_diff(interior_data, document_id=DOC_ID)["pages"][0]
    assert loud["cross_check"] == "mismatch"


def test_pipeline_failure_is_reported_not_raised_and_the_frame_is_kept(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(D, "pw", _PwProxy(_source_page_segments=boom))
    report = D.run_shadow_diff(build_sheet(90), document_id=DOC_ID)
    page = report["pages"][0]
    assert page["pipeline_status"] == "pipeline_error:RuntimeError"
    assert page["walls"] == [] and page["cross_check"] == "not_run"
    assert page["consumer_width"] is None and page["consumer_height"] is None and page["scope_complete"] is None
    assert page["frame"]["status"] == "raw" and page["frame"]["rotation"] == 90  # the descriptor is independent of the consumer
    assert page["summary"] == {
        "dangling_ends": 0,
        "current_at_boundary": 0,
        "shadow_default_tol_at_boundary": 0,
        "shadow_quantised_tol_at_boundary": 0,
        "divergent_default_tol": 0,
        "divergent_quantised_tol": 0,
        "walls": 0,
    }
    assert report["measurement_authority"] is False and report["commercial_output_changed"] is False


# ---- ownership, ordering, document-level flags -------------------------------------------------------------------
def test_frame_ownership_comes_from_the_ingested_revision_and_walls_are_ordered():
    data = build_sheet(270)
    report = D.run_shadow_diff(data, document_id=DOC_ID)
    page = report["pages"][0]
    frame = page["frame"]
    assert frame["document_id"] == DOC_ID == report["document_id"]
    assert frame["revision"] == report["revision"] and frame["source_sha256"] == report["source_sha256"]
    assert frame["page_no"] == page["page_no"] == 1
    ids = [w["wall_candidate_id"] for w in page["walls"]]
    assert len(ids) == 20 and ids == sorted(ids) and len(set(ids)) == len(ids)
    assert report["shadow_only"] is True and report["measurement_authority"] is False and report["commercial_output_changed"] is False
    assert report["schema_version"] == D.SHADOW_DIFF_SCHEMA_VERSION
    other = D.run_shadow_diff(data, document_id="another-doc")["pages"][0]["frame"]
    assert other["document_id"] == "another-doc" and other["frame_id"] != frame["frame_id"]


def test_dangling_bookkeeping_rows_carry_no_decisions_for_non_dangling_ends():
    report = _standard(90)
    non_dangling = [e for w in report["walls"] for e in w["ends"] if not e["dangling"]]
    for e in non_dangling:
        assert e["current_decision"] is None and e["shadow_decision_default_tol"] is None and e["shadow_decision_quantised_tol"] is None
        assert e["diverges_default_tol"] is None and e["diverges_quantised_tol"] is None
    dangling = [e for w in report["walls"] for e in w["ends"] if e["dangling"]]
    assert dangling and all(e["current_decision"] in TRUTH.values() for e in dangling)
    assert len(dangling) + len(non_dangling) == 2 * report["summary"]["walls"]


# ---- negative paths of the label / equivalence helpers -----------------------------------------------------------
def _stub(decisions):
    return {"walls": [{"ends": [{"label": k, "dangling": True, "decision": v} for k, v in decisions.items()]}]}


def test_rotation_equivalence_detects_disagreement_and_missing_labels():
    agree = D.rotation_equivalence({0: _stub({"a": "x", "b": "y"}), 90: _stub({"a": "x", "b": "y"})}, column="decision")
    assert agree["equivalent"] and agree["labels"] == 2 and agree["mismatches"] == []
    differ = D.rotation_equivalence({0: _stub({"a": "x"}), 90: _stub({"a": "y"}), 180: _stub({"a": "x"})}, column="decision")
    assert not differ["equivalent"] and differ["mismatches"][0]["label"] == "a"
    assert differ["mismatches"][0]["decisions"] == {"0": "x", "90": "y", "180": "x"}
    missing = D.rotation_equivalence({0: _stub({"a": "x", "b": "y"}), 90: _stub({"a": "x"})}, column="decision")
    assert not missing["equivalent"] and missing["mismatches"][0]["decisions"] == {"0": "y", "90": "absent"}
    # a non-dangling end is not compared
    mixed = {"walls": [{"ends": [{"label": "a", "dangling": True, "decision": "x"}, {"label": "z", "dangling": False, "decision": "q"}]}]}
    only = {"walls": [{"ends": [{"label": "a", "dangling": True, "decision": "x"}]}]}
    assert D.rotation_equivalence({0: mixed, 90: only}, column="decision")["equivalent"]


def test_label_page_report_rejects_ambiguous_and_unmatched_ends_and_does_not_mutate_its_input():
    page = {"walls": [{"ends": [{"point": [10.0, 10.0], "dangling": True}]}]}
    before = json.dumps(page, sort_keys=True)
    ok = D.label_page_report(page, {"w": ((10.0, 10.0), (500.0, 500.0), "EI")})
    assert ok["walls"][0]["ends"][0]["label"] == "w:0" and ok["walls"][0]["ends"][0]["truth_class"] == "E"
    assert json.dumps(page, sort_keys=True) == before
    with pytest.raises(ValueError):  # two expected ends claim the same coordinates
        D.label_page_report(page, {"w": ((10.0, 10.0), (10.0, 10.0), "EI")})
    with pytest.raises(ValueError):  # nothing expected there: no nearest-match fallback
        D.label_page_report(page, {"w": ((10.5, 10.0), (500.0, 500.0), "EI")})
    with pytest.raises(ValueError):
        D.label_page_report(page, {})


# ---- summary counts where the two shadow columns differ (cm-authored edge ends) --------------------------------------
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_summary_counts_when_default_and_quantised_columns_disagree(rotation):
    data = build_sheet(rotation, cm_scale=0.1)
    page = D.label_page_report(D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0], expected_faces(rotation))
    ends = _ends(page)
    summary = page["summary"]
    assert _wrong(page, "shadow_decision_quantised_tol") == []
    assert _wrong(page, "shadow_decision_default_tol") != []  # the float32 miss this fixture exists to exercise
    assert summary["shadow_quantised_tol_at_boundary"] == 8
    assert summary["shadow_default_tol_at_boundary"] == sum(1 for e in ends if e["shadow_decision_default_tol"] == D.DECISION_BOUNDARY)
    assert summary["shadow_default_tol_at_boundary"] < summary["shadow_quantised_tol_at_boundary"]
    assert summary["current_at_boundary"] == sum(1 for e in ends if e["current_decision"] == D.DECISION_BOUNDARY)
    assert summary["divergent_default_tol"] == sum(1 for e in ends if e["diverges_default_tol"])
    assert summary["divergent_quantised_tol"] == sum(1 for e in ends if e["diverges_quantised_tol"])
    assert summary["divergent_default_tol"] != summary["divergent_quantised_tol"]
    for e in ends:
        assert e["diverges_default_tol"] == (e["current_decision"] != e["shadow_decision_default_tol"])
        assert e["diverges_quantised_tol"] == (e["current_decision"] != e["shadow_decision_quantised_tol"])


# ---- junction (non-dangling) ends are reported but carry no boundary decision -----------------------------------------------
def junction_specs(vw=VW, vh=VH):
    """A T junction (horizontal wall ends on a vertical wall's face) plus one genuine page-edge wall."""
    return [("tee_h", (330, 300, 494, 300), "II"), ("tee_v", (500, 288, 500, 450), "II"), ("edge_h", (0, 120, 140, 120), "EI")]


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_junction_ends_are_reported_without_boundary_decisions_and_the_cross_check_still_matches(rotation):
    with mock.patch.object(support, "wall_specs", junction_specs):
        data = build_sheet(rotation)
        page = D.label_page_report(D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0], expected_faces(rotation))
    assert page["pipeline_status"] == "ok" and page["cross_check"] == "match"
    every = [e for w in page["walls"] for e in w["ends"]]
    non_dangling = [e for e in every if not e["dangling"]]
    assert len(every) == 12 and len(non_dangling) == 2 and page["summary"]["dangling_ends"] == 10
    assert {e["label"].split("#")[0] for e in non_dangling} == {"tee_h"}
    for e in non_dangling:
        assert e["current_decision"] is None and e["shadow_decision_default_tol"] is None and e["shadow_decision_quantised_tol"] is None
        assert e["diverges_default_tol"] is None and e["diverges_quantised_tol"] is None
    assert _wrong(page, "shadow_decision_quantised_tol") == []
    assert page["summary"]["shadow_quantised_tol_at_boundary"] == 2  # the two faces of the edge wall


# ---- the script passes the descriptor's facts through unmodified -----------------------------------------------------------------
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_shadow_columns_call_the_existing_predicate_with_exactly_the_declared_extent_and_bound(rotation, monkeypatch):
    calls = []

    def recorder(point, **kwargs):
        calls.append(dict(kwargs))
        return pw._on_rect_boundary(point, **kwargs)

    monkeypatch.setattr(D, "pw", _PwProxy(_on_rect_boundary=recorder))
    page = D.run_shadow_diff(build_sheet(rotation, cm_scale=0.1), document_id=DOC_ID)["pages"][0]
    frame, native = page["frame"], page["frame"]["native_extent"]
    bound = frame["edge_quantisation_pt"]
    consumer = (page["consumer_width"], page["consumer_height"])
    shadow = (native["width"], native["height"])
    assert len(calls) == 3 * page["summary"]["dangling_ends"]  # current, shadow default, shadow quantised per dangling end
    assert all(c["x0"] == 0.0 and c["y0"] == 0.0 for c in calls)
    by_kind = {"current": [], "default": [], "quantised": []}
    for c in calls:
        extent = (c["x1"], c["y1"])
        if "tol" in c:
            assert c["tol"] == bound and extent == shadow  # the derived bound, not scaled, not rounded
            by_kind["quantised"].append(c)
        elif extent == consumer and extent != shadow:
            by_kind["current"].append(c)
        else:
            assert extent == shadow  # default tolerance with the declared native extent
            by_kind["default"].append(c)
    n = page["summary"]["dangling_ends"]
    if consumer != shadow:  # 90 / 270: the consumer still sees the rotated extent
        assert len(by_kind["current"]) == n and len(by_kind["default"]) == n and len(by_kind["quantised"]) == n
    else:
        assert len(by_kind["quantised"]) == n and len(by_kind["current"]) + len(by_kind["default"]) == 2 * n
    assert bound > 1e-6 and (native["width"], native["height"]) != (0.0, 0.0)


def _four_page_document() -> bytes:
    import fitz

    out = fitz.open()
    for rotation in ROTATIONS:
        src = fitz.open(stream=build_sheet(rotation), filetype="pdf")
        out.insert_pdf(src)
        src.close()
    data = out.tobytes(no_new_id=True)
    out.close()
    return data


def test_page_numbers_are_deduplicated_sorted_and_clipped_and_each_page_keeps_its_own_identity():
    data = _four_page_document()
    report = D.run_shadow_diff(data, document_id=DOC_ID, page_numbers=[3, 1, 3, 0, -2, 9])
    assert [p["page_no"] for p in report["pages"]] == [1, 3]
    assert [p["frame"]["page_no"] for p in report["pages"]] == [1, 3]
    assert [p["frame"]["rotation"] for p in report["pages"]] == [0, 180]
    full = D.run_shadow_diff(data, document_id=DOC_ID)
    assert [p["page_no"] for p in full["pages"]] == [1, 2, 3, 4]
    # the subset report equals the matching pages of the full report (page selection is addressing only)
    assert report["pages"] == [full["pages"][0], full["pages"][2]]
    assert report["revision"] == full["revision"] and report["source_sha256"] == full["source_sha256"]
    # every page was decided by its own rotation's native extent, not by another page's
    ext = [(p["frame"]["native_extent"]["width"], p["frame"]["native_extent"]["height"]) for p in full["pages"]]
    assert ext[0] == ext[2] and ext[1] == ext[3] and ext[0] != ext[1]
    assert [(p["consumer_width"], p["consumer_height"]) for p in full["pages"]] == [ext[0]] * 4  # consumer sees the display extent everywhere


# ---- cm-authored sheets: only the bound-carrying column is per-label rotation-equivalent --------------------
@lru_cache(maxsize=None)
def _cm_labelled(vw, vh, cm, rotation):
    data = build_sheet(rotation, vw=vw, vh=vh, cm_scale=cm)
    page = D.run_shadow_diff(data, document_id=DOC_ID)["pages"][0]
    return json.dumps(D.label_page_report(page, expected_faces(rotation, vw, vh)))


@pytest.mark.parametrize("vw,vh,cm", [(VW, VH, 0.1), (2383.94, 1683.78, 0.1), (842.0, 595.0, 0.3527777)])
def test_cm_authored_sheets_extent_plus_bound_column_is_per_label_rotation_equivalent_and_matches_truth(vw, vh, cm):
    labelled = {rot: json.loads(_cm_labelled(vw, vh, cm, rot)) for rot in ROTATIONS}
    # cross_check is deliberately not asserted here: with a title anchor on the page the real consumer
    # stops at an earlier dangling end (BOUNDS_UNRESOLVED) and can mask a page-edge end, so the public
    # reason legitimately differs from the page-edge-only recomputation (see the script docstring).
    assert all(r["pipeline_status"] == "ok" for r in labelled.values())
    quantised = D.rotation_equivalence(labelled, column="shadow_decision_quantised_tol")
    assert quantised["equivalent"] and quantised["labels"] == 40
    for report in labelled.values():
        assert _wrong(report, "shadow_decision_quantised_tol") == []
    # Scope of the claim: the extent-only column (consumer default tolerance 1e-6) is NOT per-label
    # rotation-equivalent on these sheets, because float32 edge slop misses different ends per rotation.
    default = D.rotation_equivalence(labelled, column="shadow_decision_default_tol")
    assert not default["equivalent"] and default["mismatches"]
