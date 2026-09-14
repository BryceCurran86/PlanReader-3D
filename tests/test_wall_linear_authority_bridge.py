"""Adversarial tests for the wall-linear authority bridge.

Existence, measurable baseline geometry, and scale/dimension authority are
separate. Thickness may remain PROVISIONAL. Metadata strings are not authority.
Quantity tests go through adapt_wall_candidate_to_entity_evidence.
"""
from __future__ import annotations

import ast
import math
from dataclasses import replace
from pathlib import Path

import pytest

from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_PAIRED_WALL_FACES,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import ScaleSourceReading, ScaleSourceType, resolve_page_scale_calibration
from pb_physical_wall_existence_authority import (
    PHYSICAL_WALL_EXISTENCE_KIND,
    adapt_wall_candidate_to_entity_evidence,
    resolve_physical_wall_existence,
    wall_physical_existence_status,
)
from pb_wall_length_quantity import build_wall_length_quantities, build_wall_length_quantity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

SHA = "c" * 64
REPO = Path(__file__).resolve().parents[1]


def _context(**overrides) -> ProviderContext:
    kwargs = dict(
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
    kwargs.update(overrides)
    return ProviderContext(**kwargs)


def _document(ids: tuple[str, ...], *, document_id: str = "doc", source_sha256: str = SHA) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=document_id,
        source_sha256=source_sha256,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(*, viewport_id: str = "vp", document_id: str = "doc") -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id=document_id,
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
    *,
    wall_id: str = "w1",
    points=((0.0, 0.0), (100.0, 0.0)),
    face_ids=("seg-1",),
    supporting: tuple[str, ...] = (),
    conflicting: tuple[str, ...] = (),
    viewport_id: str = "vp",
    metadata: dict | None = None,
    thickness_m=None,
    thickness_authority=MeasurementAuthorityType.PROVISIONAL,
    length_m=None,
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
        thickness_m=thickness_m,
        thickness_authority=thickness_authority,
        length_m=length_m,
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


def _scale(ratio: float = 100.0, revision: str = "R1", page_no: int = 1):
    return resolve_page_scale_calibration(
        page_no=page_no,
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


def _adapt(wall: WallCandidate, atoms: tuple[EvidenceAtom, ...], *, extra: tuple[str, ...] = (), context=None, document=None, viewport=None):
    context = context or _context()
    viewport = viewport or _viewport()
    ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *wall.conflicting_evidence_ids, *(a.evidence_id for a in atoms), *extra)))
    document = document or _document(ids)
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=atoms,
        document=document,
        viewport=viewport,
        context=context,
        additional_owned_evidence_ids=extra,
    )
    return entity, document, viewport, context


def _qty(wall, atoms, *, extra=(), **overrides):
    entity, document, viewport, context = _adapt(wall, atoms, extra=extra)
    kwargs = dict(
        wall=wall,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=_scale(),
    )
    kwargs.update(overrides)
    if "entity" in overrides and overrides["entity"] is None:
        raise AssertionError("quantity builder must not be called with a missing adapter result")
    if kwargs["entity"] is None:
        return None
    return build_wall_length_quantity(**kwargs)


def test_trusted_wall_and_firm_scale_publish_linear_quantity() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
    assert wall_physical_existence_status(
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport()
    ) == EvidenceResolutionStatus.CORROBORATED
    entity, document, viewport, context = _adapt(wall, atoms)
    assert entity is not None
    assert entity.candidate_entity_id == wall.candidate_id
    assert entity.status == EvidenceResolutionStatus.CORROBORATED
    assert wall.status == EvidenceResolutionStatus.CANDIDATE
    assert wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL
    assert wall.thickness_m is None
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained is False
    assert qty.status == AuthorityStatus.FIRM.value
    assert math.isclose(qty.value or 0.0, 4.0, abs_tol=1e-6)
    assert qty.metadata["thickness_authority"] == MeasurementAuthorityType.PROVISIONAL.value
    assert qty.metadata["thickness_m"] is None
    assert qty.metadata["entity_status"] == EvidenceResolutionStatus.CORROBORATED.value


def test_trusted_wall_unknown_scale_abstains() -> None:
    wall, atoms = _two_domain_wall()
    qty = _qty(wall, atoms, scale_calibration=None)
    assert qty is not None
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
    assert wall_physical_existence_status(
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport()
    ) != EvidenceResolutionStatus.CORROBORATED
    qty = _qty(wall, atoms, scale_calibration=scale)
    assert qty is not None
    assert qty.abstained
    assert "physical_wall_existence_not_corroborated" in qty.blocking_reasons


def test_existence_conflict_abstains() -> None:
    scale = _scale()
    opposing = _source_atom("opp-ev", "glazing")
    wall, atoms = _two_domain_wall(
        points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)),
        conflicting=("opp-ev",),
    )
    qty = _qty(wall, atoms + (opposing,), scale_calibration=scale)
    assert qty is not None
    assert qty.abstained
    assert "physical_wall_existence_conflict" in qty.blocking_reasons
    assert "physical_wall_conflict_evidence_present" in qty.blocking_reasons


def test_existence_abstained_without_provenance_returns_no_entity() -> None:
    wall = _wall(supporting=())
    entity, _, _, _ = _adapt(wall, ())
    assert entity is None
    assert wall_physical_existence_status(
        wall, evidence_atoms=(), document=_document(()), viewport=_viewport()
    ) == EvidenceResolutionStatus.ABSTAINED


def test_existence_abstained_unmapped_kind_abstains_quantity() -> None:
    wall = _wall(supporting=("noise-ev",))
    noise = _source_atom("noise-ev", "title_block_noise")
    entity, document, viewport, context = _adapt(wall, (noise,))
    assert entity is not None
    assert entity.status == EvidenceResolutionStatus.ABSTAINED
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=_scale(),
    )
    assert qty.abstained
    assert "physical_wall_existence_abstained" in qty.blocking_reasons


def test_metadata_physical_evidence_status_is_not_authority() -> None:
    wall = _wall(
        supporting=(),
        metadata={"physical_evidence_status": "corroborated"},
    )
    entity, _, _, _ = _adapt(wall, ())
    assert entity is None
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
    entity, _, _, _ = _adapt(wall, atoms)
    assert entity is not None
    assert entity.status == EvidenceResolutionStatus.CANDIDATE
    assert wall_physical_existence_status(
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "layer-ev")), viewport=_viewport()
    ) == EvidenceResolutionStatus.CANDIDATE


def test_plural_lineage_replay_is_deterministic() -> None:
    wall, atoms = _two_domain_wall(face_ids=("seg-a", "seg-b"))
    first, _, _, _ = _adapt(wall, atoms)
    second, _, _, _ = _adapt(wall, tuple(reversed(atoms)))
    assert first is not None and second is not None
    assert first.candidate_entity_id == second.candidate_entity_id == "w1"
    assert first.status == second.status == EvidenceResolutionStatus.CORROBORATED
    assert first.evidence_ids == second.evidence_ids


def test_reverse_and_rechunk_keep_length() -> None:
    scale = _scale()
    length = scale.px_per_m * 6.0
    forward, atoms = _two_domain_wall(points=((0.0, 0.0), (length, 0.0)))
    reversed_wall, _ = _two_domain_wall(points=((length, 0.0), (0.0, 0.0)))
    rechunked, _ = _two_domain_wall(points=((0.0, 0.0), (length / 2.0, 0.0), (length, 0.0)))
    values = []
    for wall in (forward, reversed_wall, rechunked):
        qty = _qty(wall, atoms, scale_calibration=scale)
        assert qty is not None and qty.abstained is False
        values.append(qty.value)
    assert values[0] == values[1] == values[2] == 6.0


def test_viewport_isolation_adapter_abstains_on_mismatch() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)), viewport_id="other-vp")
    entity, _, _, _ = _adapt(wall, atoms)
    assert entity is None


def test_wrong_document_adapter_abstains() -> None:
    wall, atoms = _two_domain_wall()
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=atoms,
        document=_document(("u2-ev", "pair-ev"), document_id="other-doc"),
        viewport=_viewport(document_id="other-doc"),
        context=_context(),
    )
    assert entity is None


def test_wrong_document_on_quantity_abstains() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    entity, document, viewport, context = _adapt(wall, atoms)
    assert entity is not None
    other = DocumentEvidence(
        document_id="other-doc",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=document.evidence_ids,
    )
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=other,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "physical_wall_existence_document_mismatch" in qty.blocking_reasons


def test_wrong_source_sha_adapter_abstains() -> None:
    wall, atoms = _two_domain_wall()
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=atoms,
        document=_document(("u2-ev", "pair-ev"), source_sha256="d" * 64),
        viewport=_viewport(),
        context=_context(),
    )
    assert entity is None


def test_stale_revision_abstains_at_measurement() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    stale = _context(revision_id="R0", current_revision_id="R1")
    entity, document, viewport, _ = _adapt(wall, atoms, context=stale)
    assert entity is not None
    qty = build_wall_length_quantity(
        wall=wall,
        context=stale,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "stale_revision" in qty.blocking_reasons


def test_entity_for_other_wall_cannot_authorize_length() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    other = _wall(wall_id="w2", supporting=("u2-ev", "pair-ev"))
    entity, document, viewport, context = _adapt(other, atoms)
    assert entity is not None
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "wall_entity_identity_mismatch" in qty.blocking_reasons


def test_zero_length_centerline_abstains() -> None:
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (0.0, 0.0)))
    qty = _qty(wall, atoms)
    assert qty is not None
    assert qty.abstained
    assert "wall_centerline_length_invalid" in qty.blocking_reasons


def test_nan_and_inf_geometry_rejected_at_wall_construction() -> None:
    with pytest.raises(ValueError, match="finite"):
        _wall(points=((float("nan"), 0.0), (100.0, 0.0)))
    with pytest.raises(ValueError, match="finite"):
        _wall(points=((0.0, 0.0), (float("inf"), 0.0)))


def test_thickness_change_alone_does_not_alter_length() -> None:
    scale = _scale()
    length = scale.px_per_m * 2.5
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (length, 0.0)))
    thicker = replace(
        wall,
        thickness_m=0.2,
        thickness_authority=MeasurementAuthorityType.USER_APPROVED,
    )
    a = _qty(wall, atoms, scale_calibration=scale)
    b = _qty(thicker, atoms, scale_calibration=scale)
    assert a is not None and b is not None
    assert a.abstained is False and b.abstained is False
    assert a.value == b.value == 2.5
    assert a.metadata["thickness_m"] is None
    assert b.metadata["thickness_m"] == 0.2


def test_height_or_stored_length_alone_does_not_alter_length() -> None:
    scale = _scale()
    length = scale.px_per_m * 2.5
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (length, 0.0)))
    with_height = replace(wall, length_m=99.0, metadata={"documented_height_m": 2.8, "height_m": 2.8})
    a = _qty(wall, atoms, scale_calibration=scale)
    b = _qty(with_height, atoms, scale_calibration=scale)
    assert a is not None and b is not None
    assert a.value == b.value == 2.5
    assert "height" not in (a.formula or "")


def test_shuffled_batch_is_deterministic() -> None:
    scale = _scale()
    length = scale.px_per_m * 3.0
    w1, atoms = _two_domain_wall(wall_id="w1", points=((0.0, 0.0), (length, 0.0)), face_ids=("seg-1",))
    w2, _ = _two_domain_wall(wall_id="w2", points=((0.0, 10.0), (length, 10.0)), face_ids=("seg-2",))
    e1, document, viewport, context = _adapt(w1, atoms)
    e2, _, _, _ = _adapt(w2, atoms)
    assert e1 is not None and e2 is not None
    entities = {"w1": e1, "w2": e2}
    forward = build_wall_length_quantities(
        walls=(w1, w2),
        entities_by_wall_id=entities,
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        scale_calibration=scale,
    )
    reverse = build_wall_length_quantities(
        walls=(w2, w1),
        entities_by_wall_id=entities,
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        scale_calibration=scale,
    )
    by_id_fwd = {q.semantic_key: q.value for q in forward}
    by_id_rev = {q.semantic_key: q.value for q in reverse}
    assert by_id_fwd == by_id_rev == {"wall_length:w1": 3.0, "wall_length:w2": 3.0}


def test_same_wall_cannot_double_count() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    clone = replace(wall, candidate_id="w1-dup", face_a_segment_ids=wall.face_a_segment_ids)
    entity, document, viewport, context = _adapt(wall, atoms)
    clone_entity = replace(entity, candidate_entity_id="w1-dup")
    out = build_wall_length_quantities(
        walls=(wall, clone),
        entities_by_wall_id={"w1": entity, "w1-dup": clone_entity},
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        scale_calibration=scale,
    )
    assert all(q.abstained for q in out)
    assert all("overlapping_wall_source_segments" in q.blocking_reasons for q in out)


def test_scale_from_another_page_cannot_leak() -> None:
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (300.0, 0.0)))
    qty = _qty(wall, atoms, scale_calibration=_scale(page_no=2))
    assert qty is not None
    assert qty.abstained
    assert "scale_page_mismatch" in qty.blocking_reasons


def test_unbound_scale_cannot_leak_across_viewports_on_same_page() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    multi = _context(
        owned_viewport_ids=("vp", "vp-other"),
        viewport_page_ownership=(("vp", 1), ("vp-other", 1)),
    )
    entity, document, viewport, _ = _adapt(wall, atoms, context=multi)
    assert entity is not None
    qty = build_wall_length_quantity(
        wall=wall,
        context=multi,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scale_calibration=scale,
    )
    assert qty.abstained
    assert "scale_not_bound_to_multi_viewport" in qty.blocking_reasons


def test_provisional_thickness_does_not_block_length_and_is_not_invented() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 2.5, 0.0)))
    qty = _qty(wall, atoms, scale_calibration=scale)
    assert qty is not None
    assert qty.abstained is False
    assert wall.thickness_m is None
    assert wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL
    assert "height" not in qty.formula
    assert qty.unit == "m"
    assert qty.value != 0.15


def _imported_top_level(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_no_live_commercial_publisher_imports_the_bridge() -> None:
    forbidden = {"pb_wall_length_quantity", "pb_physical_wall_existence_authority"}
    publishers = (
        "pb_planreader_pdf_extractor.py",
        "pb_quantity_takeoff_adapter.py",
        "pb_jobhub_publishing_pipeline.py",
        "pb_quantity_commercial_adapter.py",
    )
    for name in publishers:
        imported = _imported_top_level(REPO / name)
        assert imported.isdisjoint(forbidden), f"{name} imports {imported & forbidden}"
