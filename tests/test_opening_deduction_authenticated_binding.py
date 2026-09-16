"""GenericOpeningDeductionPipeline.bind_openings_to_walls -- no trust mechanism at all.

Every opening is unconditionally PROVISIONAL_UNBOUND. Removed, and
deliberately not replaced with any new heuristic OR any new
self-certification mechanism:
- the "exactly one wall exists" shortcut;
- bounding-box intersection as a proxy for physical hosting;
- trusting a caller-populated OpeningInstance.bound_wall_id at face value;
- a caller-supplied "authenticated" opening_id -> wall_id mapping (an
  earlier revision of this method accepted one; that was still caller
  self-certification with extra steps -- any caller able to invoke the
  method could construct {"opening-123": "wall-456"} exactly as freely as
  setting bound_wall_id directly. Naming a parameter "authenticated" does
  not authenticate it).

A genuine positive binding requires a result from a SEALED, producer-owned
authority object (see pb_opening_host_binding_authority.py) that no caller
can construct by hand. That authority is not yet reconciled and this module
does not depend on it yet (see bind_openings_to_walls' own docstring for
why). Until it exists and is wired in: NO POSITIVE HOST BINDING, ever, via
this method.
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
        "regardless of source"
    )
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_multiple_candidate_walls_abstain() -> None:
    """Several plausible walls must all abstain -- never pick first,
    nearest, or smallest."""
    walls = [WallInstance(wall_id=f"wall-{i}", gross_area_m2=10.0 * i) for i in range(1, 4)]
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    _pipeline().bind_openings_to_walls([opening], walls)
    assert opening.bound_wall_id is None
    assert opening.status is OpeningDeductionStatus.PROVISIONAL_UNBOUND


def test_a_caller_asserted_authenticated_mapping_is_not_a_real_parameter() -> None:
    """Regression guard for the exact defect found in review: a prior
    revision accepted an authenticated_host_bindings kwarg that any caller
    could populate freely. That parameter must not exist at all -- calling
    bind_openings_to_walls with it must raise, not silently ignore it."""
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=50.0)
    opening = OpeningInstance(opening_id="W1", width_m=1.0, height_m=1.5, quantity=1.0)
    try:
        _pipeline().bind_openings_to_walls(
            [opening], [wall], authenticated_host_bindings={"W1": "perimeter_walling"}
        )  # type: ignore[call-arg]
    except TypeError:
        pass
    else:
        raise AssertionError(
            "bind_openings_to_walls must not accept any caller-suppliable "
            "trust mechanism, authenticated_host_bindings or otherwise"
        )


def test_unresolved_host_prevents_deduction_publication() -> None:
    """End to end: with no trust mechanism available at all (today's only
    correct state), a wall's deduction is unresolved, and net area is
    correctly withheld (None, not zero, not gross) rather than silently
    equal to gross."""
    wall = WallInstance(wall_id="perimeter_walling", gross_area_m2=87.7)
    opening = OpeningInstance(opening_id="W1", width_m=1.72, height_m=2.1, quantity=1.0)
    pipeline = _pipeline()
    results = pipeline.deduct_openings_for_all_walls([wall], [opening])
    result = results["perimeter_walling"]
    assert result.unbound_openings
    assert result.net_area_evidence.abstained is True
    assert result.net_area_evidence.value is None
    assert result.net_area_m2 == 87.7  # best-known estimate only, not final
