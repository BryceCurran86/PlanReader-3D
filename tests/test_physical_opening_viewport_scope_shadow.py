"""SHADOW floor-plan viewport scope for G17 opening candidates.

Scope is observation only: it must never change G17 existence, semantic
enumeration, or any other live output. Only authenticated views (RESOLVED
frames or authoritative derived partitions) may scope a candidate; ordinary
title partitions and pages without view structure abstain.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_opening_viewport_scope_shadow import (
    AMBIGUOUS_AUTHENTICATED_OWNERSHIP,
    IN_AUTHENTICATED_FLOOR_PLAN,
    IN_AUTHENTICATED_NON_PLAN,
    NO_AUTHENTICATED_VIEWPORT,
    OPENING_VIEWPORT_SCOPE_ASSESSED,
    OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS,
    OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,
    OUTSIDE_AUTHENTICATED_VIEWPORTS,
    assess_opening_candidate_viewport_scope,
)
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _opening(page, x, y, *, gap=40.0, run=50.0, thick=10.0):
    """One jamb-bounded two-face interruption: faces at y and y+thick."""
    a, b = x + run, x + run + gap
    for yy in (y, y + thick):
        page.draw_line((x, yy), (a, yy), width=1)
        page.draw_line((b, yy), (b + run, yy), width=1)
    page.draw_line((a, y), (a, y + thick), width=1)
    page.draw_line((b, y), (b, y + thick), width=1)


def _two_view_sheet(
    *,
    right_title: str = "FRONT ELEVATION",
    dx: float = 0.0,
    dy: float = 0.0,
    with_outside: bool = True,
    with_straddle: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    page.draw_rect(fitz.Rect(20 + dx, 20 + dy, 300 + dx, 320 + dy), color=(0, 0, 0), width=1)
    page.draw_rect(fitz.Rect(300 + dx, 20 + dy, 600 + dx, 320 + dy), color=(0, 0, 0), width=1)
    page.insert_text((70 + dx, 300 + dy), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((365 + dx, 300 + dy), right_title, fontsize=11)
    _opening(page, 60 + dx, 100 + dy)
    _opening(page, 340 + dx, 100 + dy)
    if with_outside:
        _opening(page, 80 + dx, 360 + dy)
    if with_straddle:
        _opening(page, 250 + dx, 200 + dy)
    payload = doc.tobytes()
    doc.close()
    return payload


def _untitled_sheet() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    _opening(page, 60, 100)
    _opening(page, 260, 100)
    payload = doc.tobytes()
    doc.close()
    return payload


def _title_partition_only_sheet() -> bytes:
    """Two titles and no frames: ordinary (non-authoritative) derived partitions."""
    doc = fitz.open()
    page = doc.new_page(width=700, height=400)
    page.insert_text((70, 300), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((420, 300), "FRONT ELEVATION", fontsize=11)
    _opening(page, 60, 100)
    _opening(page, 420, 100)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(payload: bytes, name: str = "sheet"):
    source = SourceVisibilityProducer(producer_method="viewport-scope-shadow-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{name}",
        source_bytes=payload,
        source_locator=f"memory://{name}.pdf",
    )
    return source, published


def _assess(payload: bytes, name: str = "sheet"):
    source, published = _ingest(payload, name)
    report = assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    return source, published, report


def _scopes(report) -> list[tuple[str, str | None]]:
    return sorted((item.scope, item.view_type) for item in report.candidate_scopes)


def test_plan_candidate_is_scoped_to_the_authenticated_floor_plan() -> None:
    _source, _published, report = _assess(_two_view_sheet())
    assert report.status is EvidenceResolutionStatus.CORROBORATED
    assert report.reason_codes == (OPENING_VIEWPORT_SCOPE_ASSESSED,)
    assert {item.view_type for item in report.authenticated_viewports} == {"floor_plan", "elevation"}
    assert report.scope_counts[IN_AUTHENTICATED_FLOOR_PLAN] == 1
    plan = [item for item in report.candidate_scopes if item.scope == IN_AUTHENTICATED_FLOOR_PLAN]
    assert plan[0].view_type == "floor_plan"
    assert plan[0].existence_corroborated is True


@pytest.mark.parametrize(
    "title, view_type",
    [
        ("FRONT ELEVATION", "elevation"),
        ("SECTION A-A", "section"),
        ("ROOF PLAN", "roof_plan"),
    ],
)
def test_same_pattern_in_an_authenticated_non_plan_view_is_typed_negative(title, view_type) -> None:
    _source, _published, report = _assess(_two_view_sheet(right_title=title), name=view_type)
    negatives = [item for item in report.candidate_scopes if item.scope == IN_AUTHENTICATED_NON_PLAN]
    assert len(negatives) == 1
    assert negatives[0].view_type == view_type
    assert report.scope_counts[IN_AUTHENTICATED_FLOOR_PLAN] == 1


def test_candidate_outside_every_authenticated_view_is_out_of_scope() -> None:
    _source, _published, report = _assess(_two_view_sheet(with_outside=True))
    assert report.scope_counts[OUTSIDE_AUTHENTICATED_VIEWPORTS] == 1


def test_candidate_straddling_a_view_boundary_is_ambiguous() -> None:
    _source, _published, report = _assess(_two_view_sheet(with_outside=False, with_straddle=True))
    assert report.scope_counts[AMBIGUOUS_AUTHENTICATED_OWNERSHIP] >= 1
    assert all(
        item.view_id is None
        for item in report.candidate_scopes
        if item.scope == AMBIGUOUS_AUTHENTICATED_OWNERSHIP
    )


def test_page_without_view_structure_abstains_rather_than_negates() -> None:
    _source, _published, report = _assess(_untitled_sheet(), name="untitled")
    assert report.status is EvidenceResolutionStatus.CORROBORATED
    assert report.authenticated_viewports == ()
    assert report.candidate_scopes
    assert {item.scope for item in report.candidate_scopes} == {NO_AUTHENTICATED_VIEWPORT}
    assert report.scope_counts[IN_AUTHENTICATED_NON_PLAN] == 0


def test_ordinary_title_partitions_never_scope_a_candidate() -> None:
    _source, _published, report = _assess(_title_partition_only_sheet(), name="partition")
    assert report.authenticated_viewports == ()
    assert report.unauthenticated_viewport_count >= 1
    assert {item.scope for item in report.candidate_scopes} == {NO_AUTHENTICATED_VIEWPORT}


def _existence_snapshot(source, published) -> list[tuple[str, str, str | None]]:
    authority = PhysicalOpeningAuthority(source.authority())
    rows = []
    for observation_id in published.visible_observation_ids:
        result = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        record = result.existence_record
        rows.append((observation_id, result.status.value, None if record is None else record.record_id))
    return rows


def test_shadow_assessment_does_not_change_existence_or_enumeration() -> None:
    payload = _two_view_sheet(with_straddle=True)
    baseline_source, baseline_published = _ingest(payload, "baseline")
    before = _existence_snapshot(baseline_source, baseline_published)
    before_enumeration = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        baseline_source
    ).publish_page_scope(
        revision_id=baseline_published.revision.revision_id,
        decision_scope_id="scope",
        page_ids=("1",),
    )

    source, published = _ingest(payload, "baseline")
    assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    after = _existence_snapshot(source, published)
    after_enumeration = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    ).publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="scope",
        page_ids=("1",),
    )
    assert after == before
    assert after_enumeration == before_enumeration
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published


def test_replay_is_deterministic() -> None:
    payload = _two_view_sheet(with_straddle=True)
    _s1, _p1, first = _assess(payload, "replay")
    _s2, _p2, second = _assess(payload, "replay")
    assert first.record_id == second.record_id
    assert first.candidate_scopes == second.candidate_scopes


def test_translation_keeps_every_scope() -> None:
    _s1, _p1, base = _assess(_two_view_sheet(), "base")
    _s2, _p2, moved = _assess(_two_view_sheet(dx=37.0, dy=21.0), "moved")
    assert _scopes(base) == _scopes(moved)


def test_unknown_revision_abstains() -> None:
    source, _published = _ingest(_two_view_sheet(), "unknown")
    report = assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id="not-a-revision",
        page_id="1",
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.reason_codes == (OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,)
    assert report.candidate_scopes == ()


def test_page_without_visible_segments_abstains() -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((40, 100), "GROUND FLOOR PLAN", fontsize=11)
    payload = doc.tobytes()
    doc.close()
    _source, _published, report = _assess(payload, "empty")
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.reason_codes == (OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS,)


def test_source_bytes_are_producer_owned_and_hash_checked() -> None:
    source, published = _ingest(_two_view_sheet(), "tamper")
    store = source._producer._store
    store.source_bytes_by_revision[published.revision.revision_id] = _untitled_sheet()
    report = assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.reason_codes == (OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,)


def test_rejects_non_producer_inputs() -> None:
    with pytest.raises(TypeError):
        assess_opening_candidate_viewport_scope(
            source_visibility_producer=object(),  # type: ignore[arg-type]
            revision_id="r",
            page_id="1",
        )
