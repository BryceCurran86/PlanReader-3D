from __future__ import annotations

import math

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
    AuthorityScope,
    bind_resolution_fingerprint,
    build_authority_universe,
    build_completeness_manifest,
    physical_wall_identity_member,
    scale_binding_member,
)
from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_enumerator_snapshot_commitment import (
    build_enumerator_snapshot_commitment,
    immutable_snapshot_fingerprint,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import (
    resolve_linear_measurement_input,
    scale_calibration_fingerprint,
)
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
    PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    resolve_physical_wall_equivalence,
    resolve_physical_wall_identity,
)
from pb_viewport_scale_binding import ViewportScaleBinding
from pb_wall_length_quantity import (
    FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON,
    _downgrade_figured_dimension_result,
    build_wall_length_quantities,
    build_wall_length_quantity,
)
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


def _viewport(*, resolved_scale_id=None) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp",
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-ev",),
        resolved_scale_id=resolved_scale_id,
        confidence=1.0,
    )


def _source_atom(evidence_id: str, kind: str, wall_id: str = "w1") -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="page-1",
        viewport_id="vp",
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
    wall_id="w1",
    points=((0.0, 0.0), (100.0, 0.0)),
    face_ids=("seg-1",),
    *,
    supporting=("u2-ev", "pair-ev"),
    status=EvidenceResolutionStatus.CANDIDATE,
    thickness_authority=MeasurementAuthorityType.PROVISIONAL,
    thickness_m=None,
    viewport_id="vp",
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
        length_m=None,
        end_node_ids=(f"{wall_id}-n1", f"{wall_id}-n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id="L1",
        status=status,
        confidence=1.0,
        supporting_evidence_ids=supporting,
    )


def _atoms(wall_id: str = "w1") -> tuple[EvidenceAtom, EvidenceAtom]:
    return (
        _source_atom("u2-ev", KIND_PHYSICAL_WALL, wall_id),
        _source_atom("pair-ev", FAMILY_PAIRED_WALL_FACES, wall_id),
    )


def _scale(ratio=100.0, revision="R1", page_no=1):
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


def _figured(text="5000", wall_id: str = "w1") -> EvidenceAtom:
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
        metadata={
            "wall_candidate_id": wall_id,
            "revision_id": "R1",
            "evidence_snapshot_id": "evsnap",
            "source_sha256": SHA,
        },
    )


def _bind(wall: WallCandidate, extra_atoms: tuple[EvidenceAtom, ...] = ()):
    atoms = _atoms(wall.candidate_id) + extra_atoms
    extra_ids = tuple(atom.evidence_id for atom in extra_atoms)
    ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *wall.conflicting_evidence_ids, *extra_ids)))
    document = _document(ids)
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=atoms,
        document=document,
        viewport=_viewport(),
        context=_context(),
        additional_owned_evidence_ids=extra_ids,
    )
    assert entity is not None
    return entity, document, atoms


def _authority_scope(domain: str, viewport_id: str = "vp") -> AuthorityScope:
    return AuthorityScope(
        domain=domain,
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="evsnap",
        graph_snapshot_id="graphsnap",
        page_id="page-1",
        viewport_id=viewport_id,
    )


def _test_identity(wall: WallCandidate):
    edge_ids = tuple(wall.face_a_segment_ids) + tuple(wall.face_b_segment_ids or ())
    if not edge_ids:
        edge_ids = (f"test-edge-{wall.candidate_id}",)
    start = wall.centerline_pts[0]
    end = wall.centerline_pts[-1]
    edges = {
        edge_id: {
            "id": edge_id,
            "x1": float(start[0]),
            "y1": float(start[1]),
            "x2": float(end[0]),
            "y2": float(end[1]),
            "primitive_lineage": {
                "source_primitive_ids": [f"native-{wall.candidate_id}-{edge_id}"]
            },
        }
        for edge_id in edge_ids
    }
    identity = resolve_physical_wall_identity(
        wall=wall,
        edge_ids=edge_ids,
        edges_by_id=edges,
    )
    assert identity.usable
    return identity


def _scale_proof(bindings):
    scope = _authority_scope(DOMAIN_WALL_LENGTH_SCALE)
    universe = build_authority_universe(
        scope,
        tuple(scale_binding_member(binding) for binding in bindings),
    )
    manifest = build_completeness_manifest(
        universe,
        admitted_candidate_ids=tuple(scale_binding_member(binding).candidate_id for binding in bindings),
    )
    return universe, manifest


def _candidate_proof(walls, identities):
    scope = _authority_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES)
    identity_seq = tuple(identities.values()) if isinstance(identities, dict) else tuple(identities)
    universe = build_authority_universe(
        scope,
        tuple(physical_wall_identity_member(identity) for identity in identity_seq),
    )
    manifest = build_completeness_manifest(
        universe,
        admitted_candidate_ids=tuple(wall.candidate_id for wall in walls),
    )
    return identity_seq, universe, manifest


def _enumerator_proof(domain: str, universe, tag: str):
    snapshot_id = f"{tag}-snapshot"
    snapshot_fingerprint = immutable_snapshot_fingerprint(
        {
            "domain": domain,
            "scope": universe.scope.payload(),
            "members": [
                {
                    "candidate_id": member.candidate_id,
                    "provenance_fingerprint": member.provenance_fingerprint,
                }
                for member in sorted(universe.members, key=lambda item: item.candidate_id)
            ],
        }
    )
    commitment = build_enumerator_snapshot_commitment(
        scope=universe.scope,
        enumerator_id=f"test.{tag}.enumerator",
        enumerator_version="1",
        upstream_snapshot_id=snapshot_id,
        upstream_snapshot_fingerprint=snapshot_fingerprint,
        candidate_universe=universe,
    )
    return commitment, snapshot_id, snapshot_fingerprint, universe


def _qty_kwargs(wall: WallCandidate, extra_atoms: tuple[EvidenceAtom, ...] = (), **overrides):
    entity, document, atoms = _bind(wall, extra_atoms=extra_atoms)
    scale = overrides.pop("scale", _scale()) if "scale_bindings" not in overrides else None
    bindings = overrides.pop(
        "scale_bindings",
        (_scale_binding(scale),) if scale is not None else (),
    )
    binding = bindings[0] if bindings else None
    viewport = overrides.pop(
        "viewport",
        _viewport(resolved_scale_id=binding.scale_fingerprint if binding is not None else None),
    )
    scale_universe, scale_manifest = _scale_proof(bindings)
    scale_commitment, scale_snapshot_id, scale_snapshot_fp, scale_current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        scale_universe,
        "scale",
    )
    identity = _test_identity(wall)
    identities, candidate_universe, candidate_manifest = _candidate_proof((wall,), (identity,))
    candidate_commitment, candidate_snapshot_id, candidate_snapshot_fp, candidate_current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        candidate_universe,
        "physical-wall",
    )
    equivalence = resolve_physical_wall_equivalence(
        identities,
        walls_by_id={wall.candidate_id: wall},
    )
    equivalence_binding = bind_resolution_fingerprint(
        equivalence,
        scope=_authority_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        candidate_universe=candidate_universe,
        identities=identities,
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )
    kwargs = dict(
        wall=wall,
        context=_context(),
        document=document,
        viewport=viewport,
        entity=entity,
        evidence_atoms=atoms,
        equivalence=equivalence,
        equivalence_binding=equivalence_binding,
        page_no=1,
        scale_bindings=bindings,
        scale_universe=scale_universe,
        scale_manifest=scale_manifest,
        scale_enumerator_commitment=scale_commitment,
        scale_upstream_snapshot_id=scale_snapshot_id,
        scale_upstream_snapshot_fingerprint=scale_snapshot_fp,
        scale_enumerated_universe=scale_current,
        candidate_universe=candidate_universe,
        candidate_manifest=candidate_manifest,
        candidate_enumerator_commitment=candidate_commitment,
        candidate_upstream_snapshot_id=candidate_snapshot_id,
        candidate_upstream_snapshot_fingerprint=candidate_snapshot_fp,
        candidate_enumerated_universe=candidate_current,
        physical_identity_universe=identities,
        physical_walls_by_id={wall.candidate_id: wall},
    )
    kwargs.update(overrides)
    return kwargs


def _page_length(wall: WallCandidate) -> float:
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(wall.centerline_pts, wall.centerline_pts[1:])
    )


def _resolve_scaled_wall(wall: WallCandidate, scale):
    entity, document, _atoms_seen = _bind(wall)
    binding = _scale_binding(scale)
    viewport = _viewport(resolved_scale_id=binding.scale_fingerprint)
    return resolve_linear_measurement_input(
        context=_context(),
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=1,
        scaled_length_page_units=_page_length(wall),
        scale_bindings=(binding,),
        wall_viewport_id=wall.viewport_id,
    )


def test_scaled_wall_length_publication_blocks_without_authoritative_snapshot_content() -> None:
    scale = _scale()
    wall = _wall(points=((0.0, 0.0), (scale.px_per_m * 5.0, 0.0)))
    qty = build_wall_length_quantity(**_qty_kwargs(wall, scale=scale))
    assert qty.abstained is True
    assert qty.value is None
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "authoritative_upstream_snapshot_content_unavailable" in qty.blocking_reasons


def test_translation_is_metamorphically_invariant_below_publication_boundary() -> None:
    scale = _scale()
    length = scale.px_per_m * 7.25
    a = _wall(points=((0.0, 0.0), (length, 0.0)))
    b = _wall(points=((500.0, -200.0), (500.0 + length, -200.0)))
    left = _resolve_scaled_wall(a, scale)
    right = _resolve_scaled_wall(b, scale)
    assert left.abstained is False and right.abstained is False
    assert left.value_m == right.value_m == 7.25


def test_rotation_is_metamorphically_invariant_below_publication_boundary() -> None:
    scale = _scale()
    length = scale.px_per_m * 3.0
    horizontal = _wall(points=((0.0, 0.0), (length, 0.0)))
    vertical = _wall(points=((0.0, 0.0), (0.0, length)))
    left = _resolve_scaled_wall(horizontal, scale)
    right = _resolve_scaled_wall(vertical, scale)
    assert left.abstained is False and right.abstained is False
    assert left.value_m == right.value_m == 3.0


def test_figured_dimension_route_is_disabled_after_lower_level_resolution() -> None:
    wall = _wall()
    figured = _figured("5000")
    entity, document, _atoms_seen = _bind(wall, extra_atoms=(figured,))
    resolved = resolve_linear_measurement_input(
        context=_context(),
        document=document,
        viewport=_viewport(),
        entity=entity,
        page_no=1,
        figured_evidence=figured,
        wall_viewport_id=wall.viewport_id,
    )
    assert resolved.abstained is False
    assert resolved.value_m == 5.0
    downgraded = _downgrade_figured_dimension_result(resolved)
    assert downgraded.abstained is True
    assert downgraded.value_m is None
    assert downgraded.authority_status == AuthorityStatus.BLOCKED.value
    assert FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON in downgraded.blocking_reasons


def test_untrusted_physical_existence_abstains() -> None:
    wall = _wall(supporting=("u2-ev",))
    qty = build_wall_length_quantity(**_qty_kwargs(wall))
    assert qty.abstained
    assert "physical_wall_existence_not_corroborated" in qty.blocking_reasons


def test_duplicate_candidate_identity_fails_closed() -> None:
    walls = (_wall("w1", face_ids=("seg-1",)), _wall("w1", face_ids=("seg-2",)))
    entity, document, atoms = _bind(walls[0])
    out = build_wall_length_quantities(
        walls=walls,
        entities_by_wall_id={"w1": entity},
        evidence_atoms=atoms,
        physical_identities={},
        context=_context(),
        document=document,
        page_no=1,
        scale_bindings=(_scale_binding(_scale()),),
        viewport=_viewport(resolved_scale_id=scale_calibration_fingerprint(_scale())),
    )
    assert len(out) == 2
    assert all(q.abstained for q in out)
    assert all("duplicate_wall_identity" in q.blocking_reasons for q in out)


def test_overlapping_source_segments_fail_closed_instead_of_double_counting() -> None:
    w1 = _wall("w1", face_ids=("shared-seg",))
    w2 = _wall("w2", points=((0.0, 10.0), (100.0, 10.0)), face_ids=("shared-seg",))
    e1, document, atoms1 = _bind(w1)
    e2, _, atoms2 = _bind(w2)
    out = build_wall_length_quantities(
        walls=(w1, w2),
        entities_by_wall_id={"w1": e1, "w2": e2},
        evidence_atoms=atoms1 + atoms2,
        physical_identities={},
        context=_context(),
        document=document,
        page_no=1,
        scale_bindings=(_scale_binding(_scale()),),
        viewport=_viewport(resolved_scale_id=scale_calibration_fingerprint(_scale())),
    )
    assert len(out) == 2
    assert all(q.abstained for q in out)
    assert all("overlapping_wall_source_segments" in q.blocking_reasons for q in out)


def test_stale_scale_is_rejected_by_measurement_resolver() -> None:
    scale = _scale(revision="R0")
    wall = _wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
    entity, document, _atoms_seen = _bind(wall)
    binding = _scale_binding(scale)
    resolved = resolve_linear_measurement_input(
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=binding.scale_fingerprint),
        entity=entity,
        page_no=1,
        scaled_length_page_units=_page_length(wall),
        scale_bindings=(binding,),
        wall_viewport_id=wall.viewport_id,
    )
    assert resolved.abstained is True
    assert "scale_binding_revision_mismatch" in resolved.blocking_reasons


def test_bare_scale_calibration_cannot_reach_quantity_builder() -> None:
    wall = _wall()
    kwargs = _qty_kwargs(wall, scale_bindings=())
    kwargs["scale_calibration"] = _scale()
    try:
        qty = build_wall_length_quantity(**kwargs)
    except TypeError:
        return
    assert qty.abstained
    assert "bare_scale_calibration_rejected" in qty.blocking_reasons


def _edge(edge_id: str, x1, y1, x2, y2, *primitive_ids: str) -> dict:
    return {
        "id": edge_id,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "primitive_lineage": {"source_primitive_ids": list(primitive_ids)},
    }


def _batch_with_identities(walls, identities):
    from dataclasses import replace as _dc_replace

    scoped_walls = [
        _dc_replace(
            wall,
            supporting_evidence_ids=(f"u2-ev-{wall.candidate_id}", f"pair-ev-{wall.candidate_id}"),
        )
        for wall in walls
    ]
    entities = {}
    all_atoms: list[EvidenceAtom] = []
    all_ids: list[str] = []
    for wall in scoped_walls:
        wall_atoms = (
            _source_atom(f"u2-ev-{wall.candidate_id}", KIND_PHYSICAL_WALL, wall.candidate_id),
            _source_atom(f"pair-ev-{wall.candidate_id}", FAMILY_PAIRED_WALL_FACES, wall.candidate_id),
        )
        all_atoms.extend(wall_atoms)
        all_ids.extend(atom.evidence_id for atom in wall_atoms)
    document = _document(tuple(dict.fromkeys(all_ids)))
    viewport = _viewport()
    context = _context()
    for wall in scoped_walls:
        entity = adapt_wall_candidate_to_entity_evidence(
            wall, evidence_atoms=all_atoms, document=document, viewport=viewport, context=context,
        )
        assert entity is not None
        entities[wall.candidate_id] = entity
    scale = _scale()
    binding = _scale_binding(scale)
    scale_universe, scale_manifest = _scale_proof((binding,))
    scale_commitment, scale_snapshot_id, scale_snapshot_fp, scale_current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        scale_universe,
        "scale-batch",
    )
    identity_seq, candidate_universe, candidate_manifest = _candidate_proof(scoped_walls, identities)
    candidate_commitment, candidate_snapshot_id, candidate_snapshot_fp, candidate_current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        candidate_universe,
        "physical-wall-batch",
    )
    identity_map = (
        dict(identities)
        if isinstance(identities, dict)
        else {identity.wall_candidate_id: identity for identity in identity_seq}
    )
    return build_wall_length_quantities(
        walls=scoped_walls,
        entities_by_wall_id=entities,
        evidence_atoms=all_atoms,
        physical_identities=identity_map,
        physical_identity_universe=identity_seq,
        context=context,
        document=document,
        viewport=_dc_replace(viewport, resolved_scale_id=binding.scale_fingerprint),
        page_no=1,
        scale_bindings=(binding,),
        scale_universe=scale_universe,
        scale_manifest=scale_manifest,
        scale_enumerator_commitment=scale_commitment,
        scale_upstream_snapshot_id=scale_snapshot_id,
        scale_upstream_snapshot_fingerprint=scale_snapshot_fp,
        scale_enumerated_universe=scale_current,
        candidate_universe=candidate_universe,
        candidate_manifest=candidate_manifest,
        candidate_enumerator_commitment=candidate_commitment,
        candidate_upstream_snapshot_id=candidate_snapshot_id,
        candidate_upstream_snapshot_fingerprint=candidate_snapshot_fp,
        candidate_enumerated_universe=candidate_current,
    )


def test_reversed_and_rechunked_walls_reconcile_to_one_representative() -> None:
    from pb_physical_wall_identity import collect_physical_wall_identities

    length = 100.0
    forward = _wall("w1", points=((0.0, 0.0), (length, 0.0)), face_ids=("e1",))
    reversed_wall = _wall("w2", points=((length, 0.0), (0.0, 0.0)), face_ids=("e2",))
    rechunked = _wall(
        "w3",
        points=((0.0, 0.0), (length / 2.0, 0.0), (length, 0.0)),
        face_ids=("e3a", "e3b"),
    )
    graph = {
        "edges": [
            _edge("e1", 0.0, 0.0, length, 0.0, "native"),
            _edge("e2", length, 0.0, 0.0, 0.0, "native"),
            _edge("e3a", 0.0, 0.0, length / 2.0, 0.0, "native"),
            _edge("e3b", length / 2.0, 0.0, length, 0.0, "native"),
        ]
    }
    identities = collect_physical_wall_identities((forward, reversed_wall, rechunked), graph)
    resolution = resolve_physical_wall_equivalence(
        tuple(identities.values()),
        walls_by_id={wall.candidate_id: wall for wall in (forward, reversed_wall, rechunked)},
    )
    assert len(resolution.representative_wall_ids) == 1
    assert len(resolution.abstained_wall_ids) == 2
    assert all(
        any(reason.startswith("equivalent_physical_wall_represented_by:") for reason in resolution.blockers_for(wall_id))
        for wall_id in resolution.abstained_wall_ids
    )


def test_same_endpoints_different_interior_path_is_ambiguous_without_shared_provenance() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_equivalence,
        resolve_physical_wall_identity,
    )

    straight = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e0",))
    detour = _wall("w2", points=((0.0, 0.0), (50.0, 40.0), (100.0, 0.0)), face_ids=("e1", "e2"))
    edges = {
        "e0": _edge("e0", 0.0, 0.0, 100.0, 0.0, "native_straight"),
        "e1": _edge("e1", 0.0, 0.0, 50.0, 40.0, "native_detour_a"),
        "e2": _edge("e2", 50.0, 40.0, 100.0, 0.0, "native_detour_b"),
    }
    left = resolve_physical_wall_identity(wall=straight, edge_ids=("e0",), edges_by_id=edges)
    right = resolve_physical_wall_identity(wall=detour, edge_ids=("e1", "e2"), edges_by_id=edges)
    assert left.usable and right.usable
    assert left.candidate_identity_id != right.candidate_identity_id
    assert left.path_fingerprint != right.path_fingerprint
    assert classify_physical_wall_pair(left, right) == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    resolution = resolve_physical_wall_equivalence((left, right))
    assert set(resolution.ambiguous_wall_ids) == {"w1", "w2"}
    assert resolution.representative_wall_ids == ()


def test_same_u1_ancestor_disjoint_spans_stay_distinct() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_equivalence,
        resolve_physical_wall_identity,
    )

    left = _wall("w1", points=((0.0, 0.0), (40.0, 0.0)), face_ids=("e1",))
    right = _wall("w2", points=((60.0, 0.0), (100.0, 0.0)), face_ids=("e2",))
    edges = {
        "e1": _edge("e1", 0.0, 0.0, 40.0, 0.0, "shared_native"),
        "e2": _edge("e2", 60.0, 0.0, 100.0, 0.0, "shared_native"),
    }
    identities = (
        resolve_physical_wall_identity(wall=left, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=right, edge_ids=("e2",), edges_by_id=edges),
    )
    assert identities[0].candidate_identity_id != identities[1].candidate_identity_id
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS
    resolution = resolve_physical_wall_equivalence(identities)
    assert resolution.ambiguous_wall_ids == ()
    assert set(resolution.representative_wall_ids) == {"w1", "w2"}


def test_different_viewport_label_alone_is_ambiguous_not_distinct() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_identity,
    )

    a = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",))
    b = _wall("w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), viewport_id="vp-other")
    edges = {"e1": _edge("e1", 0.0, 0.0, 100.0, 0.0, "native")}
    identities = (
        resolve_physical_wall_identity(wall=a, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=b, edge_ids=("e1",), edges_by_id=edges),
    )
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def test_distinct_viewports_with_disjoint_ancestry_spans_stay_distinct() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_identity,
    )

    a = _wall("w1", points=((0.0, 0.0), (60.0, 0.0)), face_ids=("e1",))
    b = _wall("w2", points=((100.0, 0.0), (160.0, 0.0)), face_ids=("e2",), viewport_id="vp-other")
    edges = {
        "e1": _edge("e1", 0.0, 0.0, 60.0, 0.0, "shared_native"),
        "e2": _edge("e2", 100.0, 0.0, 160.0, 0.0, "shared_native"),
    }
    identities = (
        resolve_physical_wall_identity(wall=a, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=b, edge_ids=("e2",), edges_by_id=edges),
    )
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS


def test_missing_lineage_or_edges_abstains_identity_instead_of_endpoint_hash() -> None:
    from pb_physical_wall_identity import resolve_physical_wall_identity

    wall = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",))
    missing = resolve_physical_wall_identity(wall=wall, edge_ids=("e1",), edges_by_id=None)
    assert missing.usable is False
    assert "physical_identity_path_inputs_unavailable" in missing.blocking_reasons
    no_coords = resolve_physical_wall_identity(
        wall=wall,
        edge_ids=("e1",),
        edges_by_id={"e1": {"id": "e1", "primitive_lineage": {"source_primitive_ids": ["n"]}}},
    )
    assert no_coords.usable is False
    assert "physical_identity_edge_geometry_unavailable" in no_coords.blocking_reasons


def test_paired_face_and_centerline_reconcile_as_ambiguous() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        collect_physical_wall_identities,
    )

    center = _wall("w1", points=((0.0, 5.0), (100.0, 5.0)), face_ids=("c1",))
    face = _wall("w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("f1",))
    graph = {
        "edges": [
            _edge("c1", 0.0, 5.0, 100.0, 5.0, "native_a"),
            _edge("f1", 0.0, 0.0, 100.0, 0.0, "native_a"),
        ]
    }
    identities = collect_physical_wall_identities((center, face), graph)
    assert (
        classify_physical_wall_pair(identities["w1"], identities["w2"])
        == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    )
    resolution = resolve_physical_wall_equivalence(
        tuple(identities.values()),
        walls_by_id={"w1": center, "w2": face},
    )
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {"w1", "w2"}
    assert all(
        "ambiguous_physical_wall_equivalence" in resolution.blockers_for(wall_id)
        for wall_id in ("w1", "w2")
    )


def test_same_path_different_duplicated_native_ids_reconcile_as_ambiguous() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        collect_physical_wall_identities,
        resolve_physical_wall_equivalence,
    )

    a = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",))
    b = _wall("w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e2",))
    graph = {
        "edges": [
            _edge("e1", 0.0, 0.0, 100.0, 0.0, "native_copy_a"),
            _edge("e2", 0.0, 0.0, 100.0, 0.0, "native_copy_b"),
        ]
    }
    identities = collect_physical_wall_identities((a, b), graph)
    assert identities["w1"].candidate_identity_id != identities["w2"].candidate_identity_id
    assert identities["w1"].path_fingerprint == identities["w2"].path_fingerprint
    assert (
        classify_physical_wall_pair(identities["w1"], identities["w2"])
        == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    )
    resolution = resolve_physical_wall_equivalence(
        tuple(identities.values()),
        walls_by_id={"w1": a, "w2": b},
    )
    assert set(resolution.ambiguous_wall_ids) == {"w1", "w2"}
    assert resolution.representative_wall_ids == ()
    assert all(
        "ambiguous_physical_wall_equivalence" in resolution.blockers_for(wall_id)
        for wall_id in ("w1", "w2")
    )


def test_slight_offset_candidate_is_ambiguous_without_positive_distinctness() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_equivalence,
        resolve_physical_wall_identity,
    )

    a = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",))
    b = _wall("w2", points=((0.0, 2.0), (100.0, 2.0)), face_ids=("e2",))
    edges = {
        "e1": _edge("e1", 0.0, 0.0, 100.0, 0.0, "native_a"),
        "e2": _edge("e2", 0.0, 2.0, 100.0, 2.0, "native_b"),
    }
    identities = (
        resolve_physical_wall_identity(wall=a, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=b, edge_ids=("e2",), edges_by_id=edges),
    )
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    resolution = resolve_physical_wall_equivalence(identities)
    assert set(resolution.ambiguous_wall_ids) == {"w1", "w2"}
    assert resolution.representative_wall_ids == ()


def test_rechunk_equivalent_geometry_reconciles_to_one_representative() -> None:
    from pb_physical_wall_identity import collect_physical_wall_identities

    length = 100.0
    forward = _wall("w1", points=((0.0, 0.0), (length, 0.0)), face_ids=("e1",))
    rechunked = _wall(
        "w2",
        points=((0.0, 0.0), (length / 2.0, 0.0), (length, 0.0)),
        face_ids=("e2a", "e2b"),
    )
    graph = {
        "edges": [
            _edge("e1", 0.0, 0.0, length, 0.0, "native"),
            _edge("e2a", 0.0, 0.0, length / 2.0, 0.0, "native"),
            _edge("e2b", length / 2.0, 0.0, length, 0.0, "native"),
        ]
    }
    identities = collect_physical_wall_identities((forward, rechunked), graph)
    resolution = resolve_physical_wall_equivalence(
        tuple(identities.values()),
        walls_by_id={"w1": forward, "w2": rechunked},
    )
    assert len(resolution.representative_wall_ids) == 1
    assert len(resolution.abstained_wall_ids) == 1
    assert any(
        reason.startswith("equivalent_physical_wall_represented_by:")
        for reason in resolution.blockers_for(resolution.abstained_wall_ids[0])
    )


def test_partial_overlap_same_ancestry_is_ambiguous() -> None:
    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_identity,
    )

    left = _wall("w1", points=((0.0, 0.0), (60.0, 0.0)), face_ids=("e1",))
    right = _wall("w2", points=((40.0, 0.0), (100.0, 0.0)), face_ids=("e2",))
    edges = {
        "e1": _edge("e1", 0.0, 0.0, 60.0, 0.0, "shared_native"),
        "e2": _edge("e2", 40.0, 0.0, 100.0, 0.0, "shared_native"),
    }
    identities = (
        resolve_physical_wall_identity(wall=left, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=right, edge_ids=("e2",), edges_by_id=edges),
    )
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def test_different_level_label_alone_is_ambiguous_not_distinct() -> None:
    from dataclasses import replace as dc_replace

    from pb_physical_wall_identity import (
        PhysicalEquivalenceClass,
        classify_physical_wall_pair,
        resolve_physical_wall_identity,
    )

    left = _wall("w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",))
    right = dc_replace(
        _wall("w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e2",)),
        level_id="L2",
    )
    edges = {
        "e1": _edge("e1", 0.0, 0.0, 100.0, 0.0, "native_a"),
        "e2": _edge("e2", 0.0, 0.0, 100.0, 0.0, "native_b"),
    }
    identities = (
        resolve_physical_wall_identity(wall=left, edge_ids=("e1",), edges_by_id=edges),
        resolve_physical_wall_identity(wall=right, edge_ids=("e2",), edges_by_id=edges),
    )
    assert classify_physical_wall_pair(*identities) == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
