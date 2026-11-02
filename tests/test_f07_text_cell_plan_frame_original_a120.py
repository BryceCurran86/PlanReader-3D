"""Original Maryborough A120 (page 9): the plan-frame shadow, pinned to the SHA-verified source.

Needs the private original at ``documents/sources``; in public CI the conftest policy skips it
(not a passing original-source verification). The synthetic proofs live in
``test_f07_text_cell_plan_frame_shadow.py``. Nothing here is an input to production code.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

import pb_viewport_segmentation as v

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
FLAG = "source_connected_text_cell_plan_frame_shadow"
GPT2_SHADOWS = {
    "source_connected_table_cell_shadow": True,
    "source_native_multipath_semantic_frame_shadow": True,
}

EAST_HALF = (279.84, 471.20, 1217.04, 1376.72)  # the unstroked white mask the default binds the schedule to
OUTLINE = (279.84, 470.72, 1219.44, 1926.80)  # white background rectangle spanning the building outline
RING = (571.20, 1556.96, 1217.04, 1946.48)  # the overhanging room-sized white rectangle


def _near(box, expected, tol=0.01):
    return box is not None and all(abs(a - b) <= tol for a, b in zip(box, expected))


def _by_id(views):
    return {view.view_id: view for view in views}


@pytest.fixture(scope="module")
def page9_document():
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert doc.page_count == 31
        assert doc[8].rotation == 90
        yield doc
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SHA


def test_default_output_is_unchanged_by_an_absent_or_false_flag(page9_document):
    default = v.segment_page_viewports(page9_document.load_page(8), page_number=9)
    explicit = v.segment_page_viewports(page9_document.load_page(8), page_number=9, **{FLAG: False})
    assert [v.segmented_viewport_producer_fingerprint(x) for x in default] == [
        v.segmented_viewport_producer_fingerprint(x) for x in explicit
    ]
    views = _by_id(default)
    assert views["view_p9_4"].status == "resolved" and _near(views["view_p9_4"].bounding_box, EAST_HALF)
    assert views["view_p9_5"].status == "derived"
    assert all(FLAG not in (x.provenance or {}) for x in default)


def test_shadow_resolves_the_plan_to_the_background_rectangle_and_releases_the_schedule(page9_document):
    views = _by_id(v.segment_page_viewports(page9_document.load_page(8), page_number=9, **{FLAG: True}))
    plan, schedule = views["view_p9_5"], views["view_p9_4"]
    assert plan.status == "resolved" and _near(plan.bounding_box, OUTLINE)
    assert schedule.status == "unsupported" and schedule.bounding_box is None
    receipt = plan.provenance[FLAG]
    assert sorted(tuple(round(c, 2) for c in b) for b in receipt["table_veto_lifted_frames"]) == sorted([RING, OUTLINE])
    assert len(receipt["near_nested_rival_frames"]) == 1
    rival = receipt["near_nested_rival_frames"][0]
    assert _near(rival["frame"], RING) and _near(rival["contained_in"], OUTLINE)
    # the resolved extent is an invisible fill, not a drawn frame: the receipt says so
    assert {e["ink"] for e in receipt["frame_source_ink"]} == {"unstroked_opaque_white_fill"}
    assert v.validate_non_overlapping_viewports(list(views.values()))


def test_shadow_composes_with_the_two_existing_gpt2_shadows(page9_document):
    page = page9_document.load_page(8)
    gpt2 = _by_id(v.segment_page_viewports(page, page_number=9, **GPT2_SHADOWS))
    both = _by_id(v.segment_page_viewports(page, page_number=9, **GPT2_SHADOWS, **{FLAG: True}))
    assert gpt2["view_p9_5"].status == "ambiguous"
    assert both["view_p9_5"].status == "resolved" and _near(both["view_p9_5"].bounding_box, OUTLINE)
    assert both["view_p9_4"].status == "resolved"
    assert _near(both["view_p9_4"].bounding_box, (1393.68, 416.0, 1496.4, 991.04), tol=0.05)
    assert v.validate_non_overlapping_viewports(list(both.values()))


def test_every_vector_frame_f07_sees_on_a120_is_an_unstroked_white_fill(page9_document):
    page = page9_document.load_page(8)
    calibration = v.calibrate_viewport_layout(page)
    frames = v.extract_vector_frames(page, calibration)
    assert len(frames) == 8
    assert {v._frame_source_ink_class(page, f, calibration) for f in frames} == {"unstroked_opaque_white_fill"}
    # GPT2's opt-in exclusion would therefore leave this sheet with no frame at all
    assert v.extract_vector_frames(page, calibration, exclude_opaque_white_fill_masks_shadow=True) == []


def test_the_veto_is_caused_by_an_unconnected_labelled_lattice_not_by_blank_tiles(page9_document):
    page = page9_document.load_page(8)
    calibration = v.calibrate_viewport_layout(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(OUTLINE, page, calibration)  # the legacy veto
    assert not v._frame_looks_like_source_connected_text_cell_table(OUTLINE, page, calibration, fragments)
    families = []
    centres = sorted(v._bbox_center(b) for b, _t in fragments)
    mesh = v._frame_source_edge_mesh(OUTLINE, page)

    def record(family):
        families.append((
            len(family),
            round(v._cells_text_bearing_fraction(family, centres, [c[0] for c in centres]), 3),
            sum(1 for cell in family if cell in mesh),
        ))
        return False

    v._frame_looks_like_table(OUTLINE, page, calibration, allow_line_grid_only=False, family_filter=record)
    # exactly one qualifying family: a text-bearing (1.0) lattice with no cell on a shared edge
    assert [(n, text, connected) for n, text, connected in families] == [(36, 1.0, 0)]
