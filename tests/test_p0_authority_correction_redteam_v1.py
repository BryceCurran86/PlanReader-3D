from __future__ import annotations

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
from pb_opening_deduction_readiness import build_opening_deduction_quantity
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_wall_height_authority import build_wall_height_quantity
from pb_wall_room_topology_contracts import OpeningHostCandidate

SHA = "e" * 64
WALL = "WALL-CORR"
OPENING = "OPENING-CORR"
VP = "VP-CORR"
PAGE = "page-corr"


def _ctx() -> ProviderContext:
    return ProviderContext(
        run_id="run-corr",
        workspace_id="ws",
        project_id="project",
        document_id="doc-corr",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=(VP,),
        evidence_snapshot_id="snap-current",
        canonical_graph_snapshot_id="graph-current",
        owned_page_numbers=(1,),
        viewport_page_ownership=((VP, 1),),
    )


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=VP,
        document_id="doc-corr",
        page_id=PAGE,
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _opening_meta(**extra: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "source_sha256": SHA,
        "revision_id": "R1",
        "evidence_snapshot_id": "snap-current",
        "canonical_graph_snapshot_id": "graph-current",
        "target_entity_id": OPENING,
        "physical_opening_id": OPENING,
        "physical_identity_status": "proven",
        "phase": "new",
        "commercial_applicability": "applicable",
    }
    metadata.update(extra)
    return metadata


def _opening_ev(eid: str, kind: str, value: float) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc-corr",
        page_id=PAGE,
        viewport_id=VP,
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit="mm",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_opening_meta(),
    )


def _opening_entity(**metadata: object) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=OPENING,
        candidate_type="opening",
        evidence_ids=("ow", "oh"),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_opening_meta(**metadata),
    )


def _opening_quantity(*, entity: EntityEvidence) -> QuantityEvidence:
    width = _opening_ev("ow", "opening_width_dimension", 900.0)
    height = _opening_ev("oh", "opening_height_dimension", 2100.0)
    return build_opening_deduction_quantity(
        host=OpeningHostCandidate(
            host_candidate_id=OPENING,
            wall_candidate_id=WALL,
            position_along_wall_m=None,
            gap_width_m=None,
            host_status="hosted",
            candidate_wall_ids_considered=(WALL,),
            confidence=1.0,
            reason_codes=(),
        ),
        wall_id=WALL,
        context=_ctx(),
        document=DocumentEvidence(
            document_id="doc-corr",
            source_sha256=SHA,
            page_count=1,
            page_ids=(PAGE,),
            evidence_ids=("ow", "oh"),
        ),
        viewport=_viewport(),
        opening_entity=entity,
        width_evidence=width,
        height_evidence=height,
    )


def _height_evidence(
    *,
    kind: str = "wall_height_dimension",
    method: str = "documented_dimension",
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id="height",
        document_id="doc-corr",
        page_id=PAGE,
        viewport_id=VP,
        kind=kind,
        method=method,
        normalized_value=3.0,
        unit="m",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "evidence_snapshot_id": "snap-current",
            "canonical_graph_snapshot_id": "graph-current",
            "target_entity_id": WALL,
            "height_semantic_role": "wall_height",
        },
    )


def _height_quantity(
    evidence: EvidenceAtom,
    *,
    entity_metadata: dict[str, object] | None = None,
) -> QuantityEvidence:
    return build_wall_height_quantity(
        wall_id=WALL,
        context=_ctx(),
        document=DocumentEvidence(
            document_id="doc-corr",
            source_sha256=SHA,
            page_count=1,
            page_ids=(PAGE,),
            evidence_ids=(evidence.evidence_id,),
        ),
        viewport=_viewport(),
        entity=EntityEvidence(
            candidate_entity_id=WALL,
            candidate_type="wall",
            evidence_ids=(evidence.evidence_id,),
            status=EvidenceResolutionStatus.CORROBORATED,
            confidence=1.0,
            metadata=entity_metadata or {},
        ),
        direct_height_evidence=evidence,
    )


def _length(**metadata: object) -> QuantityEvidence:
    provenance: dict[str, object] = {
        "source_sha256": SHA,
        "revision_id": "R1",
        "evidence_snapshot_id": "snap-current",
        "canonical_graph_snapshot_id": "graph-current",
        "viewport_id": VP,
        "page_no": 1,
    }
    provenance.update(metadata)
    return QuantityEvidence(
        quantity_id="length",
        family="wall_length",
        semantic_key=f"wall_length:{WALL}",
        value=4.0,
        unit="m",
        input_entity_ids=(WALL,),
        formula="authoritative_length",
        formula_version="test",
        evidence_ids=("length-evidence",),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        metadata=provenance,
    )


def _firm_height() -> QuantityEvidence:
    quantity = _height_quantity(_height_evidence())
    assert quantity.status == AuthorityStatus.FIRM.value
    return quantity


def test_physical_void_does_not_depend_on_commercial_applicability() -> None:
    result = _opening_quantity(
        entity=_opening_entity(commercial_applicability="unknown")
    )
    assert "opening_commercial_applicability_unproven" not in result.blocking_reasons
    assert "opening_host_universe_completeness_not_authenticated" in result.blocking_reasons


def test_fabricated_physical_identity_metadata_cannot_establish_identity() -> None:
    result = _opening_quantity(entity=_opening_entity())
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_physical_identity_unproven" in result.blocking_reasons


def test_fabricated_height_semantic_role_cannot_mint_wall_height() -> None:
    result = _height_quantity(
        _height_evidence(kind="explicit_wall_height", method="caller_supplied")
    )
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "unsupported_direct_height_semantics" in result.blocking_reasons


def test_fabricated_scalar_representative_flag_cannot_mint_sloped_height() -> None:
    result = _height_quantity(
        _height_evidence(),
        entity_metadata={
            "height_profile": "sloped",
            "scalar_height_representative_proven": True,
        },
    )
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "variable_height_requires_profile_authority" in result.blocking_reasons


def test_missing_length_evidence_snapshot_preserves_length_but_blocks_gross() -> None:
    length = _length()
    metadata = dict(length.metadata)
    metadata.pop("evidence_snapshot_id")
    length = QuantityEvidence(**{**length.to_dict(), "metadata": metadata})
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=length,
        wall_height=_firm_height(),
        context=_ctx(),
    )
    assert length.status == AuthorityStatus.FIRM.value
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_length_evidence_snapshot_missing" in gross.blocking_reasons


def test_missing_length_graph_snapshot_preserves_length_but_blocks_gross() -> None:
    length = _length()
    metadata = dict(length.metadata)
    metadata.pop("canonical_graph_snapshot_id")
    length = QuantityEvidence(**{**length.to_dict(), "metadata": metadata})
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=length,
        wall_height=_firm_height(),
        context=_ctx(),
    )
    assert length.status == AuthorityStatus.FIRM.value
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_length_graph_snapshot_missing" in gross.blocking_reasons


def test_stale_length_evidence_snapshot_blocks_gross() -> None:
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=_length(evidence_snapshot_id="snap-old"),
        wall_height=_firm_height(),
        context=_ctx(),
    )
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_length_evidence_snapshot_stale" in gross.blocking_reasons


def test_stale_length_graph_snapshot_blocks_gross() -> None:
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=_length(canonical_graph_snapshot_id="graph-old"),
        wall_height=_firm_height(),
        context=_ctx(),
    )
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_length_graph_snapshot_stale" in gross.blocking_reasons
