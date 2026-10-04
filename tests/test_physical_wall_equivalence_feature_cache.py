"""Differential gates for cached physical-wall equivalence features."""
from __future__ import annotations

import random

import pb_physical_wall_identity as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP,
    PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE,
    PAIR_EXCLUDED_SEPARATION_BEYOND_BAND,
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
    physical_wall_pair_identity_candidacy,
    resolve_physical_wall_equivalence,
)


def _identity(
    wall_id: str,
    *,
    path=((0.0, 0.0), (100.0, 0.0)),
    primitives=("p0",),
    viewport="v",
    level=None,
    usable=True,
):
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=viewport,
        candidate_identity_id=(f"cid:{wall_id}" if usable else None),
        path_fingerprint=(tuple(path) if path is not None else None),
        source_primitive_ids=tuple(primitives),
        edge_ids=(f"edge:{wall_id}",),
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if usable
            else EvidenceResolutionStatus.ABSTAINED
        ),
        blocking_reasons=(() if usable else ("blocked",)),
        level_id=level,
    )


def _legacy_candidacy(left, right, *, points_per_mm=None):
    if not left.usable or not right.usable:
        return True, None
    if set(left.source_primitive_ids) & set(right.source_primitive_ids):
        return True, None
    if (
        left.path_fingerprint is not None
        and left.path_fingerprint == right.path_fingerprint
    ):
        return True, None

    left_level = str(left.level_id or "").strip()
    right_level = str(right.level_id or "").strip()
    if left.viewport_id != right.viewport_id or (
        bool(left_level) and bool(right_level) and left_level != right_level
    ):
        return True, None

    left_path = tuple(left.path_fingerprint or ())
    right_path = tuple(right.path_fingerprint or ())
    if len(left_path) < 2 or len(right_path) < 2:
        return True, None

    if module._paths_share_both_endpoints(
        left_path,
        right_path,
        module._EQUIVALENCE_LATERAL_TOL_PT,
    ):
        return True, None

    if module._paths_meet_as_same_wall_candidates(
        left_path,
        right_path,
        module._EQUIVALENCE_LATERAL_TOL_PT,
    ):
        return True, None

    band = module.max_plausible_wall_body_separation_pt(points_per_mm)
    saw_parallel = False
    saw_overlap = False
    for a in module._segments(left_path):
        for b in module._segments(right_path):
            relation = module._parallel_overlap_separation(
                a,
                b,
                angle_tolerance_deg=module._EQUIVALENCE_ANGLE_TOL_DEG,
            )
            if relation is None:
                continue
            saw_parallel = True
            overlap, separation = relation
            if overlap <= module._EQUIVALENCE_LATERAL_TOL_PT:
                continue
            saw_overlap = True
            if band is None or separation <= band:
                return True, None

    if not saw_parallel:
        return False, PAIR_EXCLUDED_ORIENTATION_INCOMPATIBLE
    if not saw_overlap:
        return False, PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP
    if band is None:
        return True, None
    return False, PAIR_EXCLUDED_SEPARATION_BEYOND_BAND


def _legacy_classify(left, right):
    if not left.usable or not right.usable:
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    left_level = str(left.level_id or "").strip()
    right_level = str(right.level_id or "").strip()
    cross_scope = (left.viewport_id != right.viewport_id) or (
        bool(left_level) and bool(right_level) and left_level != right_level
    )

    same_path = (
        left.path_fingerprint is not None
        and left.path_fingerprint == right.path_fingerprint
    )
    left_prims = tuple(left.source_primitive_ids)
    right_prims = tuple(right.source_primitive_ids)
    shared = set(left_prims) & set(right_prims)
    equal_ancestry = module._ancestry_equal(left_prims, right_prims)
    coverage_identical = module._ancestry_coverage_identical(
        left_prims, right_prims
    )

    if same_path and (equal_ancestry or coverage_identical) and not cross_scope:
        return PhysicalEquivalenceClass.SAME_PHYSICAL_WALL

    if same_path and not equal_ancestry:
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    left_iv = module._axis_interval(left.path_fingerprint or ())
    right_iv = module._axis_interval(right.path_fingerprint or ())

    if equal_ancestry and left_iv is not None and right_iv is not None:
        if module._intervals_disjoint(left_iv, right_iv):
            return PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    if shared and left_iv is not None and right_iv is not None:
        if module._intervals_overlap(left_iv, right_iv):
            return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
        return PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS

    return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _random_path(rng):
    kind = rng.randrange(7)
    x = rng.uniform(-300.0, 300.0)
    y = rng.uniform(-300.0, 300.0)
    if kind == 0:
        return None
    if kind == 1:
        return ((x, y),)
    if kind in (2, 3):
        return ((x, y), (x + rng.uniform(10, 200), y))
    if kind == 4:
        return ((x, y), (x, y + rng.uniform(10, 200)))
    if kind == 5:
        return (
            (x, y),
            (x + rng.uniform(10, 80), y + rng.uniform(-2, 2)),
            (x + rng.uniform(90, 200), y + rng.uniform(-2, 2)),
        )
    return (
        (x, y),
        (x + rng.uniform(10, 100), y + rng.uniform(10, 100)),
    )


def _random_identity(rng, index):
    pool = ("p0", "p1", "p2", "p3", "p4", "p5")
    count = rng.randrange(0, 4)
    primitives = tuple(rng.sample(pool, count))
    return _identity(
        f"w{index}",
        path=_random_path(rng),
        primitives=primitives,
        viewport=rng.choice(("v0", "v0", "v1")),
        level=rng.choice((None, "", "L1", "L1", "L2")),
        usable=rng.random() > 0.12,
    )


def test_cached_pair_functions_match_pre_cache_oracle_randomized():
    rng = random.Random(20260929)
    identities = [_random_identity(rng, i) for i in range(140)]
    scales = (None, 0.02, 0.1, 1.0)

    for _ in range(3500):
        left, right = rng.sample(identities, 2)
        scale = rng.choice(scales)
        assert physical_wall_pair_identity_candidacy(
            left, right, points_per_mm=scale
        ) == _legacy_candidacy(left, right, points_per_mm=scale)
        assert classify_physical_wall_pair(left, right) == _legacy_classify(
            left, right
        )


def test_cached_pair_functions_match_adversarial_explicit_cases():
    cases = [
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p",)),
            _identity("b", path=((0, 0), (100, 0)), primitives=("p",)),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p1",)),
            _identity("b", path=((0, 0), (100, 0)), primitives=("p2",)),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p",)),
            _identity("b", path=((110, 0), (210, 0)), primitives=("p",)),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p1",)),
            _identity("b", path=((0, 20), (100, 20)), primitives=("p2",)),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=()),
            _identity("b", path=((50, -50), (50, 50)), primitives=()),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p1",), viewport="v0"),
            _identity("b", path=((500, 500), (600, 500)), primitives=("p2",), viewport="v1"),
        ),
        (
            _identity("a", path=((0, 0), (100, 0)), primitives=("p1",), level="L1"),
            _identity("b", path=((500, 500), (600, 500)), primitives=("p2",), level="L2"),
        ),
        (
            _identity("a", usable=False),
            _identity("b"),
        ),
    ]

    for left, right in cases:
        for scale in (None, 0.01, 1.0):
            assert physical_wall_pair_identity_candidacy(
                left, right, points_per_mm=scale
            ) == _legacy_candidacy(left, right, points_per_mm=scale)
            assert classify_physical_wall_pair(left, right) == _legacy_classify(
                left, right
            )



def test_candidacy_computes_each_segment_pair_relation_once(monkeypatch):
    left = _identity(
        "left",
        path=((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)),
        primitives=("left-source",),
    )
    right = _identity(
        "right",
        path=((100.0, 5.0), (110.0, 5.0), (120.0, 5.0)),
        primitives=("right-source",),
    )

    original = module._parallel_overlap_separation
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_parallel_overlap_separation", counted)
    result = physical_wall_pair_identity_candidacy(
        left, right, points_per_mm=0.1
    )

    assert result == (False, PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP)
    assert calls == 4

def test_resolver_extracts_pair_features_once_per_usable_wall(monkeypatch):
    identities = [
        _identity(
            f"w{i}",
            path=((float(i) * 1000.0, 0.0), (float(i) * 1000.0 + 100.0, 0.0)),
            primitives=(f"p{i}",),
        )
        for i in range(180)
    ]

    original = module._physical_wall_pair_features
    calls = 0

    def counted(identity):
        nonlocal calls
        calls += 1
        return original(identity)

    monkeypatch.setattr(module, "_physical_wall_pair_features", counted)
    result = resolve_physical_wall_equivalence(identities, points_per_mm=0.1)

    assert calls == len(identities)
    assert result.candidate_pair_audit.total_pairs == (
        len(identities) * (len(identities) - 1) // 2
    )
    assert len(result.representative_wall_ids) == len(identities)


def test_public_standalone_pair_api_remains_self_contained(monkeypatch):
    left = _identity("a", path=((0, 0), (100, 0)), primitives=("p1",))
    right = _identity("b", path=((0, 10), (100, 10)), primitives=("p2",))

    calls = 0
    original = module._physical_wall_pair_features

    def counted(identity):
        nonlocal calls
        calls += 1
        return original(identity)

    monkeypatch.setattr(module, "_physical_wall_pair_features", counted)
    physical_wall_pair_identity_candidacy(left, right, points_per_mm=1.0)
    classify_physical_wall_pair(left, right)
    assert calls == 4


def test_full_resolver_matches_pre_cache_pair_logic(monkeypatch):
    rng = random.Random(424242)
    groups = []
    for group_index in range(20):
        identities = [
            _random_identity(rng, group_index * 20 + i)
            for i in range(12)
        ]
        groups.append((identities, rng.choice((None, 0.02, 0.1, 1.0))))

    cached_candidacy = module._physical_wall_pair_identity_candidacy_with_features
    cached_classify = module._classify_physical_wall_pair_with_features

    for identities, scale in groups:
        def legacy_candidacy(left, right, _lf, _rf, *, points_per_mm=None):
            return _legacy_candidacy(
                left, right, points_per_mm=points_per_mm
            )

        def legacy_classify(left, right, _lf, _rf):
            return _legacy_classify(left, right)

        monkeypatch.setattr(
            module,
            "_physical_wall_pair_identity_candidacy_with_features",
            legacy_candidacy,
        )
        monkeypatch.setattr(
            module,
            "_classify_physical_wall_pair_with_features",
            legacy_classify,
        )
        expected = resolve_physical_wall_equivalence(
            identities, points_per_mm=scale
        )

        monkeypatch.setattr(
            module,
            "_physical_wall_pair_identity_candidacy_with_features",
            cached_candidacy,
        )
        monkeypatch.setattr(
            module,
            "_classify_physical_wall_pair_with_features",
            cached_classify,
        )
        actual = resolve_physical_wall_equivalence(
            identities, points_per_mm=scale
        )

        assert actual == expected


def _legacy_segments_meet_within(left, right, tolerance):
    ax, ay, bx, by = left
    cx, cy, dx, dy = right

    def orient(x1, y1, x2, y2, x3, y3):
        return (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)

    o1 = orient(ax, ay, bx, by, cx, cy)
    o2 = orient(ax, ay, bx, by, dx, dy)
    o3 = orient(cx, cy, dx, dy, ax, ay)
    o4 = orient(cx, cy, dx, dy, bx, by)
    if ((o1 > 0.0) != (o2 > 0.0)) and ((o3 > 0.0) != (o4 > 0.0)):
        return True

    return min(
        module._point_segment_distance(cx, cy, left),
        module._point_segment_distance(dx, dy, left),
        module._point_segment_distance(ax, ay, right),
        module._point_segment_distance(bx, by, right),
    ) <= tolerance


def test_segment_contact_bbox_prefilter_matches_historical_randomized():
    rng = random.Random(20261004)
    for _ in range(5000):
        left = tuple(rng.uniform(-500.0, 500.0) for _ in range(4))
        right = tuple(rng.uniform(-500.0, 500.0) for _ in range(4))
        tolerance = rng.choice((0.0, 0.1, 0.5, 1.0, 2.0, 5.0))
        assert module._segments_meet_within(
            left, right, tolerance
        ) == _legacy_segments_meet_within(left, right, tolerance)


def test_segment_contact_bbox_prefilter_skips_impossible_distance_work(monkeypatch):
    def unexpected_distance(*_args, **_kwargs):
        raise AssertionError("distance work should be skipped for disjoint expanded bboxes")

    monkeypatch.setattr(module, "_point_segment_distance", unexpected_distance)
    assert not module._segments_meet_within(
        (0.0, 0.0, 10.0, 0.0),
        (100.0, 100.0, 110.0, 100.0),
        1.0,
    )


def test_segment_contact_bbox_prefilter_keeps_exact_tolerance_boundary():
    assert module._segments_meet_within(
        (0.0, 0.0, 10.0, 0.0),
        (11.0, 0.0, 20.0, 0.0),
        1.0,
    )
