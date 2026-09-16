from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.g17_phase2_test_support import make_resolved, selector as raw_selector


IDENTITIES_DISTINCT = "physical_opening_identities_distinct"
IDENTITY_SCOPE_MISMATCH = "physical_opening_identity_scope_mismatch"
IDENTITY_EXISTENCE_REQUIRED = "physical_opening_identity_existence_required"


def _draw_opening(page: fitz.Page, *, y: float, x0: float = 20.0) -> None:
    left_jamb_x = x0 + 80.0
    right_jamb_x = x0 + 120.0
    far_right_x = x0 + 200.0
    upper = y
    lower = y + 10.0
    for first, second in (
        ((x0, upper), (left_jamb_x, upper)),
        ((right_jamb_x, upper), (far_right_x, upper)),
        ((x0, lower), (left_jamb_x, lower)),
        ((right_jamb_x, lower), (far_right_x, lower)),
        ((left_jamb_x, upper), (left_jamb_x, lower)),
        ((right_jamb_x, upper), (right_jamb_x, lower)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)


def _pdf_bytes(*, openings_by_page: tuple[tuple[float, ...], ...], marker: str = "") -> bytes:
    doc = fitz.open()
    for page_openings in openings_by_page:
        page = doc.new_page(width=800, height=800)
        for y in page_openings:
            _draw_opening(page, y=y)
    if marker:
        doc.set_metadata({"title": marker})
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _resolved_groups(physical: PhysicalOpeningAuthority, published):
    groups: dict[str, list[ObservationSelector]] = {}
    records = {}
    for observation_id in published.visible_observation_ids:
        sel = _selector(published, observation_id)
        existence = physical.prove_existence(sel)
        if existence.proposition != PHYSICAL_OPENING_EXISTS:
            continue
        assert existence.status is EvidenceResolutionStatus.CORROBORATED
        assert existence.existence_record is not None
        record = existence.existence_record
        groups.setdefault(record.record_id, []).append(sel)
        records[record.record_id] = record
    return groups, records


def _visible_fixture(payload: bytes, *, document_id: str = "identity-doc"):
    producer = SourceVisibilityProducer(
        producer_method="opening-instance-identity-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    return producer, published, physical


def test_two_supports_of_same_g17_opening_resolve_same_instance_identity() -> None:
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=((100.0,),))
    )
    groups, records = _resolved_groups(physical, published)
    assert len(groups) == 1
    record_id, supports = next(iter(groups.items()))
    assert len(supports) == 6

    result = physical.compare_identity(supports[0], supports[-1])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is True
    assert result.physical_opening_identity == record_id
    assert records[record_id].record_id == result.physical_opening_identity


def test_same_selector_replay_is_deterministically_same_instance() -> None:
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=((100.0,),)),
        document_id="identity-replay",
    )
    groups, _ = _resolved_groups(physical, published)
    support = next(iter(groups.values()))[0]

    first = physical.compare_identity(support, support)
    second = physical.compare_identity(support, support)

    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.proven_same is True


def test_two_proven_openings_in_same_page_are_distinct_instances() -> None:
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=((100.0, 300.0),)),
        document_id="identity-two-openings",
    )
    groups, _ = _resolved_groups(physical, published)
    assert len(groups) == 2
    ordered = sorted(groups.items())

    result = physical.compare_identity(ordered[0][1][0], ordered[1][1][0])

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert result.physical_opening_identity == IDENTITIES_DISTINCT


def test_identical_geometry_in_different_documents_does_not_self_merge() -> None:
    producer = SourceVisibilityProducer(
        producer_method="opening-instance-identity-test",
        producer_version="1.0",
    )
    payload = _pdf_bytes(openings_by_page=((100.0,),))
    left_published = producer.ingest_native_pdf_bytes(
        document_id="identity-doc-a",
        source_bytes=payload,
        source_locator="memory://identity-doc-a.pdf",
    )
    right_published = producer.ingest_native_pdf_bytes(
        document_id="identity-doc-b",
        source_bytes=payload,
        source_locator="memory://identity-doc-b.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    left_groups, _ = _resolved_groups(physical, left_published)
    right_groups, _ = _resolved_groups(physical, right_published)

    result = physical.compare_identity(
        next(iter(left_groups.values()))[0],
        next(iter(right_groups.values()))[0],
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_identical_geometry_on_different_pages_requires_cross_view_authority() -> None:
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=((100.0,), (100.0,))),
        document_id="identity-two-pages",
    )
    groups, records = _resolved_groups(physical, published)
    by_page: dict[str, list[ObservationSelector]] = {}
    for record_id, supports in groups.items():
        by_page.setdefault(records[record_id].page_id, []).append(supports[0])
    assert len(by_page) == 2
    page_supports = [items[0] for _, items in sorted(by_page.items())]

    result = physical.compare_identity(page_supports[0], page_supports[1])

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_identical_geometry_across_different_source_revisions_does_not_self_merge() -> None:
    producer = SourceVisibilityProducer(
        producer_method="opening-instance-identity-test",
        producer_version="1.0",
    )
    first = producer.ingest_native_pdf_bytes(
        document_id="identity-revision-doc",
        source_bytes=_pdf_bytes(openings_by_page=((100.0,),), marker="revision-a"),
        source_locator="memory://identity-revision-a.pdf",
    )
    first_physical = PhysicalOpeningAuthority(producer.authority())
    first_groups, _ = _resolved_groups(first_physical, first)
    assert len(first_groups) == 1
    first_selector = next(iter(first_groups.values()))[0]

    second = producer.ingest_native_pdf_bytes(
        document_id="identity-revision-doc",
        source_bytes=_pdf_bytes(openings_by_page=((100.0,),), marker="revision-b"),
        source_locator="memory://identity-revision-b.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    second_groups, _ = _resolved_groups(physical, second)
    assert len(second_groups) == 1

    result = physical.compare_identity(
        first_selector,
        next(iter(second_groups.values()))[0],
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert IDENTITY_SCOPE_MISMATCH in result.reason_codes


def test_raw_native_geometry_cannot_establish_instance_identity() -> None:
    payload = _pdf_bytes(openings_by_page=((100.0,),))
    producer = SourceObservationProducer(
        producer_method="opening-instance-identity-raw-negative",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="identity-raw-negative",
        source_bytes=payload,
        source_locator="memory://identity-raw-negative.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    raw_ids = list(published.snapshot.observation_ids)
    assert len(raw_ids) >= 2

    result = physical.compare_identity(
        _selector(published, raw_ids[0]),
        _selector(published, raw_ids[1]),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert IDENTITY_EXISTENCE_REQUIRED in result.reason_codes


def test_caller_derived_structural_semantics_cannot_create_instance_identity() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    result = physical.compare_identity(
        raw_selector(published, snapshot_id, "face-a"),
        raw_selector(published, snapshot_id, "jamb-left"),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_identity_resolution_unlocks_only_identity_capability() -> None:
    _, published, physical = _visible_fixture(
        _pdf_bytes(openings_by_page=((100.0,),)),
        document_id="identity-firewall",
    )
    groups, _ = _resolved_groups(physical, published)
    supports = next(iter(groups.values()))
    result = physical.compare_identity(supports[0], supports[1])
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is True

    assert physical.capabilities() == {
        "physical_opening_existence": True,
        "physical_opening_identity": True,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
    for forbidden_method in (
        "resolve_dimensions",
        "bind_host",
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
        "jobhub_publish",
    ):
        assert not hasattr(physical, forbidden_method)
