"""No geometric/native image match may grant physical opening or W4 identity."""
import hashlib
import fitz
import pytest

from tools.diag_gptmax_native_image_xref_scope import (
    native_g17_w4_pixel_registration_shadow as audit,
    _placement,
)


def _pdf(two=False, overlap=False):
    doc = fitz.open()
    page = doc.new_page(width=220, height=120)
    img = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
    img.clear_with(50)
    page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=img)
    if two:
        other = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
        other.clear_with(100)
        page.insert_image(
            fitz.Rect(0 if overlap else 100, 0, 100 if overlap else 200, 100),
            pixmap=other,
        )
    data = doc.tobytes()
    doc.close()
    return data, hashlib.sha256(data).hexdigest()


def _edge(edge_id, coords):
    return {"edge_id": edge_id, "geometry_pdf_pts": coords}


def _audit(original, digest, a, b):
    return audit(original, expected_sha256=digest, page_id="1",
                 g17_edges=(_edge("g17", a),),
                 w4_edges=(_edge("w4", b),))


def test_one_true_original_native_xref_pixel_lattice_but_no_host():
    original, digest = _pdf()
    result = _audit(original, digest, (10., 40., 90., 40.), (20., 40.5, 80., 40.5))
    one = result["g17_edges"][0]
    assert len(one["same_image_pixel_lattice_candidates"]) == 1
    assert one["original_pixel_placement_unique"] is True
    assert one["source_native_image_xref"] is not None
    assert not result["source_parent_equivalence_granted"]
    assert not result["opening_host_granted"]
    assert not result["firm_opening_area_granted"]
    assert not result["benchmark_score_granted"]


def test_two_different_original_tiles_never_form_one_native_pixel_owner():
    original, digest = _pdf(two=True)
    result = _audit(original, digest, (60., 40., 99.8, 40.),
                    (99.0, 40.0, 130., 40.0))
    one = result["g17_edges"][0]
    assert one["same_image_pixel_lattice_candidates"] == []
    assert one["foreign_image_or_ambiguous_lattice_candidates"]
    assert not one["host_binding_granted"]


def test_overlaid_image_placement_is_ambiguous_not_elected():
    original, digest = _pdf(two=True, overlap=True)
    result = _audit(original, digest, (10., 40., 90., 40.), (20., 40., 80., 40.))
    assert result["g17_edges"][0]["source_image_placement_count"] == 2
    assert result["g17_edges"][0]["same_image_pixel_lattice_candidates"] == []


@pytest.mark.parametrize("damaged", (
    {"xref": 3, "width": 100, "height": 100, "bbox": (0., 0., 100., 100.),
     "transform": (0., 100., -100., 0., 0., 0.)},
    {"xref": 3, "width": 100, "height": 100, "bbox": (0., 0., 100., 100.),
     "transform": (90., 0., 0., 100., 0., 0.)},
    {"xref": 3, "width": 0, "height": 100, "bbox": (0., 0., 100., 100.),
     "transform": (100., 0., 0., 100., 0., 0.)},
))
def test_wrong_rotated_scaled_or_malformed_pixel_placement_abstains(damaged):
    assert _placement(damaged) is None


def test_malformed_or_duplicate_caller_edge_fails_and_source_sha_is_required():
    original, digest = _pdf()
    with pytest.raises(ValueError, match="source SHA"):
        _audit(original, "0"*64, (10., 40., 90., 40.), (20., 40., 80., 40.))
    with pytest.raises(ValueError, match="duplicated"):
        audit(original, expected_sha256=digest, page_id="1",
              g17_edges=(_edge("a",(10.,40.,90.,40.)),
                         _edge("a",(10.,40.,90.,40.))), w4_edges=())
    with pytest.raises(ValueError, match="non-axis"):
        _audit(original, digest, (10.,40.,90.,43.), (20.,40.,80.,40.))


def test_missing_original_image_owner_is_not_an_empty_source_proof():
    original, digest = _pdf()
    result = _audit(original, digest, (150.,40.,200.,40.),
                    (160.,40.,190.,40.))
    assert result["g17_edges"][0]["first_blocker"] == (
        "original_g17_single_image_placement_unproven"
    )
    assert result["g17_edges"][0]["same_image_pixel_lattice_candidates"] == []


def test_reused_same_xref_at_two_distinct_placements_is_not_shared_pixel_frame():
    """A reused PDF XObject hash cannot alias physically distinct placements."""
    doc = fitz.open()
    page = doc.new_page(width=220, height=120)
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
    image.clear_with(35)
    xref = page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=image)
    page.insert_image(fitz.Rect(100, 0, 200, 100), xref=xref)
    original = doc.tobytes()
    doc.close()
    result = _audit(
        original, hashlib.sha256(original).hexdigest(),
        (60.0, 40.0, 99.8, 40.0),
        (99.0, 40.0, 130.0, 40.0),
    )
    edge = result["g17_edges"][0]
    assert edge["source_native_image_xref"] == xref
    assert edge["same_image_pixel_lattice_candidates"] == []
    # The W4 span straddles the image seam: it cannot be owned by ONE
    # actual source XObject, even if the PDF reuses that SAME xref on
    # both sides. This ambiguity is more precise than a fabricated
    # cross-image pixel mismatch and must remain a non-hosting negative.
    assert edge["foreign_image_or_ambiguous_lattice_candidates"] == [{
        "w4_edge_id": "w4",
        "reason": "w4_native_image_ownership_ambiguous_or_missing",
    }]
    assert not result["physical_wall_equivalence_granted"]
    assert not result["opening_host_granted"]


def test_distinct_adjacent_xrefs_with_matching_dark_seam_pixels_never_share_native_owner():
    """The same dashed black marks at a tile seam are not source ancestry."""
    doc = fitz.open()
    page = doc.new_page(width=220, height=120)
    left = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
    right = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
    left.clear_with(240)
    right.clear_with(230)
    for row in (10, 11, 40, 41, 70, 71):
        for pixel in (97, 98, 99):
            left.set_pixel(pixel, row, (0, 0, 0))
        for pixel in (0, 1, 2):
            right.set_pixel(pixel, row, (0, 0, 0))
        assert left.pixel(99, row) == right.pixel(0, row)
    xref_left = page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=left)
    xref_right = page.insert_image(fitz.Rect(100, 0, 200, 100), pixmap=right)
    assert xref_left != xref_right
    original = doc.tobytes()
    doc.close()
    result = _audit(
        original, hashlib.sha256(original).hexdigest(),
        (60.0, 40.0, 99.8, 40.0),
        (100.2, 40.0, 140.0, 40.0),
    )
    edge = result["g17_edges"][0]
    assert edge["source_native_image_xref"] == xref_left
    assert edge["original_pixel_placement_unique"] is True
    assert edge["same_image_pixel_lattice_candidates"] == []
    assert edge["host_binding_granted"] is False
    assert result["source_parent_equivalence_granted"] is False
    assert result["physical_wall_equivalence_granted"] is False
    assert result["opening_count_granted"] is False
    assert result["firm_opening_area_granted"] is False
