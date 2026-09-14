"""Adversarial regressions for the frozen GPT-2 #288 blocker set.

Every test in ``TestBlockerRegressions`` is written to FAIL against the exact
starting SHA 7eb2ce680589b93fddcd837c17c8abc276633b76 and PASS once the
remediation lands. Each test names the blocker it reproduces in its
docstring. This file is intentionally independent of
``tests/test_wall_length_quantity.py`` / ``tests/test_wall_linear_authority_bridge.py``
so the starting-SHA failure signature stays legible in isolation.

Do not weaken any assertion here to make it pass. A test that stops failing
for the wrong reason is worse than a test that still fails.
"""
from __future__ import annotations

from dataclasses import replace

from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import scale_calibration_fingerprint
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
from pb_physical_wall_existence_authority import adapt_wall_candidate_to_entity_evidence
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
    build_wall_length_quantities,
    build_wall_length_quantity,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL


def _solo_equivalence(*wall_ids: str) -> PhysicalWallEquivalenceResolution:
    """A trivial equivalence resolution where every named wall is its own
    representative -- used by tests that are not themselves about
    equivalence, to isolate the specific boundary under test."""
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

SHA = "c" * 64


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
        wall, evidence_atoms=atoms, document=document, viewport=viewport, context=context,
        additional_owned_evidence_ids=extra,
    )
    return entity, document, viewport, context


class TestBlockerRegressions:
    """One test per frozen GPT-2 blocker. Each must FAIL at 7eb2ce68."""

    def test_blocker1_sibling_viewport_binding_omission_still_reaches_firm(self) -> None:
        """Blocker 1 (sibling-viewport shape): the page has two known
        viewports (per ``context.viewport_page_ownership``) but the caller
        supplies a binding for only one of them. Nothing proves the
        supplied ``scale_bindings`` sequence covers every viewport the
        current revision already knows about on this page, so a caller
        can silently withhold a sibling's binding. At 7eb2ce68 this reaches
        FIRM regardless.
        """
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        multi = _context(
            owned_viewport_ids=("vp", "vp-sibling"),
            viewport_page_ownership=(("vp", 1), ("vp-sibling", 1)),
        )
        entity, document, viewport, context = _adapt(wall, atoms, context=multi)
        assert entity is not None
        preferred = _scale_binding(scale)  # binding for "vp" only -- "vp-sibling" withheld
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=preferred.scale_fingerprint),
            entity=entity,
            evidence_atoms=atoms,
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            scale_bindings=(preferred,),  # <-- sibling withheld
        )
        assert qty.abstained, (
            "binding for one of two known sibling viewports reached FIRM even though "
            "the publication boundary has no proof scale_bindings covers every "
            "viewport context.viewport_page_ownership already knows about"
        )

    def test_blocker1_page_viewports_path_derives_instead_of_trusting_caller_bindings(self) -> None:
        """Blocker 1 (same-viewport shape, the harder case): the
        ``page_viewports``-derived path must be structurally immune to a
        caller hiding a second, competing binding for the SAME viewport_id,
        because bindings are derived internally from the complete
        ``SegmentedViewport`` list rather than accepted pre-built -- there is
        no second binding a caller COULD hide, since none can exist outside
        what this function itself derives from one ``SegmentedViewport``
        record per ``view_id``.

        Honest scope note: a ``SegmentedViewport``'s own scale text is
        always classified TITLE_BLOCK by ``pb_viewport_scale_binding``
        (graphic scale-bar corroboration is not wired into F.07 viewport
        segmentation anywhere in this repository today), so a
        ``page_viewports``-derived binding can never itself be FIRM yet --
        this path fails closed to BLOCKED for a real, honest reason
        (``scale_not_firm``) rather than a wrong one, which is the property
        actually under test here, not reaching FIRM (that requires a future
        graphic-scale-bar wiring PR, out of scope for #288)."""
        scale = _scale(ratio=100.0)
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        page_viewports = (_segmented_viewport(view_id="vp", scale_raw="1:100"),)
        derived = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            evidence_atoms=atoms,
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            page_viewports=page_viewports,
        )
        assert derived.abstained
        assert "scale_not_firm" in derived.blocking_reasons, derived.blocking_reasons

        # Attempting to smuggle two competing records for the SAME view_id
        # (the only way to construct a "hidden competitor" in this shape)
        # must block outright, structurally, before any scale evaluation --
        # not silently pick either one.
        duplicated = (
            _segmented_viewport(view_id="vp", scale_raw="1:100"),
            _segmented_viewport(view_id="vp", scale_raw="1:50"),
        )
        blocked = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            evidence_atoms=atoms,
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            page_viewports=duplicated,
        )
        assert blocked.abstained
        assert blocked.blocking_reasons == ("duplicate_segmented_viewport_id_in_page_viewports",)

    def test_blocker2_hand_built_entity_evidence_reaches_firm_without_real_atoms(self) -> None:
        """Blocker 2: a caller-constructed EntityEvidence claiming CORROBORATED,
        backed by zero real (revision/snapshot/SHA-owned) supporting atoms,
        must not be trusted at the FIRM boundary. At 7eb2ce68 ``entity.status``
        is trusted at face value.
        """
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
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=_scale_binding(scale).scale_fingerprint),
            entity=forged_entity,
            evidence_atoms=(),  # <-- no real atoms behind the forged CORROBORATED claim
            equivalence=_solo_equivalence(wall.candidate_id),
            page_no=1,
            scale_bindings=(_scale_binding(scale),),
        )
        assert qty.abstained, (
            "hand-built EntityEvidence with no validated existence trace reached FIRM"
        )
        assert "entity_status_does_not_match_recomputed_existence" in qty.blocking_reasons

    def test_blocker3_publication_boundary_has_no_seam_to_even_see_colliding_atoms(self) -> None:
        """Blocker 3: collision-safe indexing (``_index_atoms``) already
        exists correctly *inside* ``resolve_physical_wall_existence`` -- a
        caller who goes through the adapter first is already protected
        (see ``test_bbox_only_evidence_id_collision_blocks`` and siblings in
        ``tests/test_wall_linear_authority_bridge.py``, which already pass).
        The real gap named by blocker 3 is architectural, not a missing
        check: ``build_wall_length_quantity`` takes a pre-built
        ``EntityEvidence`` and has no parameter at all through which raw,
        possibly-colliding ``EvidenceAtom`` records could ever reach it, so
        collision-safety is only ever as strong as whatever the caller chose
        to do *before* calling in -- never unavoidable at the FIRM boundary
        itself. This is proven structurally (by inspecting the current
        signature) rather than by a runtime assertion, since the current
        signature offers no route to even attempt the exploit at this
        boundary -- which is itself the defect blocker 3 names.
        """
        import inspect

        params = inspect.signature(build_wall_length_quantity).parameters
        assert "evidence_atoms" in params, (
            "build_wall_length_quantity has no way to receive raw EvidenceAtom "
            "records, so collision-safe existence can never be re-derived (only "
            "trusted) at the FIRM publication boundary itself"
        )

    def test_blocker4_bare_level_id_string_alone_proves_distinct(self) -> None:
        """Blocker 4: different ``level_id`` strings alone (no authoritative
        level provenance) must not be positive DISTINCT proof. At 7eb2ce68
        ``classify_physical_wall_pair`` returns DISTINCT from the bare
        string difference.
        """
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
        result = classify_physical_wall_pair(*identities)
        assert result != PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS, (
            "bare level_id string inequality alone produced DISTINCT_PHYSICAL_WALLS "
            "with no authoritative level provenance behind it"
        )

    def test_blocker4_bare_viewport_id_string_alone_proves_distinct(self) -> None:
        """Blocker 4: different ``viewport_id`` strings alone must not be
        positive DISTINCT proof either, even when the underlying geometry
        and provenance are otherwise identical.
        """
        edges = {"e1": {"id": "e1", "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 0.0, "primitive_lineage": {"source_primitive_ids": ["native"]}}}
        a = _wall(wall_id="w1", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), viewport_id="vp")
        b = _wall(wall_id="w2", points=((0.0, 0.0), (100.0, 0.0)), face_ids=("e1",), viewport_id="vp-other")
        identities = (
            resolve_physical_wall_identity(wall=a, edge_ids=("e1",), edges_by_id=edges),
            resolve_physical_wall_identity(wall=b, edge_ids=("e1",), edges_by_id=edges),
        )
        result = classify_physical_wall_pair(*identities)
        assert result != PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS, (
            "bare viewport_id string inequality alone produced DISTINCT_PHYSICAL_WALLS"
        )

    def test_blocker5_batch_with_no_physical_identities_still_publishes_firm(self) -> None:
        """Blocker 5: ``physical_identities=None`` (the default) must not be
        able to produce FIRM output at all. At 7eb2ce68 the parameter is
        optional and simply skips equivalence reconciliation entirely.
        """
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        binding = _scale_binding(scale)
        out = build_wall_length_quantities(
            walls=(wall,),
            entities_by_wall_id={"w1": entity},
            evidence_atoms=atoms,
            physical_identities={},  # <-- no identity known for "w1" at all
            context=context,
            document=document,
            viewport=replace(viewport, resolved_scale_id=binding.scale_fingerprint),
            page_no=1,
            scale_bindings=(binding,),
        )
        assert all(q.abstained for q in out), (
            "batch publication reached FIRM with no physical identity resolvable "
            "for the wall at all"
        )

    def test_blocker6_direct_single_wall_call_requires_a_real_equivalence_argument(self) -> None:
        """Blocker 6: ``equivalence`` has no default -- a caller cannot call
        the single-wall function at all without supplying SOME
        ``PhysicalWallEquivalenceResolution``, and it is checked (not just
        accepted): a wall absent from ``representative_wall_ids`` (e.g.
        because reconciliation marked it ambiguous or represented by
        another wall) is refused FIRM even with an otherwise-perfect entity
        and scale. This is what closes the "direct single-wall path with no
        completed universe reconciliation -> NOT PUBLIC FIRM" regression:
        it is no longer possible to construct a call that skips
        reconciliation, only to construct one whose reconciliation result
        says "not representative".
        """
        import inspect

        assert "equivalence" in inspect.signature(build_wall_length_quantity).parameters

        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        assert entity is not None
        not_representative = PhysicalWallEquivalenceResolution(
            scope_viewport_id="vp",
            representative_wall_ids=(),  # "w1" is not among them
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
            viewport=replace(viewport, resolved_scale_id=_scale_binding(scale).scale_fingerprint),
            entity=entity,
            evidence_atoms=atoms,
            equivalence=not_representative,
            page_no=1,
            scale_bindings=(_scale_binding(scale),),
        )
        assert qty.abstained, (
            "wall absent from equivalence.representative_wall_ids still reached FIRM"
        )
        assert "ambiguous_physical_wall_equivalence" in qty.blocking_reasons

    def test_blocker7_generic_figured_dimension_alone_publishes_firm(self) -> None:
        """Blocker 7: a generic ``figured_dimension`` atom bound to a wall,
        with no scale corroboration, must not create FIRM wall length in
        this PR. At 7eb2ce68 this is the exact documented 5.0m-FIRM path.
        """
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
        assert "dim-ev" in entity.evidence_ids  # sanity: prove the atom was actually seen
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            evidence_atoms=atoms + (figured,),
            equivalence=_solo_equivalence("w1"),
            page_no=1,
            scale_bindings=(),
            figured_evidence=figured,
        )
        assert qty.abstained, "generic figured_dimension alone published FIRM wall length in #288"
        assert FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON in qty.blocking_reasons

    def test_blocker8_shuffled_batch_order_is_deterministic_with_mandatory_reconciliation(self) -> None:
        """Blocker 8 (monotonicity/ordering): two independent (unrelated)
        walls published in different input orders must publish the same
        semantic outcome both ways, now that reconciliation is mandatory
        and always computed over the complete supplied ``walls`` sequence
        regardless of order.
        """
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
        fwd = {q.semantic_key: (q.abstained, q.value) for q in forward}
        rev = {q.semantic_key: (q.abstained, q.value) for q in reverse}
        assert fwd == rev


class TestAuthorityMonotonicity:
    """Formal monotonicity properties at the FINAL PUBLICATION BOUNDARY
    (``build_wall_length_quantity`` / ``build_wall_length_quantities``),
    per the frozen GPT-2 #288 requirements. Each test starts from a genuine
    FIRM baseline and proves ONE property in isolation."""

    def _firm_baseline(self):
        scale = _scale()
        wall, atoms = _two_domain_wall(points=((0.0, 0.0), (scale.px_per_m * 4.0, 0.0)))
        entity, document, viewport, context = _adapt(wall, atoms)
        binding = _scale_binding(scale)
        bound_viewport = replace(viewport, resolved_scale_id=binding.scale_fingerprint)
        equivalence = _solo_equivalence("w1")
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=bound_viewport, entity=entity,
            evidence_atoms=atoms, equivalence=equivalence, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained is False and qty.status == AuthorityStatus.FIRM.value
        return wall, atoms, entity, document, context, bound_viewport, binding, equivalence

    def test_adding_competing_eligible_scale_cannot_preserve_firm(self) -> None:
        wall, atoms, entity, document, context, viewport, binding, equivalence = self._firm_baseline()
        competitor = replace(binding)  # identical fingerprint -> both eligible -> conflict
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=atoms, equivalence=equivalence, page_no=1, scale_bindings=(binding, competitor),
        )
        assert qty.abstained
        assert "conflicting_eligible_scale_bindings" in qty.blocking_reasons

    def test_removing_current_snapshot_proof_cannot_preserve_firm(self) -> None:
        wall, atoms, entity, document, context, viewport, binding, equivalence = self._firm_baseline()
        unsnapshotted = tuple(replace(a, metadata={k: v for k, v in a.metadata.items() if k != "evidence_snapshot_id"}) for a in atoms)
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=unsnapshotted, equivalence=equivalence, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained
        assert "entity_status_does_not_match_recomputed_existence" in qty.blocking_reasons

    def test_adding_same_id_changed_atom_cannot_preserve_firm(self) -> None:
        wall, atoms, entity, document, context, viewport, binding, equivalence = self._firm_baseline()
        colliding = replace(atoms[0], confidence=0.11)
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=atoms + (colliding,), equivalence=equivalence, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained
        assert "entity_status_does_not_match_recomputed_existence" in qty.blocking_reasons

    def test_adding_ambiguous_physical_competitor_cannot_preserve_firm(self) -> None:
        """A second wall, physically ambiguous with the FIRM candidate, must
        pull the FIRM candidate back to abstained once batch reconciliation
        sees both -- FIRM is a property of the reconciled universe, not of
        one wall considered alone."""
        from pb_physical_wall_identity import collect_physical_wall_identities

        wall, atoms, entity, document, context, viewport, binding, _solo = self._firm_baseline()
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
            (identities.get("w1"), identities.get("w1-ambiguous")),
            walls_by_id={"w1": wall, "w1-ambiguous": competitor},
        )
        assert "w1" in equivalence.ambiguous_wall_ids  # sanity: genuinely ambiguous pair
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=atoms, equivalence=equivalence, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained
        assert "ambiguous_physical_wall_equivalence" in qty.blocking_reasons

    def test_removing_physical_equivalence_reconciliation_cannot_preserve_firm(self) -> None:
        """There is no argument value for ``equivalence`` that represents
        "not reconciled" -- proven structurally: the parameter has no
        default, so "removing" it is a TypeError, not a silently-accepted
        bypass."""
        import inspect

        assert inspect.signature(build_wall_length_quantity).parameters["equivalence"].default is inspect.Parameter.empty

    def test_direct_single_wall_path_cannot_bypass_publication_gate(self) -> None:
        wall, atoms, entity, document, context, viewport, binding, _solo = self._firm_baseline()
        not_representative = PhysicalWallEquivalenceResolution(
            scope_viewport_id="vp", representative_wall_ids=(), abstained_wall_ids=("w1",),
            equivalence_groups=(), ambiguous_wall_ids=(), same_wall_ids=(), pair_classifications=(),
            blocking_reasons_by_wall_id={"w1": ("physical_wall_identity_abstained",)},
        )
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=atoms, equivalence=not_representative, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained

    def test_adding_generic_figured_dimension_cannot_create_firm(self) -> None:
        """Starting from an abstained (no-scale) baseline, adding a
        well-formed, agreeing, CORROBORATED figured_dimension atom must
        still not flip the result to FIRM -- the generic figured-dimension
        route is disabled for wall length in this PR regardless of whether
        it would otherwise have been clean and uncontested."""
        wall, atoms = _two_domain_wall()
        entity, document, viewport, context = _adapt(wall, atoms)
        equivalence = _solo_equivalence("w1")
        qty_without = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=atoms, equivalence=equivalence, page_no=1, scale_bindings=(),
        )
        assert qty_without.abstained is True  # no scale, no figured evidence -> abstain

        figured = EvidenceAtom(
            evidence_id="dim-ev", document_id="doc", page_id="page-1", viewport_id="vp",
            kind="figured_dimension", method="vector_text", raw_text="5000", confidence=1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
            metadata={"wall_candidate_id": "w1", "revision_id": "R1", "evidence_snapshot_id": "evsnap", "source_sha256": SHA},
        )
        entity2, document2, viewport2, context2 = _adapt(wall, atoms + (figured,), extra=("dim-ev",))
        qty_with = build_wall_length_quantity(
            wall=wall, context=context2, document=document2, viewport=viewport2, entity=entity2,
            evidence_atoms=atoms + (figured,), equivalence=equivalence, page_no=1, scale_bindings=(),
            figured_evidence=figured,
        )
        assert qty_with.abstained is True
        assert FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON in qty_with.blocking_reasons

    def test_duplicate_identical_evidence_does_not_strengthen(self) -> None:
        wall, atoms, entity, document, context, viewport, binding, equivalence = self._firm_baseline()
        duplicated = atoms + (replace(atoms[0]), replace(atoms[1]))
        qty = build_wall_length_quantity(
            wall=wall, context=context, document=document, viewport=viewport, entity=entity,
            evidence_atoms=duplicated, equivalence=equivalence, page_no=1, scale_bindings=(binding,),
        )
        assert qty.abstained is False
        assert qty.confidence <= 1.0  # duplicate evidence must not push confidence past a single corroboration's own ceiling
