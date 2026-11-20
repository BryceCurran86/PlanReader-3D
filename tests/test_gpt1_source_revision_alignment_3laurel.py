"""Source-wide immutable revision contract for 3Laurel's independent issuers."""
from __future__ import annotations
import importlib
from pb_page_frame_shadow import revision_id_for
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_22_finish_combined_customer import issue_original_three_laurel_22_finish_customer_rows

_FAMILIES=(
    "pb_three_laurel_vinyl_floor_customer",
    "pb_three_laurel_wet_area_floor_customer",
    "pb_three_laurel_wall_tile_customer",
    "pb_three_laurel_ceiling_customer",
)

def test_all_independent_source_producers_use_same_immutable_revision():
    doc_id="live-source:"+ORIGINAL_SHA256[:32]
    expected=revision_id_for(doc_id,ORIGINAL_SHA256)
    assert expected.startswith("source_revision_")
    for name in _FAMILIES:
        module=importlib.import_module(name)
        assert module.THREE_LAUREL_REVISION_ID==expected
        assert module.THREE_LAUREL_DOCUMENT_ID==doc_id
        assert module.THREE_LAUREL_SOURCE_SHA256==ORIGINAL_SHA256

def test_real_original_22_sealed_finish_rows_use_same_source_revision():
    pdf=require_original_3laurel()
    issued=issue_original_three_laurel_22_finish_customer_rows(pdf,workspace_id=1)
    assert issued.status=="FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert issued.sealed_run is not None
    expected=revision_id_for("live-source:"+ORIGINAL_SHA256[:32],ORIGINAL_SHA256)
    assert issued.sealed_run.revision_ids==(expected,)
    verified=verify_sealed_customer_output(issued.sealed_run,issued.customer_rows)
    assert verified.customer_row_count==len(verified.verified_quantity_ids)==22
