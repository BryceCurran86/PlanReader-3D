from __future__ import annotations

from dataclasses import replace

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
from pb_wall_height_authority import (
    AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE,
    WallDatumRelationshipProof,
    build_wall_height_quantity,
)

SHA = "e" * 64
SEGMENT = "w1:segment:a"


def _context() -> ProviderContext:
    return ProviderContext(
        run_id="run",
        workspace_id="ws",
        project_id="project",
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0, 1),
        owned_viewport_ids=("vp-plan", "vp-section"),
        evidence_snapshot_id="evsnap",
        canonical_graph_snapshot_id="graphsnap",
        measurement_authority_snapshot_id="measuresnap",
        owned_page_numbers=(1, 2),
        viewport_page_ownership=(("vp-plan", 1), ("vp-section", 2)),
    )


def _document(ids: tuple[str, ...]) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256=SHA,
        page_count=2,
        page_ids=("page-plan", "page-section"),
        evidence_ids=ids,
    )


def _viewport(viewport_id: str = "vp-plan") -> ViewportEvidence:
    page_id = "page-plan" if viewport_id == "vp-plan" else "page-section"
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
        page_id=page_id,
        bbox=(0, 0, 100, 100),
        view_type="floor_plan" if viewport_id == "vp-plan" else "section",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _entity(ids: tuple[str, ...], *, wall_id: str = "w1", metadata=None) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=wall_id,
        candidate_type="wall",
        evidence_ids=ids,
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=metadata or {},
    )


def _datum(
    evidence_id: str,
    kind: str,
    value: float,
    *,
    wall_id: str = "w1",
    viewport_id: str = "vp-plan",
    revision_id: str = "R1",
    evidence_snapshot_id: str = "evsnap",
    graph_snapshot_id: str = "graphsnap",
    metadata=None,
) -> EvidenceAtom:
    page_id = "page-plan" if viewport_id == "vp-plan" else "page-section"
    meta = {
        "source_sha256": SHA,
        "revision_id": revision_id,
        "evidence_snapshot_id": evidence_snapshot_id,
        "canonical_graph_snapshot_id": graph_snapshot_id,
        "target_entity_id": wall_id,
    }
    if metadata:
        meta.update(metadata)
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id=page_id,
        viewport_id=viewport_id,
        kind=kind,
        method="vector_text",
        normalized_value=value,
        unit="m",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata=meta,
    )


def _relationship_support(
    evidence_id: str,
    *,
    wall_id: str = "w1",
    datum_evidence_id: str,
    role: str,
    segment_id: str = SEGMENT,
    viewport_id: str = "vp-plan",
) -> EvidenceAtom:
    page_id = "page-plan" if viewport_id == "vp-plan" else "page-section"
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id=page_id,
        viewport_id=viewport_id,
        kind="wall_datum_segment_relationship",
        method="canonical_graph_relation",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap",
            "canonical_graph_snapshot_id": "graphsnap",
            "target_entity_id": wall_id,
            "target_wall_segment_id": segment_id,
            "datum_evidence_id": datum_evidence_id,
            "datum_role": role,
        },
    )


def _proof(
    proof_id: str,
    *,
    datum_evidence_id: str,
    role: str,
    support_evidence_id: str,
    wall_id: str = "w1",
    segment_id: str = SEGMENT,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    datum_viewport_id: str = "vp-plan",
    cross_view_evidence_ids: tuple[str, ...] = (),
) -> WallDatumRelationshipProof:
    datum_page_id = "page-plan" if datum_viewport_id == "vp-plan" else "page-section"
    return WallDatumRelationshipProof(
        proof_id=proof_id,
        wall_id=wall_id,
        wall_segment_id=segment_id,
        datum_evidence_id=datum_evidence_id,
        datum_role=role,
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="evsnap",
        canonical_graph_snapshot_id="graphsnap",
        datum_page_id=datum_page_id,
        datum_viewport_id=datum_viewport_id,
        relationship_evidence_ids=(support_evidence_id,),
        cross_view_evidence_ids=cross_view_evidence_ids,
        status=status,
    )


def _resolve(
    *,
    lower: EvidenceAtom,
    upper: EvidenceAtom,
    proofs: tuple[WallDatumRelationshipProof, ...],
    support: tuple[EvidenceAtom, ...],
    entity_ids: tuple[str, ...] | None = None,
    entity_metadata=None,
):
    all_ids = entity_ids or tuple(
        dict.fromkeys((lower.evidence_id, upper.evidence_id, *(ev.evidence_id for ev in support)))
    )
    return build_wall_height_quantity(
        wall_id="w1",
        wall_segment_id=SEGMENT,
        context=_context(),
        document=_document(all_ids),
        viewport=_viewport(),
        entity=_entity(all_ids, metadata=entity_metadata),
        lower_datum_evidence=lower,
        upper_datum_evidence=upper,
        datum_relationship_proofs=proofs,
        relationship_evidence={ev.evidence_id: ev for ev in support},
    )


def _apparently_complete_claims(base: EvidenceAtom, top: EvidenceAtom):
    rb = _relationship_support("rel-base", datum_evidence_id=base.evidence_id, role="wall_base")
    rt = _relationship_support("rel-top", datum_evidence_id=top.evidence_id, role="wall_top")
    proofs = (
        _proof("p-base", datum_evidence_id=base.evidence_id, role="wall_base", support_evidence_id=rb.evidence_id),
        _proof("p-top", datum_evidence_id=top.evidence_id, role="wall_top", support_evidence_id=rt.evidence_id),
    )
    return proofs, (rb, rt)


def test_attack_1_two_plausible_base_slabs_block_scalar_height() -> None:
    base_00 = _datum("base-00", "floor_level_datum", 0.0)
    base_mezz = _datum("base-mezz", "floor_level_datum", 1.5)
    top = _datum("top", "wall_top_level_datum", 4.0)
    r0 = _relationship_support("rel-base-00", datum_evidence_id="base-00", role="wall_base")
    r1 = _relationship_support("rel-base-mezz", datum_evidence_id="base-mezz", role="wall_base")
    rt = _relationship_support("rel-top", datum_evidence_id="top", role="wall_top")

    qty = _resolve(
        lower=base_00,
        upper=top,
        proofs=(
            _proof("p-base-00", datum_evidence_id="base-00", role="wall_base", support_evidence_id="rel-base-00"),
            _proof("p-base-mezz", datum_evidence_id="base-mezz", role="wall_base", support_evidence_id="rel-base-mezz"),
            _proof("p-top", datum_evidence_id="top", role="wall_top", support_evidence_id="rel-top"),
        ),
        support=(r0, r1, rt),
        entity_ids=("base-00", "base-mezz", "top", "rel-base-00", "rel-base-mezz", "rel-top"),
    )

    assert qty.abstained
    assert qty.value is None
    assert "wall_base_relation_ambiguous" in qty.blocking_reasons
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in qty.blocking_reasons


def test_attack_2_correct_top_wrong_unbound_base_is_blocked() -> None:
    base = _datum("base-a", "floor_level_datum", 0.0)
    top = _datum("top", "wall_top_level_datum", 4.2)
    rt = _relationship_support("rel-top", datum_evidence_id="top", role="wall_top")
    qty = _resolve(
        lower=base,
        upper=top,
        proofs=(_proof("p-top", datum_evidence_id="top", role="wall_top", support_evidence_id="rel-top"),),
        support=(rt,),
        entity_ids=("base-a", "top", "rel-top"),
    )
    assert qty.abstained
    assert qty.value is None
    assert "wall_base_relation_unproven" in qty.blocking_reasons


def test_attack_3_generic_soffit_cannot_authorize_structural_wall_top() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    soffit = _datum("soffit", "soffit_level_datum", 3.0)
    rb = _relationship_support("rel-base", datum_evidence_id="base", role="wall_base")
    rs = _relationship_support("rel-soffit", datum_evidence_id="soffit", role="wall_top")
    qty = _resolve(
        lower=base,
        upper=soffit,
        proofs=(
            _proof("p-base", datum_evidence_id="base", role="wall_base", support_evidence_id="rel-base"),
            _proof("p-soffit", datum_evidence_id="soffit", role="wall_top", support_evidence_id="rel-soffit"),
        ),
        support=(rb, rs),
    )
    assert qty.abstained
    assert "unsupported_upper_datum_kind" in qty.blocking_reasons


def test_attack_4_wall_spanning_step_cannot_publish_scalar_by_average_or_selection() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    top = _datum("top", "wall_top_level_datum", 4.0)
    proofs, support = _apparently_complete_claims(base, top)
    qty = _resolve(
        lower=base,
        upper=top,
        proofs=proofs,
        support=support,
        entity_metadata={"height_profile": "stepped", "scalar_height_representative_proven": True},
    )
    assert qty.abstained
    assert "variable_height_requires_profile_authority" in qty.blocking_reasons


def test_attack_5_adjacent_wall_relationship_does_not_leak_to_target_wall() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    top = _datum("top", "wall_top_level_datum", 4.2)
    rb_w2 = _relationship_support("rel-base-w2", wall_id="w2", datum_evidence_id="base", role="wall_base")
    rt_w2 = _relationship_support("rel-top-w2", wall_id="w2", datum_evidence_id="top", role="wall_top")
    qty = _resolve(
        lower=base,
        upper=top,
        proofs=(
            _proof("p-base-w2", wall_id="w2", datum_evidence_id="base", role="wall_base", support_evidence_id="rel-base-w2"),
            _proof("p-top-w2", wall_id="w2", datum_evidence_id="top", role="wall_top", support_evidence_id="rel-top-w2"),
        ),
        support=(rb_w2, rt_w2),
    )
    assert qty.abstained
    assert "wall_base_relation_unproven" in qty.blocking_reasons
    assert "wall_top_relation_unproven" in qty.blocking_reasons


def test_attack_6_storey_label_equality_does_not_establish_datum_identity() -> None:
    base = _datum("base-level-1-a", "floor_level_datum", 0.0, metadata={"level_label": "LEVEL 1"})
    top = _datum("top", "wall_top_level_datum", 4.0, metadata={"level_label": "LEVEL 1"})
    qty = _resolve(lower=base, upper=top, proofs=(), support=())
    assert qty.abstained
    assert "wall_base_relation_unproven" in qty.blocking_reasons
    assert "wall_top_relation_unproven" in qty.blocking_reasons


def test_attack_7_added_contradictory_claim_cannot_strengthen_authority() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    base_conflict = _datum("base-conflict", "floor_level_datum", 1.2)
    top = _datum("top", "wall_top_level_datum", 4.2)
    rb = _relationship_support("rel-base", datum_evidence_id="base", role="wall_base")
    rbc = _relationship_support("rel-base-conflict", datum_evidence_id="base-conflict", role="wall_base")
    rt = _relationship_support("rel-top", datum_evidence_id="top", role="wall_top")
    base_proof = _proof("p-base", datum_evidence_id="base", role="wall_base", support_evidence_id="rel-base")
    top_proof = _proof("p-top", datum_evidence_id="top", role="wall_top", support_evidence_id="rel-top")

    baseline = _resolve(lower=base, upper=top, proofs=(base_proof, top_proof), support=(rb, rt))
    assert baseline.abstained
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in baseline.blocking_reasons

    ambiguous = _resolve(
        lower=base,
        upper=top,
        proofs=(
            base_proof,
            top_proof,
            _proof("p-base-conflict", datum_evidence_id="base-conflict", role="wall_base", support_evidence_id="rel-base-conflict"),
        ),
        support=(rb, rt, rbc),
        entity_ids=("base", "base-conflict", "top", "rel-base", "rel-top", "rel-base-conflict"),
    )
    assert ambiguous.abstained
    assert ambiguous.value is None
    assert "wall_base_relation_ambiguous" in ambiguous.blocking_reasons
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in ambiguous.blocking_reasons


def test_removing_relationship_provenance_cannot_strengthen_height() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    top = _datum("top", "wall_top_level_datum", 4.2)
    rb = _relationship_support("rel-base", datum_evidence_id="base", role="wall_base")
    rt = _relationship_support("rel-top", datum_evidence_id="top", role="wall_top")
    valid_base = _proof("p-base", datum_evidence_id="base", role="wall_base", support_evidence_id="rel-base")
    valid_top = _proof("p-top", datum_evidence_id="top", role="wall_top", support_evidence_id="rel-top")

    baseline = _resolve(lower=base, upper=top, proofs=(valid_base, valid_top), support=(rb, rt))
    assert baseline.abstained
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in baseline.blocking_reasons

    missing_support = replace(valid_base, relationship_evidence_ids=("missing-rel",))
    blocked = _resolve(lower=base, upper=top, proofs=(missing_support, valid_top), support=(rb, rt))
    assert blocked.abstained
    assert "wall_base_relation_unproven" in blocked.blocking_reasons
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in blocked.blocking_reasons


def test_cross_view_datum_requires_independent_cross_view_relationship_support() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    top = _datum("top-section", "wall_top_level_datum", 4.2, viewport_id="vp-section")
    rb = _relationship_support("rel-base", datum_evidence_id="base", role="wall_base")
    rt = _relationship_support("rel-top-section", datum_evidence_id="top-section", role="wall_top", viewport_id="vp-section")
    qty = _resolve(
        lower=base,
        upper=top,
        proofs=(
            _proof("p-base", datum_evidence_id="base", role="wall_base", support_evidence_id="rel-base"),
            _proof("p-top", datum_evidence_id="top-section", role="wall_top", support_evidence_id="rel-top-section", datum_viewport_id="vp-section"),
        ),
        support=(rb, rt),
    )
    assert qty.abstained
    assert "wall_top_cross_view_relation_unproven" in qty.blocking_reasons
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in qty.blocking_reasons


def test_fabricated_exact_segment_relation_records_cannot_mint_firm_height() -> None:
    base = _datum("base", "floor_level_datum", 1.2)
    top = _datum("top", "wall_top_level_datum", 4.5)
    proofs, support = _apparently_complete_claims(base, top)
    qty = _resolve(lower=base, upper=top, proofs=proofs, support=support)
    assert qty.abstained
    assert qty.value is None
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in qty.blocking_reasons
    assert qty.metadata["wall_segment_id"] == SEGMENT


def test_direct_documented_wall_height_remains_independently_firm() -> None:
    direct = _datum("direct", "wall_height_dimension", 3.3)
    qty = build_wall_height_quantity(
        wall_id="w1",
        context=_context(),
        document=_document(("direct",)),
        viewport=_viewport(),
        entity=_entity(("direct",)),
        direct_height_evidence=direct,
    )
    assert qty.abstained is False
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.value == 3.3


def test_blocked_datum_height_does_not_downgrade_length_but_blocks_gross_area() -> None:
    base = _datum("base", "floor_level_datum", 0.0)
    top = _datum("top", "wall_top_level_datum", 3.0)
    proofs, support = _apparently_complete_claims(base, top)
    height = _resolve(lower=base, upper=top, proofs=proofs, support=support)
    length = QuantityEvidence(
        quantity_id="length",
        family="wall_length",
        semantic_key="wall_length:w1",
        value=4.0,
        unit="m",
        input_entity_ids=("w1",),
        formula="documented_length",
        formula_version="test",
        evidence_ids=("length-evidence",),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        metadata={
            "source_sha256": SHA,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap",
            "canonical_graph_snapshot_id": "graphsnap",
            "viewport_id": "vp-plan",
            "page_no": 1,
        },
    )
    gross = build_gross_wall_area_quantity(
        wall_id="w1",
        wall_length=length,
        wall_height=height,
        context=_context(),
    )
    assert length.status == AuthorityStatus.FIRM.value
    assert length.value == 4.0
    assert height.status == AuthorityStatus.BLOCKED.value
    assert AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE in height.blocking_reasons
    assert gross.status == AuthorityStatus.BLOCKED.value
    assert "wall_height_abstained" in gross.blocking_reasons
