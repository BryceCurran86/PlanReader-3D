"""The cross-report shadow join cannot make a host, even for an exact flank match."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from tools.diag_gptmax_pixel_host_flank_join import join_flank_pixel_evidence

PDF = b"%PDF-1.4\n% test-only bytes; no PDF parsing is assumed in the join\n"
SOURCE = sha256(PDF).hexdigest()
FLAGS = dict(host_publication_allowed=False, opening_count_publication_allowed=False,
             metric_quantity_publication_allowed=False, benchmark_accuracy=None)


def fixture():
    basis = dict(origin=[20.0, 20.0], axis=[1.0, 0.0], normal=[0.0, 1.0],
                 length=10.0, thickness=2.0)
    original = {**FLAGS, "source_sha256": SOURCE, "page_id": "3", "opening_rows": [{
        "opening_identity_id": "opening-one", "original_binding_reason_codes":
            ["host_source_unavailable"], "original_aperture_coordinate_basis": basis,
    }]}
    raw = (json.dumps(original, sort_keys=True) + "\n").encode()
    required = {**FLAGS, "source_sha256": SOURCE, "page_id": "3",
                "input_report_sha256": sha256(raw).hexdigest(),
                "original_pdf_reauthenticated": False,
                "opening_rows": [{"opening_identity_id": "opening-one",
                                  "reported_flank_geometry_available": True, "flanks": [
                    dict(role="left", axis_span_pt=[-4., 0.], normal_span_pt=[-1., 1.],
                         end_axis_coordinate_pt=0.0),
                    dict(role="right", axis_span_pt=[10., 14.], normal_span_pt=[-1., 1.],
                         end_axis_coordinate_pt=10.0),
                ]}]}
    receipts = []
    edges = []
    census = []
    for name, coords in (("pixel-left", [16., 20., 20., 20.]),
                         ("pixel-right", [30., 20., 34., 20.])):
        pixels = [int(v * 2) for v in coords]
        receipts.append({
            "source_pixels_authenticated": True,
            "proposition": "source_observation_exists",
            "physical_wall_authority": False,
            "ordinary_visible_segment_authority": False,
            "host_publication_allowed": False,
            "source_observation": {
                "observation_id": name, "source_sha256": SOURCE, "page_id": "3",
                "observation_kind": "raster_positive_pixel_run_shadow",
                "viewport_id": None, "geometry": coords,
            },
            "pixel_receipt": {
                "geometry": coords,
                "orientation": "horizontal",
                "pixel_geometry": pixels,
                "component_bbox": [pixels[0], pixels[1], pixels[2], pixels[3]],
            },
        })
        edges.append({"edge_id": "edge-" + name, "source_observation_ids": [name],
                      "experimental_w4_candidate_ids":
                          (["unproved-wall-left"] if name == "pixel-left" else [])})
        census.append({"source_observation_id": name,
                       "w2_edge_ids": ["edge-" + name],
                       "snap_collapsed_fragment_ids": []})
    pixel = {**FLAGS, "source_sha256": SOURCE, "page_id": "3",
             "ordinary_visibility_rejects_shadow_kind": True,
             "original_source_render_reauthenticated": True,
             "render_dpi": 144,
             "ordinary_source_snapshot_unchanged": True,
             "source_universe_completeness_proven": False,
             "authenticated_pixel_source_count": 2,
             "authenticated_pixel_source_records": receipts,
             "experimental_w2_w4": {
                 "host_publication_allowed": False, "physical_equivalence_proven": False,
                 "input_source_count": 2, "all_w2_edges": edges,
                 "all_snap_collapsed_fragments": [],
                 "source_parent_census": census,
                 "all_experimental_w4_candidates": [
                     {"candidate_id": "unproved-wall-left",
                      "w2_edge_ids": ["edge-pixel-left"]},
                 ],
             }}
    return raw, required, pixel


def join(raw, required, pixel, *, pdf_bytes=PDF):
    return join_flank_pixel_evidence(raw, required, pixel, expected_source_sha=SOURCE,
                                     original_pdf_bytes=pdf_bytes)


def test_both_visible_flank_pixel_candidates_remain_unpublished():
    raw, required, pixel = fixture()
    before = deepcopy((required, pixel))
    report = join(raw, required, pixel)
    rows = report["opening_rows"]
    assert len(rows) == 1
    flanks = rows[0]["flanks"]
    assert [r["role"] for r in flanks] == ["left", "right"]
    assert [[p["pixel_source_observation_id"] for p in f["pixel_run_candidates"]]
            for f in flanks] == [["pixel-left"], ["pixel-right"]]
    assert flanks[0]["pixel_run_candidates"][0]["experimental_lineage"][
        "experimental_w4_candidate_alternatives"] == ["unproved-wall-left"]
    assert flanks[1]["pixel_run_candidates"][0]["experimental_lineage"][
        "experimental_w4_candidate_alternatives"] == []
    assert all(f["first_unproved_authority"] == "ORIGINAL_VISIBLE_WALL_LINE_AUTHORITY"
               for f in flanks)
    assert not any(f["physical_host_proven"] for f in flanks)
    assert all(not candidate["host_publication_allowed"]
               for flank in flanks for candidate in flank["pixel_run_candidates"])
    assert all(report[k] is False for k in
               ("source_receipts_freshly_reauthenticated", "host_publication_allowed",
                "opening_count_publication_allowed", "metric_quantity_publication_allowed",
                "physical_equivalence_proven", "source_universe_completeness_proven"))
    assert report["benchmark_accuracy"] is None
    assert (required, pixel) == before


def test_nearby_but_not_endpoint_anchored_pixel_is_not_an_opening_host():
    raw, required, pixel = fixture()
    far = [22., 20., 26., 20.]
    record = pixel["authenticated_pixel_source_records"][0]
    record["source_observation"]["geometry"] = far
    record["pixel_receipt"]["geometry"] = far
    record["pixel_receipt"]["pixel_geometry"] = [44, 40, 52, 40]
    record["pixel_receipt"]["component_bbox"] = [44, 40, 52, 40]
    result = join(raw, required, pixel)
    left = result["opening_rows"][0]["flanks"][0]
    assert left["pixel_run_candidates"] == []
    assert left["first_unproved_authority"] == "PIXEL_SOURCE_FLANK_CANDIDATE_UNAVAILABLE"
    assert result["host_publication_allowed"] is False


@pytest.mark.parametrize("mutation", [
    "foreign_source", "foreign_page", "source_pdf_changed",
    "forged_flank_input", "pixel_claims_host", "pixel_claims_visibility",
    "pixel_claims_completeness", "changed_pixel_receipt", "missing_w2_parent",
    "duplicate_pixel_id", "duplicate_opening_id", "missing_flank",
    "bad_original_basis", "bad_original_status", "bad_pixel_count",
    "pixel_missing_experimental_graph", "pixel_extra_w2_parent",
    "pixel_unbacked_w4_member", "pixel_missing_w4_member",
    "false_flank_geometry_flag", "partial_reported_flanks",
    "wrong_w2_input_count", "missing_w2_source_parent", "malformed_w4_alternatives",
    "render_not_authenticated", "forged_physical_wall", "wrong_pixel_proposition",
    "experimental_claims_equivalence",
])
def test_corrupt_source_or_ancestry_fails_closed(mutation):
    raw, required, pixel = fixture()
    pdf_bytes = PDF
    if mutation == "foreign_source":
        pixel["source_sha256"] = "b" * 64
    elif mutation == "foreign_page":
        pixel["page_id"] = "4"
    elif mutation == "source_pdf_changed":
        pdf_bytes = b"altered source"
    elif mutation == "forged_flank_input":
        required["input_report_sha256"] = "b" * 64
    elif mutation == "pixel_claims_host":
        pixel["host_publication_allowed"] = True
    elif mutation == "pixel_claims_visibility":
        pixel["authenticated_pixel_source_records"][0][
            "ordinary_visible_segment_authority"] = True
    elif mutation == "pixel_claims_completeness":
        pixel["source_universe_completeness_proven"] = True
    elif mutation == "changed_pixel_receipt":
        pixel["authenticated_pixel_source_records"][0]["pixel_receipt"][
            "geometry"] = [0., 0., 1., 0.]
    elif mutation == "missing_w2_parent":
        pixel["experimental_w2_w4"]["source_parent_census"][0]["w2_edge_ids"] = ["missing"]
    elif mutation == "duplicate_pixel_id":
        pixel["authenticated_pixel_source_records"][1]["source_observation"][
            "observation_id"] = "pixel-left"
    elif mutation == "duplicate_opening_id":
        required["opening_rows"].append(deepcopy(required["opening_rows"][0]))
    elif mutation == "missing_flank":
        del required["opening_rows"][0]["flanks"]
    elif mutation == "bad_original_basis":
        original = json.loads(raw)
        original["opening_rows"][0]["original_aperture_coordinate_basis"]["length"] = False
        raw = (json.dumps(original, sort_keys=True) + "\n").encode()
        required["input_report_sha256"] = sha256(raw).hexdigest()
    elif mutation == "bad_original_status":
        original = json.loads(raw)
        original["host_publication_allowed"] = True
        raw = (json.dumps(original, sort_keys=True) + "\n").encode()
        required["input_report_sha256"] = sha256(raw).hexdigest()
    elif mutation == "bad_pixel_count":
        pixel["authenticated_pixel_source_count"] = 1
    elif mutation == "pixel_missing_experimental_graph":
        pixel["experimental_w2_w4"] = None
    elif mutation == "pixel_extra_w2_parent":
        pixel["experimental_w2_w4"]["all_w2_edges"][0][
            "source_observation_ids"] = ["unrelated"]
    elif mutation == "pixel_unbacked_w4_member":
        pixel["experimental_w2_w4"]["all_experimental_w4_candidates"][0][
            "w2_edge_ids"] = ["edge-pixel-right"]
    elif mutation == "pixel_missing_w4_member":
        pixel["experimental_w2_w4"]["all_experimental_w4_candidates"] = []
    elif mutation == "false_flank_geometry_flag":
        required["opening_rows"][0]["reported_flank_geometry_available"] = False
    elif mutation == "partial_reported_flanks":
        required["opening_rows"][0]["flanks"].pop()
    elif mutation == "wrong_w2_input_count":
        pixel["experimental_w2_w4"]["input_source_count"] = 3
    elif mutation == "missing_w2_source_parent":
        pixel["experimental_w2_w4"]["all_w2_edges"][0]["source_observation_ids"] = ["unknown"]
    elif mutation == "malformed_w4_alternatives":
        pixel["experimental_w2_w4"]["all_w2_edges"][0]["experimental_w4_candidate_ids"] = "unproved-wall-left"
    elif mutation == "render_not_authenticated":
        pixel["original_source_render_reauthenticated"] = False
    elif mutation == "forged_physical_wall":
        pixel["authenticated_pixel_source_records"][0]["physical_wall_authority"] = True
    elif mutation == "wrong_pixel_proposition":
        pixel["authenticated_pixel_source_records"][0]["proposition"] = "physical_wall_exists"
    elif mutation == "experimental_claims_equivalence":
        pixel["experimental_w2_w4"]["physical_equivalence_proven"] = True
    with pytest.raises((ValueError, TypeError, KeyError)):
        join(raw, required, pixel, pdf_bytes=pdf_bytes)


def test_empty_original_flanks_stay_unavailable_without_fabrication():
    raw, required, pixel = fixture()
    required["opening_rows"][0]["flanks"] = []
    required["opening_rows"][0]["reported_flank_geometry_available"] = False
    result = join(raw, required, pixel)
    assert result["opening_rows"][0]["flank_geometry_reported"] is False
    assert result["opening_rows"][0]["flanks"] == []
    assert result["host_publication_allowed"] is False


@pytest.mark.parametrize("invalid_pdf", [None, "", bytearray(b"fake"), {"sha256": SOURCE}])
def test_caller_cannot_forge_original_pdf_byte_hash(invalid_pdf):
    raw, required, pixel = fixture()
    with pytest.raises(TypeError, match="immutable bytes"):
        join(raw, required, pixel, pdf_bytes=invalid_pdf)


@pytest.mark.parametrize("mutation", [
    "wrong_render_dpi", "wrong_pixel_scale", "false_vertical_orientation",
    "component_bbox_excludes_endpoint", "negative_pixel", "boolean_pixel",
    "pixel_run_endpoints_reversed", "page_geometry_mismatch_with_same_receipt",
])
def test_reported_pixel_receipt_must_replay_complete_original_render_coordinates(mutation):
    raw, required, pixel = fixture()
    record = pixel["authenticated_pixel_source_records"][0]
    receipt = record["pixel_receipt"]
    if mutation == "wrong_render_dpi":
        pixel["render_dpi"] = 72
    elif mutation == "wrong_pixel_scale":
        receipt["pixel_geometry"][2] += 2
    elif mutation == "false_vertical_orientation":
        receipt["orientation"] = "vertical"
    elif mutation == "component_bbox_excludes_endpoint":
        receipt["component_bbox"][2] -= 1
    elif mutation == "negative_pixel":
        receipt["pixel_geometry"][0] = -1
    elif mutation == "boolean_pixel":
        receipt["pixel_geometry"][0] = True
    elif mutation == "pixel_run_endpoints_reversed":
        receipt["pixel_geometry"][0], receipt["pixel_geometry"][2] = (
            receipt["pixel_geometry"][2], receipt["pixel_geometry"][0])
    elif mutation == "page_geometry_mismatch_with_same_receipt":
        record["source_observation"]["geometry"] = [18., 20., 22., 20.]
        receipt["geometry"] = [18., 20., 22., 20.]
    with pytest.raises((ValueError, TypeError)):
        join(raw, required, pixel)
