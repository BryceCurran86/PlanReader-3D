from __future__ import annotations

from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import scale_calibration_fingerprint
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    ScaleSourceReading,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    resolve_page_scale_calibration,
)
from pb_physical_wall_existence_authority import adapt_wall_candidate_to_entity_evidence
from pb_physical_wall_identity import (
    PhysicalWallEquivalenceResolution,
    resolve_physical_wall_identity,
)
from pb_viewport_scale_binding import ViewportScaleBinding
from pb_wall_length_quantity import build_wall_length_quantities, build_wall_length_quantity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

SHA = "d" * 64


def _context() -> ProviderContext:
    return ProviderContext(
        run_id="run-c145",
        workspace_id="ws",
        project_id="project",
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=("vp",),
        evidence_snapshot_id="evsnap-1",
        canonical_graph_snapshot_id="graphsnap-1",
        measurement_authority_snapshot_id="measuresnap-1",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp", 1),),
    )


def _document(ids: tuple[str, ...]) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(*, resolved_scale_id: str | None = None) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp",
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-w1",),
        resolved_scale_id=resolved_scale_id,
        confidence=1.0,
    )


def _wall(wall_id: str, *, y: float = 0.0, face_id: str | None = None) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id="vp",
        representation="single_line",
        centerline_pts=((0.0, y), (100.0, y)),
        face_a_segment_ids=(face_id or f"seg-{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}-n1", f"{wall_id}-n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id="L1",
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=1.0,
        supporting_evidence_ids=(f"u2-{wall_id}", f"pair-{wall_id}"),
    )


def _atoms(wall_id: str) -> tuple[EvidenceAtom, EvidenceAtom]:
    metadata = {
        "wall_candidate_id": wall_id,
        "revision_id": "R1",
        "evidence_snapshot_id": "evsnap-1",
        "source_sha256": SHA,
    }
    return (
        EvidenceAtom(
            evidence_id=f"u2-{wall_id}",
            document_id="doc",
            page_id="page-1",
            viewport_id="vp",
            kind=KIND_PHYSICAL_WALL,
            method="test",
            confidence=0.8,
            status=EvidenceResolutionStatus.CANDIDATE,
            metadata=metadata,
        ),
        EvidenceAtom(
            evidence_id=f"pair-{wall_id}",
            document_id="doc",
            page_id="page-1",
            viewport_id="vp",
            kind=FAMILY_PAIRED_WALL_FACES,
            method="test",
            confidence=0.8,
            status=EvidenceResolutionStatus.CANDIDATE,
            metadata=metadata,
        ),
    )


def _entity(wall: WallCandidate, document: DocumentEvidence):
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=_atoms(wall.candidate_id),
        document=document,
        viewport=_viewport(),
        context=_context(),
    )
    assert entity is not None
    return entity


def _scale(ratio: float):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="A101",
        readings=(ScaleSourceReading(ScaleSourceType.SCALE_BAR.value, f"1:{ratio:g}", ratio, 1.0),),
        revision_id="R1",
    )


def _binding(ratio: float) -> ViewportScaleBinding:
    scale = _scale(ratio)
    authority = measurement_authority_for_page_scale(scale)
    return ViewportScaleBinding(
        viewport_id="vp",
        page_no=1,
        source_sha256=SHA,
        revision_id="R1",
        calibration=scale,
        scale_fingerprint=scale_calibration_fingerprint(scale),
        measurement_authority=authority,
        blocking_reasons=() if authority == AuthorityStatus.FIRM.value else ("scale_not_firm",),
    )


def _fake_solo_equivalence(wall_id: str) -> PhysicalWallEquivalenceResolution:
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="vp",
        representative_wall_ids=(wall_id,),
        abstained_wall_ids=(),
        equivalence_groups=(),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


def _identity(wall: WallCandidate):
    edge_id = wall.face_a_segment_ids[0]
    return resolve_physical_wall_identity(
        wall=wall,
        edge_ids=(edge_id,),
        edges_by_id={
            edge_id: {
                "id": edge_id,
                "x1": wall.centerline_pts[0][0],
                "y1": wall.centerline_pts[0][1],
                "x2": wall.centerline_pts[-1][0],
                "y2": wall.centerline_pts[-1][1],
                "primitive_lineage": {"source_primitive_ids": [f"native-{wall.candidate_id}"]},
            }
        },
    )


def test_c1_hidden_same_viewport_scale_competitor_cannot_leave_firm() -> None:
    wall = _wall("w1")
    atoms = _atoms("w1")
    document = _document(tuple(atom.evidence_id for atom in atoms))
    admitted = _binding(100.0)
    hidden_competitor = _binding(50.0)
    assert hidden_competitor.scale_fingerprint != admitted.scale_fingerprint

    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=admitted.scale_fingerprint),
        entity=_entity(wall, document),
        evidence_atoms=atoms,
        equivalence=_fake_solo_equivalence("w1"),
        page_no=1,
        scale_bindings=(admitted,),  # attack: competing same-viewport binding omitted
    )

    assert qty.abstained is True
    assert "scale_universe_completeness_unproven" in qty.blocking_reasons


def test_c4_hand_constructed_equivalence_cannot_authorize_firm() -> None:
    wall = _wall("w1")
    atoms = _atoms("w1")
    document = _document(tuple(atom.evidence_id for atom in atoms))
    binding = _binding(100.0)

    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=binding.scale_fingerprint),
        entity=_entity(wall, document),
        evidence_atoms=atoms,
        equivalence=_fake_solo_equivalence("w1"),  # attack: structurally plausible forgery
        page_no=1,
        scale_bindings=(binding,),
    )

    assert qty.abstained is True
    assert "physical_equivalence_authenticity_unproven" in qty.blocking_reasons


def test_c5_hidden_wall_candidate_cannot_make_supplied_subset_look_complete() -> None:
    admitted_wall = _wall("w1", y=0.0)
    hidden_competitor = _wall("w2", y=2.0)
    assert hidden_competitor.candidate_id != admitted_wall.candidate_id

    atoms = _atoms("w1")
    document = _document(tuple(atom.evidence_id for atom in atoms))
    binding = _binding(100.0)
    identity = _identity(admitted_wall)
    assert identity.usable

    out = build_wall_length_quantities(
        walls=(admitted_wall,),  # attack: w2 omitted before reconciliation
        entities_by_wall_id={"w1": _entity(admitted_wall, document)},
        evidence_atoms=atoms,
        physical_identities={"w1": identity},
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=binding.scale_fingerprint),
        page_no=1,
        scale_bindings=(binding,),
    )

    assert len(out) == 1
    assert out[0].abstained is True
    assert "physical_candidate_universe_completeness_unproven" in out[0].blocking_reasons
