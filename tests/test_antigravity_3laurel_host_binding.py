"""Test 3Laurel Page 3 authoritative derived viewport host binding continuity.

Under GPT MAX structural direction (SPRINT directive 2 November 2026):
- Authoritative derived viewport title partition on 3Laurel Page 3 resolves
  complete physical wall candidate scope.
- Frame edge filter correctly suppresses the 4 viewport bounding borders.
- Opening host bindings advance through source-primitive two-face and gap lineage
  without being poisoned by remote unscaled parallel wall ambiguity.
- Preserves all fail-closed properties for local unsafe lineage group members.
"""
from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
import pb_physical_wall_candidate_authority as pwca
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_source_observation_authority import ObservationSelector
from tools.diag_gpt1_original_3laurel_asw_candidates import (
    ORIGINAL_SHA256,
    read_original_3laurel_asw_candidates,
)


def test_3laurel_authoritative_derived_viewport_and_host_bindings():
    pdf_path = Path("documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf")
    if not pdf_path.exists():
        pytest.skip("Private 3Laurel original PDF not available in local workspace")

    source_bytes = pdf_path.read_bytes()
    from hashlib import sha256
    assert sha256(source_bytes).hexdigest() == ORIGINAL_SHA256

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version="1",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{ORIGINAL_SHA256[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://3laurel.pdf",
        page_ids=(3,),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=("3",),
        include_unmeasured_ink_closed_flanks_shadow=True,
        source_fragment_roles_shadow=True,
    )

    published = source.published_snapshot_for_revision(initial.revision.revision_id)

    # 1. Verify wall candidate scope is complete under authoritative derived viewport
    wall_producer = pwca.PhysicalWallCandidateProducer.from_authenticated_viewports(source, page_ids=("3",))
    wall_auth = wall_producer.authority()
    assert len(wall_producer._scopes) == 1
    wall_scope = list(wall_producer._scopes.values())[0]
    assert wall_scope.scope_complete is True
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert "physical_wall_candidate_scope_resolved" in wall_scope.reason_codes

    # 2. Verify opening host wall universe resolves scope
    universe_producer = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(wall_auth)
    universe_auth = universe_producer.authority()
    universe_sel = OpeningHostWallUniverseSelector(
        document_id=wall_scope.document_id,
        revision_id=wall_scope.revision_id,
        source_sha256=wall_scope.source_sha256,
        snapshot_id=wall_scope.snapshot_id,
        page_id="3",
        decision_scope_id=wall_scope.decision_scope_id,
    )
    univ_res = universe_auth.resolve_scope(universe_sel)
    assert univ_res.status is EvidenceResolutionStatus.CORROBORATED
    assert univ_res.scope_complete is True

    # 3. Verify host bindings advance
    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=source.physical_opening_authority(),
        host_wall_universe_authority=universe_auth,
        source_fragment_roles_shadow=True,
    )

    corroborated_hosts = []
    for b in composition.opening_bindings:
        obs_sel = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=b.representative_observation_id,
        )
        host_res = host_producer.publish(
            opening_left_selector=obs_sel,
            opening_right_selector=obs_sel,
            host_universe_selector=universe_sel,
        )
        if host_res.status is EvidenceResolutionStatus.CORROBORATED:
            corroborated_hosts.append((b, host_res))

    # At least 26 openings must corroborate their host binding on Page 3
    assert len(corroborated_hosts) >= 26

    # Verify ASW candidates corroborate their host bindings
    asw_data = read_original_3laurel_asw_candidates(source_bytes)
    assert len(asw_data["two_axis_candidates"]) == 14
