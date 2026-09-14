from __future__ import annotations

from dataclasses import replace
from itertools import permutations

import pytest

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
    AuthorityBindingStatus,
    AuthorityScope,
    AuthorityUniverseMember,
    ExplicitExclusion,
    bind_resolution_fingerprint,
    build_authority_universe,
    build_completeness_manifest,
    canonical_sha256,
    physical_wall_identity_member,
    scale_binding_member,
    verify_bound_resolution_fingerprint,
)
from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_enumerator_snapshot_commitment import (
    build_enumerator_snapshot_commitment,
    immutable_snapshot_fingerprint,
    verify_enumerator_snapshot_commitment,
)
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
    PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    PhysicalWallEquivalenceResolution,
    resolve_physical_wall_equivalence,
    resolve_physical_wall_identity,
)
from pb_viewport_scale_binding import ViewportScaleBinding
from pb_wall_length_quantity import (
    _local_physical_identities,
    build_wall_length_quantities,
    build_wall_length_quantity,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

SHA = "d" * 64


def _context(**overrides) -> ProviderContext:
    values = dict(
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
    values.update(overrides)
    return ProviderContext(**values)


def _document(ids: tuple[str, ...], *, document_id: str = "doc", sha: str = SHA) -> DocumentEvidence:
    return DocumentEvidence(
        document_id=document_id,
        source_sha256=sha,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(*, resolved_scale_id: str | None = None, viewport_id: str = "vp") -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-w1",),
        resolved_scale_id=resolved_scale_id,
        confidence=1.0,
    )


def _wall(
    wall_id: str,
    *,
    y: float = 0.0,
    face_id: str | None = None,
    viewport_id: str = "vp",
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id=viewport_id,
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


def _entity(wall: WallCandidate, document: DocumentEvidence, atoms=None):
    resolved_atoms = tuple(atoms or _atoms(wall.candidate_id))
    entity = adapt_wall_candidate_to_entity_evidence(
        wall,
        evidence_atoms=resolved_atoms,
        document=document,
        viewport=_viewport(viewport_id=wall.viewport_id),
        context=_context(),
    )
    assert entity is not None
    return entity


def _scale(ratio: float, *, label: str = "A101"):
    return resolve_page_scale_calibration(
        page_no=1,
        sheet_label=label,
        readings=(
            ScaleSourceReading(
                ScaleSourceType.SCALE_BAR.value,
                f"1:{ratio:g}",
                ratio,
                1.0,
            ),
        ),
        revision_id="R1",
    )


def _binding(ratio: float, *, label: str = "A101") -> ViewportScaleBinding:
    scale = _scale(ratio, label=label)
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


def _identity(wall: WallCandidate, *, lineage: str | None = None):
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
                "primitive_lineage": {
                    "source_primitive_ids": [lineage or f"native-{wall.candidate_id}"]
                },
            }
        },
    )


def _scope(domain: str, **overrides) -> AuthorityScope:
    values = dict(
        domain=domain,
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="evsnap-1",
        graph_snapshot_id="graphsnap-1",
        page_id="page-1",
        viewport_id="vp",
    )
    values.update(overrides)
    return AuthorityScope(**values)


def _scale_proof(
    bindings: tuple[ViewportScaleBinding, ...],
    *,
    extra_members: tuple[AuthorityUniverseMember, ...] = (),
    admitted_ids: tuple[str, ...] | None = None,
    unresolved_ids: tuple[str, ...] = (),
    exclusions: tuple[ExplicitExclusion, ...] = (),
    scope: AuthorityScope | None = None,
):
    members = tuple(scale_binding_member(item) for item in bindings) + tuple(extra_members)
    universe = build_authority_universe(scope or _scope(DOMAIN_WALL_LENGTH_SCALE), members)
    manifest = build_completeness_manifest(
        universe,
        admitted_candidate_ids=(
            admitted_ids
            if admitted_ids is not None
            else tuple(scale_binding_member(item).candidate_id for item in bindings)
        ),
        unresolved_candidate_ids=unresolved_ids,
        explicit_exclusions=exclusions,
    )
    return universe, manifest


def _candidate_proof(
    identities,
    *,
    extra_members: tuple[AuthorityUniverseMember, ...] = (),
    admitted_ids: tuple[str, ...] | None = None,
    unresolved_ids: tuple[str, ...] = (),
    exclusions: tuple[ExplicitExclusion, ...] = (),
    scope: AuthorityScope | None = None,
):
    members = tuple(physical_wall_identity_member(item) for item in identities) + tuple(extra_members)
    universe = build_authority_universe(
        scope or _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        members,
    )
    manifest = build_completeness_manifest(
        universe,
        admitted_candidate_ids=(
            admitted_ids
            if admitted_ids is not None
            else tuple(item.wall_candidate_id for item in identities)
        ),
        unresolved_candidate_ids=unresolved_ids,
        explicit_exclusions=exclusions,
    )
    return universe, manifest


def _snapshot_payload(domain: str, universe) -> dict[str, object]:
    return {
        "domain": domain,
        "scope": universe.scope.payload(),
        "members": tuple(
            {
                "candidate_id": item.candidate_id,
                "provenance_fingerprint": item.provenance_fingerprint,
            }
            for item in sorted(universe.members, key=lambda item: item.candidate_id)
        ),
    }


def _enumerator_proof(domain: str, universe: object, *, snapshot_tag: str):
    snapshot_payload = _snapshot_payload(domain, universe)
    snapshot_id = f"{snapshot_tag}-snapshot-1"
    snapshot_fingerprint = immutable_snapshot_fingerprint(snapshot_payload)
    commitment = build_enumerator_snapshot_commitment(
        scope=universe.scope,
        enumerator_id=f"test.{snapshot_tag}.enumerator",
        enumerator_version="1",
        upstream_snapshot_id=snapshot_id,
        upstream_snapshot_fingerprint=snapshot_fingerprint,
        candidate_universe=universe,
    )
    return commitment, snapshot_id, snapshot_fingerprint, universe


def _verify_enumerator_current(
    domain: str,
    universe,
    manifest,
    supplied_admitted_ids: tuple[str, ...],
    *,
    snapshot_tag: str,
):
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        domain,
        universe,
        snapshot_tag=snapshot_tag,
    )
    return verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(domain),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=supplied_admitted_ids,
        current_upstream_snapshot_payload=_snapshot_payload(domain, current),
    )


def _install_scale_enumerator(kwargs: dict, universe) -> None:
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        snapshot_tag="scale",
    )
    kwargs.update(
        scale_enumerator_commitment=commitment,
        scale_upstream_snapshot_id=snapshot_id,
        scale_upstream_snapshot_fingerprint=snapshot_fp,
        scale_enumerated_universe=current,
    )


def _install_candidate_enumerator(kwargs: dict, universe) -> None:
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        snapshot_tag="physical-wall",
    )
    kwargs.update(
        candidate_enumerator_commitment=commitment,
        candidate_upstream_snapshot_id=snapshot_id,
        candidate_upstream_snapshot_fingerprint=snapshot_fp,
        candidate_enumerated_universe=current,
    )


def _equivalence_bundle(walls, identities, candidate_universe, *, scope=None):
    walls_by_id = {wall.candidate_id: wall for wall in walls}
    resolution = resolve_physical_wall_equivalence(
        tuple(identities),
        walls_by_id=walls_by_id,
    )
    binding = bind_resolution_fingerprint(
        resolution,
        scope=scope or _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        candidate_universe=candidate_universe,
        identities=tuple(identities),
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )
    return resolution, binding


def _firm_single_kwargs(wall: WallCandidate | None = None):
    """Legacy-shaped public-boundary inputs.

    These deliberately do not and cannot install an authoritative upstream
    snapshot payload. They are useful for asserting the publication boundary
    fails closed, not for constructing a synthetic FIRM quantity.
    """
    resolved_wall = wall or _wall("w1")
    atoms = _atoms(resolved_wall.candidate_id)
    document = _document(tuple(atom.evidence_id for atom in atoms))
    scale_binding = _binding(100.0)
    scale_universe, scale_manifest = _scale_proof((scale_binding,))
    identity = _identity(resolved_wall)
    candidate_universe, candidate_manifest = _candidate_proof((identity,))
    equivalence, equivalence_binding = _equivalence_bundle(
        (resolved_wall,),
        (identity,),
        candidate_universe,
    )
    kwargs = dict(
        wall=resolved_wall,
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=scale_binding.scale_fingerprint),
        entity=_entity(resolved_wall, document, atoms),
        evidence_atoms=atoms,
        equivalence=equivalence,
        page_no=1,
        scale_bindings=(scale_binding,),
        scale_universe=scale_universe,
        scale_manifest=scale_manifest,
        candidate_universe=candidate_universe,
        candidate_manifest=candidate_manifest,
        physical_identity_universe=(identity,),
        physical_walls_by_id={resolved_wall.candidate_id: resolved_wall},
        equivalence_binding=equivalence_binding,
    )
    _install_scale_enumerator(kwargs, scale_universe)
    _install_candidate_enumerator(kwargs, candidate_universe)
    return kwargs


def _assert_blocked(qty, reason: str) -> None:
    assert qty.abstained is True
    assert qty.status == AuthorityStatus.BLOCKED.value
    assert reason in qty.blocking_reasons


def test_public_boundary_stays_blocked_without_authoritative_snapshot_producer() -> None:
    qty = build_wall_length_quantity(**_firm_single_kwargs())
    assert qty.abstained is True
    assert qty.value is None
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "authoritative_upstream_snapshot_content_unavailable" in qty.blocking_reasons


# C1 --------------------------------------------------------------------------


def test_c1_hidden_same_viewport_scale_competitor_is_detected_below_public_boundary() -> None:
    admitted = _binding(100.0, label="A101")
    hidden = _binding(50.0, label="A102")
    universe, manifest = _scale_proof((admitted, hidden))
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        (scale_binding_member(admitted).candidate_id,),
        snapshot_tag="scale-hidden",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_admitted_set_mismatch" in result.reasons


def test_c1_two_agreeing_scale_candidates_remain_unreconciled() -> None:
    first = _binding(100.0, label="A101")
    second = _binding(100.0, label="A101-SECOND")
    universe, manifest = _scale_proof((first, second))
    admitted = tuple(item.candidate_id for item in universe.members)
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        admitted,
        snapshot_tag="scale-agreeing",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "scale_universe_multiple_admitted_candidates_unreconciled" in result.reasons


def test_c1_two_conflicting_scales_remain_unreconciled() -> None:
    first = _binding(100.0, label="A101")
    second = _binding(50.0, label="A102")
    universe, manifest = _scale_proof((first, second))
    admitted = tuple(item.candidate_id for item in universe.members)
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        admitted,
        snapshot_tag="scale-conflicting",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "scale_universe_multiple_admitted_candidates_unreconciled" in result.reasons


def test_c1_omitted_admitted_scale_candidate_blocks() -> None:
    first = _binding(100.0, label="A101")
    second = _binding(75.0, label="A103")
    universe, manifest = _scale_proof((first, second))
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        (scale_binding_member(first).candidate_id,),
        snapshot_tag="scale-omitted",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_admitted_set_mismatch" in result.reasons


def test_c1_unresolved_scale_candidate_blocks() -> None:
    first = _binding(100.0)
    unresolved = AuthorityUniverseMember("scale-unresolved", canonical_sha256({"candidate": "u"}))
    universe, manifest = _scale_proof(
        (first,),
        extra_members=(unresolved,),
        admitted_ids=(scale_binding_member(first).candidate_id,),
        unresolved_ids=("scale-unresolved",),
    )
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        (scale_binding_member(first).candidate_id,),
        snapshot_tag="scale-unresolved",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_unresolved_candidates" in result.reasons


def test_c1_explicit_evidenced_scale_exclusion_authenticates_remaining_scale() -> None:
    first = _binding(100.0, label="A101")
    excluded = _binding(50.0, label="A102")
    first_id = scale_binding_member(first).candidate_id
    excluded_id = scale_binding_member(excluded).candidate_id
    universe, manifest = _scale_proof(
        (first, excluded),
        admitted_ids=(first_id,),
        exclusions=(ExplicitExclusion(excluded_id, "wrong_view_type", ("ev-exclusion",)),),
    )
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        (first_id,),
        snapshot_tag="scale-exclusion",
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC
    assert result.authentic


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_sha256", "e" * 64),
        ("revision_id", "R0"),
        ("evidence_snapshot_id", "evsnap-old"),
        ("graph_snapshot_id", "graph-old"),
        ("viewport_id", "vp-other"),
        ("document_id", "doc-other"),
    ),
)
def test_c1_stale_or_wrong_scale_scope_blocks(field: str, value: str) -> None:
    binding = _binding(100.0)
    stale_scope = replace(_scope(DOMAIN_WALL_LENGTH_SCALE), **{field: value})
    universe, manifest = _scale_proof((binding,), scope=stale_scope)
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        snapshot_tag="scale-stale-scope",
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_SCALE),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=(scale_binding_member(binding).candidate_id,),
        current_upstream_snapshot_payload=_snapshot_payload(DOMAIN_WALL_LENGTH_SCALE, current),
    )
    assert result.status in {AuthorityBindingStatus.STALE, AuthorityBindingStatus.MISMATCH}


def test_c1_conflict_added_after_manifest_creation_invalidates_manifest() -> None:
    first = _binding(100.0)
    old_universe, old_manifest = _scale_proof((first,))
    added = _binding(50.0, label="A102")
    current_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_SCALE),
        (scale_binding_member(first), scale_binding_member(added)),
    )
    assert current_universe.fingerprint != old_universe.fingerprint
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        current_universe,
        old_manifest,
        (scale_binding_member(first).candidate_id,),
        snapshot_tag="scale-added-after-manifest",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "manifest_not_bound_to_enumerator_commitment" in result.reasons


def test_c1_conflict_monotonicity_never_strengthens_authority() -> None:
    first = _binding(100.0)
    baseline_universe, baseline_manifest = _scale_proof((first,))
    baseline = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        baseline_universe,
        baseline_manifest,
        (scale_binding_member(first).candidate_id,),
        snapshot_tag="scale-monotonic-baseline",
    )
    assert baseline.status == AuthorityBindingStatus.AUTHENTIC

    unresolved = AuthorityUniverseMember("late-scale", canonical_sha256({"late": True}))
    universe, manifest = _scale_proof(
        (first,),
        extra_members=(unresolved,),
        admitted_ids=(scale_binding_member(first).candidate_id,),
        unresolved_ids=("late-scale",),
    )
    degraded = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        manifest,
        (scale_binding_member(first).candidate_id,),
        snapshot_tag="scale-monotonic-conflict",
    )
    assert degraded.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_unresolved_candidates" in degraded.reasons


# C4 --------------------------------------------------------------------------


def _same_wall_equivalence_fixture():
    a = _wall("w1", face_id="e1")
    b = _wall("w2", face_id="e2")
    identities = (_identity(a, lineage="shared"), _identity(b, lineage="shared"))
    universe, manifest = _candidate_proof(identities)
    resolution, bound = _equivalence_bundle((a, b), identities, universe)
    return (a, b), identities, universe, manifest, resolution, bound


def _verify_resolution(resolution, bound, identities, universe, walls, *, scope=None):
    expected = resolve_physical_wall_equivalence(
        tuple(identities),
        walls_by_id={wall.candidate_id: wall for wall in walls},
    )
    return verify_bound_resolution_fingerprint(
        resolution,
        bound,
        expected_resolution=expected,
        expected_scope=scope or _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        candidate_universe=universe,
        identities=tuple(identities),
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )


def test_c4_hand_constructed_fake_same_resolution_is_rejected_even_if_self_hashed() -> None:
    walls, identities, universe, _, genuine, _ = _same_wall_equivalence_fixture()
    fake = PhysicalWallEquivalenceResolution(
        scope_viewport_id="vp",
        representative_wall_ids=("w2",),
        abstained_wall_ids=("w1",),
        equivalence_groups=(("w1", "w2"),),
        ambiguous_wall_ids=(),
        same_wall_ids=("w1", "w2"),
        pair_classifications=(("w1", "w2", "same_physical_wall"),),
        blocking_reasons_by_wall_id={"w1": ("equivalent_physical_wall_represented_by:w2",)},
    )
    fake_bound = bind_resolution_fingerprint(
        fake,
        scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        candidate_universe=universe,
        identities=identities,
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )
    assert fake != genuine
    result = _verify_resolution(fake, fake_bound, identities, universe, walls)
    assert result.status == AuthorityBindingStatus.MISMATCH


def test_c4_genuine_resolution_with_member_removed_is_rejected() -> None:
    walls, identities, universe, _, resolution, bound = _same_wall_equivalence_fixture()
    result = _verify_resolution(resolution, bound, identities[:1], universe, walls[:1])
    assert result.status == AuthorityBindingStatus.MISMATCH


def test_c4_genuine_resolution_with_member_added_is_rejected() -> None:
    walls, identities, universe, _, resolution, bound = _same_wall_equivalence_fixture()
    c = _wall("w3", y=20.0)
    added_identities = identities + (_identity(c),)
    result = _verify_resolution(resolution, bound, added_identities, universe, walls + (c,))
    assert result.status == AuthorityBindingStatus.MISMATCH


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("graph_snapshot_id", "graph-new"),
        ("evidence_snapshot_id", "evsnap-new"),
        ("revision_id", "R2"),
        ("viewport_id", "vp-other"),
    ),
)
def test_c4_resolution_reuse_under_changed_scope_is_stale_or_mismatch(field: str, value: str) -> None:
    walls, identities, universe, _, resolution, bound = _same_wall_equivalence_fixture()
    scope = replace(_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES), **{field: value})
    result = _verify_resolution(resolution, bound, identities, universe, walls, scope=scope)
    assert result.status in {AuthorityBindingStatus.STALE, AuthorityBindingStatus.MISMATCH}


def test_c4_representative_mutation_is_rejected() -> None:
    walls, identities, universe, _, resolution, bound = _same_wall_equivalence_fixture()
    mutated = replace(resolution, representative_wall_ids=tuple(reversed(resolution.representative_wall_ids)))
    if mutated.representative_wall_ids == resolution.representative_wall_ids:
        mutated = replace(resolution, representative_wall_ids=("w2",))
    assert _verify_resolution(mutated, bound, identities, universe, walls).status == AuthorityBindingStatus.MISMATCH


def test_c4_semantic_order_permutation_remains_authentic() -> None:
    walls, identities, universe, _, resolution, _ = _same_wall_equivalence_fixture()
    reordered = replace(
        resolution,
        equivalence_groups=tuple(tuple(reversed(group)) for group in reversed(resolution.equivalence_groups)),
        pair_classifications=tuple(reversed(resolution.pair_classifications)),
        same_wall_ids=tuple(reversed(resolution.same_wall_ids)),
    )
    reordered_bound = bind_resolution_fingerprint(
        reordered,
        scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        candidate_universe=universe,
        identities=tuple(reversed(identities)),
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )
    result = _verify_resolution(reordered, reordered_bound, tuple(reversed(identities)), universe, walls)
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_c4_provenance_mutation_rejects_old_bound_resolution() -> None:
    walls, identities, universe, _, resolution, bound = _same_wall_equivalence_fixture()
    mutated_identity = replace(
        identities[0],
        source_primitive_ids=(*identities[0].source_primitive_ids, "late-provenance"),
    )
    mutated_identities = (mutated_identity, identities[1])
    mutated_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        tuple(physical_wall_identity_member(item) for item in mutated_identities),
    )
    result = _verify_resolution(resolution, bound, mutated_identities, mutated_universe, walls)
    assert result.status == AuthorityBindingStatus.MISMATCH


def test_c4_unbound_resolution_cannot_authorize_publication() -> None:
    kwargs = _firm_single_kwargs()
    kwargs["equivalence_binding"] = None
    _assert_blocked(
        build_wall_length_quantity(**kwargs),
        "physical_equivalence_authenticity_unproven",
    )


# C5 --------------------------------------------------------------------------


def _batch_inputs(walls: tuple[WallCandidate, ...], identities=None):
    """Legacy-shaped public-boundary batch inputs; intentionally no snapshot payload."""
    resolved_identities = tuple(identities or tuple(_identity(wall) for wall in walls))
    atoms = tuple(atom for wall in walls for atom in _atoms(wall.candidate_id))
    document = _document(tuple(atom.evidence_id for atom in atoms))
    entities = {
        wall.candidate_id: _entity(wall, document, _atoms(wall.candidate_id))
        for wall in walls
    }
    scale_binding = _binding(100.0)
    scale_universe, scale_manifest = _scale_proof((scale_binding,))
    candidate_universe, candidate_manifest = _candidate_proof(resolved_identities)
    kwargs = dict(
        walls=walls,
        entities_by_wall_id=entities,
        evidence_atoms=atoms,
        physical_identities={item.wall_candidate_id: item for item in resolved_identities},
        physical_identity_universe=resolved_identities,
        context=_context(),
        document=document,
        viewport=_viewport(resolved_scale_id=scale_binding.scale_fingerprint),
        page_no=1,
        scale_bindings=(scale_binding,),
        scale_universe=scale_universe,
        scale_manifest=scale_manifest,
        candidate_universe=candidate_universe,
        candidate_manifest=candidate_manifest,
    )
    _install_scale_enumerator(kwargs, scale_universe)
    _install_candidate_enumerator(kwargs, candidate_universe)
    return kwargs


def test_c5_hidden_competing_wall_is_detected_below_public_boundary() -> None:
    admitted = _identity(_wall("w1"))
    hidden = _identity(_wall("w2", y=2.0))
    universe, manifest = _candidate_proof((admitted, hidden))
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        manifest,
        ("w1",),
        snapshot_tag="wall-hidden",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_admitted_set_mismatch" in result.reasons


def test_c5_omitted_duplicate_candidate_is_detected() -> None:
    admitted = _identity(_wall("w1"), lineage="native-w1")
    duplicate = _identity(_wall("w2", y=0.0), lineage="native-w1")
    universe, manifest = _candidate_proof((admitted, duplicate))
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        manifest,
        ("w1",),
        snapshot_tag="wall-duplicate-omitted",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_admitted_set_mismatch" in result.reasons


def test_c5_unresolved_candidate_blocks() -> None:
    identity = _identity(_wall("w1"))
    unresolved = AuthorityUniverseMember("w-unresolved", canonical_sha256({"candidate": "w-unresolved"}))
    universe, manifest = _candidate_proof(
        (identity,),
        extra_members=(unresolved,),
        admitted_ids=("w1",),
        unresolved_ids=("w-unresolved",),
    )
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        manifest,
        ("w1",),
        snapshot_tag="wall-unresolved",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_unresolved_candidates" in result.reasons


def test_c5_silent_exclusion_is_rejected_by_manifest_builder() -> None:
    w1 = _identity(_wall("w1"))
    w2 = _identity(_wall("w2", y=20.0))
    universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (physical_wall_identity_member(w1), physical_wall_identity_member(w2)),
    )
    with pytest.raises(ValueError, match="partition_incomplete"):
        build_completeness_manifest(universe, admitted_candidate_ids=("w1",))


def test_c5_explicit_evidenced_exclusion_authenticates_unrelated_wall_removal() -> None:
    identity = _identity(_wall("w1"))
    excluded_identity = _identity(_wall("w2", y=100.0))
    universe, manifest = _candidate_proof(
        (identity, excluded_identity),
        admitted_ids=("w1",),
        exclusions=(ExplicitExclusion("w2", "outside_local_wall_scope", ("scope-ev",)),),
    )
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        manifest,
        ("w1",),
        snapshot_tag="wall-exclusion",
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC
    assert result.authentic


def test_c5_candidate_added_after_manifest_creation_blocks() -> None:
    identity = _identity(_wall("w1"))
    old_universe, old_manifest = _candidate_proof((identity,))
    late = _identity(_wall("w2", y=20.0))
    current_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (physical_wall_identity_member(identity), physical_wall_identity_member(late)),
    )
    assert current_universe.fingerprint != old_universe.fingerprint
    result = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        current_universe,
        old_manifest,
        ("w1",),
        snapshot_tag="wall-added-after-manifest",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "manifest_not_bound_to_enumerator_commitment" in result.reasons


def test_c5_candidate_removed_after_enumeration_is_stale() -> None:
    w1 = _identity(_wall("w1"))
    w2 = _identity(_wall("w2", y=20.0))
    old_universe, _old_manifest = _candidate_proof((w1, w2))
    commitment, snapshot_id, _old_snapshot_fp, _ = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        old_universe,
        snapshot_tag="wall-pre-removal",
    )
    current_universe, current_manifest = _candidate_proof((w1,))
    current_payload = _snapshot_payload(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES, current_universe)
    current_fp = immutable_snapshot_fingerprint(current_payload)
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=current_fp,
        current_enumerated_universe=current_universe,
        manifest=current_manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=current_payload,
    )
    assert result.status == AuthorityBindingStatus.STALE
    assert "enumerator_upstream_snapshot_fingerprint_stale" in result.reasons


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("graph_snapshot_id", "graph-old"),
        ("evidence_snapshot_id", "evsnap-old"),
        ("document_id", "doc-other"),
        ("viewport_id", "vp-other"),
    ),
)
def test_c5_stale_or_wrong_candidate_scope_blocks(field: str, value: str) -> None:
    identity = _identity(_wall("w1"))
    scope = replace(_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES), **{field: value})
    universe, manifest = _candidate_proof((identity,), scope=scope)
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        snapshot_tag="wall-stale-scope",
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=_snapshot_payload(
            DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
            current,
        ),
    )
    assert result.status in {AuthorityBindingStatus.STALE, AuthorityBindingStatus.MISMATCH}


def test_c5_duplicate_candidate_ids_fail_closed() -> None:
    member = physical_wall_identity_member(_identity(_wall("w1")))
    with pytest.raises(ValueError, match="duplicate_authority_universe_candidate_id"):
        build_authority_universe(
            _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
            (member, member),
        )


def test_c5_candidate_order_does_not_change_universe_or_manifest_hash() -> None:
    identities = (
        _identity(_wall("w1")),
        _identity(_wall("w2", y=20.0)),
        _identity(_wall("w3", y=40.0)),
    )
    fingerprints = set()
    manifests = set()
    for ordered in permutations(identities):
        universe, manifest = _candidate_proof(tuple(ordered))
        fingerprints.add(universe.fingerprint)
        manifests.add(manifest.manifest_fingerprint)
    assert len(fingerprints) == 1
    assert len(manifests) == 1


def test_c5_scope_domain_mismatch_blocks() -> None:
    identity = _identity(_wall("w1"))
    wrong_scope = _scope(DOMAIN_WALL_LENGTH_SCALE)
    universe, manifest = _candidate_proof((identity,), scope=wrong_scope)
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        snapshot_tag="wall-wrong-domain",
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=_snapshot_payload(
            DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
            current,
        ),
    )
    assert result.status == AuthorityBindingStatus.MISMATCH


def test_c5_candidate_outside_local_viewport_does_not_poison_local_identity_scope() -> None:
    local_identity = _identity(_wall("w1"))
    outside_identity = _identity(_wall("w-outside", y=50.0, viewport_id="vp-other"))
    local = _local_physical_identities((local_identity, outside_identity), "vp")
    assert tuple(item.wall_candidate_id for item in local) == ("w1",)


def test_c5_conflict_addition_monotonicity_never_strengthens() -> None:
    identity = _identity(_wall("w1"))
    baseline_universe, baseline_manifest = _candidate_proof((identity,))
    baseline = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        baseline_universe,
        baseline_manifest,
        ("w1",),
        snapshot_tag="wall-monotonic-baseline",
    )
    assert baseline.status == AuthorityBindingStatus.AUTHENTIC

    late = AuthorityUniverseMember("w-late", canonical_sha256({"late": True}))
    universe, manifest = _candidate_proof(
        (identity,),
        extra_members=(late,),
        admitted_ids=("w1",),
        unresolved_ids=("w-late",),
    )
    degraded = _verify_enumerator_current(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        manifest,
        ("w1",),
        snapshot_tag="wall-monotonic-conflict",
    )
    assert degraded.status == AuthorityBindingStatus.MISMATCH
    assert "authority_universe_unresolved_candidates" in degraded.reasons


def test_explicit_exclusion_evidence_removal_cannot_strengthen() -> None:
    identity = _identity(_wall("w1"))
    excluded = AuthorityUniverseMember("w2", canonical_sha256({"w": 2}))
    universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (physical_wall_identity_member(identity), excluded),
    )
    with pytest.raises(ValueError, match="requires_reason_and_evidence"):
        build_completeness_manifest(
            universe,
            admitted_candidate_ids=("w1",),
            explicit_exclusions=(ExplicitExclusion("w2", "excluded", ()),),
        )


def test_canonical_hash_rejects_unordered_set_identity_inputs() -> None:
    with pytest.raises(TypeError, match="unordered sets"):
        canonical_sha256({"forbidden": {"a", "b"}})
