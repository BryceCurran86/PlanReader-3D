"""The full-foreground seven-flank ledger never confuses ink with a wall host."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from tools.diag_gptmax_full_foreground_flank import full_foreground_flank_census


PDF = b"PDF source fixture bytes, not a rendered image"
SOURCE = sha256(PDF).hexdigest()
FLAGS = {"host_publication_allowed": False,
         "opening_count_publication_allowed": False,
         "metric_quantity_publication_allowed": False,
         "benchmark_accuracy": None}


def fixture():
    source = {**FLAGS, "source_sha256": SOURCE, "page_id": "1",
              "opening_rows": [{"opening_identity_id": "source-opening-one",
                "original_aperture_coordinate_basis": {
                    "origin": [20., 20.], "axis": [1., 0.], "normal": [0., 1.],
                    "length": 10., "thickness": 2.,
                }}]}
    raw = (json.dumps(source, sort_keys=True) + "\n").encode()
    required = {**FLAGS, "source_sha256": SOURCE, "page_id": "1",
       "original_pdf_reauthenticated": False,
       "input_report_sha256": sha256(raw).hexdigest(),
       "opening_rows": [{
          "opening_identity_id": "source-opening-one",
          "reported_flank_geometry_available": True,
          "flanks": [
              {"role": "left", "axis_span_pt": [-4., 0.],
               "normal_span_pt": [-1., 1.], "end_axis_coordinate_pt": 0.},
              {"role": "right", "axis_span_pt": [10., 14.],
               "normal_span_pt": [-1., 1.], "end_axis_coordinate_pt": 10.},
          ]}]}
    receipts = []
    for oid, coords in (("left", [16., 20., 20., 20.]), ("right", [30., 20., 34., 20.])):
        point = [int(value * 2) for value in coords]
        receipts.append({"source_pixels_authenticated": True,
            "ordinary_visible_segment_authority": False,
            "physical_wall_authority": False, "host_publication_allowed": False,
            "proposition": "source_observation_exists",
            "source_observation": {"observation_id": oid, "source_sha256": SOURCE,
                "page_id": "1", "observation_kind": "raster_full_foreground_run_shadow",
                "viewport_id": None, "geometry": coords},
            "pixel_receipt": {"orientation": "horizontal",
                "geometry": coords, "pixel_geometry": point, "run_pixel_count": 9,
                "foreground_sha256": "a" * 64, "scanline_sha256": "b" * 64}})
    foreground = {**FLAGS, "source_sha256": SOURCE, "page_id": "1", "render_dpi": 144,
        "inventory_kind": "all_complete_original_foreground_runs",
        "original_source_render_reauthenticated": True,
        "ordinary_visibility_rejects_shadow_kind": True,
        "ordinary_source_snapshot_unchanged": True,
        "authenticated_pixel_source_count": 2,
        "authenticated_pixel_source_records": receipts}
    return raw, required, foreground


def join(raw, required, pixels, source_bytes=PDF):
    return full_foreground_flank_census(raw, required, pixels,
        pdf_bytes=source_bytes, expected_source_sha=SOURCE)


def test_both_source_pixel_flanks_retain_complete_options_and_no_host():
    raw, required, pixels = fixture()
    previous = deepcopy((required, pixels))
    got = join(raw, required, pixels)
    flanks = got["opening_rows"][0]["flanks"]
    assert [f["role"] for f in flanks] == ["left", "right"]
    assert [[x["source_observation_id"] for x in f["pixel_run_candidates"]]
            for f in flanks] == [["left"], ["right"]]
    assert all(f["first_unproved_authority"] == "ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE"
               and not f["physical_host_proven"] for f in flanks)
    assert all(not x["visible_wall_authority_proven"]
               for f in flanks for x in f["pixel_run_candidates"])
    assert got["source_receipts_freshly_reauthenticated"] is False
    assert got["structural_source_universe_complete"] is False
    assert all(got[k] is False for k in (
        "physical_equivalence_proven", "host_publication_allowed",
        "opening_count_publication_allowed", "metric_quantity_publication_allowed"))
    assert got["benchmark_accuracy"] is None
    assert (required, pixels) == previous


@pytest.mark.parametrize("error", [
   "forged_pdf", "wrong_report_sha", "bad_pixel_kind", "bad_pixel_page",
   "duplicate_pixel_id", "wrong_run_count", "bad_pixel_coords",
   "pixel_cast_boolean", "wrong_frame_dpi", "wrong_source_polarity",
   "physical_host_promoted", "pixel_visible_promoted", "missing_end",
   "duplicate_flank_role", "partial_flank", "foreign_required_opening",
   "incomplete_source_count", "mismatched_opening_basis", "pixel_record_shift",
   "source_hash_mismatch", "invalid_scanline_digest", "stale_pixel_source",
])
def test_foreign_fabricated_or_incomplete_original_evidence_fails_closed(error):
    raw, required, pixels = fixture()
    pdf = PDF
    record = pixels["authenticated_pixel_source_records"][0]
    if error == "forged_pdf":
        pdf = b"substituted PDF"
    elif error == "wrong_report_sha":
        required["input_report_sha256"] = "0" * 64
    elif error == "bad_pixel_kind":
        record["source_observation"]["observation_kind"] = "raster_pdf_visible_segment"
    elif error == "bad_pixel_page":
        record["source_observation"]["page_id"] = "2"
    elif error == "duplicate_pixel_id":
        pixels["authenticated_pixel_source_records"][1]["source_observation"]["observation_id"] = "left"
    elif error == "wrong_run_count":
        record["pixel_receipt"]["run_pixel_count"] = 1
    elif error == "bad_pixel_coords":
        record["pixel_receipt"]["pixel_geometry"][2] += 3
    elif error == "pixel_cast_boolean":
        record["pixel_receipt"]["pixel_geometry"][0] = True
    elif error == "wrong_frame_dpi":
        pixels["render_dpi"] = 72
    elif error == "wrong_source_polarity":
        pixels["ordinary_visibility_rejects_shadow_kind"] = False
    elif error == "physical_host_promoted":
        record["physical_wall_authority"] = True
    elif error == "pixel_visible_promoted":
        record["ordinary_visible_segment_authority"] = True
    elif error == "missing_end":
        del required["opening_rows"][0]["flanks"][0]["end_axis_coordinate_pt"]
    elif error == "duplicate_flank_role":
        required["opening_rows"][0]["flanks"][1]["role"] = "left"
    elif error == "partial_flank":
        required["opening_rows"][0]["flanks"].pop()
    elif error == "foreign_required_opening":
        required["opening_rows"][0]["opening_identity_id"] = "foreign"
    elif error == "incomplete_source_count":
        pixels["authenticated_pixel_source_count"] = 3
    elif error == "mismatched_opening_basis":
        source = json.loads(raw)
        source["opening_rows"][0]["original_aperture_coordinate_basis"]["axis"] = [1., 1.]
        raw = (json.dumps(source, sort_keys=True) + "\n").encode()
        required["input_report_sha256"] = sha256(raw).hexdigest()
    elif error == "pixel_record_shift":
        record["source_observation"]["geometry"][0] = 11.
    elif error == "source_hash_mismatch":
        pixels["source_sha256"] = "0" * 64
    elif error == "invalid_scanline_digest":
        record["pixel_receipt"]["scanline_sha256"] = "m"
    elif error == "stale_pixel_source":
        pixels["original_source_render_reauthenticated"] = False
    with pytest.raises((ValueError, TypeError, KeyError)):
        join(raw, required, pixels, source_bytes=pdf)


def test_nonrepresentable_missing_flanks_remain_unavailable():
    raw, required, pixels = fixture()
    required["opening_rows"][0]["reported_flank_geometry_available"] = False
    required["opening_rows"][0]["flanks"] = []
    output = join(raw, required, pixels)
    row = output["opening_rows"][0]
    assert row["flanks"] == []
    assert row["reported_flank_geometry_available"] is False
    assert output["host_publication_allowed"] is False
