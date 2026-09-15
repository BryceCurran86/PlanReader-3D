from __future__ import annotations

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
from pb_wall_net_area_quantity import build_net_wall_area_quantity
from pb_wall_room_topology_contracts import OpeningHostCandidate

SHA = "a" * 64
WALL = "WALL-1"
VP = "VP-1"
PAGE = "page-1"


def _ctx() -> ProviderContext:
    return ProviderContext(
        run_id="run", workspace_id="ws", project_id="p", document_id="doc",
        source_sha256=SHA, revision_id="R1", current_revision_id="R1",
        selected_pages=(0,), owned_viewport_ids=(VP,), evidence_snapshot_id="snap",
        canonical_graph_snapshot_id="graph", owned_page_numbers=(1,),
        viewport_page_ownership=((VP, 1),),
    )


def _vp() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=VP, document_id="doc", page_id=PAGE, bbox=(0, 0, 100, 100),
        view_type="plan", status=ViewportResolutionStatus.RESOLVED, confidence=1.0,
    )


def _meta(opening_id: str, **extra: object) -> dict[str, object]:
    out: dict[str, object] = {
        "source_sha256": SHA,
        "revision_id": "R1",
        "evidence_snapshot_id": "snap",
        "canonical_graph_snapshot_id": "graph",
        "target_entity_id": opening_id,
        "physical_opening_id": opening_id,
        "physical_identity_status": "proven",
        "phase": "new",
        "commercial_applicability": "applicable",
    }
    out.update(extra)
    return out


def _ev(eid: str, kind: str, value: float, *, opening_id: str = "OP-1", **meta: object) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid, document_id="doc", page_id=PAGE, viewport_id=VP,
        kind=kind, method="documented_dimension", normalized_value=value, unit="mm",
        status=EvidenceResolutionStatus.CORROBORATED, confidence=1.0,
        metadata=_meta(opening_id, **meta),
    )


def _entity(opening_id: str = "OP-1", ids=("w", "h"), **meta: object) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=opening_id, candidate_type="opening", evidence_ids=tuple(ids),
        status=EvidenceResolutionStatus.CORROBORATED, confidence=1.0,
        metadata=_meta(opening_id, **meta),
    )


def _host(opening_id: str = "OP-1", *, status="hosted", walls=(WALL,), reasons=()) -> OpeningHostCandidate:
    if status == "ambiguous_host" and not reasons:
        reasons = ("multiple_plausible_wall_candidates",)
    return OpeningHostCandidate(
        host_candidate_id=opening_id, wall_candidate_id=WALL,
        position_along_wall_m=None, gap_width_m=None, host_status=status,
        candidate_wall_ids_considered=tuple(walls), confidence=1.0,
        reason_codes=tuple(reasons),
    )


def _deduct(
    *, host=None, entity=None, width="default", height="default",
) -> QuantityEvidence:
    host = host or _host()
    if width == "default":
        width = _ev("w", "opening_width_dimension", 900, opening_id=host.host_candidate_id)
    if height == "default":
        height = _ev("h", "opening_height_dimension", 2100, opening_id=host.host_candidate_id)
    ids = tuple(ev.evidence_id for ev in (width, height) if isinstance(ev, EvidenceAtom))
    entity = entity or _entity(host.host_candidate_id, ids=ids)
    return build_opening_deduction_quantity(
        host=host, wall_id=WALL, context=_ctx(), document=DocumentEvidence(
            document_id="doc", source_sha256=SHA, page_count=1, page_ids=(PAGE,), evidence_ids=ids,
        ), viewport=_vp(), opening_entity=entity,
        width_evidence=width if isinstance(width, EvidenceAtom) else None,
        height_evidence=height if isinstance(height, EvidenceAtom) else None,
    )


def _gross() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="gross", family="wall_gross_area", semantic_key=f"wall_gross_area:{WALL}",
        value=12.0, unit="m2", input_entity_ids=(WALL,), formula="l*h", formula_version="1",
        evidence_ids=("wall",), authority="derived_from_firm_measurements",
        status=AuthorityStatus.FIRM.value, confidence=1.0,
        metadata={"source_sha256": SHA, "revision_id": "R1", "viewport_id": VP,
                  "page_id": PAGE, "evidence_snapshot_id": "snap",
                  "canonical_graph_snapshot_id": "graph"},
    )


def _completion(ids: tuple[str, ...], **meta: object) -> EvidenceAtom:
    data = {"wall_id": WALL, "target_entity_id": WALL, "opening_ids": list(ids),
            "source_sha256": SHA, "revision_id": "R1", "evidence_snapshot_id": "snap",
            "canonical_graph_snapshot_id": "graph"}
    data.update(meta)
    return EvidenceAtom(
        evidence_id="complete", document_id="doc", page_id=PAGE, viewport_id=VP,
        kind="opening_set_complete", method="caller_reconciliation",
        status=EvidenceResolutionStatus.CORROBORATED, confidence=1.0, metadata=data,
    )


def _net(*, deductions=(), completion=None, unresolved=()) -> QuantityEvidence:
    eids = ["wall"]
    if completion is not None:
        eids.append(completion.evidence_id)
    for d in deductions:
        eids.extend(d.evidence_ids)
    eids = list(dict.fromkeys(eids))
    wall = EntityEvidence(
        candidate_entity_id=WALL, candidate_type="wall", evidence_ids=tuple(eids),
        status=EvidenceResolutionStatus.CORROBORATED, confidence=1.0,
    )
    doc = DocumentEvidence(
        document_id="doc", source_sha256=SHA, page_count=1, page_ids=(PAGE,),
        evidence_ids=tuple(eids),
    )
    return build_net_wall_area_quantity(
        wall_id=WALL, gross_wall_area=_gross(), opening_deductions=tuple(deductions),
        opening_set_complete_evidence=completion, context=_ctx(), document=doc,
        viewport=_vp(), wall_entity=wall, unresolved_opening_host_ids=tuple(unresolved),
    )


def _firm_deduction(opening_id="OP-1") -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"d-{opening_id}", family="opening_deduction_area",
        semantic_key=f"opening_deduction:{opening_id}", value=1.89, unit="m2",
        input_entity_ids=(opening_id, WALL), formula="w*h", formula_version="1",
        evidence_ids=(f"{opening_id}-w", f"{opening_id}-h"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value, confidence=1.0,
        metadata={"source_sha256": SHA, "revision_id": "R1", "viewport_id": VP,
                  "page_id": PAGE, "evidence_snapshot_id": "snap",
                  "canonical_graph_snapshot_id": "graph", "wall_id": WALL},
    )


def test_a01_omitted_opening_from_caller_list_fails_closed() -> None:
    result = _net(deductions=(_firm_deduction(),), completion=_completion(("OP-1",)))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a02_omitted_competing_host_fails_closed() -> None:
    result = _deduct(host=_host(walls=(WALL,)))
    assert "opening_host_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a03_two_plausible_hosts_remain_ambiguous() -> None:
    result = _deduct(host=_host(status="ambiguous_host", walls=(WALL, "WALL-2")))
    assert "opening_host_not_uniquely_resolved" in result.blocking_reasons
    assert "opening_host_candidate_cardinality_not_one" in result.blocking_reasons


def test_a04_viewport_boundary_opening_blocks() -> None:
    result = _deduct(host=_host(reasons=("opening_crosses_viewport_boundary",)))
    assert "opening_crosses_viewport_boundary" in result.blocking_reasons


def test_a05_visible_opening_with_unresolved_dimensions_blocks() -> None:
    result = _deduct(width=None, height=None, entity=_entity(ids=("physical",)))
    assert "opening_width_missing" in result.blocking_reasons
    assert "opening_height_missing" in result.blocking_reasons


def test_a06_host_proven_opening_universe_unproven_blocks_net() -> None:
    result = _net(deductions=(_firm_deduction(),), completion=None)
    assert "opening_set_completeness_not_evidenced" in result.blocking_reasons


def test_a07_dimensions_without_physical_identity_block() -> None:
    entity = _entity(physical_identity_status="unproven")
    result = _deduct(entity=entity)
    assert "opening_physical_identity_unproven" in result.blocking_reasons


def test_a08_schedule_row_without_physical_instance_proof_blocks() -> None:
    entity = _entity(physical_identity_status="unproven")
    result = _deduct(
        entity=entity,
        width=_ev("w", "opening_width_schedule", 900),
        height=_ev("h", "opening_height_schedule", 2100),
    )
    assert "opening_physical_identity_unproven" in result.blocking_reasons


def test_a09_physical_opening_without_schedule_dimensions_is_not_zero() -> None:
    result = _deduct(width=None, height=None, entity=_entity(ids=("physical",)))
    assert result.value is None
    assert "opening_width_missing" in result.blocking_reasons
    assert "opening_height_missing" in result.blocking_reasons


def test_a10_same_tag_reused_across_viewports_does_not_bind() -> None:
    width = _ev("w", "opening_width_schedule", 900)
    width = EvidenceAtom(
        evidence_id=width.evidence_id, document_id=width.document_id, page_id=width.page_id,
        viewport_id="VP-2", kind=width.kind, method=width.method,
        normalized_value=width.normalized_value, unit=width.unit, status=width.status,
        confidence=width.confidence, metadata=width.metadata,
    )
    result = _deduct(width=width)
    assert "opening_width_viewport_mismatch" in result.blocking_reasons


def test_a11_repeated_type_cannot_reuse_one_dimension_atom_across_instances() -> None:
    shared = _ev("shared", "opening_width_schedule", 900, opening_id="OP-1")
    results = build_opening_deduction_quantities(
        hosts=(_host("OP-1"), _host("OP-2")), wall_id=WALL, context=_ctx(),
        document=DocumentEvidence(document_id="doc", source_sha256=SHA, page_count=1,
                                  page_ids=(PAGE,), evidence_ids=("shared", "h1", "h2")),
        viewport=_vp(),
        opening_entities={"OP-1": _entity("OP-1", ids=("shared", "h1")),
                          "OP-2": _entity("OP-2", ids=("shared", "h2"))},
        width_evidence={"OP-1": shared, "OP-2": shared},
        height_evidence={"OP-1": _ev("h1", "opening_height_schedule", 2100, opening_id="OP-1"),
                         "OP-2": _ev("h2", "opening_height_schedule", 2100, opening_id="OP-2")},
    )
    assert all("opening_dimension_evidence_reused_across_identities" in r.blocking_reasons for r in results)


def test_a12_multiple_fragments_for_one_physical_opening_block_double_count() -> None:
    e1 = _entity("F1", ids=("w1", "h1"), physical_opening_id="PHYS-1")
    e2 = _entity("F2", ids=("w2", "h2"), physical_opening_id="PHYS-1")
    results = build_opening_deduction_quantities(
        hosts=(_host("F1"), _host("F2")), wall_id=WALL, context=_ctx(),
        document=DocumentEvidence(document_id="doc", source_sha256=SHA, page_count=1,
                                  page_ids=(PAGE,), evidence_ids=("w1", "h1", "w2", "h2")),
        viewport=_vp(), opening_entities={"F1": e1, "F2": e2},
        width_evidence={"F1": _ev("w1", "opening_width_dimension", 900, opening_id="F1"),
                        "F2": _ev("w2", "opening_width_dimension", 900, opening_id="F2")},
        height_evidence={"F1": _ev("h1", "opening_height_dimension", 2100, opening_id="F1"),
                         "F2": _ev("h2", "opening_height_dimension", 2100, opening_id="F2")},
    )
    assert all("duplicate_physical_opening_identity" in r.blocking_reasons for r in results)


def test_a13_duplicate_candidates_same_void_block() -> None:
    results = build_opening_deduction_quantities(
        hosts=(_host("OP-1"), _host("OP-1")), wall_id=WALL, context=_ctx(),
        document=DocumentEvidence(document_id="doc", source_sha256=SHA, page_count=1,
                                  page_ids=(PAGE,), evidence_ids=("w", "h")), viewport=_vp(),
        opening_entities={"OP-1": _entity("OP-1")},
        width_evidence={"OP-1": _ev("w", "opening_width_dimension", 900)},
        height_evidence={"OP-1": _ev("h", "opening_height_dimension", 2100)},
    )
    assert all("duplicate_opening_identity" in r.blocking_reasons for r in results)


@pytest.mark.parametrize(
    ("meta", "reason"),
    [
        ({"revision_id": "R0"}, "opening_width_revision_mismatch"),
        ({"evidence_snapshot_id": "old"}, "opening_width_evidence_snapshot_mismatch"),
        ({"source_sha256": "b" * 64}, "opening_width_source_sha_mismatch"),
        ({"canonical_graph_snapshot_id": "old"}, "opening_width_graph_snapshot_mismatch"),
    ],
)
def test_a14_to_a17_stale_opening_evidence_blocks(meta: dict[str, object], reason: str) -> None:
    result = _deduct(width=_ev("w", "opening_width_dimension", 900, **meta))
    assert reason in result.blocking_reasons


@pytest.mark.parametrize(
    ("nomination", "reason"),
    [
        ("nearest_wall_only", "opening_host_nearest_only_not_authoritative"),
        ("bbox_overlap_only", "opening_host_bbox_overlap_only_not_authoritative"),
        ("regional_clip_only", "opening_host_regional_clip_not_complete"),
    ],
)
def test_a18_to_a20_nomination_is_not_host_authority(nomination: str, reason: str) -> None:
    result = _deduct(host=_host(reasons=(nomination,)))
    assert reason in result.blocking_reasons


def test_a21_semantic_filter_disappearance_cannot_certify_empty_universe() -> None:
    result = _net(completion=_completion((), semantic_filter_applied=True))
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_a22_missing_dimensions_never_become_zero_deduction() -> None:
    result = _deduct(width=None, height=None, entity=_entity(ids=("physical",)))
    assert result.abstained and result.value is None
    assert {"opening_width_missing", "opening_height_missing"}.issubset(result.blocking_reasons)


def test_a23_conflicting_plan_schedule_dimensions_block() -> None:
    result = _deduct(width=_ev("w", "opening_width_dimension", 900, dimension_conflict=True))
    assert "opening_dimension_conflict" in result.blocking_reasons


def test_a24_phase_conflict_blocks() -> None:
    result = _deduct(entity=_entity(phase_conflict=True))
    assert "opening_phase_conflict" in result.blocking_reasons


def test_a25_trade_specific_applicability_must_be_proven() -> None:
    result = _deduct(entity=_entity(commercial_applicability="unknown"))
    assert "opening_commercial_applicability_unproven" in result.blocking_reasons
