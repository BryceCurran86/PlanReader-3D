from pb_w4_candidate_id_collision_shadow import build_w4_candidate_id_collision_shadow


def test_distinct_geometry_under_shared_id_is_retained_not_merged():
    report = build_w4_candidate_id_collision_shadow([
        {
            "wall_candidate_id": "wall_shared",
            "centerline_pts": ((0.0, 0.0), (5.0, 0.0)),
            "source_primitive_ids": ("split_2296",),
        },
        {
            "wall_candidate_id": "wall_shared",
            "centerline_pts": ((10.0, 0.0), (15.0, 0.0)),
            "source_primitive_ids": ("split_9744",),
        },
    ])
    assert report["collision_count"] == 1
    row = report["collisions"][0]
    assert row["collision_kind"] == "distinct_geometry_under_shared_wall_candidate_id"
    assert row["distinct_fingerprint_count"] == 2
    assert row["merged_into_single_physical_wall"] is False
    assert row["last_write_wins_applied"] is False
    assert report["host_granted"] is False


def test_identical_duplicate_address_is_typed_separately():
    pts = ((0.0, 0.0), (5.0, 0.0))
    report = build_w4_candidate_id_collision_shadow([
        {"wall_candidate_id": "wall_a", "centerline_pts": pts, "source_primitive_ids": ("s1",)},
        {"wall_candidate_id": "wall_a", "centerline_pts": pts, "source_primitive_ids": ("s1",)},
    ])
    assert report["collisions"][0]["collision_kind"] == "duplicate_identical_wall_candidate_address"


def test_unique_ids_produce_no_collision():
    report = build_w4_candidate_id_collision_shadow([
        {"wall_candidate_id": "a", "centerline_pts": ((0, 0), (1, 0)), "source_primitive_ids": ()},
        {"wall_candidate_id": "b", "centerline_pts": ((2, 0), (3, 0)), "source_primitive_ids": ()},
    ])
    assert report["collision_count"] == 0
    assert report["records_retained"] is True
