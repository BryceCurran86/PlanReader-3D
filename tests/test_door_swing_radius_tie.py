"""Two equally common swing radii are not a fillet mode."""
from pb_plan_door_swing_geometry import QuarterCircleCubic, unlabeled_door_swing_count


def _hits(radius: float, count: int) -> list[QuarterCircleCubic]:
    return [QuarterCircleCubic(radius=radius, x=float(i), y=0.0, page=1) for i in range(count)]


def test_one_modal_radius_stays_and_a_tie_does_not() -> None:
    fillets = _hits(14.0, 8)
    door = _hits(40.0, 1)
    assert unlabeled_door_swing_count(fillets + door) == 1
    tied = _hits(14.0, 8) + _hits(20.0, 8) + door
    assert unlabeled_door_swing_count(tied) == 0
