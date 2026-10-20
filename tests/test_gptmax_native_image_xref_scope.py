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
