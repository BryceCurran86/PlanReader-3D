"""The strip face-family shadow through the real producer on synthetic PDFs (no caller-built records)."""
from __future__ import annotations

import inspect
from dataclasses import fields, replace

import fitz
import pytest

import pb_source_visibility_authority as visibility_module
import pb_strip_face_family_shadow as F
import pb_vector_geometry_v130 as vector
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
Q = 0.24
BLACK = (0, 0, 0)
W = 0.48
# the strip: x 200..404, band y 300..305.52
LO, HI, B0, B1 = 200.0, 404.0, 300.0, 305.52


class Sheet:
    """Two-page synthetic sheet; pages are fetched by index because PyMuPDF orphans a page once another is added."""

    def __init__(self, size=(900.0, 700.0)):
        self.size = size
        self.doc = fitz.open()
        self.doc.new_page(width=size[0], height=size[1])
        self.doc.new_page(width=size[0], height=size[1])

    def line(self, a, b, page=0, width=W, color=BLACK, dashes=None, times=1, opacity=None):
        extra = {} if opacity is None else {"stroke_opacity": opacity}
        for _ in range(times):
            self.doc[page].draw_line(fitz.Point(*a), fitz.Point(*b), color=color, width=width, dashes=dashes, **extra)

    def strip(self, lo=LO, hi=HI, n0=B0, depth=B1 - B0, page=0):
        """A horizontal window strip: two long frame lines and the two end ticks."""
        for y in (n0, n0 + depth):
            self.line((lo, y), (hi, y), page=page)
        for x in (lo, hi):
            self.line((x, n0), (x, n0 + depth), page=page)

    def pdf(self) -> bytes:
        return self.doc.tobytes()


def _publish(sheet):
    source = SourceVisibilityProducer(producer_method="strip-face-family-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="strip-face-family", source_bytes=sheet.pdf(), source_locator="memory://strip-face-family")
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


def _scene(build=None):
    sheet = Sheet()
    sheet.strip()
    if build is not None:
        build(sheet)
    source, published = _publish(sheet)
    return source, published, _ids_in(source, published, (LO, B0, HI, B1))


def _gap_scene(through=False):
    """A jamb-bounded void: wall faces broken once, jambs at both ends, glazing between (optionally a face runs on)."""
    sheet = Sheet()
    for y in (300.0, 305.52):
        sheet.line((50.0, y), (150.0, y))
        sheet.line((354.0, y), (454.0, y))
    sheet.line((150.0, 300.0), (150.0, 305.52))
    sheet.line((354.0, 300.0), (354.0, 305.52))
    for y in (301.5, 304.0):
        sheet.line((150.0, y), (354.0, y))
    for x in (150.0, 250.0, 354.0):
        sheet.line((x, 301.5), (x, 304.0))
    if through:
        sheet.line((50.0, 310.0), (454.0, 310.0))
    source, published = _publish(sheet)
    return source, published, _ids_in(source, published, (150.0, 301.4, 354.0, 304.1))


def _patch_resolve(monkeypatch, mutate):
    """Wrap the producer-owned visible-observation resolver: `mutate(observation_id, result)` returns the result."""
    real = visibility_module.SourceVisibilityAuthority.resolve_visible

    def wrapped(self, selector):
        return mutate(selector.observation_id, real(self, selector))

    monkeypatch.setattr(visibility_module.SourceVisibilityAuthority, "resolve_visible", wrapped)


def _patch_primitives(monkeypatch, mutate):
    """Wrap the producer's native page extraction: `mutate(segments)` returns the segment list the adapter sees."""
    real = vector.extract_native_page

    def wrapped(page):
        out = real(page)
        out["segments"] = mutate([dict(s) for s in out["segments"]])
        return out

    monkeypatch.setattr(vector, "extract_native_page", wrapped)


def _audit(source, published, ids, enabled=True, page_id=1):
    return F.StripFaceFamilyShadow(source, enabled=enabled).audit(
        revision_id=published.revision.revision_id, page_id=page_id, nominated_observation_ids=ids,
        coordinate_quantum_pt=Q)


def _outside(got):
    return [g for g in got.groups if not g.inside_band]


# --- gate -----------------------------------------------------------------------------------------


def test_the_shadow_is_off_by_default_and_a_disabled_call_touches_nothing():
    source, published, ids = _scene()
    shadow = F.StripFaceFamilyShadow(source)
    got = shadow.audit(revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
                       coordinate_quantum_pt=Q)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_DISABLED,) and got.ownership is None
    assert got.evidence_atoms == () and got.groups == () and got.nominated_strokes == ()
    assert source._physical_opening_authority_cache is None
    bad_arguments = shadow.audit(revision_id=1, page_id="x", nominated_observation_ids="abc", coordinate_quantum_pt=-1)
    assert bad_arguments.reason_codes == (F.FACE_FAMILY_DISABLED,)        # a disabled shadow reads nothing, not even args


@pytest.mark.parametrize("bad", [1, 0, None, "true", [], {}])
def test_the_gate_must_be_a_strict_boolean_and_the_source_the_concrete_producer(bad):
    source, _, _ = _scene()
    with pytest.raises(ValueError):
        F.StripFaceFamilyShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        F.StripFaceFamilyShadow(object(), enabled=True)


def test_there_is_no_caller_channel_for_widths_roles_colours_or_provenance():
    signature = inspect.signature(F.StripFaceFamilyShadow.audit)
    assert [p for p in signature.parameters if p != "self"] == [
        "revision_id", "page_id", "nominated_observation_ids", "coordinate_quantum_pt"]
    source, published, ids = _scene()
    with pytest.raises(TypeError):
        F.StripFaceFamilyShadow(source, enabled=True).audit(
            revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
            coordinate_quantum_pt=Q, stroke_width=0.96)


# --- the face family through the producer ------------------------------------------------------------------


def test_a_continuous_face_line_through_the_strip_is_a_candidate_with_the_producers_own_width_and_colour(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0), width=0.96))
    got = _audit(source, published, ids)
    assert got.status is CAND and got.reason_codes == (F.FACE_FAMILY_CONTINUOUS,)
    assert got.axis == "H" and got.along_extent == pytest.approx((LO, HI), abs=0.01)
    assert got.band_extent == pytest.approx((B0, B1), abs=0.01) and got.viewport_id == "vp-0"
    (g,) = _outside(got)
    assert g.offset_pt == pytest.approx(-4.0, abs=0.01) and g.stroke_width == pytest.approx(0.96)
    assert g.stroke_rgb == (0.0, 0.0, 0.0) and g.black and g.solid is True and g.role_verified
    assert g.covers_whole_extent and g.through_both_terminals and g.nominated_member_ids == ()
    assert len(g.along_intervals) == 1 and g.along_intervals[0] == pytest.approx((100.0, 600.0), abs=0.01)
    assert got.continuous_group_ids == (g.group_id,)
    # the strip's own four strokes are the nominated, role-verified, in-band evidence
    assert len(got.nominated_strokes) == 4 and all(s.role_verified for s in got.nominated_strokes)
    assert {round(s.stroke_width, 2) for s in got.nominated_strokes} == {W}
    assert all(group.inside_band for group in got.groups if group.nominated_member_ids)
    assert (got.ownership.document_id, got.ownership.revision_id, got.ownership.source_sha256,
            got.ownership.snapshot_id, got.ownership.page_id) == (
        published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
        published.snapshot.snapshot_id, "1")
    assert got.standing_limits == F.STANDING_LIMITS
    for flag in F._GRANT_FLAGS:
        assert getattr(got, flag) is False


def test_a_face_line_broken_at_the_strip_is_not_a_candidate_and_the_break_is_inventoried(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.line((100.0, 296.0), (LO, 296.0))
        s.line((HI, 296.0), (600.0, 296.0))

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    (g,) = _outside(got)
    assert not g.covers_whole_extent and not g.through_both_terminals and len(g.member_observation_ids) == 2
    assert len(g.along_intervals) == 2
    assert len(g.uncovered_within_extent) == 1
    assert g.uncovered_within_extent[0] == pytest.approx((LO, HI), abs=0.01)


def test_a_face_line_stopping_short_of_one_terminal_and_a_line_on_each_side(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.line((100.0, 296.0), (350.0, 296.0))                 # stops 54 pt short of the hi terminal
        s.line((100.0, 310.52), (600.0, 310.52))               # a clean through line on the other side

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    assert got.status is CAND and len(got.continuous_group_ids) == 1
    short, through = _outside(got)
    assert short.offset_pt == pytest.approx(-4.0, abs=0.01) and through.offset_pt == pytest.approx(5.0, abs=0.01)
    assert short.extends_past_lo and not short.extends_past_hi and not short.covers_whole_extent
    assert through.group_id == got.continuous_group_ids[0]


def test_double_ink_and_collinear_splitting_do_not_change_the_group_flags(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    plain_source, plain_pub, plain_ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    plain = _outside(_audit(plain_source, plain_pub, plain_ids))[0]

    def doubled(s):
        s.line((100.0, 296.0), (600.0, 296.0), times=2)

    def split(s):
        for a, b in ((100.0, 260.0), (260.0, 330.0), (330.0, 600.0)):
            s.line((a, 296.0), (b, 296.0))

    for build, members in ((doubled, 2), (split, 3)):
        source, published, ids = _scene(build)
        got = _audit(source, published, ids)
        (g,) = _outside(got)
        assert got.status is CAND
        assert len(g.member_observation_ids) == members            # double ink and split pieces are all retained
        assert (g.covers_whole_extent, g.through_both_terminals, g.uncovered_within_extent) == (
            plain.covers_whole_extent, plain.through_both_terminals, plain.uncovered_within_extent)
        assert len(g.along_intervals) == 1 and g.along_intervals[0] == pytest.approx(plain.along_intervals[0], abs=0.01)
        assert g.offset_pt == pytest.approx(plain.offset_pt, abs=1e-6)


def test_dashed_grey_and_thick_through_lines_are_inventoried_with_their_producer_verified_attributes(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.line((100.0, 280.0), (600.0, 280.0), dashes="[4 2] 0")
        s.line((100.0, 285.0), (600.0, 285.0), color=(0.5, 0.5, 0.5))
        s.line((100.0, 290.0), (600.0, 290.0), width=1.44)

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    dashed, grey, thick = _outside(got)
    assert dashed.solid is False and dashed.through_both_terminals and dashed.black
    assert grey.black is False and grey.stroke_rgb == pytest.approx((0.5, 0.5, 0.5), abs=1e-3)
    assert thick.stroke_width == pytest.approx(1.44) and thick.black and thick.solid is True
    # only the solid black line is the face family; the dashed and grey ones are retained but never promoted
    assert got.status is CAND and got.continuous_group_ids == (thick.group_id,)
    assert dashed.group_id not in got.continuous_group_ids and grey.group_id not in got.continuous_group_ids


def test_a_through_line_and_a_thicker_stub_at_one_offset_is_a_conflict_with_both_retained(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.line((100.0, 296.0), (600.0, 296.0), width=0.48)
        s.line((300.0, 296.0), (310.0, 296.0), width=0.96)

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    assert got.status is CONF and F.FACE_FAMILY_SAME_OFFSET_BROKEN in got.reason_codes
    assert sorted(round(g.stroke_width, 2) for g in _outside(got)) == [0.48, 0.96]
    assert len(got.conflicted_group_ids) == 2 and got.continuous_group_ids == ()


def test_a_fill_only_shape_edge_is_grouped_without_an_invented_stroke_width(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.doc[0].draw_rect(fitz.Rect(100.0, 290.0, 600.0, 290.0 + 4.0), color=None, fill=(0, 0, 0))

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    unverified = [g for g in got.groups if not g.role_verified]
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    assert sorted(round(g.offset_pt, 2) for g in unverified) == [-10.0, -6.0]        # both long edges are inventoried
    for g in unverified:
        assert g.stroke_width is None and g.stroke_rgb is None and g.solid is None
        assert g.through_both_terminals and not g.black                               # through, yet never the face family


def test_a_jamb_bounded_void_has_no_face_family_through_it_and_a_continuous_neighbour_line_is_reported(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _gap_scene()
    got = _audit(source, published, ids)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)
    faces = _outside(got)
    assert [round(g.offset_pt, 2) for g in faces] == [-1.5, 1.52]
    assert all(not g.covers_whole_extent and not g.extends_past_lo and not g.extends_past_hi for g in faces)
    for g in faces:
        assert len(g.along_intervals) == 2 and len(g.uncovered_within_extent) == 1
        assert g.uncovered_within_extent[0] == pytest.approx((150.0, 354.0), abs=0.01)
    through_source, through_pub, through_ids = _gap_scene(through=True)
    carried = _audit(through_source, through_pub, through_ids)
    assert carried.status is CAND and len(carried.continuous_group_ids) == 1
    (line,) = [g for g in carried.groups if g.group_id in carried.continuous_group_ids]
    assert line.offset_pt == pytest.approx(6.0, abs=0.02) and line.through_both_terminals


# --- viewport ------------------------------------------------------------------------------------------


def test_without_an_authenticated_floor_plan_viewport_there_is_no_verdict():
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    got = _audit(source, published, ids)                      # a synthetic page has no segmentation at all
    assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
    assert got.groups == () and got.viewport_id is None


@pytest.mark.parametrize("kwargs", [
    dict(view_type="elevation"),
    dict(boxes=((10.0, 10.0, 890.0, 690.0), (100.0, 100.0, 800.0, 600.0))),      # two floor plans own the strip
    dict(boxes=((10.0, 10.0, 300.0, 690.0),)),                                    # the strip is cropped by the viewport
])
def test_non_floor_plan_competing_or_cropping_viewports_abstain(monkeypatch, kwargs):
    _floor_plan_viewport(monkeypatch, **kwargs)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    got = _audit(source, published, ids)
    assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)


def test_a_larger_viewport_changes_nothing_and_content_outside_it_is_still_inventoried(monkeypatch):
    def build(s):
        s.line((100.0, 296.0), (600.0, 296.0))
        s.line((20.0, 20.0), (880.0, 20.0))                   # a sheet-border style line, far from the strip

    _floor_plan_viewport(monkeypatch, boxes=((190.0, 250.0, 420.0, 350.0),))
    source, published, ids = _scene(build)
    tight = _audit(source, published, ids)
    _floor_plan_viewport(monkeypatch, boxes=((0.0, 0.0, 900.0, 700.0),))
    wide = _audit(source, published, ids)
    assert tight.status is wide.status is CAND
    assert [(g.offset_pt, g.member_observation_ids) for g in tight.groups] == [
        (g.offset_pt, g.member_observation_ids) for g in wide.groups]
    assert len(_outside(tight)) == 2                          # the distant line is inventoried, with its large offset
    assert min(g.offset_pt for g in tight.groups) == pytest.approx(-280.0, abs=0.01)


# --- ownership -----------------------------------------------------------------------------------------


def test_unknown_foreign_page_or_stale_inputs_abstain(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    assert _audit(source, published, ids + ("not-an-observation",)).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert _audit(source, published, ()).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert _audit(source, published, ids + (ids[0],)).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert _audit(source, published, ids, page_id=2).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)   # ids of page 1
    assert _audit(source, published, ids, page_id=9).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)  # not decoded
    shadow = F.StripFaceFamilyShadow(source, enabled=True)
    unknown = shadow.audit(revision_id="no-such-revision", page_id=1, nominated_observation_ids=ids,
                           coordinate_quantum_pt=Q)
    assert unknown.status is ABST and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    for bad in (dict(revision_id=1), dict(page_id="1"), dict(page_id=True), dict(coordinate_quantum_pt=0.0),
                dict(coordinate_quantum_pt=float("nan")), dict(nominated_observation_ids="abc"),
                dict(nominated_observation_ids=(1,))):
        args = dict(revision_id=published.revision.revision_id, page_id=1, nominated_observation_ids=ids,
                    coordinate_quantum_pt=Q)
        args.update(bad)
        with pytest.raises(ValueError):
            shadow.audit(**args)


def test_nominated_ids_from_another_page_of_the_same_revision_do_not_inherit_this_pages_inventory(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    sheet = Sheet()
    sheet.strip()
    sheet.strip(page=1)
    sheet.line((100.0, 296.0), (600.0, 296.0), page=1)
    source, published = _publish(sheet)
    page1 = _ids_in(source, published, (LO, B0, HI, B1), page="1")
    page2 = _ids_in(source, published, (LO, B0, HI, B1), page="2")
    assert set(page1).isdisjoint(page2)
    first, second = _audit(source, published, page1, page_id=1), _audit(source, published, page2, page_id=2)
    assert first.status is ABST and first.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,)     # page 1 has no face line
    assert second.status is CAND                                                              # page 2 does
    assert first.ownership.page_id == "1" and second.ownership.page_id == "2"
    assert _audit(source, published, page2, page_id=1).reason_codes == (F.NOMINATION_NOT_VISIBLE_ON_PAGE,)


def test_a_later_revision_makes_the_earlier_nomination_stale(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene()
    other = Sheet()
    other.strip(hi=410.0)
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id, source_bytes=other.pdf(),
                                   source_locator="memory://strip-face-family-2")
    got = _audit(source, published, ids)
    assert got.status is ABST and got.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_a_translucent_black_line_is_inventoried_with_its_opacity_and_is_never_a_continuous_black_face(monkeypatch):
    _floor_plan_viewport(monkeypatch)

    def build(s):
        s.line((100.0, 296.0), (600.0, 296.0), opacity=0.2)             # black, the stated width, but 20% ink

    source, published, ids = _scene(build)
    got = _audit(source, published, ids)
    (faint,) = _outside(got)
    assert faint.opaque is False and faint.black and faint.solid is True and faint.role_verified
    assert faint.through_both_terminals and faint.stroke_width == pytest.approx(W)
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,) and got.continuous_group_ids == ()
    assert {s.opaque for s in got.nominated_strokes} == {True}           # the strip's own ink is opaque

    def both(s):
        s.line((100.0, 296.0), (600.0, 296.0))
        s.line((300.0, 296.0), (310.0, 296.0), opacity=0.2)             # a faint stub on the same line
    source2, published2, ids2 = _scene(both)
    mixed = _audit(source2, published2, ids2)
    assert mixed.status is CONF and {g.opaque for g in _outside(mixed)} == {True, False}


def test_a_primitive_that_disagrees_with_the_observation_geometry_leaves_the_nominated_role_unproven(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene()
    import pb_vector_geometry_v130 as vector

    real = vector.extract_native_page

    def perturbed(page):
        out = real(page)
        first = sorted(out["segments"], key=lambda s: s["id"])[0]
        first["x2"] = float(first["x2"]) + 1.0
        return out

    monkeypatch.setattr(vector, "extract_native_page", perturbed)
    got = _audit(source, published, ids)
    assert got.status is ABST and F.SOURCE_ROLE_UNPROVEN in got.reason_codes


# --- the census is fail-closed: no published observation is ever quietly skipped -------------------------


def _stub_scene():
    """A thin line through the strip plus a thicker stub of it: the stub is the rival that must never go missing."""
    def build(s):
        s.line((100.0, 296.0), (600.0, 296.0), width=0.48)
        s.line((300.0, 296.0), (310.0, 296.0), width=0.96)
    source, published, ids = _scene(build)
    (stub,) = _ids_in(source, published, (299.9, 295.9, 310.1, 296.1))
    return source, published, ids, stub


def test_a_published_observation_that_cannot_be_resolved_fails_the_call_instead_of_hiding_a_rival(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()
    assert _audit(source, published, ids).status is CONF                  # with the stub present the offset is contested

    def fail(observation_id, result):
        if observation_id == stub:
            return replace(result, status=EvidenceResolutionStatus.CONFLICT)
        return result

    _patch_resolve(monkeypatch, fail)
    got = _audit(source, published, ids)
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert got.groups == () and got.continuous_group_ids == ()            # never a clean CANDIDATE from the survivors


def test_a_failed_observation_on_another_page_of_the_revision_also_fails_the_call(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    sheet = Sheet()
    sheet.strip()
    sheet.line((100.0, 296.0), (600.0, 296.0))
    sheet.line((50.0, 50.0), (60.0, 50.0), page=1)
    source, published = _publish(sheet)
    ids = _ids_in(source, published, (LO, B0, HI, B1))
    (other,) = _ids_in(source, published, (49.9, 49.9, 60.1, 50.1), page="2")
    assert _audit(source, published, ids).status is CAND

    def fail(observation_id, result):
        return replace(result, status=EvidenceResolutionStatus.CONFLICT) if observation_id == other else result

    _patch_resolve(monkeypatch, fail)
    assert _audit(source, published, ids).reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


@pytest.mark.parametrize("field,value", [
    ("snapshot_id", "another-snapshot"), ("revision_id", "another-revision"), ("document_id", "another-document"),
    ("source_sha256", "b" * 64), ("observation_id", "another-observation"),
])
def test_an_observation_wrapper_for_a_foreign_identity_is_an_integrity_failure(monkeypatch, field, value):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()

    def foreign(observation_id, result):
        if observation_id == stub and result.observation is not None:
            return replace(result, observation=replace(result.observation, **{field: value}))
        return result

    _patch_resolve(monkeypatch, foreign)
    assert _audit(source, published, ids).reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


@pytest.mark.parametrize("change", [
    dict(geometry=(1.0, 2.0, 3.0)), dict(geometry=(1.0, 2.0, float("nan"), 2.0)), dict(observation_kind="native_pdf_text"),
])
def test_a_same_page_observation_that_is_malformed_or_not_a_native_segment_is_an_integrity_failure(monkeypatch, change):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()

    def malformed(observation_id, result):
        if observation_id == stub and result.observation is not None:
            return replace(result, observation=replace(result.observation, **change))
        return result

    _patch_resolve(monkeypatch, malformed)
    assert _audit(source, published, ids).reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


def test_an_observation_without_a_native_primitive_is_an_integrity_failure(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()
    assert _audit(source, published, ids).status is CONF
    seen = []

    def drop_the_last(segments):
        seen.append(len(segments))
        return segments[:-1]                                              # some page primitive no longer exists

    _patch_primitives(monkeypatch, drop_the_last)
    got = _audit(source, published, ids)
    assert seen and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.groups == ()


def test_two_primitives_sharing_one_id_are_an_integrity_failure_not_a_last_one_wins_join(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()

    def duplicate_with_another_geometry(segments):
        # a dict join would quietly keep whichever came last and the observation would join the wrong primitive
        return segments + [dict(segments[0], x2=float(segments[0]["x2"]) + 1.0)]

    _patch_primitives(monkeypatch, duplicate_with_another_geometry)
    got = _audit(source, published, ids)
    assert got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.groups == ()


def test_a_non_nominated_segment_whose_paint_is_not_proven_stays_in_the_inventory_as_an_unverified_rival(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids, stub = _stub_scene()
    ink = _ids_in(source, published, (99.0, 295.9, 601.0, 296.1))
    (through,) = [i for i in ink if i != stub]
    def unprove(segments):
        for segment in segments:
            if abs(float(segment["x1"]) - 300.0) < 0.01 and abs(float(segment["y1"]) - 296.0) < 0.01:
                segment["x2"] = float(segment["x2"]) + 1.0               # the primitive no longer matches the observation
        return segments

    _patch_primitives(monkeypatch, unprove)
    got = _audit(source, published, ids)
    unverified = [g for g in got.groups if stub in g.member_observation_ids]
    assert len(unverified) == 1 and not unverified[0].role_verified
    assert unverified[0].stroke_width is None and unverified[0].stroke_rgb is None and unverified[0].opaque is None
    assert got.status is CONF and through in {m for g in got.groups for m in g.member_observation_ids}


@pytest.mark.parametrize("attribute", ["solid", "opaque"])
def test_an_attribute_the_producer_does_not_state_is_unknown_never_claimed_and_never_a_through_line(monkeypatch, attribute):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    assert _audit(source, published, ids).status is CAND

    def withhold(segments):
        for segment in segments:
            if abs(float(segment["y1"]) - 296.0) < 0.01:
                if attribute == "solid":
                    segment["dashes"], segment["dashes_present"] = "", False      # no dash pattern is stated
                else:
                    segment["sequence_number"] = -1       # the drawing the producer names is not the one it joins to
        return segments

    _patch_primitives(monkeypatch, withhold)
    got = _audit(source, published, ids)
    (g,) = _outside(got)
    assert getattr(g, attribute) is None and g.role_verified and g.black and g.through_both_terminals
    assert (g.opaque, g.solid) == ((True, None) if attribute == "solid" else (None, True))
    assert got.status is ABST and got.reason_codes == (F.FACE_FAMILY_NOT_OBSERVED,) and got.continuous_group_ids == ()


def test_nominated_ids_may_be_any_collection_and_a_generator_is_not_silently_emptied(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    shadow = F.StripFaceFamilyShadow(source, enabled=True)
    args = dict(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q)
    listed = shadow.audit(nominated_observation_ids=list(ids), **args)
    streamed = shadow.audit(nominated_observation_ids=(i for i in ids), **args)
    assert listed.status is streamed.status is CAND and listed.record_id == streamed.record_id
    assert shadow.audit(nominated_observation_ids=frozenset(ids), **args).record_id == listed.record_id
    with pytest.raises(ValueError):
        shadow.audit(nominated_observation_ids=123, **args)


def test_replay_is_deterministic_input_order_free_and_ids_are_stable(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    first, again = _audit(source, published, ids), _audit(source, published, tuple(reversed(ids)))
    assert first == again and first.record_id == again.record_id and first.nomination_id == again.nomination_id
    assert [g.group_id for g in first.groups] == [g.group_id for g in again.groups]
    # an independent ingest of the same bytes gives the same measurements
    source2, published2, ids2 = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    other = _audit(source2, published2, ids2)
    assert [(g.offset_pt, g.stroke_width, g.through_both_terminals) for g in other.groups] == [
        (g.offset_pt, g.stroke_width, g.through_both_terminals) for g in first.groups]


def test_unrelated_far_content_and_other_pages_change_nothing(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    quiet = _audit(source, published, ids)

    def noisy(s):
        s.line((100.0, 296.0), (600.0, 296.0))
        for k in range(40):
            s.line((700.0 + k, 400.0), (700.0 + k, 450.0))             # vertical, along-disjoint
            s.line((500.0, 400.0 + k), (520.0, 400.0 + k))             # parallel but along-disjoint from the strip
        s.line((100.0, 296.0), (600.0, 296.0), page=1)

    source2, published2, ids2 = _scene(noisy)
    loud = _audit(source2, published2, ids2)
    def measured(result):
        return [(g.offset_pt, g.stroke_width, g.stroke_rgb, g.solid, g.opaque, len(g.member_observation_ids),
                 g.along_intervals, g.through_both_terminals, g.covers_whole_extent, g.uncovered_within_extent)
                for g in result.groups]

    assert measured(loud) == measured(quiet) and len(quiet.groups) == 3
    assert loud.status is quiet.status is CAND


def test_a_rotated_page_is_measured_in_native_coordinates(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    plain_source, plain_pub, plain_ids = _scene(lambda s: s.line((100.0, 296.0), (600.0, 296.0)))
    plain = _audit(plain_source, plain_pub, plain_ids)

    sheet = Sheet()
    sheet.strip()
    sheet.line((100.0, 296.0), (600.0, 296.0))
    sheet.doc[0].set_rotation(90)
    source, published = _publish(sheet)
    ids = _ids_in(source, published, (LO, B0, HI, B1))
    rotated = _audit(source, published, ids)
    assert rotated.axis == plain.axis and rotated.status is plain.status
    assert [(round(g.offset_pt, 2), g.through_both_terminals) for g in rotated.groups] == [
        (round(g.offset_pt, 2), g.through_both_terminals) for g in plain.groups]


# --- the producer is untouched ----------------------------------------------------------------------------


def _shape(obj):
    return {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None) for k, v in sorted(vars(obj).items())
            if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}


def test_the_shadow_changes_no_output_and_no_state_of_the_producer(monkeypatch):
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _gap_scene(through=True)
    before_producer = _shape(source)
    store_before = _shape(source._producer._store)
    assert source._physical_opening_authority_cache is None
    visible_before = tuple(published.visible_observation_ids)
    first = _audit(source, published, ids)
    assert first.status is CAND
    assert _shape(source) == before_producer and _shape(source._producer._store) == store_before
    assert source._physical_opening_authority_cache is None            # no opening authority was ever built
    assert tuple(source.published_snapshot_for_revision(published.revision.revision_id).visible_observation_ids) == visible_before
    # a second shadow, and a second call, leave the same shape
    _audit(source, published, ids)
    assert _shape(source) == before_producer


def test_positive_control_the_state_check_does_see_a_consumer_filling_the_producers_memos(monkeypatch):
    """The equality above is only meaningful if an ordinary consumer call WOULD change that state."""
    _floor_plan_viewport(monkeypatch)
    source, published, ids = _gap_scene()
    _audit(source, published, ids)
    before = _shape(source)
    assert source._physical_opening_authority_cache is None
    authority = source.physical_opening_authority()
    for oid in published.visible_observation_ids:
        authority.prove_existence(_selector(published, oid))
    assert _shape(source) != before and source._physical_opening_authority_cache is not None


def test_the_result_type_cannot_be_mistaken_for_an_existence_record_or_a_host_candidate():
    names = {f.name for f in fields(F.StripFaceFamily)}
    assert not ({"aperture_bbox_pt", "structural_pattern", "host_candidate_id", "candidate_wall_ids_considered",
                 "existence_record", "source_geometry", "host_wall_id", "area_m2", "wall_id", "window_id"} & names)
    assert "existence_record_issued" in names     # explicitly a False grant flag, never a record
