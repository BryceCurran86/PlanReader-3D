"""Proposal tests: layered faces of one gap are ONE opening, and the seeded existence proof (unwired)."""
from __future__ import annotations

import ast
import math
from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    LAYERED_FACES_OF_ONE_GAP,
    PHYSICAL_OPENING_EXISTS,
    SEEDED_OPENING_INK_UNACCOUNTED,
    SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,
    STRUCTURAL_OPENING_EXISTENCE_RESOLVED,
    VISIBLE_WALL_CONTINUATION_REQUIRED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

REPO = Path(__file__).resolve().parent.parent
CORR = EvidenceResolutionStatus.CORROBORATED
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT

PLAIN = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 110.0)), ((140.0, 100.0), (140.0, 110.0)),
)
# a wall drawn in two layers: three face lines split by one gap, a jamb per layer at each end
LAYERED = (
    ((20.0, 100.0), (100.0, 100.0)), ((140.0, 100.0), (220.0, 100.0)),
    ((20.0, 105.0), (100.0, 105.0)), ((140.0, 105.0), (220.0, 105.0)),
    ((20.0, 110.0), (100.0, 110.0)), ((140.0, 110.0), (220.0, 110.0)),
    ((100.0, 100.0), (100.0, 105.0)), ((140.0, 100.0), (140.0, 105.0)),
    ((100.0, 105.0), (100.0, 110.0)), ((140.0, 105.0), (140.0, 110.0)),
)
# the same gap in a second, unrelated wall far away: shares nothing with LAYERED
OTHER_WALL = (
    ((20.0, 300.0), (100.0, 300.0)), ((140.0, 300.0), (220.0, 300.0)),
    ((20.0, 305.0), (100.0, 305.0)), ((140.0, 305.0), (220.0, 305.0)),
    ((100.0, 300.0), (100.0, 305.0)), ((140.0, 300.0), (140.0, 305.0)),
)
GLAZING = (((104.0, 102.0), (136.0, 102.0)), ((104.0, 108.0), (136.0, 108.0)))     # between the outer faces
SILL_STUB = (((112.0, 100.0), (128.0, 100.0)),)                                     # collinear with a face


def _transform(point, *, angle_deg, scale, offset):
    angle = math.radians(angle_deg)
    x, y = point
    return (scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0],
            scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1])


def _pdf(segments, **kw) -> bytes:
    kw = {"angle_deg": 0.0, "scale": 1.0, "offset": (0.0, 0.0), **kw}
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for first, second in segments:
        a, b = _transform(first, **kw), _transform(second, **kw)
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id):
    return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                               published.revision.source_sha256, published.snapshot.snapshot_id, observation_id)


def _fixture(segments, *, producer_owned=True, **kw):
    producer = SourceVisibilityProducer(producer_method="seeded-existence-test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(document_id="seeded-existence-doc", source_bytes=_pdf(segments, **kw),
                                                 source_locator="memory://seeded-existence.pdf")
    visibility = producer.authority()
    ids = {}
    for observation_id in published.visible_observation_ids:
        g = visibility.resolve_visible(_selector(published, observation_id)).observation.geometry
        ids[frozenset(((round(g[0], 2), round(g[1], 2)), (round(g[2], 2), round(g[3], 2))))] = observation_id
    physical = producer.physical_opening_authority() if producer_owned else PhysicalOpeningAuthority(visibility)
    return physical, published, ids, kw


def _ids(ids, segments, kw):
    kw = {"angle_deg": 0.0, "scale": 1.0, "offset": (0.0, 0.0), **kw}
    out = []
    for first, second in segments:
        a, b = _transform(first, **kw), _transform(second, **kw)
        out.append(ids[frozenset(((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))))])
    return out


# ---- the rule: layered faces of one gap are one opening -----------------------------------------------------------------
@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)}])
def test_today_the_page_calls_a_shared_face_ambiguous_and_gives_each_layer_its_own_identity(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    shared_face = physical.prove_existence(_selector(published, members[2]))
    assert shared_face.status is CONF and shared_face.reason_codes == (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,)
    first, second = (physical.prove_existence(_selector(published, members[i])) for i in (6, 8))
    assert first.status is CORR and second.status is CORR
    # one wall opening, two existence identities: the same gap is counted once per pair of layers
    assert first.existence_record.record_id != second.existence_record.record_id


@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)},
                                {"angle_deg": 180.0, "offset": (300.0, 400.0)}])
def test_the_seeded_universe_merges_the_layers_into_one_candidate(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    result = physical.seeded_candidate_structures(_selector(published, members[6]), members)
    assert result.status is CAND and len(result.candidates) == 1
    candidate = result.candidates[0]
    assert set(candidate.source_observation_ids) == set(members)
    assert candidate.structural_pattern == JAMB_BOUNDED_TWO_FACE_INTERRUPTION
    assert LAYERED_FACES_OF_ONE_GAP in candidate.reason_codes


def test_structures_of_the_same_gap_that_share_no_line_are_never_merged():
    physical, published, ids, kw = _fixture(LAYERED + OTHER_WALL)
    members = _ids(ids, LAYERED + OTHER_WALL, kw)
    result = physical.seeded_candidate_structures(_selector(published, members[6]), members)
    assert len(result.candidates) == 2
    assert all(LAYERED_FACES_OF_ONE_GAP not in c.reason_codes or len(c.source_observation_ids) == 10
               for c in result.candidates)
    proof = physical.prove_seeded_existence(_selector(published, members[6]), members)
    assert proof.status is CONF and proof.reason_codes == (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,)
    assert proof.existence_record is None


def test_a_plain_opening_is_not_merged_with_anything():
    physical, published, ids, kw = _fixture(PLAIN)
    members = _ids(ids, PLAIN, kw)
    result = physical.seeded_candidate_structures(_selector(published, members[4]), members)
    assert [LAYERED_FACES_OF_ONE_GAP in c.reason_codes for c in result.candidates] == [False]


# ---- the seeded existence proof ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("producer_owned", [True, False])
@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)}])
def test_for_a_plain_opening_the_seeded_proof_issues_the_identical_record_prove_existence_issues(producer_owned, kw):
    physical, published, ids, kw = _fixture(PLAIN, producer_owned=producer_owned, **kw)
    members = _ids(ids, PLAIN, kw)
    selector = _selector(published, members[4])
    page = physical.prove_existence(selector)
    seeded = physical.prove_seeded_existence(selector, members)
    assert page.status is CORR and seeded.status is CORR
    assert seeded.existence_record == page.existence_record
    assert seeded.proposition == PHYSICAL_OPENING_EXISTS and seeded.reason_codes == (STRUCTURAL_OPENING_EXISTENCE_RESOLVED,)


@pytest.mark.parametrize("kw", [{}, {"scale": 2.0, "offset": (40.0, 30.0)}, {"angle_deg": 90.0, "offset": (350.0, 20.0)}])
def test_a_layered_opening_gets_one_existence_record_that_names_the_layers(kw):
    physical, published, ids, kw = _fixture(LAYERED, **kw)
    members = _ids(ids, LAYERED, kw)
    seeded = physical.prove_seeded_existence(_selector(published, members[6]), members)
    assert seeded.status is CORR and seeded.proposition == PHYSICAL_OPENING_EXISTS
    record = seeded.existence_record
    assert set(record.source_observation_ids) == set(members)
    assert record.structural_pattern == JAMB_BOUNDED_TWO_FACE_INTERRUPTION
    assert record.structural_reason_codes == (STRUCTURAL_OPENING_EXISTENCE_RESOLVED, LAYERED_FACES_OF_ONE_GAP)
    for member in (members[0], members[7], members[9]):
        assert physical.prove_seeded_existence(_selector(published, member), members).existence_record == record


def test_the_record_is_geometry_identity_so_it_does_not_depend_on_the_order_of_the_named_members():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[6])
    first = physical.prove_seeded_existence(selector, members)
    assert physical.prove_seeded_existence(selector, list(reversed(members))) == first
    assert physical.prove_seeded_existence(selector, tuple(members) + tuple(members)) == first


# ---- what the restricted universe left out ----------------------------------------------------------------------------------
def test_glazing_between_the_faces_must_be_accounted_for_by_name():
    physical, published, ids, kw = _fixture(LAYERED + GLAZING)
    members = _ids(ids, LAYERED, kw)
    glass = _ids(ids, GLAZING, kw)
    selector = _selector(published, members[6])
    refused = physical.prove_seeded_existence(selector, members)
    assert refused.status is ABST and refused.reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
    assert refused.existence_record is None and refused.candidate is not None
    partly = physical.prove_seeded_existence(selector, members, glass[:1])
    assert partly.status is ABST
    named = physical.prove_seeded_existence(selector, members, glass)
    assert named.status is CORR and named.existence_record.source_observation_ids == tuple(sorted(members))


SHARED_STUB = (((112.0, 105.0), (128.0, 105.0)),)           # collinear with the face both layers share
FLUSH_OUTER = (((100.0, 100.0), (140.0, 100.0)), ((100.0, 110.0), (140.0, 110.0)))   # jamb to jamb on the outer faces
FLUSH_MIDDLE = (((100.0, 105.0), (140.0, 105.0)),)           # jamb to jamb on the shared face


@pytest.mark.parametrize("accounted", [False, True])
def test_a_stub_on_the_face_both_layers_share_is_refused_even_when_named(accounted):
    physical, published, ids, kw = _fixture(LAYERED + SHARED_STUB)
    members = _ids(ids, LAYERED, kw)
    stub = _ids(ids, SHARED_STUB, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[6]), members, stub if accounted else ())
    assert proof.status is ABST and proof.reason_codes == (SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,)
    assert proof.existence_record is None
    # naming the stub as a MEMBER puts it back into the universe the six-line rule sees, which then finds no opening
    assert physical.prove_seeded_existence(_selector(published, members[6]), members + stub).existence_record is None


def test_a_stub_on_one_outer_face_drops_only_the_layer_that_face_belongs_to():
    physical, published, ids, kw = _fixture(LAYERED + SILL_STUB)
    members = _ids(ids, LAYERED, kw)
    dropped = physical.prove_seeded_existence(_selector(published, members[6]), members)      # a jamb of the dropped layer
    assert dropped.status is ABST and dropped.reason_codes == (VISIBLE_WALL_CONTINUATION_REQUIRED,)
    kept = physical.prove_seeded_existence(_selector(published, members[8]), members)          # a jamb of the kept layer
    assert kept.status is CORR and LAYERED_FACES_OF_ONE_GAP not in kept.existence_record.structural_reason_codes
    assert not set(kept.existence_record.source_observation_ids) & {members[6], members[7]}


def test_lines_anchored_at_both_jambs_on_the_outer_faces_are_not_stubs_but_one_on_the_shared_face_must_be_named():
    physical, published, ids, kw = _fixture(LAYERED + FLUSH_OUTER + FLUSH_MIDDLE)
    members = _ids(ids, LAYERED, kw)
    middle = _ids(ids, FLUSH_MIDDLE, kw)
    selector = _selector(published, members[6])
    unnamed = physical.prove_seeded_existence(selector, members)
    assert unnamed.status is ABST and unnamed.reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
    assert physical.prove_seeded_existence(selector, members, middle).status is CORR


def test_ink_outside_the_gap_or_outside_the_faces_is_not_inside_the_opening():
    far = (((300.0, 150.0), (360.0, 150.0)), ((104.0, 130.0), (136.0, 130.0)))
    physical, published, ids, kw = _fixture(LAYERED + far)
    members = _ids(ids, LAYERED, kw)
    assert physical.prove_seeded_existence(_selector(published, members[6]), members).status is CORR


# ---- abstentions and refusals -----------------------------------------------------------------------------------------------
def test_unknown_foreign_or_selector_less_members_and_unknown_accounted_ids_abstain():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[6])
    for bad in ([], ["no-such-observation"], members + ["no-such-observation"], [m for m in members if m != members[6]]):
        proof = physical.prove_seeded_existence(selector, bad)
        assert proof.status is ABST and proof.existence_record is None
    assert physical.prove_seeded_existence(selector, members, ["no-such-observation"]).status is ABST


def test_wrong_argument_types_are_refused_and_without_a_visibility_authority_it_abstains():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[6])
    with pytest.raises(TypeError):
        physical.prove_seeded_existence("not-a-selector", members)
    with pytest.raises(TypeError):
        physical.prove_seeded_existence(selector, members[0])
    with pytest.raises(TypeError):
        physical.prove_seeded_existence(selector, members, members[0])
    raw = PhysicalOpeningAuthority.__new__(PhysicalOpeningAuthority)
    raw._source_visibility_authority = None
    raw._source_visibility_producer = None
    assert raw.prove_seeded_existence(selector, members).status is ABST


def test_it_uses_and_writes_none_of_the_per_page_memos():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    names = [n for n in ("_visible_candidate_cache", "_visible_candidate_membership_cache", "_visible_existence_cache",
                         "_visible_viewport_scope_cache", "_visible_viewport_candidate_membership_cache")
             if hasattr(physical, n)]
    before = {n: dict(getattr(physical, n)) for n in names}
    physical.prove_seeded_existence(_selector(published, members[6]), members)
    physical.seeded_candidate_structures(_selector(published, members[6]), members)
    assert {n: dict(getattr(physical, n)) for n in names} == before


def test_the_page_level_answer_is_unchanged_by_asking_the_seeded_question():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[6])
    first = physical.prove_existence(selector)
    physical.prove_seeded_existence(selector, members)
    assert physical.prove_existence(selector) == first


def test_nothing_in_the_repository_calls_the_seeded_proof():
    callers = []
    for path in sorted(REPO.glob("*.py")) + sorted((REPO / "tools").glob("*.py")) + sorted((REPO / "scripts").glob("*.py")):
        if path.name == "pb_physical_opening_authority.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if any(isinstance(node, ast.Attribute) and node.attr == "prove_seeded_existence" for node in ast.walk(tree)):
            callers.append(path.relative_to(REPO).as_posix())
    assert callers == []
