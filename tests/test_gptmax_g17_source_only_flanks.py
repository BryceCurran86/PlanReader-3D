"""Synthetic source-only G17 flank shadow; no host or quantity authority."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_g17_source_only_flanks import source_only_closed_flanks


def _row(name, kind, geometry):
    return {
        "observation_id": name,
        "observation_kind": kind,
        "geometry_pdf_pts": geometry,
        "source_primitive_ref": "visible:" + name,
        "authenticated_source_parents": [
            {"observation_id": "original-parent:" + name},
        ],
        "exact_source_ref_w4_candidates": [],
    }


def receipt():
    return {
        "source_sha256": "a" * 64,
        "physical_opening_id": "physical-opening-source",
        "host_status": "abstained",
        "host_granted": False,
        "metric_quantity_granted": False,
        "source_g17_observations": [
            _row("l1", "raster_wall_band_face", [10, 1, 20, 1]),
            _row("l2", "raster_wall_band_face", [10, 3, 20, 3]),
            _row("le", "raster_wall_band_end", [20, 1, 20, 3]),
            _row("r1", "raster_wall_band_face", [30, 1, 80, 1]),
            _row("r2", "raster_wall_band_face", [30, 4, 80, 4]),
            _row("re", "raster_wall_band_end", [30, 1, 30, 4]),
            _row("ink", "raster_thin_ink_run", [25, 1, 25, 4]),
        ],
    }


def test_closed_original_faces_ends_nominate_only_source_and_do_not_mutate():
    r = receipt()
    prior = deepcopy(r)
    result = source_only_closed_flanks(r)
    assert r == prior
    assert result["closed_source_flank_nomination"] is True
    assert result["source_flank_boxes"] == [
        {
            "side_in_original_source_order": "first",
            "orientation": "horizontal",
            "source_bbox_pdf_pts": [10, 1, 20, 3],
            "source_observation_ids": ["l1", "l2", "le"],
        },
        {
            "side_in_original_source_order": "second",
            "orientation": "horizontal",
            "source_bbox_pdf_pts": [30, 1, 80, 4],
            "source_observation_ids": ["r1", "r2", "re"],
        },
    ]
    for field in ("physical_host_granted", "opening_height_or_count_granted",
                  "metric_quantity_granted", "customer_publication_granted",
                  "benchmark_score_granted"):
        assert result[field] is False


@pytest.mark.parametrize("damage", [
    "missing_end", "wrong_end", "face_cross_mismatch",
    "gap_closed", "opposite_axis", "invalid_face_split",
])
def test_partial_or_source_opposed_face_end_topology_stays_unavailable(damage):
    r = receipt()
    if damage == "missing_end":
        r["source_g17_observations"] = [v for v in r["source_g17_observations"]
                                        if v["observation_id"] != "le"]
    elif damage == "wrong_end":
        r["source_g17_observations"][2]["geometry_pdf_pts"] = [21, 1, 21, 3]
    elif damage == "face_cross_mismatch":
        r["source_g17_observations"][3]["geometry_pdf_pts"] = [30, 10, 80, 10]
        r["source_g17_observations"][4]["geometry_pdf_pts"] = [30, 12, 80, 12]
        r["source_g17_observations"][5]["geometry_pdf_pts"] = [30, 10, 30, 12]
    elif damage == "gap_closed":
        r["source_g17_observations"][3]["geometry_pdf_pts"] = [20, 1, 80, 1]
        r["source_g17_observations"][4]["geometry_pdf_pts"] = [20, 4, 80, 4]
        r["source_g17_observations"][5]["geometry_pdf_pts"] = [20, 1, 20, 4]
    elif damage == "opposite_axis":
        r["source_g17_observations"][3]["geometry_pdf_pts"] = [30, 1, 30, 80]
        r["source_g17_observations"][4]["geometry_pdf_pts"] = [32, 1, 32, 80]
        r["source_g17_observations"][5]["geometry_pdf_pts"] = [30, 1, 32, 1]
    else:
        r["source_g17_observations"][1]["geometry_pdf_pts"] = [10, 3, 18, 3]
    result = source_only_closed_flanks(r)
    assert result["source_flank_boxes"] == []
    assert result["closed_source_flank_nomination"] is False
    assert result["physical_host_granted"] is False


@pytest.mark.parametrize("damage", [
    "foreign_parent", "duplicate_id", "invalid_geometry", "host_promoted",
    "quantity_promoted", "missing_original_source", "bad_source_sha",
])
def test_forged_or_promoted_source_fails_closed(damage):
    r = receipt()
    if damage == "foreign_parent":
        r["source_g17_observations"][0]["authenticated_source_parents"] = []
    elif damage == "duplicate_id":
        r["source_g17_observations"][1]["observation_id"] = "l1"
    elif damage == "invalid_geometry":
        r["source_g17_observations"][0]["geometry_pdf_pts"] = [10, 1, float("nan"), 1]
    elif damage == "host_promoted":
        r["host_granted"] = True
    elif damage == "quantity_promoted":
        r["metric_quantity_granted"] = True
    elif damage == "missing_original_source":
        r["source_g17_observations"] = []
    else:
        r["source_sha256"] = ""
    with pytest.raises(ValueError):
        source_only_closed_flanks(r)


def test_raster_vertical_orientation_original_source_closes_without_axis_guess():
    r = receipt()
    source = r["source_g17_observations"]
    # Geometry rotation: (x,y) -> (-y,x). Source caps and both flanks rotate.
    for item in source:
        x0, y0, x1, y1 = item["geometry_pdf_pts"]
        item["geometry_pdf_pts"] = [-y0, x0, -y1, x1]
        # Canonicalize ordered endpoints to satisfy original segment schema.
        a, b, c, d = item["geometry_pdf_pts"]
        if item["observation_kind"] == "raster_wall_band_face" and b > d:
            item["geometry_pdf_pts"] = [c, d, a, b]
        elif item["observation_kind"] == "raster_wall_band_end" and a > c:
            item["geometry_pdf_pts"] = [c, d, a, b]
    # Original source order and caps are still required; any mirrored end
    # orientation conflict may abstain but can never elect a wall owner.
    result = source_only_closed_flanks(r)
    assert result["physical_host_granted"] is False
    assert result["metric_quantity_granted"] is False
