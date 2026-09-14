"""Focused regressions for post-#288 authority gaps found by GPT-2.

These tests deliberately exercise only the three defects remediated by
``gpt/authority-remediation-v4``:

* an owned, target-bound opposing atom present in the supplied evidence
  catalog must not be hidden merely because the caller omitted its id from
  ``wall.conflicting_evidence_ids``;
* source atoms already resolved as CONFLICT/ABSTAINED must not contribute
  positive physical-wall existence support; and
* differing dominant axes are not positive proof of DISTINCT physical walls.

Do not weaken these assertions to preserve legacy publication behaviour.
"""
from __future__ import annotations

import pytest

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
from pb_physical_wall_existence_authority import resolve_physical_wall_existence
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_GRID, KIND_PHYSICAL_WALL

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


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp",
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def _wall() -> WallCandidate:
    return WallCandidate(
        candidate_id="w1",
        viewport_id="vp",
        representation="single_line",
        centerline_pts=((0.0, 0.0), (100.0, 0.0)),
        face_a_segment_ids=("seg-1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id="L1",
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.9,
        supporting_evidence_ids=("support-u2", "support-pair"),
        conflicting_evidence_ids=(),
    )


def _atom(
    evidence_id: str,
    kind: str,
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE,
    polarity: str | None = None,
) -> EvidenceAtom:
    metadata = {
        "wall_candidate_id": "w1",
        "revision_id": "R1",
        "evidence_snapshot_id": "evsnap",
        "source_sha256": SHA,
    }
    if polarity is not None:
        metadata["polarity"] = polarity
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="page-1",
        viewport_id="vp",
        kind=kind,
        method="redteam-test",
        confidence=0.8,
        status=status,
        metadata=metadata,
    )


def _resolve(atoms: tuple[EvidenceAtom, ...]):
    return resolve_physical_wall_existence(
        wall=_wall(),
        evidence_atoms=atoms,
        document=DocumentEvidence(
            document_id="doc",
            source_sha256=SHA,
            page_count=1,
            page_ids=("page-1",),
            evidence_ids=tuple(atom.evidence_id for atom in atoms),
        ),
        viewport=_viewport(),
        context=_context(),
    )


def _normal_support_atoms() -> tuple[EvidenceAtom, EvidenceAtom]:
    return (
        _atom("support-u2", KIND_PHYSICAL_WALL),
        _atom("support-pair", FAMILY_PAIRED_WALL_FACES),
    )


def test_unlisted_owned_target_bound_opposing_atom_cannot_be_hidden() -> None:
    """The supplied catalog is authority input, not just ids curated on wall."""
    support_a, support_b = _normal_support_atoms()
    hidden_opposition = _atom("grid-opposes", KIND_GRID, polarity="opposing")

    resolved = _resolve((support_a, support_b, hidden_opposition))

    assert resolved.status == EvidenceResolutionStatus.CONFLICT
    assert "grid-opposes" in tuple(resolved.metadata.get("opposing_evidence_ids") or ())


@pytest.mark.parametrize(
    "bad_status",
    (EvidenceResolutionStatus.CONFLICT, EvidenceResolutionStatus.ABSTAINED),
)
def test_conflict_or_abstained_source_atom_cannot_support_existence(
    bad_status: EvidenceResolutionStatus,
) -> None:
    """A source atom that has already failed authority cannot be positive support."""
    bad_support = _atom("support-u2", KIND_PHYSICAL_WALL, status=bad_status)
    good_support = _atom("support-pair", FAMILY_PAIRED_WALL_FACES)

    resolved = _resolve((bad_support, good_support))

    assert resolved.status == EvidenceResolutionStatus.ABSTAINED
    assert f"existence_support_atom_status_{bad_status.value}" in resolved.reason_codes


def _identity(
    wall_id: str,
    path: tuple[tuple[float, float], ...],
    primitives: tuple[str, ...],
) -> PhysicalWallIdentity:
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id="vp",
        candidate_identity_id=f"cid-{wall_id}",
        path_fingerprint=path,
        source_primitive_ids=primitives,
        edge_ids=(f"edge-{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
        level_id="L1",
    )


def test_different_dominant_axes_under_equal_ancestry_are_not_distinct_proof() -> None:
    left = _identity("left", ((0.0, 0.0), (10.0, 0.0)), ("prim",))
    right = _identity("right", ((20.0, 0.0), (20.0, 10.0)), ("prim",))

    assert (
        classify_physical_wall_pair(left, right)
        == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    )


def test_different_dominant_axes_under_shared_ancestry_are_not_distinct_proof() -> None:
    left = _identity("left", ((0.0, 0.0), (10.0, 0.0)), ("shared", "left-only"))
    right = _identity("right", ((20.0, 0.0), (20.0, 10.0)), ("shared", "right-only"))

    assert (
        classify_physical_wall_pair(left, right)
        == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    )
