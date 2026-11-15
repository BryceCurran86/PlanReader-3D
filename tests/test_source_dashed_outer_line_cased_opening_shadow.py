"""Dashed inner + outer wall lines are openings, not doors."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import fitz
import pytest

from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_CASED_OPENING,
    collect_dashed_outer_line_cased_openings,
)
from pb_source_dashed_outer_line_cased_opening_shadow import (
    SOURCE_DASHED_OUTER_LINE_CASED_OPENING,
    apply_source_dashed_outer_line_cased_openings,
    opening_has_cased_opening_evidence,
)
from pb_source_quarter_swing_opening_kind_shadow import (
    apply_source_quarter_swing_opening_kinds,
)
from pb_source_swing_figured_width_shadow import (
    SwingFiguredWidthCallout,
    apply_source_swing_figured_widths,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import _cased_opening_room
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_source_quarter_swing_opening_kind_shadow import (
    _hosted,
    _quarter_swing_drawings,
)


def test_unique_hosted_interruption_at_the_outer_pair_is_tagged_not_kinded() -> None:
    opening = _hosted(geom=(98.0, 40.0, 100.0, 64.0), kind=None)
    composition = apply_source_dashed_outer_line_cased_openings(
        _composition(opening),
        drawings_by_page_id={"3": _cased_opening_room()},
    )
    updated = composition.canonical_openings[0]
    assert updated.opening_kind is None
    assert opening_has_cased_opening_evidence(updated)
    assert any(
        item.startswith(SOURCE_DASHED_OUTER_LINE_CASED_OPENING)
        for item in updated.evidence_ids
    )


def test_two_jamb_ticks_of_one_cased_opening_are_both_tagged() -> None:
    low = _hosted(geom=(98.0, 40.0, 100.0, 40.0), kind=None, opening_id="opening-lo")
    high = _hosted(geom=(98.0, 64.0, 100.0, 64.0), kind=None, opening_id="opening-hi")
    composition = apply_source_dashed_outer_line_cased_openings(
        _composition(low, high),
        drawings_by_page_id={"3": _cased_opening_room()},
    )
    assert opening_has_cased_opening_evidence(composition.canonical_openings[0])
    assert opening_has_cased_opening_evidence(composition.canonical_openings[1])
    assert composition.canonical_openings[0].opening_kind is None
    assert composition.canonical_openings[1].opening_kind is None


def test_two_openings_in_one_cased_box_stay_untagged() -> None:
    left = _hosted(geom=(98.0, 40.0, 100.0, 50.0), kind=None, opening_id="opening-a")
    right = _hosted(geom=(98.0, 54.0, 100.0, 64.0), kind=None, opening_id="opening-b")
    composition = apply_source_dashed_outer_line_cased_openings(
        _composition(left, right),
        drawings_by_page_id={"3": _cased_opening_room()},
    )
    assert composition.canonical_openings[0].evidence_ids == left.evidence_ids
    assert composition.canonical_openings[1].evidence_ids == right.evidence_ids


def test_cased_opening_is_not_kinded_as_a_door_by_a_nearby_swing() -> None:
    opening = replace(
        _hosted(geom=(98.0, 40.0, 100.0, 64.0), kind=None),
        evidence_ids=(
            "opening-1",
            "source_dashed_outer_line_cased_opening_abc",
        ),
    )
    drawings = list(_cased_opening_room()) + _quarter_swing_drawings()
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind is None


def test_cased_opening_does_not_take_a_stacked_2100_by_900() -> None:
    opening = replace(
        _hosted(geom=(98.0, 40.0, 100.0, 64.0), kind=None),
        evidence_ids=(
            "opening-1",
            "source_dashed_outer_line_cased_opening_abc",
        ),
    )
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings() + _cased_opening_room()},
        dimensions_by_page_id={
            "3": (
                SwingFiguredWidthCallout("native-2100", 2100.0, (70.0, 48.0, 80.0, 52.0)),
                SwingFiguredWidthCallout("native-900", 900.0, (70.0, 54.0, 80.0, 58.0)),
            )
        },
    )
    updated = composition.canonical_openings[0]
    assert updated.figured_single_axis_mm is None
    assert updated.opening_kind is None


def test_already_kinded_door_is_not_rewritten_as_a_cased_opening() -> None:
    opening = _hosted(geom=(98.0, 40.0, 100.0, 64.0), kind="door")
    composition = apply_source_dashed_outer_line_cased_openings(
        _composition(opening),
        drawings_by_page_id={"3": _cased_opening_room()},
    )
    updated = composition.canonical_openings[0]
    assert updated.opening_kind == "door"
    assert not opening_has_cased_opening_evidence(updated)


def test_original_page3_has_two_unique_wir_cased_openings() -> None:
    original = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("3Laurel original PDF not provisioned")
    with fitz.open(original) as doc:
        drawings = tuple(doc[2].get_drawings())
    found = collect_dashed_outer_line_cased_openings(drawings)
    assert len(found) == 2
    assert {item.horizontal for item in found} == {False}
    from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings

    sha = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_SHA256")
    if not sha:
        import hashlib
        sha = hashlib.sha256(Path(original).read_bytes()).hexdigest()
    rings = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=sha, page_index=2,
    )
    cased = [item for item in rings.closures if item.kind == KIND_CASED_OPENING]
    assert len(cased) == 2
