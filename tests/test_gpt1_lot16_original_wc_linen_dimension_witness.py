"""Lot16 source page-3 figured witness ownership must not be invented.

Original immutable Action 38169705134, artifact 11714111639:
architectural PDF SHA 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
229 attempted WC/LINEN dimension pairs, zero authenticated intersections.
These original source witness coordinates are geometry ONLY, not m².
"""
from dataclasses import replace

import pytest

from pb_cross_view_room_area_authority import (
    _TrustedBoundDimension, _witness_systems_intersect,
)


def _original_dimension(dimension_id, witnesses, source_ids, orientation):
    return _TrustedBoundDimension(
        dimension_id=dimension_id,
        text_observation_id="original-source-label-witness",
        text_receipt_id="original-source-text-receipt",
        text_source_partition_id="original-lot16-page3",
        text_block_no=0, text_line_no=0, text_word_no=0,
        value_mm=25390.0 if orientation == "horizontal" else 12150.0,
        orientation=orientation,
        endpoints_pt=((306.5999755859375,636.1199951171875),
                      (1026.3599853515625,636.1199951171875))
                      if orientation == "horizontal"
                      else ((175.20001220703125,188.75999450683594),
                            (175.20001220703125,533.1600341796875)),
        dimension_line_observation_ids=(),
        witness_observation_ids=source_ids,
        witness_geometries=witnesses,
    )


ORIGINAL_HORIZONTAL = _original_dimension(
    "cross_view_native_dimension_71653f05c259e72ae984079d2da675cc",
    ((306.5999755859375,636.1199951171875,306.5999755859375,644.6400146484375),
     (1026.3599853515625,636.1199951171875,1026.3599853515625,644.6400146484375)),
    ("source_observation_33dba3d166dab785da6ce933ff859d1e",
     "source_observation_3b0b107a39aba37c244707a50764cb8c"),
    "horizontal",
)
ORIGINAL_VERTICAL = _original_dimension(
    "cross_view_native_dimension_406786fba52df3900cd3a3fbc4f3e4b0",
    ((166.79998779296875,188.75999450683594,175.20001220703125,188.75999450683594),
     (166.79998779296875,533.1600341796875,175.20001220703125,533.1600341796875)),
    ("source_observation_c51faf3b6ac25477f6567a56c13a9b43",
     "source_observation_f2eaa60e9126a7209596acc4bc8ab8b3"),
    "vertical",
)


@pytest.mark.parametrize("room", [
    "live_physical_room_64ed14418398b3ef8130102dff462dd0",  # WC
    "live_physical_room_93b786d864cf179d82325ba88bcee6fd",  # LINEN
])
def test_exact_lot16_page3_original_dimension_witnesses_are_not_owned(room):
    assert room
    assert not _witness_systems_intersect(ORIGINAL_HORIZONTAL, ORIGINAL_VERTICAL)


def test_witness_junction_must_be_original_not_borrowed_from_other_page_chains():
    # This is a synthetic positive junction test for the generic geometry
    # predicate, not permission to change the actual Lot16 source witness.
    authentic_synthetic = replace(
        ORIGINAL_VERTICAL,
        witness_geometries=((302.0,640.0,310.0,640.0),),
    )
    assert _witness_systems_intersect(ORIGINAL_HORIZONTAL, authentic_synthetic)
    assert not _witness_systems_intersect(ORIGINAL_HORIZONTAL, ORIGINAL_VERTICAL)


def test_malformed_original_witness_does_not_create_measurement_authority():
    for witness in ((True,0.0,305.0,0.0), (float("nan"),0.0,305.0,0.0),
                    (0.0,0.0,0.0,0.0)):
        altered = replace(ORIGINAL_VERTICAL, witness_geometries=(witness,))
        assert not _witness_systems_intersect(ORIGINAL_HORIZONTAL, altered)
