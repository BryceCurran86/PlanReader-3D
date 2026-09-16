"""Opening Universe Completeness — current-main executable validator v2.

Exact base: e27ffad284b05123ffacbbe123c69823c5367dee
Historical attack source: PR #335 @ ee732e7a5536265cd87bfcbeb2abe180e8d1245d

Thirty historical tests are preserved by identity and intent: nine current-main
fail-closed/firewall checks plus twenty-one strict expected-RED attacks.  The
successor removes historical placeholder failures and does not pass
``UniverseEnumerationClaim`` to the authority.  Expected production shape is a
trusted writer that owns enumeration records and a read-only
``OpeningUniverseCompletenessAuthority.resolve(OpeningUniverseSelector)``
boundary.  Ordinary query callers supply only lineage/scope selectors.
"""
from __future__ import annotations

import importlib
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
from tests.opening_universe_completeness_test_support_v2 import (
    BACKGROUND_PRIMITIVE,
    BASE_SHA,
    FULL_PAGE_PRIMITIVES,
    HISTORICAL_335_HEAD,
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


MODULE_NAME = "pb_opening_universe_completeness_authority"
HAS_COMPLETENESS_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_COMPLETENESS_AUTHORITY,
    strict=True,
    reason="producer-owned opening-universe completeness authority is absent on e27ffad",
)

WALL = "WALL-1"
VP = "vp_1"
PAGE = "page-1"
DOC = "doc-univ"
SCOPE = "opening-host-decision:page-1"
_UNSET = object()


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


def _completion(opening_ids: Sequence[str] = (), **meta: object) -> EvidenceAtom:
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


def _require_api():
    assert HAS_COMPLETENESS_AUTHORITY, (
        "OpeningUniverseCompletenessAuthority.resolve(selector) and its trusted "
        "producer are the genuine missing behaviors on the validator base"
    )
    mod = importlib.import_module(MODULE_NAME)
    for name in (
        "OpeningUniverseCompletenessProducer",
        "OpeningUniverseCompletenessAuthority",
        "OpeningUniverseSelector",
    ):
        assert hasattr(mod, name), f"missing required producer-owned completeness API: {name}"
    return mod


def _coverage_for(
    *,
    document_id: str,
    revision_id: str,
    page_ids: tuple[str, ...],
    state: str,
):
    total = max(1, len(page_ids))
    if state == "complete":
        return coverage_record(
            document_id=document_id,
            revision_id=revision_id,
            total_pages=total,
            decoded_pages=tuple(range(1, total + 1)),
            failed_pages=(),
        )
    return coverage_record(
        document_id=document_id,
        revision_id=revision_id,
        total_pages=total,
        decoded_pages=tuple(range(1, total)),
        failed_pages=(total,),
    )


def _resolve(
    claim: UniverseEnumerationClaim,
    *,
    source_primitives: Sequence[IndexedPrimitive] | None = None,
    producer_document_id: str = DOC,
    producer_revision_id: str = "R1",
    producer_source_sha256: str = SHA_A,
    producer_snapshot_id: str | None = None,
    producer_page_ids: tuple[str, ...] | None = None,
    producer_viewport_id: str | None | object = _UNSET,
    producer_scope_id: str = SCOPE,
    selector_document_id: str | None = None,
    selector_revision_id: str | None = None,
    selector_source_sha256: str | None = None,
    selector_snapshot_id: str | None = None,
    selector_scope_id: str | None = None,
):
    """Install trusted producer state, then query using selector-only authority.

    ``UniverseEnumerationClaim`` is only scenario input for the trusted writer.
    It is never passed to ``authority.resolve`` and therefore cannot be a
    consumer self-certification object.
    """

    mod = _require_api()
    trusted_snapshot = producer_snapshot_id or claim.snapshot_id
    trusted_pages = producer_page_ids or claim.page_ids
    trusted_viewport = (
        claim.viewport_id if producer_viewport_id is _UNSET else producer_viewport_id
    )
    producer = mod.OpeningUniverseCompletenessProducer(
        producer_method="gpt2-opening-universe-completeness-redteam-v2",
        producer_version="1.0",
    )
    coverage = _coverage_for(
        document_id=producer_document_id,
        revision_id=producer_revision_id,
        page_ids=trusted_pages,
        state=claim.coverage_state,
    )
    producer.publish_enumeration(
        decision_scope_id=producer_scope_id,
        decision_scope_kind="opening_host_competitor_universe",
        document_id=producer_document_id,
        revision_id=producer_revision_id,
        source_sha256=producer_source_sha256,
        snapshot_id=trusted_snapshot,
        page_ids=trusted_pages,
        viewport_id=trusted_viewport,
        coverage=coverage,
        source_primitives=tuple(source_primitives or FULL_PAGE_PRIMITIVES),
        enumerated_primitives=claim.primitives,
        optional_content_state=claim.optional_content_state,
        xobject_traversal_truncated=claim.xobject_traversal_truncated,
    )
    authority = producer.authority()
    assert isinstance(authority, mod.OpeningUniverseCompletenessAuthority)
    selector = mod.OpeningUniverseSelector(
        document_id=selector_document_id or claim.document_id,
        revision_id=selector_revision_id or claim.revision_id,
        source_sha256=selector_source_sha256 or claim.source_sha256,
        snapshot_id=selector_snapshot_id or claim.snapshot_id,
        decision_scope_id=selector_scope_id or producer_scope_id,
    )
    return authority.resolve(selector)


def _assert_complete(result, *, expected_scope: str = SCOPE) -> None:
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.source_decode_complete is True
    assert result.semantic_enumeration_complete is True
    assert result.decision_scope_complete is True
    assert result.record is not None
    assert result.record.decision_scope_id == expected_scope
    assert result.record.enumeration_state == "complete"
    assert result.record.record_id
    assert result.record.universe_fingerprint


def _assert_blocked(result) -> None:
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.semantic_enumeration_complete is not True or result.decision_scope_complete is not True
    assert result.reason_codes


# ---------------------------------------------------------------------------
# Nine current-main GREEN fail-closed / poison / firewall checks
# ---------------------------------------------------------------------------


def test_branch_bound_to_merged_g17_main() -> None:
    assert BASE_SHA == "e27ffad284b05123ffacbbe123c69823c5367dee"
    assert HISTORICAL_335_HEAD == "ee732e7a5536265cd87bfcbeb2abe180e8d1245d"


def test_opening_universe_complete_capability_remains_false() -> None:
    assert_completeness_capability_locked(
        expect_completeness=False if not HAS_COMPLETENESS_AUTHORITY else None
    )


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
        page_id="1",
        viewport_id=VP,
    )
    assert echo == snapshot_echo_hash(probe.snapshot_id)
    if HAS_COMPLETENESS_AUTHORITY:
        mod = importlib.import_module(MODULE_NAME)
        assert not hasattr(mod, "resolve_opening_universe_completeness"), (
            "public claim-based resolver would re-open caller self-certification"
        )


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
    assert_completeness_capability_locked(
        expect_completeness=False if not HAS_COMPLETENESS_AUTHORITY else None
    )


def test_coverage_record_partial_when_failed_pages() -> None:
    cov = coverage_record(total_pages=2, decoded_pages=(1,), failed_pages=(2,))
    assert cov.state == "partial"


# ---------------------------------------------------------------------------
# Twenty-one strict EXPECTED-RED attacks. No placeholder AssertionError paths.
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
        viewport_id=None,
        coverage_state="complete",
    )
    result = _resolve(claim)
    _assert_complete(result)
    assert tuple(result.record.page_ids) == (PAGE,)
    assert result.record.document_id == DOC
    assert result.record.revision_id == "R1"
    assert result.record.source_sha256 == SHA_A
    assert result.record.snapshot_id == "snap-full"


@EXPECTED_RED
def test_attack02_truncated_viewport_blocked() -> None:
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
    _assert_blocked(_resolve(claim))


@EXPECTED_RED
def test_attack03_unknown_clipping_blocked() -> None:
    prims = tuple(
        IndexedPrimitive(
            p.primitive_id,
            p.page_id,
            p.geometry,
            layer=p.layer,
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
    _assert_blocked(_resolve(claim, source_primitives=prims))


@EXPECTED_RED
def test_attack04_active_clip_hiding_competitor_blocks_local_claim() -> None:
    visible = FULL_PAGE_PRIMITIVES[:4]
    clipped = tuple(
        IndexedPrimitive(
            p.primitive_id,
            p.page_id,
            p.geometry,
            layer=p.layer,
            clip_known=True,
            clip_present=True,
            clip=(0.0, 0.0, 230.0, 200.0),
        )
        for p in visible
    )
    claim = UniverseEnumerationClaim(
        primitives=clipped,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-clip-hide",
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    _assert_blocked(_resolve(claim))


@EXPECTED_RED
def test_attack07_missing_source_primitive_from_index() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES[:-1],
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-missing",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _assert_blocked(_resolve(claim))


@EXPECTED_RED
def test_attack08_unindexed_background_layer_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-bg",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    source_truth = FULL_PAGE_PRIMITIVES + (BACKGROUND_PRIMITIVE,)
    _assert_blocked(_resolve(claim, source_primitives=source_truth))


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
    _assert_blocked(_resolve(claim))


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
    result = _resolve(
        claim,
        producer_page_ids=("page-A",),
        producer_scope_id="scope-page-A",
        selector_scope_id="scope-page-B",
    )
    _assert_blocked(result)


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
    _assert_blocked(
        _resolve(
            claim,
            producer_revision_id="R1",
            producer_snapshot_id="snap-current",
        )
    )


@EXPECTED_RED
def test_attack12_source_hash_laundering_blocked() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_B,
        snapshot_id="snap-sha-b",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    _assert_blocked(
        _resolve(
            claim,
            producer_source_sha256=SHA_A,
            producer_snapshot_id="snap-sha-a",
        )
    )


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
    _assert_blocked(_resolve(claim, producer_snapshot_id="snap-current"))


@EXPECTED_RED
def test_attack14_filtered_candidate_echo_cannot_certify_exclusions() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES[:2],
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-filter",
        page_ids=(PAGE,),
        viewport_id=VP,
        coverage_state="complete",
    )
    _assert_blocked(_resolve(claim))


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
        claimed_complete=probe.is_complete,
        document_id=probe.document_id,
        revision_id=probe.revision_id,
        source_sha256=probe.source_sha256,
        snapshot_id=probe.snapshot_id,
        page_ids=(probe.page_id,),
        viewport_id=probe.viewport_id,
        coverage_state="complete",
    )
    assert probe.search_radius_m == 2.0
    _assert_blocked(_resolve(claim))


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
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES,
        claimed_complete=probe.is_complete,
        document_id=probe.document_id,
        revision_id=probe.revision_id,
        source_sha256=probe.source_sha256,
        snapshot_id=probe.snapshot_id,
        page_ids=(probe.page_id,),
        viewport_id=probe.viewport_id,
        coverage_state="complete",
    )
    assert probe.index_hit_count == len(claim.primitives)
    source_truth = FULL_PAGE_PRIMITIVES + (BACKGROUND_PRIMITIVE,)
    _assert_blocked(_resolve(claim, source_primitives=source_truth))


@EXPECTED_RED
def test_attack17_duplicate_replay_does_not_inflate_completeness() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES + FULL_PAGE_PRIMITIVES,
        claimed_complete=True,
        document_id=DOC,
        revision_id="R1",
        source_sha256=SHA_A,
        snapshot_id="snap-dup",
        page_ids=(PAGE,),
        viewport_id=None,
        coverage_state="complete",
    )
    result = _resolve(claim)
    _assert_complete(result)
    accounted = tuple(result.record.accounted_member_ids)
    assert len(accounted) == len(set(accounted)) == len(FULL_PAGE_PRIMITIVES)


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
    _assert_blocked(_resolve(claim))


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
    _assert_blocked(_resolve(claim))


@EXPECTED_RED
def test_attack20_recursive_xobject_silent_truncate_must_not_mark_complete() -> None:
    claim = UniverseEnumerationClaim(
        primitives=FULL_PAGE_PRIMITIVES[:3],
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
    _assert_blocked(_resolve(claim))


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
        result = _resolve(claim)
        _assert_complete(result)
        results.append(result)
    assert len({r.record.record_id for r in results}) == 1
    assert len({r.record.universe_fingerprint for r in results}) == 1
    assert len({r.status for r in results}) == 1


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
    first = _resolve(claim_one, source_primitives=FULL_PAGE_PRIMITIVES)
    second = _resolve(claim_two, source_primitives=split_set)
    _assert_complete(first)
    _assert_complete(second)
    assert first.record.universe_fingerprint == second.record.universe_fingerprint


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
    result = _resolve(claim)
    _assert_complete(result)
    caps = PhysicalOpeningAuthority.capabilities()
    for key in (
        "opening_dimensions",
        "host_identity",
        "host_binding",
        "physical_void",
        "net_wall_area",
    ):
        assert caps[key] is False
