"""Independent supplement for host-binding prerequisite/completeness authority.

This file extends, but does not modify, frozen host-binding validator PR #360.
It targets requirements added after that freeze: authenticated physical-opening
prerequisites, exact page compatibility, and host-wall-universe completeness
that cannot be minted from a caller/local boolean or omitted competitor set.

Exact base: 36a1f49ad92f553102101f8a2bf1d01ee45b2f52
Production files changed by this validator branch: 0.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
import math

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_hosted_opening_geometry import HostedOpeningSpan
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
from pb_physical_opening_authority import (
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY


BASE_SHA = "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"
MODULE_NAME = "pb_opening_host_binding_authority"
HAS_HOST_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_HOST_AUTHORITY,
    strict=True,
    reason="producer-owned host-binding authority absent on exact validator base",
)

DOC = "doc-host-supplement"
REV = "R1"
SHA = "c" * 64
SNAP = "snap-host-supplement"
PAGE = "1"
SCOPE = "host-scope:page-1"
Point = tuple[float, float]


def _make_wall(
    wall_id: str = "host-wall",
    *,
    y: float = 100.0,
    x0: float = 20.0,
    x1: float = 220.0,
    confidence: float = 0.8,
) -> WallCandidate:
    return WallCandidate(
        candidate_id=wall_id,
        viewport_id="vp_1",
        representation="single_line",
        centerline_pts=((x0, y), (x1, y)),
        face_a_segment_ids=(f"seg:{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}:n0", f"{wall_id}:n1"),
        junction_types=(JunctionType.L_CORNER, JunctionType.L_CORNER),
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=confidence,
    )


def _make_span(*, page: int = 1, y: float = 100.0) -> HostedOpeningSpan:
    start = (100.0, y)
    end = (140.0, y)
    return HostedOpeningSpan(
        page=page,
        host_orientation_deg=0.0,
        jamb_start=start,
        jamb_end=end,
        span_pt=math.hypot(end[0] - start[0], end[1] - start[1]),
        width_m=None,
        wall_thickness_pt=10.0,
        subtype="door_like",
        evidence_flags=(
            "host_wall_band",
            "aligned_two_face_gap",
            "jamb_boundaries_confirmed",
        ),
        reason="synthetic_validator_fixture",
    )


def _edges(walls: tuple[WallCandidate, ...]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for wall in walls:
        start = wall.centerline_pts[0]
        end = wall.centerline_pts[-1]
        for edge_id in wall.face_a_segment_ids:
            records[str(edge_id)] = {
                "id": str(edge_id),
                "x1": float(start[0]),
                "y1": float(start[1]),
                "x2": float(end[0]),
                "y2": float(end[1]),
                LINEAGE_KEY: {"source_primitive_ids": (f"src:{wall.candidate_id}",)},
            }
    return records


def _require_api():
    assert HAS_HOST_AUTHORITY, (
        "the genuine missing behavior on the validator base is a producer-owned "
        "host-binding authority that also authenticates opening prerequisites"
    )
    mod = importlib.import_module(MODULE_NAME)
    for name in (
        "OpeningHostBindingProducer",
        "OpeningHostBindingAuthority",
        "OpeningHostBindingSelector",
    ):
        assert hasattr(mod, name)
    return mod


def _publish_raw(
    *,
    opening_record_id: str,
    span: HostedOpeningSpan,
    walls: tuple[WallCandidate, ...] | None = None,
    page_id: str = PAGE,
    host_universe_complete: bool = True,
):
    """Exercise only the candidate host module's claimed trusted-writer surface."""
    mod = _require_api()
    chosen_walls = walls or (_make_wall(),)
    producer = mod.OpeningHostBindingProducer()
    result = producer.publish_scope(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        viewport_id=None,
        decision_scope_id=SCOPE,
        opening_record_id=opening_record_id,
        opening_span=span,
        walls=chosen_walls,
        edges_by_id=_edges(chosen_walls),
        source_complete=True,
        host_universe_complete=host_universe_complete,
        traversal_truncated=False,
    )
    selector = mod.OpeningHostBindingSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_record_id=opening_record_id,
    )
    resolved = producer.authority().resolve(selector)
    assert resolved == result
    return resolved


def _assert_blocked(result: object) -> None:
    assert getattr(result, "status", None) in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert getattr(result, "host_wall_id", None) is None


# ---------------------------------------------------------------------------
# Current-main facts that must remain true regardless of future host production.
# ---------------------------------------------------------------------------


def test_supplement_exact_base_is_explicit() -> None:
    assert BASE_SHA == "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"


def test_opening_existence_records_carry_exact_source_and_page_scope() -> None:
    fields = {field.name for field in dataclasses.fields(PhysicalOpeningExistenceRecord)}
    assert {
        "record_id",
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
    } <= fields


def test_opening_universe_completeness_does_not_unlock_host_or_void_caps() -> None:
    assert OpeningUniverseCompletenessProducer is not None
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["host_identity"] is False
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def test_raw_span_wall_and_opening_label_are_not_host_authority_on_main() -> None:
    wall = _make_wall()
    span = _make_span()
    assert wall.candidate_id == "host-wall"
    assert span.page == 1
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["host_binding"] is False


# ---------------------------------------------------------------------------
# Strict expected RED on current main. These are supplemental frozen attacks.
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack_s01_arbitrary_opening_id_and_raw_geometry_cannot_mint_host_binding() -> None:
    result = _publish_raw(
        opening_record_id="caller-invented-opening-id",
        span=_make_span(),
    )
    _assert_blocked(result)


@EXPECTED_RED
def test_attack_s02_opening_existence_like_id_without_proven_identity_cannot_bind() -> None:
    # A string that merely looks like an upstream existence record is not proof
    # that the exact physical opening instance identity has been established.
    result = _publish_raw(
        opening_record_id="physical-opening-existence:unverified",
        span=_make_span(),
    )
    _assert_blocked(result)


@EXPECTED_RED
@pytest.mark.parametrize(
    "caller_label",
    (
        "gap-only",
        "swing-symbol-only",
        "door-tag-D01",
        "schedule-row-D01",
        "ocr-label-door",
        "cv-detected-opening",
    ),
)
def test_attack_s03_labels_tags_schedule_rows_and_cv_ocr_ids_cannot_bind(caller_label: str) -> None:
    result = _publish_raw(opening_record_id=caller_label, span=_make_span())
    _assert_blocked(result)


@EXPECTED_RED
def test_attack_s04_page_mismatch_between_opening_geometry_and_host_scope_blocks() -> None:
    # The host writer says page 1 while the opening geometry itself says page 2.
    # A free opening id must not launder that contradiction.
    result = _publish_raw(
        opening_record_id="opening-page-2-unverified",
        span=_make_span(page=2),
        page_id="1",
    )
    _assert_blocked(result)


@EXPECTED_RED
def test_attack_s05_bare_host_complete_boolean_cannot_replace_scoped_completeness_proof() -> None:
    # A local wall slice plus True is still only a claim unless producer-owned
    # evidence proves that this exact host decision scope has no omitted rivals.
    result = _publish_raw(
        opening_record_id="caller-invented-opening-id",
        span=_make_span(),
        host_universe_complete=True,
    )
    _assert_blocked(result)


@EXPECTED_RED
def test_attack_s06_omitted_valid_competitor_cannot_manufacture_unique_host() -> None:
    visible_subset = (_make_wall("wall-a", y=100.0),)
    omitted_valid_competitor = _make_wall("wall-b", y=102.0)
    assert omitted_valid_competitor.candidate_id not in {
        wall.candidate_id for wall in visible_subset
    }
    result = _publish_raw(
        opening_record_id="caller-invented-opening-id",
        span=_make_span(y=100.0),
        walls=visible_subset,
        host_universe_complete=True,
    )
    _assert_blocked(result)


@EXPECTED_RED
def test_attack_s07_public_selector_excludes_extended_host_self_certification_fields() -> None:
    mod = _require_api()
    selector_type = mod.OpeningHostBindingSelector
    if dataclasses.is_dataclass(selector_type):
        fields = {field.name for field in dataclasses.fields(selector_type)}
    else:
        fields = {
            name
            for name in inspect.signature(selector_type).parameters
            if name != "self"
        }
    forbidden = {
        "wall_id",
        "host_wall_id",
        "nearest_wall_id",
        "candidate_wall_ids",
        "candidate_count",
        "index_hit_count",
        "radius",
        "claimed_complete",
        "host_universe_complete",
        "host_boolean",
        "confidence",
        "proof",
        "receipt",
        "wall_fingerprint",
        "opening_fingerprint",
        "opening_tag",
        "schedule_row",
        "ocr_label",
        "cv_label",
    }
    assert fields.isdisjoint(forbidden)


@EXPECTED_RED
def test_attack_s08_positive_host_module_does_not_unlock_downstream_caps() -> None:
    # Even if a host module exists, its presence alone must not change later gates.
    _require_api()
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
