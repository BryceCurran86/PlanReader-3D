"""Fixtures for host-binding authenticated-prerequisite validator v3.

TEST SUPPORT ONLY / SELF-AUTHORED VALIDATOR.

Every positive prerequisite is producer-owned. Native PDF bytes are ingested by
SourceVisibilityProducer; physical-opening existence/identity are re-proven from
that authority; physical-wall candidates are derived by the merged sealed
PhysicalWallCandidateProducer.from_source_visibility_producer() bridge.

No helper creates a WallCandidate, host id, candidate subset, completeness flag,
or caller geometry and then treats it as authority.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    PublishedVisibleSourceSnapshot,
    SourceVisibilityAuthority,
    SourceVisibilityProducer,
)

BASE_SHA = "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"
HISTORICAL_360_HEAD = "4231222348c9d575232097b9c4072ac3a83cfcba"
HISTORICAL_364_HEAD = "931506b0b80531383c78a621ca9c09473642ed58"
FROZEN_4A_VALIDATOR_HEAD = "4f9503d027b32664bbdac235289fb401d310d27e"
MERGED_4A_PRODUCTION_HEAD = "082810b541bbe4072376f7328fc6064351cb383c"


@dataclass(frozen=True)
class RealHostFixture:
    source_producer: SourceVisibilityProducer
    source_authority: SourceVisibilityAuthority
    published: PublishedVisibleSourceSnapshot
    physical_opening_authority: PhysicalOpeningAuthority
    left_selector: ObservationSelector
    right_selector: ObservationSelector
    existence_record: PhysicalOpeningExistenceRecord
    wall_producer: PhysicalWallCandidateProducer
    wall_authority: PhysicalWallCandidateAuthority
    wall_selector: PhysicalWallCandidateSelector
    wall_scope: PhysicalWallCandidateScopeResult

    @property
    def document_id(self) -> str:
        return self.existence_record.document_id

    @property
    def revision_id(self) -> str:
        return self.existence_record.revision_id

    @property
    def source_sha256(self) -> str:
        return self.existence_record.source_sha256

    @property
    def snapshot_id(self) -> str:
        return self.existence_record.snapshot_id

    @property
    def page_id(self) -> str:
        return self.existence_record.page_id


@dataclass(frozen=True)
class CallerHostTruth:
    """Caller-authored lookalike data. It is never authority."""

    opening_record_id: str = "physical-opening-record-lookalike"
    wall_id: str = "host-wall-lookalike"
    candidate_wall_ids: tuple[str, ...] = ("host-wall-lookalike",)
    claimed_complete: bool = True
    radius: float = 25.0
    tag: str = "D1"
    schedule_row: str = "D1 900x2100"
    ocr_label: str = "DOOR D1"
    cv_label: str = "door"


def _host_pdf_bytes(*, include_competitor: bool = False) -> bytes:
    """Create a real native-PDF opening plus optional competing wall evidence.

    The primary six segments form the reviewed G17 jamb-bounded two-face
    interruption. The optional competitor is a second independent wall band in
    the same exact producer-owned source scope. Host V3 must never make that
    competitor disappear merely because a downstream caller would prefer a
    local subset.
    """
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        shape = page.new_shape()
        segments = [
            ((20.0, 80.0), (120.0, 80.0)),
            ((160.0, 80.0), (280.0, 80.0)),
            ((20.0, 100.0), (120.0, 100.0)),
            ((160.0, 100.0), (280.0, 100.0)),
            ((120.0, 80.0), (120.0, 100.0)),
            ((160.0, 80.0), (160.0, 100.0)),
        ]
        if include_competitor:
            segments.extend(
                [
                    ((20.0, 128.0), (120.0, 128.0)),
                    ((160.0, 128.0), (280.0, 128.0)),
                    ((20.0, 148.0), (120.0, 148.0)),
                    ((160.0, 148.0), (280.0, 148.0)),
                    ((120.0, 128.0), (120.0, 148.0)),
                    ((160.0, 128.0), (160.0, 148.0)),
                ]
            )
        for start, end in segments:
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def make_real_host_fixture(*, include_competitor: bool = False) -> RealHostFixture:
    producer = SourceVisibilityProducer(
        producer_method="host-binding-v3-validator-native-pdf",
        producer_version="3",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-host-v3",
        source_bytes=_host_pdf_bytes(include_competitor=include_competitor),
        source_locator="memory://host-binding-v3.pdf",
    )
    assert published.coverage.state == "complete"
    assert published.coverage.failed_pages == ()
    assert published.coverage.decoded_pages == (1,)
    assert len(published.visible_observation_ids) >= 6

    source_authority = producer.authority()
    physical = PhysicalOpeningAuthority(source_authority)
    selectors = tuple(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.visible_observation_ids
    )

    positives: list[tuple[ObservationSelector, object]] = []
    for selector in selectors:
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            positives.append((selector, result))
    assert len(positives) >= 2, "real source must prove at least one opening twice"

    first_selector, first_result = positives[0]
    record = first_result.existence_record
    assert record is not None
    peer_selector = None
    for selector, result in positives[1:]:
        candidate = result.existence_record
        if candidate is None or candidate.record_id != record.record_id:
            continue
        identity = physical.compare_identity(first_selector, selector)
        if (
            identity.status is EvidenceResolutionStatus.CORROBORATED
            and identity.proven_same is True
            and identity.physical_opening_identity == record.record_id
            and PHYSICAL_OPENING_IDENTITY_RESOLVED in identity.reason_codes
        ):
            peer_selector = selector
            break
    assert peer_selector is not None, "real opening identity must be independently re-proven"

    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(producer)
    wall_authority = wall_producer.authority()
    wall_selector = PhysicalWallCandidateSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        page_id=record.page_id,
        decision_scope_id=f"wall-source:page-{record.page_id}",
    )
    wall_scope = wall_authority.resolve_scope(wall_selector)
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    assert tuple(wall_scope.records)
    assert set(wall_scope.source_observation_ids) == set(published.visible_observation_ids)
    assert all(item.physical_identity.usable for item in wall_scope.records)

    return RealHostFixture(
        source_producer=producer,
        source_authority=source_authority,
        published=published,
        physical_opening_authority=physical,
        left_selector=first_selector,
        right_selector=peer_selector,
        existence_record=record,
        wall_producer=wall_producer,
        wall_authority=wall_authority,
        wall_selector=wall_selector,
        wall_scope=wall_scope,
    )


def wall_record_ids(fixture: RealHostFixture) -> tuple[str, ...]:
    return tuple(record.wall_candidate_id for record in fixture.wall_scope.records)
