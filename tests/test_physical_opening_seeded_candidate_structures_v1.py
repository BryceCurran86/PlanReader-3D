"""The seeded accessor: the existing six-line enumerator on a universe restricted to the named observations."""
from __future__ import annotations

import ast
import math
from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

REPO = Path(__file__).resolve().parent.parent
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED

# two wall faces that continue on both sides of one gap, and the two jambs at the gap bounds
OPENING = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
)
# glazing inside the gap: frame lines interrupted by a post, and a sill stub collinear with the faces
GLAZING = (
    ((100.0, 103.0), (118.0, 103.0)), ((122.0, 103.0), (140.0, 103.0)),
    ((100.0, 107.0), (118.0, 107.0)), ((122.0, 107.0), (140.0, 107.0)),
    ((118.0, 103.0), (118.0, 107.0)), ((122.0, 103.0), (122.0, 107.0)),
)
STUB = (((112.0, 100.0), (128.0, 100.0)),)


def _transform(point, *, angle_deg, scale, offset):
    angle = math.radians(angle_deg)
    x, y = point
    return (scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0],
            scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1])


def _pdf(segments, *, angle_deg=0.0, scale=1.0, offset=(0.0, 0.0)) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for first, second in segments:
        a = _transform(first, angle_deg=angle_deg, scale=scale, offset=offset)
        b = _transform(second, angle_deg=angle_deg, scale=scale, offset=offset)
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id):
    return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                               published.revision.source_sha256, published.snapshot.snapshot_id, observation_id)


def _fixture(segments, **kw):
    producer = SourceVisibilityProducer(producer_method="seeded-structure-test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(document_id="seeded-doc", source_bytes=_pdf(segments, **kw),
                                                 source_locator="memory://seeded.pdf")
    visibility = producer.authority()
    ids = {}
    for observation_id in published.visible_observation_ids:
        g = visibility.resolve_visible(_selector(published, observation_id)).observation.geometry
        ids[frozenset(((round(g[0], 3), round(g[1], 3)), (round(g[2], 3), round(g[3], 3))))] = observation_id
    return PhysicalOpeningAuthority(visibility), published, ids


def _id_of(ids, segment, **kw):
    a = _transform(segment[0], angle_deg=kw.get("angle_deg", 0.0), scale=kw.get("scale", 1.0), offset=kw.get("offset", (0.0, 0.0)))
    b = _transform(segment[1], angle_deg=kw.get("angle_deg", 0.0), scale=kw.get("scale", 1.0), offset=kw.get("offset", (0.0, 0.0)))
    return ids[frozenset(((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))))]


def _opening_ids(ids, **kw):
    return [_id_of(ids, segment, **kw) for segment in OPENING]


# ---- the same rules, on a smaller universe --------------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)}])
def test_for_a_plain_opening_the_restricted_universe_finds_exactly_what_page_discovery_finds(kw):
    physical, published, ids = _fixture(OPENING, **kw)
    members = _opening_ids(ids, **kw)
    selector = _selector(published, members[4])
    page = physical.visible_candidate_structures(selector)
    seeded = physical.seeded_candidate_structures(selector, members)
    assert seeded.status is CAND and seeded.page_id == page.page_id
    assert [(c.candidate_id, c.source_observation_ids, c.structural_pattern) for c in seeded.candidates] == [
        (c.candidate_id, c.source_observation_ids, c.structural_pattern) for c in page.candidates]
    assert [c.structural_pattern for c in seeded.candidates] == [JAMB_BOUNDED_TWO_FACE_INTERRUPTION]


def test_a_sill_stub_inside_the_gap_blocks_page_discovery_but_not_the_seeded_universe_that_leaves_it_out():
    physical, published, ids = _fixture(OPENING + STUB)
    members = _opening_ids(ids)
    selector = _selector(published, members[4])
    assert not [c for c in physical.visible_candidate_structures(selector).candidates
                if members[4] in c.source_observation_ids]
    seeded = physical.seeded_candidate_structures(selector, members)
    assert [c.structural_pattern for c in seeded.candidates] == [JAMB_BOUNDED_TWO_FACE_INTERRUPTION]
    # the accessor does not look at what it was told to leave out: that is the caller's burden, and naming the stub
    # as a member puts it back into the universe the rules see
    stub_id = _id_of(ids, STUB[0])
    assert not [c for c in physical.seeded_candidate_structures(selector, members + [stub_id]).candidates
                if members[4] in c.source_observation_ids]


def test_glazing_that_is_not_named_cannot_make_the_named_structure_ambiguous():
    physical, published, ids = _fixture(OPENING + GLAZING)
    members = _opening_ids(ids)
    seeded = physical.seeded_candidate_structures(_selector(published, members[5]), members)
    assert len(seeded.candidates) == 1 and set(seeded.candidates[0].source_observation_ids) == set(members)


# ---- it decides nothing -------------------------------------------------------------------------------------------------
def test_it_never_returns_corroborated_or_an_existence_record_and_leaves_prove_existence_alone():
    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    selector = _selector(published, members[4])
    before = physical.prove_existence(selector)
    result = physical.seeded_candidate_structures(selector, members)
    assert result.status is CAND and not hasattr(result, "existence_record")
    assert physical.prove_existence(selector) == before


def test_it_uses_and_writes_none_of_the_per_page_memos():
    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    caches = ("_visible_candidate_cache", "_visible_candidate_membership_cache", "_visible_existence_cache")
    snapshot = {name: dict(getattr(physical, name)) for name in caches if hasattr(physical, name)}
    assert snapshot
    physical.seeded_candidate_structures(_selector(published, members[4]), members)
    assert {name: dict(getattr(physical, name)) for name in snapshot} == snapshot


def test_order_of_the_named_members_and_replay_do_not_change_the_result():
    physical, published, ids = _fixture(OPENING + GLAZING)
    members = _opening_ids(ids)
    selector = _selector(published, members[4])
    first = physical.seeded_candidate_structures(selector, members)
    assert physical.seeded_candidate_structures(selector, list(reversed(members))) == first
    assert physical.seeded_candidate_structures(selector, tuple(members) + tuple(members)) == first


# ---- abstentions ---------------------------------------------------------------------------------------------------------
def test_an_empty_foreign_or_selector_less_member_set_abstains():
    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    selector = _selector(published, members[4])
    for bad in ([], ["no-such-observation"], members + ["no-such-observation"], [m for m in members if m != members[4]]):
        result = physical.seeded_candidate_structures(selector, bad)
        assert result.status is ABST and result.candidates == ()


def test_a_selector_the_authority_cannot_resolve_abstains():
    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    result = physical.seeded_candidate_structures(_selector(published, "not-an-observation"), members)
    assert result.status is not CAND and result.candidates == ()


def test_wrong_argument_types_are_refused():
    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    selector = _selector(published, members[4])
    with pytest.raises(TypeError):
        physical.seeded_candidate_structures("not-a-selector", members)
    with pytest.raises(TypeError):
        physical.seeded_candidate_structures(selector, members[0])


def test_without_a_visibility_authority_it_abstains():
    from pb_source_observation_authority import SourceObservationProducer  # noqa: F401  (the raw path has no visible universe)

    physical, published, ids = _fixture(OPENING)
    members = _opening_ids(ids)
    raw = PhysicalOpeningAuthority.__new__(PhysicalOpeningAuthority)
    raw._source_visibility_authority = None
    result = raw.seeded_candidate_structures(_selector(published, members[4]), members)
    assert result.status is ABST and result.candidates == ()


# ---- who may call it -----------------------------------------------------------------------------------------------------
def test_only_the_aperture_correspondence_calls_the_seeded_accessor():
    callers = []
    for path in sorted(REPO.glob("*.py")):
        if path.name == "pb_physical_opening_authority.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if any(isinstance(node, ast.Attribute) and node.attr == "seeded_candidate_structures" for node in ast.walk(tree)):
            callers.append(path.name)
    assert callers == ["pb_callout_strip_whole_aperture_correspondence_shadow.py"]
