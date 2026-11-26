"""Guided snap is a positioning aid, never a quantity authority."""
from dataclasses import asdict
import hashlib
from pathlib import Path
import shutil
import subprocess

import fitz
import pytest

from pb_guided_plan_review import ReviewScope
from pb_guided_plan_review_snap import build_review_snap_targets
from pb_native_page_frame import native_page_frame


def sample(tmp_path, rotation):
    path = tmp_path / "sheet.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.set_rotation(rotation)
        doc.save(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with fitz.open(path) as doc:
        page = doc[0]
        frame = native_page_frame(page)
        image = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False).tobytes("png")
    scope = ReviewScope(1, 2, 1, digest, hashlib.sha256(image).hexdigest())
    report = {
        "source_sha256": digest, "page_index": 0,
        "producer": "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings",
        "legacy_envelope_used": False, "quantity_authorized": False,
        "native_page_frame": asdict(frame), "preview_png_orientation": "displayed",
        "exterior_source_wall_network": {
            "unjoined_native_wall_endpoints_pdf_pts": [[100, 75], [100, 75], [-1, 0]],
            "source_endpoint_near_misses": [{"tip_pdf_pts": [100, 75]}],
        },
        "external_wall_path_points": [[200, 150], [float("inf"), 50]],
    }
    return path, scope, image, report


@pytest.mark.parametrize("rotation,expected", [
    (0, [(25,25), (50,50)]), (90, [(50,50), (75,25)]),
])
def test_source_endpoints_use_display_frame_and_dedupe(tmp_path, rotation, expected):
    path, scope, image, report = sample(tmp_path, rotation)
    targets = build_review_snap_targets(scope=scope, pdf_path=path, image_bytes=image, report=report)
    assert [(t["x"], t["y"]) for t in targets] == expected


def test_changed_preview_and_excessive_targets_refused(tmp_path):
    path, scope, image, report = sample(tmp_path, 0)
    report["page_index"] = 1
    with pytest.raises(ValueError, match="provenance"):
        build_review_snap_targets(scope=scope, pdf_path=path, image_bytes=image, report=report)
    report["page_index"] = 0
    report["external_wall_path_points"] = [[10, 10]] * 2049
    with pytest.raises(ValueError, match="Too many"):
        build_review_snap_targets(scope=scope, pdf_path=path, image_bytes=image, report=report)


def test_nearest_snap_uses_screen_pixels_and_refuses_ambiguity():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available")
    html = (Path(__file__).resolve().parents[1] /
            "planreader_line_mapper/frontend/index.html").read_text(encoding="utf-8")
    start = html.index("  function nearestReviewSnap(")
    end = html.index("  function reviewPoint(", start)
    code = html[start:end] + """
const assert = require('node:assert/strict');
const p = {x:50,y:50};
assert.deepEqual(nearestReviewSnap(p,[{x:50.5,y:50}],1000,500,10),{x:50.5,y:50});
assert.equal(nearestReviewSnap(p,[{x:50.5,y:50}],3000,500,10),null);
assert.equal(nearestReviewSnap(p,[{x:49.5,y:50},{x:50.5,y:50}],1000,500,10),null);
assert.deepEqual(nearestReviewSnap(p,[{x:50.5,y:50},{x:50.5,y:50}],1000,500,10),{x:50.5,y:50});
assert.equal(nearestReviewSnap(p,[{x:NaN,y:50},{x:101,y:50}],1000,500,10),null);
"""
    subprocess.run([node, "-e", code], check=True, timeout=10)


@pytest.mark.parametrize("rotation,point", [(0, (25,25)), (90, (75,25))])
def test_only_unresolved_post_aperture_endpoints_are_navigable(tmp_path, rotation, point):
    from pb_guided_plan_review_snap import build_review_issue_targets
    path, scope, image, report = sample(tmp_path, rotation)
    unmatched = "unmatched_raw_wall_ink_terminal_needs_post_opening_review"
    report["source_wall_endpoint_aperture_review"] = {"endpoint_reviews": [
        {"status": unmatched, "endpoint_pdf_pts": [100,75]},
        {"status": unmatched, "endpoint_pdf_pts": [100,75]},
        {"status": "source_hosted_aperture_terminal_candidate", "endpoint_pdf_pts": [200,150]},
        {"status": "source_post_aperture_union_covers_terminal_not_missing_wall", "endpoint_pdf_pts": [200,100]},
        {"status": "source_internal_wall_terminal_not_outer_face", "endpoint_pdf_pts": [50,50]},
        {"status": "source_exclusion_or_joinery_terminal_not_outer_face", "endpoint_pdf_pts": [30,30]},
        {"status": "ambiguous_competing_hosted_apertures", "endpoint_pdf_pts": [-1,50]},
    ]}
    locations = build_review_issue_targets(scope=scope, pdf_path=path,
                                         image_bytes=image, report=report)
    assert len(locations) == 1
    assert (locations[0]["x"], locations[0]["y"]) == point
    assert locations[0]["label"] == "Unmatched wall endpoint"
    assert locations == build_review_issue_targets(scope=scope, pdf_path=path,
                                                  image_bytes=image, report=report)
    report["source_wall_endpoint_aperture_review"]["endpoint_reviews"] = []
    assert build_review_issue_targets(scope=scope, pdf_path=path,
                                      image_bytes=image, report=report) == []


def test_issue_focus_scroll_centres_and_clamps_edges():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available")
    html = (Path(__file__).resolve().parents[1] /
            "planreader_line_mapper/frontend/index.html").read_text(encoding="utf-8")
    start = html.index("  function reviewFocusScroll(")
    end = html.index("  function render(", start)
    code = html[start:end] + """
const assert = require('node:assert/strict');
assert.deepEqual(reviewFocusScroll({x:50,y:50},2000,1000,800,400),{left:600,top:300});
assert.deepEqual(reviewFocusScroll({x:0,y:100},2000,1000,800,400),{left:0,top:600});
assert.deepEqual(reviewFocusScroll({x:100,y:0},500,300,800,400),{left:0,top:0});
"""
    subprocess.run([node, "-e", code], check=True, timeout=10)
