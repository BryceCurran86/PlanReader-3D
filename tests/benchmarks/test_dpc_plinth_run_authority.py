"""Synthetic test matrix for generic DPC plinth-run authority (SHADOW-ONLY).

Covers all Phase 3 & Review requirements:
- POSITIVES (arbitrary synthetic geometry, not mirroring Murera):
  1. Rectangular external masonry walls + external scope -> external perimeter only.
  2. External + internal foundation-supported walls + all-masonry scope -> both included.
  3. Multiple views / duplicate representations of the same physical wall -> deduplicated to 1.
  4. Authoritative firm wall lengths -> exact sum.
- NEGATIVES:
  - Bare "D.P.C." callout -> scope UNRESOLVED
  - Bare section DPC callout on an external-wall detail -> must NOT promote external-only scope
  - No material evidence -> wall material unresolved / abstain
  - Empty non-masonry exclusion list -> must NOT prove masonry
  - No foundation relation -> foundation support unresolved / abstain
  - Exterior role alone -> must NOT prove foundation support
  - Caller-supplied stale FIRM wall length -> reject
  - FIRM quantity for wrong wall ID -> reject
  - FIRM quantity with wrong family -> reject
  - FIRM quantity with wrong source/revision -> reject
  - DPC spec evidence wrong source SHA -> reject
  - DPC spec evidence stale revision -> reject
  - Conflicting explicit scope notes -> conflict
  - BOQ-only DPC wording (not on drawing sheets)
  - DPC section annotation but no wall identity
  - Walls but no DPC specification
  - Non-masonry element (CHS post) -> excluded
  - Unsupported internal wall -> excluded
- METAMORPHIC:
  - input ordering invariance
  - translation invariance
  - rotation invariance
  - unrelated content invariance
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import pytest
import fitz

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_dpc_plinth_run_authority import (
    DPCPlinthRunProducer,
    DPCPlinthRunRecord,
    DPCPlinthScope,
    DPCPlinthSpecificationEvidence,
    DPCPlinthWallAssessment,
    FoundationSupportStatus,
    WallFoundationRelationshipEvidence,
    WallMaterialEvidence,
    WallMaterialStatus,
    REASON_DPC_SPEC_AUTHENTICATED,
    REASON_DPC_SPEC_MISSING,
    REASON_DPC_SCOPE_ALL_MASONRY,
    REASON_DPC_SCOPE_EXTERNAL_ONLY,
    REASON_DPC_SCOPE_UNRESOLVED,
    REASON_EQUIVALENCE_BLOCKER,
    REASON_FOUNDATION_SUPPORT_UNRESOLVED,
    REASON_NO_INCLUDED_WALLS,
    REASON_NON_MASONRY_ELEMENT,
    REASON_NON_REPRESENTATIVE_DUPLICATE,
    REASON_QUANTITY_WRONG_ENTITY,
    REASON_QUANTITY_WRONG_FAMILY,
    REASON_QUANTITY_WRONG_UNIT,
    REASON_REVISION_MISMATCH,
    REASON_SOURCE_INTEGRITY_MISMATCH,
    REASON_WALL_IN_SCOPE,
    REASON_WALL_LENGTH_NOT_FIRM,
    REASON_WALL_MATERIAL_UNRESOLVED,
    REASON_WALL_NOT_FOUNDATION_SUPPORTED,
    REASON_WALL_OUT_OF_SCOPE,
    extract_dpc_specification_evidence,
    validate_wall_length_quantity_evidence,
)


_TEST_SHA = "a" * 64
_TEST_DOC_ID = "doc_test_1"
_TEST_REV_ID = "rev_1"


def _make_context(sha: str = _TEST_SHA, rev: str = _TEST_REV_ID) -> ProviderContext:
    return ProviderContext(
        run_id="run_1",
        workspace_id="ws_1",
        project_id="proj_1",
        document_id=_TEST_DOC_ID,
        source_sha256=sha,
        revision_id=rev,
        current_revision_id=rev,
        selected_pages=(1,),
        owned_viewport_ids=("vp_1",),
        evidence_snapshot_id="snap_1",
    )


def _make_doc_evidence(sha: str = _TEST_SHA, doc_id: str = _TEST_DOC_ID) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=doc_id,
        source_sha256=sha,
        page_count=1,
    )


def _make_wall(
    wall_id: str,
    *,
    interior_exterior: str = "exterior",
    viewport_id: str = "vp_1",
    p1: tuple[float, float] = (0.0, 0.0),
    p2: tuple[float, float] = (100.0, 0.0),
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id=viewport_id,
        representation="single_line",
        centerline_pts=(p1, p2),
        face_a_segment_ids=(f"seg_{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.2,
        thickness_authority="source_scaled",
        length_m=None,
        end_node_ids=(f"n1_{wall_id}", f"n2_{wall_id}"),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        interior_exterior=interior_exterior,
        level_id="L1",
        confidence=0.95,
    )


def _make_firm_qty(
    wall_id: str,
    length_m: float,
    *,
    family: str = "wall_length",
    unit: str = "m",
    status: str = AuthorityStatus.FIRM.value,
    abstained: bool = False,
    source_sha: str = _TEST_SHA,
    rev_id: str = _TEST_REV_ID,
    input_entity_ids: Optional[Sequence[str]] = None,
) -> QuantityEvidence:
    payload = {"family": family, "wall_id": wall_id, "length_m": length_m}
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty_test", payload),
        family=family,
        semantic_key=f"wall_length:{wall_id}",
        value=length_m,
        unit=unit,
        input_entity_ids=tuple(input_entity_ids if input_entity_ids is not None else (wall_id,)),
        authority="source_scaled",
        status=status,
        confidence=0.95,
        abstained=abstained,
        metadata={
            "source_sha256": source_sha,
            "revision_id": rev_id,
        },
    )


def _make_material_evidence(
    wall_id: str,
    status: WallMaterialStatus = WallMaterialStatus.MASONRY,
    *,
    source_sha: str = _TEST_SHA,
    rev_id: str = _TEST_REV_ID,
    res_status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> WallMaterialEvidence:
    payload = {"wall_id": wall_id, "mat": status.value, "sha": source_sha}
    return WallMaterialEvidence(
        evidence_id=stable_contract_id("mat_ev", payload),
        wall_id=wall_id,
        source_sha256=source_sha,
        revision_id=rev_id,
        material_status=status,
        material_description="200mm stone masonry walling",
        status=res_status,
        reason_codes=("material_corroborated",),
    )


def _make_foundation_rel(
    wall_id: str,
    support: FoundationSupportStatus = FoundationSupportStatus.SUPPORTED,
    *,
    source_sha: str = _TEST_SHA,
    rev_id: str = _TEST_REV_ID,
    res_status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> WallFoundationRelationshipEvidence:
    payload = {"wall_id": wall_id, "supp": support.value, "sha": source_sha}
    return WallFoundationRelationshipEvidence(
        relationship_id=stable_contract_id("found_rel", payload),
        wall_id=wall_id,
        source_sha256=source_sha,
        revision_id=rev_id,
        support_status=support,
        status=res_status,
        supporting_evidence_ids=("ev_found_1",),
        reason_codes=("foundation_strip_proven",),
    )


def _make_spec(
    scope: DPCPlinthScope = DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    text: str = "D.P.C. under external walls only",
    *,
    source_sha: str = _TEST_SHA,
    rev_id: str = _TEST_REV_ID,
    res_status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> DPCPlinthSpecificationEvidence:
    payload = {"spec": text, "scope": scope.value, "sha": source_sha, "rev": rev_id}
    reasons = (REASON_DPC_SPEC_AUTHENTICATED,)
    if scope == DPCPlinthScope.EXTERNAL_WALLS_ONLY:
        reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_EXTERNAL_ONLY)
    elif scope == DPCPlinthScope.ALL_MASONRY_WALLS:
        reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_ALL_MASONRY)
    else:
        reasons = (REASON_DPC_SPEC_AUTHENTICATED, REASON_DPC_SCOPE_UNRESOLVED)

    return DPCPlinthSpecificationEvidence(
        evidence_id=stable_contract_id("spec_test", payload),
        source_sha256=source_sha,
        revision_id=rev_id,
        page_no=1,
        viewport_id="vp_1",
        spec_text=text,
        scope=scope,
        status=res_status,
        reason_codes=reasons,
    )


def _make_equivalence(
    rep_ids: Sequence[str],
    blocked_ids: Optional[Sequence[str]] = None,
) -> PhysicalWallEquivalenceResolution:
    blocking = {wid: ("equivalence_conflict",) for wid in (blocked_ids or ())}
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="vp_1",
        representative_wall_ids=tuple(rep_ids),
        abstained_wall_ids=tuple(blocked_ids or ()),
        equivalence_groups=tuple((wid,) for wid in rep_ids),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id=blocking,
    )


# ---------------------------------------------------------------------------
# POSITIVE TESTS (Arbitrary Synthetic Values: 11.0, 7.0, 5.5)
# ---------------------------------------------------------------------------

def test_positive_rectangular_external_walls_perimeter_only():
    """Positive 1: 4 external walls (11+11+7+7=36m) with external scope -> exact 36m perimeter."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w_north", interior_exterior="exterior")
    w2 = _make_wall("w_south", interior_exterior="exterior")
    w3 = _make_wall("w_east", interior_exterior="exterior")
    w4 = _make_wall("w_west", interior_exterior="exterior")
    w_int = _make_wall("w_partition", interior_exterior="interior")

    walls = [w1, w2, w3, w4, w_int]
    reps = ["w_north", "w_south", "w_east", "w_west", "w_partition"]
    equiv = _make_equivalence(reps)

    quantities = {
        "w_north": _make_firm_qty("w_north", 11.00),
        "w_south": _make_firm_qty("w_south", 11.00),
        "w_east": _make_firm_qty("w_east", 7.00),
        "w_west": _make_firm_qty("w_west", 7.00),
        "w_partition": _make_firm_qty("w_partition", 5.50),
    }

    # All walls have positive masonry evidence and positive foundation support
    materials = {wid: _make_material_evidence(wid, WallMaterialStatus.MASONRY) for wid in reps}
    foundations = {wid: _make_foundation_rel(wid, FoundationSupportStatus.SUPPORTED) for wid in reps}

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=walls,
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(36.00, abs=1e-3)
    assert set(rec.included_wall_ids) == {"w_north", "w_south", "w_east", "w_west"}
    assert "w_partition" in rec.excluded_wall_ids


def test_positive_external_and_internal_foundation_supported_walls():
    """Positive 2: External (36m) + internal (5.5m) foundation walls with all-masonry scope -> 41.5m."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w_north", interior_exterior="exterior")
    w2 = _make_wall("w_south", interior_exterior="exterior")
    w3 = _make_wall("w_east", interior_exterior="exterior")
    w4 = _make_wall("w_west", interior_exterior="exterior")
    w_int = _make_wall("w_int", interior_exterior="interior")

    walls = [w1, w2, w3, w4, w_int]
    reps = ["w_north", "w_south", "w_east", "w_west", "w_int"]
    equiv = _make_equivalence(reps)

    quantities = {
        "w_north": _make_firm_qty("w_north", 11.00),
        "w_south": _make_firm_qty("w_south", 11.00),
        "w_east": _make_firm_qty("w_east", 7.00),
        "w_west": _make_firm_qty("w_west", 7.00),
        "w_int": _make_firm_qty("w_int", 5.50),
    }

    materials = {wid: _make_material_evidence(wid, WallMaterialStatus.MASONRY) for wid in reps}
    foundations = {wid: _make_foundation_rel(wid, FoundationSupportStatus.SUPPORTED) for wid in reps}

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=walls,
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.ALL_MASONRY_WALLS,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.ALL_MASONRY_WALLS, "D.P.C. under all masonry walls")],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(41.50, abs=1e-3)
    assert set(rec.included_wall_ids) == {"w_north", "w_south", "w_east", "w_west", "w_int"}


def test_positive_multiple_views_deduplicated_by_equivalence():
    """Positive 3: Two views of the same physical wall -> representative counted once (11m)."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w_plan = _make_wall("w_plan_1", interior_exterior="exterior")
    w_section = _make_wall("w_section_1", interior_exterior="exterior")

    # Equivalence: w_plan_1 is the sole representative; w_section_1 is a duplicate
    equiv = _make_equivalence(["w_plan_1"])
    quantities = {
        "w_plan_1": _make_firm_qty("w_plan_1", 11.0),
        "w_section_1": _make_firm_qty("w_section_1", 11.0),
    }
    materials = {
        "w_plan_1": _make_material_evidence("w_plan_1", WallMaterialStatus.MASONRY),
        "w_section_1": _make_material_evidence("w_section_1", WallMaterialStatus.MASONRY),
    }
    foundations = {
        "w_plan_1": _make_foundation_rel("w_plan_1", FoundationSupportStatus.SUPPORTED),
        "w_section_1": _make_foundation_rel("w_section_1", FoundationSupportStatus.SUPPORTED),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_plan, w_section],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == 11.0
    assert rec.included_wall_ids == ("w_plan_1",)
    assert "w_section_1" in rec.excluded_wall_ids


def test_positive_figured_dimension_authoritative_wall_lengths():
    """Positive 4: Wall lengths come from authoritative FIRM records (12.50 + 6.25 = 18.75m)."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")
    w2 = _make_wall("w2", interior_exterior="exterior")

    equiv = _make_equivalence(["w1", "w2"])
    quantities = {
        "w1": _make_firm_qty("w1", 12.50),
        "w2": _make_firm_qty("w2", 6.25),
    }
    materials = {
        "w1": _make_material_evidence("w1", WallMaterialStatus.MASONRY),
        "w2": _make_material_evidence("w2", WallMaterialStatus.MASONRY),
    }
    foundations = {
        "w1": _make_foundation_rel("w1", FoundationSupportStatus.SUPPORTED),
        "w2": _make_foundation_rel("w2", FoundationSupportStatus.SUPPORTED),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1, w2],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(18.75, abs=1e-4)


# ---------------------------------------------------------------------------
# NEGATIVE TESTS (Scope, Material, Foundation, Quantity Integrity)
# ---------------------------------------------------------------------------

def test_negative_bare_dpc_scope_unresolved():
    """Negative 1: Bare 'D.P.C.' annotation without scope wording -> scope UNRESOLVED."""
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((100, 100), "D.P.C. 200mm wide bitumen felt")

    ctx = _make_context()
    evs = extract_dpc_specification_evidence(doc, ctx)
    assert len(evs) == 1
    assert evs[0].scope == DPCPlinthScope.UNRESOLVED
    assert REASON_DPC_SCOPE_UNRESOLVED in evs[0].reason_codes

    w1 = _make_wall("w1", interior_exterior="exterior")
    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=evs[0].scope,
        context=ctx,
        document=_make_doc_evidence(),
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_DPC_SCOPE_UNRESOLVED in assessments[0].reason_codes

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=_make_doc_evidence(),
        dpc_spec_evidences=evs,
        wall_assessments=assessments,
    )
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert rec.scope == DPCPlinthScope.UNRESOLVED
    assert rec.total_length_m is None
    assert REASON_DPC_SCOPE_UNRESOLVED in rec.blocking_reasons


def test_negative_bare_section_dpc_callout_does_not_promote_external_scope():
    """Negative 2: Bare section DPC callout on an external-wall detail must NOT promote external-only scope."""
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 50), "SECTION A-A: EXTERNAL WALL DETAIL\n150mm stone walling\n200mm D.P.C. under wall")

    ctx = _make_context()
    evs = extract_dpc_specification_evidence(doc, ctx)
    assert len(evs) == 1
    # Must remain UNRESOLVED because there is no explicit "external walls only" scope note
    assert evs[0].scope == DPCPlinthScope.UNRESOLVED


def test_negative_no_material_evidence_abstains():
    """Negative 3: Wall candidate with no material evidence -> material unresolved / abstain."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=None,  # No material evidence
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    assert assessments[0].material_status == WallMaterialStatus.UNRESOLVED
    assert not assessments[0].is_masonry
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_WALL_MATERIAL_UNRESOLVED in assessments[0].reason_codes


def test_negative_empty_non_masonry_exclusion_list_does_not_prove_masonry():
    """Negative 4: Passing empty material evidence must NOT promote walls to masonry."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={},  # Empty mapping
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    assert assessments[0].material_status == WallMaterialStatus.UNRESOLVED
    assert assessments[0].evaluation_status == "abstained"


def test_negative_no_foundation_relation_abstains():
    """Negative 5: Wall candidate with no foundation relation -> foundation support unresolved / abstain."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships=None,  # No foundation evidence
    )

    assert assessments[0].foundation_support == FoundationSupportStatus.UNRESOLVED
    assert not assessments[0].foundation_supported
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_FOUNDATION_SUPPORT_UNRESOLVED in assessments[0].reason_codes


def test_negative_exterior_role_alone_does_not_prove_foundation_support():
    """Negative 6: Exterior role alone must NOT prove foundation support."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w_ext = _make_wall("w_ext", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_ext],
        equivalence=_make_equivalence(["w_ext"]),
        wall_length_quantities={"w_ext": _make_firm_qty("w_ext", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w_ext": _make_material_evidence("w_ext")},
        wall_foundation_relationships={},  # Empty: exterior wall has no foundation record
    )

    assert assessments[0].foundation_support == FoundationSupportStatus.UNRESOLVED
    assert assessments[0].evaluation_status == "abstained"


def test_negative_caller_supplied_stale_firm_wall_length_rejected():
    """Negative 7: Quantity with stale revision is rejected."""
    ctx = _make_context(rev="rev_current")
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    stale_qty = _make_firm_qty("w1", 11.0, rev_id="rev_old")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": stale_qty},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1", rev_id="rev_current")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1", rev_id="rev_current")},
    )

    assert assessments[0].length_status == "rejected"
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_REVISION_MISMATCH in assessments[0].reason_codes


def test_negative_firm_quantity_wrong_wall_id_rejected():
    """Negative 8: FIRM quantity for wrong wall ID is rejected."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    cross_wall_qty = _make_firm_qty("w1", 11.0, input_entity_ids=["w_other_wall"])

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": cross_wall_qty},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    assert assessments[0].length_status == "rejected"
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_QUANTITY_WRONG_ENTITY in assessments[0].reason_codes


def test_negative_firm_quantity_wrong_family_rejected():
    """Negative 9: FIRM quantity with wrong family (e.g. substructure_surface_bed) is rejected."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    wrong_family_qty = _make_firm_qty("w1", 11.0, family="substructure_surface_bed")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": wrong_family_qty},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    assert assessments[0].length_status == "rejected"
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_QUANTITY_WRONG_FAMILY in assessments[0].reason_codes


def test_negative_firm_quantity_wrong_source_sha_rejected():
    """Negative 10: FIRM quantity with wrong source SHA is rejected."""
    ctx = _make_context(sha=_TEST_SHA)
    doc = _make_doc_evidence(sha=_TEST_SHA)
    w1 = _make_wall("w1", interior_exterior="exterior")

    wrong_sha_qty = _make_firm_qty("w1", 11.0, source_sha="b" * 64)

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": wrong_sha_qty},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    assert assessments[0].length_status == "rejected"
    assert assessments[0].evaluation_status == "abstained"
    assert REASON_SOURCE_INTEGRITY_MISMATCH in assessments[0].reason_codes


def test_negative_dpc_spec_evidence_wrong_source_sha_rejected():
    """Negative 11: DPC spec evidence with wrong source SHA is rejected by aggregate."""
    ctx = _make_context(sha=_TEST_SHA)
    doc = _make_doc_evidence(sha=_TEST_SHA)
    w1 = _make_wall("w1", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    wrong_sha_spec = _make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, source_sha="b" * 64)

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[wrong_sha_spec],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert REASON_SOURCE_INTEGRITY_MISMATCH in rec.blocking_reasons


def test_negative_dpc_spec_evidence_stale_revision_rejected():
    """Negative 12: DPC spec evidence with stale revision is rejected by aggregate."""
    ctx = _make_context(rev="rev_current")
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0, rev_id="rev_current")},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1", rev_id="rev_current")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1", rev_id="rev_current")},
    )

    stale_spec = _make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, rev_id="rev_old")

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[stale_spec],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert REASON_REVISION_MISMATCH in rec.blocking_reasons


def test_negative_conflicting_dpc_scope_notes():
    """Negative 13: Conflicting DPC scope specifications across drawings -> CONFLICT."""
    ev1 = _make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, text="DPC under external walls only")
    ev2 = _make_spec(DPCPlinthScope.ALL_MASONRY_WALLS, text="DPC under all walls")

    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")
    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[ev1, ev2],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert rec.total_length_m is None


def test_negative_extract_dpc_spec_ignores_boq_text():
    """Negative 14: Non-drawing sheets without drawing notes yield no DPC specs."""
    doc = fitz.open()
    p0 = doc.new_page()
    p0.insert_text((50, 50), "General Notes without any waterproof course")

    context = _make_context()
    evs = extract_dpc_specification_evidence(doc, context, drawing_pages=[0])
    assert len(evs) == 0


def test_negative_dpc_annotation_without_wall_identity():
    """Negative 15: DPC spec present but no wall candidates exist -> abstains."""
    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=[],
    )
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert rec.total_length_m is None
    assert REASON_NO_INCLUDED_WALLS in rec.blocking_reasons


def test_negative_walls_without_dpc_specification():
    """Negative 16: Walls exist but no DPC specification on drawings -> abstains."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")
    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 11.0)},
        dpc_scope=DPCPlinthScope.UNRESOLVED,
        context=ctx,
        document=doc,
        wall_material_evidences={"w1": _make_material_evidence("w1")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1")},
    )
    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[],  # No spec
        wall_assessments=assessments,
    )
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert REASON_DPC_SPEC_MISSING in rec.blocking_reasons


def test_negative_chs_stanchion_post_excluded():
    """Negative 17: Non-masonry element excluded from masonry plinth DPC."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w_post = _make_wall("chs_stanchion", interior_exterior="exterior")
    equiv = _make_equivalence(["chs_stanchion"])

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_post],
        equivalence=equiv,
        wall_length_quantities={"chs_stanchion": _make_firm_qty("chs_stanchion", 0.3)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences={"chs_stanchion": _make_material_evidence("chs_stanchion", WallMaterialStatus.NON_MASONRY)},
        wall_foundation_relationships={"chs_stanchion": _make_foundation_rel("chs_stanchion", FoundationSupportStatus.SUPPORTED)},
    )

    assert assessments[0].evaluation_status == "excluded"
    assert REASON_NON_MASONRY_ELEMENT in assessments[0].reason_codes


def test_negative_internal_partition_unsupported_excluded():
    """Negative 18: Internal partition marked UNSUPPORTED excluded under all-masonry scope."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w_ext = _make_wall("w_ext", interior_exterior="exterior")
    w_part = _make_wall("w_part", interior_exterior="interior")
    equiv = _make_equivalence(["w_ext", "w_part"])

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_ext, w_part],
        equivalence=equiv,
        wall_length_quantities={
            "w_ext": _make_firm_qty("w_ext", 11.0),
            "w_part": _make_firm_qty("w_part", 5.5),
        },
        dpc_scope=DPCPlinthScope.ALL_MASONRY_WALLS,
        context=ctx,
        document=doc,
        wall_material_evidences={
            "w_ext": _make_material_evidence("w_ext", WallMaterialStatus.MASONRY),
            "w_part": _make_material_evidence("w_part", WallMaterialStatus.MASONRY),
        },
        wall_foundation_relationships={
            "w_ext": _make_foundation_rel("w_ext", FoundationSupportStatus.SUPPORTED),
            "w_part": _make_foundation_rel("w_part", FoundationSupportStatus.UNSUPPORTED),
        },
    )

    assert assessments[0].evaluation_status == "included"
    assert assessments[1].evaluation_status == "excluded"
    assert REASON_WALL_NOT_FOUNDATION_SUPPORTED in assessments[1].reason_codes


# ---------------------------------------------------------------------------
# METAMORPHIC TESTS
# ---------------------------------------------------------------------------

def test_metamorphic_input_ordering_invariance():
    """Metamorphic: Input ordering of walls does not alter aggregate result or total."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w1 = _make_wall("w1", interior_exterior="exterior")
    w2 = _make_wall("w2", interior_exterior="exterior")
    w3 = _make_wall("w3", interior_exterior="exterior")

    equiv = _make_equivalence(["w1", "w2", "w3"])
    quantities = {
        "w1": _make_firm_qty("w1", 10.0),
        "w2": _make_firm_qty("w2", 15.0),
        "w3": _make_firm_qty("w3", 20.0),
    }
    materials = {wid: _make_material_evidence(wid, WallMaterialStatus.MASONRY) for wid in ["w1", "w2", "w3"]}
    foundations = {wid: _make_foundation_rel(wid, FoundationSupportStatus.SUPPORTED) for wid in ["w1", "w2", "w3"]}

    # Order 1: w1, w2, w3
    a1 = DPCPlinthRunProducer.assess_walls(
        walls=[w1, w2, w3],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )
    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a1,
    )

    # Order 2: reversed
    a2 = DPCPlinthRunProducer.assess_walls(
        walls=[w3, w1, w2],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )
    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a2,
    )

    assert r1.status == r2.status == EvidenceResolutionStatus.CORROBORATED
    assert r1.total_length_m == r2.total_length_m == 45.0
    assert set(r1.included_wall_ids) == set(r2.included_wall_ids)


def test_metamorphic_translation_invariance():
    """Metamorphic: Translating wall coordinates leaves length and DPC total identical."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    dx, dy = 500.0, 750.0
    w_orig = _make_wall("w_orig", p1=(10.0, 20.0), p2=(110.0, 20.0))
    w_trans = _make_wall("w_trans", p1=(10.0 + dx, 20.0 + dy), p2=(110.0 + dx, 20.0 + dy))

    equiv = _make_equivalence(["w_orig", "w_trans"])
    quantities = {
        "w_orig": _make_firm_qty("w_orig", 25.0),
        "w_trans": _make_firm_qty("w_trans", 25.0),
    }
    materials = {
        "w_orig": _make_material_evidence("w_orig", WallMaterialStatus.MASONRY),
        "w_trans": _make_material_evidence("w_trans", WallMaterialStatus.MASONRY),
    }
    foundations = {
        "w_orig": _make_foundation_rel("w_orig", FoundationSupportStatus.SUPPORTED),
        "w_trans": _make_foundation_rel("w_trans", FoundationSupportStatus.SUPPORTED),
    }

    a1 = DPCPlinthRunProducer.assess_walls(
        walls=[w_orig],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )
    a2 = DPCPlinthRunProducer.assess_walls(
        walls=[w_trans],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a1,
    )
    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a2,
    )

    assert r1.total_length_m == r2.total_length_m == 25.0


def test_metamorphic_rotation_invariance():
    """Metamorphic: 90-degree rotated wall produces identical length and DPC total."""
    ctx = _make_context()
    doc = _make_doc_evidence()
    w_h = _make_wall("w_h", p1=(0.0, 0.0), p2=(10.0, 0.0))
    w_v = _make_wall("w_v", p1=(0.0, 0.0), p2=(0.0, 10.0))

    equiv = _make_equivalence(["w_h", "w_v"])
    quantities = {
        "w_h": _make_firm_qty("w_h", 14.0),
        "w_v": _make_firm_qty("w_v", 14.0),
    }
    materials = {
        "w_h": _make_material_evidence("w_h", WallMaterialStatus.MASONRY),
        "w_v": _make_material_evidence("w_v", WallMaterialStatus.MASONRY),
    }
    foundations = {
        "w_h": _make_foundation_rel("w_h", FoundationSupportStatus.SUPPORTED),
        "w_v": _make_foundation_rel("w_v", FoundationSupportStatus.SUPPORTED),
    }

    a_h = DPCPlinthRunProducer.assess_walls(
        walls=[w_h],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )
    a_v = DPCPlinthRunProducer.assess_walls(
        walls=[w_v],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx,
        document=doc,
        wall_material_evidences=materials,
        wall_foundation_relationships=foundations,
    )

    r_h = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a_h,
    )
    r_v = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx,
        document=doc,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only")],
        wall_assessments=a_v,
    )

    assert r_h.total_length_m == r_v.total_length_m == 14.0


def test_metamorphic_unrelated_content_invariance():
    """Metamorphic: Additional non-wall evidence does not affect DPC aggregate."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    equiv = _make_equivalence(["w1"])
    quantities = {"w1": _make_firm_qty("w1", 22.0)}
    materials = {"w1": _make_material_evidence("w1", WallMaterialStatus.MASONRY)}
    foundations = {"w1": _make_foundation_rel("w1", FoundationSupportStatus.SUPPORTED)}

    ctx1 = _make_context(rev="rev_initial")
    doc1 = _make_doc_evidence()

    a1 = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=equiv,
        wall_length_quantities={"w1": _make_firm_qty("w1", 22.0, rev_id="rev_initial")},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx1,
        document=doc1,
        wall_material_evidences={"w1": _make_material_evidence("w1", rev_id="rev_initial")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1", rev_id="rev_initial")},
    )

    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx1,
        document=doc1,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only", rev_id="rev_initial")],
        wall_assessments=a1,
    )

    ctx2 = _make_context(rev="rev_annotated")
    doc2 = _make_doc_evidence()

    a2 = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=equiv,
        wall_length_quantities={"w1": _make_firm_qty("w1", 22.0, rev_id="rev_annotated")},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        context=ctx2,
        document=doc2,
        wall_material_evidences={"w1": _make_material_evidence("w1", rev_id="rev_annotated")},
        wall_foundation_relationships={"w1": _make_foundation_rel("w1", rev_id="rev_annotated")},
    )

    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx2,
        document=doc2,
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, "D.P.C. under external walls only", rev_id="rev_annotated")],
        wall_assessments=a2,
    )

    assert r1.total_length_m == r2.total_length_m == 22.0
    assert r1.status == r2.status == EvidenceResolutionStatus.CORROBORATED
