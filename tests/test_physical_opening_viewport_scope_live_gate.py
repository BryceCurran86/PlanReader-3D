from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _opening(page, x, y, *, gap=40.0, run=50.0, thick=10.0):
    a, b = x + run, x + run + gap
    for yy in (y, y + thick):
        page.draw_line((x, yy), (a, yy), width=1)
        page.draw_line((b, yy), (b + run, yy), width=1)
    page.draw_line((a, y), (a, y + thick), width=1)
    page.draw_line((b, y), (b, y + thick), width=1)


def _two_view_sheet() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    page.draw_rect(fitz.Rect(20, 20, 300, 320), color=(0, 0, 0), width=1)
    page.draw_rect(fitz.Rect(300, 20, 600, 320), color=(0, 0, 0), width=1)
    page.insert_text((70, 300), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((365, 300), "FRONT ELEVATION", fontsize=11)
    _opening(page, 60, 100)
    _opening(page, 340, 100)
    payload = doc.tobytes()
    doc.close()
    return payload


def _untitled_sheet() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    _opening(page, 60, 100)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload: bytes, name: str):
    source = SourceVisibilityProducer(
        producer_method="live-opening-viewport-gate-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="test:" + name,
        source_bytes=payload,
        source_locator="fixture:" + name,
    )
    return source, published


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _candidate_mean_x(candidate, source, published) -> float:
    authority = source.authority()
    xs = []
    for observation_id in candidate.source_observation_ids:
        resolved = authority.resolve_visible(_selector(published, observation_id))
        assert resolved.observation is not None
        x1, _y1, x2, _y2 = resolved.observation.geometry
        xs.extend((float(x1), float(x2)))
    return sum(xs) / len(xs)


def _raw_candidates(source, published):
    raw = PhysicalOpeningAuthority(source.authority())
    seed = published.visible_observation_ids[0]
    structures = raw.visible_candidate_structures(_selector(published, seed))
    assert structures.status is EvidenceResolutionStatus.CANDIDATE
    return structures.candidates


def test_live_authority_promotes_only_authenticated_floor_plan_candidate() -> None:
    source, published = _ingest(_two_view_sheet(), "two-view")
    candidates = _raw_candidates(source, published)
    assert len(candidates) == 2

    ordered = sorted(candidates, key=lambda candidate: _candidate_mean_x(candidate, source, published))
    plan_candidate, elevation_candidate = ordered
    scoped = PhysicalOpeningAuthority.from_source_visibility_producer(source)

    plan = scoped.prove_existence(_selector(published, plan_candidate.source_observation_ids[0]))
    assert plan.status is EvidenceResolutionStatus.CORROBORATED
    assert plan.existence_record is not None
    assert plan.existence_record.viewport_id is not None

    elevation = scoped.prove_existence(
        _selector(published, elevation_candidate.source_observation_ids[0])
    )
    assert elevation.status is EvidenceResolutionStatus.ABSTAINED
    assert elevation.existence_record is None
    assert "in_authenticated_non_plan_viewport" in elevation.reason_codes


def test_source_producer_cached_opening_authority_is_viewport_scoped() -> None:
    source, published = _ingest(_two_view_sheet(), "producer-cache-two-view")
    candidates = _raw_candidates(source, published)
    ordered = sorted(
        candidates,
        key=lambda candidate: _candidate_mean_x(candidate, source, published),
    )
    plan_candidate, elevation_candidate = ordered

    scoped = source.physical_opening_authority()
    assert scoped is source.physical_opening_authority()

    plan = scoped.prove_existence(
        _selector(published, plan_candidate.source_observation_ids[0])
    )
    elevation = scoped.prove_existence(
        _selector(published, elevation_candidate.source_observation_ids[0])
    )
    assert plan.status is EvidenceResolutionStatus.CORROBORATED
    assert plan.existence_record is not None
    assert elevation.status is EvidenceResolutionStatus.ABSTAINED
    assert elevation.existence_record is None


def test_semantic_enumeration_excludes_authenticated_elevation_false_candidate() -> None:
    source, published = _ingest(_two_view_sheet(), "semantic-two-view")
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    result = producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="test:page-1",
        page_ids=("1",),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert len(result.record.physical_opening_record_ids) == 1
    assert len(result.record.representative_observation_ids) == 1
    assert result.record.physical_opening_universe_complete is True


def test_missing_authenticated_viewport_fails_closed_in_live_authority() -> None:
    source, published = _ingest(_untitled_sheet(), "untitled")
    candidates = _raw_candidates(source, published)
    assert candidates

    scoped = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    result = scoped.prove_existence(_selector(published, candidates[0].source_observation_ids[0]))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.existence_record is None
    assert "no_authenticated_viewport" in result.reason_codes
