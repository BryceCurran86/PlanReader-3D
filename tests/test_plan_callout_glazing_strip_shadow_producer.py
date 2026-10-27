"""The producer adapter on a synthetic two-page PDF, through the real producers (no caller-built records)."""
from __future__ import annotations

import fitz
import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from plan_callout_strip_fixture import GAP, HEX_H, Sheet

CAND = EvidenceResolutionStatus.CANDIDATE
ELEVATION_MM_PER_PT = 35.28      # a 1:100 elevation beside the 1:50 plan; used only to draw consistent fixtures
SPECS = (("W1", 3, 3600.0, 2400.0), ("W2", 3, 4100.0, 2400.0), ("W3", 7, 7585.0, 2400.0))


def _draw_elevation(sheet: Sheet, *, drop_dimension_for=None):
    page = sheet.elev
    page.insert_text(fitz.Point(30.0, 40.0), "WINDOW ELEVATIONS", fontsize=10.0)
    for k, (mark, panels, width_mm, height_mm) in enumerate(SPECS):
        x0, y0 = 150.0 + 330.0 * k, 160.0
        x1, y1 = x0 + width_mm / ELEVATION_MM_PER_PT, y0 + height_mm / ELEVATION_MM_PER_PT
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), width=1.0)
        for i in range(panels):
            fx = x0 + (i + 0.5) * (x1 - x0) / panels
            page.insert_text(fitz.Point(fx - 3.0, y0 + 0.3 * (y1 - y0)), "FG", fontsize=8.0)
        page.insert_text(fitz.Point((x0 + x1) / 2.0 - 6.0, y0 + 0.75 * (y1 - y0)), mark, fontsize=9.0)
        if mark == drop_dimension_for:
            continue
        wy = y0 - 40.0
        page.draw_line(fitz.Point(x0, wy), fitz.Point(x1, wy), width=0.7)
        page.draw_line(fitz.Point(x0, wy - 10.0), fitz.Point(x0, y0 + 4.0), width=0.7)
        page.draw_line(fitz.Point(x1, wy - 10.0), fitz.Point(x1, y0 + 4.0), width=0.7)
        page.insert_text(fitz.Point((x0 + x1) / 2.0 - 12.0, wy + 3.0), f"{int(width_mm)}", fontsize=8.0)
        vx = x0 - 40.0
        page.draw_line(fitz.Point(vx, y0), fitz.Point(vx, y1), width=0.7)
        page.draw_line(fitz.Point(vx - 10.0, y0), fitz.Point(x0 + 4.0, y0), width=0.7)
        page.draw_line(fitz.Point(vx - 10.0, y1), fitz.Point(x0 + 4.0, y1), width=0.7)
        page.insert_text(fitz.Point(vx + 3.0, (y0 + y1) / 2.0 + 12.0), f"{int(height_mm)}", fontsize=8.0, rotate=90)


def _plan_sheet(*, plan_rotation=0, drop_dimension_for=None, second_strip_for_w2=False):
    sheet = Sheet(size=(1500.0, 700.0))
    for k, (mark, panels, width_mm, _height) in enumerate(SPECS):
        length = width_mm / (ELEVATION_MM_PER_PT / 2.0)         # 1:50 plan against the 1:100 elevation
        s = sheet.strip("H", 100.0 + 400.0 * k, 300.0, panels=panels, frame_len=length)
        sheet.callout(((s["frame"][0] + s["frame"][1]) / 2.0 + 2.0, s["band"][1] + GAP + HEX_H), mark)
    if second_strip_for_w2:
        sheet.strip("H", 100.0, 500.0, panels=3, frame_len=4100.0 / (ELEVATION_MM_PER_PT / 2.0))
    _draw_elevation(sheet, drop_dimension_for=drop_dimension_for)
    if plan_rotation:
        sheet.plan.set_rotation(plan_rotation)
    return sheet


def _publish(sheet: Sheet, *, native_finish_text_shadow=False):
    source = SourceVisibilityProducer(producer_method="plan-callout-strip-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="plan-callout-strip", source_bytes=sheet.pdf(), source_locator="memory://plan-callout-strip.pdf")
    return source, published


def _audit(source, published, pattern=r"[WD]\d+", **kw):
    return shadow.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=1, elevation_page_id=2,
        callout_mark_pattern=pattern, panel_token="FG", coordinate_quantum_pt=0.24,
        dimension_quantum_mm=5.0, **kw)


def _resolved_viewport(monkeypatch, bbox=(10.0, 10.0, 1490.0, 690.0)):
    """The repository's own test convention: stamp a RESOLVED floor-plan viewport at the segmentation boundary."""
    import pb_viewport_segmentation as seg

    def segment(_page, *, page_number):
        return tuple(seg._stamp_segment_page_viewports_product([seg.SegmentedViewport(
            view_id="vp-plan", page_number=page_number, view_type="floor_plan", label="FLOOR_PLAN",
            title_bbox=(20.0, 10.0, 160.0, 25.0), bounding_box=bbox,
            status=seg.ViewportSegmentationStatus.RESOLVED.value,
            boundary_source=seg.ViewportBoundarySource.VECTOR_FRAME.value, confidence=1.0)]))

    monkeypatch.setattr(seg, "segment_page_viewports", segment)


def test_a_page_with_no_segmented_viewport_never_yields_a_candidate_but_keeps_its_diagnostics():
    source, published = _publish(_plan_sheet())
    result = _audit(source, published)
    got = {c.tag_mark: c for c in result.correspondences}
    assert {m: c.status for m, c in got.items()} == {m: EvidenceResolutionStatus.ABSTAINED for m in ("W1", "W2", "W3")}
    assert all("plan_viewport_not_resolved" in c.reason_codes for c in got.values())
    assert all(dict(c.conditions)["callout_in_one_resolved_plan_viewport"] == shadow.FAILED for c in got.values())
    assert "plan_viewport_whole_page_unsegmented" in result.page_reason_codes
    assert {s.panel_count for s in result.strips} == {3, 7}               # the strip inventory is still reported
    assert all(c.position_strip_ids for c in got.values())


@pytest.mark.parametrize("plan_rotation", [0, 90])
def test_the_adapter_reads_only_producer_owned_records_and_finds_the_three_windows(plan_rotation, monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet(plan_rotation=plan_rotation))
    result = _audit(source, published)
    got = {c.tag_mark: c for c in result.correspondences}
    assert {m: c.status for m, c in got.items()} == {"W1": CAND, "W2": CAND, "W3": CAND}, \
        {m: (c.reason_codes, c.conditions) for m, c in got.items()}
    ownership = result.ownership
    assert (ownership.document_id, ownership.revision_id, ownership.source_sha256, ownership.snapshot_id) == (
        published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
        published.snapshot.snapshot_id)
    assert ownership.input_provenance == shadow.PRODUCER_INPUT_PROVENANCE
    # every evidence id is a producer observation id, never a locally invented one
    visible = set(published.visible_observation_ids)
    for c in got.values():
        assert c.ring.ink_ids and set(c.ring.ink_ids) <= visible
    assert all(set(s.ink_ids) <= visible for s in result.strips)
    assert "plan_viewport_whole_page_unsegmented" not in result.page_reason_codes
    assert {c.plan_viewport_id for c in got.values()} == {"vp-plan"}
    assert {s.panel_count for s in result.strips} == {3, 7}
    for flag in shadow._GRANT_FLAGS:
        assert getattr(result, flag) is False


def test_the_adapter_is_replay_stable(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet())
    assert _audit(source, published) == _audit(source, published)


def test_an_elevation_type_without_its_figured_dimension_abstains_and_does_not_borrow_another_frame(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet(drop_dimension_for="W2"))
    got = {c.tag_mark: c for c in _audit(source, published).correspondences}
    assert got["W2"].status is EvidenceResolutionStatus.ABSTAINED
    assert "elevation_type_record_missing" in got["W2"].reason_codes
    assert got["W1"].status is CAND and got["W3"].status is CAND


def test_a_second_identical_strip_for_a_type_is_a_conflict_through_the_producer_path_too(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet(second_strip_for_w2=True))
    got = {c.tag_mark: c for c in _audit(source, published).correspondences}
    assert got["W2"].status is EvidenceResolutionStatus.CONFLICT
    assert len(got["W2"].scale_consistent_strip_ids) == 2


def test_the_adapter_refuses_foreign_inputs():
    source, published = _publish(_plan_sheet())
    with pytest.raises(TypeError):
        shadow.audit_plan_callout_to_glazing_strip_from_source(
            object(), revision_id="x", plan_page_id=1, elevation_page_id=2, callout_mark_pattern="W.",
            panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0)
    with pytest.raises(ValueError, match="revision"):
        shadow.audit_plan_callout_to_glazing_strip_from_source(
            source, revision_id="no-such-revision", plan_page_id=1, elevation_page_id=2, callout_mark_pattern="W.",
            panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0)
    with pytest.raises(ValueError, match="pages"):
        shadow.audit_plan_callout_to_glazing_strip_from_source(
            source, revision_id=published.revision.revision_id, plan_page_id=1, elevation_page_id=9,
            callout_mark_pattern="W.", panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0)
    with pytest.raises(TypeError):
        shadow.audit_plan_callout_to_glazing_strip_from_source(
            source, revision_id=published.revision.revision_id, plan_page_id="1", elevation_page_id=2,
            callout_mark_pattern="W.", panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0)


def test_a_narrow_report_pattern_through_the_producer_path_is_a_projection_of_the_same_decision(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet())
    broad = {c.tag_mark: c for c in _audit(source, published).correspondences}
    narrow = {c.tag_mark: c for c in _audit(source, published, pattern=r"W[12]").correspondences}
    assert set(narrow) == {"W1", "W2"}
    for m in narrow:
        assert (narrow[m].status, narrow[m].reason_codes, narrow[m].conditions) == \
               (broad[m].status, broad[m].reason_codes, broad[m].conditions)
    assert {c.status for c in narrow.values()} == {CAND}
