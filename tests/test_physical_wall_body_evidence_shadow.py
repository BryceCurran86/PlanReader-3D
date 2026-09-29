from __future__ import annotations

import copy

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_body_evidence_shadow import (
    NEGATIVE_AMBIGUOUS_DOUBLE_LINE_PATTERN_DETECTED,
    NEGATIVE_DIMENSION_PATTERN_DETECTED,
    NEGATIVE_LOCAL_FIXTURE_PATTERN_DETECTED,
    NEGATIVE_ROOF_OR_FINISH_HATCH_PATTERN_DETECTED,
    NEGATIVE_STRUCTURAL_GRID_PATTERN_DETECTED,
    NEGATIVE_TITLE_BLOCK_OR_ANNOTATION_PATTERN_DETECTED,
    NETWORK_INCOMPLETE_FOR_SCOPE,
    OPENING_LOCAL_TOPOLOGY_PRESENT,
    PHYSICAL_WALL_BODY_CORROBORATED_LOCAL,
    PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT,
    PHYSICAL_WALL_BODY_FACE_CARDINALITY_UNSUPPORTED,
    PHYSICAL_WALL_BODY_GEOMETRY_UNAVAILABLE,
    PHYSICAL_WALL_BODY_NEGATIVE_EVIDENCE_BLOCKED,
    PHYSICAL_WALL_BODY_PARALLEL_FACES_WITHOUT_STRONG_SUPPORT,
    PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_UNAVAILABLE,
    PHYSICAL_WALL_BODY_SOURCE_PROVENANCE_INCOMPLETE,
    generate_wall_band_candidates_shadow,
    resolve_physical_wall_body_evidence_shadow,
    source_negative_reason_codes,
)


SOURCE_SHA = "a" * 64
BAND_GEOMETRY = ((0.0, 0.0), (100.0, 0.0), (100.0, 10.0), (0.0, 10.0))


def _resolve(**overrides):
    values = {
        "document_id": "doc-1",
        "revision_id": "rev-1",
        "source_sha256": SOURCE_SHA,
        "snapshot_id": "snapshot-1",
        "page_id": "page-1",
        "viewport_id": "vp-1",
        "view_scope_id": "scope-1",
        "candidate_face_ids": ("face-a", "face-b"),
        "source_observation_ids": ("obs-a", "obs-b"),
        "wall_band_geometry": BAND_GEOMETRY,
        "thickness_family_id": "thickness-family-1",
        "topology_evidence_ids": ("junction-L-1",),
    }
    values.update(overrides)
    return resolve_physical_wall_body_evidence_shadow(**values)


def test_double_face_topology_plus_thickness_corroborates_without_segmentation():
    result = _resolve()

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert PHYSICAL_WALL_BODY_CORROBORATED_LOCAL in result.reason_codes
    assert result.physical_wall_body_id is None
    assert result.view_scope_id == "scope-1"


def test_parallel_faces_alone_abstain():
    result = _resolve(
        thickness_family_id=None,
        topology_evidence_ids=(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_PARALLEL_FACES_WITHOUT_STRONG_SUPPORT in result.reason_codes
    assert PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT in result.reason_codes


def test_segmentation_cannot_substitute_for_thickness_family():
    result = _resolve(
        thickness_family_id=None,
        segmentation_support_observation_ids=("segmentation-wall-mask-1",),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_PARALLEL_FACES_WITHOUT_STRONG_SUPPORT in result.reason_codes


def test_single_face_requires_segmentation_thickness_and_two_topology_witnesses():
    result = _resolve(
        candidate_face_ids=("face-a",),
        wall_band_geometry=((0.0, 0.0), (100.0, 0.0)),
        segmentation_support_observation_ids=("segmentation-wall-mask-1",),
        topology_evidence_ids=("junction-L-1", "network-run-1"),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert PHYSICAL_WALL_BODY_CORROBORATED_LOCAL in result.reason_codes


def test_single_face_without_segmentation_abstains():
    result = _resolve(
        candidate_face_ids=("face-a",),
        wall_band_geometry=((0.0, 0.0), (100.0, 0.0)),
        topology_evidence_ids=("junction-L-1", "network-run-1"),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_UNAVAILABLE in result.reason_codes


def test_typed_negative_evidence_blocks_otherwise_strong_wall():
    result = _resolve(
        negative_evidence_ids=("negative-fixture-1",),
        negative_reason_codes=(NEGATIVE_LOCAL_FIXTURE_PATTERN_DETECTED,),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_NEGATIVE_EVIDENCE_BLOCKED in result.reason_codes
    assert NEGATIVE_LOCAL_FIXTURE_PATTERN_DETECTED in result.reason_codes


def test_ambiguous_double_line_negative_blocks_candidate():
    result = _resolve(
        negative_evidence_ids=("ambiguous-double-line-1",),
        negative_reason_codes=(
            NEGATIVE_AMBIGUOUS_DOUBLE_LINE_PATTERN_DETECTED,
        ),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert NEGATIVE_AMBIGUOUS_DOUBLE_LINE_PATTERN_DETECTED in result.reason_codes


def test_cropped_scope_allows_local_corroboration_without_completeness_claim():
    result = _resolve(network_complete_for_scope=False)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert NETWORK_INCOMPLETE_FOR_SCOPE in result.reason_codes
    assert not hasattr(result, "scope_complete")


def test_opening_local_topology_is_only_a_reason_not_opening_authority():
    result = _resolve(
        thickness_family_id=None,
        topology_evidence_ids=(),
        opening_local_topology_present=True,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_LOCAL_TOPOLOGY_PRESENT in result.reason_codes
    assert PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT in result.reason_codes


def test_record_id_and_sorted_contract_fields_are_input_order_invariant():
    left = _resolve(
        candidate_face_ids=("face-b", "face-a"),
        source_observation_ids=("obs-b", "obs-a"),
        topology_evidence_ids=("network-run-1", "junction-L-1"),
    )
    right = _resolve(
        candidate_face_ids=("face-a", "face-b"),
        source_observation_ids=("obs-a", "obs-b"),
        topology_evidence_ids=("junction-L-1", "network-run-1"),
    )

    assert left.record_id == right.record_id
    assert left.candidate_face_ids == right.candidate_face_ids == ("face-a", "face-b")
    assert left.source_observation_ids == right.source_observation_ids == ("obs-a", "obs-b")


def test_missing_source_observations_abstains():
    result = _resolve(source_observation_ids=())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_SOURCE_PROVENANCE_INCOMPLETE in result.reason_codes


def test_missing_wall_band_geometry_abstains():
    result = _resolve(wall_band_geometry=None)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_GEOMETRY_UNAVAILABLE in result.reason_codes


def test_unsupported_face_cardinality_abstains():
    result = _resolve(candidate_face_ids=("a", "b", "c"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_WALL_BODY_FACE_CARDINALITY_UNSUPPORTED in result.reason_codes


def test_invalid_source_hash_is_rejected():
    with pytest.raises(ValueError, match="source_sha256"):
        _resolve(source_sha256="not-a-hash")


def _segment(
    segment_id,
    x1,
    y1,
    x2,
    y2,
    *,
    layer="",
    dashes="",
):
    return {
        "id": segment_id,
        "kind": "line",
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "width": 1.0,
        "stroke": (0.0, 0.0, 0.0),
        "fill": None,
        "layer": layer,
        "dashes": dashes,
    }


def test_wall_band_candidate_generation_is_input_order_and_endpoint_order_invariant():
    a = _segment("face-a", 0, 0, 100, 0)
    b = _segment("face-b", 0, 10, 100, 10)
    first = generate_wall_band_candidates_shadow((a, b))

    a_reversed = _segment("face-a", 100, 0, 0, 0)
    b_reversed = _segment("face-b", 100, 10, 0, 10)
    second = generate_wall_band_candidates_shadow((b_reversed, a_reversed))

    assert len(first) == len(second) == 1
    assert first[0].candidate_id == second[0].candidate_id
    assert first[0].candidate_face_ids == second[0].candidate_face_ids
    assert first[0].wall_band_geometry == second[0].wall_band_geometry


def test_wall_band_candidate_generation_does_not_mutate_source_segments():
    segments = [
        _segment("face-a", 0, 0, 100, 0),
        _segment("face-b", 0, 10, 100, 10),
    ]
    original = copy.deepcopy(segments)

    result = generate_wall_band_candidates_shadow(segments)

    assert len(result) == 1
    assert segments == original
    assert not hasattr(result[0], "status")


def test_source_negative_reason_codes_reuse_existing_source_metadata():
    segments = (
        _segment("dim", 0, 0, 100, 0, layer="DIMENSION"),
        _segment("grid", 0, 10, 100, 10, layer="STRUCTURAL GRID"),
        _segment("title", 0, 20, 100, 20, layer="TITLE FRAME"),
        _segment("roof", 0, 30, 100, 30, layer="ROOF HATCH"),
    )

    reasons = source_negative_reason_codes(segments)

    assert NEGATIVE_DIMENSION_PATTERN_DETECTED in reasons
    assert NEGATIVE_STRUCTURAL_GRID_PATTERN_DETECTED in reasons
    assert NEGATIVE_TITLE_BLOCK_OR_ANNOTATION_PATTERN_DETECTED in reasons
    assert NEGATIVE_ROOF_OR_FINISH_HATCH_PATTERN_DETECTED in reasons
