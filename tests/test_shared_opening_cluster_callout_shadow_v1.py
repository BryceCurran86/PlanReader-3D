"""Tests for shared/adjacent opening cluster callout resolution (Item 18)."""
from __future__ import annotations

import math
from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_shared_opening_cluster_callout_shadow as soc
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "a" * 64
_SHA_OTHER = "b" * 64


def _leg(
    leg_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    host_wall_id: str,
    page_id: str = "3",
    viewport_id: str = "vp-plan-1",
    rev_id: str = "rev-1",
    sha: str = _SHA,
) -> soc.ClusterOpeningLegCandidate:
    return soc.ClusterOpeningLegCandidate(
        leg_id=leg_id,
        document_id="doc-1",
        revision_id=rev_id,
        source_sha256=sha,
        page_id=page_id,
        viewport_id=viewport_id,
        host_wall_id=host_wall_id,
        start_pt=start,
        end_pt=end,
        evidence_ids=(f"ev-{leg_id}",),
        opening_kind="glazed_opening",
    )


def _callout(
    callout_id: str,
    anchor: tuple[float, float],
    *,
    text: str = "2124 STACKER",
    height_mm: int | None = 2100,
    width_mm: int | None = 2400,
    explicit_leg_id: str | None = None,
    page_id: str = "3",
    viewport_id: str = "vp-plan-1",
    rev_id: str = "rev-1",
    sha: str = _SHA,
) -> soc.OpeningClusterCalloutWitness:
    return soc.OpeningClusterCalloutWitness(
        callout_id=callout_id,
        document_id="doc-1",
        revision_id=rev_id,
        source_sha256=sha,
        page_id=page_id,
        viewport_id=viewport_id,
        observation_id=f"obs-{callout_id}",
        raw_text=text,
        anchor_pt=anchor,
        declared_height_mm=height_mm,
        declared_width_mm=width_mm,
        explicit_leg_id=explicit_leg_id,
    )


def test_corner_two_leg_assembly_shares_unique_callout_without_double_counting() -> None:
    """Two orthogonal corner stackers meeting at a 4 pt post share one callout (2 legs, never 3)."""
    leg_h = _leg("leg-east", (100.0, 200.0), (200.0, 200.0), host_wall_id="wall-south")
    leg_v = _leg("leg-north", (204.0, 200.0), (204.0, 300.0), host_wall_id="wall-east")
    callout = _callout("c-2124", (222.0, 185.0), text="2124", height_mm=2100, width_mm=2400)

    report = soc.resolve_shared_opening_clusters(legs=[leg_v, leg_h], callouts=[callout])
    assert report.commercial_authority_granted is False
    assert report.unclustered_leg_ids == ()
    assert report.conflict_leg_ids == ()
    assert len(report.clusters) == 1

    cluster = report.clusters[0]
    assert cluster.cluster_kind == soc.CLUSTER_CORNER_ASSEMBLY
    assert cluster.status == EvidenceResolutionStatus.CORROBORATED
    assert cluster.resolved_leg_count == 2
    assert cluster.shared_callout_applied_to_both_legs is True
    assert cluster.commercial_authority_granted is False
    assert sum(m.member_count for m in cluster.members) == 2
    assert all(m.callout_id == "c-2124" and m.shared_callout_inherited is True for m in cluster.members)
    assert all((m.declared_height_mm, m.declared_width_mm) == (2100, 2400) for m in cluster.members)


def test_adjacent_shared_pier_pair_resolves_without_double_counting() -> None:
    leg_1 = _leg("win-left", (100.0, 100.0), (160.0, 100.0), host_wall_id="wall-north")
    leg_2 = _leg("win-right", (168.0, 100.0), (228.0, 100.0), host_wall_id="wall-north")
    callout = _callout("c-pair", (164.0, 82.0), text="1812", height_mm=1800, width_mm=1200)

    report = soc.resolve_shared_opening_clusters(legs=[leg_1, leg_2], callouts=[callout])
    assert len(report.clusters) == 1
    cluster = report.clusters[0]
    assert cluster.cluster_kind == soc.CLUSTER_ADJACENT_SHARED_PIER
    assert cluster.status == EvidenceResolutionStatus.CORROBORATED
    assert cluster.resolved_leg_count == 2
    assert cluster.separation_pt == pytest.approx(8.0)


def test_overlapping_duplicate_legs_fail_closed_instead_of_double_counting() -> None:
    leg_1 = _leg("dup-a", (100.0, 100.0), (180.0, 100.0), host_wall_id="wall-1")
    leg_2 = _leg("dup-b", (140.0, 100.0), (200.0, 100.0), host_wall_id="wall-1")

    report = soc.resolve_shared_opening_clusters(legs=[leg_1, leg_2], callouts=[])
    assert report.clusters == ()
    assert report.conflict_leg_ids == ("dup-a", "dup-b")
    assert "duplicate_or_overlapping_cluster_leg" in report.reason_codes


def test_three_way_junction_fails_closed_as_ambiguous() -> None:
    a = _leg("leg-a", (100.0, 200.0), (200.0, 200.0), host_wall_id="wall-1")
    b = _leg("leg-b", (202.0, 200.0), (202.0, 300.0), host_wall_id="wall-2")
    c = _leg("leg-c", (202.0, 198.0), (202.0, 100.0), host_wall_id="wall-3")

    report = soc.resolve_shared_opening_clusters(legs=[a, b, c], callouts=[])
    assert report.clusters == ()
    assert set(report.conflict_leg_ids) == {"leg-a", "leg-b", "leg-c"}
    assert "ambiguous_multi_leg_cluster" in report.reason_codes


def test_cross_viewport_and_cross_revision_callouts_never_transfer() -> None:
    leg_h = _leg("leg-h", (100.0, 200.0), (200.0, 200.0), host_wall_id="wall-s")
    leg_v = _leg("leg-v", (202.0, 200.0), (202.0, 300.0), host_wall_id="wall-e")
    wrong_vp = _callout("c-vp", (215.0, 190.0), viewport_id="vp-other")
    wrong_rev = _callout("c-rev", (215.0, 190.0), rev_id="rev-2")
    wrong_sha = _callout("c-sha", (215.0, 190.0), sha=_SHA_OTHER)

    report = soc.resolve_shared_opening_clusters(
        legs=[leg_h, leg_v], callouts=[wrong_vp, wrong_rev, wrong_sha],
    )
    assert len(report.clusters) == 1
    cluster = report.clusters[0]
    assert cluster.status == EvidenceResolutionStatus.ABSTAINED
    assert cluster.shared_callout_applied_to_both_legs is False
    assert all(m.callout_id is None for m in cluster.members)


def test_shared_callout_ambiguous_across_two_clusters_and_conflicts_fail_closed() -> None:
    # Two nearby corner clusters equidistant from a single callout -> CONFLICT for both
    c1_a = _leg("c1-a", (0.0, 100.0), (80.0, 100.0), host_wall_id="w1")
    c1_b = _leg("c1-b", (82.0, 100.0), (82.0, 180.0), host_wall_id="w2")
    c2_a = _leg("c2-a", (142.0, 100.0), (222.0, 100.0), host_wall_id="w3")
    c2_b = _leg("c2-b", (140.0, 100.0), (140.0, 180.0), host_wall_id="w4")
    amb = _callout("c-mid", (111.0, 100.0))
    rep = soc.resolve_shared_opening_clusters(legs=[c1_a, c1_b, c2_a, c2_b], callouts=[amb])
    assert len(rep.clusters) == 2
    assert all(c.status == EvidenceResolutionStatus.CONFLICT for c in rep.clusters)
    assert "callout_ambiguous_across_clusters" in rep.reason_codes

    # Shared callout disagreeing with an explicit leg callout -> CONFLICT
    ex_conflict = _callout("c-leg", (40.0, 95.0), height_mm=2400, width_mm=2400, explicit_leg_id="c1-a")
    sh = _callout("c-sh", (85.0, 95.0), height_mm=2100, width_mm=2400)
    rep2 = soc.resolve_shared_opening_clusters(legs=[c1_a, c1_b], callouts=[sh, ex_conflict])
    assert rep2.clusters[0].status == EvidenceResolutionStatus.CONFLICT
    assert "shared_vs_leg_callout_conflict" in rep2.clusters[0].reason_codes

    # Leg-specific callout on one leg NEVER silently copies onto unlabelled partner leg
    rep3 = soc.resolve_shared_opening_clusters(legs=[c1_a, c1_b], callouts=[ex_conflict])
    assert rep3.clusters[0].status == EvidenceResolutionStatus.ABSTAINED
    by_leg = {m.leg_id: m for m in rep3.clusters[0].members}
    assert by_leg["c1-a"].callout_id == "c-leg"
    assert by_leg["c1-b"].callout_id is None


def test_translation_rotation_metamorphic_invariance_and_zero_project_literals() -> None:
    def rot(pt: tuple[float, float], deg: float, dx: float, dy: float) -> tuple[float, float]:
        rad = math.radians(deg)
        c, s = math.cos(rad), math.sin(rad)
        return (pt[0] * c - pt[1] * s + dx, pt[0] * s + pt[1] * c + dy)

    base_a, base_b, base_c = ((100.0, 200.0), (200.0, 200.0)), ((204.0, 200.0), (204.0, 300.0)), (220.0, 185.0)
    ref = soc.resolve_shared_opening_clusters(
        legs=[
            _leg("la", *base_a, host_wall_id="w1"),
            _leg("lb", *base_b, host_wall_id="w2"),
        ],
        callouts=[_callout("c1", base_c)],
    )
    for deg, dx, dy in ((90.0, 50.0, -30.0), (180.0, 300.0, 400.0), (270.0, -25.0, 80.0)):
        out = soc.resolve_shared_opening_clusters(
            legs=[
                _leg("lb", rot(base_b[0], deg, dx, dy), rot(base_b[1], deg, dx, dy), host_wall_id="w2"),
                _leg("la", rot(base_a[0], deg, dx, dy), rot(base_a[1], deg, dx, dy), host_wall_id="w1"),
            ],
            callouts=[_callout("c1", rot(base_c, deg, dx, dy))],
        )
        assert out.clusters[0].status == ref.clusters[0].status
        assert out.clusters[0].cluster_kind == ref.clusters[0].cluster_kind
        assert out.clusters[0].resolved_leg_count == ref.clusters[0].resolved_leg_count
        assert out.clusters[0].members == ref.clusters[0].members

    mod_path = Path(soc.__file__)
    assert audit_shared_source(mod_path.read_text(encoding="utf-8"), filename=mod_path.name) == ()
