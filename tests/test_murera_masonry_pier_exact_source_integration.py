"""Optional, SHA-locked integration of the real source with production authority.

Set PLANREADER_MURERA_SOURCE_PDF to the official PDF to execute these tests.
The source hash and page selection belong to this integration fixture only.
No diagnostic probe, benchmark scorer, or expected quantity is imported.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_DEFINITION_ONLY,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberProducer,
    StructuralMemberSelector,
)
from pb_structural_member_definition_source_shadow import (
    compile_structural_definition_source_shadow,
)
from pb_structural_member_registration_producer import (
    STRUCTURAL_REGISTRATION_VIEW_COMPLETENESS_UNAUTHENTICATED,
    StructuralMemberRegistrationEvidenceProducer,
    build_structural_member_registration_authority,
)


MURERA_SOURCE_SHA256 = (
    "84dec737ede7adfa32b02c6732d4289a6a2d25f7ae50cf07209428f1b4e0c94b"
)


@pytest.fixture(scope="module")
def exact_source_path() -> Path:
    configured = os.environ.get("PLANREADER_MURERA_SOURCE_PDF")
    if not configured:
        pytest.skip("set PLANREADER_MURERA_SOURCE_PDF for exact-source integration")
    path = Path(configured)
    assert path.is_file(), f"configured exact source is missing: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MURERA_SOURCE_SHA256
    return path


@pytest.fixture(scope="module")
def exact_source_authorities(exact_source_path: Path):
    producer = SourceVisibilityProducer(
        producer_method="structural-member-exact-source-integration",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="official-structural-member-integration-source",
        source_bytes=exact_source_path.read_bytes(),
        source_locator=str(exact_source_path),
        page_ids=("183", "223", "225"),
    )
    assert published.revision.source_sha256 == MURERA_SOURCE_SHA256
    assert set(published.coverage.decoded_pages) == {183, 223, 225}
    selector = StructuralMemberSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="source-member-universe-unproven",
        member_kind="masonry_pier",
    )
    visibility = producer.authority()
    visible_by_page = {"223": [], "225": []}
    for observation_id in published.visible_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.observation is not None
        observation = result.observation
        if observation.page_id in visible_by_page:
            visible_by_page[observation.page_id].append(observation)
    assert all(visible_by_page.values()), "fixture must exercise real visible geometry"
    return producer, published, selector, visible_by_page


def test_exact_trusted_pier_definition_has_no_physical_member_authority(
    exact_source_authorities,
) -> None:
    producer, published, member_selector, _visible = exact_source_authorities
    # The definition parser owns generic role metadata; it does not own the
    # masonry-pier instance universe or a link from this unscoped page to it.
    selector = replace(member_selector, member_kind="structural_support")
    shadow = compile_structural_definition_source_shadow(
        selector=selector,
        source_visibility_producer=producer,
        page_ids=("183",),
    )
    assert shadow.status is EvidenceResolutionStatus.CORROBORATED
    piers = tuple(row for row in shadow.definitions if row.member_role == "pier")
    assert piers
    assert all(row.definition.page_id == "183" for row in piers)
    assert all(row.scope_id == "source-page:183:unscoped" for row in piers)
    assert all(row.definition.section_spec == "masonry; 300 x 300mm; pier" for row in piers)
    assert shadow.trusted_text_observation_ids
    assert set(shadow.trusted_text_observation_ids) <= set(published.text_observation_ids)

    authority = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        definitions=tuple(row.definition for row in piers),
        observations=(),
        relations=(),
        view_scopes=(),
    ).authority()
    resolution = authority.resolve(selector)
    assert resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert resolution.reason_codes == (STRUCTURAL_MEMBER_DEFINITION_ONLY,)
    assert resolution.quantity is None
    assert resolution.members == ()


@pytest.mark.parametrize("page_id", ("223", "225"))
def test_exact_visible_geometry_without_member_propositions_is_not_registered(
    exact_source_authorities,
    page_id: str,
) -> None:
    producer, published, selector, visible_by_page = exact_source_authorities
    evidence = StructuralMemberRegistrationEvidenceProducer.from_source_visibility(
        selector=selector,
        source_visibility_producer=producer,
    )
    view_id = f"source-page:{page_id}:unscoped"
    geometry = tuple(visible_by_page[page_id])
    # Submit every visible primitive on the selected page, without shape,
    # proximity, count, or role-intersection heuristics. Visibility receipts
    # authenticate the source, but supply no physical-member proposition.
    unowned = tuple(
        evidence.observation(
            member_kind=selector.member_kind,
            page_id=page_id,
            view_id=view_id,
            view_type="unscoped",
            source_evidence_ids=(row.observation_id,),
            source_primitive_ids=(row.source_primitive_ref,),
            member_proposition_evidence_ids=(),
        )
        for row in geometry
    )
    view = evidence.view(
        page_id=page_id,
        view_id=view_id,
        view_type="unscoped",
        complete=False,
        source_evidence_ids=tuple(row.observation_id for row in geometry),
        reason_codes=("source_member_universe_completeness_unproven",),
    )
    result = build_structural_member_registration_authority(
        selector=selector,
        source_observations=unowned,
        source_views=(view,),
    )
    assert result.observations == ()
    assert result.relations == ()
    assert result.view_scopes and all(not scope.complete for scope in result.view_scopes)
    authority = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        observations=result.observations,
        relations=result.relations,
        view_scopes=result.view_scopes,
    ).authority()
    resolution = authority.resolve(selector)
    assert resolution == result.resolution
    assert resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert resolution.reason_codes == (STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,)
    assert resolution.members == ()
    assert resolution.quantity is None
    assert producer.published_snapshot_for_revision(selector.revision_id) == published


def test_exact_source_receipts_cannot_authenticate_caller_claimed_complete_view(
    exact_source_authorities,
) -> None:
    producer, _published, selector, visible_by_page = exact_source_authorities
    evidence = StructuralMemberRegistrationEvidenceProducer.from_source_visibility(
        selector=selector,
        source_visibility_producer=producer,
    )
    with pytest.raises(
        ValueError,
        match=STRUCTURAL_REGISTRATION_VIEW_COMPLETENESS_UNAUTHENTICATED,
    ):
        evidence.view(
            page_id="225",
            view_id="source-page:225:unscoped",
            view_type="unscoped",
            complete=True,
            source_evidence_ids=tuple(
                row.observation_id for row in visible_by_page["225"]
            ),
        )


def test_exact_full_pdf_extraction_does_not_publish_unproven_masonry_piers(
    exact_source_path: Path,
) -> None:
    # This executes the full live extractor, independently of the scoped
    # structural checks above. It reads neither diagnostic rows nor gold.
    predictions = GenericPlanReaderExtractor().extract_from_pdf(exact_source_path)
    assert "masonry_piers" not in {prediction.tag for prediction in predictions}
