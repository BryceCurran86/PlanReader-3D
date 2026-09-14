"""Adversarial regressions for the wall-length authority boundary.

The completeness remediation intentionally makes public FIRM publication
unavailable until a real content-addressed upstream snapshot producer exists.
Tests whose subject is scale, existence, figured dimensions, or physical
identity therefore exercise those lower-level authorities directly. Public
quantity tests assert the new fail-closed boundary rather than manufacturing a
synthetic authoritative universe.
"""
from __future__ import annotations

from dataclasses import replace

from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import (
    resolve_linear_measurement_input,
    scale_calibration_fingerprint,
)
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
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
from pb_physical_wall_existence_authority import (
    adapt_wall_candidate_to_entity_evidence,
    resolve_physical_wall_existence,
)
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    classify_physical_wall_pair,
    resolve_physical_wall_equivalence,
    resolve_physical_wall_identity,
)
from pb_viewport_scale_binding import ViewportScaleBinding
from pb_viewport_segmentation import SegmentedViewport, ViewportSegmentationStatus
from pb_wall_length_quantity import (
    FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON,
    _downgrade_figured_dimension_result,
    _scale_bindings_from_page_viewports,
    build_wall_length_quantities,
    build_wall_length_quantity,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

SHA = "c" * 64


def _solo_equivalence(*wall_ids: str) -> PhysicalWallEquivalenceResolution:
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


def _segmented_viewport(
    *, view_id: str = "vp", page_number: int = 1, scale_raw: str = "1:100", label: str = "A101"
) -> SegmentedViewport:
    return SegmentedViewport(
        view_id=view_id,
        page_number=page_number,
        view_type="floor_plan",
        label=label,
        title_bbox=(0.0, 0.0, 50.0, 12.0),
        bounding_box=(0.0, 0.0, 1000.0, 1000.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source="vector_frame",
        confidence=1.0,
        scale_raw=scale_raw,
    )


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


def _document(ids: tuple[str, ...], *, document_id: str = "doc") -> DocumentEvidence:
    return DocumentEvidence(
        document_id=document_id,
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(*, viewport_id: str = "vp", resolved_scale_id=None) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
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
    viewport_id: str = "vp",
    level_id: str = "L1",
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
        level_id=level_id,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.9,
        supporting_evidence_ids=supporting,
    )


def _two_domain_wall(**kwargs):
    wall_id = kwargs.get("wall_id", "w1")
    viewport_id = kwargs.get("viewport_id", "vp")
    atoms = (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL, wall_id, viewport_id),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES, wall_id, viewport_id),
    )
    wall = _wall(supporting=("u2-ev", "pair-ev"), **kwargs)
    return wall, atoms


def _scale(ratio: float = 100.0, revision: str = "R1", page_no: int = 1):
    return resolve_page_scale_calibration(
        page_no=page_no,
        sheet_label="A101",
        readings=[ScaleSourceReading(ScaleSourceType.SCALE_BAR.value, f"1:{ratio:g}", ratio, 1.0)],
        revision_id=revision,
    )


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


def _adapt(wall, atoms, *, extra=(), context=None, document=None, viewport=None):
    context = context or _context()
    viewport = viewport or _viewport()
    ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *(a.evidence_id for a in atoms), *extra)))
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


def _scaled_resolution(wall, atoms, scale, *, bindings=None, context=None, viewport=None):
    entity, document, base_viewport, base_context = _adapt(
        wall,
        atoms,
        context=context,
        viewport=viewport,
    )
    assert entity is not None
    binding = _scale_binding(scale)
    selected_bindings = tuple(bindings) if bindings is not None else (binding,)
    bound_viewport = replace(
        base_viewport,
        resolved_scale_id=binding.scale_fingerprint,
    )
    length = sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(wall.centerline_pts, wall.centerline_pts[1:])
    )
    return resolve_linear_measurement_input(
        context=base_context,
        document=document,
        viewport=bound_viewport,
        entity=entity,
        page_no=1,
        scaled_length_page_units=length,
        scale_bindings=selected_bindings,
        wall_viewport_id=wall.viewport_id,
    )


class TestBlockerRegressions:
    def test_blocker1_sibling_viewport_binding_omission_blocks_publication(self) -> None:
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        multi = _context(
            owned_viewport_ids=("vp", "vp-sibling"),
            viewport_page_ownership=(("vp", 1), ("vp-sibling", 1)),
        )
        entity, document, viewport, context = _adapt(wall, atoms, context=multi)
        assert entity is not None
        preferred = _scale_binding(scale)
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=preferred.scale_fingerprint),
            entity=entity,
            evidence_atoms=atoms,
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            scale_bindings=(preferred,),
        )
        assert qty.abstained
        assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
        assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons

    def test_blocker1_page_viewports_derivation_is_fail_closed_and_duplicate_safe(self) -> None:
        wall, atoms = _two_domain_wall()
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        derived, reasons = _scale_bindings_from_page_viewports(
            (_segmented_viewport(view_id="vp", scale_raw="1:100"),),
            page_no=1,
            context=context,
            document=document,
        )
        assert reasons == ()
        assert derived is not None and len(derived) == 1
        assert derived[0].viewport_id == viewport.viewport_id
        assert "scale_not_firm" in derived[0].blocking_reasons

        duplicated, duplicate_reasons = _scale_bindings_from_page_viewports(
            (
                _segmented_viewport(view_id="vp", scale_raw="1:100"),
                _segmented_viewport(view_id="vp", scale_raw="1:50"),
            ),
            page_no=1,
            context=context,
            document=document,
        )
        assert duplicated is None
        assert duplicate_reasons == ("duplicate_segmented_viewport_id_in_page_viewports",)

    def test_blocker2_hand_built_entity_evidence_cannot_authorize_publication(self) -> None:
        scale = _scale()
        wall = _wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        document = _document(("forged-ev",))
        viewport = _viewport()
        context = _context()
        forged_entity = EntityEvidence(
            candidate_entity_id=wall.candidate_id,
            candidate_type="wall",
            evidence_ids=("forged-ev",),
            status=EvidenceResolutionStatus.CORROBORATED,
            confidence=1.0,
        )
        binding = _scale_binding(scale)
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
            entity=forged_entity,
            evidence_atoms=(),
            equivalence=_solo_equivalence(wall.candidate_id),
            page_no=1,
            scale_bindings=(binding,),
        )
        assert qty.abstained
        assert "entity_status_does_not_match_recomputed_existence" in qty.blocking_reasons

    def test_blocker3_publication_boundary_receives_raw_evidence_atoms(self) -> None:
        import inspect

        assert "evidence_atoms" in inspect.signature(build_wall_length_quantity).parameters

    def test_blocker4_bare_level_id_string_alone_does_not_prove_distinct(self) -> None:
        left = _wall(wall_id="w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), level_id="L1")
        right = _wall(wall_id="w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e2",), level_id="L2")
        edges = {
            "e1": {"id": "e1", "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_a"]}},
            "e2": {"id": "e2", "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_b"]}},
        }
        identities = (
            resolve_physical_wall_identity(wall=left, edge_ids=("e1",), edges_by_id=edges),
            resolve_physical_wall_identity(wall=right, edge_ids=("e2",), edges_by_id=edges),
        )
        assert classify_physical_wall_pair(*identities) != PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS

    def test_blocker4_bare_viewport_id_string_alone_does_not_prove_distinct(self) -> None:
        edges = {"e1": {"id": "e1", "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native"]}}}
        a = _wall(wall_id="w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), viewport_id="vp")
        b = _wall(wall_id="w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), viewport_id="vp-other")
        identities = (
            resolve_physical_wall_identity(wall=a, edge_ids=("e1",), edges_by_id=edges),
            resolve_physical_wall_identity(wall=b, edge_ids=("e1",), edges_by_id=edges),
        )
        assert classify_physical_wall_pair(*identities) != PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS

    def test_blocker5_batch_with_no_physical_identities_blocks(self) -> None:
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        binding = _scale_binding(scale)
        out = build_wall_length_quantities(
            walls=(wall,),
            entities_by_wall_id={"w1": entity},
            evidence_atoms=atoms,
            physical_identities={},
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
            page_no=1,
            scale_bindings=(binding,),
        )
        assert len(out) == 1 and out[0].abstained
        assert "physical_candidate_enumerator_commitment_unavailable" in out[0].blocking_reasons

    def test_blocker6_direct_single_wall_requires_equivalence_and_snapshot_authority(self) -> None:
        import inspect

        parameter = inspect.signature(build_wall_length_quantity).parameters["equivalence"]
        assert parameter.default is inspect.Parameter.empty

        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        binding = _scale_binding(scale)
        not_representative = PhysicalWallEquivalenceResolution(
            scope_viewport_id="vp",
            representative_wall_ids=(),
            abstained_wall_ids=("w1",),
            equivalence_groups=(),
            ambiguous_wall_ids=("w1",),
            same_wall_ids=(),
            pair_classifications=(),
            blocking_reasons_by_wall_id={"w1": ("ambiguous_physical_wall_equivalence",)},
        )
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
            entity=entity,
            evidence_atoms=atoms,
            equivalence=not_representative,
            page_no=1,
            scale_bindings=(binding,),
        )
        assert qty.abstained
        assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
        assert "physical_equivalence_authenticity_unproven" in qty.blocking_reasons

    def test_blocker7_generic_figured_dimension_is_disabled_below_publication_boundary(self) -> None:
        wall, atoms = _two_domain_wall()
        figured = EvidenceAtom(
            evidence_id="dim-ev",
            document_id="doc",
            page_id="page-1",
            viewport_id="vp",
            kind="figured_dimension",
            method="vector_text",
            raw_text="5000",
            confidence=1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
            metadata={
                "wall_candidate_id": "w1",
                "revision_id": "R1",
                "evidence_snapshot_id": "evsnap",
                "source_sha256": SHA,
            },
        )
        entity, document, viewport, context = _adapt(wall, atoms + (figured,), extra=("dim-ev",))
        assert entity is not None and "dim-ev" in entity.evidence_ids
        resolved = resolve_linear_measurement_input(
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            page_no=1,
            figured_evidence=figured,
            wall_viewport_id=wall.viewport_id,
        )
        assert resolved.abstained is False and resolved.value_m == 5.0
        downgraded = _downgrade_figured_dimension_result(resolved)
        assert downgraded.authority_status == AuthorityStatus.BLOCKED.value
        assert downgraded.value_m is None
        assert FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON in downgraded.blocking_reasons

    def test_blocker8_shuffled_batch_order_is_deterministic_with_mandatory_reconciliation(self) -> None:
        scale = _scale()
        w1, a1 = _two_domain_wall(wall_id="w1", points=((0.0, 0.0), (scale.px_per_m * 3.0, 0.0)), face_ids=("seg-1",))
        w2, a2 = _two_domain_wall(wall_id="w2", points=((0.0, 10.0), (scale.px_per_m * 3.0, 10.0)), face_ids=("seg-2",))
        e1, document, viewport, context = _adapt(w1, a1)
        e2, _, _, _ = _adapt(w2, a2)
        assert e1 is not None and e2 is not None
        binding = _scale_binding(scale)
        bound_viewport = replace(viewport, resolved_scale_id=binding.scale_fingerprint)
        all_atoms = a1 + a2
        forward = build_wall_length_quantities(
            walls=(w1, w2), entities_by_wall_id={"w1": e1, "w2": e2}, evidence_atoms=all_atoms,
            physical_identities={}, context=context, document=document,
            viewport=bound_viewport, page_no=1, scale_bindings=(binding,),
        )
        reverse = build_wall_length_quantities(
            walls=(w2, w1), entities_by_wall_id={"w1": e1, "w2": e2}, evidence_atoms=all_atoms,
            physical_identities={}, context=context, document=document,
            viewport=bound_viewport, page_no=1, scale_bindings=(binding,),
        )
        fwd = {q.semantic_key: (q.abstained, q.value, q.blocking_reasons) for q in forward}
        rev = {q.semantic_key: (q.abstained, q.value, q.blocking_reasons) for q in reverse}
        assert fwd == rev
        assert all(value[0] is True and value[1] is None for value in fwd.values())


class TestAuthorityMonotonicity:
    def test_adding_competing_eligible_scale_cannot_strengthen(self) -> None:
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        baseline = _scaled_resolution(wall, atoms, scale)
        assert baseline.abstained is False and baseline.value_m == 4.0

        binding = _scale_binding(scale)
        conflict = _scaled_resolution(wall, atoms, scale, bindings=(binding, replace(binding)))
        assert conflict.abstained
        assert "conflicting_eligible_scale_bindings" in conflict.blocking_reasons

    def test_removing_current_snapshot_proof_cannot_strengthen_existence(self) -> None:
        wall, atoms = _two_domain_wall()
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        baseline = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=atoms,
            document=document,
            viewport=viewport,
            context=context,
        )
        assert baseline.status == EvidenceResolutionStatus.CORROBORATED

        unsnapshotted = tuple(
            replace(atom, metadata={k: v for k, v in atom.metadata.items() if k != "evidence_snapshot_id"})
            for atom in atoms
        )
        degraded = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=unsnapshotted,
            document=document,
            viewport=viewport,
            context=context,
        )
        assert degraded.status == EvidenceResolutionStatus.ABSTAINED
        assert "existence_atom_snapshot_unproven" in degraded.reason_codes

    def test_adding_same_id_changed_atom_cannot_strengthen_existence(self) -> None:
        wall, atoms = _two_domain_wall()
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        baseline = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=atoms,
            document=document,
            viewport=viewport,
            context=context,
        )
        assert baseline.status == EvidenceResolutionStatus.CORROBORATED

        colliding = replace(atoms[0], confidence=0.11)
        degraded = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=atoms + (colliding,),
            document=document,
            viewport=viewport,
            context=context,
        )
        assert degraded.status == EvidenceResolutionStatus.ABSTAINED
        assert "existence_evidence_id_collision" in degraded.reason_codes

    def test_adding_ambiguous_physical_competitor_cannot_strengthen_equivalence(self) -> None:
        from pb_physical_wall_identity import collect_physical_wall_identities

        scale = _scale()
        wall, _atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        length = wall.centerline_pts[1][0]
        competitor = _wall(wall_id="w1-ambiguous", points=wall.centerline_pts, face_ids=("seg-competitor",))
        graph = {
            "edges": [
                {"id": "seg-1", "x1": 0.0, "y1": 0.0, "x2": length, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_x"]}},
                {"id": "seg-competitor", "x1": 0.0, "y1": 0.0, "x2": length, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native_y"]}},
            ]
        }
        identities = collect_physical_wall_identities((wall, competitor), graph)
        equivalence = resolve_physical_wall_equivalence(
            (identities["w1"], identities["w1-ambiguous"]),
            walls_by_id={"w1": wall, "w1-ambiguous": competitor},
        )
        assert set(equivalence.ambiguous_wall_ids) == {"w1", "w1-ambiguous"}
        assert equivalence.representative_wall_ids == ()

    def test_removing_physical_equivalence_argument_is_not_a_bypass(self) -> None:
        import inspect

        assert inspect.signature(build_wall_length_quantity).parameters["equivalence"].default is inspect.Parameter.empty

    def test_direct_single_wall_path_cannot_bypass_publication_gate(self) -> None:
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        binding = _scale_binding(scale)
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
            entity=entity,
            evidence_atoms=atoms,
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            scale_bindings=(binding,),
        )
        assert qty.abstained
        assert qty.value is None
        assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
        assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons

    def test_adding_generic_figured_dimension_cannot_create_wall_length_authority(self) -> None:
        wall, atoms = _two_domain_wall()
        figured = EvidenceAtom(
            evidence_id="dim-ev",
            document_id="doc",
            page_id="page-1",
            viewport_id="vp",
            kind="figured_dimension",
            method="vector_text",
            raw_text="5000",
            confidence=1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
            metadata={
                "wall_candidate_id": "w1",
                "revision_id": "R1",
                "evidence_snapshot_id": "evsnap",
                "source_sha256": SHA,
            },
        )
        entity, document, viewport, context = _adapt(wall, atoms + (figured,), extra=("dim-ev",))
        assert entity is not None
        lower = resolve_linear_measurement_input(
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            page_no=1,
            figured_evidence=figured,
            wall_viewport_id=wall.viewport_id,
        )
        assert lower.abstained is False and lower.value_m == 5.0
        wall_length_input = _downgrade_figured_dimension_result(lower)
        assert wall_length_input.authority_status == AuthorityStatus.BLOCKED.value
        assert wall_length_input.value_m is None
        assert FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON in wall_length_input.blocking_reasons

    def test_duplicate_identical_evidence_does_not_strengthen_existence(self) -> None:
        wall, atoms = _two_domain_wall()
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        baseline = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=atoms,
            document=document,
            viewport=viewport,
            context=context,
        )
        duplicated = resolve_physical_wall_existence(
            wall=wall,
            evidence_atoms=atoms + (replace(atoms[0]), replace(atoms[1])),
            document=document,
            viewport=viewport,
            context=context,
        )
        assert baseline.status == duplicated.status == EvidenceResolutionStatus.CORROBORATED
        assert baseline.confidence == duplicated.confidence
        assert baseline.reason_codes == duplicated.reason_codes
