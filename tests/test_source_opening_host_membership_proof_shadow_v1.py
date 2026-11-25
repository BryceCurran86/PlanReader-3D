"""Unit tests for Item 17: opening host wall membership proof shadow."""

from __future__ import annotations

import math
from pathlib import Path

from pb_source_opening_host_membership_proof_shadow import (
    CandidateHostWallBand,
    HostLineageRef,
    PhysicalOpeningApertureWitness,
    prove_opening_host_wall_membership_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lin(page: str = "page_01", vp: str = "vp_main", rev: str = "rev_1") -> HostLineageRef:
    return HostLineageRef(
        document_id="doc_01",
        revision_id=rev,
        source_sha256="c" * 64,
        page_id=page,
        viewport_id=vp,
    )


def _rot(pt: tuple[float, float], deg: float, tx: float, ty: float) -> tuple[float, float]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return (pt[0] * c - pt[1] * s + tx, pt[0] * s + pt[1] * c + ty)


def test_proves_unique_host_and_rejects_parallel_neighbor_and_cross_viewport_with_rotation_invariance() -> None:
    baseline_digest = None
    for deg, tx, ty in ((0.0, 0.0, 0.0), (90.0, 120.0, -40.0), (180.0, -50.0, 200.0), (270.0, 33.0, 77.0), (28.5, 11.0, -19.0)):
        opening = PhysicalOpeningApertureWitness(
            opening_id="open_d01",
            lineage=_lin(),
            jamb_a_pt=_rot((80.0, 50.0), deg, tx, ty),
            jamb_b_pt=_rot((120.0, 50.0), deg, tx, ty),
            wall_thickness_pts=8.0,
        )
        walls = (
            # Genuine coplanar whole host wall
            CandidateHostWallBand(
                wall_id="wall_true_host",
                lineage=_lin(),
                p0=_rot((20.0, 50.0), deg, tx, ty),
                p1=_rot((200.0, 50.0), deg, tx, ty),
                thickness_pts=8.0,
            ),
            # Parallel neighbor corridor wall offset by 18 pts (MUST be rejected!)
            CandidateHostWallBand(
                wall_id="wall_parallel_neighbor",
                lineage=_lin(),
                p0=_rot((20.0, 68.0), deg, tx, ty),
                p1=_rot((200.0, 68.0), deg, tx, ty),
                thickness_pts=8.0,
            ),
            # Cross-viewport identical geometry wall (MUST be rejected!)
            CandidateHostWallBand(
                wall_id="wall_other_viewport",
                lineage=_lin(vp="vp_enlarged_inset"),
                p0=_rot((20.0, 50.0), deg, tx, ty),
                p1=_rot((200.0, 50.0), deg, tx, ty),
                thickness_pts=8.0,
            ),
            # Cross-revision identical geometry wall (MUST be rejected!)
            CandidateHostWallBand(
                wall_id="wall_other_revision",
                lineage=_lin(rev="rev_2"),
                p0=_rot((20.0, 50.0), deg, tx, ty),
                p1=_rot((200.0, 50.0), deg, tx, ty),
                thickness_pts=8.0,
            ),
            # Perpendicular intersecting wall (MUST be rejected!)
            CandidateHostWallBand(
                wall_id="wall_perpendicular",
                lineage=_lin(),
                p0=_rot((80.0, 10.0), deg, tx, ty),
                p1=_rot((80.0, 90.0), deg, tx, ty),
                thickness_pts=8.0,
            ),
        )
        res = prove_opening_host_wall_membership_shadow(opening, walls)
        assert res.proven is True
        assert res.abstained is False
        assert res.proven_host_wall_id == "wall_true_host"
        assert res.commercial_authority_granted is False
        assert res.shadow_only is True

        rej = {r.wall_id: r.reason for r in res.rejections}
        assert rej["wall_parallel_neighbor"] == "parallel_neighbor_wall_rejected"
        assert rej["wall_other_viewport"] == "cross_viewport_host_rejected"
        assert rej["wall_other_revision"] == "cross_lineage_host_rejected"
        assert rej["wall_perpendicular"] == "non_collinear_wall_angle_rejected"

        if baseline_digest is None:
            baseline_digest = res.digest_sha256
        else:
            assert res.digest_sha256 == baseline_digest


def test_split_host_collapses_only_with_proven_equivalence_and_abstains_when_ambiguous() -> None:
    opening = PhysicalOpeningApertureWitness(
        opening_id="open_d02",
        lineage=_lin(),
        jamb_a_pt=(80.0, 50.0),
        jamb_b_pt=(120.0, 50.0),
        wall_thickness_pts=8.0,
    )
    left = CandidateHostWallBand("wall_left", _lin(), (20.0, 50.0), (80.0, 50.0), 8.0)
    right = CandidateHostWallBand("wall_right", _lin(), (120.0, 50.0), (190.0, 50.0), 8.0)

    # Without upstream SAME_PHYSICAL_WALL equivalence -> fail closed!
    res_unproven = prove_opening_host_wall_membership_shadow(opening, (left, right))
    assert res_unproven.proven is False
    assert res_unproven.abstained is True
    assert "ambiguous_multiple_distinct_host_candidates" in res_unproven.blocking_reasons

    # With upstream SAME_PHYSICAL_WALL equivalence -> proves unique host!
    res_equiv = prove_opening_host_wall_membership_shadow(
        opening,
        (left, right),
        same_physical_wall_pairs=(("wall_left", "wall_right"),),
    )
    assert res_equiv.proven is True
    assert res_equiv.equivalent_member_wall_ids == ("wall_left", "wall_right")

    # With upstream AMBIGUOUS equivalence flag -> must block!
    res_ambig = prove_opening_host_wall_membership_shadow(
        opening,
        (left, right),
        same_physical_wall_pairs=(("wall_left", "wall_right"),),
        ambiguous_equivalence_wall_ids=("wall_left",),
    )
    assert res_ambig.proven is False
    assert "ambiguous_physical_wall_equivalence_for_host" in res_ambig.blocking_reasons


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_opening_host_membership_proof_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
