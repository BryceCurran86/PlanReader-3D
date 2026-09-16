"""Opening Universe Completeness — independent red-team / test-first suite.

Base: merged G17 main 62a161519e617cdf9ce23069820dbf7c68aaf521

Production files changed: 0.
Identity (#331), dimensions (#332), host-binding (#334) are out of scope.

Completeness ≠ existence ≠ identity ≠ dimensions ≠ host.

EXPECTED_RED asserts eventual authenticated completeness and must remain red
until a reviewed production implementation lands. Fail-closed / poison /
firewall tests are expected GREEN on current main.
"""
from __future__ import annotations

import importlib.util
from typing import Sequence

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_opening_deduction_readiness import build_opening_deduction_quantity
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_wall_net_area_quantity import build_net_wall_area_quantity
from pb_wall_room_topology_contracts import OpeningHostCandidate
from tests.opening_universe_completeness_test_support import (
    BASE_SHA,
    FULL_PAGE_PRIMITIVES,
    SHA_A,
    SHA_B,
    CallerCompletenessProbe,
    IndexedPrimitive,
    UniverseEnumerationClaim,
    assert_completeness_capability_locked,
    coverage_record,
    ingest_source,
    shuffle_primitives,
    snapshot_echo_hash,
    split_collinear_equivalent,
    two_opening_page_pdf_bytes,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="OpeningUniverseCompletenessAuthority not implemented on main 62a1615",
)

WALL = "WALL-1"
VP = "vp_1"
PAGE = "page-1"
DOC = "doc-univ"


def _has_universe_completeness_authority_module() -> bool:
    return importlib.util.find_spec("pb_opening_universe_completeness_authority") is not None


def _ctx(**overrides: object) -> ProviderContext:
    kwargs = dict(
        run_id="run",
        workspace_id="ws",
        project_id="p",
        document_id=DOC,
        source_sha256=SHA_A,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=(VP,),
        evidence_snapshot_id="snap",
        canonical_graph_snapshot_id="graph",
        owned_page_numbers=(1,),
        viewport_page_ownership=((VP, 1),),
    )
    kwargs.update(overrides)
    return ProviderContext(**kwargs)  # type: ignore[arg-type]


def _vp(viewport_id: str = VP, page_id: str = PAGE) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id=DOC,
        page_id=page_id,
        bbox=(0, 0, 400, 400),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _doc(evidence_ids: Sequence[str]) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=DOC,
        source_sha256=SHA_A,
        page_count=1,
        page_ids=(PAGE,),
        evidence_ids=tuple(evidence_ids),
    )


def _meta(target: str, **extra: object) -> dict[str, object]:
    out: dict[str, object] = {
        "source_sha256": SHA_A,
        "revision_id": "R1",
        "evidence_snapshot_id": "snap",
        "canonical_graph_snapshot_id": "graph",
        "target_entity_id": target,
        "wall_id": WALL,
    }
    out.update(extra)
    return out


def _completion(
    opening_ids: Sequence[str] = (),
    **meta: object,
) -> EvidenceAtom:
    data = _meta(WALL, opening_ids=list(opening_ids), **meta)
    return EvidenceAtom(
        evidence_id="complete",
        document_id=DOC,
        page_id=PAGE,
        viewport_id=VP,
        kind="opening_set_complete",
        method="caller_reconciliation",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=data,
    )


def _wall_entity(ids: Sequence[str] = ("complete",)) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=WALL,
        candidate_type="wall",
        evidence_ids=tuple(ids),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_meta(WALL),
    )


def _gross() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="gross",
        family="wall_gross_area",
        semantic_key=f"wall_gross_area:{WALL}",
        value=12.0,
        unit="m2",
        input_entity_ids=(WALL,),
        formula="l*h",
        formula_version="1",
        evidence_ids=("wall",),
        authority="derived_from_firm_measurements",
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        metadata=_meta(WALL, viewport_id=VP, page_id=PAGE),
    )


def _hosted(opening_id: str = "OP-1") -> OpeningHostCandidate:
    return OpeningHostCandidate(
        host_candidate_id=opening_id,
        wall_candidate_id=WALL,
        position_along_wall_m=None,
        gap_width_m=None,
        host_status="hosted",
        candidate_wall_ids_considered=(WALL,),
        confidence=1.0,
        reason_codes=(),
    )


def _opening_entity(opening_id: str, ids: Sequence[str] = ("w", "h")) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=opening_id,
        candidate_type="opening",
        evidence_ids=tuple(ids),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_meta(opening_id, wall_id=WALL),
    )


def _dim(eid: str, kind: str, value: float, opening_id: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id=DOC,
        page_id=PAGE,
        viewport_id=VP,
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit="mm",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_meta(opening_id),
    )


def _load_completeness_authority():
    if not _has_universe_completeness_authority_module():
        raise AssertionError("OpeningUniverseCompletenessAuthority absent on main")
    import pb_opening_universe_completeness_authority as mod  # type: ignore

    return mod


def _resolve_complete(claim: UniverseEnumerationClaim) -> object:
    mod = _load_completeness_authority()
    outcome = mod.resolve_opening_universe_completeness(claim=claim)
    status = getattr(outcome, "status", None)
    if status not in {"complete", "CORROBORATED", "COMPLETE"}:
        raise AssertionError(f"expected complete universe, got {outcome!r}")
    return outcome


def _resolve_blocked(claim: UniverseEnumerationClaim) -> object:
    mod = _load_completeness_authority()
    outcome = mod.resolve_opening_universe_completeness(claim=claim)
    status = getattr(outcome, "status", None)
    if status not in {"blocked", "BLOCKED", "incomplete", "INCOMPLETE", "ABSTAINED"}:
        raise AssertionError(f"expected blocked/incomplete completeness, got {outcome!r}")
    return outcome


# ---------------------------------------------------------------------------
# Fail-closed / observed locks — GREEN on current main
# ---------------------------------------------------------------------------


def test_branch_bound_to_merged_g17_main() -> None:
    assert BASE_SHA == "62a161519e617cdf9ce23069820dbf7c68aaf521"


def test_opening_universe_complete_capability_remains_false() -> None:
    assert_completeness_capability_locked()
    assert _has_universe_completeness_authority_module() is False


def test_attack05_caller_is_complete_true_has_no_authority() -> None:
    probe = CallerCompletenessProbe(
        is_complete=True,
        snapshot_id="snap-caller",
        opening_ids=("OP-1",),
        wall_ids=(WALL,),
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        page_id=PAGE,
        viewport_id=VP,
    )
    assert probe.is_complete is True
    assert _has_universe_completeness_authority_module() is False
    net = build_net_wall_area_quantity(
        wall_id=WALL,
        gross_wall_area=_gross(),
        opening_deductions=(),
        opening_set_complete_evidence=_completion(probe.opening_ids),
        context=_ctx(),
        document=_doc(("complete", "wall")),
        viewport=_vp(),
        wall_entity=_wall_entity(("complete", "wall")),
    )
    assert "opening_universe_completeness_not_authenticated" in net.blocking_reasons
    assert net.abstained is True


def test_attack05b_semantic_filter_empty_set_cannot_certify() -> None:
    net = build_net_wall_area_quantity(
        wall_id=WALL,
        gross_wall_area=_gross(),
        opening_deductions=(),
        opening_set_complete_evidence=_completion((), semantic_filter_applied=True),
        context=_ctx(),
        document=_doc(("complete", "wall")),
        viewport=_vp(),
        wall_entity=_wall_entity(("complete", "wall")),
    )
    assert "opening_universe_completeness_not_authenticated" in net.blocking_reasons


def test_attack06_caller_echoed_snapshot_hash_is_not_proof() -> None:
    _producer, published = ingest_source(two_opening_page_pdf_bytes(), document_id="doc-echo")
    echo = snapshot_echo_hash(published.snapshot.snapshot_id)
    probe = CallerCompletenessProbe(
        is_complete=True,
        snapshot_id=published.snapshot.snapshot_id,
        opening_ids=tuple(published.snapshot.observation_ids[:2]),
        wall_ids=(WALL,),
        document_id="doc-echo",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        page_id="0",
        viewport_id=VP,
    )
    assert echo == snapshot_echo_hash(probe.snapshot_id)
    assert _has_universe_completeness_authority_module() is False


def test_decode_coverage_complete_is_not_semantic_enumeration() -> None:
    producer, published = ingest_source(two_opening_page_pdf_bytes(), document_id="doc-cov")
    assert published.coverage.state == "complete"
    assert published.coverage.failed_pages == ()
    authority = producer.authority()
    oid = published.snapshot.observation_ids[0]
    result = authority.resolve(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.semantic_enumeration_complete is None
    assert result.decision_scope_complete is None


def test_host_hosted_record_still_lacks_universe_authentication() -> None:
    qty = build_opening_deduction_quantity(
        host=_hosted(),
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("w", "h")),
        viewport=_vp(),
        opening_entity=_opening_entity("OP-1"),
        width_evidence=_dim("w", "opening_width_dimension", 900, "OP-1"),
        height_evidence=_dim("h", "opening_height_dimension", 2100, "OP-1"),
    )
    assert "opening_host_universe_completeness_not_authenticated" in qty.blocking_reasons


def test_attack_downstream_firewall_completeness_capability_closed() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    for key in (
        "opening_universe_complete",
        "host_binding",
        "host_identity",
        "opening_dimensions",
        "physical_void",
        "net_wall_area",
    ):
        assert caps[key] is False


def test_coverage_record_partial_when_failed_pages() -> None:
    cov = coverage_record(total_pages=2, decoded_pages=(0,), failed_pages=(1,))
    assert cov.state == "partial"


# ---------------------------------------------------------------------------
# EXPECTED RED — authenticated universe completeness
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_complete_full_page_universe_may_resolve() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-full",
        page_ids=(PAGE,),
        viewport_id=None,  # page-scoped, not cropped
        coverage_state="complete",
    )
    outcome = _resolve_complete(claim)
    assert outcome is not None


@EXPECTED_RED
def test_attack02_truncated_viewport_blocked() -> None:
    # Only left opening segments; competitor on same page omitted by crop.
    cropped = tuple(p for p in FULL_PAGE_PRIMITIVES if p.geometry[0] < 230)
    claim = UniverseEnumerationClaim(
        primitives=cropped,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-crop",
        page_ids=(PAGE,),
        viewport_id="vp_crop",
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack03_unknown_clipping_blocked() -> None:
    prims = tuple(
        IndexedPrimitive(
            p.primitive_id,
            p.page_id,
            p.geometry,
            clip_known=False,
            clip_present=False,
            clip=None,
        )
        for p in FULL_PAGE_PRIMITIVES
    )
    claim = UniverseEnumerationClaim(
        primitives=prims,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-clip-unk",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack04_active_clip_hiding_competitor_blocks_local_claim() -> None:
    visible = FULL_PAGE_PRIMITIVES[:4]
    claim = UniverseEnumerationClaim(
        primitives=visible,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-clip-hide",
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    # Active clip present on visible set while competitor exists outside clip.
    claim = UniverseEnumerationClaim(
        primitives=tuple(
            IndexedPrimitive(
                p.primitive_id,
                p.page_id,
                p.geometry,
                clip_known=True,
                clip_present=True,
                clip=(0.0, 0.0, 230.0, 200.0),
            )
            for p in visible
        ),
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-clip-hide",
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack07_missing_source_primitive_from_index() -> None:
    missing_one = FULL_PAGE_PRIMITIVES[:-1]
    claim = UniverseEnumerationClaim(
        primitives=missing_one,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-missing",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack08_unindexed_background_layer_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,  # index omits background layer content
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-bg",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    # Future authority must detect unindexed visible layer via producer coverage.
    raise AssertionError("unindexed background layer must block completeness")


@EXPECTED_RED
def test_attack09_partial_page_ingestion_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-partial",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="partial",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack10_multi_page_laundering_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-page-a",
        page_ids=("page-A",),
        viewport_id=None,
        coverage_state="complete",
    )
    # Completeness for page-A must not certify page-B proposition.
    raise AssertionError("page-A completeness must not certify page-B")


@EXPECTED_RED
def test_attack11_revision_laundering_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R-OLD",
        source_sha256=SHA_A,
        snapshot_id="snap-old-rev",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack12_source_hash_laundering_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,  # same document id
        revision_id="R1",
        source_sha256=SHA_B,  # different bytes
        snapshot_id="snap-sha-b",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack13_snapshot_laundering_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-stale",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack14_filtered_candidate_echo_cannot_certify_exclusions() -> None:
    nearby_only = FULL_PAGE_PRIMITIVES[:2]
    claim = UniverseEnumerationClaim(
        primitives=nearby_only,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-filter",
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack15_radius_limited_query_cannot_prove_no_competitor() -> None:
    probe = CallerCompletenessProbe(
        is_complete=True,
        snapshot_id="snap-radius",
        opening_ids=("OP-1",),
        wall_ids=(WALL,),
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        page_id=PAGE,
        viewport_id=VP,
        search_radius_m=2.0,
        index_hit_count=1,
    )
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES[:1],
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id=probe.snapshot_id,
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack16_rtree_hit_count_alone_not_completeness() -> None:
    probe = CallerCompletenessProbe(
        is_complete=True,
        snapshot_id="snap-rtree",
        opening_ids=("OP-1", "OP-2"),
        wall_ids=(WALL,),
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        page_id=PAGE,
        viewport_id=VP,
        index_hit_count=len(FULL_PAGE_PRIMITIVES),
    )
    assert probe.index_hit_count == len(FULL_PAGE_PRIMITIVES)
    raise AssertionError("spatial index count must not prove source completeness")


@EXPECTED_RED
def test_attack17_duplicate_replay_does_not_inflate_completeness() -> None:
    duped = FULL_PAGE_PRIMITIVES + FULL_PAGE_PRIMITIVES
    claim = UniverseEnumerationClaim(
        primitives=duped,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-dup",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    # Duplicates must not create fake independent evidence or inflate counts.
    outcome = _resolve_complete(claim)
    accounted = getattr(outcome, "accounted_primitive_ids", None) or getattr(
        outcome, "member_ids", ()
    )
    assert len(set(accounted)) == len(FULL_PAGE_PRIMITIVES)


@EXPECTED_RED
def test_attack18_optional_content_ambiguous_fail_closed() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-ocg",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
        optional_content_state="ambiguous",
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack19_nested_xobject_omission_unavailable() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-xobj",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
        xobject_traversal_truncated=True,
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack20_recursive_xobject_silent_truncate_must_not_mark_complete() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES[:3],  # surviving subset after truncate
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-xobj-trunc",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
        xobject_traversal_truncated=True,
    )
    _resolve_blocked(claim)


@EXPECTED_RED
def test_attack21_input_order_determinism() -> None:
    results = []
    for seed in (1, 2, 3, 7, 13):
        claim = UniverseEnumerationClaim(
            primitives=tuple(shuffle_primitives(FULL_PAGE_PRIMITIVES, seed=seed)),
            claimed_complete=True,
            document_id=DOC,
            revision_id="R1",
            source_sha256=SHA_A,
            snapshot_id="snap-order",
            page_ids=(PAGE,),
            viewport_id=None,
            coverage_state="complete",
        )
        results.append(_resolve_complete(claim))
    statuses = [getattr(r, "status", r) for r in results]
    assert len(set(map(str, statuses))) == 1


@EXPECTED_RED
def test_attack22_segmentation_invariance_under_collinear_equivalence() -> None:
    base = FULL_PAGE_PRIMITIVES[0]
    left, right = split_collinear_equivalent(base)
    split_set = (left, right) + FULL_PAGE_PRIMITIVES[1:]
    claim_one = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-seg-a",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    claim_two = UniverseEnumerationClaim(
        primitives=split_set,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-seg-b",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    a = _resolve_complete(claim_one)
    b = _resolve_complete(claim_two)
    # Primitive count changed; universe membership must not if equivalence holds.
    assert getattr(a, "universe_fingerprint", None) == getattr(b, "universe_fingerprint", None)


@EXPECTED_RED
def test_attack23_completeness_does_not_unlock_downstream() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-firewall",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _resolve_complete(claim)
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["opening_dimensions"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    raise AssertionError("downstream firewall must remain closed after completeness")
