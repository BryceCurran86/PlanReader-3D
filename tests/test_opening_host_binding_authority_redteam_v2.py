"""Opening -> Host Wall Binding — current-main executable validator v2.

Exact base: 36a1f49ad92f553102101f8a2bf1d01ee45b2f52
Historical attack source: PR #334 / c1c1ad1a64e7c5c26ee85dc9455c31e4c0c8c0fc.

The historical lane predated merged opening identity, producer-bound figured
width, and opening-universe completeness.  This successor preserves its host
attack intent while updating those upstream assumptions.  Host identity and
host binding remain separate propositions, and neither may be minted by caller
wall lists, caller fingerprints, nearest/first selection, or the existence of
opening dimensions/completeness authority.

Expected production shape is a trusted writer plus a selector-only read API:
``OpeningHostBindingProducer.authority().resolve(OpeningHostBindingSelector)``.
Ordinary query callers never submit walls, geometry, host IDs, fingerprints,
completeness booleans, candidate counts, radii, or local universe lists.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect

import pytest

from pb_hosted_opening_wall_binding import bind_hosted_opening_to_walls
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_wall_room_topology_contracts import JunctionType
from pb_wall_room_topology_opening_host_binding import detect_opening_host_candidates
from pb_wall_room_topology_wall_identity_v2 import canonical_path_fingerprint
from tests.opening_host_binding_test_support_v2 import (
    BASE_SHA,
    HISTORICAL_334_HEAD,
    SHA_A,
    SHA_B,
    CallerHostBindingProbe,
    HostUniverseSlice,
    assert_host_capability_locked,
    collinear_split_points,
    continuous_host_wall,
    edge_records_for,
    flanking_host_walls,
    make_span,
    make_wall,
    parallel_competitor,
    producer_path_fingerprint,
    reverse_wall_direction,
    shuffle_walls,
    transform_polyline,
)


MODULE_NAME = "pb_opening_host_binding_authority"
HAS_HOST_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_HOST_AUTHORITY,
    strict=True,
    reason="producer-owned opening host-binding authority is absent on 36a1f49",
)

DOC = "doc-host"
REV = "R1"
SNAP = "snap-host"
PAGE = "1"
SCOPE = "host-scope:page-1"
OPENING = "physical-opening-record-1"


def _require_api():
    assert HAS_HOST_AUTHORITY, (
        "OpeningHostBindingProducer + selector-only OpeningHostBindingAuthority "
        "are the genuine missing behaviors on the validator base"
    )
    mod = importlib.import_module(MODULE_NAME)
    for name in (
        "OpeningHostBindingProducer",
        "OpeningHostBindingAuthority",
        "OpeningHostBindingSelector",
    ):
        assert hasattr(mod, name), f"missing required host-binding API: {name}"
    return mod


def _selector_fields(selector_type: type) -> set[str]:
    if dataclasses.is_dataclass(selector_type):
        return {field.name for field in dataclasses.fields(selector_type)}
    signature = inspect.signature(selector_type)
    return {name for name in signature.parameters if name != "self"}


def _host_id(result: object) -> str | None:
    direct = getattr(result, "host_wall_id", None)
    if direct:
        return str(direct)
    record = getattr(result, "record", None)
    if record is not None:
        value = getattr(record, "host_wall_id", None)
        if value:
            return str(value)
    return None


def _record_id(result: object) -> str | None:
    record = getattr(result, "record", None)
    value = getattr(record, "record_id", None) if record is not None else None
    return str(value) if value else None


def _resolve(
    universe: HostUniverseSlice,
    span,
    *,
    opening_record_id: str = OPENING,
    selector_document_id: str | None = None,
    selector_revision_id: str | None = None,
    selector_source_sha256: str | None = None,
    selector_snapshot_id: str | None = None,
    selector_scope_id: str | None = None,
):
    """Drive the future writer boundary, then query only by selector.

    ``HostUniverseSlice`` is deliberately test-side producer input.  It is never
    passed to ``authority.resolve`` and therefore cannot become a caller-side
    self-certification route.
    """

    mod = _require_api()
    producer = mod.OpeningHostBindingProducer()
    publish = getattr(producer, "publish_scope", None)
    assert callable(publish), "trusted host writer must expose publish_scope"
    publish(
        document_id=universe.document_id,
        revision_id=universe.revision_id,
        source_sha256=universe.source_sha256,
        snapshot_id=universe.snapshot_id,
        page_id=universe.page_id,
        viewport_id=universe.viewport_id,
        decision_scope_id=universe.decision_scope_id,
        opening_record_id=opening_record_id,
        opening_span=span,
        walls=universe.walls,
        edges_by_id=edge_records_for(universe.walls),
        source_complete=universe.source_complete,
        host_universe_complete=universe.claimed_complete,
        traversal_truncated=universe.traversal_truncated,
    )
    authority = producer.authority()
    assert type(authority).__name__ == "OpeningHostBindingAuthority"
    resolve_signature = inspect.signature(authority.resolve)
    assert tuple(resolve_signature.parameters) == ("selector",)
    selector = mod.OpeningHostBindingSelector(
        document_id=selector_document_id or universe.document_id,
        revision_id=selector_revision_id or universe.revision_id,
        source_sha256=selector_source_sha256 or universe.source_sha256,
        snapshot_id=selector_snapshot_id or universe.snapshot_id,
        decision_scope_id=selector_scope_id or universe.decision_scope_id,
        opening_record_id=opening_record_id,
    )
    return authority.resolve(selector)


def _assert_unique(result: object, expected_wall_id: str) -> None:
    assert getattr(result, "status", None) is EvidenceResolutionStatus.CORROBORATED
    assert _host_id(result) == expected_wall_id
    assert _record_id(result), "positive host binding must publish a producer-owned record"


def _assert_blocked(result: object) -> None:
    assert getattr(result, "status", None) in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert _host_id(result) is None


# ---------------------------------------------------------------------------
# Current-main fail-closed / firewall checks.  These stay valid after a later
# host module lands; they do not require that the module remain absent.
# ---------------------------------------------------------------------------


def test_current_main_anchor_and_historical_source_are_explicit() -> None:
    assert BASE_SHA == "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"
    assert HISTORICAL_334_HEAD == "c1c1ad1a64e7c5c26ee85dc9455c31e4c0c8c0fc"


def test_upstream_authorities_do_not_unlock_host_capabilities() -> None:
    # Completeness production is merged and constructible; its existence is not
    # host identity or host binding.
    assert OpeningUniverseCompletenessProducer is not None
    assert importlib.util.find_spec("pb_opening_dimension_authority") is not None
    assert_host_capability_locked()


def test_w7_dangling_gap_remains_ambiguous_nomination() -> None:
    left, right = flanking_host_walls()
    candidates = detect_opening_host_candidates([left, right])
    assert candidates
    assert all(item.host_status == "ambiguous_host" for item in candidates)
    assert all(len(item.candidate_wall_ids_considered) >= 2 for item in candidates)


def test_diagnostic_binder_refuses_one_sided_adjacency() -> None:
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    one_side = make_wall("one-side", ((20.0, 100.0), (100.0, 100.0)))
    result = bind_hosted_opening_to_walls(span, [one_side], viewport_id="vp_1")
    assert result.status == "unbound"
    assert result.wall_candidate_id is None


def test_first_or_smallest_candidate_id_is_not_host_authority() -> None:
    left, right = flanking_host_walls(left_id="z-wall", right_id="a-wall")
    candidates = detect_opening_host_candidates([left, right])
    assert len(candidates) == 1
    assert candidates[0].wall_candidate_id == "a-wall"
    assert candidates[0].host_status == "ambiguous_host"
    assert set(candidates[0].candidate_wall_ids_considered) == {"a-wall", "z-wall"}


def test_323_fingerprint_is_direction_and_segmentation_canonical() -> None:
    straight = ((0.0, 0.0), (100.0, 0.0))
    split = collinear_split_points(straight, (0.25, 0.5, 0.75))
    assert canonical_path_fingerprint(straight) == canonical_path_fingerprint(tuple(reversed(straight)))
    assert canonical_path_fingerprint(straight) == canonical_path_fingerprint(split)


def test_caller_local_universe_claim_does_not_change_capabilities() -> None:
    universe = HostUniverseSlice(walls=(continuous_host_wall(),), claimed_complete=True)
    assert universe.claimed_complete is True
    assert_host_capability_locked()


def test_caller_fingerprint_probe_is_only_data() -> None:
    points = ((20.0, 100.0), (220.0, 100.0))
    probe = CallerHostBindingProbe(
        opening_record_id=OPENING,
        wall_candidate_id="caller-wall",
        path_fingerprint=canonical_path_fingerprint(points),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA_A,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        claimed_complete=True,
    )
    assert probe.path_fingerprint == producer_path_fingerprint(points)
    assert probe.claimed_complete is True
    assert_host_capability_locked()


def test_host_lock_is_independent_of_dimension_and_completeness_modules() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    # These legacy publication flags are deliberately not used as assertions
    # for the now-merged separate dimension/completeness modules.
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False


def test_downstream_firewall_stays_closed_before_host_authority() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


# ---------------------------------------------------------------------------
# Strict expected RED: future producer-owned host authority behavior.
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_one_unambiguous_host_with_complete_producer_scope() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    result = _resolve(HostUniverseSlice(walls=(wall,)), span)
    _assert_unique(result, wall.candidate_id)


@EXPECTED_RED
def test_attack02_corner_door_does_not_bind_to_perpendicular_corner_leg() -> None:
    horizontal = make_wall(
        "horizontal",
        ((20.0, 100.0), (100.0, 100.0)),
        junction_types=(JunctionType.ENDPOINT, JunctionType.L_CORNER),
    )
    vertical = make_wall(
        "vertical",
        ((100.0, 100.0), (100.0, 200.0)),
        junction_types=(JunctionType.L_CORNER, JunctionType.ENDPOINT),
    )
    through = continuous_host_wall(wall_id="through-corner", x0=20.0, x1=180.0)
    span = make_span(jamb_start=(40.0, 100.0), jamb_end=(70.0, 100.0))
    result = _resolve(HostUniverseSlice(walls=(horizontal, vertical, through)), span)
    _assert_unique(result, "through-corner")


@EXPECTED_RED
def test_attack03_t_junction_stem_does_not_steal_host() -> None:
    through = continuous_host_wall(wall_id="t-through")
    stem = make_wall(
        "t-stem",
        ((120.0, 100.0), (120.0, 180.0)),
        junction_types=(JunctionType.T_JUNCTION, JunctionType.ENDPOINT),
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    _assert_unique(_resolve(HostUniverseSlice(walls=(through, stem)), span), "t-through")


@EXPECTED_RED
def test_attack04_two_competing_same_path_wall_identities_conflict() -> None:
    first = continuous_host_wall(wall_id="row-a")
    second = continuous_host_wall(wall_id="row-b")
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    _assert_blocked(_resolve(HostUniverseSlice(walls=(first, second)), span))


@EXPECTED_RED
def test_attack05_multi_wythe_cavity_blocks_without_assembly_identity() -> None:
    first = continuous_host_wall(wall_id="wythe-a", y=100.0)
    second = continuous_host_wall(wall_id="wythe-b", y=110.0)
    span = make_span(jamb_start=(100.0, 105.0), jamb_end=(140.0, 105.0))
    _assert_blocked(_resolve(HostUniverseSlice(walls=(first, second)), span))


@EXPECTED_RED
def test_attack06_collinear_segment_split_does_not_change_host() -> None:
    straight = continuous_host_wall(wall_id="seg-wall")
    segmented = make_wall(
        "seg-wall",
        collinear_split_points(straight.centerline_pts, (0.25, 0.5, 0.75)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        face_a_segment_ids=straight.face_a_segment_ids,
    )
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    first = _resolve(HostUniverseSlice(walls=(straight,)), span)
    second = _resolve(HostUniverseSlice(walls=(segmented,)), span)
    _assert_unique(first, "seg-wall")
    _assert_unique(second, "seg-wall")
    assert _record_id(first) == _record_id(second)


@EXPECTED_RED
def test_attack07_angled_wall_uses_local_axis_not_global_x() -> None:
    angled = make_wall(
        "angled",
        ((20.0, 20.0), (220.0, 120.0)),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    span = make_span(jamb_start=(100.0, 60.0), jamb_end=(140.0, 80.0))
    _assert_unique(_resolve(HostUniverseSlice(walls=(angled,)), span), "angled")


@EXPECTED_RED
def test_attack08_nearby_wall_cannot_win_and_truncated_scope_cannot_claim_unique() -> None:
    real = continuous_host_wall(wall_id="real", y=100.0)
    nearby = parallel_competitor(wall_id="nearby", y=160.0)
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    truncated = HostUniverseSlice(
        walls=(nearby,),
        claimed_complete=False,
        traversal_truncated=True,
    )
    _assert_blocked(_resolve(truncated, span))
    full = HostUniverseSlice(walls=(real, nearby))
    _assert_unique(_resolve(full, span), "real")


@EXPECTED_RED
def test_attack09_two_flanking_candidates_remain_ambiguous() -> None:
    left, right = flanking_host_walls()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    _assert_blocked(_resolve(HostUniverseSlice(walls=(left, right)), span))


@EXPECTED_RED
def test_attack10_same_geometry_different_provenance_is_not_silently_collapsed() -> None:
    first = continuous_host_wall(wall_id="id-a")
    second = continuous_host_wall(wall_id="id-b")
    assert producer_path_fingerprint(first.centerline_pts) == producer_path_fingerprint(second.centerline_pts)
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    _assert_blocked(_resolve(HostUniverseSlice(walls=(first, second)), span))


@EXPECTED_RED
def test_attack11_public_selector_excludes_self_certifying_host_inputs() -> None:
    mod = _require_api()
    fields = _selector_fields(mod.OpeningHostBindingSelector)
    required = {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "decision_scope_id",
        "opening_record_id",
    }
    assert required <= fields
    forbidden = {
        "walls",
        "wall_candidate_id",
        "host_wall_id",
        "path_fingerprint",
        "claimed_complete",
        "host_universe_complete",
        "candidate_wall_ids",
        "candidate_count",
        "radius",
        "geometry",
        "opening_span",
    }
    assert fields.isdisjoint(forbidden)
    authority_type = mod.OpeningHostBindingAuthority
    with pytest.raises((TypeError, ValueError)):
        authority_type()


@EXPECTED_RED
def test_attack12_caller_fingerprint_and_complete_flag_cannot_create_record() -> None:
    mod = _require_api()
    probe = CallerHostBindingProbe(
        opening_record_id="never-published",
        wall_candidate_id="caller-wall",
        path_fingerprint=((20.0, 100.0), (220.0, 100.0)),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA_A,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        claimed_complete=True,
    )
    producer = mod.OpeningHostBindingProducer()
    authority = producer.authority()
    selector = mod.OpeningHostBindingSelector(
        document_id=probe.document_id,
        revision_id=probe.revision_id,
        source_sha256=probe.source_sha256,
        snapshot_id=probe.snapshot_id,
        decision_scope_id=probe.decision_scope_id,
        opening_record_id=probe.opening_record_id,
    )
    _assert_blocked(authority.resolve(selector))


@EXPECTED_RED
def test_attack13_incomplete_or_truncated_host_universe_blocks_positive_binding() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    incomplete = HostUniverseSlice(walls=(wall,), claimed_complete=False)
    truncated = HostUniverseSlice(walls=(wall,), traversal_truncated=True)
    _assert_blocked(_resolve(incomplete, span))
    _assert_blocked(_resolve(truncated, span))


@EXPECTED_RED
def test_attack14_document_revision_source_snapshot_and_scope_laundering_block() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    universe = HostUniverseSlice(walls=(wall,))
    cases = (
        dict(selector_document_id="other-doc"),
        dict(selector_revision_id="R-OLD"),
        dict(selector_source_sha256=SHA_B),
        dict(selector_snapshot_id="other-snapshot"),
        dict(selector_scope_id="other-scope"),
    )
    for overrides in cases:
        _assert_blocked(_resolve(universe, span, **overrides))


@EXPECTED_RED
def test_attack15_viewport_laundering_or_local_crop_cannot_establish_unique_host() -> None:
    wall = continuous_host_wall(viewport_id="vp-child")
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    local = HostUniverseSlice(
        walls=(wall,),
        viewport_id="vp-child",
        claimed_complete=True,
    )
    _assert_blocked(_resolve(local, span))


@EXPECTED_RED
def test_attack16_input_order_direction_and_segmentation_are_deterministic() -> None:
    host = continuous_host_wall(wall_id="stable")
    competitor = parallel_competitor(wall_id="far", y=180.0)
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    record_ids: list[str] = []
    for seed in (1, 2, 3, 5, 8):
        result = _resolve(HostUniverseSlice(walls=shuffle_walls((host, competitor), seed)), span)
        _assert_unique(result, "stable")
        record_ids.append(_record_id(result) or "")
    reversed_host = reverse_wall_direction(host)
    reversed_result = _resolve(HostUniverseSlice(walls=(reversed_host, competitor)), span)
    _assert_unique(reversed_result, "stable")
    record_ids.append(_record_id(reversed_result) or "")
    assert len(set(record_ids)) == 1


@EXPECTED_RED
def test_attack17_translation_and_rotation_preserve_structural_binding() -> None:
    base_wall = continuous_host_wall(wall_id="xform")
    base_span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    base = _resolve(HostUniverseSlice(walls=(base_wall,)), base_span)
    _assert_unique(base, "xform")
    for angle, offset in ((90.0, (500.0, 20.0)), (180.0, (300.0, 400.0))):
        wall = make_wall(
            "xform",
            transform_polyline(base_wall.centerline_pts, angle_deg=angle, offset=offset),
            junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
            face_a_segment_ids=base_wall.face_a_segment_ids,
        )
        jambs = transform_polyline(
            (base_span.jamb_start, base_span.jamb_end),
            angle_deg=angle,
            offset=offset,
        )
        span = make_span(jamb_start=jambs[0], jamb_end=jambs[1], host_orientation_deg=angle)
        result = _resolve(HostUniverseSlice(walls=(wall,)), span)
        _assert_unique(result, "xform")


@EXPECTED_RED
def test_attack18_positive_host_binding_does_not_unlock_void_net_or_commercial_authority() -> None:
    wall = continuous_host_wall()
    span = make_span(jamb_start=(100.0, 100.0), jamb_end=(140.0, 100.0))
    result = _resolve(HostUniverseSlice(walls=(wall,)), span)
    _assert_unique(result, wall.candidate_id)
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
