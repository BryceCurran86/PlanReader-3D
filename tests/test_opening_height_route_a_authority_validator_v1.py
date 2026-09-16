"""Route A: Cross-sheet physical-opening instance registration validator."""
from __future__ import annotations

import pytest

from pb_opening_height_route_a_authority import (
    CrossSheetOpeningRegistrationProducer,
    CrossSheetOpeningRegistrationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _make_selector(
    *,
    plan_id: str = "plan_record_123",
    doc_id: str = "doc_1",
    rev_id: str = "rev_1",
    sha: str = "sha_1",
    snap_id: str = "snap_1",
    obs_id: str = "obs_1",
    scope: str = "scope_1",
) -> CrossSheetOpeningRegistrationSelector:
    return CrossSheetOpeningRegistrationSelector(
        plan_opening_record_id=plan_id,
        elevation_document_id=doc_id,
        elevation_revision_id=rev_id,
        elevation_source_sha256=sha,
        elevation_snapshot_id=snap_id,
        elevation_observation_id=obs_id,
        decision_scope_id=scope,
    )


def test_route_a_validator_is_producer_owned() -> None:
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    producer = CrossSheetOpeningRegistrationProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_make_selector())


@pytest.mark.parametrize("attack", [
    "same_width_different_opening",
    "same_tag_different_opening",
    "nearest_elevation_object",
    "mirrored_rotated_view",
    "wrong_sheet",
    "wrong_section",
    "wrong_revision",
    "wrong_source_sha",
    "wrong_snapshot",
    "caller_mapping",
    "multiple_possible_elevation_instances",
    "missing_cross_reference",
    "reused_type_mark",
    "coordinate_coincidence_alone",
])
def test_route_a_adversarial_registration_fails_closed(attack: str) -> None:
    """Every adversarial test must raise NotImplementedError against the draft contract,
    proving the interface exists but rejects production fallback."""
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    producer = CrossSheetOpeningRegistrationProducer.from_source_visibility_producer(src)
    selector = _make_selector(obs_id=f"attack_{attack}")
    with pytest.raises(NotImplementedError):
        producer.publish_scope(selector)
