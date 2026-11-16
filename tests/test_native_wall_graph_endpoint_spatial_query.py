"""Source-native endpoint query equivalence after the 3Laurel wall-stroke recovery.

The STRtree is an acceleration ONLY: no extra wall joins, no changing
source interval tolerances, no customer quantities.
"""
from dataclasses import dataclass
from shapely.geometry import box
from pb_new_wall_graph_diagnostic import inspect_native_wall_graph


@dataclass(frozen=True)
class Bar:
    polygon: object
    owner: int
    def native_path_indices(self):
        return (self.owner,)


def test_ten_walls_form_exactly_two_real_free_endpoints():
    strips=[Bar(box(10+i*20,40,30+i*20,42),i) for i in range(10)]
    result=inspect_native_wall_graph(strips)
    assert result.component_count==1
    assert result.largest_component_band_count==10
    assert result.largest_component_open_endpoints_pdf_pts==((10.,41.),(210.,41.))
    assert not result.measurement_authorized
    assert not result.outside_ink_filter_authorized


def test_real_t_junction_is_not_mislabeled_a_wall_end():
    strips=[
        Bar(box(10,40,110,42),1),
        Bar(box(60,42,62,100),2),
    ]
    result=inspect_native_wall_graph(strips)
    assert result.component_count==1
    # Stem at the T junction touches the first bar, only 3 ends remain.
    assert set(result.largest_component_open_endpoints_pdf_pts)=={
        (10.,41.),(110.,41.),(61.,100.)
    }


def test_disconnected_source_gap_stays_unclosed_even_at_small_distance():
    strips=[
        Bar(box(10,40,20,42),1),
        Bar(box(20.3,40,40,42),2),
    ]
    result=inspect_native_wall_graph(strips)
    assert result.component_count==2
    assert not result.second_stage_join_applied
    assert result.measurement_authorized is False
    assert result.endpoint_near_miss_total>=1


def test_many_contiguous_dark_source_bars_do_not_go_quadratic():
    # 500 already-owned walls, 1000 tips: equal exact terminal receipts.
    # This is a large regression for the source wall extraction extension.
    bars=[Bar(box(i*9.,0.,i*9.+9.,2.),i+1000) for i in range(500)]
    result=inspect_native_wall_graph(bars)
    assert result.component_count==1
    assert result.largest_component_band_count==500
    assert result.largest_component_open_endpoints_pdf_pts==((0.,1.),(4500.,1.))
    assert result.largest_component_source_paths==(tuple(range(1000,1500)))
    assert not result.measurement_authorized
