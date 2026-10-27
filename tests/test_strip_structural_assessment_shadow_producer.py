"""The strip structural assessment through the real producer on synthetic PDFs (no caller-built records)."""
from __future__ import annotations

import inspect
from dataclasses import fields, replace

import pytest

import pb_strip_structural_assessment_shadow as A
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED, VISIBLE_SOURCE_AUTHORITY_REQUIRED
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from plan_callout_strip_fixture import Sheet

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
Q = 0.24


def _publish(sheet):
    source = SourceVisibilityProducer(producer_method="strip-assessment-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="strip-assessment", source_bytes=sheet.pdf(), source_locator="memory://strip-assessment.pdf")
    return source, published


def _selector(published, oid):
    return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                               published.revision.source_sha256, published.snapshot.snapshot_id, oid)


def _ids_in(source, published, box, page="1", tol=0.01):
    vis = source.authority()
    out = []
    for oid in published.visible_observation_ids:
        o = vis.resolve_visible(_selector(published, oid)).observation
        if o is None or str(o.page_id) != page:
            continue
        g = o.geometry
        if (box[0] - tol <= min(g[0], g[2]) and max(g[0], g[2]) <= box[2] + tol
                and box[1] - tol <= min(g[1], g[3]) and max(g[1], g[3]) <= box[3] + tol):
            out.append(oid)
    return tuple(sorted(out))


def _floor_plan_viewport(monkeypatch, *, view_type="floor_plan", boxes=((10.0, 10.0, 890.0, 690.0),)):
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


def _per_bay_strip():
    """The regime seen on the real page: a 3-panel strip whose glass pair breaks at the posts, plus thick end piers."""
    sheet = Sheet(size=(900.0, 700.0))
    sheet.strip("H", 200.0, 300.0, panels=3, frame_len=204.0)
    sheet.line((200.0, 296.0), (200.0, 310.0), width=0.96)
    sheet.line((404.0, 296.0), (404.0, 310.0), width=0.96)
    source, published = _publish(sheet)
    return source, published, _ids_in(source, published, (200.0, 300.0, 404.0, 305.52))


def _whole_strip(*, fill_box=None, fill_color=(1.0, 1.0, 1.0)):
    """The positive regime: wall faces broken once, jambs at both ends, glazing inside the gap on other offsets."""
    sheet = Sheet(size=(900.0, 700.0))
    for y in (300.0, 305.52):
        sheet.line((50.0, y), (150.0, y))
        sheet.line((354.0, y), (454.0, y))
    sheet.line((150.0, 300.0), (150.0, 305.52))
    sheet.line((354.0, 300.0), (354.0, 305.52))
    for y in (301.5, 304.0):
        sheet.line((150.0, y), (354.0, y))
    for x in (150.0, 250.0, 354.0):
        sheet.line((x, 301.5), (x, 304.0))
    if fill_box is not None:
        sheet.plan.draw_rect(fill_box, color=None, fill=fill_color)
    source, published = _publish(sheet)
    return source, published, _ids_in(source, published, (150.0, 301.4, 354.0, 304.1))


def _assess(source, published, ids, enabled=True, page_id=1):
    return A.StripStructuralAssessmentShadow(source, enabled=enabled).assess(
        revision_id=published.revision.revision_id, page_id=page_id, nominated_observation_ids=ids,
        coordinate_quantum_pt=Q)


# --- gate -----------------------------------------------------------------------------------------


def test_the_assessment_is_off_by_default_and_a_disabled_call_touches_nothing():
    source, published, ids = _per_bay_strip()
    shadow = A.StripStructuralAssessmentShadow(source)
    got = shadow.assess(revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
                        coordinate_quantum_pt=Q)
    assert got.status is ABST and got.reason_codes == (A.ASSESSMENT_DISABLED,) and got.ownership is None
    assert got.evidence_atoms == () and got.fragments == () and got.terminals == ()
    assert source._physical_opening_authority_cache is None and shadow._forks == {}


@pytest.mark.parametrize("bad", [1, 0, None, "true", [], {}])
def test_the_gate_must_be_a_strict_boolean_and_the_source_the_concrete_producer(bad):
    source, _, _ = _per_bay_strip()
    with pytest.raises(ValueError):
        A.StripStructuralAssessmentShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        A.StripStructuralAssessmentShadow(object(), enabled=True)


def test_there_is_no_caller_channel_for_widths_roles_or_provenance():
    signature = inspect.signature(A.StripStructuralAssessmentShadow.assess)
    assert [p for p in signature.parameters if p != "self"] == [
        "revision_id", "page_id", "nominated_observation_ids", "coordinate_quantum_pt"]
    source, published, ids = _per_bay_strip()
    with pytest.raises(TypeError):
        A.StripStructuralAssessmentShadow(source, enabled=True).assess(
            revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
            coordinate_quantum_pt=Q, stroke_width=0.96)


def test_a_warmed_shadow_reauthenticates_each_call_and_never_reuses_a_revoked_fork(monkeypatch):
    """A cache hit must not turn a later unavailable original into an opening candidate."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    shadow = A.StripStructuralAssessmentShadow(source, enabled=True)
    revision = published.revision.revision_id
    args = dict(revision_id=revision, page_id=1, nominated_observation_ids=ids, coordinate_quantum_pt=Q)
    original_fork = source.fork_native_source_shadow
    fork_calls = []

    def independently_replay(revision_id):
        fork_calls.append(revision_id)
        if len(fork_calls) == 3:
            raise RuntimeError("source fork unavailable on the later assessment")
        return original_fork(revision_id)

    monkeypatch.setattr(source, "fork_native_source_shadow", independently_replay)
    first = shadow.assess(**args)
    second = shadow.assess(**args)
    assert first.status is CONF and second == first
    assert fork_calls == [revision, revision]
    assert shadow._forks == {}  # no stale replay retained after either positive observation

    revoked = shadow.assess(**args)
    assert fork_calls == [revision, revision, revision]
    assert revoked.status is ABST
    assert revoked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert revoked.fragments == () and revoked.terminals == ()
    assert revoked.ownership is None
    assert shadow._forks == {}


# --- the two regimes ---------------------------------------------------------------------------------


def test_the_per_bay_regime_keeps_the_conflict_and_is_never_a_candidate(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    got = _assess(source, published, ids)
    assert got.status is CONF
    assert got.axis == "H" and got.along_extent == pytest.approx((200.0, 404.0), abs=0.01)
    assert len(got.fragments) >= 2 and not any(f.spans_whole_extent for f in got.fragments)
    assert any(f.existence == "corroborated" for f in got.fragments)
    assert all(f.strong_pattern for f in got.fragments)
    # the openings the authority names are post gaps, not the strip
    for f in got.fragments:
        assert f.gap_span is not None and (f.gap_span[1] - f.gap_span[0]) < 0.9 * (got.along_extent[1] - got.along_extent[0])
    assert got.ownership.document_id == published.revision.document_id
    assert (got.ownership.revision_id, got.ownership.source_sha256, got.ownership.snapshot_id) == (
        published.revision.revision_id, published.revision.source_sha256, published.snapshot.snapshot_id)
    assert got.viewport_id == "vp-0" and got.standing_limits == A.STANDING_LIMITS


def test_terminal_ink_carries_the_producers_own_widths_for_every_stroke_at_each_end(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    got = _assess(source, published, ids)
    piers = [t for t in got.terminals if t.orientation == "perpendicular" and t.stroke_width and abs(t.stroke_width - 0.96) < 1e-6]
    assert sorted(t.end for t in piers) == ["hi", "lo"]
    assert all(t.spans_band and t.extends_beyond_band and not t.nominated and t.role_verified for t in piers)
    assert {round(r.stroke_width, 2) for r in got.roles} == {0.48} and all(r.role_verified for r in got.roles)


def test_a_whole_strip_with_jambs_at_both_terminals_is_the_only_way_to_a_candidate(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    got = _assess(source, published, ids)
    assert got.status is CAND, (got.reason_codes, [(f.existence, f.gap_span) for f in got.fragments])
    assert len(got.fragments) == 1 and got.fragments[0].spans_whole_extent and got.fragments[0].existence == "corroborated"
    assert got.fragments[0].gap_span == pytest.approx(got.along_extent, abs=0.01)
    assert A.TERMINAL_ROLE_UNPROVEN in got.reason_codes
    assert got.evidence_atoms[0].status is CAND and got.evidence_atoms[0].metadata["physical_opening_granted"] is False
    for flag in A._GRANT_FLAGS:
        assert getattr(got, flag) is False


@pytest.mark.parametrize("color", [(1.0, 1.0, 1.0), (0.3, 0.5, 0.7)])
def test_known_fill_only_original_paths_remain_in_terminal_census_without_invented_strokes(monkeypatch, color):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip(fill_box=(149.0, 301.75, 149.95, 303.75), fill_color=color)
    before = _shape(source)
    got = _assess(source, published, ids)
    assert A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE not in got.reason_codes
    assert got.ownership.snapshot_id == published.snapshot.snapshot_id
    fills = [t for t in got.terminals if t.fill_rgb is not None]
    assert fills, "the source fill boundary must be retained, not silently discarded"
    assert all(t.role_verified and t.stroke_width is None and t.stroke_rgb is None for t in fills)
    assert all(t.fill_rgb == pytest.approx(color) for t in fills)
    assert _shape(source) == before
    assert _assess(source, published, tuple(reversed(ids))) == got
    assert all(getattr(got, flag) is False for flag in A._GRANT_FLAGS)


def test_nominated_fill_only_original_boundary_cannot_become_stroked_strip_evidence(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip(fill_box=(600.0, 500.0, 680.0, 510.0))
    assert _assess(source, published, ids).status is CAND
    fills = _ids_in(source, published, (600.0, 500.0, 680.0, 510.0))
    assert len(fills) == 4 and not set(fills) & set(ids)
    got = _assess(source, published, fills)
    assert got.status is ABST and A.SOURCE_ROLE_UNPROVEN in got.reason_codes
    assert all(r.role_verified and r.fill_rgb == (1.0, 1.0, 1.0) and r.stroke_width is None for r in got.roles)
    assert all(getattr(got, flag) is False for flag in A._GRANT_FLAGS)


@pytest.mark.parametrize("present, fill", [
    (False, None), (True, []), (True, [True, 0.0, 0.0]),
    (True, [float("nan"), 0.0, 0.0]), (True, [float("inf"), 0.0, 0.0]),
    (True, [10 ** 1000, 0.0, 0.0]), (True, [1.01, 0.0, 0.0]),
])
def test_absent_stroke_without_original_fill_proof_still_fails_integrity(monkeypatch, present, fill):
    import pb_vector_geometry_v130 as native

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip(fill_box=(600.0, 500.0, 680.0, 510.0))
    original = native.extract_native_page

    def without_fill_proof(page):
        extracted = original(page)
        for primitive in extracted["segments"]:
            if not primitive.get("stroke_present"):
                primitive["fill_present"] = present
                primitive["fill"] = fill
        return extracted

    with monkeypatch.context() as patch:
        patch.setattr(native, "extract_native_page", without_fill_proof)
        got = _assess(source, published, ids)
    assert got.status is ABST and got.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert all(getattr(got, flag) is False for flag in A._GRANT_FLAGS)


def test_optional_original_fill_roles_preserve_full_strip_conflicts_and_source_state():
    # Reuse the existing private-original parameter loader: no customer PDF,
    # project identity, source constants or expected quantities enter this test.
    from test_plan_callout_glazing_strip_original_source import _parameters
    from pb_source_plan_glazing_strip_callout_shadow import audit_plan_callout_to_glazing_strip_from_source

    params, data = _parameters()
    source = SourceVisibilityProducer(
        producer_method="strip-assessment-original-test", producer_version="1",
        source_native_finish_text_shadow=bool(params.get("native_finish_text_shadow", True)))
    published = source.ingest_native_pdf_bytes(
        document_id=f"original:{params['sha256'][:32]}", source_bytes=data, source_locator="memory://original.pdf",
        page_ids=(params["plan_page"], params["elevation_page"]))
    result = audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=params["plan_page"],
        elevation_page_id=params["elevation_page"], callout_mark_pattern=params["callout_mark_pattern"],
        panel_token=params["panel_token"], coordinate_quantum_pt=params["coordinate_quantum_pt"],
        dimension_quantum_mm=params["dimension_quantum_mm"])
    assert result.strips, "original source acceptance must exercise a real strip, not an empty census"
    for strip in result.strips:
        before = _shape(source)
        got = A.StripStructuralAssessmentShadow(source, enabled=True).assess(
            revision_id=published.revision.revision_id, page_id=params["plan_page"],
            nominated_observation_ids=strip.ink_ids, coordinate_quantum_pt=params["coordinate_quantum_pt"])
        assert A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE not in got.reason_codes
        assert got.ownership.snapshot_id == published.snapshot.snapshot_id
        assert _shape(source) == before
        assert all(getattr(got, flag) is False for flag in A._GRANT_FLAGS)
        if any(f.existence == "corroborated" and not f.spans_whole_extent for f in got.fragments):
            assert got.status is CONF


def test_fill_boundary_in_corroborated_whole_extent_cannot_supply_a_stroked_jamb(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    fragment = baseline.fragments[0]
    changed = next(i for i in fragment.member_observation_ids if i not in ids)
    visibility = source.authority()
    page = []
    for oid in published.visible_observation_ids:
        observation = visibility.resolve_visible(_selector(published, oid)).observation
        if observation.page_id != "1":
            continue
        # Exercise the pure core with a source-role negative even when the
        # independent existing opening authority supplies positive membership.
        page.append(A.SourceRole(oid, observation.geometry, None if oid == changed else 0.48,
                                 None if oid == changed else (0.0, 0.0, 0.0), "line", True,
                                 (1.0, 1.0, 1.0) if oid == changed else None))
    got = A.assess_strip_hypothesis(
        ownership=baseline.ownership, viewport=A.ViewportRef("vp-0", (10.0, 10.0, 890.0, 690.0)),
        nominated_ids=ids, page_segments=page,
        candidates=[(fragment.candidate_id, fragment.structural_pattern, fragment.member_observation_ids)],
        corroborated_member_sets=frozenset([frozenset(fragment.member_observation_ids)]),
        member_status={i: "corroborated" for i in fragment.member_observation_ids}, coordinate_quantum_pt=Q)
    assert got.status is ABST and A.SOURCE_ROLE_UNPROVEN in got.reason_codes
    assert got.fragments[0].existence == "corroborated"  # retain, never silently rewrite, the upstream verdict
    assert all(getattr(got, flag) is False for flag in A._GRANT_FLAGS)


# --- viewport ------------------------------------------------------------------------------------------


def test_without_an_authenticated_floor_plan_viewport_there_is_no_verdict():
    source, published, ids = _per_bay_strip()          # a synthetic page has no segmentation at all
    got = _assess(source, published, ids)
    assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
    assert got.fragments == () and got.viewport_id is None


@pytest.mark.parametrize("kwargs", [
    dict(view_type="elevation"),
    dict(boxes=((10.0, 10.0, 890.0, 690.0), (100.0, 100.0, 800.0, 600.0))),      # two floor plans own the strip
    dict(boxes=((10.0, 10.0, 300.0, 690.0),)),                                    # the strip is cropped by the viewport
])
def test_non_floor_plan_competing_or_cropping_viewports_abstain(monkeypatch, kwargs):
    _floor_plan_viewport(monkeypatch, **kwargs)
    source, published, ids = _per_bay_strip()
    got = _assess(source, published, ids)
    assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)


# --- ownership -----------------------------------------------------------------------------------------


def test_unknown_foreign_page_or_stale_inputs_abstain(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    assert _assess(source, published, ids + ("not-an-observation",)).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert _assess(source, published, ()).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert _assess(source, published, ids, page_id=2).reason_codes == (A.NOMINATION_NOT_VISIBLE_ON_PAGE,)     # ids of another page
    assert _assess(source, published, ids, page_id=9).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)   # page not decoded
    shadow = A.StripStructuralAssessmentShadow(source, enabled=True)
    unknown = shadow.assess(revision_id="no-such-revision", page_id=1, nominated_observation_ids=ids, coordinate_quantum_pt=Q)
    assert unknown.status is ABST and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    for bad in (dict(revision_id=1), dict(page_id="1"), dict(coordinate_quantum_pt=0.0),
                dict(nominated_observation_ids="abc"), dict(nominated_observation_ids=(1,))):
        args = dict(revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
                    coordinate_quantum_pt=Q)
        args.update(bad)
        with pytest.raises(ValueError):
            shadow.assess(**args)


def test_a_later_revision_makes_the_earlier_nomination_stale(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    other = Sheet(size=(900.0, 700.0))
    other.strip("H", 200.0, 300.0, panels=3, frame_len=210.0)
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id, source_bytes=other.pdf(),
                                   source_locator="memory://strip-assessment-2.pdf")
    got = _assess(source, published, ids)
    assert got.status is ABST and got.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_replay_is_deterministic_and_ids_are_stable(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    first, again = _assess(source, published, ids), _assess(source, published, tuple(reversed(ids)))
    assert first == again and first.record_id == again.record_id and first.nomination_id == again.nomination_id


# --- the producer's own opening authority is untouched --------------------------------------------------


def _shape(obj):
    shape = {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None)
             for k, v in sorted(vars(obj).items())
             if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}
    # Opening authority creation is a consumer-owned memo even when it does not
    # populate any producer dict/list. Include this object cache in the sentinel.
    shape["_physical_opening_authority_cache_present"] = obj._physical_opening_authority_cache is not None
    return shape


def test_the_assessment_changes_no_output_and_no_state_of_the_producer_or_its_opening_authority(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    before_producer = _shape(source)
    assert source._physical_opening_authority_cache is None
    first = _assess(source, published, ids)
    assert first.status is CONF and any(f.existence == "corroborated" for f in first.fragments)
    # nothing the existing consumers memoise (paint, dimension, viewport proofs, opening caches) was filled by it
    assert _shape(source) == before_producer
    assert source._physical_opening_authority_cache is None
    # ... and the authority a consumer later builds sees exactly what it would have seen without any assessment
    shared = source.physical_opening_authority()
    outputs = [(shared.prove_existence(_selector(published, i)).status.value,
                shared.prove_existence(_selector(published, i)).reason_codes) for i in ids]
    fresh_source, fresh_published, fresh_ids = _per_bay_strip()
    fresh = fresh_source.physical_opening_authority()
    fresh_outputs = [(fresh.prove_existence(_selector(fresh_published, i)).status.value,
                      fresh.prove_existence(_selector(fresh_published, i)).reason_codes) for i in fresh_ids]
    assert sorted(outputs) == sorted(fresh_outputs)


def test_positive_control_the_state_check_does_see_a_consumer_filling_the_producers_memos(monkeypatch):
    """The equality above is only meaningful if an ordinary consumer call WOULD change that state."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    first = _assess(source, published, ids)
    corroborated = next(f for f in first.fragments if f.existence == "corroborated")
    before = _shape(source)
    source.physical_opening_authority().prove_existence(_selector(published, corroborated.member_observation_ids[0]))
    assert _shape(source) != before


def test_the_result_type_cannot_be_mistaken_for_an_existence_record_or_a_host_candidate():
    names = {f.name for f in fields(A.StripStructuralAssessment)}
    assert not ({"aperture_bbox_pt", "structural_pattern", "host_candidate_id", "candidate_wall_ids_considered",
                 "existence_record", "source_geometry", "host_wall_id", "area_m2"} & names)
    assert "existence_record_issued" in names     # explicitly a False grant flag, never a record


def test_the_schedule_binder_gives_the_same_typed_result_for_every_fragment_before_and_after_an_assessment(monkeypatch):
    """A/B over a real consumer: nominating a strip changes nothing the binder can see, and a fragment is still unbound."""
    from pb_schedule_opening_instance_binding_authority import (
        BINDING_OPENING_UNRESOLVED, ScheduleOpeningInstanceBindingProducer,
    )

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _per_bay_strip()
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)

    def binder_results():
        out = []
        for oid in ids[:8]:
            result = binder.publish_scope(opening_selector=_selector(published, oid), decision_scope_id="scope-1")
            out.append((result.status.value, tuple(result.reason_codes)))
        return out

    before = binder_results()
    assessment = _assess(source, published, ids)
    assert assessment.status is CONF
    assert binder_results() == before
    assert all(status != "corroborated" for status, _ in before)        # nothing here was ever a bound opening
    assert any(BINDING_OPENING_UNRESOLVED in reasons for _, reasons in before)


def test_duplicate_source_nomination_is_not_silently_deduplicated(monkeypatch):
    """Producer adapter must preserve malformed source IDs for the core ABSTAIN gate."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    assert ids and _assess(source, published, ids).status is CAND
    duplicated = ids + (ids[0],)
    got = _assess(source, published, duplicated)
    assert got.status is ABST
    assert A.NOMINATION_NOT_VISIBLE_ON_PAGE in got.reason_codes
    assert not got.takeoff_eligible and not got.customer_publication_granted


def test_failed_nonnominated_visible_source_cannot_vanish_from_terminal_census(monkeypatch):
    """A bad original observation is a negative, not an invitation to omit rival ink."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    other = next(oid for oid in published.visible_observation_ids if oid not in ids)
    visibility = source.authority()
    original_resolve = visibility.resolve_visible

    def with_corrupt_rival(selector):
        if selector.observation_id == other:
            return visibility._conflict("synthetic_visible_source_integrity_failure")
        return original_resolve(selector)

    with monkeypatch.context() as patch:
        patch.setattr(visibility, "resolve_visible", with_corrupt_rival)
        patch.setattr(source, "authority", lambda: visibility)
        blocked = _assess(source, published, ids)
    assert blocked.status is ABST
    assert A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE in blocked.reason_codes
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _assess(source, published, ids) == baseline



@pytest.mark.parametrize("malformed", [
    None,
    17,
    ("bad-number", 2.0, 3.0, 4.0),
    (float("nan"), 2.0, 3.0, 4.0),
    (float("inf"), 2.0, 3.0, 4.0),
    (10 ** 1000, 2.0, 3.0, 4.0),
    (True, 2.0, 3.0, 4.0),
])
def test_nonfinite_or_nonnumeric_published_rival_abstains_instead_of_crashing(monkeypatch, malformed):
    """The real producer's clean strip cannot outvote a malformed published rival."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    other = next(oid for oid in published.visible_observation_ids if oid not in ids)
    visibility = source.authority()
    original_resolve = visibility.resolve_visible
    before = _shape(source)

    def corrupt_rival(selector):
        result = original_resolve(selector)
        if selector.observation_id == other:
            assert result.observation is not None
            return replace(result, observation=replace(result.observation, geometry=malformed))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(visibility, "resolve_visible", corrupt_rival)
        patch.setattr(source, "authority", lambda: visibility)
        blocked = _assess(source, published, ids)
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


def test_malformed_same_page_visible_rival_geometry_vetoes_positive_strip(monkeypatch):
    """A CORROBORATED but malformed published rival cannot disappear from the page census."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    other = next(oid for oid in published.visible_observation_ids if oid not in ids)
    visibility = source.authority()
    original_resolve = visibility.resolve_visible

    def malformed_visible_rival(selector):
        result = original_resolve(selector)
        if selector.observation_id == other:
            assert result.observation is not None
            return replace(result, observation=replace(result.observation, geometry=(1.0, 2.0, 3.0)))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(visibility, "resolve_visible", malformed_visible_rival)
        patch.setattr(source, "authority", lambda: visibility)
        blocked = _assess(source, published, ids)
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("corrupt_field", ["source_primitive_ref", "geometry"])
def test_unverified_same_page_published_rival_cannot_leave_a_positive_strip(monkeypatch, corrupt_field):
    """A valid-length rival with a broken original primitive join is a source negative."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    other = next(oid for oid in published.visible_observation_ids if oid not in ids)
    visibility = source.authority()
    original_resolve = visibility.resolve_visible
    before = _shape(source)

    def corrupt_rival(selector):
        result = original_resolve(selector)
        if selector.observation_id == other:
            assert result.observation is not None
            observation = result.observation
            if corrupt_field == "source_primitive_ref":
                observation = replace(observation, source_primitive_ref="visible:segment:missing-original")
            else:
                geometry = observation.geometry
                observation = replace(observation, geometry=(geometry[0] + 0.125, *geometry[1:]))
            return replace(result, observation=observation)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(visibility, "resolve_visible", corrupt_rival)
        patch.setattr(source, "authority", lambda: visibility)
        blocked = _assess(source, published, ids)
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("fault", ["page_census", "member_proof"])
def test_downstream_source_integrity_negative_cannot_be_overridden_by_a_clean_strip(monkeypatch, fault):
    """A failed authority read must not become absence or be masked by another member's signed proof."""
    from pb_physical_opening_authority import PhysicalOpeningAuthority

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    before = _shape(source)
    reason = A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE
    seen = {"faulted": False}

    with monkeypatch.context() as patch:
        if fault == "page_census":
            original = PhysicalOpeningAuthority.visible_candidate_structures

            def corrupt_page_census(self, selector):
                result = original(self, selector)
                assert result.status is CAND and result.candidates
                seen["faulted"] = True
                # Preserve stale positive candidates to prove status is checked.
                return replace(result, status=ABST, reason_codes=(reason,))

            patch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", corrupt_page_census)
        else:
            original = PhysicalOpeningAuthority.prove_existence

            def corrupt_one_member_proof(self, selector):
                result = original(self, selector)
                if not seen["faulted"] and result.existence_record is not None:
                    seen["faulted"] = True
                    return replace(result, status=ABST, reason_codes=(reason,), existence_record=None)
                return result

            patch.setattr(PhysicalOpeningAuthority, "prove_existence", corrupt_one_member_proof)
        blocked = _assess(source, published, ids)

    assert seen["faulted"]
    assert blocked.status is ABST
    assert blocked.reason_codes == (reason,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("fault", ["unknown_member", "duplicate_member"])
def test_corrupt_page_candidate_membership_cannot_vanish_before_rival_filter(monkeypatch, fault):
    """A candidate with unowned or repeated members cannot prove it is disjoint from a nominated strip."""
    from pb_physical_opening_authority import PhysicalOpeningAuthority

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    before = _shape(source)
    original = PhysicalOpeningAuthority.visible_candidate_structures
    seen = {"injected": False}

    def corrupt_page_candidate(self, selector):
        result = original(self, selector)
        assert result.status is CAND and result.candidates
        existing = result.candidates[0]
        members = (("not-a-published-source-observation",) if fault == "unknown_member"
                   else (existing.source_observation_ids[0],) * 2)
        injected = replace(existing, candidate_id="shadow-corrupt-rival", source_observation_ids=members)
        seen["injected"] = True
        return replace(result, candidates=tuple(result.candidates) + (injected,))

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", corrupt_page_candidate)
        blocked = _assess(source, published, ids)
    assert seen["injected"]
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("corrupt_field, foreign_value", [
    ("document_id", "foreign-document"),
    ("revision_id", "foreign-revision"),
    ("source_sha256", "0" * 64),
    ("snapshot_id", "foreign-snapshot"),
    ("page_id", "999"),
    ("status", ABST),
    ("proposition", "foreign-proposition"),
    ("source_observation_ids", ("not-published-on-page",)),
    ("source_observation_ids", ()),
])
def test_foreign_positive_existence_record_cannot_upgrade_strip_shadow(
        monkeypatch, corrupt_field, foreign_value):
    """The wrapper's CORROBORATED status cannot launder an alien source record."""
    from pb_physical_opening_authority import PhysicalOpeningAuthority

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    before = _shape(source)
    original = PhysicalOpeningAuthority.prove_existence
    seen = {"injected": False}

    def foreign_positive(self, selector):
        result = original(self, selector)
        record = result.existence_record
        if not seen["injected"] and record is not None and result.status is EvidenceResolutionStatus.CORROBORATED:
            seen["injected"] = True
            return replace(result, existence_record=replace(record, **{corrupt_field: foreign_value}))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "prove_existence", foreign_positive)
        blocked = _assess(source, published, ids)
    assert seen["injected"]
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("foreign_field, foreign_value", [
    ("observation_id", "foreign-observation"),
    ("document_id", "foreign-document"),
    ("revision_id", "foreign-revision"),
    ("source_sha256", "0" * 64),
    ("snapshot_id", "foreign-snapshot"),
])
def test_foreign_published_source_observation_cannot_launder_positive_strip(
        monkeypatch, foreign_field, foreign_value):
    """A CORROBORATED wrapper does not authenticate an alien same-geometry observation."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    before = _shape(source)
    other = next(oid for oid in published.visible_observation_ids if oid not in ids)
    visibility = source.authority()
    original_resolve = visibility.resolve_visible
    seen = {"injected": False}

    def foreign_observation(selector):
        result = original_resolve(selector)
        if selector.observation_id == other:
            assert result.observation is not None
            seen["injected"] = True
            return replace(result, observation=replace(
                result.observation, **{foreign_field: foreign_value}))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(visibility, "resolve_visible", foreign_observation)
        patch.setattr(source, "authority", lambda: visibility)
        blocked = _assess(source, published, ids)
    assert seen["injected"]
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline


@pytest.mark.parametrize("foreign_field, foreign_value", [
    ("document_id", "foreign-document"),
    ("revision_id", "foreign-revision"),
    ("source_sha256", "0" * 64),
    ("snapshot_id", "foreign-snapshot"),
    ("page_id", "999"),
])
def test_foreign_page_candidate_cannot_launder_positive_strip(
        monkeypatch, foreign_field, foreign_value):
    """Every census candidate must belong to the same immutable source, even if disjoint."""
    from pb_physical_opening_authority import PhysicalOpeningAuthority

    _floor_plan_viewport(monkeypatch)
    source, published, ids = _whole_strip()
    baseline = _assess(source, published, ids)
    assert baseline.status is CAND
    before = _shape(source)
    original_census = PhysicalOpeningAuthority.visible_candidate_structures
    seen = {"injected": False}

    def foreign_candidate(self, selector):
        result = original_census(self, selector)
        assert result.status is CAND and result.candidates
        candidate = replace(result.candidates[0], **{foreign_field: foreign_value})
        seen["injected"] = True
        return replace(result, candidates=(candidate,) + tuple(result.candidates[1:]))

    with monkeypatch.context() as patch:
        patch.setattr(PhysicalOpeningAuthority, "visible_candidate_structures", foreign_candidate)
        blocked = _assess(source, published, ids)
    assert seen["injected"]
    assert blocked.status is ABST
    assert blocked.reason_codes == (A.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert blocked.fragments == () and blocked.terminals == ()
    assert not blocked.takeoff_eligible and not blocked.customer_publication_granted
    assert _shape(source) == before
    assert _assess(source, published, ids) == baseline
