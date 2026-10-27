"""The glazing anatomy inventory through the real producer on synthetic PDFs (no caller-built records)."""
from __future__ import annotations

import inspect

import pytest

import pb_glazing_anatomy_inventory_shadow as A
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, VISIBLE_SOURCE_AUTHORITY_REQUIRED
from pb_source_visibility_authority import SourceVisibilityProducer
from plan_callout_strip_fixture import Sheet

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
Q = 0.24
G1, G2, G5, G6, G8 = (A.GATE_NAMES[i] for i in (0, 1, 4, 5, 7))


def _cell(sheet, a, b, n0, *, depth=5.52, pane=(2.4, 3.12), pane_ticks=(True, True), cell_edges=(True, True),
          color=(0, 0, 0)):
    """One H cell drawn line by line (the fixture's strip helper cannot omit a stroke)."""
    for off in (n0, n0 + depth):
        sheet.line((a, off), (b, off), double=True, color=color)
    for off in (n0 + pane[0], n0 + pane[1]):
        sheet.line((a, off), (b, off), color=color)
    for edge, present in zip((a, b), cell_edges):
        if present:
            sheet.line((edge, n0), (edge, n0 + depth), color=color)
    for edge, present in zip((a, b), pane_ticks):
        if present:
            sheet.line((edge, n0 + pane[0]), (edge, n0 + pane[1]), color=color)


def _sheet():
    """A valid 3-panel strip, a one-panel strip, a vertical 2-panel strip, and three near-miss cells."""
    sheet = Sheet(size=(900.0, 700.0))
    sheet.strip("H", 60.0, 100.0, panels=3, frame_len=204.0)
    sheet.strip("H", 60.0, 200.0, panels=1, frame_len=70.0)
    sheet.strip("V", 100.0, 700.0, panels=2, frame_len=140.0)
    _cell(sheet, 400.0, 460.0, 300.0, pane_ticks=(True, False))        # g1: second pane tick missing
    _cell(sheet, 400.0, 460.0, 380.0, cell_edges=(True, False))        # g6: cell end not closed across the depth
    _cell(sheet, 400.0, 460.0, 460.0, pane=(1.5, 2.22))                # g5: off-centre pair
    return sheet


def _publish(sheet):
    """Ingest a sheet, or the exact bytes of one (PyMuPDF stamps a fresh document id on every `tobytes`)."""
    source = SourceVisibilityProducer(producer_method="glazing-anatomy-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="glazing-anatomy", source_bytes=sheet if isinstance(sheet, bytes) else sheet.pdf(),
        source_locator="memory://glazing-anatomy.pdf")
    return source, published


def _inventory(source, published, enabled=True, page_id=1, **kw):
    return A.GlazingAnatomyInventoryShadow(source, enabled=enabled).inventory(
        revision_id=published.revision.revision_id, page_id=page_id, coordinate_quantum_pt=Q, **kw)


def _floor_plan_viewports(monkeypatch, *, view_type="floor_plan", boxes=((10.0, 10.0, 890.0, 690.0),)):
    """The repository's own test convention: stamp the viewports at the segmentation boundary."""
    import pb_viewport_segmentation as seg

    def segment(_page, *, page_number):
        return tuple(seg._stamp_segment_page_viewports_product([
            seg.SegmentedViewport(
                view_id=f"vp-{k}", page_number=page_number, view_type=view_type, label=view_type.upper(),
                title_bbox=(20.0, 10.0, 160.0, 25.0), bounding_box=box,
                status=seg.ViewportSegmentationStatus.RESOLVED.value,
                boundary_source=seg.ViewportBoundarySource.VECTOR_FRAME.value, confidence=1.0)
            for k, box in enumerate(boxes)]))

    monkeypatch.setattr(seg, "segment_page_viewports", segment)


def _merged_strips(source, published):
    import pb_source_plan_glazing_strip_callout_shadow as merged

    result = merged.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=1, elevation_page_id=2,
        callout_mark_pattern=r"[WD]\d+", panel_token="FG", coordinate_quantum_pt=Q, dimension_quantum_mm=5.0)
    return result, sorted(_strip_key(s) for s in result.strips)


def _strip_key(s):
    return (s.axis, s.band, s.along, s.frame_along, s.panel_count, s.panel_lengths, s.inner_post_widths,
            s.end_post_widths, s.extent_complete, s.stroke_width, s.ink_ids)


# --- gate -----------------------------------------------------------------------------------------------------


def test_the_inventory_is_off_by_default_and_a_disabled_call_touches_nothing():
    source, published = _publish(_sheet())
    shadow = A.GlazingAnatomyInventoryShadow(source)
    got = shadow.inventory(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q)
    assert got.status is ABST and got.reason_codes == (A.INVENTORY_DISABLED,) and got.ownership is None
    assert got.candidates == () and got.strips == () and got.evidence_atoms == () and got.record_id is None
    assert source._physical_opening_authority_cache is None


@pytest.mark.parametrize("bad", [1, 0, None, "true", [], {}])
def test_the_gate_must_be_a_strict_boolean_and_the_source_the_concrete_producer(bad):
    source, _ = _publish(_sheet())
    with pytest.raises(ValueError):
        A.GlazingAnatomyInventoryShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        A.GlazingAnatomyInventoryShadow(object(), enabled=True)


def test_there_is_no_caller_channel_for_nominations_widths_roles_or_provenance():
    signature = inspect.signature(A.GlazingAnatomyInventoryShadow.inventory)
    assert [p for p in signature.parameters if p != "self"] == ["revision_id", "page_id", "coordinate_quantum_pt"]
    source, published = _publish(_sheet())
    with pytest.raises(TypeError):
        A.GlazingAnatomyInventoryShadow(source, enabled=True).inventory(
            revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q,
            nominated_observation_ids=("x",))
    with pytest.raises(TypeError):
        A.GlazingAnatomyInventoryShadow(source, enabled=True).inventory(
            revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q, stroke_width=0.48)


# --- the inventory through the producer -------------------------------------------------------------------------------


def test_the_producer_path_finds_every_variant_with_producer_owned_ids_and_the_expected_first_failures():
    source, published = _publish(_sheet())
    got = _inventory(source, published)
    assert got.status is CAND and got.reason_codes == (A.ACCEPTED_CELLS_PRESENT,)
    ownership = got.ownership
    assert (ownership.document_id, ownership.revision_id, ownership.source_sha256, ownership.snapshot_id,
            ownership.page_id) == (published.revision.document_id, published.revision.revision_id,
                                   published.revision.source_sha256, published.snapshot.snapshot_id, "1")
    assert sorted((s.axis, s.panel_count) for s in got.strips) == [("H", 1), ("H", 3), ("V", 2)]
    assert all(s.extent_complete and s.full_anatomy and s.merged_rule_copy_agrees is True for s in got.strips)
    visible = set(published.visible_observation_ids)
    assert got.ink_count == len(visible) and got.unverified_ink_count == 0
    assert all(set(s.ink_ids) <= visible for s in got.strips)
    assert all(set(c.ink_ids) <= visible for c in got.candidates)
    by_first = {}
    for c in got.candidates:
        by_first.setdefault(c.first_failed_gate, []).append(c)
    assert len(by_first[G1]) == 1 and by_first[G1][0].closure == A.CLOSURE_HI_MISSING
    assert len(by_first[G6]) == 1 and by_first[G6][0].near_miss and not by_first[G6][0].in_merged_inventory
    assert len(by_first[G5]) == 1 and by_first[G5][0].rebates == pytest.approx((1.5, 3.3), abs=1e-3)
    assert G2 in by_first                               # the frame outline of the cell whose pane tick is missing
    assert {c.first_failed_gate for c in got.near_misses} == {G6}
    for flag in A._GRANT_FLAGS:
        assert getattr(got, flag) is False


def test_the_accepted_strips_equal_the_merged_modules_strip_inventory_through_the_producer():
    source, published = _publish(_sheet())
    got = _inventory(source, published)
    _, merged = _merged_strips(source, published)
    assert sorted(_strip_key(s) for s in got.strips) == merged
    assert len(merged) == 3


def test_a_strip_without_end_posts_is_in_the_merged_inventory_and_a_g8_near_miss_here():
    sheet = Sheet(size=(900.0, 700.0))
    sheet.strip("H", 60.0, 100.0, panels=2, frame_len=140.0, end_posts=False)
    source, published = _publish(sheet)
    got = _inventory(source, published)
    (strip,) = got.strips
    assert not strip.extent_complete and strip.end_post_widths == (None, None)
    assert {c.first_failed_gate for c in got.near_misses} == {G8} and len(got.near_misses) == 2
    _, merged = _merged_strips(source, published)
    assert [_strip_key(strip)] == merged


def test_a_rotated_page_is_read_in_native_coordinates_and_gives_the_same_inventory():
    flat, flat_published = _publish(_sheet())
    spun_sheet = _sheet()
    spun_sheet.plan.set_rotation(90)
    spun, spun_published = _publish(spun_sheet)
    a, b = _inventory(flat, flat_published), _inventory(spun, spun_published)
    key = lambda inv: ([(c.axis, c.pair, c.along, c.first_failed_gate) for c in inv.candidates],   # noqa: E731
                       sorted(_strip_key(s)[:-1] for s in inv.strips))          # ink ids differ per ingested bytes
    assert key(a) == key(b) and len(a.strips) == 3


def test_grey_ink_forms_no_cell_through_the_producer():
    sheet = Sheet(size=(900.0, 700.0))
    for k in range(3):
        _cell(sheet, 100.0 + 90.0 * k, 160.0 + 90.0 * k, 300.0, color=(0.5, 0.5, 0.5))
    source, published = _publish(sheet)
    got = _inventory(source, published)
    assert got.candidates == () and got.status is ABST and got.reason_codes == (A.NO_ACCEPTED_CELL,)


# --- viewport: reported, never gating -------------------------------------------------------------------------------------


def test_the_resolved_floor_plan_viewport_is_reported_per_strip(monkeypatch):
    _floor_plan_viewports(monkeypatch)
    source, published = _publish(_sheet())
    got = _inventory(source, published)
    assert got.status is CAND and {s.viewport_id for s in got.strips} == {"vp-0"}


def test_a_page_without_a_floor_plan_viewport_still_gets_its_inventory_with_viewport_none():
    source, published = _publish(_sheet())               # a synthetic page has no segmentation at all
    got = _inventory(source, published)
    assert got.status is CAND and len(got.strips) == 3 and {s.viewport_id for s in got.strips} == {None}


@pytest.mark.parametrize("kwargs", [
    dict(view_type="elevation"),
    dict(boxes=((10.0, 10.0, 890.0, 690.0), (100.0, 50.0, 800.0, 600.0))),       # two floor plans can hold a strip
    dict(boxes=((10.0, 10.0, 300.0, 690.0),)),                                    # strips beyond x=300 are cropped
])
def test_a_non_floor_plan_competing_or_cropping_viewport_gives_none_without_abstaining(monkeypatch, kwargs):
    _floor_plan_viewports(monkeypatch, **kwargs)
    source, published = _publish(_sheet())
    got = _inventory(source, published)
    assert got.status is CAND and len(got.strips) == 3
    boxes = kwargs.get("boxes", ((10.0, 10.0, 890.0, 690.0),)) if kwargs.get("view_type", "floor_plan") == "floor_plan" else ()
    for strip in got.strips:
        f0, f1 = strip.frame_along
        o0, o1 = strip.band
        box = (f0, o0, f1, o1) if strip.axis == "H" else (o0, f0, o1, f1)
        holders = [k for k, b in enumerate(boxes) if b[0] <= box[0] and b[1] <= box[1] and box[2] <= b[2] and box[3] <= b[3]]
        assert strip.viewport_id == (f"vp-{holders[0]}" if len(holders) == 1 else None)
    ids = {s.viewport_id for s in got.strips}
    if kwargs.get("view_type") == "elevation":
        assert ids == {None}
    elif len(kwargs.get("boxes", ())) == 2:
        assert ids == {None, "vp-0"}          # strips inside both boxes get None, strips inside only the first get it
    else:
        assert None in ids and "vp-0" in ids  # some strips are cropped, some are not


# --- ownership and staleness ------------------------------------------------------------------------------------------------


def test_unknown_foreign_page_or_stale_inputs_abstain_with_the_existing_vocabulary():
    source, published = _publish(_sheet())
    assert _inventory(source, published, page_id=9).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    shadow = A.GlazingAnatomyInventoryShadow(source, enabled=True)
    unknown = shadow.inventory(revision_id="no-such-revision", page_id=1, coordinate_quantum_pt=Q)
    assert unknown.status is ABST and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    for bad in (dict(revision_id=1), dict(page_id="1"), dict(page_id=True), dict(coordinate_quantum_pt=0.0),
                dict(coordinate_quantum_pt=float("nan")), dict(coordinate_quantum_pt=None)):
        args = dict(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q)
        args.update(bad)
        with pytest.raises(ValueError):
            shadow.inventory(**args)


def test_a_later_revision_makes_the_earlier_revision_stale():
    source, published = _publish(_sheet())
    other = Sheet(size=(900.0, 700.0))
    other.strip("H", 60.0, 100.0, panels=3, frame_len=210.0)
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id, source_bytes=other.pdf(),
                                   source_locator="memory://glazing-anatomy-2.pdf")
    got = _inventory(source, published)
    assert got.status is ABST and got.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_source_bytes_that_fail_their_sha_check_abstain():
    source, published = _publish(_sheet())
    store = source._producer._store.source_bytes_by_revision
    store[published.revision.revision_id] = bytes(store[published.revision.revision_id]) + b"\n%tamper"
    got = _inventory(source, published)
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


def test_ink_whose_geometry_does_not_match_the_producers_primitive_is_counted_and_excluded(monkeypatch):
    import pb_vector_geometry_v130 as vg

    source, published = _publish(_sheet())
    clean = _inventory(source, published)
    real = vg.extract_native_page

    def tampered(page, *args, **kwargs):
        out = real(page, *args, **kwargs)
        segments = [dict(s) for s in out["segments"]]
        victim = segments[0]
        victim["x2"] = float(victim["x2"]) + 5.0
        return {**out, "segments": segments}

    monkeypatch.setattr(vg, "extract_native_page", tampered)
    got = _inventory(source, published)
    assert got.unverified_ink_count == 1 and got.reason_codes == (A.INK_UNVERIFIED,)
    assert got.ink_count == clean.ink_count - 1
    assert got.status is ABST                           # unknown evidence abstains; the lists stay attached as data
    assert clean.status is CAND and len(got.strips) >= 1


def test_replay_is_deterministic_and_ids_are_stable_across_a_fresh_ingest():
    pdf = _sheet().pdf()
    source, published = _publish(pdf)
    first, again = _inventory(source, published), _inventory(source, published)
    assert first == again and first.record_id == again.record_id
    fresh_source, fresh_published = _publish(pdf)
    fresh = _inventory(fresh_source, fresh_published)
    assert fresh.record_id == first.record_id
    assert [c.candidate_id for c in fresh.candidates] == [c.candidate_id for c in first.candidates]


# --- the producer is untouched ---------------------------------------------------------------------------------------------------


def _shape(obj):
    return {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None) for k, v in sorted(vars(obj).items())
            if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}


def test_the_inventory_changes_no_state_of_the_producer_or_its_opening_authority():
    source, published = _publish(_sheet())
    before = _shape(source)
    assert source._physical_opening_authority_cache is None
    first = _inventory(source, published)
    assert first.status is CAND
    assert _shape(source) == before
    assert source._physical_opening_authority_cache is None
    assert _inventory(source, published) == first
    assert _shape(source) == before


def test_positive_control_the_state_check_does_see_a_consumer_filling_the_producers_memos():
    """The equality above is only meaningful if an ordinary consumer call WOULD change that state."""
    from pb_source_observation_authority import ObservationSelector

    source, published = _publish(_sheet())
    strip = _inventory(source, published).strips[0]
    before = _shape(source)
    authority = source.physical_opening_authority()
    for oid in strip.ink_ids:
        authority.prove_existence(ObservationSelector(
            published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
            published.snapshot.snapshot_id, oid))
    assert _shape(source) != before


def test_the_producers_outputs_are_identical_with_and_without_an_inventory_having_run():
    from pb_source_observation_authority import ObservationSelector

    pdf = _sheet().pdf()

    def outputs(run_inventory_first):
        source, published = _publish(pdf)
        if run_inventory_first:
            _inventory(source, published)
        authority = source.physical_opening_authority()
        out = []
        for oid in sorted(published.visible_observation_ids)[:12]:
            result = authority.prove_existence(ObservationSelector(
                published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
                published.snapshot.snapshot_id, oid))
            out.append((result.status.value, tuple(result.reason_codes)))
        return sorted(out)

    assert outputs(True) == outputs(False)


# --- the producer's state, to the depth that matters ------------------------------------------------------------------------------


def _deep_shape(obj, seen=None, path="source", depth=0, out=None):
    """Container sizes (and whether each scalar slot is None) down through the producer, its store and its caches."""
    import collections

    out = {} if out is None else out
    seen = set() if seen is None else seen
    if id(obj) in seen or depth > 6:
        return out
    seen.add(id(obj))
    if isinstance(obj, (dict, collections.OrderedDict)):
        out[path] = len(obj)
        for key, value in list(obj.items())[:60]:
            if isinstance(value, (dict, list, set, tuple)) or hasattr(value, "__dict__"):
                _deep_shape(value, seen, f"{path}[{str(key)[:30]}]", depth + 1, out)
    elif isinstance(obj, (list, set, tuple)):
        out[path] = len(obj)
    elif hasattr(obj, "__dict__"):
        for key, value in sorted(vars(obj).items()):
            if isinstance(value, (dict, list, set, tuple)) or hasattr(value, "__dict__"):
                _deep_shape(value, seen, f"{path}.{key}", depth + 1, out)
            else:
                out[f"{path}.{key}"] = "None" if value is None else "set"
    return out


def _changed(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def test_the_only_producer_state_the_inventory_touches_is_the_verification_memo_every_consumer_fills():
    """The top-level shape check above cannot see the store; this one walks the producer, its store and its caches."""
    source, published = _publish(_sheet())
    before = _deep_shape(source)
    first = _inventory(source, published)
    assert first.status is CAND
    after = _deep_shape(source)
    changed = _changed(before, after)
    assert changed and all("verified_resolution_cache" in key for key in changed), changed
    assert source._physical_opening_authority_cache is None
    # a second call finds the memo warm: nothing at all changes, and the result is identical
    assert _inventory(source, published) == first
    assert _deep_shape(source) == after
    # the memo is the same one the merged adapter's identical resolve_visible calls fill
    other, other_published = _publish(_sheet())
    other_before = _deep_shape(other)
    _merged_strips(other, other_published)
    assert any("verified_resolution_cache" in key for key in _changed(other_before, _deep_shape(other)))


def test_positive_control_the_deep_state_check_does_see_a_consumer_building_the_opening_authority():
    from pb_source_observation_authority import ObservationSelector

    source, published = _publish(_sheet())
    strip = _inventory(source, published).strips[0]
    before = _deep_shape(source)
    authority = source.physical_opening_authority()
    authority.prove_existence(ObservationSelector(
        published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
        published.snapshot.snapshot_id, strip.ink_ids[0]))
    assert any("verified_resolution_cache" not in key for key in _changed(before, _deep_shape(source)))


# --- integrity of the census: nothing foreign, duplicated or malformed is merged in silently ------------------------------------


def _forged(observation, **fields):
    """A copy of a frozen observation with fields replaced, bypassing the record's own constructor checks."""
    import copy

    forged = copy.copy(observation)
    for name, value in fields.items():
        object.__setattr__(forged, name, value)
    return forged


def _tamper_one_resolution(monkeypatch, mutate):
    import dataclasses

    import pb_source_visibility_authority as vis

    real = vis.SourceVisibilityAuthority.resolve_visible
    state = {"n": 0}

    def patched(self, selector):
        result = real(self, selector)
        state["n"] += 1
        if state["n"] == 3 and result.observation is not None:
            return dataclasses.replace(result, observation=mutate(result.observation))
        return result

    monkeypatch.setattr(vis.SourceVisibilityAuthority, "resolve_visible", patched)


@pytest.mark.parametrize("field,value", [
    ("observation_id", "visible:segment:other"), ("document_id", "another-document"),
    ("revision_id", "another-revision"), ("source_sha256", "f" * 64), ("snapshot_id", "another-snapshot"),
])
def test_a_resolved_observation_with_a_foreign_identity_abstains_instead_of_joining_the_census(monkeypatch, field, value):
    source, published = _publish(_sheet())
    assert _inventory(source, published).status is CAND
    _tamper_one_resolution(monkeypatch, lambda observation: _forged(observation, **{field: value}))
    got = _inventory(source, published)
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert got.candidates == () and got.strips == () and got.ownership is None


@pytest.mark.parametrize("geometry", [("a", 0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (float("nan"), 0.0, 1.0, 1.0),
                                      (float("inf"), 0.0, 1.0, 1.0), 7])
def test_malformed_published_geometry_is_counted_as_unverified_and_never_crashes(monkeypatch, geometry):
    source, published = _publish(_sheet())
    clean = _inventory(source, published)
    _tamper_one_resolution(monkeypatch, lambda observation: _forged(observation, geometry=geometry))
    got = _inventory(source, published)
    assert got.unverified_ink_count == 1 and got.reason_codes == (A.INK_UNVERIFIED,) and got.status is ABST
    assert got.ink_count == clean.ink_count - 1


def test_a_repeated_published_visible_id_abstains_instead_of_being_merged(monkeypatch):
    import dataclasses

    source, published = _publish(_sheet())
    ids = tuple(published.visible_observation_ids)
    forged = dataclasses.replace(published, visible_observation_ids=ids + (ids[0],))
    monkeypatch.setattr(source, "published_snapshot_for_revision",
                        lambda revision_id: forged if revision_id == published.revision.revision_id else None)
    got = _inventory(source, published)
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert got.candidates == () and got.strips == ()


def test_ink_on_another_page_is_neither_counted_nor_able_to_change_this_pages_inventory():
    base_source, base_published = _publish(_sheet())
    base = _inventory(base_source, base_published)
    sheet = _sheet()
    for k in range(6):                                 # a whole second strip's worth of ink on the elevation page
        sheet.line((100.0 + 40.0 * k, 100.0), (100.0 + 40.0 * k, 160.0), page=sheet.elev)
    sheet.line((100.0, 300.0), (400.0, 300.0), page=sheet.elev)
    source, published = _publish(sheet)
    got = _inventory(source, published)
    assert got.ink_count == base.ink_count and got.unverified_ink_count == 0
    key = lambda inv: ([(c.axis, c.pair, c.along, c.first_failed_gate) for c in inv.candidates],   # noqa: E731
                       sorted(_strip_key(s)[:-1] for s in inv.strips))
    assert key(got) == key(base)
    other_page = _inventory(source, published, page_id=2)
    assert other_page.ownership.page_id == "2" and other_page.ink_count == 7 and other_page.candidates == ()
