"""Differential and scaling gates for cached wall-segment unit vectors."""
from __future__ import annotations

import random

import pb_physical_wall_identity as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import PhysicalWallIdentity, resolve_physical_wall_equivalence


def _identity(index, path):
    return PhysicalWallIdentity(
        wall_candidate_id=f"w{index}",
        viewport_id="v",
        candidate_identity_id=f"cid:{index}",
        path_fingerprint=tuple(path),
        source_primitive_ids=(f"p{index}",),
        edge_ids=(f"e{index}",),
        status=EvidenceResolutionStatus.CORROBORATED,
        blocking_reasons=(),
        level_id=None,
    )


def test_cached_parallel_relation_matches_existing_wrapper_randomized():
    rng = random.Random(991016)
    for _ in range(5000):
        left = (
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
        )
        right = (
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
            rng.uniform(-500, 500),
        )
        expected = module._parallel_overlap_separation(
            left,
            right,
            angle_tolerance_deg=module._EQUIVALENCE_ANGLE_TOL_DEG,
        )
        actual = module._parallel_overlap_separation_with_units(
            left,
            right,
            module._unit(left),
            module._unit(right),
            angle_tolerance_deg=module._EQUIVALENCE_ANGLE_TOL_DEG,
        )
        assert actual == expected


def test_cached_meeting_predicate_matches_existing_wrapper_randomized():
    rng = random.Random(991017)
    for _ in range(1200):
        left = tuple(
            (
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
            )
            for _ in range(rng.randrange(1, 5))
        )
        right = tuple(
            (
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
                rng.uniform(-200, 200),
            )
            for _ in range(rng.randrange(1, 5))
        )
        expected = module._segments_meet_as_same_wall_candidates(
            left,
            right,
            module._EQUIVALENCE_LATERAL_TOL_PT,
        )
        actual = module._segments_meet_as_same_wall_candidates_with_units(
            left,
            right,
            tuple(module._unit(segment) for segment in left),
            tuple(module._unit(segment) for segment in right),
            module._EQUIVALENCE_LATERAL_TOL_PT,
        )
        assert actual == expected


def test_resolver_computes_segment_units_once_per_wall_feature(monkeypatch):
    identities = []
    total_segments = 0
    for i in range(240):
        x = float(i * 50)
        path = ((x, 0.0), (x + 20.0, 0.0), (x + 40.0, 0.0))
        identities.append(_identity(i, path))
        total_segments += 2

    original = module._unit
    calls = 0

    def counted(segment):
        nonlocal calls
        calls += 1
        return original(segment)

    monkeypatch.setattr(module, "_unit", counted)
    result = resolve_physical_wall_equivalence(identities, points_per_mm=0.1)

    assert result.candidate_pair_audit.total_pairs == 240 * 239 // 2
    assert calls == total_segments


def test_full_resolver_result_matches_without_cached_units(monkeypatch):
    rng = random.Random(991018)
    identities = []
    for i in range(80):
        x = rng.uniform(-400, 400)
        y = rng.uniform(-400, 400)
        if i % 5 == 0:
            path = ((x, y), (x + 80.0, y), (x + 160.0, y))
        elif i % 5 == 1:
            path = ((x, y), (x, y + 120.0))
        else:
            path = ((x, y), (x + rng.uniform(20, 160), y + rng.uniform(-8, 8)))
        identities.append(_identity(i, path))

    cached = resolve_physical_wall_equivalence(identities, points_per_mm=0.08)

    original_cached_relation = module._parallel_overlap_separation_with_units
    def uncached_relation(left, right, _lu, _ru, *, angle_tolerance_deg):
        return original_cached_relation(
            left,
            right,
            module._unit(left),
            module._unit(right),
            angle_tolerance_deg=angle_tolerance_deg,
        )

    monkeypatch.setattr(
        module,
        "_parallel_overlap_separation_with_units",
        uncached_relation,
    )
    uncached = resolve_physical_wall_equivalence(identities, points_per_mm=0.08)
    assert cached == uncached
