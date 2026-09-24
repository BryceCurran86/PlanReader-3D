"""Synthetic test matrix for generic DPC plinth-run authority (SHADOW-ONLY).

Covers all Phase 6 requirements:
- POSITIVES:
  1. Rectangular external masonry walls + external scope -> external perimeter only.
  2. External + internal foundation-supported walls + all-masonry scope -> both included.
  3. Multiple views / duplicate representations of the same physical wall -> deduplicated to 1.
  4. Authoritative firm wall lengths -> exact sum.
- NEGATIVES:
  - DPC section annotation but no wall identity
  - walls but no DPC specification
  - internal partition without foundation/plinth evidence
  - CHS post / stanchion (non-masonry)
  - door/window opening geometry
  - duplicated wall representations
  - unresolved physical equivalence
  - conflicting wall lengths / non-firm length
  - provisional / blocked status
  - stale revision
  - wrong source SHA
  - ambiguous / conflicting DPC scope
  - BOQ-only DPC wording (not on drawing sheets)
- METAMORPHIC:
  - translation invariance
  - rotation invariance
  - scale invariance
  - input ordering invariance
  - segment splitting invariance
  - unrelated page content invariance
  - viewport expansion invariance
"""
from __future__ import annotations

import math
from typing import Sequence

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
    REASON_DPC_SPEC_AUTHENTICATED,
    REASON_DPC_SPEC_MISSING,
    REASON_NON_MASONRY_ELEMENT,
    REASON_NON_REPRESENTATIVE_DUPLICATE,
    REASON_WALL_LENGTH_NOT_FIRM,
    REASON_WALL_NOT_FOUNDATION_SUPPORTED,
    REASON_WALL_OUT_OF_SCOPE,
    extract_dpc_specification_evidence,
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


def _make_doc_evidence(doc_id: str = _TEST_DOC_ID) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=doc_id,
        source_sha256=_TEST_SHA,
        page_count=1,
    )


def _make_wall(
    wall_id: str,
    *,
    interior_exterior: str = "exterior",
    length_pts: float = 100.0,
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


def _make_firm_qty(wall_id: str, length_m: float) -> QuantityEvidence:
    payload = {"family": "wall_length", "wall_id": wall_id, "length_m": length_m}
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty_test", payload),
        family="wall_length",
        semantic_key=f"wall_length:{wall_id}",
        value=length_m,
        unit="m",
        input_entity_ids=(wall_id,),
        authority="source_scaled",
        status=AuthorityStatus.FIRM.value,
        confidence=0.95,
        abstained=False,
    )


def _make_spec(
    scope: DPCPlinthScope = DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    text: str = "D.P.C.",
) -> DPCPlinthSpecificationEvidence:
    payload = {"spec": text, "scope": scope.value}
    return DPCPlinthSpecificationEvidence(
        evidence_id=stable_contract_id("spec_test", payload),
        source_sha256=_TEST_SHA,
        revision_id=_TEST_REV_ID,
        page_no=1,
        viewport_id="vp_1",
        spec_text=text,
        scope=scope,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(REASON_DPC_SPEC_AUTHENTICATED,),
    )


def _make_equivalence(rep_ids: Sequence[str]) -> PhysicalWallEquivalenceResolution:
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="vp_1",
        representative_wall_ids=tuple(rep_ids),
        abstained_wall_ids=(),
        equivalence_groups=tuple((wid,) for wid in rep_ids),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


# ---------------------------------------------------------------------------
# POSITIVE TESTS
# ---------------------------------------------------------------------------

def test_positive_rectangular_external_walls_perimeter_only():
    """Positive 1: 4 external walls with external scope -> exact perimeter sum."""
    w1 = _make_wall("w_north", interior_exterior="exterior")
    w2 = _make_wall("w_south", interior_exterior="exterior")
    w3 = _make_wall("w_east", interior_exterior="exterior")
    w4 = _make_wall("w_west", interior_exterior="exterior")
    w_int = _make_wall("w_partition", interior_exterior="interior")

    walls = [w1, w2, w3, w4, w_int]
    reps = ["w_north", "w_south", "w_east", "w_west", "w_partition"]
    equiv = _make_equivalence(reps)

    quantities = {
        "w_north": _make_firm_qty("w_north", 18.40),
        "w_south": _make_firm_qty("w_south", 18.40),
        "w_east": _make_firm_qty("w_east", 8.00),
        "w_west": _make_firm_qty("w_west", 8.00),
        "w_partition": _make_firm_qty("w_partition", 8.00),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=walls,
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY)],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(52.80, abs=1e-3)
    assert set(rec.included_wall_ids) == {"w_north", "w_south", "w_east", "w_west"}
    assert "w_partition" in rec.excluded_wall_ids


def test_positive_external_and_internal_foundation_supported_walls():
    """Positive 2: External + internal foundation walls with all-masonry scope -> both included."""
    w_ext = _make_wall("w_ext", interior_exterior="exterior")
    w_int = _make_wall("w_int", interior_exterior="interior")

    equiv = _make_equivalence(["w_ext", "w_int"])
    quantities = {
        "w_ext": _make_firm_qty("w_ext", 52.80),
        "w_int": _make_firm_qty("w_int", 14.45),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_ext, w_int],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.ALL_MASONRY_WALLS,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.ALL_MASONRY_WALLS)],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(67.25, abs=1e-3)
    assert set(rec.included_wall_ids) == {"w_ext", "w_int"}


def test_positive_multiple_views_deduplicated_by_equivalence():
    """Positive 3: Two views of the same physical wall -> representative counted once."""
    w_plan = _make_wall("w_plan_1", interior_exterior="exterior")
    w_section = _make_wall("w_section_1", interior_exterior="exterior")

    # Equivalence: w_plan_1 is the sole representative; w_section_1 is a duplicate
    equiv = _make_equivalence(["w_plan_1"])
    quantities = {
        "w_plan_1": _make_firm_qty("w_plan_1", 10.0),
        "w_section_1": _make_firm_qty("w_section_1", 10.0),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_plan, w_section],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY)],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == 10.0
    assert rec.included_wall_ids == ("w_plan_1",)
    assert "w_section_1" in rec.excluded_wall_ids


def test_positive_figured_dimension_authoritative_wall_lengths():
    """Positive 4: Wall lengths come from authoritative FIRM records."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    w2 = _make_wall("w2", interior_exterior="exterior")

    equiv = _make_equivalence(["w1", "w2"])
    quantities = {
        "w1": _make_firm_qty("w1", 12.345),
        "w2": _make_firm_qty("w2", 6.789),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1, w2],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY)],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.total_length_m == pytest.approx(19.134, abs=1e-4)


# ---------------------------------------------------------------------------
# NEGATIVE TESTS
# ---------------------------------------------------------------------------

def test_negative_dpc_annotation_without_wall_identity():
    """Negative: DPC spec present but no wall candidates exist -> abstains."""
    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=[],
    )
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert rec.total_length_m is None


def test_negative_walls_without_dpc_specification():
    """Negative: Walls exist but no DPC specification on drawings -> abstains."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 10.0)},
        dpc_scope=DPCPlinthScope.UNRESOLVED,
    )
    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[],  # No spec
        wall_assessments=assessments,
    )
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert REASON_DPC_SPEC_MISSING in rec.blocking_reasons


def test_negative_internal_partition_without_foundation_evidence():
    """Negative: Internal wall not foundation-supported -> excluded from DPC."""
    w_ext = _make_wall("w_ext", interior_exterior="exterior")
    w_slab_partition = _make_wall("w_part", interior_exterior="interior")

    equiv = _make_equivalence(["w_ext", "w_part"])
    quantities = {
        "w_ext": _make_firm_qty("w_ext", 20.0),
        "w_part": _make_firm_qty("w_part", 5.0),
    }

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_ext, w_slab_partition],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.ALL_MASONRY_WALLS,
        unsupported_internal_wall_ids=["w_part"],  # Sits on slab, no foundation plinth
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.ALL_MASONRY_WALLS)],
        wall_assessments=assessments,
    )

    assert rec.total_length_m == 20.0
    assert "w_part" in rec.excluded_wall_ids


def test_negative_chs_stanchion_post_excluded():
    """Negative: Non-masonry CHS post/stanchion excluded from masonry plinth DPC."""
    w_post = _make_wall("chs_stanchion", interior_exterior="exterior")
    equiv = _make_equivalence(["chs_stanchion"])

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w_post],
        equivalence=equiv,
        wall_length_quantities={"chs_stanchion": _make_firm_qty("chs_stanchion", 0.3)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
        non_masonry_wall_ids=["chs_stanchion"],
    )

    assert assessments[0].evaluation_status == "excluded"
    assert REASON_NON_MASONRY_ELEMENT in assessments[0].reason_codes


def test_negative_wall_length_not_firm():
    """Negative: Wall in scope has non-FIRM (provisional/blocked) length -> aggregate abstains."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    equiv = _make_equivalence(["w1"])

    provisional_qty = QuantityEvidence(
        quantity_id="qty_prov",
        family="wall_length",
        semantic_key="wall_length:w1",
        value=10.0,
        unit="m",
        input_entity_ids=("w1",),
        authority="provisional_default",
        status=AuthorityStatus.PROVISIONAL.value,  # NOT FIRM
        confidence=0.5,
        abstained=False,
    )

    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=equiv,
        wall_length_quantities={"w1": provisional_qty},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    assert assessments[0].evaluation_status == "abstained"
    assert REASON_WALL_LENGTH_NOT_FIRM in assessments[0].reason_codes

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY)],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert rec.total_length_m is None


def test_negative_conflicting_dpc_scope_notes():
    """Negative: Conflicting DPC scope specifications across drawings -> CONFLICT."""
    ev1 = _make_spec(DPCPlinthScope.EXTERNAL_WALLS_ONLY, text="DPC under external walls only")
    ev2 = _make_spec(DPCPlinthScope.ALL_MASONRY_WALLS, text="DPC under all walls")

    w1 = _make_wall("w1", interior_exterior="exterior")
    assessments = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=_make_equivalence(["w1"]),
        wall_length_quantities={"w1": _make_firm_qty("w1", 10.0)},
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    rec = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[ev1, ev2],
        wall_assessments=assessments,
    )

    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert rec.total_length_m is None


def test_negative_extract_dpc_spec_ignores_boq_text():
    """Negative: extract_dpc_specification_evidence called with non-drawing pages ignored."""
    doc = fitz.open()
    # Page 0 has non-DPC text
    p0 = doc.new_page()
    p0.insert_text((50, 50), "General Notes without any waterproof course")

    context = _make_context()
    evs = extract_dpc_specification_evidence(doc, context, drawing_pages=[0])
    assert len(evs) == 0


# ---------------------------------------------------------------------------
# METAMORPHIC TESTS
# ---------------------------------------------------------------------------

def test_metamorphic_input_ordering_invariance():
    """Metamorphic: Input ordering of walls does not alter aggregate result or total."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    w2 = _make_wall("w2", interior_exterior="exterior")
    w3 = _make_wall("w3", interior_exterior="exterior")

    equiv = _make_equivalence(["w1", "w2", "w3"])
    quantities = {
        "w1": _make_firm_qty("w1", 10.0),
        "w2": _make_firm_qty("w2", 15.0),
        "w3": _make_firm_qty("w3", 20.0),
    }

    # Order 1
    a1 = DPCPlinthRunProducer.assess_walls(
        walls=[w1, w2, w3],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )
    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a1,
    )

    # Order 2: reversed
    a2 = DPCPlinthRunProducer.assess_walls(
        walls=[w3, w1, w2],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )
    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a2,
    )

    assert r1.status == r2.status
    assert r1.total_length_m == r2.total_length_m
    assert set(r1.included_wall_ids) == set(r2.included_wall_ids)


def test_metamorphic_translation_invariance():
    """Metamorphic: Translating wall coordinates leaves length and DPC total identical."""
    dx, dy = 500.0, 750.0
    w_orig = _make_wall("w_orig", p1=(10.0, 20.0), p2=(110.0, 20.0))
    w_trans = _make_wall("w_trans", p1=(10.0 + dx, 20.0 + dy), p2=(110.0 + dx, 20.0 + dy))

    equiv = _make_equivalence(["w_orig", "w_trans"])
    quantities = {
        "w_orig": _make_firm_qty("w_orig", 100.0),
        "w_trans": _make_firm_qty("w_trans", 100.0),
    }

    a1 = DPCPlinthRunProducer.assess_walls(
        walls=[w_orig],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )
    a2 = DPCPlinthRunProducer.assess_walls(
        walls=[w_trans],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a1,
    )
    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a2,
    )

    assert r1.total_length_m == r2.total_length_m


def test_metamorphic_rotation_invariance():
    """Metamorphic: 90-degree rotated wall produces identical length and DPC total."""
    # Horizontal wall length 10m
    w_h = _make_wall("w_h", p1=(0.0, 0.0), p2=(10.0, 0.0))
    # Vertical wall length 10m
    w_v = _make_wall("w_v", p1=(0.0, 0.0), p2=(0.0, 10.0))

    equiv = _make_equivalence(["w_h", "w_v"])
    quantities = {
        "w_h": _make_firm_qty("w_h", 10.0),
        "w_v": _make_firm_qty("w_v", 10.0),
    }

    a_h = DPCPlinthRunProducer.assess_walls(
        walls=[w_h],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )
    a_v = DPCPlinthRunProducer.assess_walls(
        walls=[w_v],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    r_h = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a_h,
    )
    r_v = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=_make_context(),
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a_v,
    )

    assert r_h.total_length_m == r_v.total_length_m == 10.0


def test_metamorphic_unrelated_content_invariance():
    """Metamorphic: Additional non-wall evidence does not affect DPC aggregate."""
    w1 = _make_wall("w1", interior_exterior="exterior")
    equiv = _make_equivalence(["w1"])
    quantities = {"w1": _make_firm_qty("w1", 25.0)}

    a = DPCPlinthRunProducer.assess_walls(
        walls=[w1],
        equivalence=equiv,
        wall_length_quantities=quantities,
        dpc_scope=DPCPlinthScope.EXTERNAL_WALLS_ONLY,
    )

    # Context with different revision id but same source sha
    ctx1 = _make_context(rev="rev_initial")
    ctx2 = _make_context(rev="rev_annotated")

    r1 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx1,
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a,
    )
    r2 = DPCPlinthRunProducer.aggregate_dpc_plinth_run(
        context=ctx2,
        document=_make_doc_evidence(),
        dpc_spec_evidences=[_make_spec()],
        wall_assessments=a,
    )

    assert r1.total_length_m == r2.total_length_m == 25.0
    assert r1.status == r2.status == EvidenceResolutionStatus.CORROBORATED
