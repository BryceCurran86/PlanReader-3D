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
from pb_measurement_input_authority import scale_calibration_fingerprint
from pb_page_scale_calibration_authority import (
    ScaleSourceReading,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    resolve_page_scale_calibration,
)
from pb_viewport_scale_binding import ViewportScaleBinding
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


def _viewport(*, viewport_id: str = "vp", document_id: str = "doc", resolved_scale_id=None) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id=document_id,
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-ev",),
        resolved_scale_id=resolved_scale_id,
        confidence=1.0,
    )


def _source_atom(evidence_id: str, kind: str, wall_id: str = "w1", viewport_id: str = "vp") -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="page-1",
        viewport_id=viewport_id,
        kind=kind,
        method="test",
        confidence=0.7,
        status=EvidenceResolutionStatus.CANDIDATE,
        metadata={
            "wall_candidate_id": wall_id,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap",
            "source_sha256": SHA,
        },
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
    wall_id = kwargs.get("wall_id", "w1")
    viewport_id = kwargs.get("viewport_id", "vp")
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL, wall_id, viewport_id),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES, wall_id, viewport_id),
    )
    wall = _wall(supporting=("u2-ev", "pair-ev"), **kwargs)
    return wall, atoms


def _scale_binding(scale, *, viewport_id="vp"):
    fingerprint = scale_calibration_fingerprint(scale)
    authority = measurement_authority_for_page_scale(scale)
    return ViewportScaleBinding(
        viewport_id=viewport_id,
        page_no=scale.page_no,
        source_sha256=SHA,
        revision_id=scale.revision_id,
        calibration=scale,
        scale_fingerprint=fingerprint,
        measurement_authority=authority,
        blocking_reasons=() if authority == AuthorityStatus.FIRM.value else ("scale_not_firm",),
    )


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


def _solo_equivalence(*wall_ids: str):
    from pb_physical_wall_identity import PhysicalWallEquivalenceResolution

    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="vp",
        representative_wall_ids=tuple(wall_ids),
        abstained_wall_ids=(),
        equivalence_groups=(),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


def _qty(wall, atoms, *, extra=(), extra_atoms=(), scale=None, scale_bindings=None, bind_scale=True, **overrides):
    all_atoms = tuple(atoms) + tuple(extra_atoms)
    extra_ids = extra + tuple(atom.evidence_id for atom in extra_atoms)
    entity, document, viewport, context = _adapt(wall, all_atoms, extra=extra_ids)
    if scale_bindings is None and bind_scale and "scale_bindings" not in overrides:
        used_scale = scale if scale is not None else _scale()
        scale_bindings = (_scale_binding(used_scale, viewport_id=wall.viewport_id),)
    if scale_bindings and bind_scale:
        viewport = replace(viewport, resolved_scale_id=scale_bindings[0].scale_fingerprint)
    kwargs = dict(
        wall=wall,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        evidence_atoms=all_atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=scale_bindings or (),
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
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport(), context=_context()
    ) == EvidenceResolutionStatus.CORROBORATED
    entity, document, viewport, context = _adapt(wall, atoms)
    assert entity is not None
    assert entity.candidate_entity_id == wall.candidate_id
    assert entity.status == EvidenceResolutionStatus.CORROBORATED
    assert wall.status == EvidenceResolutionStatus.CANDIDATE
    assert wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL
    assert wall.thickness_m is None
    binding = _scale_binding(scale)
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=document,
        viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
        entity=entity,
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(binding,),
    )
    assert qty.abstained is False
    assert qty.status == AuthorityStatus.FIRM.value
    assert math.isclose(qty.value or 0.0, 4.0, abs_tol=1e-6)
    assert qty.metadata["thickness_authority"] == MeasurementAuthorityType.PROVISIONAL.value
    assert qty.metadata["thickness_m"] is None
    assert qty.metadata["entity_status"] == EvidenceResolutionStatus.CORROBORATED.value


def test_trusted_wall_unknown_scale_abstains() -> None:
    wall, atoms = _two_domain_wall()
    qty = _qty(wall, atoms, scale_bindings=(), bind_scale=False)
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
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport(), context=_context()
    ) != EvidenceResolutionStatus.CORROBORATED
    qty = _qty(wall, atoms, scale=scale)
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
    qty = _qty(wall, atoms + (opposing,), scale=scale)
    assert qty is not None
    assert qty.abstained
    assert "physical_wall_existence_conflict" in qty.blocking_reasons
    assert "physical_wall_conflict_evidence_present" in qty.blocking_reasons


def test_existence_abstained_without_provenance_returns_no_entity() -> None:
    wall = _wall(supporting=())
    entity, _, _, _ = _adapt(wall, ())
    assert entity is None
    assert wall_physical_existence_status(
        wall, evidence_atoms=(), document=_document(()), viewport=_viewport(), context=_context()
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
        evidence_atoms=(noise,),
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(_scale_binding(_scale()),),
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
        context=_context(),
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
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "layer-ev")), viewport=_viewport(), context=_context()
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
        qty = _qty(wall, atoms, scale=scale)
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
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(_scale_binding(scale),),
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
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(_scale_binding(scale),),
    )
    assert qty.abstained
    assert (
        "stale_revision" in qty.blocking_reasons
        or "existence_context_revision_stale" in qty.blocking_reasons
        or "physical_wall_existence_abstained" in qty.blocking_reasons
    )

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
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(_scale_binding(scale),),
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
    a = _qty(wall, atoms, scale=scale)
    b = _qty(thicker, atoms, scale=scale)
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
    a = _qty(wall, atoms, scale=scale)
    b = _qty(with_height, atoms, scale=scale)
    assert a is not None and b is not None
    assert a.value == b.value == 2.5
    assert "height" not in (a.formula or "")


def test_shuffled_batch_is_deterministic() -> None:
    scale = _scale()
    length = scale.px_per_m * 3.0
    # Wall-scoped literal evidence ids: real production ids are content-hashed
    # (and therefore already wall-specific), so two different walls sharing
    # the bare "u2-ev"/"pair-ev" literal in one pooled evidence_atoms sequence
    # would be a fixture-only collision under collision-safe existence
    # recomputation -- construct genuinely distinct ids per wall instead.
    w1 = _wall(wall_id="w1", points=((0.0, 0.0), (length, 0.0)), face_ids=("seg-1",), supporting=("u2-ev-w1", "pair-ev-w1"))
    w2 = _wall(wall_id="w2", points=((length + 50.0, 0.0), (2 * length + 50.0, 0.0)), face_ids=("seg-2",), supporting=("u2-ev-w2", "pair-ev-w2"))
    a1 = (_source_atom("u2-ev-w1", KIND_PHYSICAL_WALL, "w1"), _source_atom("pair-ev-w1", FAMILY_PAIRED_WALL_FACES, "w1"))
    a2 = (_source_atom("u2-ev-w2", KIND_PHYSICAL_WALL, "w2"), _source_atom("pair-ev-w2", FAMILY_PAIRED_WALL_FACES, "w2"))
    all_atoms = a1 + a2
    e1, document, viewport, context = _adapt(w1, all_atoms)
    e2, _, _, _ = _adapt(w2, all_atoms)
    assert e1 is not None and e2 is not None
    entities = {"w1": e1, "w2": e2}
    binding = _scale_binding(scale)
    bound_viewport = replace(viewport, resolved_scale_id=binding.scale_fingerprint)
    # This test is about batch ordering determinism under the now-mandatory
    # reconciliation boundary. w1/w2 share one native ancestor but occupy
    # proven-disjoint spans along it (pb_physical_wall_identity's own
    # positive-distinctness rule, unchanged by this remediation) so both are
    # legitimately independent DISTINCT representatives -- the property
    # under test is that reconciliation reaches the same conclusion, and
    # both walls the same FIRM value, regardless of batch input order.
    from pb_physical_wall_identity import collect_physical_wall_identities

    graph = {
        "edges": [
            {"id": "seg-1", "x1": 0.0, "y1": 0.0, "x2": length, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_shared"]}},
            {"id": "seg-2", "x1": length + 50.0, "y1": 0.0, "x2": 2 * length + 50.0, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_shared"]}},
        ]
    }
    identities = collect_physical_wall_identities((w1, w2), graph)
    forward = build_wall_length_quantities(
        walls=(w1, w2),
        entities_by_wall_id=entities,
        evidence_atoms=all_atoms,
        physical_identities=identities,
        context=context,
        document=document,
        viewport=bound_viewport,
        page_no=1,
        scale_bindings=(binding,),
    )
    reverse = build_wall_length_quantities(
        walls=(w2, w1),
        entities_by_wall_id=entities,
        evidence_atoms=all_atoms,
        physical_identities=identities,
        context=context,
        document=document,
        viewport=bound_viewport,
        page_no=1,
        scale_bindings=(binding,),
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
        evidence_atoms=atoms,
        physical_identities={},
        context=context,
        document=document,
        viewport=viewport,
        page_no=1,
        scale_bindings=(_scale_binding(scale),),
    )
    assert all(q.abstained for q in out)
    assert all("overlapping_wall_source_segments" in q.blocking_reasons for q in out)


def test_scale_from_another_page_cannot_leak() -> None:
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (300.0, 0.0)))
    qty = _qty(wall, atoms, scale=_scale(page_no=2))
    assert qty is not None
    assert qty.abstained
    assert "scale_binding_page_mismatch" in qty.blocking_reasons


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
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(_scale_binding(scale),),
    )
    assert qty.abstained
    # A binding for only one of the two context-known sibling viewports is now
    # caught earlier, by the scale-binding universe completeness gate (GPT-2
    # #288 blocker 1), before the deeper per-binding fingerprint check would
    # otherwise have caught the same underlying leak.
    assert "incomplete_scale_binding_universe" in qty.blocking_reasons


def test_provisional_thickness_does_not_block_length_and_is_not_invented() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 2.5, 0.0)))
    qty = _qty(wall, atoms, scale=scale)
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
    forbidden = {
        "pb_wall_length_quantity",
        "pb_physical_wall_existence_authority",
        "pb_physical_wall_identity",
    }
    publishers = (
        "pb_planreader_pdf_extractor.py",
        "pb_quantity_takeoff_adapter.py",
        "pb_jobhub_publishing_pipeline.py",
        "pb_quantity_commercial_adapter.py",
    )
    for name in publishers:
        imported = _imported_top_level(REPO / name)
        assert imported.isdisjoint(forbidden), f"{name} imports {imported & forbidden}"


def test_scale_fingerprint_and_binding_import_smoke_has_no_cycle() -> None:
    import pb_measurement_input_authority as mia
    import pb_page_scale_calibration_authority as psa
    import pb_viewport_scale_binding as vsb
    import pb_wall_length_quantity as wlq
    from pb_measurement_input_authority import validate_owned_viewport_scale_binding
    from pb_viewport_scale_binding import ViewportScaleBinding

    assert mia.scale_calibration_fingerprint is psa.scale_calibration_fingerprint
    assert vsb.scale_calibration_fingerprint is psa.scale_calibration_fingerprint
    assert wlq.build_wall_length_quantity is not None
    assert callable(validate_owned_viewport_scale_binding)
    assert ViewportScaleBinding is vsb.ViewportScaleBinding


def _existence(wall, atoms, document=None, viewport=None, context=None):
    document = document or _document(tuple(dict.fromkeys(atom.evidence_id for atom in atoms)))
    viewport = viewport or _viewport()
    context = context or _context()
    return resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=atoms,
        document=document,
        viewport=viewport,
        context=context,
    )


def test_wrong_page_atom_cannot_corroborate_existence() -> None:
    wall, atoms = _two_domain_wall()
    foreign_page = replace(atoms[0], page_id="page-other")
    existence = _existence(wall, (foreign_page, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_page_mismatch" in existence.reason_codes


def test_wrong_viewport_atom_cannot_corroborate_existence() -> None:
    wall, atoms = _two_domain_wall()
    foreign_viewport = replace(atoms[0], viewport_id="vp-other")
    existence = _existence(wall, (foreign_viewport, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_viewport_mismatch" in existence.reason_codes


def test_foreign_document_atom_cannot_corroborate_existence() -> None:
    wall, atoms = _two_domain_wall()
    foreign_doc = replace(atoms[0], document_id="other-doc")
    existence = _existence(wall, (foreign_doc, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_document_mismatch" in existence.reason_codes


def test_atom_targeting_another_wall_cannot_corroborate() -> None:
    wall, atoms = _two_domain_wall()
    foreign_wall = replace(atoms[0], metadata={"wall_candidate_id": "other-wall"})
    existence = _existence(wall, (foreign_wall, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_not_bound_to_wall" in existence.reason_codes


def test_unrestricted_additional_evidence_cannot_become_wall_authority() -> None:
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES),
    )
    wall = _wall(supporting=("u2-ev",))
    noise = _source_atom("noise-ev", KIND_PHYSICAL_WALL, wall_id="other-wall")
    entity, _, _, _ = _adapt(wall, atoms + (noise,), extra=("noise-ev",))
    assert entity is not None
    assert entity.status != EvidenceResolutionStatus.CORROBORATED
    assert "noise-ev" not in entity.evidence_ids


def test_conflicting_duplicate_evidence_ids_block_deterministically() -> None:
    wall, atoms = _two_domain_wall()
    colliding = replace(atoms[0], kind=FAMILY_PAIRED_WALL_FACES, method="other")
    first = _existence(wall, (atoms[0], colliding, atoms[1]))
    shuffled = _existence(wall, (atoms[1], colliding, atoms[0]))
    assert first.status == shuffled.status == EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == shuffled.reason_codes
    assert "existence_evidence_id_collision" in first.reason_codes


def test_identical_duplicate_atoms_do_not_increase_authority() -> None:
    wall = _wall(supporting=("u2-ev", "u2-ev-copy"))
    atom = _source_atom("u2-ev", KIND_PHYSICAL_WALL)
    copy = replace(atom)
    other_same_domain = _source_atom("u2-ev-copy", KIND_PHYSICAL_WALL)
    existence = _existence(wall, (atom, copy, other_same_domain))
    assert existence.status == EvidenceResolutionStatus.CANDIDATE
    shuffled = _existence(wall, (other_same_domain, copy, atom))
    assert shuffled.status == existence.status
    assert shuffled.reason_codes == existence.reason_codes


def test_removing_support_cannot_increase_existence_authority() -> None:
    wall, atoms = _two_domain_wall()
    corroborated = wall_physical_existence_status(
        wall, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport(), context=_context()
    )
    reduced = _wall(supporting=("u2-ev",))
    weaker = wall_physical_existence_status(
        reduced, evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport(), context=_context()
    )
    assert corroborated == EvidenceResolutionStatus.CORROBORATED
    assert weaker != EvidenceResolutionStatus.CORROBORATED


def test_adding_conflict_cannot_leave_firm_length() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)))
    qty = _qty(wall, atoms, scale=scale)
    assert qty is not None and qty.abstained is False
    opposing = _source_atom("opp-ev", "glazing")
    conflicted, _ = _two_domain_wall(
        points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)),
        conflicting=("opp-ev",),
    )
    blocked = _qty(conflicted, atoms + (opposing,), scale=scale)
    assert blocked is not None
    assert blocked.abstained
    assert blocked.status != AuthorityStatus.FIRM.value


def test_unrelated_other_wall_evidence_does_not_change_target() -> None:
    wall, atoms = _two_domain_wall()
    other = _source_atom("other-ev", KIND_PHYSICAL_WALL, wall_id="w2")
    before = _existence(wall, atoms)
    after = _existence(wall, atoms + (other,))
    assert before.status == after.status == EvidenceResolutionStatus.CORROBORATED
    assert before.reason_codes == after.reason_codes


def test_shuffled_source_atoms_do_not_change_existence() -> None:
    wall, atoms = _two_domain_wall()
    forward = _existence(wall, atoms)
    reverse = _existence(wall, tuple(reversed(atoms)))
    assert forward.status == reverse.status
    assert forward.reason_codes == reverse.reason_codes
    assert forward.evidence_id == reverse.evidence_id


def test_stale_revision_atom_cannot_corroborate_existence() -> None:
    wall, atoms = _two_domain_wall()
    stale = replace(
        atoms[0],
        metadata={**dict(atoms[0].metadata), "revision_id": "R0"},
    )
    existence = _existence(wall, (stale, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_revision_stale" in existence.reason_codes


def test_missing_snapshot_metadata_cannot_corroborate_existence() -> None:
    wall, atoms = _two_domain_wall()
    bare = replace(atoms[0], metadata={"wall_candidate_id": "w1"})
    existence = _existence(wall, (bare, atoms[1]))
    assert existence.status != EvidenceResolutionStatus.CORROBORATED
    assert "existence_atom_revision_unproven" in existence.reason_codes
    assert "existence_atom_snapshot_unproven" in existence.reason_codes


def test_bbox_only_evidence_id_collision_blocks() -> None:
    wall, atoms = _two_domain_wall()
    left = replace(atoms[0], bbox=(0.0, 0.0, 10.0, 10.0))
    right = replace(atoms[0], bbox=(1.0, 1.0, 11.0, 11.0))
    existence = _existence(wall, (left, right, atoms[1]))
    assert "existence_evidence_id_collision" in existence.reason_codes
    assert existence.status != EvidenceResolutionStatus.CORROBORATED


def test_confidence_only_evidence_id_collision_blocks() -> None:
    wall, atoms = _two_domain_wall()
    left = replace(atoms[0], confidence=0.7)
    right = replace(atoms[0], confidence=0.8)
    existence = _existence(wall, (left, right, atoms[1]))
    assert "existence_evidence_id_collision" in existence.reason_codes


def test_schema_version_only_evidence_id_collision_blocks() -> None:
    wall, atoms = _two_domain_wall()
    left = replace(atoms[0], schema_version="1.0.0")
    right = replace(atoms[0], schema_version="1.0.1")
    existence = _existence(wall, (left, right, atoms[1]))
    assert "existence_evidence_id_collision" in existence.reason_codes


def test_firm_path_reconciles_complete_binding_set_not_caller_preferred() -> None:
    scale = _scale()
    wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
    preferred = _scale_binding(scale)
    competitor = replace(
        preferred,
        calibration=replace(scale, px_per_m=scale.px_per_m * 2.0),
    )
    # Force competitor eligible by matching fingerprint on viewport for preferred only —
    # both bindings share viewport/page/SHA/revision; only preferred matches resolved_scale_id.
    # Construct a second eligible clone with identical fingerprint via replace.
    twin = replace(preferred)
    entity, document, viewport, context = _adapt(wall, atoms)
    assert entity is not None
    qty = build_wall_length_quantity(
        wall=wall,
        context=context,
        document=document,
        viewport=replace(viewport, resolved_scale_id=preferred.scale_fingerprint),
        entity=entity,
        evidence_atoms=atoms,
        equivalence=_solo_equivalence(wall.candidate_id),
        page_no=1,
        scale_bindings=(preferred, twin),
    )
    assert qty.abstained
    assert "conflicting_eligible_scale_bindings" in qty.blocking_reasons
