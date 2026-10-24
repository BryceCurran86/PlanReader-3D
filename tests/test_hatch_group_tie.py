"""Two equally large hatch groups are not one plan."""
from pb_hatch_detection_v160 import HatchCluster
from pb_wall_hatch_perimeter_correction import _largest_spatially_connected_group


def _cluster(x: float) -> HatchCluster:
    return HatchCluster(bbox=(x, 0.0, x + 10.0, 10.0))


def test_one_larger_group_stays_and_a_tie_does_not() -> None:
    larger = _largest_spatially_connected_group([_cluster(0), _cluster(20), _cluster(2000)])
    assert len(larger) == 2
    tied = _largest_spatially_connected_group(
        [_cluster(0), _cluster(20), _cluster(2000), _cluster(2020)]
    )
    assert tied == []
