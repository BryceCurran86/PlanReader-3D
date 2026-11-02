"""The occupancy adapter through the real producer on synthetic drawings (no caller-built authority records)."""
from __future__ import annotations

import fitz
import pytest

import pb_plan_tag_opening_occupancy_shadow as M
import pb_source_plan_glazing_strip_callout_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_plan_glazing_strip_callout_shadow import OCCUPANCY_BASIS_ENVELOPE, OCCUPANCY_BASIS_TEXT
from pb_source_visibility_authority import SourceVisibilityProducer
from plan_callout_strip_fixture import GAP, HEX_H, Sheet


def _pdf(lines, *, width=700.0, height=650.0) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    for first, second in lines:
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _wall(spans, top=100.0, gap=10.0):
    out = []
    for x0, x1 in spans:
        out += [((x0, top), (x1, top)), ((x0, top + gap), (x1, top + gap))]
    return out


def _jambs(xs, top=100.0, gap=10.0):
    return [((x, top), (x, top + gap)) for x in xs]


def _door(x0, x1, top=100.0, left=20.0, right=220.0):
    """An opening between jambs at x0 and x1 in a wall whose faces are 10 pt apart."""
    return _wall([(left, x0), (x1, right)], top=top) + _jambs([x0, x1], top=top)


SINGLE = _door(100.0, 140.0)
ADJACENT = _wall([(20, 100), (140, 180), (220, 300)]) + _jambs([100, 140, 180, 220])     # a spanning candidate rivals both
TWO = _door(100.0, 140.0, top=100.0) + _door(100.0, 150.0, top=300.0)


def _publish(lines, *, document_id="occupancy", **page):
    source = SourceVisibilityProducer(producer_method="occupancy-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=_pdf(lines, **page), source_locator="memory://occupancy.pdf")
    return source, published


def _anchor(word, cx, cy, half=3.0, basis=OCCUPANCY_BASIS_ENVELOPE):
    return M.TagAnchor(word, (cx - half, cy - half, cx + half, cy + half), basis)


def _inventory(source, published, anchors, *, page_id=1, enabled=True, **kw):
    return M.PlanTagOpeningOccupancyShadow(source, enabled=enabled).inventory(
        revision_id=published.revision.revision_id, page_id=page_id, anchors=anchors, **kw)


def _selector(published, observation_id):
    return ObservationSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id)


def _outcomes(inv):
    return {d.word_observation_id: d.outcome for d in inv.diagnostics}


# ------------------------------------------------------------------------------------
# positive, and what the producer's own authority says about the same opening
# ------------------------------------------------------------------------------------

def test_an_anchor_in_a_corroborated_opening_gap_is_occupied_and_matches_the_producers_own_record():
    source, published = _publish(SINGLE)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.CANDIDATE and inv.reason_codes == (M.OCCUPANCY_CENSUS_PRODUCED,)
    assert _outcomes(inv) == {"w": M.OUTCOME_OCCUPIED} and inv.candidate_count == 1
    occ = inv.occupancies[0]
    # the record is the one an ordinary consumer gets from the producer's own authority
    authority = source.physical_opening_authority()
    member = sorted(published.visible_observation_ids)[0]
    record = authority.prove_existence(_selector(published, member)).existence_record
    assert record is not None and record.proposition == PHYSICAL_OPENING_EXISTS
    assert occ.occupied_record_id == record.record_id and set(occ.occupied_observation_ids) == set(record.source_observation_ids)
    assert (occ.aperture_along, occ.aperture_normal_range) == ((100.0, 140.0), (100.0, 110.0))
    assert occ.ownership.document_id == published.revision.document_id
    assert occ.ownership.snapshot_id == published.snapshot.snapshot_id
    assert occ.ownership.source_sha256 == published.revision.source_sha256
    assert occ.ownership.input_provenance == shadow.PRODUCER_INPUT_PROVENANCE and occ.competing_candidate_count == 0
    assert set(occ.occupied_observation_ids) <= set(published.visible_observation_ids)


@pytest.mark.parametrize("cx,cy", [(60.0, 105.0), (160.0, 105.0), (120.0, 150.0), (120.0, 95.0), (120.0, 111.0)])
def test_an_anchor_outside_the_gap_or_the_face_band_is_not_occupied(cx, cy):
    source, published = _publish(SINGLE)
    inv = _inventory(source, published, [_anchor("w", cx, cy, half=0.5)])
    assert inv.status is S.CANDIDATE and inv.occupancies == () and _outcomes(inv) == {"w": M.OUTCOME_NONE}


def test_two_openings_that_share_a_wall_stub_are_each_ambiguous_so_neither_occupies():
    source, published = _publish(ADJACENT)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0), _anchor("v", 200.0, 105.0)])
    assert inv.occupancies == ()
    assert _outcomes(inv) == {"w": M.OUTCOME_NOT_CORROBORATED, "v": M.OUTCOME_NOT_CORROBORATED}
    # the producer is ambiguous about the shared members, and one unshared member alone would have said otherwise:
    authority = source.physical_opening_authority()
    statuses = {authority.prove_existence(_selector(published, oid)).status for oid in published.visible_observation_ids}
    assert S.CORROBORATED in statuses and S.CONFLICT in statuses


def test_each_anchor_of_two_walls_is_matched_to_its_own_opening():
    source, published = _publish(TWO)
    inv = _inventory(source, published, [_anchor("a", 120.0, 105.0), _anchor("b", 125.0, 305.0), _anchor("c", 60.0, 105.0)])
    by_word = {o.word_observation_id: o for o in inv.occupancies}
    assert set(by_word) == {"a", "b"} and by_word["a"].occupied_record_id != by_word["b"].occupied_record_id
    assert not set(by_word["a"].occupied_observation_ids) & set(by_word["b"].occupied_observation_ids)
    assert _outcomes(inv)["c"] == M.OUTCOME_NONE


def test_a_page_with_no_candidate_at_all_occupies_nothing():
    source, published = _publish([((20.0, 100.0), (220.0, 100.0))])
    inv = _inventory(source, published, [_anchor("w", 120.0, 100.0)])
    assert inv.status is S.CANDIDATE and inv.candidate_count == 0 and _outcomes(inv) == {"w": M.OUTCOME_NONE}


# ------------------------------------------------------------------------------------
# invariants
# ------------------------------------------------------------------------------------

def _shifted(lines, dx, dy):
    return [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in lines]


def test_translating_the_drawing_and_the_anchor_gives_the_same_outcome():
    s0, p0 = _publish(SINGLE)
    s1, p1 = _publish(_shifted(SINGLE, 123.0, 77.0))
    base = _inventory(s0, p0, [_anchor("w", 120.0, 105.0)])
    moved = _inventory(s1, p1, [_anchor("w", 243.0, 182.0)])
    assert _outcomes(base) == _outcomes(moved) == {"w": M.OUTCOME_OCCUPIED}
    assert moved.occupancies[0].aperture_along == (223.0, 263.0)


def test_unrelated_content_does_not_change_the_outcome():
    s0, p0 = _publish(SINGLE)
    noise = [((400.0 + 7 * i, 420.0), (400.0 + 7 * i + 3.0, 430.0)) for i in range(40)]
    s1, p1 = _publish(SINGLE + noise)
    a = _inventory(s0, p0, [_anchor("w", 120.0, 105.0)])
    b = _inventory(s1, p1, [_anchor("w", 120.0, 105.0)])
    assert _outcomes(a) == _outcomes(b) and b.occupancies[0].aperture_along == a.occupancies[0].aperture_along


def test_replay_and_input_order_are_deterministic_and_the_record_id_is_stable():
    source, published = _publish(TWO)
    anchors = [_anchor("a", 120.0, 105.0), _anchor("b", 125.0, 305.0), _anchor("c", 60.0, 105.0)]
    first = _inventory(source, published, anchors)
    again = _inventory(source, published, list(reversed(anchors)))
    assert first == again and first.record_id == again.record_id
    other = _inventory(source, published, anchors[:2])
    assert other.record_id != first.record_id


def test_the_envelope_and_text_bases_are_carried_unchanged():
    source, published = _publish(SINGLE)
    inv = _inventory(source, published, [_anchor("a", 110.0, 105.0, basis=OCCUPANCY_BASIS_TEXT),
                                         _anchor("b", 130.0, 105.0, basis=OCCUPANCY_BASIS_ENVELOPE)])
    assert {o.word_observation_id: o.basis for o in inv.occupancies} == {
        "a": OCCUPANCY_BASIS_TEXT, "b": OCCUPANCY_BASIS_ENVELOPE}


# ------------------------------------------------------------------------------------
# off by default, strict, ownership, fail-closed
# ------------------------------------------------------------------------------------

def _shape(obj):
    shape = {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None)
             for k, v in sorted(vars(obj).items())
             if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}
    shape["_physical_opening_authority_cache_present"] = obj._physical_opening_authority_cache is not None
    return shape


def test_disabled_by_default_touches_nothing_and_says_so():
    source, published = _publish(SINGLE)
    before = _shape(source)
    for inv in (M.PlanTagOpeningOccupancyShadow(source).inventory(
            revision_id=published.revision.revision_id, page_id=1, anchors=[_anchor("w", 120.0, 105.0)]),
            _inventory(source, published, [_anchor("w", 120.0, 105.0)], enabled=False)):
        assert inv.status is S.ABSTAINED and inv.reason_codes == (M.OCCUPANCY_DISABLED,) and inv.occupancies == ()
    assert _shape(source) == before


@pytest.mark.parametrize("flag", [1, 0, None, "true", [True]])
def test_enabled_must_be_an_explicit_bool(flag):
    source, _ = _publish(SINGLE)
    with pytest.raises(TypeError):
        M.PlanTagOpeningOccupancyShadow(source, enabled=flag)


def test_malformed_arguments_are_rejected_before_any_work():
    source, published = _publish(SINGLE)
    shadow_on = M.PlanTagOpeningOccupancyShadow(source, enabled=True)
    rid = published.revision.revision_id
    for bad in (dict(revision_id=1), dict(page_id="1"), dict(page_id=True), dict(anchors="abc"), dict(anchors=["a"]),
                dict(anchors=[_anchor("w", 1.0, 1.0), _anchor("w", 2.0, 2.0)])):
        args = dict(revision_id=rid, page_id=1, anchors=[_anchor("w", 120.0, 105.0)])
        args.update(bad)
        with pytest.raises(ValueError):
            shadow_on.inventory(**args)


def test_an_unknown_undecoded_or_superseded_revision_abstains():
    source, published = _publish(SINGLE)
    anchors = [_anchor("w", 120.0, 105.0)]
    shadow_on = M.PlanTagOpeningOccupancyShadow(source, enabled=True)
    unknown = shadow_on.inventory(revision_id="no-such-revision", page_id=1, anchors=anchors)
    assert unknown.status is S.ABSTAINED and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    assert _inventory(source, published, anchors, page_id=9).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id, source_bytes=_pdf(_door(100.0, 150.0)),
                                   source_locator="memory://occupancy-2.pdf")
    stale = _inventory(source, published, anchors)
    assert stale.status is S.ABSTAINED and stale.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_an_unbuildable_candidate_aperture_abstains_the_whole_inventory(monkeypatch):
    import pb_schedule_opening_instance_binding_authority as binder
    source, published = _publish(SINGLE)
    monkeypatch.setattr(binder, "_opening_aperture", lambda records: None)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (M.CANDIDATE_APERTURE_UNAVAILABLE,)
    assert inv.occupancies == () and inv.diagnostics == ()


def test_a_failed_replay_abstains_with_a_source_integrity_reason(monkeypatch):
    source, published = _publish(SINGLE)

    def broken(revision_id):
        raise RuntimeError("source bytes unavailable")

    monkeypatch.setattr(source, "fork_native_source_shadow", broken)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


def test_a_replay_that_is_not_the_same_snapshot_abstains(monkeypatch):
    source, published = _publish(SINGLE)
    other_source, _ = _publish(_door(100.0, 150.0), document_id="occupancy")
    real = source.fork_native_source_shadow

    def lookalike(revision_id):
        fork, extra = real(revision_id)
        monkeypatch.setattr(fork, "published_snapshot_for_revision", lambda rid: other_source.published_snapshot_for_revision(
            other_source._producer.current_revision_id("occupancy")))
        return fork, extra

    monkeypatch.setattr(source, "fork_native_source_shadow", lookalike)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


# ------------------------------------------------------------------------------------
# the producer is not changed by a census, and the state check can see a change
# ------------------------------------------------------------------------------------

def test_the_census_changes_no_state_of_the_producer_or_its_opening_authority():
    source, published = _publish(TWO)
    before = _shape(source)
    assert source._physical_opening_authority_cache is None
    inv = _inventory(source, published, [_anchor("a", 120.0, 105.0), _anchor("b", 125.0, 305.0)])
    assert len(inv.occupancies) == 2
    assert _shape(source) == before and source._physical_opening_authority_cache is None
    # a consumer built afterwards sees exactly what a never-censused producer shows it
    shared = source.physical_opening_authority()
    outputs = sorted((shared.prove_existence(_selector(published, i)).status.value) for i in published.visible_observation_ids)
    fresh_source, fresh_published = _publish(TWO)
    fresh = fresh_source.physical_opening_authority()
    fresh_outputs = sorted((fresh.prove_existence(_selector(fresh_published, i)).status.value)
                           for i in fresh_published.visible_observation_ids)
    assert outputs == fresh_outputs


def test_positive_control_the_state_check_does_see_a_consumer_calling_the_authority():
    source, published = _publish(SINGLE)
    before = _shape(source)
    source.physical_opening_authority().prove_existence(_selector(published, sorted(published.visible_observation_ids)[0]))
    assert _shape(source) != before


def test_the_result_is_not_an_existence_record_and_grants_nothing():
    source, published = _publish(SINGLE)
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    for name in M._GRANT_FLAGS:
        assert getattr(inv, name) is False
    assert inv.shadow_only is True and inv.existence_record_issued is False
    assert M.TAG_TYPE_VS_INSTANCE_UNPROVED in inv.standing_limits


# ------------------------------------------------------------------------------------
# end to end through the callout shadow's own source adapter
# ------------------------------------------------------------------------------------

ELEVATION_MM_PER_PT = 35.28
SPECS = (("W1", 3, 3600.0, 2400.0), ("W2", 3, 4100.0, 2400.0), ("W3", 7, 7585.0, 2400.0))


def _draw_elevation(sheet: Sheet):
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


def _plan_with_door(*, door=True, door_in_gap=True):
    sheet = Sheet(size=(1500.0, 700.0))
    for k, (mark, panels, width_mm, _h) in enumerate(SPECS):
        length = width_mm / (ELEVATION_MM_PER_PT / 2.0)
        s = sheet.strip("H", 100.0 + 400.0 * k, 300.0, panels=panels, frame_len=length)
        sheet.callout(((s["frame"][0] + s["frame"][1]) / 2.0 + 2.0, s["band"][1] + GAP + HEX_H), mark)
    cy = 305.52 + GAP + HEX_H                              # the rival door callout shares W1's side and extent
    centre = (160.0 if door_in_gap else 260.0, cy)
    sheet.callout(centre, "D1")
    if door:
        # a door gap in a wall running along x through the callout: faces 10 pt apart, jambs 30 pt apart
        top, x0, x1 = cy - 5.0, 145.0, 175.0
        for off in (top, top + 10.0):
            sheet.line((60.0, off), (x0, off))
            sheet.line((x1, off), (290.0, off))
        for x in (x0, x1):
            sheet.line((x, top), (x, top + 10.0))
    _draw_elevation(sheet)
    return sheet


def _resolved_viewport(monkeypatch, bbox=(10.0, 10.0, 1490.0, 690.0)):
    import pb_viewport_segmentation as seg

    def segment(_page, *, page_number):
        return tuple(seg._stamp_segment_page_viewports_product([seg.SegmentedViewport(
            view_id="vp-plan", page_number=page_number, view_type="floor_plan", label="FLOOR_PLAN",
            title_bbox=(20.0, 10.0, 160.0, 25.0), bounding_box=bbox,
            status=seg.ViewportSegmentationStatus.RESOLVED.value,
            boundary_source=seg.ViewportBoundarySource.VECTOR_FRAME.value, confidence=1.0)]))

    monkeypatch.setattr(seg, "segment_page_viewports", segment)


def _audit(source, published, **kw):
    return shadow.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=1, elevation_page_id=2,
        callout_mark_pattern=r"[WD]\d+", panel_token="FG", coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0, **kw)


def _publish_sheet(sheet):
    source = SourceVisibilityProducer(producer_method="occupancy-e2e", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="occupancy-e2e", source_bytes=sheet.pdf(), source_locator="memory://occupancy-e2e.pdf")
    return source, published


def test_end_to_end_a_door_callout_in_a_corroborated_door_gap_is_separated_through_the_real_adapter(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish_sheet(_plan_with_door())
    plain = {c.tag_mark: c for c in _audit(source, published).correspondences}
    assert plain["W1"].status is S.CONFLICT and plain["D1"].tag_observation_id in plain["W1"].rival_callout_ids
    on_result = _audit(source, published, claimant_occupancy=True)
    on = {c.tag_mark: c for c in on_result.correspondences}
    assert on["W1"].status is S.CANDIDATE, (on["W1"].reason_codes, on_result.page_reason_codes)
    assert shadow.CLAIMANT_SEPARATED_REASON in on["W1"].reason_codes
    assert {s.word_observation_id for s in on["W1"].separated_claimants} == {on["D1"].tag_observation_id}
    assert "claimant_occupancy_evaluated" in on_result.page_reason_codes
    # the occupied opening is a real producer observation set, and nothing else moved
    occupied = set(on["W1"].separated_claimants[0].occupied_observation_ids)
    assert occupied <= set(published.visible_observation_ids)
    assert not occupied & set(next(s for s in on_result.strips if s.strip_id == on["W1"].strip_id).ink_ids)
    for mark in ("W2", "W3"):
        assert on[mark].record_id == plain[mark].record_id


def test_end_to_end_the_flag_off_is_byte_identical_and_a_rival_outside_any_door_gap_stays_a_rival(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish_sheet(_plan_with_door(door_in_gap=False))
    default = _audit(source, published)
    assert default == _audit(source, published, claimant_occupancy=False)
    on = {c.tag_mark: c for c in _audit(source, published, claimant_occupancy=True).correspondences}
    assert on["W1"].status is S.CONFLICT and on["W1"].separated_claimants == ()


def test_end_to_end_without_any_door_gap_the_rival_is_not_separated(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish_sheet(_plan_with_door(door=False))
    on = {c.tag_mark: c for c in _audit(source, published, claimant_occupancy=True).correspondences}
    assert on["W1"].status is S.CONFLICT and on["W1"].separated_claimants == ()


def test_end_to_end_an_unavailable_inventory_separates_nothing_and_says_so(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish_sheet(_plan_with_door())

    def broken(revision_id):
        raise RuntimeError("source bytes unavailable")

    monkeypatch.setattr(source, "fork_native_source_shadow", broken)
    result = _audit(source, published, claimant_occupancy=True)
    assert "claimant_occupancy_unavailable" in result.page_reason_codes
    got = {c.tag_mark: c for c in result.correspondences}
    assert got["W1"].status is S.CONFLICT and got["W1"].separated_claimants == ()


def test_end_to_end_the_source_producer_is_not_changed_by_the_occupancy_pass(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish_sheet(_plan_with_door())
    _audit(source, published)
    before = _shape(source)
    _audit(source, published, claimant_occupancy=True)
    assert _shape(source) == before and source._physical_opening_authority_cache is None


def test_the_local_census_tool_reports_separations_only_when_asked(monkeypatch, tmp_path):
    _resolved_viewport(monkeypatch)
    path = tmp_path / "generated.pdf"
    path.write_bytes(_plan_with_door().pdf())
    from tools.diag_plan_callout_strip_census import census

    args = dict(plan_page=1, elevation_page=2, callout_mark_pattern=r"W1", panel_token="FG",
                coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0, native_finish_text_shadow=False)
    plain = census(path, **args)
    asked = census(path, claimant_occupancy=True, **args)
    assert plain["claimant_occupancy"] is False and asked["claimant_occupancy"] is True
    assert plain["rows"][0]["status"] == S.CONFLICT.value and plain["rows"][0]["separated_claimants"] == []
    row = asked["rows"][0]
    assert row["status"] == S.CANDIDATE.value and row["separated_claimants"]
    assert {x["entry"] for x in row["separated_claimants"]} <= {"ring", "exclusion", "unresolved_word"}
    assert all(x["occupied_observation_ids"] for x in row["separated_claimants"])
    assert all(value is False for value in asked["grants"].values())


# ------------------------------------------------------------------------------------
# a published candidate is a source-owned record: a foreign, stale or malformed one abstains the census
# ------------------------------------------------------------------------------------

def _forge_candidates(monkeypatch, transform):
    from dataclasses import replace as dc_replace

    from pb_physical_opening_authority import PhysicalOpeningAuthority

    real = PhysicalOpeningAuthority.visible_candidate_structures

    def forged(self, selector):
        result = real(self, selector)
        return dc_replace(result, candidates=tuple(transform(c) for c in result.candidates))

    monkeypatch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", forged)


@pytest.mark.parametrize("field,value", [
    ("document_id", "another-document"), ("revision_id", "another-revision"), ("source_sha256", "0" * 64),
    ("snapshot_id", "another-snapshot"), ("page_id", "9"), ("source_observation_ids", ()),
])
def test_a_foreign_or_malformed_candidate_abstains_with_a_source_integrity_reason(monkeypatch, field, value):
    from dataclasses import replace as dc_replace

    source, published = _publish(SINGLE)
    _forge_candidates(monkeypatch, lambda c: dc_replace(c, **{field: value}))
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert inv.occupancies == () and inv.diagnostics == ()


def test_a_candidate_with_a_duplicated_member_abstains(monkeypatch):
    from dataclasses import replace as dc_replace

    source, published = _publish(SINGLE)
    _forge_candidates(monkeypatch, lambda c: dc_replace(
        c, source_observation_ids=c.source_observation_ids + c.source_observation_ids[:1]))
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


def test_a_failed_page_candidate_census_abstains(monkeypatch):
    from dataclasses import replace as dc_replace

    from pb_physical_opening_authority import PhysicalOpeningAuthority

    source, published = _publish(SINGLE)
    real = PhysicalOpeningAuthority.visible_candidate_structures
    monkeypatch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures",
                        lambda self, selector: dc_replace(real(self, selector), status=S.ABSTAINED))
    inv = _inventory(source, published, [_anchor("w", 120.0, 105.0)])
    assert inv.status is S.ABSTAINED and inv.reason_codes == (M.PAGE_CANDIDATE_CENSUS_UNAVAILABLE,)


def _floor_plan_viewport(monkeypatch, bbox=(10.0, 10.0, 1490.0, 690.0)):
    """The structural assessment needs the nominated strip inside a positively authenticated floor-plan view."""
    _resolved_viewport(monkeypatch, bbox)


def test_the_census_tool_hands_the_corresponded_strip_to_the_structural_assessment_only_when_asked(monkeypatch, tmp_path):
    _floor_plan_viewport(monkeypatch)
    path = tmp_path / "generated.pdf"
    path.write_bytes(_plan_with_door().pdf())
    from tools.diag_plan_callout_strip_census import census

    args = dict(plan_page=1, elevation_page=2, callout_mark_pattern=r"W1", panel_token="FG",
                coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0, native_finish_text_shadow=False,
                claimant_occupancy=True)
    plain = census(path, **args)
    asked = census(path, assess_corresponded_strips=True, **args)
    p_row, a_row = plain["rows"][0], asked["rows"][0]
    assert plain["assess_corresponded_strips"] is False and "structural_assessment" not in p_row
    assert asked["assess_corresponded_strips"] is True
    # the hand-off is the correspondence's own source-owned strip, identical with and without the assessment
    for key in ("correspondence_record_id", "strip_id", "strip_ink_ids", "strip_frame_along", "strip_band", "status"):
        assert p_row[key] == a_row[key]
    assert a_row["status"] == S.CANDIDATE.value and a_row["strip_ink_ids"] and a_row["strip_id"]
    assess = a_row["structural_assessment"]
    assert assess["status"] in {S.CANDIDATE.value, S.ABSTAINED.value, S.CONFLICT.value} and assess["nomination_id"]
    if assess["status"] != S.ABSTAINED.value:
        assert assess["axis"] == "H" and assess["along_extent"] == a_row["strip_frame_along"]
        assert assess["band_extent"] == a_row["strip_band"]
    assert all(value is False for value in asked["grants"].values())


def test_a_row_without_a_candidate_correspondence_has_no_structural_assessment(monkeypatch, tmp_path):
    _floor_plan_viewport(monkeypatch)
    path = tmp_path / "generated.pdf"
    path.write_bytes(_plan_with_door().pdf())
    from tools.diag_plan_callout_strip_census import census

    report = census(path, plan_page=1, elevation_page=2, callout_mark_pattern=r"W1", panel_token="FG",
                    coordinate_quantum_pt=0.24, dimension_quantum_mm=5.0, native_finish_text_shadow=False,
                    claimant_occupancy=False, assess_corresponded_strips=True)
    row = report["rows"][0]
    assert row["status"] == S.CONFLICT.value and "structural_assessment" not in row
    assert row["strip_id"] is None and row["strip_ink_ids"] == []
