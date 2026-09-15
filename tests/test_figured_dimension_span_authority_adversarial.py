"""Adversarial contract tests for pb_figured_dimension_span_authority.py.

Each test is numbered against the 20 required adversarial scenarios from the
"EXACT FIGURED-DIMENSION SPAN AUTHORITY" mandate, followed by the required
formal monotonicity properties, followed by a production-wiring guard.

Fixture idiom (ProviderContext/DocumentEvidence/ViewportEvidence/EntityEvidence/
EvidenceAtom construction) mirrors tests/test_measurement_input_authority.py
exactly, since this module sits directly on top of that existing authority
chain and must not invent a second ownership vocabulary.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from pb_figured_dimension_span_authority import (
    DimensionSpanCandidate,
    EndpointReference,
    EndpointReferenceKind,
    SemanticSpanKind,
    SpanClassification,
    classify_candidate_pair,
    resolve_figured_dimension_span_authority,
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

SHA = "a" * 64


def _context(*, revision: str = "R1") -> ProviderContext:
    return ProviderContext(
        run_id="run-1",
        workspace_id="ws-1",
        project_id="project-1",
        document_id="doc-1",
        source_sha256=SHA,
        revision_id=revision,
        current_revision_id=revision,
        selected_pages=(0,),
        owned_viewport_ids=("vp-1",),
        evidence_snapshot_id="ev-snap-1",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-1", 1),),
    )


def _document(*evidence_ids: str) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc-1",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=tuple(evidence_ids),
        producer="test",
        producer_version="1",
    )


def _viewport(viewport_id: str = "vp-1") -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc-1",
        page_id="page-1",
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def _entity(entity_id: str, *evidence_ids: str) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=entity_id,
        candidate_type="wall",
        evidence_ids=tuple(evidence_ids),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _figured_atom(evidence_id: str, text: str = "6500", *, viewport_id: str = "vp-1") -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc-1",
        page_id="page-1",
        viewport_id=viewport_id,
        kind="figured_dimension",
        method="vector_text",
        raw_text=text,
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def _ep(kind: EndpointReferenceKind, target_id: str, sub: str = None) -> EndpointReference:
    return EndpointReference(kind=kind, target_id=target_id, subreference=sub)


_UNSET = object()  # sentinel: "caller did not specify" -- distinct from an
                    # explicitly-passed None, which means "unresolved endpoint"


def _candidate(
    candidate_id: str,
    *,
    dimension_system_id: str = None,
    target_entity_id: str = "wall-1",
    kind: SemanticSpanKind = SemanticSpanKind.WALL_RUN,
    value_m: float = 6.5,
    endpoint_a=_UNSET,
    endpoint_b=_UNSET,
    text_evidence_id: str = None,
    dimension_line_id: str = "dimline-1",
    witness_line_ids=("w1", "w2"),
    viewport_id: str = "vp-1",
    revision_id: str = "R1",
    evidence_status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE,
) -> DimensionSpanCandidate:
    if endpoint_a is _UNSET:
        endpoint_a = _ep(EndpointReferenceKind.FACE, target_entity_id, "face_a")
    if endpoint_b is _UNSET:
        endpoint_b = _ep(EndpointReferenceKind.FACE, target_entity_id, "face_b")
    return DimensionSpanCandidate(
        candidate_id=candidate_id,
        document_id="doc-1",
        page_id="page-1",
        viewport_id=viewport_id,
        revision_id=revision_id,
        dimension_system_id=dimension_system_id or f"dimsys-{candidate_id}",
        text_evidence_id=text_evidence_id or f"ev-{candidate_id}",
        dimension_line_id=dimension_line_id,
        witness_line_ids=tuple(witness_line_ids),
        endpoint_a=endpoint_a,
        endpoint_b=endpoint_b,
        target_entity_id=target_entity_id,
        semantic_span_kind=kind,
        value_m=value_m,
        evidence_status=evidence_status,
    )


def _resolve(
    *,
    target_entity_id="wall-1",
    kind=SemanticSpanKind.WALL_RUN,
    candidates,
    atoms,
    context=None,
    entity_evidence_ids=None,
    doc_evidence_ids=None,
):
    ctx = context or _context()
    atom_ids = [a.evidence_id for a in atoms]
    doc = _document(*(doc_evidence_ids if doc_evidence_ids is not None else atom_ids))
    ent = _entity(target_entity_id, *(entity_evidence_ids if entity_evidence_ids is not None else atom_ids))
    return resolve_figured_dimension_span_authority(
        target_entity_id=target_entity_id,
        semantic_span_kind=kind,
        candidates=candidates,
        context=ctx,
        document=doc,
        viewport=_viewport(),
        entity=ent,
        page_no=1,
        evidence_atoms_by_id={a.evidence_id: a for a in atoms},
    )


# ---------------------------------------------------------------------------
# 1. room-clear dimension beside wall run
# ---------------------------------------------------------------------------
def test_01_room_clear_dimension_beside_wall_run_does_not_contaminate_wall():
    wall_atom = _figured_atom("ev-wall", "6500")
    room_atom = _figured_atom("ev-room", "6350")
    wall_c = _candidate("c-wall", target_entity_id="wall-1", kind=SemanticSpanKind.WALL_RUN,
                         value_m=6.5, text_evidence_id="ev-wall")
    room_c = _candidate("c-room", target_entity_id="room-1", kind=SemanticSpanKind.ROOM_CLEAR_SPAN,
                         value_m=6.35, text_evidence_id="ev-room",
                         endpoint_a=_ep(EndpointReferenceKind.CORNER, "room-1", "nw"),
                         endpoint_b=_ep(EndpointReferenceKind.CORNER, "room-1", "ne"))
    result = _resolve(candidates=[wall_c, room_c], atoms=[wall_atom, room_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)
    assert result.contributing_candidate_ids == ("c-wall",)


# ---------------------------------------------------------------------------
# 2. wall thickness dimension
# ---------------------------------------------------------------------------
def test_02_wall_thickness_dimension_never_answers_a_wall_run_query():
    run_atom = _figured_atom("ev-run", "6500")
    thick_atom = _figured_atom("ev-thick", "230")
    run_c = _candidate("c-run", kind=SemanticSpanKind.WALL_RUN, value_m=6.5, text_evidence_id="ev-run")
    thick_c = _candidate("c-thick", kind=SemanticSpanKind.WALL_THICKNESS, value_m=0.23,
                          text_evidence_id="ev-thick",
                          endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-1", "outer"),
                          endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-1", "inner"))
    result = _resolve(candidates=[run_c, thick_c], atoms=[run_atom, thick_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)
    assert ("dimsys-c-thick", "non_applicable_semantic_kind") in result.completeness.dimension_systems_rejected


# ---------------------------------------------------------------------------
# 3. door width dimension
# ---------------------------------------------------------------------------
def test_03_door_width_dimension_distinct_target_ignored_for_wall_query():
    run_atom = _figured_atom("ev-run", "6500")
    door_atom = _figured_atom("ev-door", "900")
    run_c = _candidate("c-run", kind=SemanticSpanKind.WALL_RUN, value_m=6.5, text_evidence_id="ev-run")
    door_c = _candidate("c-door", target_entity_id="door-1", kind=SemanticSpanKind.OPENING_WIDTH,
                         value_m=0.9, text_evidence_id="ev-door",
                         endpoint_a=_ep(EndpointReferenceKind.JAMB, "door-1", "left"),
                         endpoint_b=_ep(EndpointReferenceKind.JAMB, "door-1", "right"))
    result = _resolve(candidates=[run_c, door_c], atoms=[run_atom, door_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)


# ---------------------------------------------------------------------------
# 4. window width dimension
# ---------------------------------------------------------------------------
def test_04_window_width_dimension_distinct_target_ignored_for_wall_query():
    run_atom = _figured_atom("ev-run", "6500")
    win_atom = _figured_atom("ev-win", "1200")
    run_c = _candidate("c-run", kind=SemanticSpanKind.WALL_RUN, value_m=6.5, text_evidence_id="ev-run")
    win_c = _candidate("c-win", target_entity_id="window-1", kind=SemanticSpanKind.OPENING_WIDTH,
                        value_m=1.2, text_evidence_id="ev-win",
                        endpoint_a=_ep(EndpointReferenceKind.JAMB, "window-1", "left"),
                        endpoint_b=_ep(EndpointReferenceKind.JAMB, "window-1", "right"))
    result = _resolve(candidates=[run_c, win_c], atoms=[run_atom, win_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)


# ---------------------------------------------------------------------------
# 5. grid spacing
# ---------------------------------------------------------------------------
def test_05_grid_spacing_distinct_target_ignored_for_wall_query():
    run_atom = _figured_atom("ev-run", "6500")
    grid_atom = _figured_atom("ev-grid", "6500")  # deliberately identical value
    run_c = _candidate("c-run", kind=SemanticSpanKind.WALL_RUN, value_m=6.5, text_evidence_id="ev-run")
    grid_c = _candidate("c-grid", target_entity_id="grid-A-B", kind=SemanticSpanKind.GRID_SPACING,
                         value_m=6.5, text_evidence_id="ev-grid",
                         endpoint_a=_ep(EndpointReferenceKind.GRID, "grid-A-B", "A"),
                         endpoint_b=_ep(EndpointReferenceKind.GRID, "grid-A-B", "B"))
    result = _resolve(candidates=[run_c, grid_c], atoms=[run_atom, grid_atom])
    assert result.status == "firm"
    assert result.contributing_candidate_ids == ("c-run",)


# ---------------------------------------------------------------------------
# 6. overall building dimension
# ---------------------------------------------------------------------------
def test_06_overall_building_dimension_distinct_target_ignored_for_wall_query():
    run_atom = _figured_atom("ev-run", "6500")
    overall_atom = _figured_atom("ev-overall", "13000")
    run_c = _candidate("c-run", kind=SemanticSpanKind.WALL_RUN, value_m=6.5, text_evidence_id="ev-run")
    overall_c = _candidate("c-overall", target_entity_id="building-envelope",
                            kind=SemanticSpanKind.OVERALL_BUILDING_DIMENSION, value_m=13.0,
                            text_evidence_id="ev-overall",
                            endpoint_a=_ep(EndpointReferenceKind.CORNER, "building-envelope", "sw"),
                            endpoint_b=_ep(EndpointReferenceKind.CORNER, "building-envelope", "se"))
    result = _resolve(candidates=[run_c, overall_c], atoms=[run_atom, overall_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)


# ---------------------------------------------------------------------------
# 7. two equal numbers for different spans
# ---------------------------------------------------------------------------
def test_07_two_equal_numbers_for_different_spans_resolve_independently():
    atom1 = _figured_atom("ev-1", "3000")
    atom2 = _figured_atom("ev-2", "3000")
    c1 = _candidate("c-1", target_entity_id="wall-1", value_m=3.0, text_evidence_id="ev-1")
    c2 = _candidate("c-2", target_entity_id="wall-2", value_m=3.0, text_evidence_id="ev-2",
                     endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-2", "face_a"),
                     endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-2", "face_b"))
    r1 = _resolve(target_entity_id="wall-1", candidates=[c1, c2], atoms=[atom1, atom2])
    r2 = _resolve(target_entity_id="wall-2", candidates=[c1, c2], atoms=[atom1, atom2])
    assert r1.status == "firm" and r1.value_m == pytest.approx(3.0, abs=1e-6)
    assert r2.status == "firm" and r2.value_m == pytest.approx(3.0, abs=1e-6)
    assert classify_candidate_pair(c1, c2) == SpanClassification.DISTINCT_SPAN


# ---------------------------------------------------------------------------
# 8. conflicting dimensions for same span
# ---------------------------------------------------------------------------
def test_08_conflicting_dimensions_for_same_span_abstains():
    atom1 = _figured_atom("ev-1", "3000")
    atom2 = _figured_atom("ev-2", "3500")
    c1 = _candidate("c-1", value_m=3.0, text_evidence_id="ev-1")
    c2 = _candidate("c-2", value_m=3.5, text_evidence_id="ev-2")
    assert classify_candidate_pair(c1, c2) == SpanClassification.NUMERIC_CONFLICT
    result = _resolve(candidates=[c1, c2], atoms=[atom1, atom2])
    assert result.abstained
    assert result.blocking_reasons == ("numeric_conflict_within_same_span",)


# ---------------------------------------------------------------------------
# 9. duplicate identical dimension graphics
# ---------------------------------------------------------------------------
def test_09_duplicate_identical_dimension_graphics_does_not_double_count():
    atom = _figured_atom("ev-1", "6500")
    c1 = _candidate("c-1", dimension_system_id="dimsys-shared", value_m=6.5, text_evidence_id="ev-1")
    c2 = _candidate("c-2", dimension_system_id="dimsys-shared", value_m=6.5, text_evidence_id="ev-1")
    result_one = _resolve(candidates=[c1], atoms=[atom])
    result_two = _resolve(candidates=[c1, c2], atoms=[atom])
    assert result_one.status == result_two.status == "firm"
    assert result_one.value_m == pytest.approx(result_two.value_m, abs=1e-9)


# ---------------------------------------------------------------------------
# 10. reversed dimension-line orientation
# ---------------------------------------------------------------------------
def test_10_reversed_dimension_line_orientation_is_the_same_span():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "6500")
    forward = _candidate(
        "c-fwd", value_m=6.5, text_evidence_id="ev-1",
        endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-1", "face_a"),
        endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-1", "face_b"),
    )
    reversed_ = _candidate(
        "c-rev", dimension_system_id="dimsys-c-rev", value_m=6.5, text_evidence_id="ev-2",
        endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-1", "face_b"),
        endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-1", "face_a"),
    )
    assert forward.endpoint_pair_key() == reversed_.endpoint_pair_key()
    assert classify_candidate_pair(forward, reversed_) == SpanClassification.DUPLICATE_CORROBORATING
    result = _resolve(candidates=[forward, reversed_], atoms=[atom1, atom2])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)


# ---------------------------------------------------------------------------
# 11. dimension text moved but leader/geometry binding preserved
# ---------------------------------------------------------------------------
def test_11_endpoint_coordinate_is_not_identity():
    atom = _figured_atom("ev-1", "6500")
    a1 = EndpointReference(EndpointReferenceKind.FACE, "wall-1", "face_a", coordinate=(0.0, 0.0))
    a2 = EndpointReference(EndpointReferenceKind.FACE, "wall-1", "face_a", coordinate=(999.0, 999.0))
    assert a1 == a2 or a1.identity_key == a2.identity_key
    c_moved = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1", endpoint_a=a2)
    result = _resolve(candidates=[c_moved], atoms=[atom])
    assert result.status == "firm"


# ---------------------------------------------------------------------------
# 12. nearest wrong wall closer than true target
# ---------------------------------------------------------------------------
def test_12_nearest_wrong_wall_never_wins_by_proximity():
    true_atom = _figured_atom("ev-true", "6500")
    near_wrong_atom = _figured_atom("ev-wrong", "6480")
    true_c = _candidate("c-true", target_entity_id="wall-1", value_m=6.5, text_evidence_id="ev-true")
    # References wall-2 explicitly even though (in a real drawing) it might sit
    # physically nearer to wall-1's line than wall-2's own dimension does.
    wrong_c = _candidate("c-wrong", target_entity_id="wall-2", value_m=6.48, text_evidence_id="ev-wrong",
                          endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-2", "face_a"),
                          endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-2", "face_b"))
    result = _resolve(target_entity_id="wall-1", candidates=[true_c, wrong_c], atoms=[true_atom, near_wrong_atom])
    assert result.status == "firm"
    assert result.value_m == pytest.approx(6.5, abs=1e-6)
    assert result.contributing_candidate_ids == ("c-true",)


# ---------------------------------------------------------------------------
# 13. stale revision
# ---------------------------------------------------------------------------
def test_13_stale_revision_fails_closed():
    atom = _figured_atom("ev-1", "6500")
    stale_c = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1", revision_id="R0")
    result = _resolve(candidates=[stale_c], atoms=[atom], context=_context(revision="R1"))
    assert result.abstained
    assert ("dimsys-c-1", "stale_revision") in result.completeness.dimension_systems_rejected


# ---------------------------------------------------------------------------
# 14. sibling viewport
# ---------------------------------------------------------------------------
def test_14_sibling_viewport_evidence_fails_closed():
    atom = _figured_atom("ev-1", "6500", viewport_id="vp-2")
    sibling_c = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1", viewport_id="vp-2")
    result = _resolve(candidates=[sibling_c], atoms=[atom])
    assert result.abstained
    assert ("dimsys-c-1", "sibling_viewport_evidence") in result.completeness.dimension_systems_rejected


# ---------------------------------------------------------------------------
# 15. missing witness (alongside an otherwise-good competing candidate)
# ---------------------------------------------------------------------------
def test_15_missing_witness_blocks_even_a_good_competing_candidate():
    good_atom = _figured_atom("ev-good", "6500")
    weak_atom = _figured_atom("ev-weak", "6500")
    good_c = _candidate("c-good", value_m=6.5, text_evidence_id="ev-good")
    weak_c = _candidate("c-weak", value_m=6.5, text_evidence_id="ev-weak", witness_line_ids=())
    result = _resolve(candidates=[good_c, weak_c], atoms=[good_atom, weak_atom])
    assert result.abstained
    assert result.blocking_reasons == ("unresolved_potentially_applicable_dimension_system",)
    assert "dimsys-c-weak" in result.completeness.dimension_systems_unresolved_potentially_applicable


# ---------------------------------------------------------------------------
# 16. missing terminator (no dimension line at all)
# ---------------------------------------------------------------------------
def test_16_missing_terminator_blocks_even_a_good_competing_candidate():
    good_atom = _figured_atom("ev-good", "6500")
    weak_atom = _figured_atom("ev-weak", "6500")
    good_c = _candidate("c-good", value_m=6.5, text_evidence_id="ev-good")
    weak_c = _candidate("c-weak", value_m=6.5, text_evidence_id="ev-weak", dimension_line_id=None)
    result = _resolve(candidates=[good_c, weak_c], atoms=[good_atom, weak_atom])
    assert result.abstained
    assert "dimsys-c-weak" in result.completeness.dimension_systems_unresolved_potentially_applicable


# ---------------------------------------------------------------------------
# 17. one endpoint unresolved
# ---------------------------------------------------------------------------
def test_17_one_endpoint_unresolved_blocks_even_a_good_competing_candidate():
    good_atom = _figured_atom("ev-good", "6500")
    weak_atom = _figured_atom("ev-weak", "6500")
    good_c = _candidate("c-good", value_m=6.5, text_evidence_id="ev-good")
    weak_c = _candidate("c-weak", value_m=6.5, text_evidence_id="ev-weak", endpoint_b=None)
    result = _resolve(candidates=[good_c, weak_c], atoms=[good_atom, weak_atom])
    assert result.abstained
    assert "dimsys-c-weak" in result.completeness.dimension_systems_unresolved_potentially_applicable


# ---------------------------------------------------------------------------
# 18. both endpoints resolved to wrong semantic references
# ---------------------------------------------------------------------------
def test_18_both_endpoints_resolved_to_wrong_semantic_basis_is_semantic_competition():
    good_atom = _figured_atom("ev-good", "6500")
    wrong_basis_atom = _figured_atom("ev-wrongbasis", "6520")
    good_c = _candidate("c-good", value_m=6.5, text_evidence_id="ev-good")
    wrong_basis_c = _candidate(
        "c-wrongbasis", value_m=6.52, text_evidence_id="ev-wrongbasis",
        endpoint_a=_ep(EndpointReferenceKind.GRID, "wall-1", "grid_a"),
        endpoint_b=_ep(EndpointReferenceKind.GRID, "wall-1", "grid_b"),
    )
    assert classify_candidate_pair(good_c, wrong_basis_c) == SpanClassification.SEMANTIC_COMPETITION
    result = _resolve(candidates=[good_c, wrong_basis_c], atoms=[good_atom, wrong_basis_atom])
    assert result.abstained
    assert result.blocking_reasons == ("semantic_competition_unresolved",)


# ---------------------------------------------------------------------------
# 19. one caller-selected dimension while a conflicting eligible one also exists
# ---------------------------------------------------------------------------
def test_19_caller_cannot_hide_a_competing_eligible_dimension():
    selected_atom = _figured_atom("ev-selected", "6500")
    hidden_atom = _figured_atom("ev-hidden", "7000")
    selected_c = _candidate("c-selected", value_m=6.5, text_evidence_id="ev-selected")
    hidden_c = _candidate("c-hidden", value_m=7.0, text_evidence_id="ev-hidden")

    # A caller passing only its preferred candidate gets FIRM...
    only_selected = _resolve(candidates=[selected_c], atoms=[selected_atom, hidden_atom])
    assert only_selected.status == "firm"

    # ...but the resolver, given the COMPLETE universe, must not silently
    # agree — the hidden, conflicting, equally-eligible candidate must
    # surface and block.
    full_universe = _resolve(candidates=[selected_c, hidden_c], atoms=[selected_atom, hidden_atom])
    assert full_universe.abstained
    assert full_universe.blocking_reasons == ("numeric_conflict_within_same_span",)


# ---------------------------------------------------------------------------
# 20. input-order permutation
# ---------------------------------------------------------------------------
def test_20_input_order_permutation_does_not_alter_result():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "6500")
    atom3 = _figured_atom("ev-3", "900")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    c2 = _candidate("c-2", dimension_system_id="dimsys-c-2", value_m=6.5, text_evidence_id="ev-2")
    c3 = _candidate("c-3", target_entity_id="door-1", kind=SemanticSpanKind.OPENING_WIDTH,
                     value_m=0.9, text_evidence_id="ev-3",
                     endpoint_a=_ep(EndpointReferenceKind.JAMB, "door-1", "left"),
                     endpoint_b=_ep(EndpointReferenceKind.JAMB, "door-1", "right"))
    atoms = [atom1, atom2, atom3]
    results = []
    for perm in itertools.permutations([c1, c2, c3]):
        results.append(_resolve(candidates=list(perm), atoms=atoms))
    first = results[0]
    for other in results[1:]:
        assert other.status == first.status
        assert other.value_m == first.value_m
        assert other.contributing_candidate_ids == first.contributing_candidate_ids


# ===========================================================================
# Formal monotonicity properties
# ===========================================================================

def test_monotonic_removing_support_cannot_increase_authority():
    atom = _figured_atom("ev-1", "6500")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    with_support = _resolve(candidates=[c1], atoms=[atom])
    without_support = _resolve(candidates=[], atoms=[atom])
    assert with_support.status == "firm"
    assert without_support.abstained


def test_monotonic_adding_competing_eligible_dimension_cannot_preserve_firm_silently():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "6520")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    baseline = _resolve(candidates=[c1], atoms=[atom1, atom2])
    assert baseline.status == "firm"

    competing = _candidate(
        "c-2", value_m=6.52, text_evidence_id="ev-2",
        endpoint_a=_ep(EndpointReferenceKind.CENTERLINE, "wall-1", "cl_a"),
        endpoint_b=_ep(EndpointReferenceKind.CENTERLINE, "wall-1", "cl_b"),
    )
    with_competitor = _resolve(candidates=[c1, competing], atoms=[atom1, atom2])
    assert with_competitor.abstained


def test_monotonic_adding_conflict_cannot_increase_authority():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "7000")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    baseline = _resolve(candidates=[c1], atoms=[atom1, atom2])
    assert baseline.status == "firm"

    conflicting = _candidate("c-2", value_m=7.0, text_evidence_id="ev-2")
    with_conflict = _resolve(candidates=[c1, conflicting], atoms=[atom1, atom2])
    assert with_conflict.abstained


def test_monotonic_duplicating_identical_evidence_cannot_strengthen():
    atom = _figured_atom("ev-1", "6500")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    c1_dup = _candidate("c-1-dup", value_m=6.5, text_evidence_id="ev-1")
    single = _resolve(candidates=[c1], atoms=[atom])
    duplicated = _resolve(candidates=[c1, c1_dup], atoms=[atom])
    assert single.status == duplicated.status == "firm"
    assert single.value_m == pytest.approx(duplicated.value_m, abs=1e-9)


def test_monotonic_reordering_candidates_cannot_alter_result():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "900")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    c2 = _candidate("c-2", target_entity_id="door-1", kind=SemanticSpanKind.OPENING_WIDTH,
                     value_m=0.9, text_evidence_id="ev-2",
                     endpoint_a=_ep(EndpointReferenceKind.JAMB, "door-1", "left"),
                     endpoint_b=_ep(EndpointReferenceKind.JAMB, "door-1", "right"))
    forward = _resolve(candidates=[c1, c2], atoms=[atom1, atom2])
    backward = _resolve(candidates=[c2, c1], atoms=[atom1, atom2])
    assert forward.status == backward.status
    assert forward.value_m == backward.value_m
    assert forward.contributing_candidate_ids == backward.contributing_candidate_ids


def test_monotonic_removing_endpoint_ownership_cannot_preserve_firm():
    atom = _figured_atom("ev-1", "6500")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1")
    baseline = _resolve(candidates=[c1], atoms=[atom])
    assert baseline.status == "firm"

    stripped = _candidate("c-1-stripped", value_m=6.5, text_evidence_id="ev-1", endpoint_b=None)
    result = _resolve(candidates=[stripped], atoms=[atom])
    assert result.abstained


def test_monotonic_changing_revision_cannot_preserve_firm():
    atom = _figured_atom("ev-1", "6500")
    c1 = _candidate("c-1", value_m=6.5, text_evidence_id="ev-1", revision_id="R1")
    baseline = _resolve(candidates=[c1], atoms=[atom], context=_context(revision="R1"))
    assert baseline.status == "firm"

    result = _resolve(candidates=[c1], atoms=[atom], context=_context(revision="R2"))
    assert result.abstained


def test_monotonic_adding_unrelated_non_applicable_dimension_cannot_affect_result():
    atom1 = _figured_atom("ev-1", "6500")
    atom2 = _figured_atom("ev-2", "6500")
    c1 = _candidate("c-1", target_entity_id="wall-1", value_m=6.5, text_evidence_id="ev-1")
    unrelated = _candidate("c-2", target_entity_id="wall-99", value_m=6.5, text_evidence_id="ev-2",
                            endpoint_a=_ep(EndpointReferenceKind.FACE, "wall-99", "face_a"),
                            endpoint_b=_ep(EndpointReferenceKind.FACE, "wall-99", "face_b"))
    baseline = _resolve(target_entity_id="wall-1", candidates=[c1], atoms=[atom1, atom2])
    with_unrelated = _resolve(target_entity_id="wall-1", candidates=[c1, unrelated], atoms=[atom1, atom2])
    assert baseline.status == with_unrelated.status == "firm"
    assert baseline.value_m == with_unrelated.value_m
    assert baseline.contributing_candidate_ids == with_unrelated.contributing_candidate_ids


# ===========================================================================
# No production wiring
# ===========================================================================

def test_no_production_module_imports_the_new_span_authority():
    repo_root = Path(__file__).resolve().parents[1]
    suspects = [
        "pb_quantity_takeoff_adapter.py",
        "pb_quantity_prediction_adapter.py",
        "pb_jobhub_publishing_pipeline.py",
        "pb_planreader_jobhub_publish_contract.py",
        "pb_wall_length_quantity.py",
        "pb_legacy_extractor_adapter.py",
    ]
    for name in suspects:
        path = repo_root / name
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        assert "pb_figured_dimension_span_authority" not in content, (
            f"{name} must not import the shadow-only span authority module yet"
        )
