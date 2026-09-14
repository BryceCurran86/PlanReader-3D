from __future__ import annotations

import math

from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import ScaleSourceReading, ScaleSourceType, resolve_page_scale_calibration
from pb_physical_wall_existence_authority import adapt_wall_candidate_to_entity_evidence
from pb_wall_length_quantity import build_wall_length_quantities, build_wall_length_quantity
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
    wall_id="w1",
    points=((0.0, 0.0), (100.0, 0.0)),
    face_ids=("seg-1",),
    *,
    supporting=("u2-ev", "pair-ev"),
    status=EvidenceResolutionStatus.CANDIDATE,
    thickness_authority=MeasurementAuthorityType.PROVISIONAL,
    thickness_m=None,
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id="vp",
        representation="single_line",
        centerline_pts=tuple(points),
        face_a_segment_ids=tuple(face_ids),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=thickness_authority,
        length_m=None,
        end_node_ids=(f"{wall_id}-n1", f"{wall_id}-n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id="L1",
        status=status,
        confidence=1.0,
        supporting_evidence_ids=supporting,
    )


def _atoms() -> tuple[EvidenceAtom, EvidenceAtom]:
    return (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES),
    )


def _scale(ratio=100.0, revision="R1"):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label="A101",
        readings=[ScaleSourceReading(ScaleSourceType.SCALE_BAR.value, f"1:{ratio:g}", ratio, 1.0)],
        revision_id=revision,
    )


def _figured(text="5000") -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id="dim-ev",
        document_id="doc",
        page_id="page-1",
        viewport_id="vp",
        kind="figured_dimension",
        method="vector_text",
        raw_text=text,
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def _bind(wall: WallCandidate, extra: tuple[str, ...] = ()):
    atoms = _atoms()
    ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *wall.conflicting_evidence_ids, *extra)))
    document = _document(ids)
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=atoms,
        document=document,
        viewport=_viewport(),
        context=_context(),
        additional_owned_evidence_ids=extra,
    )
    assert entity is not None
    return entity, document, atoms


def _qty_kwargs(wall: WallCandidate, extra: tuple[str, ...] = (), **overrides):
    entity, document, _ = _bind(wall, extra=extra)
    kwargs = dict(
        wall=wall,
        context=_context(),
        document=document,
        viewport=_viewport(),
        entity=entity,
        page_no=1,
        scale_calibration=_scale(),
    )
    kwargs.update(overrides)
    return kwargs


def test_scaled_wall_length_emits_firm_quantity() -> None:
    scale = _scale()
    wall = _wall(points=((0.0, 0.0), (scale.px_per_m * 5.0, 0.0)))
    qty = build_wall_length_quantity(**_qty_kwargs(wall, scale_calibration=scale))
    assert qty.abstained is False
    assert math.isclose(qty.value or 0.0, 5.0, abs_tol=1e-6)
    assert qty.family == "wall_length"
    assert qty.semantic_key == "wall_length:w1"
    assert qty.metadata["source_sha256"] == SHA
    assert qty.metadata["viewport_id"] == "vp"
    assert qty.metadata["thickness_authority"] == MeasurementAuthorityType.PROVISIONAL.value
    assert qty.metadata["thickness_m"] is None
    assert qty.metadata["wall_status"] == EvidenceResolutionStatus.CANDIDATE.value
    assert qty.metadata["entity_status"] == EvidenceResolutionStatus.CORROBORATED.value


def test_translation_is_metamorphically_invariant() -> None:
    scale = _scale()
    length = scale.px_per_m * 7.25
    a = _wall(points=((0.0, 0.0), (length, 0.0)))
    b = _wall(points=((500.0, -200.0), (500.0 + length, -200.0)))
    assert build_wall_length_quantity(**_qty_kwargs(a, scale_calibration=scale)).value == 7.25
    assert build_wall_length_quantity(**_qty_kwargs(b, scale_calibration=scale)).value == 7.25


def test_rotation_is_metamorphically_invariant() -> None:
    scale = _scale()
    length = scale.px_per_m * 3.0
    horizontal = _wall(points=((0.0, 0.0), (length, 0.0)))
    vertical = _wall(points=((0.0, 0.0), (0.0, length)))
    assert build_wall_length_quantity(**_qty_kwargs(horizontal, scale_calibration=scale)).value == 3.0
    assert build_wall_length_quantity(**_qty_kwargs(vertical, scale_calibration=scale)).value == 3.0


def test_figured_dimension_is_authoritative_when_scale_absent() -> None:
    wall = _wall()
    qty = build_wall_length_quantity(
        **_qty_kwargs(
            wall,
            extra=("dim-ev",),
            scale_calibration=None,
            figured_evidence=_figured("5000"),
        )
    )
    assert qty.abstained is False
    assert qty.value == 5.0
    assert qty.authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value


def test_untrusted_physical_existence_abstains() -> None:
    wall = _wall(supporting=("u2-ev",))
    qty = build_wall_length_quantity(**_qty_kwargs(wall))
    assert qty.abstained
    assert "physical_wall_existence_not_corroborated" in qty.blocking_reasons


def test_duplicate_candidate_identity_fails_closed() -> None:
    walls = (_wall("w1", face_ids=("seg-1",)), _wall("w1", face_ids=("seg-2",)))
    entity, document, _ = _bind(walls[0])
    out = build_wall_length_quantities(
        walls=walls,
        entities_by_wall_id={"w1": entity},
        context=_context(),
        document=document,
        viewport=_viewport(),
        page_no=1,
        scale_calibration=_scale(),
    )
    assert len(out) == 2
    assert all(q.abstained for q in out)
    assert all("duplicate_wall_identity" in q.blocking_reasons for q in out)


def test_overlapping_source_segments_fail_closed_instead_of_double_counting() -> None:
    w1 = _wall("w1", face_ids=("shared-seg",))
    w2 = _wall("w2", points=((0.0, 10.0), (100.0, 10.0)), face_ids=("shared-seg",))
    e1, document, _ = _bind(w1)
    e2, _, _ = _bind(w2)
    out = build_wall_length_quantities(
        walls=(w1, w2),
        entities_by_wall_id={"w1": e1, "w2": e2},
        context=_context(),
        document=document,
        viewport=_viewport(),
        page_no=1,
        scale_calibration=_scale(),
    )
    assert len(out) == 2
    assert all(q.abstained for q in out)
    assert all("overlapping_wall_source_segments" in q.blocking_reasons for q in out)


def test_stale_scale_causes_abstention_not_old_length_reuse() -> None:
    scale = _scale(revision="R0")
    wall = _wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
    qty = build_wall_length_quantity(**_qty_kwargs(wall, scale_calibration=scale))
    assert qty.abstained
    assert "scale_not_firm" in qty.blocking_reasons
