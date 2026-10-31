"""The source adapter on a synthetic PDF, through the real visibility producer and the real aperture authority."""
from __future__ import annotations

import fitz
import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
import pb_structural_whole_opening_aperture_authority as aperture_authority
import pb_vector_geometry_v130 as vector
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
BLACK = (0, 0, 0)
Q = 0.24
# content-stream coordinates start at the bottom of the 300 pt page: this is a line at x=155 across y=190..210 (top-down)
HIDDEN_LINE_CLIP = b"q\n140 90 m 170 90 l 155 110 l h W n\n0 G 0.48 w 155 90 m 155 110 l S\nQ\n"


# an unstroked white fill across the strip, under a clip no producer can prove rectangular (top-down y=192..208)
WHITE_MASK = b"q\n140 90 m 170 90 l 155 110 l h W n\n1 g 145 92 40 16 re f\nQ\n"


def _window_pdf(*, jamb_hi=True, jamb_fill=False, wall_right=True, jamb_opacity=None, hidden_line=False,
                mask=None) -> bytes:
    """A three-panel window along x, 100..304, with two internal posts, heavy end jambs and continuing wall faces."""
    doc = fitz.open()
    page = doc.new_page(width=420, height=300)

    def line(a, b, width=0.48, **kw):
        page.draw_line(a, b, color=BLACK, width=width, **kw)

    for x0, x1 in ((100.0, 160.0), (162.0, 230.0), (232.0, 304.0)):
        line((x0, 200.0), (x1, 200.0))
        line((x0, 200.72), (x1, 200.72))
        line((x0, 200.0), (x0, 200.72))
        line((x1, 200.0), (x1, 200.72))
    opacity = {} if jamb_opacity is None else {"stroke_opacity": jamb_opacity}
    if jamb_fill:
        page.draw_rect(fitz.Rect(99.52, 195.0, 100.48, 205.0), color=None, fill=BLACK)
    else:
        line((100.0, 195.0), (100.0, 205.0), 0.96, **opacity)
    if jamb_hi:
        line((304.0, 195.0), (304.0, 205.0), 0.96)
    line((20.0, 195.0), (100.0, 195.0))
    line((20.0, 205.0), (100.0, 205.0))
    if wall_right:
        line((304.0, 195.0), (380.0, 195.0))
        line((304.0, 205.0), (380.0, 205.0))
    if hidden_line or mask:
        contents = page.get_contents()
        original = b"\n".join(doc.xref_stream(xref) for xref in contents)
        if hidden_line:
            original = original + b"\n" + HIDDEN_LINE_CLIP
        if mask == "before":
            original = WHITE_MASK + b"\n" + original
        elif mask == "after":
            original = original + b"\n" + WHITE_MASK
        doc.update_stream(contents[0], original)
        for xref in contents[1:]:
            doc.update_stream(xref, b"")
    payload = doc.tobytes()
    doc.close()
    return payload


def _publish(payload: bytes):
    source = SourceVisibilityProducer(producer_method="strip-whole-aperture-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="window-doc", source_bytes=payload, source_locator="memory://w.pdf")
    return source, published


def _geometry_ids(source, published) -> dict:
    out = {}
    authority = source.authority()
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(ObservationSelector(
            published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
            published.snapshot.snapshot_id, observation_id))
        g = result.observation.geometry
        out[frozenset(((round(g[0], 3), round(g[1], 3)), (round(g[2], 3), round(g[3], 3))))] = observation_id
    return out


def _nomination(source, published, *, frame=(100.0, 304.0), band=(197.0, 203.0), ink=None):
    if ink is None:
        ink = tuple(sorted(oid for key, oid in _geometry_ids(source, published).items()
                           if all(99.9 <= x <= 304.1 and 199.9 <= y <= 200.8 for x, y in key)))
    assert ink
    return shadow.StripNomination("strip-1", "H", band, frame, True, ink, None,
                                  (shadow.CalloutClaim("W1", "tag-1", "corr-1"),))


def _audit(source, published, nomination, *, enabled=True, page=1):
    return shadow.StripWholeApertureCorrespondenceShadow(source, enabled=enabled).audit(
        revision_id=published.revision.revision_id, plan_page_id=page, nominations=[nomination], coordinate_quantum_pt=Q)


@pytest.fixture(scope="module")
def clean():
    source, published = _publish(_window_pdf())
    return source, published, _nomination(source, published)


# ---- default off -------------------------------------------------------------------------------------------------
class _Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"a disabled shadow must not touch the source ({name})")


def test_default_off_touches_nothing_and_says_so():
    out = shadow.StripWholeApertureCorrespondenceShadow(_Untouchable()).audit(
        revision_id="r", plan_page_id=1, nominations=[], coordinate_quantum_pt=Q)
    assert out.page_reason_codes == (shadow.WHOLE_APERTURE_CORRESPONDENCE_DISABLED,) and out.correspondences == ()
    assert out.ownership is None and out.shadow_only is True


@pytest.mark.parametrize("flag", [1, "yes", None])
def test_enabled_must_be_an_explicit_bool(flag):
    with pytest.raises(TypeError):
        shadow.StripWholeApertureCorrespondenceShadow(object(), enabled=flag)


def test_malformed_arguments_are_refused(clean):
    source, published, nom = clean
    shadowed = shadow.StripWholeApertureCorrespondenceShadow(source, enabled=True)
    rid = published.revision.revision_id
    for kwargs in ({"revision_id": 5}, {"plan_page_id": "1"}, {"plan_page_id": True}, {"nominations": "abc"}):
        arguments = {"revision_id": rid, "plan_page_id": 1, "nominations": [nom], "coordinate_quantum_pt": Q, **kwargs}
        with pytest.raises(ValueError):
            shadowed.audit(**arguments)


# ---- the clean window -----------------------------------------------------------------------------------------------
def test_a_clean_window_is_corresponded_to_the_one_whole_aperture_record(clean):
    source, published, nom = clean
    out = _audit(source, published, nom)
    c = out.correspondences[0]
    assert c.status is CAND, (c.reason_codes, [(r.relation, r.authority_status.value) for r in c.relations])
    assert c.linkage_basis == shadow.LINKAGE_SPAN_EQUALITY_ONLY
    assert len(c.equal_record_ids) == 1 and c.unvetoed_rival_record_ids == ()
    assert out.ownership == shadow.ApertureOwnership(
        published.revision.document_id, published.revision.revision_id, published.snapshot.snapshot_id,
        published.revision.source_sha256, "1")
    assert out.input_provenance == shadow.PRODUCER_INPUT_PROVENANCE and out.standing_limits == shadow.STANDING_LIMITS
    counts = dict(out.stroke_counts)
    assert counts["stroked"] == 18 and "native_segment_not_admitted" not in counts
    assert out.page_reason_codes == ()


def test_the_authority_receives_only_the_strokes_the_producer_authenticated(clean, monkeypatch):
    source, published, nom = clean
    captured = {}
    original = aperture_authority.StructuralWholeOpeningApertureProducer.analyze_page

    def spy(self, seed, records, **kw):
        captured["seed"], captured["records"] = seed, list(records)
        return original(self, seed, records, **kw)

    monkeypatch.setattr(aperture_authority.StructuralWholeOpeningApertureProducer, "analyze_page", spy)
    _audit(source, published, nom)
    records = captured["records"]
    assert {r.observation_id for r in records} == set(published.visible_observation_ids)
    assert all(type(r) is aperture_authority.ApertureSourceStroke and not r.is_fill_mask and not r.is_clipped for r in records)
    assert sorted({round(r.stroke_width, 2) for r in records}) == [0.48, 0.96]
    assert all(r.stroke_rgb == (0.0, 0.0, 0.0) and r.stroke_opacity == 1.0 for r in records)
    assert captured["seed"].observation_id in set(published.visible_observation_ids)
    assert str(captured["seed"].page_id) == "1"


def test_replay_is_identical_and_the_source_is_not_mutated(clean):
    source, published, nom = clean
    before = (source.published_snapshot_for_revision(published.revision.revision_id), published.visible_observation_ids)
    first, second = _audit(source, published, nom), _audit(source, published, nom)
    assert first == second
    assert (source.published_snapshot_for_revision(published.revision.revision_id), published.visible_observation_ids) == before


def test_an_independent_ingest_of_the_same_bytes_gives_the_same_decision(clean):
    source, published, nom = clean
    again_source, again = _publish(_window_pdf())
    again_nom = _nomination(again_source, again)
    a, b = _audit(source, published, nom).correspondences[0], _audit(again_source, again, again_nom).correspondences[0]
    assert (a.status, a.reason_codes, a.linkage_basis) == (b.status, b.reason_codes, b.linkage_basis)


# ---- what the real authority cannot prove, the correspondence abstains on ------------------------------------------------
@pytest.mark.parametrize("variant, expected", [
    ({"jamb_hi": False}, {shadow.EQUAL_EXTENT_STRUCTURE_NOT_PROVEN}),            # no far terminal jamb
    ({"jamb_fill": True}, {shadow.EQUAL_EXTENT_STRUCTURE_NOT_PROVEN}),            # an unstroked fill edge is not a jamb
    ({"jamb_opacity": 0.5}, {shadow.EQUAL_EXTENT_STRUCTURE_NOT_PROVEN}),          # translucent paint is not proven paint
    ({"wall_right": False}, {shadow.EQUAL_EXTENT_STRUCTURE_NOT_PROVEN}),          # no wall continues beyond the far jamb
])
def test_a_window_the_authority_cannot_prove_is_not_corresponded(variant, expected):
    source, published = _publish(_window_pdf(**variant))
    c = _audit(source, published, _nomination(source, published)).correspondences[0]
    assert c.status is ABST and c.linkage_basis is None
    assert expected <= set(c.reason_codes), c.reason_codes


def test_source_ink_the_producer_did_not_admit_inside_the_strip_stops_the_correspondence():
    source, published = _publish(_window_pdf(hidden_line=True))
    c = _audit(source, published, _nomination(source, published)).correspondences[0]
    assert c.status is ABST and shadow.UNADMITTED_INK_IN_STRIP_REGION in c.reason_codes
    out = _audit(source, published, _nomination(source, published))
    assert dict(out.stroke_counts)["native_segment_not_admitted"] == 1


def test_a_white_mask_the_producer_cannot_admit_is_cleared_only_when_it_is_painted_before_the_window_ink():
    source, published = _publish(_window_pdf(mask="before"))
    out = _audit(source, published, _nomination(source, published))
    assert dict(out.stroke_counts)["native_segment_not_admitted"] == 4          # the mask's edges are not admitted ink
    assert out.correspondences[0].status is CAND

    source, published = _publish(_window_pdf(mask="after"))
    out = _audit(source, published, _nomination(source, published))
    assert dict(out.stroke_counts)["native_segment_not_admitted"] == 4
    c = out.correspondences[0]
    assert c.status is ABST and shadow.UNADMITTED_INK_IN_STRIP_REGION in c.reason_codes


def test_a_nomination_naming_ink_the_producer_never_published_abstains(clean):
    source, published, nom = clean
    ghost = shadow.StripNomination("strip-1", "H", nom.band, nom.frame_along, True, nom.ink_ids + ("not-an-observation",),
                                   None, nom.claims)
    c = _audit(source, published, ghost).correspondences[0]
    assert c.status is ABST and shadow.STRIP_INK_NOT_IN_STROKE_INVENTORY in c.reason_codes


def test_a_strip_extent_that_is_not_the_windows_is_not_corresponded(clean):
    source, published, nom = clean
    for frame in ((100.0, 232.0), (162.0, 304.0), (90.0, 314.0)):
        shorter = shadow.StripNomination("strip-1", "H", nom.band, frame, True, nom.ink_ids, None, nom.claims)
        assert _audit(source, published, shorter).correspondences[0].status is not CAND


# ---- the producer's own integrity gates -------------------------------------------------------------------------------
def test_a_primitive_that_no_longer_matches_its_observation_makes_the_inventory_incomplete(clean, monkeypatch):
    source, published, nom = clean
    real = vector.extract_native_page

    def tampered(page, *a, **kw):
        page_data = real(page, *a, **kw)
        segments = [dict(s) for s in page_data["segments"]]
        segments[0]["x2"] = segments[0]["x2"] + 3.0
        return {**page_data, "segments": segments}

    monkeypatch.setattr(vector, "extract_native_page", tampered)
    out = _audit(source, published, nom)
    assert dict(out.stroke_counts)["primitive_join_failed"] >= 1
    assert out.correspondences[0].status is ABST
    assert shadow.PAGE_STROKE_INVENTORY_INCOMPLETE in out.correspondences[0].reason_codes


def test_a_stroke_whose_width_cannot_be_read_makes_the_inventory_incomplete(clean, monkeypatch):
    source, published, nom = clean
    real = vector.extract_native_page

    def tampered(page, *a, **kw):
        page_data = real(page, *a, **kw)
        segments = [dict(s) for s in page_data["segments"]]
        segments[0]["width"] = float("nan")
        return {**page_data, "segments": segments}

    monkeypatch.setattr(vector, "extract_native_page", tampered)
    out = _audit(source, published, nom)
    assert dict(out.stroke_counts)["stroke_width_unresolved"] >= 1 and out.correspondences[0].status is ABST


def test_bytes_that_fail_their_sha_check_abstain(clean, monkeypatch):
    source, published, nom = clean
    rid = published.revision.revision_id
    monkeypatch.setitem(source._producer._store.source_bytes_by_revision, rid, _window_pdf(jamb_hi=False))
    out = _audit(source, published, nom)
    assert out.page_reason_codes == (shadow.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)
    assert out.correspondences[0].status is ABST


def test_a_page_the_producer_did_not_decode_and_an_unknown_revision_abstain(clean):
    source, published, nom = clean
    assert _audit(source, published, nom, page=2).page_reason_codes == (shadow.VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    out = shadow.StripWholeApertureCorrespondenceShadow(source, enabled=True).audit(
        revision_id="no-such-revision", plan_page_id=1, nominations=[nom], coordinate_quantum_pt=Q)
    assert out.page_reason_codes == (shadow.VISIBLE_SOURCE_AUTHORITY_REQUIRED,) and out.ownership is None


def test_a_page_without_any_admitted_stroke_abstains():
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    source, published = _publish(doc.tobytes())
    nom = shadow.StripNomination("strip-1", "H", (1.0, 2.0), (10.0, 20.0), True, ("x",), None,
                                 (shadow.CalloutClaim("W1", "t", "c"),))
    out = _audit(source, published, nom)
    assert out.correspondences[0].status is ABST
    assert out.correspondences[0].reason_codes == (shadow.VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_every_grant_stays_false_on_a_real_run(clean):
    source, published, nom = clean
    out = _audit(source, published, nom)
    assert all(getattr(out, name) is False for name in shadow._GRANT_FLAGS)
