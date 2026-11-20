"""14 source-native door review records are NOT customer opening quantities."""
from pathlib import Path
import pytest

from pb_three_laurel_internal_door_source_review import (
    review_original_three_laurel_internal_door_source,
)
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_exact_original_recovers_each_hinge_and_cavity_width_and_2100_note():
    source = require_original_3laurel()
    review = review_original_three_laurel_internal_door_source(source)
    assert review.status == "SOURCE_NATIVE_REVIEW_ONLY"
    assert review.source_sha256 == ORIGINAL_SHA256
    assert len(review.witnesses) == 14
    assert sorted(x.width_mm for x in review.witnesses
                  if x.kind=="hinged_swing") == [720]+[870]*7
    assert sorted(x.width_mm for x in review.witnesses
                  if x.kind=="cavity_slider") == [720]*3+[870]*2+[1200]
    assert len({x.width_word_index for x in review.witnesses})==14
    assert all(x.noted_height_mm==2100 and
               x.joinery_height_note_pages==(4,5) for x in review.witnesses)
    assert all(x.commercial_quantity_authorized is False
               and x.physical_opening_authenticated is False for x in review.witnesses)
    assert review.frozen_score_updated is False
    assert review.opening_area_customer_authorized is False
    # The 25.011 m2 arithmetic is labelled source-width×joinery-note REVIEW
    # only, not an approved wall-face deduction or true customer total.
    assert abs(sum(x.source_width_height_area_preview_m2 for x in review.witnesses)-25.011)<1e-8


def test_original_source_door_review_rejects_missing_and_fake_pdf(tmp_path):
    missing=review_original_three_laurel_internal_door_source(tmp_path/"unknown.pdf")
    assert missing.status=="ABSTAIN"
    assert missing.witnesses==()
    fake=tmp_path/"fake.pdf"
    fake.write_bytes(b"fabricated plan data, not SHA-verified source")
    result=review_original_three_laurel_internal_door_source(fake)
    assert result.status=="ABSTAIN"
    assert result.witnesses==()
    assert result.reasons==("original_source_sha_mismatch",)


def test_wrong_source_link_is_not_followed(tmp_path):
    target=tmp_path/"source.pdf"
    target.write_bytes(b"not the source")
    link=tmp_path/"alias.pdf"
    try: link.symlink_to(target)
    except (NotImplementedError,OSError): pytest.skip("symlinks unavailable")
    assert review_original_three_laurel_internal_door_source(link).status=="ABSTAIN"
