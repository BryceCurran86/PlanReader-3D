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
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_wall_height_authority import WallDatumRelationshipProof, build_wall_height_quantity
from pb_wall_net_area_quantity import build_net_wall_area_quantity

SHA = "c" * 64
WALL = "WALL-H1"
SEGMENT = "WALL-H1:segment:a"
VP = "VP-H1"
PAGE = "page-h1"


def _ctx(**overrides: object) -> ProviderContext:
    values: dict[str, object] = {
        "run_id": "run-height",
        "workspace_id": "ws",
        "project_id": "project",
        "document_id": "doc-height",
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
        document_id="doc-height",
        page_id=page_id,
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _meta(*, target: str = WALL, role: str = "wall_height", **extra: object) -> dict[str, object]:
    metadata: dict[str, object] = {
        "source_sha256": SHA,
        "revision_id": "R1",
        "evidence_snapshot_id": "evsnap-1",
        "canonical_graph_snapshot_id": "graphsnap-1",
        "target_entity_id": target,
        "height_semantic_role": role,
    }
    metadata.update(extra)
    return metadata


def _ev(
    eid: str = "h",
    *,
    kind: str = "wall_height_dimension",
    value: float = 3.0,
    unit: str = "m",
    viewport_id: str = VP,
    page_id: str = PAGE,
    role: str = "wall_height",
    metadata: dict[str, object] | None = None,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc-height",
        page_id=page_id,
        viewport_id=viewport_id,
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit=unit,
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata=metadata if metadata is not None else _meta(role=role),
    )


def _doc(ids: tuple[str, ...], *, source_sha: str = SHA) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc-height",
        source_sha256=source_sha,
        page_count=1,
        page_ids=(PAGE,),
        evidence_ids=ids,
    )


def _entity(
    ids: tuple[str, ...],
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    conflicts: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=WALL,
        candidate_type="wall",
        evidence_ids=ids,
        status=status,
        confidence=1.0,
        conflict_evidence_ids=conflicts,
        metadata=metadata or {},
    )


def _height(
    evidence: EvidenceAtom,
    *,
    context: ProviderContext | None = None,
    entity: EntityEvidence | None = None,
    document: DocumentEvidence | None = None,
    viewport: ViewportEvidence | None = None,
) -> QuantityEvidence:
    return build_wall_height_quantity(
        wall_id=WALL,
        context=context or _ctx(),
        document=document or _doc((evidence.evidence_id,)),
        viewport=viewport or _viewport(),
        entity=entity or _entity((evidence.evidence_id,)),
        direct_height_evidence=evidence,
    )


def _length() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-length",
        family="wall_length",
        semantic_key=f"wall_length:{WALL}",
        value=4.0,
        unit="m",
        input_entity_ids=(WALL,),
        formula="scaled_centerline",
        formula_version="test",
        evidence_ids=("len",),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap-1",
            "canonical_graph_snapshot_id": "graphsnap-1",
            "viewport_id": VP,
            "page_no": 1,
        },
    )


def _datum_pair() -> tuple[EvidenceAtom, EvidenceAtom]:
    lower = _ev(
        "floor",
        kind="floor_level_datum",
        value=12.0,
        role="wall_base",
    )
    upper = _ev(
        "top",
        kind="wall_top_level_datum",
        value=15.2,
        role="wall_top",
    )
    return lower, upper


def _relation(eid: str, datum_id: str, role: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc-height",
        page_id=PAGE,
        viewport_id=VP,
        kind="wall_datum_segment_relationship",
        method="canonical_graph_relation",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap-1",
            "canonical_graph_snapshot_id": "graphsnap-1",
            "target_entity_id": WALL,
            "target_wall_segment_id": SEGMENT,
            "datum_evidence_id": datum_id,
            "datum_role": role,
        },
    )


def _proof(proof_id: str, datum_id: str, role: str, relation_id: str) -> WallDatumRelationshipProof:
    return WallDatumRelationshipProof(
        proof_id=proof_id,
        wall_id=WALL,
        wall_segment_id=SEGMENT,
        datum_evidence_id=datum_id,
        datum_role=role,
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="evsnap-1",
        canonical_graph_snapshot_id="graphsnap-1",
        datum_page_id=PAGE,
        datum_viewport_id=VP,
        relationship_evidence_ids=(relation_id,),
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def _datum_height(
    *,
    lower: EvidenceAtom | None = None,
    upper: EvidenceAtom | None = None,
    entity: EntityEvidence | None = None,
) -> QuantityEvidence:
    low, high = _datum_pair()
    low = lower or low
    high = upper or high
    lower_rel = _relation("rel-floor", low.evidence_id, "wall_base")
    upper_rel = _relation("rel-top", high.evidence_id, "wall_top")
    all_ids = (low.evidence_id, high.evidence_id, lower_rel.evidence_id, upper_rel.evidence_id)
    return build_wall_height_quantity(
        wall_id=WALL,
        wall_segment_id=SEGMENT,
        context=_ctx(),
        document=_doc(all_ids),
        viewport=_viewport(),
        entity=entity or _entity(all_ids),
        lower_datum_evidence=low,
        upper_datum_evidence=high,
        datum_relationship_proofs=(
            _proof("proof-floor", low.evidence_id, "wall_base", lower_rel.evidence_id),
            _proof("proof-top", high.evidence_id, "wall_top", upper_rel.evidence_id),
        ),
        relationship_evidence={lower_rel.evidence_id: lower_rel, upper_rel.evidence_id: upper_rel},
    )


def test_h01_correct_value_stale_revision_blocks() -> None:
    ev = _ev(metadata=_meta(revision_id="R0"))
    result = _height(ev)
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "height_revision_mismatch" in result.blocking_reasons


def test_h02_correct_value_stale_source_sha_blocks() -> None:
    ev = _ev(metadata=_meta(source_sha256="d" * 64))
    result = _height(ev)
    assert "height_source_sha256_mismatch" in result.blocking_reasons


def test_h03_correct_value_stale_evidence_snapshot_blocks() -> None:
    ev = _ev(metadata=_meta(evidence_snapshot_id="evsnap-old"))
    result = _height(ev)
    assert "height_evidence_snapshot_mismatch" in result.blocking_reasons


def test_h04_correct_value_stale_graph_snapshot_blocks() -> None:
    ev = _ev(metadata=_meta(canonical_graph_snapshot_id="graph-old"))
    result = _height(ev)
    assert "height_graph_snapshot_mismatch" in result.blocking_reasons


def test_h05_correct_value_wrong_viewport_blocks() -> None:
    ev = _ev(viewport_id="VP-OTHER")
    result = _height(ev)
    assert "height_viewport_mismatch" in result.blocking_reasons


def test_h06_correct_value_wrong_page_blocks() -> None:
    ev = _ev(page_id="page-other")
    result = _height(ev)
    assert "height_page_mismatch" in result.blocking_reasons


def test_h07_correct_value_wrong_target_wall_blocks() -> None:
    ev = _ev(metadata=_meta(target="WALL-OTHER"))
    result = _height(ev)
    assert "height_target_entity_mismatch" in result.blocking_reasons


def test_h08_room_ceiling_height_cannot_substitute_for_wall_height() -> None:
    ev = _ev(kind="ceiling_height_dimension", value=2.7, role="room_ceiling")
    result = _height(ev)
    assert "unsupported_direct_height_semantics" in result.blocking_reasons


def test_h09_floor_to_floor_storey_height_cannot_substitute_automatically() -> None:
    ev = _ev(kind="storey_height_dimension", value=3.2, role="storey_height")
    result = _height(ev)
    assert "unsupported_direct_height_semantics" in result.blocking_reasons


def test_h10_room_height_cannot_substitute_automatically() -> None:
    ev = _ev(kind="explicit_wall_height", value=2.8, role="room_height")
    result = _height(ev)
    assert "unsupported_direct_height_semantics" in result.blocking_reasons


def test_h11_fresh_wall_base_and_wall_top_positive_control() -> None:
    result = _datum_height()
    assert result.status == AuthorityStatus.FIRM.value
    assert result.abstained is False
    assert result.value == 3.2
    assert result.formula == "wall_top_datum - wall_base_datum"
    assert result.metadata["wall_segment_id"] == SEGMENT


def test_h12_irrelevant_stale_evidence_does_not_poison_fresh_selected_height() -> None:
    fresh = _ev("fresh")
    entity = _entity(("fresh", "old"))
    result = _height(fresh, entity=entity, document=_doc(("fresh", "old")))
    assert result.status == AuthorityStatus.FIRM.value
    assert result.value == 3.0


def test_h13_conflicting_fresh_height_entity_blocks() -> None:
    fresh = _ev("h1", value=3.0)
    entity = _entity(
        ("h1", "h2"),
        status=EvidenceResolutionStatus.CONFLICT,
        conflicts=("h2",),
    )
    result = _height(fresh, entity=entity, document=_doc(("h1", "h2")))
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "wall_height_entity_conflict" in result.blocking_reasons


def test_h14_stale_conflicting_atom_cannot_override_fresh_height() -> None:
    fresh = _ev("fresh", value=3.0)
    stale = _ev("stale", value=2.8, metadata=_meta(revision_id="R0"))
    selected_fresh = _height(fresh, entity=_entity(("fresh", "stale")), document=_doc(("fresh", "stale")))
    selected_stale = _height(stale, entity=_entity(("fresh", "stale")), document=_doc(("fresh", "stale")))
    assert selected_fresh.status == AuthorityStatus.FIRM.value
    assert selected_fresh.value == 3.0
    assert selected_stale.status == AuthorityStatus.BLOCKED.value
    assert "height_revision_mismatch" in selected_stale.blocking_reasons


def test_h15_removing_required_datum_support_cannot_strengthen_authority() -> None:
    lower, upper = _datum_pair()
    supported = _datum_height(lower=lower, upper=upper)
    missing_upper = build_wall_height_quantity(
        wall_id=WALL,
        context=_ctx(),
        document=_doc((lower.evidence_id,)),
        viewport=_viewport(),
        entity=_entity((lower.evidence_id,)),
        lower_datum_evidence=lower,
        upper_datum_evidence=None,
    )
    assert supported.status == AuthorityStatus.FIRM.value
    assert missing_upper.status == AuthorityStatus.BLOCKED.value
    assert "no_authoritative_wall_height_evidence" in missing_upper.blocking_reasons


def test_h16_variable_or_sloped_wall_scalar_blocks_without_representativeness_proof() -> None:
    ev = _ev(value=3.0)
    entity = _entity(
        ("h",),
        metadata={"height_profile": "sloped", "scalar_height_representative_proven": False},
    )
    result = _height(ev, entity=entity)
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "variable_height_requires_profile_authority" in result.blocking_reasons


def test_h17_missing_height_preserves_firm_length_but_blocks_gross_area() -> None:
    length = _length()
    missing_height = build_wall_height_quantity(
        wall_id=WALL,
        context=_ctx(),
        document=_doc(("wall-exists",)),
        viewport=_viewport(),
        entity=_entity(("wall-exists",)),
    )
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=length,
        wall_height=missing_height,
        context=_ctx(),
    )
    assert length.status == AuthorityStatus.FIRM.value
    assert length.value == 4.0
    assert missing_height.status == AuthorityStatus.BLOCKED.value
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_height_abstained" in gross.blocking_reasons


def test_h18_unresolved_opening_preserves_firm_gross_but_blocks_net() -> None:
    height = _height(_ev("h"))
    gross = build_gross_wall_area_quantity(
        wall_id=WALL,
        wall_length=_length(),
        wall_height=height,
        context=_ctx(),
    )
    wall_entity = _entity(("len", "h"))
    document = _doc(("len", "h"))
    net = build_net_wall_area_quantity(
        wall_id=WALL,
        gross_wall_area=gross,
        opening_deductions=(),
        opening_set_complete_evidence=None,
        context=_ctx(),
        document=document,
        viewport=_viewport(),
        wall_entity=wall_entity,
        unresolved_opening_host_ids=("opening-candidate-1",),
    )
    assert gross.status == AuthorityStatus.FIRM.value
    assert gross.value == 12.0
    assert net.status == AuthorityStatus.BLOCKED.value
    assert "unresolved_opening_hosts_present" in net.blocking_reasons
    assert "opening_set_completeness_not_evidenced" in net.blocking_reasons
