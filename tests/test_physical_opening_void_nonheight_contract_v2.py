"""Executable non-height attacks for Physical Opening Void V2.

TEST ONLY. These tests lock geometry/identity invariants that do not depend on the
separate Claude-owned positive height authority. Passing them does NOT authorize a
physical void; height and vertical placement remain mandatory external prerequisites.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.physical_opening_void_nonheight_support_v2 import (
    ReferenceVoidRectangle,
    ScopeLineageFixture,
    dedupe_reference_voids,
    diagnostic_area_or_none,
    exact_scope_matches,
    map_segment_span_to_group,
    nonheight_prerequisites_ready,
    supported_rectangular_profile,
)


def test_wrong_lineage_mutations_never_match_exact_scope() -> None:
    expected = ScopeLineageFixture(
        document_id="doc-a",
        revision_id="rev-7",
        source_sha256="sha-a",
        snapshot_id="snap-9",
        page_id="p-12",
        decision_scope_id="scope-openings",
    )
    assert exact_scope_matches(expected, expected)

    mutations = (
        replace(expected, document_id="doc-b"),
        replace(expected, revision_id="rev-8"),
        replace(expected, source_sha256="sha-b"),
        replace(expected, snapshot_id="snap-10"),
        replace(expected, page_id="p-13"),
        replace(expected, decision_scope_id="scope-other"),
    )
    assert all(not exact_scope_matches(expected, actual) for actual in mutations)


def test_split_and_merged_wall_representations_map_to_same_physical_group_span() -> None:
    merged = map_segment_span_to_group(
        segment_origin_u_m=0.0,
        segment_length_m=5.0,
        local_u0_m=1.2,
        local_u1_m=2.1,
    )
    split = map_segment_span_to_group(
        segment_origin_u_m=1.0,
        segment_length_m=2.0,
        local_u0_m=0.2,
        local_u1_m=1.1,
    )
    assert merged == pytest.approx((1.2, 2.1))
    assert split == pytest.approx(merged)


def test_reversed_split_wall_representation_maps_to_same_physical_group_span() -> None:
    forward = map_segment_span_to_group(
        segment_origin_u_m=1.0,
        segment_length_m=2.0,
        local_u0_m=0.2,
        local_u1_m=1.1,
    )
    reversed_local = map_segment_span_to_group(
        segment_origin_u_m=1.0,
        segment_length_m=2.0,
        local_u0_m=0.9,
        local_u1_m=1.8,
        reversed_orientation=True,
    )
    assert reversed_local == pytest.approx(forward)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            dict(
                segment_origin_u_m=0.0,
                segment_length_m=2.0,
                local_u0_m=-0.1,
                local_u1_m=0.8,
            ),
            "contained",
        ),
        (
            dict(
                segment_origin_u_m=0.0,
                segment_length_m=2.0,
                local_u0_m=1.2,
                local_u1_m=2.1,
            ),
            "contained",
        ),
        (
            dict(
                segment_origin_u_m=0.0,
                segment_length_m=2.0,
                local_u0_m=1.0,
                local_u1_m=1.0,
            ),
            "contained",
        ),
    ],
)
def test_split_wall_mapping_rejects_outside_or_degenerate_local_span(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        map_segment_span_to_group(**kwargs)


def test_duplicate_observation_of_same_physical_opening_yields_one_void() -> None:
    record = ReferenceVoidRectangle(
        opening_identity_id="opening-1",
        host_physical_group_id="wall-group-a",
        u0_m=1.2,
        u1_m=2.1,
        z0_m=0.9,
        z1_m=3.0,
    )
    deduped = dedupe_reference_voids((record, record))
    assert deduped == (record,)


def test_same_physical_opening_with_conflicting_geometry_fails_closed_not_first_wins() -> None:
    first = ReferenceVoidRectangle(
        opening_identity_id="opening-1",
        host_physical_group_id="wall-group-a",
        u0_m=1.2,
        u1_m=2.1,
        z0_m=0.9,
        z1_m=3.0,
    )
    conflicting = replace(first, u0_m=1.25, u1_m=2.15)
    with pytest.raises(ValueError, match="contradictory geometry"):
        dedupe_reference_voids((first, conflicting))


def test_same_size_distinct_physical_openings_remain_distinct() -> None:
    first = ReferenceVoidRectangle(
        opening_identity_id="opening-1",
        host_physical_group_id="wall-group-a",
        u0_m=1.2,
        u1_m=2.1,
        z0_m=0.9,
        z1_m=3.0,
    )
    second = ReferenceVoidRectangle(
        opening_identity_id="opening-2",
        host_physical_group_id="wall-group-a",
        u0_m=2.6,
        u1_m=3.5,
        z0_m=0.9,
        z1_m=3.0,
    )
    deduped = dedupe_reference_voids((first, second))
    assert len(deduped) == 2
    assert {record.opening_identity_id for record in deduped} == {"opening-1", "opening-2"}
    assert first.diagnostic_area_m2 == pytest.approx(second.diagnostic_area_m2)


def test_unknown_void_remains_none_never_numeric_zero() -> None:
    assert diagnostic_area_or_none(None) is None
    assert diagnostic_area_or_none(None) != 0.0


def test_diagnostic_area_is_derived_from_wall_local_geometry_not_input_truth() -> None:
    record = ReferenceVoidRectangle(
        opening_identity_id="opening-1",
        host_physical_group_id="wall-group-a",
        u0_m=1.2,
        u1_m=2.1,
        z0_m=0.9,
        z1_m=3.0,
    )
    assert record.diagnostic_area_m2 == pytest.approx(0.9 * 2.1)


@pytest.mark.parametrize("profile", [None, "arch", "arched", "irregular", "round", "polygon"])
def test_unsupported_profile_is_not_rectangular_void_authority(profile) -> None:
    assert supported_rectangular_profile(profile) is False


def test_only_explicit_rectangular_profile_is_supported_by_reference_contract() -> None:
    assert supported_rectangular_profile("rectangular") is True
    assert supported_rectangular_profile("RECTANGULAR") is False


@pytest.mark.parametrize(
    "missing_key",
    [
        "opening_identity_resolved",
        "host_binding_resolved",
        "horizontal_span_resolved",
        "width_resolved",
        "wall_local_frame_resolved",
        "unit_mapping_resolved",
        "opening_universe_complete",
        "relevant_wall_equivalence_unambiguous",
    ],
)
def test_each_nonheight_prerequisite_independently_blocks_readiness(missing_key: str) -> None:
    kwargs = dict(
        opening_identity_resolved=True,
        host_binding_resolved=True,
        horizontal_span_resolved=True,
        width_resolved=True,
        wall_local_frame_resolved=True,
        unit_mapping_resolved=True,
        opening_universe_complete=True,
        relevant_wall_equivalence_unambiguous=True,
        profile_kind="rectangular",
    )
    kwargs[missing_key] = False
    assert nonheight_prerequisites_ready(**kwargs) is False


def test_ambiguous_physical_wall_equivalence_blocks_nonheight_readiness() -> None:
    assert nonheight_prerequisites_ready(
        opening_identity_resolved=True,
        host_binding_resolved=True,
        horizontal_span_resolved=True,
        width_resolved=True,
        wall_local_frame_resolved=True,
        unit_mapping_resolved=True,
        opening_universe_complete=True,
        relevant_wall_equivalence_unambiguous=False,
        profile_kind="rectangular",
    ) is False


def test_unsupported_arch_blocks_nonheight_readiness_even_if_other_prerequisites_exist() -> None:
    assert nonheight_prerequisites_ready(
        opening_identity_resolved=True,
        host_binding_resolved=True,
        horizontal_span_resolved=True,
        width_resolved=True,
        wall_local_frame_resolved=True,
        unit_mapping_resolved=True,
        opening_universe_complete=True,
        relevant_wall_equivalence_unambiguous=True,
        profile_kind="arch",
    ) is False


def test_nonheight_ready_is_not_positive_void_authority() -> None:
    """A green non-height gate must not be mistaken for complete void authority.

    Height + authenticated vertical placement are deliberately not parameters of the
    helper and remain mandatory external prerequisites before production publication.
    """
    assert nonheight_prerequisites_ready(
        opening_identity_resolved=True,
        host_binding_resolved=True,
        horizontal_span_resolved=True,
        width_resolved=True,
        wall_local_frame_resolved=True,
        unit_mapping_resolved=True,
        opening_universe_complete=True,
        relevant_wall_equivalence_unambiguous=True,
        profile_kind="rectangular",
    ) is True
