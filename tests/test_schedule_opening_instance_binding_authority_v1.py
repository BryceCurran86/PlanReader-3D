"""Schedule-row <-> physical-opening-instance binding authority -- production
and red-team regression tests (v2: producer-owned evidence universe).

Uses real PDF ingestion (fitz-authored synthetic drawings, real vector
geometry and real text -- not mocks) so G17 existence, text-integrity, and
this module's own containment/matching/row-discovery logic are all
exercised genuinely.

The v1 API accepted caller-supplied ``tag_observation_ids`` and
``schedule_row_word_groups`` -- independent review found this let a caller
manufacture false uniqueness by omitting a real, in-scope competitor. The
v2 API removes both parameters entirely: ``publish_scope`` takes only an
``ObservationSelector`` addressing the opening and a plain
``decision_scope_id`` string. Every test below exercises that narrow
surface directly; there is no caller-side id/grouping plumbing left to
build.
"""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_ROWS,
    BINDING_AMBIGUOUS_TAGS,
    BINDING_NO_CONTAINED_TAG,
    BINDING_NO_MATCHING_ROW,
    BINDING_OPENING_UNRESOLVED,
    BINDING_PARTIAL_SOURCE_COVERAGE,
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingProducer,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SCOPE = "schedule-binding-scope:page-1"
TAG_Y = 106.0
SCHEDULE_HEADER_Y = 500.0
SCHEDULE_ROW_DY = 30.0
SCHEDULE_COL_X = (50.0, 150.0, 250.0)

# Evidence-shaped parameter names the public binding surface must never
# accept -- the caller may address WHAT to bind, never WHICH evidence wins.
_FORBIDDEN_PUBLIC_PARAM_NAMES = {
    "tag_observation_ids", "schedule_row_word_groups", "schedule_row_ids",
    "candidate_rows", "candidate_tags", "tag_mark", "height", "width",
    "row_count", "complete", "confidence", "nearest", "radius",
}


def _draw_opening(page: fitz.Page, *, x0: float, gap0: float, gap1: float, x1: float, y0: float, y1: float) -> None:
    """One wall run with a jamb-bounded gap between gap0 and gap1."""
    for first, second in (
        ((x0, y0), (gap0, y0)),
        ((gap1, y0), (x1, y0)),
        ((x0, y1), (gap0, y1)),
        ((gap1, y1), (x1, y1)),
        ((gap0, y0), (gap0, y1)),
        ((gap1, y0), (gap1, y1)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)


def _insert_schedule_table(page: fitz.Page, rows: tuple[tuple[str, str, str], ...], *, y0: float = SCHEDULE_HEADER_Y) -> None:
    y = y0
    for row in rows:
        for cell, x in zip(row, SCHEDULE_COL_X):
            page.insert_text(fitz.Point(x, y), cell, color=(0, 0, 0))
        y += SCHEDULE_ROW_DY


def _tag_pdf(
    *,
    tag_text: str = "W1",
    schedule_rows: tuple[tuple[str, str, str], ...] = (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
    extra_tags: tuple[tuple[str, float, float], ...] = (),
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page.insert_text(fitz.Point(112, TAG_Y), tag_text, color=(0, 0, 0))
    for text, x, y in extra_tags:
        page.insert_text(fitz.Point(x, y), text, color=(0, 0, 0))
    _insert_schedule_table(page, schedule_rows)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(producer: SourceVisibilityProducer, payload: bytes, document_id: str):
    return producer.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=payload, source_locator=f"memory://{document_id}.pdf",
    )


def _opening_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        if physical.prove_existence(selector).proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("fixture must prove one opening")


def _bind(source_visibility_producer: SourceVisibilityProducer, opening_selector: ObservationSelector):
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    return binder.publish_scope(opening_selector=opening_selector, decision_scope_id=SCOPE)


def test_authority_is_producer_minted_and_selector_only() -> None:
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    authority = producer.authority()
    assert isinstance(authority, ScheduleOpeningInstanceBindingAuthority)
    with pytest.raises(ValueError):
        ScheduleOpeningInstanceBindingAuthority({}, _seal=object())
    with pytest.raises(TypeError):
        ScheduleOpeningInstanceBindingProducer(src)  # direct construction, no seal
    with pytest.raises(TypeError):
        ScheduleOpeningInstanceBindingSelector(
            document_id="d", revision_id="r", source_sha256="s", snapshot_id="n",
        )  # type: ignore[call-arg]


def test_public_selector_never_accepts_evidence_shaped_parameters() -> None:
    """PUBLIC SELECTOR RULE: only addressing/lineage, never pre-selected
    evidence. Structurally impossible, not just empirically blocked."""
    params = set(inspect.signature(ScheduleOpeningInstanceBindingProducer.publish_scope).parameters)
    leaked = params & _FORBIDDEN_PUBLIC_PARAM_NAMES
    assert not leaked, f"publish_scope must not accept evidence parameters: {leaked}"
    assert params == {"self", "opening_selector", "decision_scope_id"}


def test_real_binding_resolves_via_contained_tag_and_matching_row() -> None:
    payload = _tag_pdf()
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-positive")
    visibility = src.authority()
    opening_selector = _opening_selector(published, visibility)
    opening = PhysicalOpeningAuthority(visibility).prove_existence(opening_selector).existence_record

    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "W1"
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100
    assert result.record.opening_record_id == opening.record_id
    assert result.record.page_id == opening.page_id
    assert result.record.schedule_page_id == opening.page_id  # same-page schedule here
    assert result.record.schedule_row_observation_ids

    resolved = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src).authority().resolve(
        ScheduleOpeningInstanceBindingSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            decision_scope_id=SCOPE,
            opening_record_id=opening.record_id,
        )
    )
    # A fresh authority (no publish_scope call of its own) legitimately
    # abstains -- this only proves the selector/resolve plumbing is sound.
    assert resolved.status is EvidenceResolutionStatus.ABSTAINED


def test_opening_unresolved_selector_abstains() -> None:
    payload = _tag_pdf()
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-badopening")
    fake_selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id="caller-invented-observation-id",
    )
    result = _bind(src, fake_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_OPENING_UNRESOLVED in result.reason_codes


def test_tag_outside_opening_footprint_is_not_contained() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page.insert_text(fitz.Point(400, 400), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-outside")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes


def test_attack_partial_source_coverage_abstains() -> None:
    payload = _tag_pdf()
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    # Instead of full ingestion, we can just patch the coverage state of an existing published snapshot
    published = _ingest(src, payload, "sched-partial")
    partial_coverage = published.coverage
    # A bit of a hack for testing, normally generated by decode failure
    object.__setattr__(partial_coverage, "state", "partial")
    object.__setattr__(partial_coverage, "failed_pages", (1,))
    
    visibility = src.authority()
    opening_selector = _opening_selector(published, visibility)
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_PARTIAL_SOURCE_COVERAGE in result.reason_codes


def test_attack_a_omitted_second_tag_is_impossible_conflict() -> None:
    """A. Two real, trusted tags inside one physical opening's footprint.
    There is no caller-side id list left to omit the second one with --
    the scan is exhaustive by construction."""
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page.insert_text(fitz.Point(103, TAG_Y), "W1", color=(0, 0, 0))
    page.insert_text(fitz.Point(122, TAG_Y), "W2", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-twotags")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_TAGS in result.reason_codes


def test_attack_left_graze_tag_is_not_contained() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    # Tag W1 left graze: place text so its centroid is < 100 but bbox max x > 100
    page.insert_text(fitz.Point(85, TAG_Y), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-left-graze")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes


def test_attack_right_graze_tag_is_not_contained() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    # Tag W1 right graze: place text so its centroid is > 140 but bbox min x < 140
    page.insert_text(fitz.Point(135, TAG_Y), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-right-graze")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes


def test_real_centered_tag_is_contained() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    # Centroid is roughly 120 (well inside 100..140)
    page.insert_text(fitz.Point(115, TAG_Y), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-centered")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED


def test_attack_bbox_normal_grazing_tag_is_not_contained() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    # normal_min=100, normal_max=110
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    
    # Tag W1 inserted at y=112 (baseline). Normal center will be ~107-108.
    # We want it to be > 110. Let's insert at y=118, which pushes centroid well outside [100, 110]
    # but still has some overlap (since bbox min y is ~118 - 12 = 106, which is <= 110).
    page.insert_text(fitz.Point(112, 118), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-overlap-normal-clip")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes


def test_attack_headerless_schedule_row_is_ignored() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page.insert_text(fitz.Point(112, TAG_Y), "W1", color=(0, 0, 0))
    # Add a schedule-like row, but without any MARK WIDTH HEIGHT header
    page.insert_text(fitz.Point(50.0, 500.0), "W1", color=(0, 0, 0))
    page.insert_text(fitz.Point(150.0, 500.0), "900", color=(0, 0, 0))
    page.insert_text(fitz.Point(250.0, 500.0), "2100", color=(0, 0, 0))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-headerless")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_MATCHING_ROW in result.reason_codes

def test_attack_b_omitted_conflicting_schedule_row_is_impossible_conflict() -> None:
    """B. Complete schedule has D1/W1 900x2100 AND 800x2000. There is no
    caller-side row grouping left to present only one with."""
    payload = _tag_pdf(
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT"),
            ("W1", "900", "2100"),
            ("W1", "800", "2000"),
        )
    )
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-dupe")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_attack_c_foreign_page_laundering_preserves_real_schedule_page() -> None:
    """C. Opening on page 1; the real, matching schedule row is on page 2.
    The record must carry opening page=1 and schedule page=2 -- neither
    ever substitutes for the other."""
    doc = fitz.open()
    page1 = doc.new_page(width=700, height=650)
    _draw_opening(page1, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page1.insert_text(fitz.Point(112, TAG_Y), "W1", color=(0, 0, 0))
    page2 = doc.new_page(width=700, height=650)
    _insert_schedule_table(page2, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-crosspage")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record.page_id == "1"
    assert result.record.schedule_page_id == "2"
    assert result.record.schedule_page_id != result.record.page_id


def test_attack_d_unrelated_foreign_schedule_cannot_be_borrowed() -> None:
    """D. Two separate documents in the SAME producer. Doc A's opening has
    no matching row of its own; doc B (different document/revision/sha/
    snapshot) happens to have one for the same mark. Doc A's binding must
    never see doc B's evidence."""
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    payload_a = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"),))  # no real row for W1
    published_a = _ingest(src, payload_a, "sched-attack-d-a")
    opening_selector = _opening_selector(published_a, src.authority())

    doc_b = fitz.open()
    page_b = doc_b.new_page(width=700, height=650)
    _insert_schedule_table(page_b, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload_b = doc_b.tobytes()
    doc_b.close()
    _ingest(src, payload_b, "sched-attack-d-b")

    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_MATCHING_ROW in result.reason_codes


def test_no_matching_schedule_row_abstains() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W9", "800", "2000")))
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-norow")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_MATCHING_ROW in result.reason_codes


def test_attack_f_five_physical_instances_sharing_one_tag_get_five_independent_bindings() -> None:
    """F. Five physical openings share tag W1 -- must NOT collapse into
    one, and each must independently prove its OWN contained tag."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=900)
    for i in range(5):
        y0 = 100.0 + i * 60.0
        y1 = y0 + 10.0
        gap0, gap1 = 100.0, 140.0
        _draw_opening(page, x0=20.0, gap0=gap0, gap1=gap1, x1=220.0, y0=y0, y1=y1)
        page.insert_text(fitz.Point(gap0 + 12, y0 + 6.0), "W1", color=(0, 0, 0))
    _insert_schedule_table(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    published = _ingest(src, payload, "sched-five")
    visibility = src.authority()
    physical = PhysicalOpeningAuthority(visibility)

    proven_openings = []
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = physical.prove_existence(selector)
        if existence.proposition == PHYSICAL_OPENING_EXISTS:
            proven_openings.append(selector)

    distinct = {physical.prove_existence(s).existence_record.record_id for s in proven_openings}
    assert len(distinct) == 5, f"fixture must independently prove 5 distinct physical openings, got {len(distinct)}"

    bound_opening_ids = set()
    for selector in proven_openings:
        result = _bind(src, selector)
        assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
        assert result.record.tag_mark == "W1"
        bound_opening_ids.add(result.record.opening_record_id)

    assert len(bound_opening_ids) == 5, "each physical instance must get its own independent binding"


def test_attack_g_contradiction_monotonicity_row_can_only_weaken() -> None:
    """G. A valid unique binding, then a genuine conflicting trusted
    schedule row added to the evidence: CORROBORATED can only become
    CONFLICT, never stay CORROBORATED."""
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")

    payload_before = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    published_before = _ingest(src, payload_before, "sched-mono-before")
    before = _bind(src, _opening_selector(published_before, src.authority()))
    assert before.status is EvidenceResolutionStatus.CORROBORATED

    src2 = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    payload_after = _tag_pdf(
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT"),
            ("W1", "900", "2100"),
            ("W1", "900", "2400"),
        )
    )
    published_after = _ingest(src2, payload_after, "sched-mono-after")
    after = _bind(src2, _opening_selector(published_after, src2.authority()))
    assert after.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in after.reason_codes


def test_attack_h_tag_monotonicity_second_contained_tag_can_only_weaken() -> None:
    """H. One contained trusted tag lets the row match proceed; adding a
    second trusted contained tag must flip the result to CONFLICT, never
    strengthen or leave it resolvable."""
    src = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    payload_before = _tag_pdf()
    published_before = _ingest(src, payload_before, "sched-tagmono-before")
    before = _bind(src, _opening_selector(published_before, src.authority()))
    assert before.status is EvidenceResolutionStatus.CORROBORATED

    src2 = SourceVisibilityProducer(producer_method="sched-bind-test", producer_version="1.0")
    payload_after = _tag_pdf(tag_text=" ", extra_tags=(("W1", 105.0, TAG_Y), ("W2", 125.0, TAG_Y)))
    published_after = _ingest(src2, payload_after, "sched-tagmono-after")
    after = _bind(src2, _opening_selector(published_after, src2.authority()))
    assert after.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_TAGS in after.reason_codes


def _insert_schedule_table_at(
    page: fitz.Page,
    rows: tuple[tuple[str, str, str], ...],
    *,
    xs: tuple[float, float, float],
    y0: float = SCHEDULE_HEADER_Y,
) -> None:
    y = y0
    for row in rows:
        for cell, x in zip(row, xs):
            page.insert_text(fitz.Point(x, y), cell, color=(0, 0, 0))
        y += SCHEDULE_ROW_DY


def test_side_by_side_matching_schedule_rows_are_both_discovered_and_conflict() -> None:
    """Two horizontal tables at the same Y must never collapse into the first.

    Both independently authenticated W1 rows are real competitors, even when
    PDF reading order interleaves their cells on the same visual row.
    """
    doc = fitz.open()
    page = doc.new_page(width=760, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    page.insert_text(fitz.Point(112, TAG_Y), "W1", color=(0, 0, 0))
    _insert_schedule_table_at(
        page,
        (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
        xs=(40.0, 120.0, 200.0),
    )
    _insert_schedule_table_at(
        page,
        (("MARK", "WIDTH", "HEIGHT"), ("W1", "800", "2000")),
        xs=(390.0, 470.0, 550.0),
    )
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(
        producer_method="sched-bind-test",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "sched-side-by-side-conflict")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes
    assert result.record is None


def test_side_by_side_other_mark_does_not_contaminate_matching_table() -> None:
    """A neighboring W2 table must not shift or overwrite W1's row cells."""
    doc = fitz.open()
    page = doc.new_page(width=760, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    page.insert_text(fitz.Point(112, TAG_Y), "W1", color=(0, 0, 0))
    _insert_schedule_table_at(
        page,
        (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
        xs=(40.0, 120.0, 200.0),
    )
    _insert_schedule_table_at(
        page,
        (("MARK", "WIDTH", "HEIGHT"), ("W2", "1200", "1500")),
        xs=(390.0, 470.0, 550.0),
    )
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(
        producer_method="sched-bind-test",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "sched-side-by-side-isolation")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "W1"
    assert result.record.schedule_row_type_mark == "W1"
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100


def test_compound_door_type_header_is_one_table_not_two() -> None:
    """DOOR + TYPE are two mark-role words in one header, not two tables."""
    doc = fitz.open()
    page = doc.new_page(width=760, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    page.insert_text(fitz.Point(112, TAG_Y), "D01", color=(0, 0, 0))
    header = ("DOOR", "TYPE", "WIDTH", "HEIGHT")
    row = ("D01", "HINGED", "820", "2040")
    xs = (40.0, 105.0, 185.0, 270.0)
    for cell, x in zip(header, xs):
        page.insert_text(fitz.Point(x, SCHEDULE_HEADER_Y), cell, color=(0, 0, 0))
    for cell, x in zip(row, xs):
        page.insert_text(
            fitz.Point(x, SCHEDULE_HEADER_Y + SCHEDULE_ROW_DY),
            cell,
            color=(0, 0, 0),
        )
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(
        producer_method="sched-bind-test",
        producer_version="1.0",
    )
    published = _ingest(src, payload, "sched-compound-mark-header")
    opening_selector = _opening_selector(published, src.authority())
    result = _bind(src, opening_selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "D1"
    assert result.record.schedule_row_width_mm == 820
    assert result.record.schedule_row_height_mm == 2040
