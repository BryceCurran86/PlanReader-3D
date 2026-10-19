from pb_wall_length_height_quantity_shadow import assess_wall_length_height_face_shadow


def test_missing_height_blocks_face_area_without_default():
    r = assess_wall_length_height_face_shadow(
        wall_id="w1",
        length_m=3.2,
        length_authority="firm",
        height_m=None,
        height_authority=None,
    )
    assert r["first_remaining_gate"] == "wall_height_authority_unproven"
    assert r["face_area_m2_review_only"] is None
    assert r["default_height_invented"] is False
    assert r["measurement_published"] is False


def test_authenticated_length_and_height_still_review_only():
    r = assess_wall_length_height_face_shadow(
        wall_id="w1",
        length_m=3.0,
        length_authority="FIRM",
        height_m=2.7,
        height_authority="corroborated",
    )
    assert r["first_remaining_gate"] == "wall_face_area_review_only"
    assert r["face_area_m2_review_only"] == 8.1
    assert r["customer_seal_granted"] is False
