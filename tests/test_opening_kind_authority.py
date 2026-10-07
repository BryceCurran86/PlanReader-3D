from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_kind_authority import (
    OPENING_KIND_CONFLICT,
    OPENING_KIND_CORROBORATED,
    OPENING_KIND_LABEL,
    OPENING_KIND_STRUCTURAL_DOOR,
    OPENING_KIND_STRUCTURAL_WINDOW,
    OPENING_KIND_UNAVAILABLE,
    resolve_opening_kind,
)
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)


def test_structural_door_pattern_classifies_without_schedule() -> None:
    result = resolve_opening_kind(
        structural_pattern=GAP_CORROBORATED_DOOR_JAMB_LEAF,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.opening_kind == "door"
    assert result.structural_kind == "door"
    assert result.schedule_kind is None
    assert OPENING_KIND_STRUCTURAL_DOOR in result.reason_codes
    assert OPENING_KIND_CORROBORATED in result.reason_codes


def test_raster_swing_structural_pattern_classifies_as_door() -> None:
    result = resolve_opening_kind(
        structural_pattern=RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.opening_kind == "door"
    assert result.structural_kind == "door"
    assert OPENING_KIND_STRUCTURAL_DOOR in result.reason_codes
    assert OPENING_KIND_CORROBORATED in result.reason_codes


def test_structural_window_pattern_classifies_without_schedule() -> None:
    result = resolve_opening_kind(
        structural_pattern=GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.opening_kind == "window"
    assert result.structural_kind == "window"
    assert result.schedule_kind is None
    assert OPENING_KIND_STRUCTURAL_WINDOW in result.reason_codes


def test_bound_schedule_can_classify_generic_structural_opening() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        schedule_trade_type="doors",
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.opening_kind == "door"
    assert result.structural_kind is None
    assert result.schedule_kind == "door"


def test_schedule_and_structure_must_agree() -> None:
    result = resolve_opening_kind(
        structural_pattern=GAP_CORROBORATED_WINDOW_JAMB_PAIR,
        schedule_trade_type="doors",
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.opening_kind is None
    assert result.structural_kind == "window"
    assert result.schedule_kind == "door"
    assert OPENING_KIND_CONFLICT in result.reason_codes


def test_unknown_structure_and_no_bound_schedule_abstains() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.opening_kind is None
    assert result.reason_codes == (OPENING_KIND_UNAVAILABLE,)


def test_arbitrary_label_like_text_cannot_create_kind() -> None:
    result = resolve_opening_kind(
        structural_pattern="D1",
        schedule_trade_type="door-ish",
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.opening_kind is None


def test_source_bound_label_can_classify_generic_physical_opening() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind="door",
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.opening_kind == "door"
    assert result.structural_kind is None
    assert result.schedule_kind is None
    assert result.label_kind == "door"
    assert OPENING_KIND_LABEL in result.reason_codes


def test_label_and_structural_kind_must_agree() -> None:
    result = resolve_opening_kind(
        structural_pattern=GAP_CORROBORATED_WINDOW_JAMB_PAIR,
        label_kind="door",
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.opening_kind is None
    assert result.structural_kind == "window"
    assert result.label_kind == "door"
    assert OPENING_KIND_CONFLICT in result.reason_codes


def test_label_and_bound_schedule_must_agree() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        schedule_trade_type="windows",
        label_kind="door",
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.opening_kind is None
    assert result.schedule_kind == "window"
    assert result.label_kind == "door"


def test_arbitrary_label_kind_still_cannot_create_semantics() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind="vsd-ish",
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.opening_kind is None
