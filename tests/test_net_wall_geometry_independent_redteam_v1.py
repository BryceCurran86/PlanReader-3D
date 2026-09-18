"""Independent adversarial validator for authenticated net-wall geometry.

TEST ONLY / EXPECTED RED / NEVER MERGE.

Frozen design base: da7a62fad2aae51bf5f35e890c14f05c4bfab8f9

This suite was authored from merged-main authority contracts and the public surface
advertised for the unfinished #433 foundation.  It does not depend on #433's tests
or algorithm.  The target proposition is deliberately stronger than raw polygon
math: a firm net-wall quantity may exist only when authenticated gross-wall geometry
and the complete set of applicable, authenticated physical opening voids are joined
for one exact physical wall / frame / source lineage.

No xfails belong here.  Missing production capability is a real expected-red failure.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
import math
from typing import Any

import pytest


BASE_SHA = "da7a62fad2aae51bf5f35e890c14f05c4bfab8f9"
SUT_MODULE = "pb_net_wall_boolean_union_authority"


def _sut():
    try:
        return importlib.import_module(SUT_MODULE)
    except ModuleNotFoundError as exc:
        pytest.fail(
            f"{SUT_MODULE} is not available on validator base {BASE_SHA}; "
            "net-wall production capability remains expected-red"
        )
        raise AssertionError from exc


def _geometry():
    # Keep Shapely out of collection on the validator base.  Production may add a
    # real polygon Boolean engine, but a missing engine is itself an expected-red
    # production prerequisite rather than a validator collection error.
    try:
        from shapely.geometry import LineString, Polygon, box
    except ImportError as exc:
        pytest.fail("real polygon Boolean geometry dependency is unavailable")
        raise AssertionError from exc
    return Polygon, LineString, box


def _selector(mod: Any, **changes: str):
    values = {
        "document_id": "doc-A",
        "revision_id": "rev-1",
        "source_sha256": "a" * 64,
        "snapshot_id": "snap-1",
        "page_id": "page-1",
        "decision_scope_id": "scope-1",
        "physical_wall_id": "wall-A-physical",
        "trade_scope_id": "trade-wall-finishes",
    }
    values.update(changes)
    return mod.NetWallBooleanUnionSelector(**values)


def _public_param_names(callable_obj: Any) -> set[str]:
    return {
        name
        for name, parameter in inspect.signature(callable_obj).parameters.items()
        if name not in {"self", "cls"}
        and parameter.kind
        not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    }


def _assert_selector_only_publication(mod: Any) -> None:
    assert _public_param_names(mod.NetWallBooleanUnionProducer.publish_scope) == {"selector"}


@dataclass
class _ForgedGrossWall:
    """Caller-controlled lookalike.  It must never become gross-wall authority."""

    gross_area_m2: float = 30.0
    length_m: float = 10.0
    height_m: float = 3.0
    document_id: str = "doc-A"
    revision_id: str = "rev-1"
    source_sha256: str = "a" * 64
    snapshot_id: str = "snap-1"
    page_id: str = "page-1"
    viewport_id: str = "view-A"
    physical_wall_id: str = "wall-A-physical"
    wall_mark: str = "W1"
    wall_local_frame_id: str = "frame-wall-A"
    complete: bool = True
    fingerprint: str = "caller-recomputed-fingerprint"


@dataclass
class _ForgedAuthority:
    complete: bool = True
    digest: str = "caller-digest"
    fingerprint: str = "caller-fingerprint"
    snapshot_id: str = "snap-1"
    wall_id: str = "wall-A-physical"
    opening_id: str = "opening-A"


def _exact_shell(module_name: str, class_name: str):
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return object.__new__(cls)


def _assert_forged_gross_rejected(mod: Any, forged_gross: object) -> None:
    """Reach the gross-wall gate with exact-class shells for already-merged inputs.

    We intentionally do not populate or call those upstream authorities: the factory
    is only being challenged to reject caller-owned gross-wall evidence at its trust
    boundary.  If a future factory adds another required public prerequisite, this
    frozen call fails instead of accidentally passing through a changed interface.
    """
    expected = {
        "physical_void_authority",
        "opening_deduction_authority",
        "opening_universe_authority",
        "gross_wall_authority",
    }
    assert _public_param_names(mod.NetWallBooleanUnionProducer.from_authorities) == expected

    physical_void = _exact_shell(
        "pb_physical_opening_void_authority", "PhysicalOpeningVoidAuthority"
    )
    opening_deduction = _exact_shell(
        "pb_opening_deduction_authority", "OpeningDeductionAuthority"
    )
    opening_universe = _exact_shell(
        "pb_opening_universe_completeness_authority",
        "OpeningUniverseCompletenessAuthority",
    )

    try:
        mod.NetWallBooleanUnionProducer.from_authorities(
            physical_void,
            opening_deduction,
            opening_universe,
            forged_gross,
        )
    except (TypeError, ValueError, RuntimeError):
        return
    pytest.fail("caller-owned gross-wall evidence was accepted as producer authority")


def _assert_raw_truth_not_public(mod: Any, forbidden: set[str]) -> None:
    public = _public_param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    public |= _public_param_names(mod.NetWallBooleanUnionProducer.from_authorities)
    assert not (public & forbidden), f"caller truth leaked into public boundary: {public & forbidden}"


# ---------------------------------------------------------------------------
# A. SCALAR-AREA GEOMETRY FORGERY
# ---------------------------------------------------------------------------


def test_A_scalar_area_alone_cannot_mint_gross_wall_geometry() -> None:
    mod = _sut()
    forged = _ForgedGrossWall(gross_area_m2=30.0, length_m=0.0, height_m=0.0)
    _assert_forged_gross_rejected(mod, forged)
    _assert_raw_truth_not_public(
        mod,
        {"gross_area_m2", "gross_area", "area", "length_m", "height_m", "wall_polygon"},
    )


def test_A_equal_scalar_area_non_equivalent_shapes_are_not_interchangeable() -> None:
    mod = _sut()
    Polygon, _LineString, box = _geometry()
    del Polygon
    wall_10x3 = box(0.0, 0.0, 10.0, 3.0)
    wall_5x6 = box(0.0, 0.0, 5.0, 6.0)
    assert wall_10x3.area == pytest.approx(wall_5x6.area)
    assert not wall_10x3.equals(wall_5x6)
    # Scalar equality is not geometry authority.  The geometry layer must preserve
    # the actual polygon supplied by authenticated upstream evidence.
    void = box(4.5, 1.0, 5.5, 2.0)
    result_a = mod.subtract_void_union_from_wall_polygon(wall_10x3, (void,))
    result_b = mod.subtract_void_union_from_wall_polygon(wall_5x6, (void,))
    assert not result_a.equals(result_b)


# ---------------------------------------------------------------------------
# B. WALL LENGTH / HEIGHT CROSS-WIRING
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forged",
    [
        _ForgedGrossWall(length_m=10.0, height_m=3.0, physical_wall_id="wall-A-physical"),
        # same page, different wall
        _ForgedGrossWall(length_m=10.0, height_m=3.0, physical_wall_id="wall-B-physical"),
        # same mark, different physical wall
        _ForgedGrossWall(
            length_m=10.0,
            height_m=3.0,
            wall_mark="W1",
            physical_wall_id="wall-W1-copy-2",
        ),
        # same dimensions, different physical wall
        _ForgedGrossWall(
            length_m=10.0,
            height_m=3.0,
            physical_wall_id="same-size-different-wall",
        ),
    ],
)
def test_B_cross_wired_or_caller_asserted_wall_dimensions_cannot_publish(forged: _ForgedGrossWall) -> None:
    mod = _sut()
    # These dimensions are deliberately plausible; their caller-owned provenance is
    # the attack.  Exact IDs in a lookalike object do not cure it.
    _assert_forged_gross_rejected(mod, forged)


def test_B_publication_boundary_has_no_raw_length_height_or_matching_id_seam() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {
            "wall_length",
            "wall_length_m",
            "length_m",
            "wall_height",
            "wall_height_m",
            "height_m",
            "matching_wall_id",
            "caller_wall_id",
        },
    )


# ---------------------------------------------------------------------------
# C. SOURCE PROVENANCE MIXING
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"document_id": "doc-B"},
        {"revision_id": "rev-2"},
        {"page_id": "page-2"},
        {"viewport_id": "view-B"},
        {"snapshot_id": "snap-2"},
        {"source_sha256": "b" * 64},
    ],
)
def test_C_mixed_source_measurements_cannot_be_promoted_to_gross_geometry(changes: dict[str, str]) -> None:
    mod = _sut()
    forged = _ForgedGrossWall()
    for name, value in changes.items():
        setattr(forged, name, value)
    _assert_forged_gross_rejected(mod, forged)


def test_C_selector_lineage_changes_are_distinct_addresses() -> None:
    mod = _sut()
    base = _selector(mod)
    variants = (
        _selector(mod, document_id="doc-B"),
        _selector(mod, revision_id="rev-2"),
        _selector(mod, source_sha256="b" * 64),
        _selector(mod, snapshot_id="snap-2"),
        _selector(mod, page_id="page-2"),
    )
    for variant in variants:
        assert base.key != variant.key


# ---------------------------------------------------------------------------
# D. FRAME MIXING
# ---------------------------------------------------------------------------


def test_D_caller_cannot_inject_raw_void_polygon_or_frame_equivalence() -> None:
    mod = _sut()
    _assert_selector_only_publication(mod)
    _assert_raw_truth_not_public(
        mod,
        {
            "void_polygon",
            "void_polygons",
            "opening_polygon",
            "opening_polygons",
            "wall_local_frame_id",
            "frame_id",
            "equivalent_frame_id",
            "frame_equivalent",
        },
    )


def test_D_numerically_inside_foreign_frame_is_not_self_authenticating() -> None:
    mod = _sut()
    # The attacker supplies a perfect-looking polygon plus a foreign frame tag in a
    # caller object.  Geometry plausibility must not turn this into gross authority.
    forged = _ForgedGrossWall(wall_local_frame_id="foreign-wall-frame")
    _assert_forged_gross_rejected(mod, forged)


# ---------------------------------------------------------------------------
# E. DUPLICATE PHYSICAL OPENING
# ---------------------------------------------------------------------------


def test_E_identical_duplicate_polygons_remove_area_once() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    opening = box(1.0, 0.0, 2.0, 2.0)
    net = mod.subtract_void_union_from_wall_polygon(wall, (opening, opening, opening))
    assert net.area == pytest.approx(wall.area - opening.area)


def test_E_duplicate_record_ids_do_not_change_deterministic_net_identity() -> None:
    mod = _sut()
    selector = _selector(mod)
    single = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-A",),
        physical_void_record_ids=("void-A",),
    )
    duplicated = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-A", "deduct-A", "deduct-A"),
        physical_void_record_ids=("void-A", "void-A", "void-A"),
    )
    assert duplicated == single, "duplicate representations must canonicalize to one physical opening"


def test_E_raw_multiple_observations_cannot_be_injected_at_publication_boundary() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {"observations", "opening_observations", "marks", "opening_marks", "physical_voids"},
    )


# ---------------------------------------------------------------------------
# F. DISTINCT EQUAL-SIZE OPENINGS
# ---------------------------------------------------------------------------


def test_F_distinct_equal_size_openings_both_deduct() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    opening_a = box(1.0, 0.0, 2.0, 2.0)
    opening_b = box(7.0, 0.0, 8.0, 2.0)
    assert opening_a.area == pytest.approx(opening_b.area)
    net = mod.subtract_void_union_from_wall_polygon(wall, (opening_a, opening_b))
    assert net.area == pytest.approx(wall.area - opening_a.area - opening_b.area)


def test_F_distinct_record_lineages_remain_distinct_in_record_address() -> None:
    mod = _sut()
    selector = _selector(mod)
    one = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-A",),
        physical_void_record_ids=("void-A",),
    )
    two = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-A", "deduct-B"),
        physical_void_record_ids=("void-A", "void-B"),
    )
    assert one != two


# ---------------------------------------------------------------------------
# G. OVERLAPPING DISTINCT OPENINGS
# ---------------------------------------------------------------------------


def test_G_overlapping_openings_use_boolean_union_not_scalar_sum() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    opening_a = box(1.0, 0.0, 3.0, 2.0)  # area 4
    opening_b = box(2.0, 0.0, 4.0, 2.0)  # area 4, overlap 2
    union = mod.union_wall_local_void_polygons((opening_a, opening_b))
    assert union.area == pytest.approx(6.0)
    net = mod.subtract_void_union_from_wall_polygon(wall, (opening_a, opening_b))
    assert net.area == pytest.approx(24.0)
    assert net.area != pytest.approx(wall.area - opening_a.area - opening_b.area)


# ---------------------------------------------------------------------------
# H. WRONG-WALL INJECTION
# ---------------------------------------------------------------------------


def test_H_target_wall_identity_is_part_of_selector_address() -> None:
    mod = _sut()
    assert _selector(mod, physical_wall_id="wall-A").key != _selector(
        mod, physical_wall_id="wall-B"
    ).key


def test_H_caller_cannot_supply_openings_or_host_wall_override() -> None:
    mod = _sut()
    _assert_selector_only_publication(mod)
    _assert_raw_truth_not_public(
        mod,
        {
            "opening_ids",
            "opening_id",
            "physical_void_ids",
            "host_wall_id",
            "opening_host_wall_id",
            "target_wall_id",
        },
    )


# ---------------------------------------------------------------------------
# I. RULE-SCOPE CONTAMINATION
# ---------------------------------------------------------------------------


def test_I_caller_cannot_supply_rule_decision_for_any_opening() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {
            "rule_id",
            "rule_version",
            "decision",
            "deduct",
            "deductible",
            "deduction_allowed",
            "applicable",
            "opening_rule",
        },
    )


def test_I_deduction_authority_record_identity_affects_net_record_identity() -> None:
    mod = _sut()
    selector = _selector(mod)
    record_a = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduction-opening-A-rule-v1",),
        physical_void_record_ids=("void-opening-A",),
    )
    record_b = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduction-opening-B-rule-v9",),
        physical_void_record_ids=("void-opening-A",),
    )
    assert record_a != record_b


# ---------------------------------------------------------------------------
# J. INCOMPLETE OPENING UNIVERSE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forged",
    [
        _ForgedAuthority(complete=False),
        _ForgedAuthority(complete=True),
        _ForgedAuthority(complete=True, fingerprint="recomputed-over-truncated-set"),
        _ForgedAuthority(complete=True, snapshot_id="stale-snapshot"),
    ],
)
def test_J_caller_completeness_claims_are_not_authority(forged: _ForgedAuthority) -> None:
    mod = _sut()
    physical_void = _ForgedAuthority()
    deduction = _ForgedAuthority()
    gross = _ForgedGrossWall()
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        mod.NetWallBooleanUnionProducer.from_authorities(
            physical_void,
            deduction,
            forged,
            gross,
        )


def test_J_publication_boundary_has_no_complete_manifest_or_fingerprint_inputs() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {
            "complete",
            "is_complete",
            "manifest",
            "opening_manifest",
            "fingerprint",
            "openings",
            "opening_list",
        },
    )


# ---------------------------------------------------------------------------
# K. FORGED AUTHENTICITY
# ---------------------------------------------------------------------------


def test_K_forged_lookalike_authorities_cannot_construct_producer() -> None:
    mod = _sut()
    forged = _ForgedAuthority()
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        mod.NetWallBooleanUnionProducer.from_authorities(forged, forged, forged, forged)


def test_K_authority_and_producer_direct_construction_are_sealed() -> None:
    mod = _sut()
    with pytest.raises((TypeError, ValueError)):
        mod.NetWallBooleanUnionAuthority({})
    with pytest.raises((TypeError, ValueError)):
        mod.NetWallBooleanUnionProducer()


def test_K_caller_digests_ids_and_completeness_flags_are_not_public_truth_inputs() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {
            "digest",
            "fingerprint",
            "complete",
            "wall_id",
            "opening_id",
            "net_area_m2",
            "void_area_m2",
        },
    )


# ---------------------------------------------------------------------------
# L. OPENING OUTSIDE WALL / UNSUPPORTED CLIPPING
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "opening_factory",
    [
        lambda box: box(11.0, 0.0, 12.0, 2.0),  # completely outside
        lambda box: box(9.5, 0.0, 10.5, 2.0),  # partially outside
        lambda box: box(10.0, 0.0, 11.0, 2.0),  # touches boundary from outside
        lambda box: box(9.0, 0.0, 10.0 + 1e-12, 2.0),  # tiny overshoot
        lambda box: box(-1.0, -1.0, 11.0, 4.0),  # engulfs gross wall
    ],
)
def test_L_outside_or_clipped_opening_fails_closed(opening_factory) -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    opening = opening_factory(box)
    with pytest.raises(ValueError):
        mod.subtract_void_union_from_wall_polygon(wall, (opening,))


def test_L_legitimate_contained_boundary_touch_is_not_confused_with_clipping() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    # A door rough opening can legitimately start at z=0.  This polygon is fully
    # covered by the wall despite sharing the lower boundary; no clipping is needed.
    opening = box(1.0, 0.0, 2.0, 2.0)
    net = mod.subtract_void_union_from_wall_polygon(wall, (opening,))
    assert net.area == pytest.approx(wall.area - opening.area)


# ---------------------------------------------------------------------------
# M. ZERO / DEGENERATE GEOMETRY
# ---------------------------------------------------------------------------


def test_M_zero_area_and_non_polygon_openings_fail_closed() -> None:
    mod = _sut()
    Polygon, LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    degenerate_polygon = Polygon([(1.0, 1.0), (1.0, 2.0), (1.0, 2.0), (1.0, 1.0)])
    line = LineString([(1.0, 0.0), (1.0, 2.0)])
    for opening in (degenerate_polygon, line):
        with pytest.raises(ValueError):
            mod.subtract_void_union_from_wall_polygon(wall, (opening,))


def test_M_self_intersecting_opening_fails_closed() -> None:
    mod = _sut()
    Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    bow_tie = Polygon([(1.0, 0.0), (2.0, 2.0), (1.0, 2.0), (2.0, 0.0)])
    assert not bow_tie.is_valid
    with pytest.raises(ValueError):
        mod.subtract_void_union_from_wall_polygon(wall, (bow_tie,))


def test_M_duplicate_polygon_points_fail_closed() -> None:
    mod = _sut()
    Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    duplicate_point = Polygon(
        [(1.0, 0.0), (2.0, 0.0), (2.0, 0.0), (2.0, 2.0), (1.0, 2.0), (1.0, 0.0)]
    )
    with pytest.raises(ValueError):
        mod.subtract_void_union_from_wall_polygon(wall, (duplicate_point,))


def test_M_non_finite_geometry_fails_closed() -> None:
    mod = _sut()
    Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    candidates = []
    for bad in (math.nan, math.inf, -math.inf):
        try:
            candidates.append(Polygon([(1.0, 0.0), (bad, 0.0), (2.0, 2.0), (1.0, 2.0)]))
        except Exception:
            # Construction rejection is also safe failure.
            continue
    for candidate in candidates:
        with pytest.raises(ValueError):
            mod.subtract_void_union_from_wall_polygon(wall, (candidate,))


def test_M_zero_or_negative_scalar_dimensions_are_not_public_inputs() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {"length", "length_m", "height", "height_m", "width", "width_m"},
    )


# ---------------------------------------------------------------------------
# N. AMBIGUOUS WALL IDENTITY
# ---------------------------------------------------------------------------


def test_N_caller_candidate_set_cannot_launder_ambiguous_wall_identity() -> None:
    mod = _sut()
    forged = _ForgedGrossWall()
    forged.candidates = (
        {"physical_wall_id": "wall-A", "length_m": 10.0, "height_m": 3.0},
        {"physical_wall_id": "wall-B", "length_m": 10.0, "height_m": 3.0},
    )
    _assert_forged_gross_rejected(mod, forged)
    _assert_raw_truth_not_public(
        mod,
        {"candidates", "wall_candidates", "candidate_order", "selected_wall"},
    )


# ---------------------------------------------------------------------------
# O. ORDER INVARIANCE
# ---------------------------------------------------------------------------


def test_O_opening_order_does_not_change_union_or_net_geometry() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    openings = (
        box(1.0, 0.0, 3.0, 2.0),
        box(2.0, 0.0, 4.0, 2.0),
        box(7.0, 0.0, 8.0, 2.0),
    )
    union_a = mod.union_wall_local_void_polygons(openings)
    union_b = mod.union_wall_local_void_polygons(tuple(reversed(openings)))
    net_a = mod.subtract_void_union_from_wall_polygon(wall, openings)
    net_b = mod.subtract_void_union_from_wall_polygon(wall, tuple(reversed(openings)))
    assert union_a.equals(union_b)
    assert net_a.equals(net_b)
    assert union_a.area == pytest.approx(union_b.area)
    assert net_a.area == pytest.approx(net_b.area)


def test_O_record_id_is_order_invariant_for_authorized_opening_records() -> None:
    mod = _sut()
    selector = _selector(mod)
    forward = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-A", "deduct-B", "deduct-C"),
        physical_void_record_ids=("void-A", "void-B", "void-C"),
    )
    reverse = mod.deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-A",
        opening_deduction_record_ids=("deduct-C", "deduct-B", "deduct-A"),
        physical_void_record_ids=("void-C", "void-B", "void-A"),
    )
    assert forward == reverse


# ---------------------------------------------------------------------------
# P. REPLAY / STALE STATE
# ---------------------------------------------------------------------------


def test_P_source_or_snapshot_change_invalidates_selector_address_and_record_id() -> None:
    mod = _sut()
    old = _selector(mod, source_sha256="a" * 64, snapshot_id="snap-1")
    changed_source = _selector(mod, source_sha256="b" * 64, snapshot_id="snap-1")
    changed_snapshot = _selector(mod, source_sha256="a" * 64, snapshot_id="snap-2")

    def rid(selector):
        return mod.deterministic_net_wall_record_id(
            selector,
            gross_wall_record_id="gross-A",
            opening_deduction_record_ids=("deduct-A",),
            physical_void_record_ids=("void-A",),
        )

    assert old.key != changed_source.key
    assert old.key != changed_snapshot.key
    assert rid(old) != rid(changed_source)
    assert rid(old) != rid(changed_snapshot)


def test_P_caller_cannot_submit_precomputed_old_net_evidence_for_replay() -> None:
    mod = _sut()
    _assert_raw_truth_not_public(
        mod,
        {
            "evidence",
            "old_evidence",
            "record",
            "record_id",
            "net_geometry",
            "net_geometry_wkb_hex",
            "net_area_m2",
        },
    )


# ---------------------------------------------------------------------------
# Q. MONOTONICITY SANITY
# ---------------------------------------------------------------------------


def test_Q_legitimate_geometry_obeys_bounds_and_add_opening_monotonicity() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    a = box(1.0, 0.0, 2.0, 2.0)
    b = box(7.0, 0.0, 8.0, 2.0)
    net_zero = mod.subtract_void_union_from_wall_polygon(wall, ())
    net_one = mod.subtract_void_union_from_wall_polygon(wall, (a,))
    net_two = mod.subtract_void_union_from_wall_polygon(wall, (a, b))
    assert 0.0 <= net_two.area <= wall.area
    assert net_two.area <= net_one.area <= net_zero.area <= wall.area


def test_Q_removing_applicable_opening_cannot_decrease_net_area() -> None:
    mod = _sut()
    _Polygon, _LineString, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    a = box(1.0, 0.0, 2.0, 2.0)
    b = box(7.0, 0.0, 8.0, 2.0)
    with_two = mod.subtract_void_union_from_wall_polygon(wall, (a, b))
    with_one = mod.subtract_void_union_from_wall_polygon(wall, (a,))
    assert with_one.area >= with_two.area
