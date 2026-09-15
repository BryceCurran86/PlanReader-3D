from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
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
from pb_opening_deduction_readiness import (
    build_opening_deduction_quantities,
    build_opening_deduction_quantity,
)
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_wall_height_authority import build_wall_height_quantity
from pb_wall_net_area_quantity import build_net_wall_area_quantity
from pb_wall_room_topology_contracts import OpeningHostCandidate

SHA = "a" * 64
OTHER_SHA = "b" * 64
WALL = "WALL-1"
OPENING = "OP-1"
VP = "VP-1"
PAGE = "page-1"


def _ctx(**overrides: object) -> ProviderContext:
    values: dict[str, object] = {
        "run_id": "run",
        "workspace_id": "ws",
        "project_id": "project",
        "document_id": "doc",
        "source_sha256": SHA,
        "revision_id": "R1",
        "current_revision_id": "R1",
        "selected_pages": (0,),
        "owned_viewport_ids": (VP,),
        "evidence_snapshot_id": "evsnap-1",
        "canonical_graph_snapshot_id": "graphsnap-1",
        "measurement_authority_snapshot_id": "measuresnap-1",
        "owned_page_numbers": (1,),
        "viewport_page_ownership": ((VP, 1),),
    }
    values.update(overrides)
    return ProviderContext(**values)


def _viewport(*, viewport_id: str = VP, page_id: str = PAGE) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
        page_id=page_id,
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _doc(ids: tuple[str, ...], *, sha: str = SHA) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256=sha,
        page_count=1,
        page_ids=(PAGE,),
        evidence_ids=ids,
    )


def _prov(
    *,
    target: str,
    source_sha256: str = SHA,
    revision_id: str = "R1",
    evidence_snapshot_id: str = "evsnap-1",
    graph_snapshot_id: str = "graphsnap-1",
    **extra: object,
) -> dict[str, object]:
    out: dict[str, object] = {
        "source_sha256": source_sha256,
        "revision_id": revision_id,
        "evidence_snapshot_id": evidence_snapshot_id,
        "canonical_graph_snapshot_id": graph_snapshot_id,
        "target_entity_id": target,
    }
    out.update(extra)
    return out


def _height_ev(
    eid: str = "h",
    *,
    kind: str = "wall_height_dimension",
    value: float = 3.0,
    page_id: str = PAGE,
    viewport_id: str | None = VP,
    metadata: dict[str, object] | None = None,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc",
        page_id=page_id,
        viewport_id=viewport_id,
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit="m",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata=metadata if metadata is not None else _prov(target=WALL, height_semantic_role="wall_height"),
    )


def _height_entity(ids: tuple[str, ...], *, metadata: dict[str, object] | None = None,
                   status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
                   conflicts: tuple[str, ...] = ()) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=WALL,
        candidate_type="wall",
        evidence_ids=ids,
        status=status,
        confidence=1.0,
        conflict_evidence_ids=conflicts,
        metadata=metadata or _prov(target=WALL),
    )


def _height_qty(ev: EvidenceAtom, *, context: ProviderContext | None = None,
                entity: EntityEvidence | None = None) -> QuantityEvidence:
    ctx = context or _ctx()
    ent = entity or _height_entity((ev.evidence_id,))
    return build_wall_height_quantity(
        wall_id=WALL,
        context=ctx,
        document=_doc((ev.evidence_id,)),
        viewport=_viewport(),
        entity=ent,
        direct_height_evidence=ev,
    )


def _opening_ev(
    eid: str,
    kind: str,
    value: float,
    *,
    opening_id: str = OPENING,
    viewport_id: str | None = VP,
    page_id: str = PAGE,
    metadata: dict[str, object] | None = None,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc",
        page_id=page_id,
        viewport_id=viewport_id,
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit="mm",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata=metadata if metadata is not None else _prov(
            target=opening_id,
            physical_opening_id=opening_id,
            phase="new",
            commercial_applicability="applicable",
        ),
    )


def _opening_entity(
    opening_id: str = OPENING,
    ids: tuple[str, ...] = ("ow", "oh"),
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    metadata: dict[str, object] | None = None,
    conflicts: tuple[str, ...] = (),
) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=opening_id,
        candidate_type="opening",
        evidence_ids=ids,
        status=status,
        confidence=1.0,
        conflict_evidence_ids=conflicts,
        metadata=metadata or _prov(
            target=opening_id,
            physical_opening_id=opening_id,
            physical_identity_status="proven",
            phase="new",
            commercial_applicability="applicable",
        ),
    )


def _host(
    opening_id: str = OPENING,
    *,
    status: str = "hosted",
    walls: tuple[str, ...] = (WALL,),
    wall_id: str = WALL,
    reasons: tuple[str, ...] = (),
) -> OpeningHostCandidate:
    if status == "ambiguous_host" and not reasons:
        reasons = ("multiple_plausible_wall_candidates",)
    return OpeningHostCandidate(
        host_candidate_id=opening_id,
        wall_candidate_id=wall_id,
        position_along_wall_m=None,
        gap_width_m=None,
        host_status=status,
        candidate_wall_ids_considered=walls,
        confidence=1.0,
        reason_codes=reasons,
    )


def _deduction(
    *,
    host: OpeningHostCandidate | None = None,
    entity: EntityEvidence | None = None,
    width: EvidenceAtom | None = None,
    height: EvidenceAtom | None = None,
    context: ProviderContext | None = None,
) -> QuantityEvidence:
    host = host or _host()
    width = width if width is not None else _opening_ev("ow", "opening_width_dimension", 900.0)
    height = height if height is not None else _opening_ev("oh", "opening_height_dimension", 2100.0)
    ids = tuple(e.evidence_id for e in (width, height) if e is not None)
    entity = entity or _opening_entity(host.host_candidate_id, ids=ids)
    return build_opening_deduction_quantity(
        host=host,
        wall_id=WALL,
        context=context or _ctx(),
        document=_doc(ids),
        viewport=_viewport(),
        opening_entity=entity,
        width_evidence=width,
        height_evidence=height,
    )


def _gross_fixture(value: float = 12.0) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="gross",
        family="wall_gross_area",
        semantic_key=f"wall_gross_area:{WALL}",
        value=value,
        unit="m2",
        input_entity_ids=(WALL,),
        formula="length*height",
        formula_version="test",
        evidence_ids=("wall-ev",),
        authority="derived_from_firm_measurements",
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "viewport_id": VP,
            "page_id": PAGE,
            "page_no": 1,
            "evidence_snapshot_id": "evsnap-1",
            "canonical_graph_snapshot_id": "graphsnap-1",
        },
    )


def _deduction_fixture(opening_id: str = OPENING, value: float = 1.89) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"ded-{opening_id}",
        family="opening_deduction_area",
        semantic_key=f"opening_deduction:{opening_id}",
        value=value,
        unit="m2",
        input_entity_ids=(opening_id, WALL),
        formula="width*height",
        formula_version="test",
        evidence_ids=(f"{opening_id}-w", f"{opening_id}-h"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "viewport_id": VP,
            "page_id": PAGE,
            "evidence_snapshot_id": "evsnap-1",
            "canonical_graph_snapshot_id": "graphsnap-1",
            "wall_id": WALL,
        },
    )


def _completion(ids: tuple[str, ...], *, metadata: dict[str, object] | None = None) -> EvidenceAtom:
    meta = _prov(target=WALL, wall_id=WALL, opening_ids=list(ids))
    if metadata:
        meta.update(metadata)
    return EvidenceAtom(
        evidence_id="opening-set",
        document_id="doc",
        page_id=PAGE,
        viewport_id=VP,
        kind="opening_set_complete",
        method="caller_reconciliation",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata=meta,
    )


def _wall_entity(ids: tuple[str, ...]) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=WALL,
        candidate_type="wall",
        evidence_ids=ids,
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_prov(target=WALL),
    )


def _net(
    *,
    deductions: tuple[QuantityEvidence, ...] = (),
    completion: EvidenceAtom | None = None,
    unresolved: tuple[str, ...] = (),
    gross: QuantityEvidence | None = None,
    context: ProviderContext | None = None,
) -> QuantityEvidence:
    gross = gross or _gross_fixture()
    completion_ids = (completion.evidence_id,) if completion else ()
    deduction_eids = tuple(eid for d in deductions for eid in d.evidence_ids)
    wall_ids = tuple(dict.fromkeys(("wall-ev", *completion_ids, *deduction_eids)))
    return build_net_wall_area_quantity(
        wall_id=WALL,
        gross_wall_area=gross,
        opening_deductions=deductions,
        opening_set_complete_evidence=completion,
        context=context or _ctx(),
        document=_doc(wall_ids),
        viewport=_viewport(),
        wall_entity=_wall_entity(wall_ids),
        unresolved_opening_host_ids=unresolved,
    )


# --- Workstream A: opening/host completeness attacks ---


def test_a01_caller_omitted_opening_cannot_self_certify_truncated_universe() -> None:
    d1 = _deduction_fixture("OP-1")
    result = _net(deductions=(d1,), completion=_completion(("OP-1",)))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a02_omitted_competing_host_cannot_make_single_host_firm() -> None:
    result = _deduction(host=_host(walls=(WALL,)))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_host_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a03_two_plausible_host_walls_stay_blocked() -> None:
    result = _deduction(host=_host(status="ambiguous_host", walls=(WALL, "WALL-2")))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_host_not_uniquely_resolved" in result.blocking_reasons


def test_a04_viewport_boundary_opening_stays_blocked() -> None:
    result = _deduction(host=_host(reasons=("opening_crosses_viewport_boundary",)))
    assert "opening_crosses_viewport_boundary" in result.blocking_reasons


def test_a05_visible_opening_with_unresolved_dimensions_stays_blocked() -> None:
    result = _deduction(width=None, height=None, entity=_opening_entity(ids=("physical",)))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_width_missing" in result.blocking_reasons
    assert "opening_height_missing" in result.blocking_reasons


def test_a06_host_proven_but_opening_universe_unproven_blocks_net() -> None:
    result = _net(deductions=(_deduction_fixture(),), completion=None)
    assert "opening_set_completeness_not_evidenced" in result.blocking_reasons


def test_a07_dimensions_without_physical_identity_proof_stay_blocked() -> None:
    entity = _opening_entity(status=EvidenceResolutionStatus.CANDIDATE)
    result = _deduction(entity=entity)
    assert "opening_entity_not_corroborated" in result.blocking_reasons


def test_a08_schedule_row_without_physical_instance_proof_stays_blocked() -> None:
    width = _opening_ev("ow", "opening_width_schedule", 900.0)
    height = _opening_ev("oh", "opening_height_schedule", 2100.0)
    entity = _opening_entity(status=EvidenceResolutionStatus.CANDIDATE)
    result = _deduction(entity=entity, width=width, height=height)
    assert "opening_entity_not_corroborated" in result.blocking_reasons


def test_a09_physical_opening_without_schedule_or_direct_dimensions_is_not_zero() -> None:
    result = _deduction(width=None, height=None, entity=_opening_entity(ids=("physical",)))
    assert result.value is None
    assert "opening_width_missing" in result.blocking_reasons
    assert "opening_height_missing" in result.blocking_reasons


def test_a10_same_tag_reused_across_viewports_does_not_bind() -> None:
    width = _opening_ev("ow", "opening_width_schedule", 900.0, viewport_id="VP-2")
    result = _deduction(width=width)
    assert "opening_width_viewport_mismatch" in result.blocking_reasons


def test_a11_repeated_schedule_type_across_instances_cannot_reuse_dimension_atom() -> None:
    shared = _opening_ev("shared-w", "opening_width_schedule", 900.0)
    h1 = _opening_ev("h1", "opening_height_schedule", 2100.0, opening_id="OP-1")
    h2 = _opening_ev("h2", "opening_height_schedule", 2100.0, opening_id="OP-2")
    results = build_opening_deduction_quantities(
        hosts=(_host("OP-1"), _host("OP-2")),
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("shared-w", "h1", "h2")),
        viewport=_viewport(),
        opening_entities={
            "OP-1": _opening_entity("OP-1", ids=("shared-w", "h1")),
            "OP-2": _opening_entity("OP-2", ids=("shared-w", "h2")),
        },
        width_evidence={"OP-1": shared, "OP-2": shared},
        height_evidence={"OP-1": h1, "OP-2": h2},
    )
    assert all("opening_dimension_evidence_reused_across_identities" in r.blocking_reasons for r in results)


def test_a12_multiple_fragments_for_one_physical_opening_do_not_double_count() -> None:
    meta1 = _prov(target="OP-FRAG-1", physical_opening_id="PHYS-1", physical_identity_status="proven")
    meta2 = _prov(target="OP-FRAG-2", physical_opening_id="PHYS-1", physical_identity_status="proven")
    results = build_opening_deduction_quantities(
        hosts=(_host("OP-FRAG-1"), _host("OP-FRAG-2")),
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("w1", "h1", "w2", "h2")),
        viewport=_viewport(),
        opening_entities={
            "OP-FRAG-1": _opening_entity("OP-FRAG-1", ids=("w1", "h1"), metadata=meta1),
            "OP-FRAG-2": _opening_entity("OP-FRAG-2", ids=("w2", "h2"), metadata=meta2),
        },
        width_evidence={
            "OP-FRAG-1": _opening_ev("w1", "opening_width_dimension", 900, opening_id="OP-FRAG-1"),
            "OP-FRAG-2": _opening_ev("w2", "opening_width_dimension", 900, opening_id="OP-FRAG-2"),
        },
        height_evidence={
            "OP-FRAG-1": _opening_ev("h1", "opening_height_dimension", 2100, opening_id="OP-FRAG-1"),
            "OP-FRAG-2": _opening_ev("h2", "opening_height_dimension", 2100, opening_id="OP-FRAG-2"),
        },
    )
    assert all("duplicate_physical_opening_identity" in r.blocking_reasons for r in results)


def test_a13_duplicate_candidate_records_for_same_physical_void_block() -> None:
    results = build_opening_deduction_quantities(
        hosts=(_host(OPENING), _host(OPENING)),
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("ow", "oh")),
        viewport=_viewport(),
        opening_entities={OPENING: _opening_entity()},
        width_evidence={OPENING: _opening_ev("ow", "opening_width_dimension", 900)},
        height_evidence={OPENING: _opening_ev("oh", "opening_height_dimension", 2100)},
    )
    assert all("duplicate_opening_identity" in r.blocking_reasons for r in results)


@pytest.mark.parametrize(
    ("metadata", "reason"),
    [
        (_prov(target=OPENING, revision_id="R0"), "opening_width_revision_mismatch"),
        (_prov(target=OPENING, evidence_snapshot_id="evsnap-old"), "opening_width_evidence_snapshot_mismatch"),
        (_prov(target=OPENING, source_sha256=OTHER_SHA), "opening_width_source_sha_mismatch"),
        (_prov(target=OPENING, graph_snapshot_id="graph-old"), "opening_width_graph_snapshot_mismatch"),
    ],
)
def test_a14_to_a17_stale_opening_dimension_provenance_blocks(metadata: dict[str, object], reason: str) -> None:
    width = _opening_ev("ow", "opening_width_dimension", 900, metadata=metadata)
    result = _deduction(width=width)
    assert reason in result.blocking_reasons


@pytest.mark.parametrize(
    ("host_reason", "expected"),
    [
        ("nearest_wall_only", "opening_host_nearest_only_not_authoritative"),
        ("bbox_overlap_only", "opening_host_bbox_overlap_only_not_authoritative"),
        ("regional_clip_only", "opening_host_regional_clip_not_complete"),
    ],
)
def test_a18_to_a20_heuristic_or_cropped_host_nomination_never_proves_identity(host_reason: str, expected: str) -> None:
    result = _deduction(host=_host(reasons=(host_reason,)))
    assert expected in result.blocking_reasons


def test_a21_semantic_filter_disappearance_cannot_certify_no_opening() -> None:
    result = _net(deductions=(), completion=_completion((), metadata={"semantic_filter_applied": True}))
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a22_missing_dimensions_cannot_become_zero_deduction() -> None:
    result = _net(deductions=(), completion=_completion(()))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert result.value is None
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a23_conflicting_plan_and_schedule_dimensions_block() -> None:
    width = _opening_ev(
        "ow",
        "opening_width_dimension",
        900,
        metadata=_prov(target=OPENING, dimension_conflict=True),
    )
    result = _deduction(width=width)
    assert "opening_dimension_conflict" in result.blocking_reasons


def test_a24_phase_conflict_blocks_deduction() -> None:
    entity = _opening_entity(metadata=_prov(target=OPENING, physical_opening_id=OPENING, phase_conflict=True))
    result = _deduction(entity=entity)
    assert "opening_phase_conflict" in result.blocking_reasons


def test_a25_trade_specific_applicability_must_be_proven() -> None:
    entity = _opening_entity(
        metadata=_prov(
            target=OPENING,
            physical_opening_id=OPENING,
            physical_identity_status="proven",
            commercial_applicability="unknown",
        )
    )
    result = _deduction(entity=entity)
    assert "opening_commercial_applicability_unproven" in result.blocking_reasons


# --- Workstream B: wall-height freshness/provenance attacks ---


@pytest.mark.parametrize(
    ("metadata", "reason"),
    [
        (_prov(target=WALL, revision_id="R0", height_semantic_role="wall_height"), "height_revision_mismatch"),
        (_prov(target=WALL, source_sha256=OTHER_SHA, height_semantic_role="wall_height"), "height_source_sha256_mismatch"),
        (_prov(target=WALL, evidence_snapshot_id="evsnap-old", height_semantic_role="wall_height"), "height_evidence_snapshot_mismatch"),
        (_prov(target=WALL, graph_snapshot_id="graph-old", height_semantic_role="wall_height"), "height_graph_snapshot_mismatch"),
    ],
)
def test_b01_to_b04_stale_height_atom_never_remains_firm(metadata: dict[str, object], reason: str) -> None:
    qty = _height_qty(_height_ev(metadata=metadata))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert reason in qty.blocking_reasons


def test_b05_wrong_viewport_blocks_height() -> None:
    qty = _height_qty(_height_ev(viewport_id="VP-2"))
    assert "height_viewport_mismatch" in qty.blocking_reasons


def test_b06_wrong_page_blocks_height() -> None:
    qty = _height_qty(_height_ev(page_id="page-2"))
    assert "height_page_mismatch" in qty.blocking_reasons


def test_b07_wrong_target_wall_blocks_height() -> None:
    qty = _height_qty(_height_ev(metadata=_prov(target="WALL-2", height_semantic_role="wall_height")))
    assert "height_target_entity_mismatch" in qty.blocking_reasons


@pytest.mark.parametrize("kind", ["ceiling_height_dimension", "storey_height_dimension"])
def test_b08_b09_ceiling_or_floor_to_floor_dimension_is_not_wall_height(kind: str) -> None:
    qty = _height_qty(_height_ev(kind=kind, metadata=_prov(target=WALL, height_semantic_role="room_or_storey_height")))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert "unsupported_direct_height_semantics" in qty.blocking_reasons


def test_b10_room_ceiling_height_is_not_bounding_wall_height() -> None:
    qty = _height_qty(
        _height_ev(kind="ceiling_height_dimension", metadata=_prov(target=WALL, height_semantic_role="room_ceiling_height"))
    )
    assert "unsupported_direct_height_semantics" in qty.blocking_reasons


def test_b11_fresh_explicitly_wall_bound_roof_floor_pair_is_positive_control() -> None:
    lower = _height_ev(
        "lo",
        kind="floor_level_datum",
        value=10.0,
        metadata=_prov(target=WALL, height_semantic_role="wall_base"),
    )
    upper = _height_ev(
        "hi",
        kind="roof_level_datum",
        value=13.0,
        metadata=_prov(target=WALL, height_semantic_role="wall_top"),
    )
    qty = build_wall_height_quantity(
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("lo", "hi")),
        viewport=_viewport(),
        entity=_height_entity(("lo", "hi")),
        lower_datum_evidence=lower,
        upper_datum_evidence=upper,
    )
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.value == 3.0


def test_b12_irrelevant_stale_entity_owned_evidence_does_not_poison_fresh_height() -> None:
    fresh = _height_ev("fresh")
    entity = _height_entity(("fresh", "old-irrelevant"))
    qty = build_wall_height_quantity(
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("fresh", "old-irrelevant")),
        viewport=_viewport(),
        entity=entity,
        direct_height_evidence=fresh,
    )
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.value == 3.0


def test_b13_conflicting_fresh_height_entity_blocks() -> None:
    entity = _height_entity(
        ("h",),
        status=EvidenceResolutionStatus.CONFLICT,
        conflicts=("h-conflict",),
    )
    qty = _height_qty(_height_ev(), entity=entity)
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert "wall_height_entity_not_corroborated" in qty.blocking_reasons


def test_b14_stale_conflict_metadata_cannot_override_fresh_direct_height() -> None:
    fresh = _height_ev("fresh")
    entity = _height_entity(
        ("fresh",),
        metadata={**_prov(target=WALL), "stale_height_conflict_ignored": True},
    )
    qty = _height_qty(fresh, entity=entity)
    assert qty.status == AuthorityStatus.FIRM.value


def test_b15_removing_required_height_snapshot_binding_cannot_strengthen_authority() -> None:
    metadata = _prov(target=WALL, height_semantic_role="wall_height")
    metadata.pop("evidence_snapshot_id")
    qty = _height_qty(_height_ev(metadata=metadata))
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert "height_evidence_snapshot_missing" in qty.blocking_reasons


def test_b16_variable_height_wall_cannot_publish_arbitrary_scalar() -> None:
    entity = _height_entity(("h",), metadata={**_prov(target=WALL), "height_profile": "variable"})
    qty = _height_qty(_height_ev(), entity=entity)
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert "variable_height_requires_profile_authority" in qty.blocking_reasons


def _measurement_fixture(
    *,
    family: str,
    value: float | None,
    authority: str,
    status: str = AuthorityStatus.FIRM.value,
    abstained: bool = False,
    blockers: tuple[str, ...] = (),
    evidence_snapshot_id: str = "evsnap-1",
    graph_snapshot_id: str = "graphsnap-1",
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"q-{family}",
        family=family,
        semantic_key=f"{family}:{WALL}",
        value=value,
        unit="m",
        input_entity_ids=(WALL,),
        formula="fixture",
        formula_version="1",
        evidence_ids=(f"ev-{family}",),
        authority=authority,
        status=status,
        confidence=1.0,
        abstained=abstained,
        blocking_reasons=blockers,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "viewport_id": VP,
            "page_id": PAGE,
            "page_no": 1,
            "evidence_snapshot_id": evidence_snapshot_id,
            "canonical_graph_snapshot_id": graph_snapshot_id,
        },
    )


def test_b17_missing_height_blocks_area_without_downgrading_length() -> None:
    length = _measurement_fixture(
        family="wall_length",
        value=4.0,
        authority=MeasurementAuthorityType.PDF_SCALED.value,
    )
    height = _measurement_fixture(
        family="wall_height",
        value=None,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.BLOCKED.value,
        abstained=True,
        blockers=("no_height",),
    )
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=length,
        wall_height=height,
        context=_ctx(),
    )
    assert length.status == AuthorityStatus.FIRM.value
    assert not length.abstained
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_height_abstained" in gross.blocking_reasons


def test_b18_unresolved_opening_blocks_net_but_not_firm_gross() -> None:
    gross = _gross_fixture()
    result = _net(gross=gross, deductions=(), completion=None)
    assert gross.status == AuthorityStatus.FIRM.value
    assert not gross.abstained
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_set_completeness_not_evidenced" in result.blocking_reasons


def test_stale_matching_height_and_length_snapshots_cannot_replay_gross_firm() -> None:
    length = _measurement_fixture(
        family="wall_length",
        value=4.0,
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        evidence_snapshot_id="evsnap-old",
        graph_snapshot_id="graph-old",
    )
    height = _measurement_fixture(
        family="wall_height",
        value=3.0,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        evidence_snapshot_id="evsnap-old",
        graph_snapshot_id="graph-old",
    )
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=length,
        wall_height=height,
        context=_ctx(),
    )
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "dependency_evidence_snapshot_stale" in gross.blocking_reasons
    assert "dependency_graph_snapshot_stale" in gross.blocking_reasons
