"""Supplemental variants for the independent net-wall red team.

TEST ONLY / EXPECTED RED / NEVER MERGE.
No production implementation is imported at collection time.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
import math
from typing import Any

import pytest


SUT_MODULE = "pb_net_wall_boolean_union_authority"


def _sut():
    try:
        return importlib.import_module(SUT_MODULE)
    except ModuleNotFoundError as exc:
        pytest.fail("net-wall production proposition is not available on validator base")
        raise AssertionError from exc


def _geometry():
    try:
        from shapely.geometry import Polygon, box
    except ImportError as exc:
        pytest.fail("real polygon Boolean geometry dependency is unavailable")
        raise AssertionError from exc
    return Polygon, box


def _param_names(callable_obj: Any) -> set[str]:
    return {
        name
        for name, p in inspect.signature(callable_obj).parameters.items()
        if name not in {"self", "cls"}
        and p.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    }


def _exact_shell(module_name: str, class_name: str):
    cls = getattr(importlib.import_module(module_name), class_name)
    return object.__new__(cls)


def _reject_forged_gross(mod: Any, forged: object) -> None:
    physical_void = _exact_shell(
        "pb_physical_opening_void_authority", "PhysicalOpeningVoidAuthority"
    )
    deduction = _exact_shell("pb_opening_deduction_authority", "OpeningDeductionAuthority")
    universe = _exact_shell(
        "pb_opening_universe_completeness_authority", "OpeningUniverseCompletenessAuthority"
    )
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        mod.NetWallBooleanUnionProducer.from_authorities(
            physical_void, deduction, universe, forged
        )


@dataclass
class _CrossWiredGross:
    gross_area_m2: float = 30.0
    length_m: float = 10.0
    height_m: float = 3.0
    length_physical_wall_id: str = "wall-A"
    height_physical_wall_id: str = "wall-B"
    length_document_id: str = "doc-A"
    height_document_id: str = "doc-A"
    length_revision_id: str = "rev-1"
    height_revision_id: str = "rev-1"
    length_page_id: str = "page-1"
    height_page_id: str = "page-1"
    length_viewport_id: str = "view-1"
    height_viewport_id: str = "view-1"
    length_snapshot_id: str = "snap-1"
    height_snapshot_id: str = "snap-1"


# B — explicit length/height cross-wire, including caller-asserted matching IDs.
def test_B_explicit_length_A_height_B_cross_wire_rejected() -> None:
    mod = _sut()
    forged = _CrossWiredGross()
    forged.physical_wall_id = "caller-says-same-wall"
    forged.wall_mark = "W1"
    _reject_forged_gross(mod, forged)


# C — each measurement can be internally plausible while its provenance differs.
@pytest.mark.parametrize(
    "field,value",
    [
        ("height_document_id", "doc-B"),
        ("height_revision_id", "rev-2"),
        ("height_page_id", "page-2"),
        ("height_viewport_id", "view-2"),
        ("height_snapshot_id", "snap-2"),
    ],
)
def test_C_length_height_provenance_mixing_rejected(field: str, value: str) -> None:
    mod = _sut()
    forged = _CrossWiredGross(length_physical_wall_id="wall-A", height_physical_wall_id="wall-A")
    setattr(forged, field, value)
    _reject_forged_gross(mod, forged)


# D — numerical coincidence is not frame equivalence.
def test_D_equal_numeric_polygons_in_distinct_frames_do_not_prove_equivalence() -> None:
    mod = _sut()
    _Polygon, box = _geometry()
    target_frame_polygon = box(1.0, 0.0, 2.0, 2.0)
    foreign_frame_polygon = box(1.0, 0.0, 2.0, 2.0)
    assert target_frame_polygon.equals(foreign_frame_polygon)
    public = _param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    assert public == {"selector"}
    assert not ({"frame_id", "wall_local_frame_id", "void_polygon", "void_polygons"} & public)


# E — slightly different observations of one physical opening must be identity-deduped
# before Boolean union.  Geometry alone cannot decide this equivalence.
def test_E_slightly_different_observations_are_not_safe_identity_deduplication() -> None:
    mod = _sut()
    _Polygon, box = _geometry()
    observation_a = box(1.0, 0.0, 2.0, 2.0)
    observation_b = box(1.0002, 0.0, 2.0002, 2.0)
    raw_union = mod.union_wall_local_void_polygons((observation_a, observation_b))
    assert raw_union.area > observation_a.area
    # Therefore callers must not be able to submit observation collections and ask
    # geometry proximity to decide physical identity.
    public = _param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    assert not ({"observations", "opening_observations", "marks", "void_polygons"} & public)


def test_E_multiple_marks_or_source_observations_cannot_be_caller_deduped() -> None:
    mod = _sut()
    public = _param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    assert public == {"selector"}
    assert not ({"opening_marks", "source_observations", "dedupe", "same_physical_opening"} & public)


# H — raw polygon math would happily subtract a wrong-wall polygon, so it must remain
# below the authority boundary and be fed only by authenticated host/frame joins.
def test_H_wrong_wall_polygon_plausibility_is_not_authority() -> None:
    mod = _sut()
    _Polygon, box = _geometry()
    target_wall = box(0.0, 0.0, 10.0, 3.0)
    wrong_wall_void_with_plausible_coordinates = box(1.0, 0.0, 2.0, 2.0)
    raw = mod.subtract_void_union_from_wall_polygon(
        target_wall, (wrong_wall_void_with_plausible_coordinates,)
    )
    assert raw.area < target_wall.area  # demonstrates the attack on geometry-only code
    assert _param_names(mod.NetWallBooleanUnionProducer.publish_scope) == {"selector"}


# J — changed source after a caller manifest was generated cannot be rescued by
# complete=True or a recomputed caller fingerprint.
def test_J_stale_manifest_after_source_change_is_not_authority() -> None:
    mod = _sut()

    class CallerManifest:
        complete = True
        source_sha256 = "old-source-sha"
        current_source_sha256 = "new-source-sha"
        fingerprint = "recomputed-by-caller-over-old-subset"
        opening_ids = ("opening-A",)

    forged_void = object()
    forged_deduction = object()
    forged_gross = object()
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        mod.NetWallBooleanUnionProducer.from_authorities(
            forged_void, forged_deduction, CallerManifest(), forged_gross
        )


# K — caller-generated identifiers that look cryptographic do not change type trust.
def test_K_cryptographic_looking_forgery_is_still_rejected() -> None:
    mod = _sut()

    class Forged:
        digest = "f" * 64
        fingerprint = "e" * 64
        snapshot_id = "snap-auth-looking"
        wall_id = "wall-auth-looking"
        opening_id = "opening-auth-looking"
        complete = True

    with pytest.raises((TypeError, ValueError, RuntimeError)):
        mod.NetWallBooleanUnionProducer.from_authorities(Forged(), Forged(), Forged(), Forged())


# M — gross wall itself must be a finite positive-area polygon.
def test_M_zero_area_gross_wall_fails_closed() -> None:
    mod = _sut()
    _Polygon, box = _geometry()
    zero_width = box(2.0, 0.0, 2.0, 3.0)
    with pytest.raises(ValueError):
        mod.subtract_void_union_from_wall_polygon(zero_width, ())


def test_M_non_finite_gross_wall_fails_closed() -> None:
    mod = _sut()
    Polygon, _box = _geometry()
    try:
        wall = Polygon([(0.0, 0.0), (math.inf, 0.0), (math.inf, 3.0), (0.0, 3.0)])
    except Exception:
        return
    with pytest.raises(ValueError):
        mod.subtract_void_union_from_wall_polygon(wall, ())


# O — caller-controlled ordering seams for rules/evidence/candidates are forbidden;
# producer resolution, not caller order, must determine the same proposition.
def test_O_rule_evidence_candidate_order_cannot_be_public_selection_input() -> None:
    mod = _sut()
    public = _param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    assert public == {"selector"}
    assert not (
        {
            "rule_order",
            "evidence_order",
            "candidate_order",
            "opening_order",
            "first",
            "nearest",
            "confidence",
        }
        & public
    )


# P — stale replay cannot be supplied as a precomputed result/evidence object.
def test_P_precomputed_stale_result_has_no_public_replay_seam() -> None:
    mod = _sut()
    public = _param_names(mod.NetWallBooleanUnionProducer.publish_scope)
    assert public == {"selector"}
    assert not ({"result", "evidence", "record", "net_area_m2", "net_geometry"} & public)


# Q — overlapping newly authorized openings may leave net area unchanged in the
# fully-covered overlap case, but may never increase it.
def test_Q_adding_overlapping_opening_never_increases_net_area() -> None:
    mod = _sut()
    _Polygon, box = _geometry()
    wall = box(0.0, 0.0, 10.0, 3.0)
    a = box(1.0, 0.0, 3.0, 2.0)
    b = box(2.0, 0.0, 4.0, 2.0)
    net_a = mod.subtract_void_union_from_wall_polygon(wall, (a,))
    net_ab = mod.subtract_void_union_from_wall_polygon(wall, (a, b))
    assert 0.0 <= net_ab.area <= net_a.area <= wall.area
