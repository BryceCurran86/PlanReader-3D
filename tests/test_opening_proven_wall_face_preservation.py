from __future__ import annotations

from dataclasses import replace
import copy

import fitz
import pytest

from pb_physical_wall_candidate_authority import (
    _filter_repeated_non_physical_drafting_primitives,
    _producer_proven_opening_wall_face_source_ids,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page


def _source(*, turns=0, scale=1, missing_jamb=False, reverse=False):
    def point(x, y):
        for _ in range(turns):
            x, y = 400 - y, x
        return fitz.Point(scale * x, scale * y)

    lines = [((20, 40), (25, 40)), ((35, 40), (40, 40)),
             ((20, 44), (25, 44)), ((35, 44), (40, 44)),
             ((25, 40), (25, 44)), ((35, 40), (35, 44))]
    if missing_jamb:
        lines.pop()
    # Same singleton family as the four physical faces, far from the opening.
    lines += [((60 + i * 10, 180), (65 + i * 10, 180)) for i in range(12)]
    if reverse:
        lines.reverse()
    doc = fitz.open()
    page = doc.new_page(width=400 * scale, height=400 * scale)
    for first, second in lines:
        page.draw_line(point(*first), point(*second), width=0.48 * scale, color=(0, 0, 0))
    segments = extract_native_page(page)["segments"]
    payload = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    source = SourceVisibilityProducer(producer_method="opening-face-preservation-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="opening-face-preservation", source_bytes=payload,
        source_locator="memory://opening-faces.pdf", page_ids=("1",))
    return source, published, segments


def _protected(source, published):
    return _producer_proven_opening_wall_face_source_ids(
        source_producer=source, published=published, page_id="1",
        physical_opening_authority=source.physical_opening_authority())


@pytest.mark.parametrize("turns,scale,reverse", [
    (0, 1, False), (1, 1, False), (2, 1, True), (3, 2, True), (0, 0.5, True),
])
def test_only_complete_source_proven_faces_survive_the_motif_filter(turns, scale, reverse):
    source, published, segments = _source(turns=turns, scale=scale, reverse=reverse)
    before = copy.deepcopy(segments)
    protected = _protected(source, published)
    assert len(protected) == 4
    without = _filter_repeated_non_physical_drafting_primitives(
        segments, page_width=400 * scale, page_height=400 * scale)
    with_proof = _filter_repeated_non_physical_drafting_primitives(
        segments, page_width=400 * scale, page_height=400 * scale,
        preserved_source_primitive_ids=protected)
    assert not (protected & {row["id"] for row in without})
    assert protected <= {row["id"] for row in with_proof}
    assert {row["id"] for row in with_proof} - {row["id"] for row in without} == protected
    # Neither the twelve look-alike strokes nor either jamb is protected.
    assert len(with_proof) == 6
    assert segments == before
    assert _protected(source, published) == protected


def test_incomplete_opening_does_not_protect_look_alike_wall_faces():
    source, published, _ = _source(missing_jamb=True)
    assert _protected(source, published) == frozenset()


def test_another_producers_opening_authority_cannot_protect_source_faces():
    source, published, _ = _source()
    other, _, _ = _source(turns=1)
    assert _producer_proven_opening_wall_face_source_ids(
        source_producer=source, published=published, page_id="1",
        physical_opening_authority=other.physical_opening_authority()) == frozenset()


def test_unpainted_source_boundaries_cannot_gain_motif_preservation():
    from test_native_unstroked_fill_evidence import _source as fill_source
    source, published, _, _ = fill_source()
    assert _protected(source, published) == frozenset()


def test_caller_opening_assertion_cannot_replace_producer_owned_authority():
    from types import SimpleNamespace
    source, published, _ = _source()
    with pytest.raises(TypeError, match="producer-owned"):
        _producer_proven_opening_wall_face_source_ids(
            source_producer=source, published=published, page_id="1",
            physical_opening_authority=SimpleNamespace(prove_existence=lambda _: None))


@pytest.mark.parametrize("warm", [False, True])
def test_narrowed_page_index_cannot_replace_the_full_source_proof_inventory(warm):
    source, published, _ = _source()
    authority = source.physical_opening_authority()
    rows = source.authority().authenticated_visible_observations(published)
    if warm:
        assert len(_producer_proven_opening_wall_face_source_ids(
            source_producer=source, published=published, page_id="1",
            physical_opening_authority=authority)) == 4
    assert _producer_proven_opening_wall_face_source_ids(
        source_producer=source, published=published, page_id="1",
        physical_opening_authority=authority,
        resolved_visible_observations=rows[:-1]) == frozenset()
    # Rejection neither poisons nor narrows the complete positive inventory.
    assert len(_producer_proven_opening_wall_face_source_ids(
        source_producer=source, published=published, page_id="1",
        physical_opening_authority=authority)) == 4


@pytest.mark.parametrize("warm", [False, True])
def test_stale_or_damaged_support_cannot_protect_a_face(warm):
    source, published, _ = _source()
    if warm:
        assert len(_protected(source, published)) == 4
    observation_id = published.visible_observation_ids[0]
    key = (published.snapshot.snapshot_id, observation_id)
    original = source._producer._store.observations[key]
    source._producer._store.observations[key] = replace(
        original, geometry=tuple(value + 1 for value in original.geometry))
    assert _protected(source, published) == frozenset()


def test_protected_faces_reenter_the_unchanged_twenty_thousand_primitive_cap(monkeypatch):
    import pb_physical_wall_candidate_authority as module
    source, published, segments = _source()
    protected = _protected(source, published)
    assert len(protected) == 4
    # Force a small cap to exercise the same failure before any W2/W4 work.
    monkeypatch.setattr(module, "MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS", 5)
    selector = module.PhysicalWallCandidateSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        page_id="1", decision_scope_id="wall-source:page-1")
    # Recovered original faces must obey the cap if/when production promotion
    # is separately source-authorized. The live W4 stage does not call this
    # diagnostic bridge until exact source/host identity retention is proved.
    recovered = module._filter_repeated_non_physical_drafting_primitives(
        segments, page_width=400, page_height=400,
        preserved_source_primitive_ids=protected,
    )
    assert len(recovered) == 6
    assert len(recovered) > module.MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
    assert module.MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS != 20_000
    # Normal W4 does not gain these face edges from a diagnostic-only proof.
    result = module._assemble_scope_result(
        source_producer=source, published=published, page_id="1", selector=selector,
        segments=segments, source_observation_ids=published.visible_observation_ids,
        page_width=400, page_height=400,
        source_bytes=source._producer._store.source_bytes_by_revision[published.revision.revision_id],
        physical_opening_authority=source.physical_opening_authority())
    assert module.PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED not in result.reason_codes
