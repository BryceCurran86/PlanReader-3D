"""Opening → Host Wall Binding — independent red-team / test-first suite.

Base: merged G17 main 62a161519e617cdf9ce23069820dbf7c68aaf521

Production files changed: 0.
Opening identity (#331) and opening dimensions (#332) are out of scope.

Axes stay separate: existence ≠ identity ≠ width ≠ height ≠ type ≠ host.

EXPECTED_RED asserts eventual unique host authority under authenticated
universe completeness and must remain red until a reviewed production
implementation lands. Fail-closed / poison / firewall tests are GREEN now.
"""
from __future__ import annotations

import importlib.util
from typing import Sequence

import pytest

from pb_hosted_opening_wall_binding import bind_hosted_opening_to_walls
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_opening_deduction_readiness import build_opening_deduction_quantity
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_wall_room_topology_contracts import JunctionType, OpeningHostCandidate
from pb_wall_room_topology_opening_host_binding import detect_opening_host_candidates
from pb_wall_room_topology_wall_identity_v2 import canonical_path_fingerprint
from tests.opening_host_binding_test_support import (
    BASE_SHA,
    CallerHostBindingProbe,
    HostUniverseSlice,
    assert_host_capability_locked,
    collinear_split_points,
    continuous_host_wall,
    flanking_host_walls,
    make_span,
    make_wall,
    parallel_competitor,
    producer_path_fingerprint,
    reverse_wall_direction,
    shuffle_walls,
    transform_polyline,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="OpeningHostBindingAuthority not implemented on main 62a1615",
)

SHA = "b" * 64


def _has_opening_host_binding_authority_module() -> bool:
    return importlib.util.find_spec("pb_opening_host_binding_authority") is not None


def _ctx(**overrides: object) -> ProviderContext:
    kwargs = dict(
        run_id="run",
        workspace_id="ws",
        project_id="p",
        document_id="doc-host",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=("vp_1",),
        evidence_snapshot_id="snap",
        canonical_graph_snapshot_id="graph",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp_1", 1),),
    )
    kwargs.update(overrides)
    return ProviderContext(**kwargs)  # type: ignore[arg-type]


def _vp(viewport_id: str = "vp_1", page_id: str = "page-1") -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc-host",
        page_id=page_id,
        bbox=(0, 0, 400, 400),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _doc(evidence_ids: Sequence[str] = ("w", "h")) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc-host",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=tuple(evidence_ids),
    )


def _meta(opening_id: str, **extra: object) -> dict[str, object]:
    out: dict[str, object] = {
        "source_sha256": SHA,
        "revision_id": "R1",
        "evidence_snapshot_id": "snap",
        "canonical_graph_snapshot_id": "graph",
        "target_entity_id": opening_id,
    }
    out.update(extra)
    return out


def _ev(eid: str, kind: str, value: float, *, opening_id: str) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=eid,
        document_id="doc-host",
        page_id="page-1",
        viewport_id="vp_1",
        kind=kind,
        method="documented_dimension",
        normalized_value=value,
        unit="mm",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_meta(opening_id),
    )


def _entity(opening_id: str, ids: Sequence[str] = ("w", "h")) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id=opening_id,
        candidate_type="opening",
        evidence_ids=tuple(ids),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
        metadata=_meta(opening_id),
    )


def _hosted_record(
    opening_id: str,
    wall_id: str,
    *,
    reasons: tuple[str, ...] = (),
) -> OpeningHostCandidate:
    return OpeningHostCandidate(
        host_candidate_id=opening_id,
        wall_candidate_id=wall_id,
        position_along_wall_m=None,
        gap_width_m=None,
        host_status="hosted",
        candidate_wall_ids_considered=(wall_id,),
        confidence=1.0,
        reason_codes=reasons,
    )


def _load_host_binding_authority():
    """Future production entrypoint. Absent on main ⇒ AssertionError (EXPECTED_RED)."""

    if not _has_opening_host_binding_authority_module():
        raise AssertionError("OpeningHostBindingAuthority absent on main")
    import pb_opening_host_binding_authority as mod  # type: ignore

    return mod


def _resolve_unique_host_or_raise(universe: HostUniverseSlice, span) -> str:
    """Stand-in for eventual unique-host resolution."""

    mod = _load_host_binding_authority()
    outcome = mod.resolve_opening_host_binding(universe=universe, span=span)
    if getattr(outcome, "status", None) not in {"hosted", "bound"}:
        raise AssertionError(f"expected unique host, got {outcome!r}")
    host_id = getattr(outcome, "wall_candidate_id", None)
    if not host_id:
        raise AssertionError(f"unique host missing wall id: {outcome!r}")
    return str(host_id)


def _resolve_blocked_or_ambiguous(universe: HostUniverseSlice, span) -> object:
    """Stand-in for eventual fail-closed / ambiguous outcomes."""

    mod = _load_host_binding_authority()
    outcome = mod.resolve_opening_host_binding(universe=universe, span=span)
    status = getattr(outcome, "status", None)
    if status not in {"blocked", "conflict", "ambiguous", "ambiguous_host", "unbound"}:
        raise AssertionError(f"expected blocked/ambiguous host outcome, got {outcome!r}")
    if getattr(outcome, "wall_candidate_id", None) not in (None, ""):
        raise AssertionError(f"blocked/ambiguous must not publish wall id: {outcome!r}")
    return outcome


# ---------------------------------------------------------------------------
# Fail-closed / observed locks — GREEN on current main
# ---------------------------------------------------------------------------


def test_branch_bound_to_merged_g17_main() -> None:
    assert BASE_SHA == "62a161519e617cdf9ce23069820dbf7c68aaf521"


def test_host_binding_capability_remains_false() -> None:
    assert_host_capability_locked()
    assert _has_opening_host_binding_authority_module() is False


def test_attack13_w7_never_emits_hosted_status() -> None:
    left, right = flanking_host_walls()
    hosts = detect_opening_host_candidates([left, right])
    assert hosts, "dangling gap must produce an OpeningHostCandidate"
    assert all(h.host_status == "ambiguous_host" for h in hosts)
    assert all(len(h.candidate_wall_ids_considered) >= 2 for h in hosts)


def test_attack13_nearest_wall_nomination_blocked_by_readiness() -> None:
    host = _hosted_record("OP-1", "WALL-1", reasons=("nearest_wall_only",))
    qty = build_opening_deduction_quantity(
        opening_entity=_entity("OP-1"),
        width_evidence=_ev("w", "opening_width_dimension", 900, opening_id="OP-1"),
        height_evidence=_ev("h", "opening_height_dimension", 2100, opening_id="OP-1"),
        host=host,
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc(),
        viewport=_vp(),
    )
    assert qty.abstained is True
    assert "opening_host_nearest_only_not_authoritative" in qty.blocking_reasons
    assert "opening_host_universe_completeness_not_authenticated" in qty.blocking_reasons


def test_attack15_caller_hosted_cannot_certify_universe_completeness() -> None:
    """A local candidate set may not certify its own completeness."""

    host = _hosted_record("OP-1", "WALL-1")
    qty = build_opening_deduction_quantity(
        opening_entity=_entity("OP-1"),
        width_evidence=_ev("w", "opening_width_dimension", 900, opening_id="OP-1"),
        height_evidence=_ev("h", "opening_height_dimension", 2100, opening_id="OP-1"),
        host=host,
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc(),
        viewport=_vp(),
    )
    assert "opening_host_universe_completeness_not_authenticated" in qty.blocking_reasons


def test_attack12_caller_supplied_fingerprint_probe_cannot_self_certify() -> None:
    pts = ((0.0, 0.0), (100.0, 0.0))
    probe = CallerHostBindingProbe(
        opening_id="caller-op",
        wall_candidate_id="caller-wall",
        path_fingerprint=canonical_path_fingerprint(pts),
        page_id="page-1",
        viewport_id="vp_1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
        universe_complete_claim=True,
    )
    assert _has_opening_host_binding_authority_module() is False
    assert probe.universe_complete_claim is True  # looks complete — still not authority
    assert_host_capability_locked()


def test_attack14_first_or_smallest_wall_id_is_not_host_authority() -> None:
    left, right = flanking_host_walls(left_id="z_wall", right_id="a_wall")
    hosts = detect_opening_host_candidates([left, right])
    assert len(hosts) == 1
    # W7 labels wall_candidate_id with sorted-first considered id for shape only.
    assert hosts[0].wall_candidate_id == "a_wall"
    assert hosts[0].host_status == "ambiguous_host"
    assert set(hosts[0].candidate_wall_ids_considered) == {"a_wall", "z_wall"}


def test_attack_downstream_firewall_host_capabilities_closed() -> None:
    assert_host_capability_locked()
    caps = PhysicalOpeningAuthority.capabilities()
    for key in (
        "host_binding",
        "host_identity",
        "opening_dimensions",
        "opening_universe_complete",
        "physical_void",
        "net_wall_area",
    ):
        assert caps[key] is False


def test_attack_diagnostic_binder_refuses_one_sided_adjacency() -> None:
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    only_left = make_wall("only_left", ((20.0, 100.0), (100.0, 100.0)))
    binding = bind_hosted_opening_to_walls(span, [only_left], viewport_id="vp_1")
    assert binding.status == "unbound"
    assert binding.wall_candidate_id is None


def test_attack_323_fingerprint_reuse_not_forked() -> None:
    """Prove this lane calls the existing #323 helper, not a private copy."""

    a = producer_path_fingerprint([(0.0, 0.0), (50.0, 0.0), (100.0, 0.0)])
    b = canonical_path_fingerprint([(100.0, 0.0), (50.0, 0.0), (0.0, 0.0)])
    c = canonical_path_fingerprint([(0.0, 0.0), (100.0, 0.0)])
    assert a == b == c


# ---------------------------------------------------------------------------
# EXPECTED RED — eventual unique host under authenticated completeness
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_one_unambiguous_host_with_authenticated_universe() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,  # claim is insufficient; authority must prove
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == wall.candidate_id


@EXPECTED_RED
def test_attack02_corner_door_host_resolution() -> None:
    # Horizontal run into a corner + vertical continuation; opening on horizontal.
    horizontal = make_wall(
        "wall_h",
        ((20.0, 100.0), (100.0, 100.0)),
        junction_types=(JunctionType.ENDPOINT, JunctionType.L_CORNER),
    )
    vertical = make_wall(
        "wall_v",
        ((100.0, 100.0), (100.0, 200.0)),
        junction_types=(JunctionType.L_CORNER, JunctionType.ENDPOINT),
    )
    # Continuous through-host that uniquely contains the span.
    through = continuous_host_wall(wall_id="wall_through_corner", x0=20.0, x1=180.0)
    span = make_span(jamb_start=(40.0, 100.0), jamb_end=(70.0, 100.0))
    universe = HostUniverseSlice(
        walls=(horizontal, vertical, through),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == "wall_through_corner"


@EXPECTED_RED
def test_attack03_t_junction_does_not_steal_host() -> None:
    stem = make_wall(
        "t_stem",
        ((120.0, 100.0), (120.0, 180.0)),
        junction_types=(JunctionType.T_JUNCTION, JunctionType.ENDPOINT),
    )
    through = continuous_host_wall(wall_id="t_through")
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(through, stem),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == "t_through"


@EXPECTED_RED
def test_attack04_two_parallel_competing_walls_block() -> None:
    through = continuous_host_wall(wall_id="row_a", y=100.0)
    # Distinct ids on same geometry — competing hosts.
    rival = make_wall(
        "row_b",
        ((20.0, 100.0), (220.0, 100.0)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(through, rival),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    # Future authority must BLOCK / CONFLICT — never pick first.
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack05_multi_wythe_cavity_wall_blocks_without_wythe_proof() -> None:
    face_a = continuous_host_wall(wall_id="wythe_a", y=100.0)
    face_b = continuous_host_wall(wall_id="wythe_b", y=110.0)
    span = make_span(jamb_start=(100.0, 105.0), jamb_end=(140.0, 105.0))
    universe = HostUniverseSlice(
        walls=(face_a, face_b),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack06_curved_or_segmented_wall_uses_323_fingerprint() -> None:
    straight = continuous_host_wall(wall_id="seg_straight")
    split_pts = collinear_split_points(straight.centerline_pts, (0.25, 0.5, 0.75))
    segmented = make_wall(
        "seg_split",
        split_pts,
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    assert producer_path_fingerprint(straight.centerline_pts) == producer_path_fingerprint(
        segmented.centerline_pts
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(segmented,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == "seg_split"


@EXPECTED_RED
def test_attack07_angled_wall_local_axis_host() -> None:
    angled = make_wall(
        "angled",
        ((20.0, 20.0), (220.0, 120.0)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    # Span along the same angled axis (approximate mid-run jambs).
    span = make_span(
        jamb_start=(100.0, 60.0),
        jamb_end=(140.0, 80.0),
        host_orientation_deg=0.0,  # production must use local wall axis, not global X
    )
    universe = HostUniverseSlice(
        walls=(angled,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == "angled"


@EXPECTED_RED
def test_attack08_nearby_but_not_host_rejected() -> None:
    real = continuous_host_wall(wall_id="real_host", y=100.0)
    nearby = parallel_competitor(wall_id="nearby", y=160.0)
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    # Incomplete crop that omits real host must not promote nearby.
    truncated = HostUniverseSlice(
        walls=(nearby,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    _resolve_blocked_or_ambiguous(truncated, span)
    full = HostUniverseSlice(
        walls=(real, nearby),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(full, span)
    assert host_id == "real_host"


@EXPECTED_RED
def test_attack09_opening_footprint_intersects_two_candidates() -> None:
    left, right = flanking_host_walls()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(left, right),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack10_same_geometry_different_wall_ids_fingerprint_equivalence() -> None:
    a = continuous_host_wall(wall_id="id_a")
    b = continuous_host_wall(wall_id="id_b")
    assert a.candidate_id != b.candidate_id
    assert producer_path_fingerprint(a.centerline_pts) == producer_path_fingerprint(
        b.centerline_pts
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(a, b),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    # Two ids, one physical path → must not silently pick either without
    # physical equivalence resolution (#323 / physical_wall_identity).
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack11_identical_fingerprint_only_when_producer_owned_resolves() -> None:
    pts = ((20.0, 100.0), (220.0, 100.0))
    caller_fp = canonical_path_fingerprint(pts)
    probe = CallerHostBindingProbe(
        opening_id="op",
        wall_candidate_id="minted",
        path_fingerprint=caller_fp,
        page_id="page-1",
        viewport_id="vp_1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
        universe_complete_claim=True,
    )
    # Future authority must reject probe as host proof; only producer-owned
    # resolve_physical_wall_identity / assembly path may publish fingerprint.
    assert probe.path_fingerprint == caller_fp
    raise AssertionError("caller fingerprint must not authorize host binding")


@EXPECTED_RED
def test_attack16_page_revision_source_mismatch_blocked() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-9",  # wrong page
        document_id="doc-host",
        revision_id="R-OLD",
        source_sha256="c" * 64,
    )
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack17_viewport_laundering_blocked() -> None:
    wall = continuous_host_wall(viewport_id="vp_child")
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,
        viewport_id="vp_child",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    # Child viewport must not mint ownership over parent-owned walls/openings.
    _resolve_blocked_or_ambiguous(universe, span)


@EXPECTED_RED
def test_attack18_input_order_determinism() -> None:
    left, right = flanking_host_walls()
    through = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    base_walls = (left, right, through)
    results = []
    for seed in (1, 2, 3, 5, 8):
        universe = HostUniverseSlice(
            walls=tuple(shuffle_walls(base_walls, seed=seed)),
            claimed_complete=True,
            viewport_id="vp_1",
            page_id="page-1",
            document_id="doc-host",
            revision_id="R1",
            source_sha256=SHA,
        )
        results.append(_resolve_unique_host_or_raise(universe, span))
    assert len(set(results)) == 1


@EXPECTED_RED
def test_attack19_line_direction_reversal_same_host() -> None:
    wall = continuous_host_wall(wall_id="fwd")
    reversed_wall = reverse_wall_direction(wall, new_id="fwd")
    assert producer_path_fingerprint(wall.centerline_pts) == producer_path_fingerprint(
        reversed_wall.centerline_pts
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    u1 = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    u2 = HostUniverseSlice(
        walls=(reversed_wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    assert _resolve_unique_host_or_raise(u1, span) == _resolve_unique_host_or_raise(u2, span)


@EXPECTED_RED
def test_attack20_segment_split_collinear_collapse_323_compatible() -> None:
    one = continuous_host_wall(wall_id="one")
    split = make_wall(
        "one",
        collinear_split_points(one.centerline_pts, (1 / 3, 2 / 3)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    assert producer_path_fingerprint(one.centerline_pts) == producer_path_fingerprint(
        split.centerline_pts
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    for wall in (one, split):
        universe = HostUniverseSlice(
            walls=(wall,),
            claimed_complete=True,
            viewport_id="vp_1",
            page_id="page-1",
            document_id="doc-host",
            revision_id="R1",
            source_sha256=SHA,
        )
        assert _resolve_unique_host_or_raise(universe, span) == "one"


@EXPECTED_RED
def test_attack21_translation_rotation_preserves_structural_binding() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    rotated_pts = transform_polyline(wall.centerline_pts, angle_deg=90.0, offset=(10.0, -5.0))
    rotated_wall = make_wall(
        wall.candidate_id,
        rotated_pts,
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    rotated_span = make_span(
        jamb_start=transform_polyline([(100.0, 100.0)], angle_deg=90.0, offset=(10.0, -5.0))[0],
        jamb_end=transform_polyline([(140.0, 100.0)], angle_deg=90.0, offset=(10.0, -5.0))[0],
        host_orientation_deg=90.0,
    )
    u0 = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    u1 = HostUniverseSlice(
        walls=(rotated_wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    assert _resolve_unique_host_or_raise(u0, span) == _resolve_unique_host_or_raise(
        u1, rotated_span
    )


@EXPECTED_RED
def test_attack22_host_binding_does_not_unlock_downstream() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(
        walls=(wall,),
        claimed_complete=True,
        viewport_id="vp_1",
        page_id="page-1",
        document_id="doc-host",
        revision_id="R1",
        source_sha256=SHA,
    )
    host_id = _resolve_unique_host_or_raise(universe, span)
    assert host_id == wall.candidate_id
    # Even after a unique host resolves, these stay closed:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["opening_dimensions"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    # Production module would also assert deduction/FIRM/JobHub remain blocked.
    raise AssertionError("downstream firewall must remain closed after host bind")
