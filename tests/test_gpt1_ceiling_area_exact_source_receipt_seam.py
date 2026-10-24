"""Original ceiling quantity lineage cannot be repaired by text trimming."""
from __future__ import annotations
from dataclasses import replace
import pytest
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from tests.test_live_ceiling_area_quantity_publication import _ceiling,_shadow_quantity,_result,SOURCE_SHA


@pytest.mark.parametrize("key,forged",[
    ("upstream_area_quantity_id"," qty-room-area-1"),
    ("upstream_area_quantity_id","qty-room-area-1 "),
    ("upstream_area_quantity_id",True),
    ("upstream_area_quantity_id",None),
    ("source_sha256"," "+SOURCE_SHA),
    ("source_sha256",SOURCE_SHA+" "),
    ("source_sha256",True),
    ("source_sha256",None),
    ("revision_id","rev-1 "),
    ("revision_id"," rev-1"),
    ("revision_id",True),
    ("revision_id",None),
])
def test_ceiling_final_m2_never_launders_padded_or_untyped_source_receipt(key,forged):
    src=_shadow_quantity()
    bad=replace(src,metadata={**src.metadata,key:forged})
    assert publish_live_ceiling_area_quantities(_result(shadow=bad))==()


def test_canonical_uppercase_original_sha_is_accepted_without_whitespace():
    src=_shadow_quantity()
    uppercase=replace(src,metadata={**src.metadata,"source_sha256":SOURCE_SHA.upper()})
    final=publish_live_ceiling_area_quantities(_result(shadow=uppercase))
    assert len(final)==1
    assert final[0].value==13.270425


def test_exact_upstream_area_source_receipt_remains_firm_but_not_commercial():
    final=publish_live_ceiling_area_quantities(_result())
    assert len(final)==1
    assert final[0].metadata["commercial_projection_allowed"] is False
    assert final[0].value==13.270425
