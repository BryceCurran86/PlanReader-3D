"""Provenance ownership for viewport-coverage authority (#288 integration).

Cursor's original hardening (commit 5df62619150187b917d1914b91873252db4f7175,
PR #289 predecessor) introduced ``resolve_viewport_coverage_authority`` to
require positive coverage evidence before an unbounded face can become
ARCHITECTURAL EXTERIOR_OPEN_SPACE / BUILDING_INTERIOR. That version matched
coverage atoms on ``viewport_id`` only.

This module hardens ownership to match the same discipline
``pb_physical_wall_existence_authority`` already applies to existence atoms:
a coverage atom must carry the CURRENT document, page, viewport, revision,
evidence snapshot, and source SHA before its ``coverage_status`` can be
trusted. A coverage atom from another document/SHA/revision/snapshot/viewport
must not be able to confer EXTERNAL/INTERNAL authority -- it must fail
exactly like a missing coverage atom, not like a present-but-wrong one that
happens to still work.

This file only imports from tests/test_wall_boundary_role_authority.py to
build fixtures; it does not modify Cursor's own test files.
"""
from __future__ import annotations

from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_boundary_role_authority import (
    VIEWPORT_COVERAGE_KIND,
    WallBoundaryRole,
    resolve_wall_boundary_roles,
)
from tests.test_wall_boundary_role_authority import (
    _atom,
    _atoms_for_walls,
    _context,
    _corroborate,
    _document,
    _owned_metadata,
    _pipeline,
    _rectangle,
    _viewport,
)


def _roles_with_custom_coverage(coverage_atom):
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    existence_atoms = _atoms_for_walls(walls)
    atoms = existence_atoms + (coverage_atom,)
    document = _document(tuple(a.evidence_id for a in atoms))
    viewport = _viewport()
    context = _context()
    records = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=document,
        viewport=viewport,
        context=context,
    )
    return walls, records


def _baseline_coverage_atom(**metadata_overrides):
    metadata = _owned_metadata(coverage_status="complete", viewport_id="vp_1")
    metadata.update(metadata_overrides)
    return _atom("cov-complete", VIEWPORT_COVERAGE_KIND, metadata=metadata)


def test_baseline_owned_coverage_atom_confers_external() -> None:
    """Sanity check: the correctly-owned atom this whole module varies from
    does grant EXTERNAL, so every negative test below is a genuine attack on
    a real positive case, not a vacuously-abstaining fixture."""
    _, records = _roles_with_custom_coverage(_baseline_coverage_atom())
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in records)
    assert all(r.status == EvidenceResolutionStatus.CORROBORATED for r in records)


def test_coverage_atom_from_another_document_cannot_confer_exterior() -> None:
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    existence_atoms = _atoms_for_walls(walls)
    foreign = replace(_baseline_coverage_atom(), document_id="other-doc")
    atoms = existence_atoms + (foreign,)
    document = _document(tuple(a.evidence_id for a in existence_atoms) + (foreign.evidence_id,))
    records = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=document,
        viewport=_viewport(),
        context=_context(),
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_document_mismatch" in r.reason_codes for r in records)


def test_coverage_atom_from_another_source_sha_cannot_confer_exterior() -> None:
    _, records = _roles_with_custom_coverage(
        _baseline_coverage_atom(source_sha256="d" * 64)
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_source_sha_mismatch" in r.reason_codes for r in records)


def test_coverage_atom_from_another_revision_cannot_confer_exterior() -> None:
    _, records = _roles_with_custom_coverage(
        _baseline_coverage_atom(revision_id="R0")
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_revision_stale" in r.reason_codes for r in records)


def test_coverage_atom_from_another_snapshot_cannot_confer_exterior() -> None:
    _, records = _roles_with_custom_coverage(
        _baseline_coverage_atom(evidence_snapshot_id="other-snap")
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_snapshot_mismatch" in r.reason_codes for r in records)


def test_coverage_atom_from_another_viewport_cannot_confer_exterior() -> None:
    _, records = _roles_with_custom_coverage(
        _baseline_coverage_atom(viewport_id="vp-other")
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_viewport_mismatch" in r.reason_codes for r in records)


def test_coverage_atom_missing_revision_metadata_fails_closed() -> None:
    """Missing provenance must fail exactly like foreign provenance -- no
    silent default/optional treatment."""
    metadata = {"coverage_status": "complete", "viewport_id": "vp_1"}
    atom = _atom("cov-complete", VIEWPORT_COVERAGE_KIND, metadata=metadata)
    _, records = _roles_with_custom_coverage(atom)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("viewport_coverage_revision_unproven" in r.reason_codes for r in records)


def test_stale_context_revision_cannot_confer_exterior_even_with_matching_atom() -> None:
    """A correctly-stamped atom cannot rescue a context whose own
    revision_id no longer matches current_revision_id -- the whole snapshot
    is stale, not just one atom."""
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    existence_atoms = _atoms_for_walls(walls)
    coverage = _baseline_coverage_atom()
    atoms = existence_atoms + (coverage,)
    stale_context = replace(_context(), revision_id="R0")
    records = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=_document(tuple(a.evidence_id for a in atoms)),
        viewport=_viewport(),
        context=stale_context,
    )
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_replacing_foreign_coverage_with_owned_coverage_recovers_external() -> None:
    """Monotonicity direction check: the ONLY difference between a blocked
    and a granted result is provenance correctness, proving the gate is the
    provenance check itself and not some other side effect of the fixture."""
    _, blocked = _roles_with_custom_coverage(_baseline_coverage_atom(source_sha256="d" * 64))
    _, granted = _roles_with_custom_coverage(_baseline_coverage_atom())
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in blocked)
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in granted)
