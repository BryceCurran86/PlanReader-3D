"""Review display must show unverified source geometry without editing PDF."""
from io import BytesIO
import fitz
from PIL import Image
from pb_source_spatial_candidate_overlay import render_unverified_enclosures


def _record(path, polygon):
    return {
        "kind": "unverified_enclosed_candidate",
        "bounding_native_path_ids": [path],
        "polygon_pdf_pts": polygon,
        "status": "abstained",
        "measurement_authorized": False,
    }


def test_source_held_review_polygons_render_in_distinct_colours():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    initial_drawings = page.get_drawings()
    report = {"regions": [
        _record(7, [(20, 20), (120, 20), (120, 100), (20, 100)]),
        _record(8, [(170, 20), (270, 20), (270, 100), (170, 100)]),
    ]}
    payload = render_unverified_enclosures(page, report)
    assert payload and payload.startswith(bytes([137, 80, 78, 71]))
    image = Image.open(BytesIO(payload)).convert("RGB")
    assert image.getpixel((65, 50)) != image.getpixel((215, 50))
    assert image.getpixel((65, 50)) != (255, 255, 255)
    assert page.get_drawings() == initial_drawings


def test_unowned_and_unverified_non_candidate_geometry_not_drawn():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    unowned = _record(None, [(20, 20), (120, 20), (120, 100), (20, 100)])
    unowned["bounding_native_path_ids"] = []
    assert render_unverified_enclosures(page, {"regions": [unowned]}) is None
    assert render_unverified_enclosures(page, {"regions": [
        {"kind": "interior_enclosed_room", "bounding_native_path_ids": [1]}
    ]}) is None
    page.set_rotation(90)
    assert render_unverified_enclosures(page, {"regions": [_record(1, [(0, 0), (10, 0), (10, 10)])]}) is None
