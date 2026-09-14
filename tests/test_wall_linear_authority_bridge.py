"""Adversarial tests for the wall-linear authority bridge.

Existence, measurable baseline geometry, and scale/dimension authority are
separate. Thickness may remain PROVISIONAL. Metadata strings are not authority.
"""
from __future__ import annotations

import math

from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_PAIRED_WALL_FACES,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import ScaleSourceReading, ScaleSourceType, resolve_page_scale_calibration
from pb_physical_wall_existence_authority import (
    PHYSICAL_WALL_EXISTENCE_KIND,
    resolve_physical_wall_existence,
)
from pb_wall_length_quantity import build_wall_length_quantity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

SHA = "c" * 64


def _context() -> ProviderContext:
    return ProviderContext(
        run_id="run",
        workspace_id="ws",
        project_id="project",
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=("vp",),
        evidence_snapshot_id="evsnap",
        canonical_graph_snapshot_id="graphsnap",
        measurement_authority_snapshot_id="measuresnap",
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


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp",
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-ev",),
        confidence=1.0,
    )


def _entity(wall_id: str, ids: tuple[str, ...]) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=wall_id,
        candidate_type="wall",
        evidence_ids=ids,
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _source_atom(evidence_id: str, kind: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="page-1",
        viewport_id="vp",
        kind=kind,
        method="test",
        confidence=0.7,
        status=EvidenceResolutionStatus.CANDIDATE,
        metadata={"wall_candidate_id": "w1"},
    )


def _wall(
    *,
    wall_id: str = "w1",
    points=((0.0, 0.0), (100.0, 0.0)),
    face_ids=("seg-1",),
    supporting: tuple[str, ...] = (),
    conflicting: tuple[str, ...] = (),
    viewport_id: str = "vp",
    metadata: dict | None = None,
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id=viewport_id,
        representation="single_line",
        centerline_pts=tuple(points),
        face_a_segment_ids=tuple(face_ids),
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
        confidence=0.4,
        supporting_evidence_ids=supporting,
        conflicting_evidence_ids=conflicting,
        metadata=metadata or {},
    )


def _scale(ratio: float = 100.0, revision: str = "R1"):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="A101",
        readings=[ScaleSourceReading(ScaleSourceType.SCALE_BAR.value, f"1:{ratio:g}", ratio, 1.0)],
        revision_id=revision,
    )


def _two_domain_wall(**kwargs) -> tuple[WallCandidate, tuple[EvidenceAtom, EvidenceAtom]]:
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES),
    )
    wall = _wall(supporting=("u2-ev", "pair-ev"), **kwargs)
    return wall, atoms


def _existence_for(wall: WallCandidate, atoms: tuple[EvidenceAtom, ...]) -> EvidenceAtom:
    return resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=atoms,
        document=_document(tuple(a.evidence_id for a in atoms)),
        viewport=_viewport(),
    )


def test_trusted_wall_and_firm_scale_publish_linear_quantity() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
    existence = _existence_for(wall, atoms)
    assert existence.status == EvidenceResolutionStatus.CORROBORATED
    assert wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL
    assert wall.thickness_m is None
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained is False
    assert qty.status == AuthorityStatus.FIRM.value
    assert math.isclose(qty.value or 0.0, 4.0, abs_tol=1e-6)
    assert qty.metadata["thickness_authority"] == MeasurementAuthorityType.PROVISIONAL.value
    assert qty.metadata["thickness_m"] is None


def test_trusted_wall_unknown_scale_abstains() -> None:
    wall, atoms = _two_domain_wall()
    existence = _existence_for(wall, atoms)
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
        existence_evidence=existence,
        page_no=1,
    )
    assert qty.abstained
    assert qty.value is None


def test_geometry_without_trusted_existence_abstains() -> None:
    scale = _scale()
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES),
    )
    wall = _wall(
        points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)),
        supporting=("u2-ev",),
    )
    existence = _existence_for(wall, atoms)
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "physical_wall_existence_not_corroborated" in qty.blocking_reasons


def test_conflicting_evidence_abstains() -> None:
    scale = _scale()
    opposing = _source_atom("opp-ev", "glazing")
    wall, atoms = _two_domain_wall(
        points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)),
        conflicting=("opp-ev",),
    )
    existence = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=atoms + (opposing,),
        document=_document(("u2-ev", "pair-ev", "opp-ev")),
        viewport=_viewport(),
    )
    assert existence.status == EvidenceResolutionStatus.CONFLICT
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev", "opp-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev", "opp-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "physical_wall_existence_conflict" in qty.blocking_reasons
    assert "physical_wall_conflict_evidence_present" in qty.blocking_reasons


def test_metadata_physical_evidence_status_is_not_authority() -> None:
    wall = _wall(
        supporting=(),
        metadata={"physical_evidence_status": "corroborated"},
    )
    existence = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=(),
        document=_document(()),
        viewport=_viewport(),
    )
    assert existence.status == EvidenceResolutionStatus.ABSTAINED
    assert existence.kind == PHYSICAL_WALL_EXISTENCE_KIND


def test_same_native_metadata_domain_does_not_count_as_two_proofs() -> None:
    wall = _wall(supporting=("u2-ev", "layer-ev"))
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL),
        _source_atom("layer-ev", FAMILY_NATIVE_LAYER_WALL_SUPPORT),
    )
    existence = _existence_for(wall, atoms)
    assert existence.status == EvidenceResolutionStatus.CANDIDATE


def test_plural_lineage_replay_is_deterministic() -> None:
    wall, atoms = _two_domain_wall(face_ids=("seg-a", "seg-b"))
    first = _existence_for(wall, atoms)
    second = _existence_for(wall, tuple(reversed(atoms)))
    assert first.evidence_id == second.evidence_id
    assert first.status == second.status == EvidenceResolutionStatus.CORROBORATED


def test_reverse_and_rechunk_keep_length() -> None:
    scale = _scale()
    length = scale.px_per_m * 6.0
    forward, atoms = _two_domain_wall(points=((0.0, 0.0), (length, 0.0)))
    reversed_wall, _ = _two_domain_wall(points=((length, 0.0), (0.0, 0.0)))
    rechunked, _ = _two_domain_wall(points=((0.0, 0.0), (length / 2.0, 0.0), (length, 0.0)))
    values = []
    for wall in (forward, reversed_wall, rechunked):
        existence = _existence_for(wall, atoms)
        qty = build_wall_length_quantity(
            wall=wall,
            context=_context(),
            document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
            viewport=_viewport(),
            entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
            existence_evidence=existence,
            page_no=1,
            scale_calibration=scale,
        )
        values.append(qty.value)
    assert values[0] == values[1] == values[2] == 6.0


def test_viewport_isolation_abstains_on_mismatch() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)), viewport_id="other-vp")
    existence = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=atoms,
        document=_document(("u2-ev", "pair-ev")),
        viewport=_viewport(),
    )
    assert existence.status == EvidenceResolutionStatus.ABSTAINED
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "wall_viewport_mismatch" in qty.blocking_reasons


def test_existence_atom_for_other_wall_cannot_authorize_length() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    other = _wall(wall_id="w2", supporting=("u2-ev", "pair-ev"))
    existence = _existence_for(other, atoms)
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "physical_wall_existence_wall_mismatch" in qty.blocking_reasons


def test_provisional_thickness_does_not_block_length_and_is_not_invented() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 2.5, 0.0)))
    existence = _existence_for(wall, atoms)
    qty = build_wall_length_quantity(
        wall=wall,
        context=_context(),
        document=_document((existence.evidence_id, "u2-ev", "pair-ev")),
        viewport=_viewport(),
        entity=_entity("w1", (existence.evidence_id, "u2-ev", "pair-ev")),
        existence_evidence=existence,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained is False
    assert wall.thickness_m is None
    assert wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL
    assert "height" not in qty.formula
    assert qty.unit == "m"
    assert qty.value != 0.15  # no default 150mm thickness leaked into metres
