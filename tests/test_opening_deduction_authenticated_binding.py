"""GenericOpeningDeductionPipeline.bind_openings_to_walls -- no heuristic binding.

Removed, and deliberately not replaced with any new heuristic:
- the "exactly one wall exists" shortcut;
- bounding-box intersection as a proxy for physical hosting;
- trusting a caller-populated OpeningInstance.bound_wall_id at face value.

The ONLY trusted source is authenticated_host_bindings (opening_id -> wall_id),
representing bindings already independently proven elsewhere (see
pb_opening_host_binding_authority.py) before this method is ever called.
Until a reconciled host-binding authority supplies that mapping, every
opening is correctly PROVISIONAL_UNBOUND, regardless of how "obvious" the
binding might look from wall count, geometry, or a pre-populated field.
"""
from __future__ import annotations

from pb_opening_deduction_pipeline import (
    GenericOpeningDeductionPipeline,
    OpeningDeductionStatus,
    OpeningInstance,
    WallInstance,
)


def _pipeline() -> GenericOpeningDeductionPipeline:
    return GenericOpeningDeductionPipeline()


def test_single_wall_does_not_automatically_establish_host() -> None:
    """A lone wall must not become the default host just because it's the
    only candidate -- that is a coincidence of scope, not proof."""
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=50.0)
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    _pipeline().bind_openings_to_walls([opening], [wall])
    assert opening.bound_wall_id is None
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_bounding_box_overlap_does_not_establish_host() -> None:
    """Geometric overlap alone is not proof of physical hosting."""
    wall = WallInstance(wall_id="wall-a", gross_area_m2=50.0, bounding_box=[0.0, 0.0, 100.0, 10.0])
    other_wall = WallInstance(wall_id="wall-b", gross_area_m2=40.0, bounding_box=[0.0, 20.0, 100.0, 30.0])
    opening = OpeningInstance(
        opening_id="W1",
        width_m=1.0,
        height_m=1.5,
        quantity=1.0,
        bounding_box=[10.0, 2.0, 20.0, 8.0],  # fully inside wall-a's bbox
    )
    _pipeline().bind_openings_to_walls([opening], [wall, other_wall])
    assert opening.bound_wall_id is None
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_caller_populated_wall_id_does_not_establish_host() -> None:
    """A caller asserting a binding is not proof of one -- even when the
    asserted wall id genuinely exists in the candidate universe."""
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=50.0)
    opening = OpeningInstance(
        opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0, bound_wall_id="perimeter_walling"
    )
    _pipeline().bind_openings_to_walls([opening], [wall])
    assert opening.bound_wall_id is None, (
        "a pre-populated bound_wall_id must be overridden to None, not trusted, "
        "when no independently authenticated binding backs it"
    )
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_multiple_candidate_walls_abstain_without_authentication() -> None:
    """Several plausible walls with no authenticated signal must all abstain
    -- never pick first, nearest, or smallest."""
    walls = [WallInstance(wall_id=f"wall-{i}", gross_area_m2=10.0 * i) for i in range(1, 4)]
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    _pipeline().bind_openings_to_walls([opening], walls)
    assert opening.bound_wall_id is None
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_authenticated_binding_is_honored() -> None:
    """The one legitimate path: a caller supplying a genuinely independently
    authenticated opening_id -> wall_id mapping is honored."""
    walls = [WallInstance(wall_id="wall-a", gross_area_m2=10.0), WallInstance(wall_id="wall-b", gross_area_m2=20.0)]
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    _pipeline().bind_openings_to_walls(
        [opening], walls, authenticated_host_bindings={"W1": "wall-b"}
    )
    assert opening.bound_wall_id == "wall-b"


def test_authenticated_binding_naming_a_nonexistent_wall_is_rejected() -> None:
    """An authenticated mapping pointing at a wall id outside the actual
    candidate universe must not be trusted either -- it can't be genuine."""
    wall = WallInstance(wall_id="wall-a", gross_area_m2=10.0)
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    _pipeline().bind_openings_to_walls(
        [opening], [wall], authenticated_host_bindings={"W1": "wall-does-not-exist"}
    )
    assert opening.bound_wall_id is None


def test_unresolved_host_prevents_deduction_publication() -> None:
    """End to end: with no authenticated binding available anywhere (today's
    live reality), a wall's deduction is unresolved, and net area is
    correctly withheld (None) rather than silently equal to gross."""
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=87.7)
    opening = OpeningInstance(opening_id="W1", width_m=1.72, height_m=2.1, quantity=1.0)
    pipeline = _pipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [opening])
    result = results["perimeter_walling"]
    assert result.unbound_openings
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.value is None
    assert result.net_area_m2 == 87.7  # best-known estimate only, not final
