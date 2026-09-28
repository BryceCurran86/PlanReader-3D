"""Candidate-pair eligibility for physical-wall equivalence.

A pair that could not possibly represent the same physical wall is not an
identity competitor: it carries no equivalence relation and must not link two
candidates into one publication contest.

Genuine identity competitors -- shared primitives, duplicate geometry,
orientation-compatible contact, cross-scope redraws, or plausible opposite faces of one wall
body -- must keep failing closed exactly as before.

Separation is only ever a candidate gate. It never proves SAME_PHYSICAL_WALL.

No benchmark values, no scoring, no tolerances on acceptance, no
project-specific coordinates, and no layer names appear here.
"""
from __future__ import annotations

import itertools
import math

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    MAX_PLAUSIBLE_WALL_BODY_MM,
    MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT,
    PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP,
    PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE,
    PAIR_EXCLUDED_SEPARATION_BEYOND_BAND,
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
    max_plausible_wall_body_separation_pt,
    physical_wall_pair_identity_candidacy,
    physical_wall_pair_is_identity_candidate,
    resolve_physical_wall_equivalence,
)

AMBIGUOUS = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
SAME = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
DISTINCT = PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS

# One paper point is 1/72 inch. At 1:50 a point spans 25.4/72*50 real mm.
_MM_PER_PT_AT_1_50 = (25.4 / 72.0) * 50.0
_POINTS_PER_MM_AT_1_50 = 1.0 / _MM_PER_PT_AT_1_50


def _pt_at_1_50(real_mm: float) -> float:
    return real_mm / _MM_PER_PT_AT_1_50


def _ident(wall_id, path, prims, *, viewport="vp", level=None):
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=viewport,
        candidate_identity_id=f"cid::{wall_id}",
        path_fingerprint=tuple((float(x), float(y)) for x, y in path),
        source_primitive_ids=tuple(prims),
        edge_ids=tuple(f"e::{p}" for p in prims),
        status=EvidenceResolutionStatus.CORROBORATED,
        level_id=level,
    )


def _ambiguous_pairs(resolution):
    return {
        (a, b)
        for a, b, c in resolution.pair_classifications
        if c == AMBIGUOUS.value
    }


def _face_pair(separation_pt, *, run=3000.0, prims=("d1i0", "d1i9")):
    return (
        _ident("f-a", ((0.0, 0.0), (run, 0.0)), (prims[0],)),
        _ident("f-b", ((0.0, separation_pt), (run, separation_pt)), (prims[1],)),
    )


# ===========================================================================
# DIRECT CONFIRMED REGRESSION
# ===========================================================================


def test_three_unrelated_walls_publish_three_representatives() -> None:
    """The confirmed ceiling: 3 unrelated walls previously published zero."""
    walls = (
        _ident("w1", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",)),
        _ident("w2", ((500.0, 400.0), (500.0, 520.0)), ("d4i0",)),
        _ident("w3", ((900.0, 900.0), (1000.0, 950.0)), ("d7i0",)),
    )

    resolution = resolve_physical_wall_equivalence(walls)

    assert _ambiguous_pairs(resolution) == set()
    assert resolution.ambiguous_wall_ids == ()
    assert set(resolution.representative_wall_ids) == {"w1", "w2", "w3"}
    assert resolution.abstained_wall_ids == ()
    assert resolution.candidate_pair_audit.total_pairs == 3
    assert resolution.candidate_pair_audit.considered_pairs == 0
    assert resolution.candidate_pair_audit.excluded_pairs == 3


def test_unrelated_wall_cannot_suppress_a_proven_same_group() -> None:
    same_a = _ident("g1", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))
    same_b = _ident("g2", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))
    unrelated = _ident("zfar", ((900.0, 500.0), (900.0, 700.0)), ("d7i0",))

    assert classify_physical_wall_pair(same_a, same_b) is SAME

    resolution = resolve_physical_wall_equivalence((same_a, same_b, unrelated))

    assert set(resolution.representative_wall_ids) == {"g1", "zfar"}
    assert resolution.equivalence_groups == (("g1", "g2"),)
    assert resolution.abstained_wall_ids == ("g2",)


# ===========================================================================
# REQUIRED CHANGE 1 -- separation is only a gate, never SAME proof
# ===========================================================================


def test_parallel_lines_within_band_never_become_same() -> None:
    """~150mm apart at 1:50 with no positive proof must stay AMBIGUOUS."""
    separation = _pt_at_1_50(150.0)
    face_a, face_b = _face_pair(separation)

    assert physical_wall_pair_is_identity_candidate(face_a, face_b)
    assert classify_physical_wall_pair(face_a, face_b) is AMBIGUOUS
    assert classify_physical_wall_pair(face_a, face_b) is not SAME

    resolution = resolve_physical_wall_equivalence((face_a, face_b))
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {"f-a", "f-b"}


@pytest.mark.parametrize("real_mm", [10.0, 50.0, 100.0, 150.0, 300.0, 450.0, 600.0])
def test_no_separation_inside_band_ever_yields_same(real_mm) -> None:
    face_a, face_b = _face_pair(_pt_at_1_50(real_mm))
    assert classify_physical_wall_pair(face_a, face_b) is not SAME


# ===========================================================================
# REQUIRED CHANGE 3 -- conservative wall-body band
# ===========================================================================


def test_band_is_conservative_and_scale_derived() -> None:
    scaled = max_plausible_wall_body_separation_pt(_POINTS_PER_MM_AT_1_50)
    assert scaled == pytest.approx(
        MAX_PLAUSIBLE_WALL_BODY_MM * _POINTS_PER_MM_AT_1_50
    )
    # Without verified scale the documented source-space policy band applies.
    assert max_plausible_wall_body_separation_pt(None) == pytest.approx(
        MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT
    )
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        assert max_plausible_wall_body_separation_pt(bad) == pytest.approx(
            MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT
        )


def test_resolver_audit_records_the_scale_and_band_actually_used() -> None:
    face_a, face_b = _face_pair(_pt_at_1_50(500.0))
    resolution = resolve_physical_wall_equivalence(
        (face_a, face_b),
        points_per_mm=_POINTS_PER_MM_AT_1_50,
    )
    audit = resolution.candidate_pair_audit
    assert audit.verified_points_per_mm == pytest.approx(
        _POINTS_PER_MM_AT_1_50
    )
    assert audit.candidate_wall_body_band_pt == pytest.approx(
        MAX_PLAUSIBLE_WALL_BODY_MM * _POINTS_PER_MM_AT_1_50
    )


def test_resolver_audit_records_source_fallback_when_scale_is_unavailable() -> None:
    left = _ident("scale-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    right = _ident("scale-b", ((5000.0, 4000.0), (5100.0, 4000.0)), ("d9i0",))
    audit = resolve_physical_wall_equivalence((left, right)).candidate_pair_audit
    assert audit.verified_points_per_mm is None
    assert audit.candidate_wall_body_band_pt == pytest.approx(
        MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT
    )


@pytest.mark.parametrize("real_mm", [450.0, 500.0, 550.0, 600.0])
def test_thick_wall_faces_remain_competing_without_scale(real_mm) -> None:
    """A 450-600mm wall at 1:50 must keep both faces in one contest."""
    face_a, face_b = _face_pair(_pt_at_1_50(real_mm))

    eligible, reason = physical_wall_pair_identity_candidacy(face_a, face_b)
    assert eligible, f"{real_mm}mm wall excluded: {reason}"

    resolution = resolve_physical_wall_equivalence((face_a, face_b))
    assert len(resolution.representative_wall_ids) != 2
    assert resolution.representative_wall_ids == ()


@pytest.mark.parametrize("real_mm", [450.0, 500.0, 550.0, 600.0])
def test_thick_wall_faces_remain_competing_with_verified_scale(real_mm) -> None:
    face_a, face_b = _face_pair(_pt_at_1_50(real_mm))

    eligible, reason = physical_wall_pair_identity_candidacy(
        face_a, face_b, points_per_mm=_POINTS_PER_MM_AT_1_50
    )
    assert eligible, f"{real_mm}mm wall excluded under scale: {reason}"

    resolution = resolve_physical_wall_equivalence(
        (face_a, face_b), points_per_mm=_POINTS_PER_MM_AT_1_50
    )
    assert resolution.representative_wall_ids == ()


def test_short_thick_pier_faces_never_publish_independently() -> None:
    """A pier thicker than it is long must still not publish both faces.

    This is the case an aspect-ratio band would get wrong.
    """
    thickness = _pt_at_1_50(500.0)
    run = thickness / 2.0
    face_a = _ident("pier-a", ((0.0, 0.0), (run, 0.0)), ("d1i0",))
    face_b = _ident("pier-b", ((0.0, thickness), (run, thickness)), ("d1i4",))

    assert physical_wall_pair_is_identity_candidate(face_a, face_b)
    resolution = resolve_physical_wall_equivalence((face_a, face_b))
    assert resolution.representative_wall_ids == ()


def test_short_pier_is_not_paired_with_collinear_neighbour_by_proximity() -> None:
    """Collinear abutting neighbours are not face partners of the pier."""
    thickness = _pt_at_1_50(500.0)
    pier = _ident("pier", ((0.0, 0.0), (thickness, 0.0)), ("d1i0",))
    # A separate collinear run further along the same line, not touching.
    neighbour = _ident(
        "neighbour",
        ((thickness * 6.0, 0.0), (thickness * 10.0, 0.0)),
        ("d8i0",),
    )

    eligible, reason = physical_wall_pair_identity_candidacy(pier, neighbour)
    assert not eligible
    assert reason == PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP


@pytest.mark.parametrize("multiplier", [1.5, 3.0, 10.0])
def test_separation_far_beyond_band_is_excluded(multiplier) -> None:
    separation = MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT * multiplier
    face_a, face_b = _face_pair(separation)

    eligible, reason = physical_wall_pair_identity_candidacy(face_a, face_b)
    assert not eligible
    assert reason == PAIR_EXCLUDED_SEPARATION_BEYOND_BAND

    resolution = resolve_physical_wall_equivalence((face_a, face_b))
    assert set(resolution.representative_wall_ids) == {"f-a", "f-b"}


def test_no_separation_sweep_ever_publishes_two_faces_inside_band() -> None:
    """Sweep the whole band; a face pair never publishes twice."""
    band = MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT
    steps = 40
    for index in range(steps + 1):
        separation = band * index / steps
        if separation <= 0.0:
            continue
        face_a, face_b = _face_pair(separation)
        resolution = resolve_physical_wall_equivalence((face_a, face_b))
        assert len(resolution.representative_wall_ids) != 2, (
            f"both faces published at separation={separation:.4f}pt"
        )


# ===========================================================================
# MANDATORY ADVERSARIAL MATRIX
# ===========================================================================


def test_cavity_wall_four_faces_do_not_become_four_walls() -> None:
    run = 3000.0
    offsets = (
        0.0,
        _pt_at_1_50(110.0),
        _pt_at_1_50(160.0),
        _pt_at_1_50(270.0),
    )
    walls = tuple(
        _ident(
            f"cav-{index}",
            ((0.0, offset), (run, offset)),
            (f"d1i{index}",),
        )
        for index, offset in enumerate(offsets)
    )

    resolution = resolve_physical_wall_equivalence(walls)

    assert len(resolution.representative_wall_ids) != 4
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {w.wall_candidate_id for w in walls}


def test_corridor_walls_are_independent_and_never_same() -> None:
    """Opposing corridor walls are separate physical walls, not one body."""
    run = 4000.0
    corridor_width = _pt_at_1_50(1500.0)
    left = _ident("cor-left", ((0.0, 0.0), (run, 0.0)), ("d1i0",))
    right = _ident(
        "cor-right",
        ((0.0, corridor_width), (run, corridor_width)),
        ("d5i0",),
    )

    eligible, reason = physical_wall_pair_identity_candidacy(left, right)
    assert not eligible
    assert reason == PAIR_EXCLUDED_SEPARATION_BEYOND_BAND
    assert classify_physical_wall_pair(left, right) is not SAME

    resolution = resolve_physical_wall_equivalence((left, right))
    assert set(resolution.representative_wall_ids) == {"cor-left", "cor-right"}


def test_corridor_walls_with_own_unresolved_faces_still_abstain() -> None:
    """Across the corridor: independent. Within each wall: still competing."""
    run = 4000.0
    corridor_width = _pt_at_1_50(1500.0)
    thickness = _pt_at_1_50(200.0)
    walls = (
        _ident("l-face-a", ((0.0, 0.0), (run, 0.0)), ("d1i0",)),
        _ident("l-face-b", ((0.0, thickness), (run, thickness)), ("d1i1",)),
        _ident(
            "r-face-a",
            ((0.0, corridor_width), (run, corridor_width)),
            ("d5i0",),
        ),
        _ident(
            "r-face-b",
            (
                (0.0, corridor_width + thickness),
                (run, corridor_width + thickness),
            ),
            ("d5i1",),
        ),
    )

    resolution = resolve_physical_wall_equivalence(walls)

    # No face pairs across the corridor.
    pairs = _ambiguous_pairs(resolution)
    assert ("l-face-a", "r-face-a") not in pairs
    assert ("l-face-b", "r-face-b") not in pairs
    # Each wall's own faces still compete, so nothing publishes.
    assert resolution.representative_wall_ids == ()


def test_two_independent_close_walls_abstain_without_nearest_selection() -> None:
    """50-100mm apart with no identity evidence: safe abstention, no pick."""
    for real_mm in (50.0, 75.0, 100.0):
        separation = _pt_at_1_50(real_mm)
        face_a, face_b = _face_pair(separation)
        resolution = resolve_physical_wall_equivalence((face_a, face_b))
        # Abstention is acceptable; picking one is not.
        assert len(resolution.representative_wall_ids) != 1
        assert resolution.representative_wall_ids == ()


def test_exact_duplicate_cad_geometry_stays_competing() -> None:
    left = _ident("dup-a", ((0.0, 0.0), (250.0, 0.0)), ("d1i0",))
    right = _ident("dup-b", ((0.0, 0.0), (250.0, 0.0)), ("d6i0",))

    assert physical_wall_pair_is_identity_candidate(left, right)
    assert classify_physical_wall_pair(left, right) is AMBIGUOUS

    resolution = resolve_physical_wall_equivalence((left, right))
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {"dup-a", "dup-b"}


@pytest.mark.parametrize("offset", [0.0, 0.001, 0.01, 0.05, 0.1])
def test_near_duplicate_cad_offsets_stay_competing(offset) -> None:
    left = _ident("nd-a", ((0.0, 0.0), (250.0, 0.0)), ("d1i0",))
    right = _ident("nd-b", ((0.0, offset), (250.0, offset)), ("d6i0",))

    assert physical_wall_pair_is_identity_candidate(left, right)
    resolution = resolve_physical_wall_equivalence((left, right))
    assert resolution.representative_wall_ids == ()


@pytest.mark.parametrize(
    "path,label",
    [
        (((100.0, 0.0), (100.0, 150.0)), "t_junction_stem"),
        (((0.0, 0.0), (0.0, 150.0)), "l_corner_leg"),
        (((100.0, -80.0), (100.0, 80.0)), "x_crossing_leg"),
    ],
)
def test_junction_geometry_is_not_a_face_pairing(path, label) -> None:
    """T / L / X wall-network contacts are not identity competitors."""
    flange = _ident("j-flange", ((0.0, 0.0), (200.0, 0.0)), ("d1i0",))
    leg = _ident(f"j-{label}", path, ("d1i4",))

    eligible, reason = physical_wall_pair_identity_candidacy(flange, leg)
    assert not eligible
    assert reason == PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE
    assert classify_physical_wall_pair(flange, leg) is not SAME

    resolution = resolve_physical_wall_equivalence((flange, leg))
    assert resolution.equivalence_groups == ()
    assert set(resolution.representative_wall_ids) == {
        "j-flange",
        f"j-{label}",
    }
    assert resolution.ambiguous_wall_ids == ()


def test_perpendicular_unrelated_walls_publish_independently() -> None:
    horizontal = _ident("w-h", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    vertical = _ident("w-v", ((400.0, 200.0), (400.0, 320.0)), ("d5i0",))

    eligible, reason = physical_wall_pair_identity_candidacy(horizontal, vertical)
    assert not eligible
    assert reason == PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE

    resolution = resolve_physical_wall_equivalence((horizontal, vertical))
    assert set(resolution.representative_wall_ids) == {"w-h", "w-v"}


def test_t_junction_stem_and_unrelated_wall_publish_independently() -> None:
    flange = _ident("w-flange", ((0.0, 0.0), (200.0, 0.0)), ("d1i0",))
    stem = _ident("w-stem", ((100.0, 0.0), (100.0, 150.0)), ("d1i4",))
    unrelated = _ident("w-other", ((800.0, 600.0), (900.0, 600.0)), ("d9i0",))

    assert not physical_wall_pair_is_identity_candidate(flange, stem)
    assert not physical_wall_pair_is_identity_candidate(flange, unrelated)
    assert not physical_wall_pair_is_identity_candidate(stem, unrelated)

    resolution = resolve_physical_wall_equivalence((flange, stem, unrelated))
    assert set(resolution.representative_wall_ids) == {
        "w-flange",
        "w-stem",
        "w-other",
    }
    assert resolution.ambiguous_wall_ids == ()
    assert _ambiguous_pairs(resolution) == set()


def test_wall_split_by_opening_is_not_merged_by_the_gate() -> None:
    """Two collinear pieces with a gap must never become SAME on geometry.

    The gate does not invent a relation across the opening: the pieces have
    disjoint spans and cannot double-count one length. Only a positive
    opening-pattern override may bind them, which
    ``test_opening_pattern_override_is_restored_after_narrowing`` covers.
    """
    left = _ident("op-left", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",))
    right = _ident("op-right", ((1900.0, 0.0), (2900.0, 0.0)), ("d1i5",))

    eligible, reason = physical_wall_pair_identity_candidacy(left, right)
    assert not eligible
    assert reason == PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP
    assert classify_physical_wall_pair(left, right) is not SAME


def test_opening_split_pieces_without_shared_provenance_publish() -> None:
    """No shared primitives, no overlap, no contact: not competitors."""
    left = _ident("os-left", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",))
    right = _ident("os-right", ((1900.0, 0.0), (2900.0, 0.0)), ("d8i0",))

    eligible, reason = physical_wall_pair_identity_candidacy(left, right)
    assert not eligible
    assert reason == PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP

    resolution = resolve_physical_wall_equivalence((left, right))
    assert set(resolution.representative_wall_ids) == {"os-left", "os-right"}


def test_one_face_compatible_with_multiple_partners_stays_ambiguous() -> None:
    shared = _ident("m-shared", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",))
    above = _ident("m-above", ((0.0, 6.0), (1000.0, 6.0)), ("d1i5",))
    below = _ident("m-below", ((0.0, -6.0), (1000.0, -6.0)), ("d1i9",))

    assert physical_wall_pair_is_identity_candidate(shared, above)
    assert physical_wall_pair_is_identity_candidate(shared, below)

    resolution = resolve_physical_wall_equivalence((shared, above, below))
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {
        "m-shared",
        "m-above",
        "m-below",
    }


def test_raster_and_vector_representations_still_compete() -> None:
    """Raster-derived candidates get no identity-safety exemption."""
    vector = _ident("rv-vector", ((0.0, 0.0), (2000.0, 0.0)), ("d1i0",))
    raster = _ident("rv-raster", ((0.0, 4.0), (2000.0, 4.0)), ("raster:seg:7",))

    assert physical_wall_pair_is_identity_candidate(vector, raster)
    resolution = resolve_physical_wall_equivalence((vector, raster))
    assert resolution.representative_wall_ids == ()


# --- Cross-scope duplicate safety (REQUIRED CHANGE 4) ----------------------


def test_plan_and_enlarged_plan_do_not_double_publish() -> None:
    """The same wall redrawn in an enlarged plan must not publish twice."""
    plan = _ident("xv-plan", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",), viewport="vp-plan")
    enlarged = _ident(
        "xv-enlarged",
        ((5000.0, 4000.0), (7500.0, 4000.0)),
        ("d9i0",),
        viewport="vp-enlarged",
    )

    # Coordinates cannot rule out a redraw, so the pair stays in contest.
    assert physical_wall_pair_is_identity_candidate(plan, enlarged)
    assert classify_physical_wall_pair(plan, enlarged) is AMBIGUOUS

    resolution = resolve_physical_wall_equivalence((plan, enlarged))
    assert len(resolution.representative_wall_ids) != 2
    assert resolution.representative_wall_ids == ()


def test_different_levels_do_not_become_automatically_independent() -> None:
    lower = _ident(
        "lv-a", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",), level="level-00"
    )
    upper = _ident(
        "lv-b", ((6000.0, 6000.0), (7000.0, 6000.0)), ("d9i0",), level="level-01"
    )

    assert physical_wall_pair_is_identity_candidate(lower, upper)
    resolution = resolve_physical_wall_equivalence((lower, upper))
    assert resolution.representative_wall_ids == ()


def test_same_scope_far_apart_walls_are_still_independent() -> None:
    """Cross-scope safety must not re-block ordinary same-viewport walls."""
    left = _ident("ss-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",), viewport="vp")
    right = _ident(
        "ss-b", ((9000.0, 7000.0), (9100.0, 7000.0)), ("d7i0",), viewport="vp"
    )

    assert not physical_wall_pair_is_identity_candidate(left, right)
    resolution = resolve_physical_wall_equivalence((left, right))
    assert set(resolution.representative_wall_ids) == {"ss-a", "ss-b"}


# --- Always-eligible fail-closed paths ------------------------------------


def test_shared_source_primitive_always_remains_a_candidate() -> None:
    """Shared provenance keeps the pair eligible however far apart it is.

    Classification then applies unchanged: shared ancestry with proven
    disjoint spans is the pre-existing positive DISTINCT rule, so both may
    publish. The point is that the gate did not silently skip the pair.
    """
    left = _ident("p-a", ((0.0, 0.0), (10.0, 0.0)), ("d1i0",))
    right = _ident("p-b", ((5000.0, 5000.0), (5010.0, 5000.0)), ("d1i0",))

    assert physical_wall_pair_is_identity_candidate(left, right)

    resolution = resolve_physical_wall_equivalence((left, right))
    assert resolution.candidate_pair_audit.considered_pairs == 1
    assert resolution.candidate_pair_audit.excluded_pairs == 0
    assert resolution.pair_classifications == (
        ("p-a", "p-b", DISTINCT.value),
    )


def test_shared_primitive_with_overlapping_span_still_abstains() -> None:
    """Shared ancestry without proven disjointness must stay fail-closed."""
    left = _ident("pv-a", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",))
    right = _ident("pv-b", ((400.0, 0.0), (1400.0, 0.0)), ("d1i0",))

    assert physical_wall_pair_is_identity_candidate(left, right)
    assert classify_physical_wall_pair(left, right) is AMBIGUOUS
    resolution = resolve_physical_wall_equivalence((left, right))
    assert resolution.representative_wall_ids == ()


def test_identical_fingerprint_far_apart_remains_a_candidate() -> None:
    path = ((0.0, 0.0), (100.0, 0.0))
    left = _ident("fp-a", path, ("d1i0",))
    right = _ident("fp-b", path, ("d9i0",))

    assert physical_wall_pair_is_identity_candidate(left, right)


def test_unusable_identity_never_escapes_classification() -> None:
    usable = _ident("u-ok", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    unusable = PhysicalWallIdentity(
        wall_candidate_id="u-bad",
        viewport_id="vp",
        candidate_identity_id=None,
        path_fingerprint=None,
        source_primitive_ids=(),
        edge_ids=(),
        status=EvidenceResolutionStatus.ABSTAINED,
        blocking_reasons=("physical_identity_edge_missing",),
    )

    assert physical_wall_pair_is_identity_candidate(usable, unusable)
    resolution = resolve_physical_wall_equivalence((usable, unusable))
    assert "u-bad" in resolution.abstained_wall_ids


def test_collinear_touching_paths_remain_identity_candidates() -> None:
    left = _ident("c-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    continuation = _ident("c-b", ((100.0, 0.0), (220.0, 0.0)), ("d9i0",))

    assert physical_wall_pair_is_identity_candidate(left, continuation)
    resolution = resolve_physical_wall_equivalence((left, continuation))
    assert resolution.representative_wall_ids == ()


def test_perpendicular_touching_paths_are_not_identity_candidates() -> None:
    left = _ident("x-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    crossing = _ident("x-b", ((50.0, -40.0), (50.0, 40.0)), ("d9i0",))

    eligible, reason = physical_wall_pair_identity_candidacy(left, crossing)
    assert not eligible
    assert reason == PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE
    resolution = resolve_physical_wall_equivalence((left, crossing))
    assert set(resolution.representative_wall_ids) == {"x-a", "x-b"}
    assert resolution.ambiguous_wall_ids == ()


# ===========================================================================
# REQUIRED CHANGE 6 -- excluded-pair diagnostics
# ===========================================================================


def test_candidate_pair_audit_reports_totals_and_reasons() -> None:
    walls = (
        # perpendicular -> orientation incompatible
        _ident("a-h", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",)),
        _ident("a-v", ((900.0, 200.0), (900.0, 320.0)), ("d2i0",)),
        # collinear, no overlap -> no longitudinal overlap
        _ident("a-far", ((4000.0, 0.0), (4100.0, 0.0)), ("d3i0",)),
    )

    audit = resolve_physical_wall_equivalence(walls).candidate_pair_audit

    assert audit.total_pairs == 3
    assert audit.excluded_pairs == 3
    assert audit.considered_pairs == 0
    assert sum(audit.exclusion_reason_counts.values()) == 3
    assert set(audit.exclusion_reason_counts) <= {
        PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE,
        PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP,
        PAIR_EXCLUDED_SEPARATION_BEYOND_BAND,
    }


def test_candidate_pair_audit_counts_considered_pairs() -> None:
    face_a, face_b = _face_pair(6.0)
    audit = resolve_physical_wall_equivalence((face_a, face_b)).candidate_pair_audit

    assert audit.total_pairs == 1
    assert audit.considered_pairs == 1
    assert audit.excluded_pairs == 0
    assert audit.exclusion_reason_counts == {}


def test_audit_reason_counts_are_exhaustive_over_excluded_pairs() -> None:
    walls = tuple(
        _ident(
            f"e{index}",
            ((index * 1000.0, index * 1000.0), (index * 1000.0 + 80.0, index * 1000.0)),
            (f"d{index}i0",),
        )
        for index in range(6)
    )
    audit = resolve_physical_wall_equivalence(walls).candidate_pair_audit

    assert audit.total_pairs == 15
    assert audit.considered_pairs + audit.excluded_pairs == audit.total_pairs
    assert sum(audit.exclusion_reason_counts.values()) == audit.excluded_pairs


# ===========================================================================
# REQUIRED CHANGE 5 -- trusted overrides must survive the narrowing
# ===========================================================================


def _reconcile(identities, overrides, **kwargs):
    import pb_physical_wall_candidate_authority as module

    baseline = resolve_physical_wall_equivalence(identities)
    return baseline, module._apply_trusted_relation_overrides(
        identities, baseline, overrides, **kwargs
    )


def test_opening_pattern_override_is_restored_after_narrowing() -> None:
    """A proven opening-pattern SAME relation must survive exclusion."""
    left = _ident("op-left", ((0.0, 0.0), (1000.0, 0.0)), ("d1i0",))
    right = _ident("op-right", ((1900.0, 0.0), (2900.0, 0.0)), ("d1i5",))

    baseline, resolved = _reconcile(
        (left, right), {("op-left", "op-right"): SAME}
    )

    # The gate excluded the pair, so it is absent from the baseline...
    assert baseline.pair_classifications == ()
    # ...and the producer's positive proof restores it rather than vanishing.
    assert resolved.pair_classifications == (
        ("op-left", "op-right", SAME.value),
    )
    assert resolved.equivalence_groups == (("op-left", "op-right"),)
    assert resolved.representative_wall_ids == ("op-left",)
    assert resolved.candidate_pair_audit.trusted_override_pairs_restored == 1
    assert resolved.candidate_pair_audit.total_pairs == baseline.candidate_pair_audit.total_pairs
    assert resolved.candidate_pair_audit.considered_pairs == baseline.candidate_pair_audit.considered_pairs
    assert resolved.candidate_pair_audit.excluded_pairs == baseline.candidate_pair_audit.excluded_pairs
    assert (
        resolved.candidate_pair_audit.exclusion_reason_counts
        == baseline.candidate_pair_audit.exclusion_reason_counts
    )


def test_wall_strip_override_is_restored_after_narrowing() -> None:
    """A proven filled-strip SAME relation must survive exclusion."""
    face_a = _ident("st-a", ((0.0, 0.0), (2000.0, 0.0)), ("d2i0",))
    face_b = _ident(
        "st-b",
        ((0.0, MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT * 4.0), (2000.0, MAX_PLAUSIBLE_WALL_BODY_SOURCE_PT * 4.0)),
        ("d2i7",),
    )

    baseline, resolved = _reconcile(
        (face_a, face_b),
        {("st-a", "st-b"): SAME},
        allow_proven_same_over_distinct=True,
    )

    assert baseline.pair_classifications == ()
    assert resolved.equivalence_groups == (("st-a", "st-b"),)
    assert resolved.candidate_pair_audit.trusted_override_pairs_restored == 1


def test_shared_source_face_override_is_restored_after_narrowing() -> None:
    left = _ident("sf-a", ((0.0, 0.0), (500.0, 0.0)), ("d3i0",))
    right = _ident("sf-b", ((4000.0, 3000.0), (4500.0, 3000.0)), ("d3i9",))

    _baseline, resolved = _reconcile(
        (left, right),
        {("sf-a", "sf-b"): SAME},
        allow_proven_same_over_distinct=True,
    )

    assert resolved.equivalence_groups == (("sf-a", "sf-b"),)
    assert resolved.candidate_pair_audit.trusted_override_pairs_restored == 1


def test_restored_distinct_override_lets_both_publish() -> None:
    left = _ident("rd-a", ((0.0, 0.0), (500.0, 0.0)), ("d3i0",))
    right = _ident("rd-b", ((4000.0, 3000.0), (4500.0, 3000.0)), ("d3i9",))

    _baseline, resolved = _reconcile(
        (left, right), {("rd-a", "rd-b"): DISTINCT}
    )

    assert resolved.pair_classifications == (
        ("rd-a", "rd-b", DISTINCT.value),
    )
    assert set(resolved.representative_wall_ids) == {"rd-a", "rd-b"}


def test_override_for_unknown_wall_is_explicitly_rejected() -> None:
    """An override outside the usable member set is rejected, not applied."""
    left = _ident("k-a", ((0.0, 0.0), (500.0, 0.0)), ("d3i0",))
    right = _ident("k-b", ((4000.0, 3000.0), (4500.0, 3000.0)), ("d3i9",))

    _baseline, resolved = _reconcile(
        (left, right), {("k-a", "ghost-wall"): SAME}
    )

    assert resolved.candidate_pair_audit.trusted_override_pairs_restored == 0
    assert resolved.candidate_pair_audit.trusted_override_pairs_rejected == 1
    import pb_physical_wall_candidate_authority as module
    assert resolved.candidate_pair_audit.trusted_override_rejection_reason_counts == {
        module.TRUSTED_EQUIVALENCE_OVERRIDE_UNKNOWN_MEMBER: 1
    }
    assert all(
        "ghost-wall" not in pair
        for pair in resolved.pair_classifications
    )


def test_override_cannot_demote_a_proven_same_pair() -> None:
    """Positive SAME already established is not overwritten by DISTINCT."""
    same_a = _ident("dm-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))
    same_b = _ident("dm-b", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))

    baseline, resolved = _reconcile(
        (same_a, same_b), {("dm-a", "dm-b"): DISTINCT}
    )

    assert baseline.pair_classifications == (("dm-a", "dm-b", SAME.value),)
    assert resolved.pair_classifications == (("dm-a", "dm-b", SAME.value),)
    assert resolved.candidate_pair_audit.trusted_override_pairs_rejected == 1
    import pb_physical_wall_candidate_authority as module
    assert resolved.candidate_pair_audit.trusted_override_rejection_reason_counts == {
        module.TRUSTED_EQUIVALENCE_OVERRIDE_CONFLICT: 1
    }


def test_override_audit_accumulates_across_multiple_producer_passes() -> None:
    import pb_physical_wall_candidate_authority as module

    left = _ident("acc-a", ((0.0, 0.0), (500.0, 0.0)), ("d3i0",))
    right = _ident("acc-b", ((4000.0, 3000.0), (4500.0, 3000.0)), ("d9i0",))
    baseline = resolve_physical_wall_equivalence((left, right))
    first = module._apply_trusted_relation_overrides(
        (left, right),
        baseline,
        {("acc-a", "acc-b"): SAME},
    )
    second = module._apply_trusted_relation_overrides(
        (left, right),
        first,
        {("acc-a", "ghost"): SAME},
    )

    assert second.candidate_pair_audit.total_pairs == baseline.candidate_pair_audit.total_pairs
    assert second.candidate_pair_audit.considered_pairs == baseline.candidate_pair_audit.considered_pairs
    assert second.candidate_pair_audit.excluded_pairs == baseline.candidate_pair_audit.excluded_pairs
    assert second.candidate_pair_audit.trusted_override_pairs_restored == 1
    assert second.candidate_pair_audit.trusted_override_pairs_rejected == 1
    assert second.candidate_pair_audit.trusted_override_rejection_reason_counts == {
        module.TRUSTED_EQUIVALENCE_OVERRIDE_UNKNOWN_MEMBER: 1
    }


def test_idempotent_trusted_override_is_not_counted_as_rejected() -> None:
    same_a = _ident("idem-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))
    same_b = _ident("idem-b", ((0.0, 0.0), (100.0, 0.0)), ("d1i0", "d1i1"))
    baseline, resolved = _reconcile(
        (same_a, same_b),
        {("idem-a", "idem-b"): SAME},
    )
    assert baseline.pair_classifications == resolved.pair_classifications
    assert resolved.candidate_pair_audit.trusted_override_pairs_rejected == 0
    assert resolved.candidate_pair_audit.trusted_override_rejection_reason_counts == {}


def test_no_overrides_leaves_narrowed_baseline_untouched() -> None:
    walls = tuple(
        _ident(wid, path, prims) for wid, path, prims in _UNRELATED_PATHS
    )
    baseline, resolved = _reconcile(walls, {})

    assert resolved is baseline
    assert set(baseline.representative_wall_ids) == {"w1", "w2", "w3"}


# ===========================================================================
# INVARIANCE
# ===========================================================================


def _transform(path, *, angle=0.0, dx=0.0, dy=0.0, scale=1.0):
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return tuple(
        (
            scale * (x * cos_a - y * sin_a) + dx,
            scale * (x * sin_a + y * cos_a) + dy,
        )
        for x, y in path
    )


_UNRELATED_PATHS = (
    ("w1", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",)),
    ("w2", ((3000.0, 2000.0), (3000.0, 2120.0)), ("d4i0",)),
    ("w3", ((6000.0, 5000.0), (6100.0, 5050.0)), ("d7i0",)),
)

_FACE_PAIR_PATHS = (
    ("f-a", ((0.0, 0.0), (3000.0, 0.0)), ("d1i0",)),
    ("f-b", ((0.0, 6.0), (3000.0, 6.0)), ("d1i9",)),
)

_TRANSFORMS = [
    (0.0, 0.0, 0.0, 1.0),
    (0.0, 1234.5, -987.6, 1.0),
    (math.pi / 6.0, 0.0, 0.0, 1.0),
    (math.pi / 4.0, 50.0, 50.0, 1.0),
    (math.pi / 3.0, -400.0, 250.0, 1.0),
]


@pytest.mark.parametrize("angle,dx,dy,scale", _TRANSFORMS)
def test_unrelated_walls_publish_under_rigid_transforms(angle, dx, dy, scale) -> None:
    walls = tuple(
        _ident(wid, _transform(path, angle=angle, dx=dx, dy=dy, scale=scale), prims)
        for wid, path, prims in _UNRELATED_PATHS
    )
    resolution = resolve_physical_wall_equivalence(walls)
    assert set(resolution.representative_wall_ids) == {"w1", "w2", "w3"}


@pytest.mark.parametrize("angle,dx,dy,scale", _TRANSFORMS)
def test_face_pair_stays_ambiguous_under_rigid_transforms(angle, dx, dy, scale) -> None:
    walls = tuple(
        _ident(wid, _transform(path, angle=angle, dx=dx, dy=dy, scale=scale), prims)
        for wid, path, prims in _FACE_PAIR_PATHS
    )
    resolution = resolve_physical_wall_equivalence(walls)
    assert resolution.representative_wall_ids == ()
    assert set(resolution.ambiguous_wall_ids) == {"f-a", "f-b"}


@pytest.mark.parametrize("scale", [0.25, 0.5, 2.0, 4.0])
def test_scaling_geometry_and_band_together_preserves_outcome(scale) -> None:
    """Scaling the drawing and the verified scale together is invariant."""
    faces = tuple(
        _ident(wid, _transform(path, scale=scale), prims)
        for wid, path, prims in _FACE_PAIR_PATHS
    )
    resolution = resolve_physical_wall_equivalence(
        faces, points_per_mm=_POINTS_PER_MM_AT_1_50 * scale
    )
    assert resolution.representative_wall_ids == ()

    unrelated = tuple(
        _ident(wid, _transform(path, scale=scale), prims)
        for wid, path, prims in _UNRELATED_PATHS
    )
    resolution = resolve_physical_wall_equivalence(
        unrelated, points_per_mm=_POINTS_PER_MM_AT_1_50 * scale
    )
    assert set(resolution.representative_wall_ids) == {"w1", "w2", "w3"}


def test_input_order_does_not_change_published_representatives() -> None:
    walls = {wid: _ident(wid, path, prims) for wid, path, prims in _UNRELATED_PATHS}
    expected = None
    for order in itertools.permutations(walls):
        resolution = resolve_physical_wall_equivalence(
            tuple(walls[wid] for wid in order)
        )
        published = tuple(sorted(resolution.representative_wall_ids))
        if expected is None:
            expected = published
        assert published == expected


def test_stable_ids_are_deterministic_across_repeated_resolution() -> None:
    walls = tuple(
        _ident(wid, path, prims) for wid, path, prims in _UNRELATED_PATHS
    )
    first = resolve_physical_wall_equivalence(walls)
    for _ in range(4):
        again = resolve_physical_wall_equivalence(walls)
        assert again.representative_wall_ids == first.representative_wall_ids
        assert again.pair_classifications == first.pair_classifications
        assert again.equivalence_groups == first.equivalence_groups


def test_split_segments_do_not_change_eligibility() -> None:
    whole = _ident("sp-a", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",))
    split = _ident(
        "sp-a",
        ((0.0, 0.0), (25.0, 0.0), (60.0, 0.0), (100.0, 0.0)),
        ("d1i0",),
    )
    unrelated = _ident("sp-far", ((8000.0, 6000.0), (8100.0, 6000.0)), ("d9i0",))
    face = _ident("sp-face", ((0.0, 6.0), (100.0, 6.0)), ("d1i8",))

    assert physical_wall_pair_is_identity_candidate(
        whole, unrelated
    ) is physical_wall_pair_is_identity_candidate(split, unrelated)
    assert physical_wall_pair_is_identity_candidate(
        whole, face
    ) is physical_wall_pair_is_identity_candidate(split, face)

    assert set(
        resolve_physical_wall_equivalence((split, unrelated)).representative_wall_ids
    ) == {"sp-a", "sp-far"}


@pytest.mark.parametrize("noise", [0.0, 1e-9, 1e-7, 1e-5, 1e-4, 1e-3, 1e-2])
def test_small_coordinate_noise_does_not_flip_outcomes(noise) -> None:
    """Sub-drafting coordinate jitter must not change publication."""
    unrelated = (
        _ident("n1", ((0.0, 0.0), (100.0, 0.0)), ("d1i0",)),
        _ident(
            "n2",
            ((3000.0 + noise, 2000.0 - noise), (3000.0 - noise, 2120.0 + noise)),
            ("d4i0",),
        ),
    )
    assert set(
        resolve_physical_wall_equivalence(unrelated).representative_wall_ids
    ) == {"n1", "n2"}

    faces = (
        _ident("nf-a", ((0.0, 0.0), (3000.0, 0.0)), ("d1i0",)),
        _ident(
            "nf-b",
            ((0.0 + noise, 6.0), (3000.0 - noise, 6.0 + noise)),
            ("d1i9",),
        ),
    )
    assert resolve_physical_wall_equivalence(faces).representative_wall_ids == ()


def test_eligibility_is_symmetric() -> None:
    cases = (
        (_UNRELATED_PATHS[0], _UNRELATED_PATHS[1]),
        (_FACE_PAIR_PATHS[0], _FACE_PAIR_PATHS[1]),
        (_UNRELATED_PATHS[0], _FACE_PAIR_PATHS[1]),
        (_UNRELATED_PATHS[1], _UNRELATED_PATHS[2]),
    )
    for (lid, lpath, lprims), (rid, rpath, rprims) in cases:
        left = _ident(lid, lpath, lprims)
        right = _ident(rid, rpath, rprims)
        assert physical_wall_pair_is_identity_candidate(
            left, right
        ) is physical_wall_pair_is_identity_candidate(right, left)
